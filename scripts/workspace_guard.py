#!/usr/bin/env python3
"""Workspace Activation Guardrail.

Enforces read-only state on ai-skills repo at rest via OS-level chmod.
Only the active harness session (Claude Code, Codex, Antigravity, or manual)
can make changes. See ADR 0004 for the complete design and threat model.

Safety model:
1. Lock state is a holder-list in .workspace-lock.json (machine-local, git-ignored).
2. Only entries with live holders or recent activation_at timestamps count as "active".
3. Stale holders (>12h old, or dead PID on same hostname) are pruned automatically.
4. Activate locks in holders (makes tree writable), deactivate removes holders.
5. Tree is read-only if no live holders exist.
6. chmod applies to entire repo tree including .git/ (needed to block git commits).
7. The script itself is never locked out: read/execute bits are never stripped.

Subcommands:
  status [--json]       Report lock state and holders
  activate              Activate this harness session; make tree writable
  deactivate            Deactivate this session; potentially relock tree
  check                 Quiet check for PreToolUse hook (exit 0 if unlocked, 2 if locked)
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import socket
import stat
import sys
import time
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
LOCK_FILE = REPO_ROOT / ".workspace-lock.json"
WRITE_BITS = stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH  # 0o222
STALE_AFTER_SECONDS = 12 * 60 * 60
VALID_HARNESSES = ("claude", "codex", "antigravity", "manual")
EXEMPT_PATHS = {LOCK_FILE}


class GuardError(RuntimeError):
    """Lock-state or filesystem error that should exit non-zero."""


# =============================================================================
# Pure Functions (testable, no filesystem I/O)
# =============================================================================


def compute_desired_mode(current_mode: int, writable: bool) -> int:
    """Compute desired file mode, toggling only write bits.

    Read and execute bits are always preserved. This guarantees that:
    - Scripts remain readable and executable regardless of lock state.
    - Directories remain traversable regardless of lock state.
    - No path needs to be exempted to keep itself runnable.
    """
    write_bits = WRITE_BITS
    if writable:
        return (current_mode & ~write_bits) | stat.S_IWUSR
    return current_mode & ~write_bits


def is_stale_holder(holder: dict, now: float | None = None) -> bool:
    """Check if a holder is stale (unreachable or expired).

    A holder is stale if:
    - Its activated_at is older than STALE_AFTER_SECONDS, OR
    - It's on a DIFFERENT host and its PID is unreachable (cross-machine orphan).

    On the same host, recent holders are trusted even if PID is dead, because
    the activation subprocess exits immediately after updating the lock file,
    but the harness session holds the lock until SessionEnd.
    """
    now = now if now is not None else time.time()
    activated_at = holder.get("activated_at", 0)

    if now - activated_at > STALE_AFTER_SECONDS:
        return True

    if holder.get("hostname") != socket.gethostname():
        pid = holder.get("pid")
        if pid:
            try:
                os.kill(pid, 0)
            except OSError:
                return True
    return False


def prune_stale_holders(holders: list[dict], now: float | None = None) -> list[dict]:
    """Remove stale holders from the list."""
    return [h for h in holders if not is_stale_holder(h, now)]


def make_holder(harness: str, session_id: str | None) -> dict:
    """Create a new holder record."""
    return {
        "harness": harness,
        "session_id": session_id,
        "hostname": socket.gethostname(),
        "user": getpass.getuser(),
        "pid": os.getpid(),
        "activated_at": time.time(),
    }


def compute_activation(
    record: dict | None,
    harness: str,
    session_id: str | None,
    force: bool = False,
) -> tuple[dict, bool]:
    """Compute new lock state after activation.

    Returns (new_record, needs_fs_unlock).
    - needs_fs_unlock=True if tree was fully locked and needs chmod to writable.
    - needs_fs_unlock=False if tree already had live holders (sibling session).
    """
    holders = prune_stale_holders((record or {}).get("holders", []))
    needs_fs_unlock = not holders

    if holders and not force:
        conflicting = [h for h in holders if h["harness"] != harness]
        if conflicting:
            other = conflicting[0]
            raise GuardError(
                f"repo already held by harness='{other['harness']}' "
                f"session='{other.get('session_id')}' pid={other.get('pid')} "
                f"on {other.get('hostname')}; use --force to override "
                "(get user confirmation first)"
            )

    if force:
        holders = []

    holders = [h for h in holders if h.get("session_id") != session_id or session_id is None]
    holders.append(make_holder(harness, session_id))
    return {"status": "active", "holders": holders, "updated_at": time.time()}, needs_fs_unlock


def compute_deactivation(
    record: dict | None,
    harness: str | None = None,
    session_id: str | None = None,
) -> tuple[dict, bool]:
    """Compute new lock state after deactivation.

    Returns (new_record, needs_fs_lock).
    - With session_id: remove that specific session from this harness.
    - With only harness: remove all sessions of that harness.
    - With neither: clear all holders (manual escape hatch).
    - needs_fs_lock=True if holder list is now empty (tree should relock).
    """
    holders = prune_stale_holders((record or {}).get("holders", []))

    if session_id:
        holders = [h for h in holders if h.get("session_id") != session_id]
    elif harness:
        holders = [h for h in holders if h.get("harness") != harness]
    else:
        holders = []

    needs_fs_lock = not holders
    status = "active" if holders else "locked"
    return {"status": status, "holders": holders, "updated_at": time.time()}, needs_fs_lock


# =============================================================================
# Filesystem I/O
# =============================================================================


def iter_tree_paths(root: Path):
    """Yield every file and directory in root, except symlinks themselves.

    os.walk(followlinks=False) naturally reaches symlink targets via their
    real paths, so all content is covered without explicitly following links.
    """
    yield root
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dp = Path(dirpath)
        for name in (*dirnames, *filenames):
            p = dp / name
            if not p.is_symlink():
                yield p


def apply_lock_state(
    root: Path, writable: bool, exempt: set[Path] | None = None
) -> dict[str, int]:
    """Apply lock or unlock to entire tree via chmod.

    Returns counters: {changed, unchanged, skipped_exempt, errors}.
    """
    exempt = exempt or set()
    counters = {"changed": 0, "unchanged": 0, "skipped_exempt": 0, "errors": 0}

    for path in iter_tree_paths(root):
        if path in exempt:
            counters["skipped_exempt"] += 1
            continue

        try:
            current = path.stat().st_mode
            desired = compute_desired_mode(current, writable)
            if stat.S_IMODE(desired) != stat.S_IMODE(current):
                os.chmod(path, stat.S_IMODE(desired))
                counters["changed"] += 1
            else:
                counters["unchanged"] += 1
        except OSError as exc:
            counters["errors"] += 1
            print(f"warning: could not chmod {path}: {exc}", file=sys.stderr)

    return counters


def read_lock(lock_file: Path) -> dict | None:
    """Read lock state from JSON file; return None if absent.

    Raises GuardError on corrupt JSON.
    """
    if not lock_file.exists():
        return None
    try:
        with open(lock_file) as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise GuardError(f"corrupted lock file {lock_file}: {e}")
    except OSError as e:
        raise GuardError(f"could not read lock file {lock_file}: {e}")


def write_lock(lock_file: Path, record: dict) -> None:
    """Write lock state to JSON file.

    Raises GuardError on I/O error.
    """
    try:
        lock_file.parent.mkdir(parents=True, exist_ok=True)
        with open(lock_file, "w") as f:
            json.dump(record, f, indent=2)
    except OSError as e:
        raise GuardError(f"could not write lock file {lock_file}: {e}")


# =============================================================================
# CLI Commands
# =============================================================================


def cmd_status(args):
    """Report lock state and holders."""
    record = read_lock(args.lock_file)
    now = time.time()

    if args.format == "json":
        record = record or {"status": "locked", "holders": [], "updated_at": now}
        record["_stale_after_seconds"] = STALE_AFTER_SECONDS
        print(json.dumps(record, indent=2))
        return

    if not record:
        print("Status: LOCKED (initial state; no activation yet)")
        print("Holders: none")
        print(f"Lock file: {args.lock_file} (will be created on first activation)")
        return

    status = record.get("status", "unknown")
    holders = record.get("holders", [])
    updated_at = record.get("updated_at")

    print(f"Status: {status.upper()}")
    print(f"Last updated: {time.ctime(updated_at) if updated_at else 'unknown'}")
    print(f"Holders ({len(holders)}):")

    if not holders:
        print("  (none)")
    else:
        for h in holders:
            stale = is_stale_holder(h, now)
            stale_mark = " [STALE]" if stale else ""
            print(
                f"  - {h.get('harness')}/{h.get('session_id')} "
                f"pid={h.get('pid')} on {h.get('hostname')} "
                f"(activated {time.ctime(h.get('activated_at', 0))}){stale_mark}"
            )

    if any(is_stale_holder(h, now) for h in holders):
        print("\nNote: stale holders will be pruned on next activate/deactivate.")


def cmd_activate(args):
    """Activate this harness session; unlock tree if it was locked."""
    if args.harness not in VALID_HARNESSES:
        raise GuardError(
            f"--harness must be one of {VALID_HARNESSES}, got {args.harness}"
        )

    record = read_lock(args.lock_file)
    new_record, needs_fs_unlock = compute_activation(
        record, args.harness, args.session_id, args.force
    )

    if needs_fs_unlock:
        print(f"Unlocking {args.repo_root}...", file=sys.stderr)
        counts = apply_lock_state(args.repo_root, writable=True, exempt=EXEMPT_PATHS)
        print(
            f"  chmod'd {counts['changed']} items "
            f"({counts['unchanged']} already writable, {counts['errors']} errors)",
            file=sys.stderr,
        )

    write_lock(args.lock_file, new_record)
    print(
        f"Activated: harness={args.harness} session_id={args.session_id} "
        f"pid={os.getpid()}"
    )


def cmd_deactivate(args):
    """Deactivate this session; relock tree if no holders remain."""
    record = read_lock(args.lock_file)
    new_record, needs_fs_lock = compute_deactivation(
        record, args.harness, args.session_id
    )

    if needs_fs_lock:
        print(f"Locking {args.repo_root}...", file=sys.stderr)
        counts = apply_lock_state(args.repo_root, writable=False, exempt=EXEMPT_PATHS)
        print(
            f"  chmod'd {counts['changed']} items "
            f"({counts['unchanged']} already read-only, {counts['errors']} errors)",
            file=sys.stderr,
        )

    write_lock(args.lock_file, new_record)
    print(
        f"Deactivated: harness={args.harness} session_id={args.session_id} "
        f"(tree is now {'locked' if needs_fs_lock else 'still active'})"
    )


def cmd_check(args):
    """Check for PreToolUse hook; output JSON for blocking decision."""
    record = read_lock(args.lock_file)
    holders = prune_stale_holders((record or {}).get("holders", []))

    if holders:
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow"
            }
        }
    else:
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": f"Workspace is locked (no active holders)"
            }
        }
    print(json.dumps(output))


def build_parser():
    """Build argument parser."""
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=REPO_ROOT,
        help="repo root (default: auto-detected)",
    )
    parser.add_argument(
        "--lock-file",
        type=Path,
        default=LOCK_FILE,
        help="lock file path (default: .workspace-lock.json in repo root)",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="output format for status command (default: text)",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    status_p = subparsers.add_parser("status", help="Report lock state")
    status_p.set_defaults(func=cmd_status)
    status_p.add_argument(
        "--json",
        action="store_const",
        const="json",
        dest="format",
        help="output as JSON",
    )

    activate_p = subparsers.add_parser("activate", help="Activate harness session")
    activate_p.set_defaults(func=cmd_activate)
    activate_p.add_argument(
        "--harness",
        required=True,
        choices=VALID_HARNESSES,
        help="harness name",
    )
    activate_p.add_argument(
        "--session-id",
        help="session ID (optional; used for multi-window detection)",
    )
    activate_p.add_argument(
        "--force",
        action="store_true",
        help="override existing holder from different harness",
    )

    deactivate_p = subparsers.add_parser("deactivate", help="Deactivate harness session")
    deactivate_p.set_defaults(func=cmd_deactivate)
    deactivate_p.add_argument(
        "--harness",
        choices=VALID_HARNESSES,
        help="harness name (if omitted, clear all holders)",
    )
    deactivate_p.add_argument(
        "--session-id",
        help="session ID (if omitted with --harness, clear all sessions of that harness)",
    )

    check_p = subparsers.add_parser(
        "check", help="Check if unlocked (for PreToolUse hook)"
    )
    check_p.set_defaults(func=cmd_check)

    return parser


def main():
    """Parse and dispatch."""
    parser = build_parser()
    args = parser.parse_args()

    try:
        args.func(args)
    except GuardError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
