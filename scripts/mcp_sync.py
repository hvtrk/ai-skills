#!/usr/bin/env python3
"""MCP Multi-Harness Sync.

Reads the canonical, harness-agnostic MCP server manifest (mcp/servers.json)
and syncs it out to each agent harness's own config file format, the same way
setup.sh syncs skills/ out via its HARNESS_REGISTRY. See ADR 0003 and
mcp/README.md for the design and safety model.

Safety model (see mcp/README.md):
1. Only entries tagged "_managedBy": "ai-skills" are ever added, updated, or
   removed. Hand-added entries in the same config file are never touched.
2. Every write is preceded by a timestamped backup of the target file.
3. Default mode is dry-run; real writes require --apply.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
DEFAULT_MANIFEST = REPO_ROOT / "mcp" / "servers.json"
MANAGED_BY = "ai-skills"

VALID_TRANSPORTS = ("stdio", "http", "sse")
ENV_PLACEHOLDER_PATTERN = re.compile(r"^\$\{([A-Za-z_][A-Za-z0-9_]*)\}$")


class ManifestError(ValueError):
    """Raised when mcp/servers.json is structurally invalid."""


# -----------------------------------------------------------------------------
# Harness Registry (mirrors setup.sh's HARNESS_REGISTRY, MCP-specific)
# -----------------------------------------------------------------------------


def _claude_transform(server: dict[str, Any]) -> dict[str, Any]:
    entry: dict[str, Any] = {"_managedBy": MANAGED_BY}
    if server["transport"] == "stdio":
        entry["command"] = server["command"]
        entry["args"] = server.get("args", [])
        if server.get("env"):
            entry["env"] = server["env"]
    else:
        entry["type"] = server["transport"]
        entry["url"] = server["url"]
    return entry


def _opencode_transform(server: dict[str, Any]) -> dict[str, Any]:
    entry: dict[str, Any] = {"_managedBy": MANAGED_BY, "enabled": True}
    if server["transport"] == "stdio":
        entry["type"] = "local"
        entry["command"] = [server["command"], *server.get("args", [])]
        if server.get("env"):
            entry["environment"] = server["env"]
    else:
        entry["type"] = "remote"
        entry["url"] = server["url"]
    return entry


def _antigravity_transform(server: dict[str, Any]) -> dict[str, Any]:
    # Mirrors the Claude/common MCP-client shape; this repo's own convention
    # for Antigravity, same status as its existing ~/.gemini/config/skills path.
    return _claude_transform(server)


HARNESS_REGISTRY: dict[str, dict[str, Any]] = {
    "claude": {
        "display_name": "Claude Code",
        "config_path": Path.home() / ".claude.json",
        "key": "mcpServers",
        "transform": _claude_transform,
    },
    "opencode": {
        "display_name": "OpenCode",
        "config_path": Path.home() / ".config" / "opencode" / "opencode.json",
        "key": "mcp",
        "transform": _opencode_transform,
    },
    "antigravity": {
        "display_name": "Google Antigravity",
        "config_path": Path.home() / ".gemini" / "config" / "mcp.json",
        "key": "mcpServers",
        "transform": _antigravity_transform,
    },
}


# -----------------------------------------------------------------------------
# Manifest loading & validation
# -----------------------------------------------------------------------------


def load_manifest(manifest_path: Path) -> list[dict[str, Any]]:
    if not manifest_path.is_file():
        raise ManifestError(f"manifest not found: {manifest_path}")

    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ManifestError(f"manifest is not valid JSON: {exc}") from exc

    servers = data.get("servers", [])
    if not isinstance(servers, list):
        raise ManifestError("manifest 'servers' must be a list")

    seen_names: set[str] = set()
    for i, server in enumerate(servers):
        if not isinstance(server, dict):
            raise ManifestError(f"servers[{i}] must be an object")
        name = server.get("name")
        if not name or not isinstance(name, str):
            raise ManifestError(f"servers[{i}] missing required 'name'")
        if name in seen_names:
            raise ManifestError(f"duplicate server name: {name}")
        seen_names.add(name)

        transport = server.get("transport")
        if transport not in VALID_TRANSPORTS:
            raise ManifestError(
                f"server '{name}': transport must be one of {VALID_TRANSPORTS}"
            )
        if transport == "stdio" and not server.get("command"):
            raise ManifestError(f"server '{name}': stdio transport requires 'command'")
        if transport in ("http", "sse") and not server.get("url"):
            raise ManifestError(f"server '{name}': {transport} transport requires 'url'")

    return servers


def servers_for_harness(servers: list[dict[str, Any]], harness_key: str) -> list[dict[str, Any]]:
    return [s for s in servers if not s.get("harnesses") or harness_key in s["harnesses"]]


def resolve_server_env(server: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of server with any "${VAR}" env values resolved from the
    local environment. The manifest itself must only ever contain the
    placeholder, never the real secret — this is what keeps real credentials
    out of mcp/servers.json (and out of git) while still landing in the local,
    untracked, per-machine harness config file at sync time.
    """
    env = server.get("env")
    if not env:
        return server

    resolved_env: dict[str, str] = {}
    for k, v in env.items():
        match = ENV_PLACEHOLDER_PATTERN.match(v) if isinstance(v, str) else None
        if not match:
            resolved_env[k] = v
            continue
        var_name = match.group(1)
        real_value = os.environ.get(var_name)
        if real_value is None:
            raise ManifestError(
                f"server '{server.get('name')}': env var '{var_name}' referenced by "
                f"'{k}: \"{v}\"' is not set in the local environment"
            )
        resolved_env[k] = real_value

    return {**server, "env": resolved_env}


# -----------------------------------------------------------------------------
# Diff & merge
# -----------------------------------------------------------------------------


def read_harness_config(config_path: Path) -> dict[str, Any]:
    if not config_path.is_file():
        return {}
    text = config_path.read_text(encoding="utf-8")
    if not text.strip():
        return {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ManifestError(f"{config_path}: existing config is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ManifestError(f"{config_path}: existing config root must be an object")
    return data


def compute_sync(
    existing_config: dict[str, Any],
    key: str,
    desired_entries: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, str]]:
    """Return (new_config, change_summary) without mutating existing_config."""
    new_config = dict(existing_config)
    section = dict(new_config.get(key, {}))

    changes: dict[str, str] = {}
    for name, entry in desired_entries.items():
        if name in section and section[name].get("_managedBy") != MANAGED_BY:
            changes[name] = "SKIPPED (unmanaged entry with same name already exists)"
            continue
        if name not in section:
            changes[name] = "ADD"
        elif section[name] != entry:
            changes[name] = "UPDATE"
        else:
            changes[name] = "UNCHANGED"
        section[name] = entry

    for name in list(section.keys()):
        if name not in desired_entries and section[name].get("_managedBy") == MANAGED_BY:
            changes[name] = "REMOVE"
            del section[name]

    new_config[key] = section
    return new_config, changes


def backup_file(path: Path) -> Path | None:
    if not path.is_file():
        return None
    backup_path = path.with_suffix(path.suffix + f".bak.{int(time.time())}")
    shutil.copy2(path, backup_path)
    return backup_path


def sync_harness(
    harness_key: str,
    servers: list[dict[str, Any]],
    manifest_path: Path,
    apply: bool,
) -> dict[str, Any]:
    harness = HARNESS_REGISTRY[harness_key]
    config_path: Path = harness["config_path"]
    key: str = harness["key"]
    transform = harness["transform"]

    relevant = servers_for_harness(servers, harness_key)
    resolved = [resolve_server_env(s) for s in relevant]
    desired_entries = {s["name"]: transform(s) for s in resolved}

    existing_config = read_harness_config(config_path)
    new_config, changes = compute_sync(existing_config, key, desired_entries)

    result: dict[str, Any] = {
        "harness": harness_key,
        "display_name": harness["display_name"],
        "config_path": str(config_path),
        "changes": changes,
        "applied": False,
        "backup_path": None,
    }

    effective_changes = {
        n: c
        for n, c in changes.items()
        if c != "UNCHANGED" and not c.startswith("SKIPPED")
    }
    if apply and effective_changes:
        backup_path = backup_file(config_path)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps(new_config, indent=2) + "\n", encoding="utf-8")
        result["applied"] = True
        result["backup_path"] = str(backup_path) if backup_path else None

    return result


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------


def cmd_list(args: argparse.Namespace) -> int:
    servers = load_manifest(Path(args.manifest))
    payload = {
        "manifest": str(Path(args.manifest)),
        "servers": servers,
        "harnesses": {
            k: {"display_name": v["display_name"], "config_path": str(v["config_path"])}
            for k, v in HARNESS_REGISTRY.items()
        },
    }
    if args.format == "json":
        print(json.dumps(payload, indent=2))
    else:
        print(f"Manifest: {payload['manifest']} ({len(servers)} server(s))")
        for s in servers:
            print(f"  - {s['name']} [{s['transport']}] -> {s.get('harnesses') or 'all harnesses'}")
        print("Harness destinations:")
        for k, v in HARNESS_REGISTRY.items():
            print(f"  - {v['display_name']} ({k}): {v['config_path']}")
    return 0


def cmd_sync(args: argparse.Namespace) -> int:
    servers = load_manifest(Path(args.manifest))

    if args.all:
        targets = list(HARNESS_REGISTRY.keys())
    else:
        if args.harness not in HARNESS_REGISTRY:
            print(
                f"error: unknown harness '{args.harness}', choose from {list(HARNESS_REGISTRY)}",
                file=sys.stderr,
            )
            return 2
        targets = [args.harness]

    results = [sync_harness(h, servers, Path(args.manifest), args.apply) for h in targets]

    if args.format == "json":
        print(json.dumps({"apply": args.apply, "results": results}, indent=2))
    else:
        mode = "APPLY" if args.apply else "DRY-RUN"
        for r in results:
            print(f"[{mode}] {r['display_name']} ({r['config_path']})")
            if not r["changes"]:
                print("  (no servers targeted for this harness)")
            for name, change in r["changes"].items():
                if change == "UNCHANGED":
                    continue
                print(f"  {change}: {name}")
            if r["applied"]:
                print(f"  written; backup at {r['backup_path']}" if r["backup_path"] else "  written (no prior file to back up)")
        if not args.apply:
            print("\nDry-run only — no files were written. Re-run with --apply to write.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="MCP Multi-Harness Sync")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST), help="path to mcp/servers.json")

    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="show the canonical manifest and harness destinations")
    p_list.set_defaults(func=cmd_list)

    p_sync = sub.add_parser("sync", help="sync manifest servers into harness config(s)")
    p_sync.add_argument("harness", nargs="?", help="harness key (e.g. claude, opencode, antigravity)")
    p_sync.add_argument("--all", action="store_true", help="sync all registered harnesses")
    p_sync.add_argument("--apply", action="store_true", help="write changes (default is dry-run)")
    p_sync.set_defaults(func=cmd_sync)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except ManifestError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
