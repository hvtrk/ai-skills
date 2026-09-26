#!/usr/bin/env python3
"""Filesystem-only Memory System v2 core.

Phase 3: Lifecycle Mutation Operations.
This CLI intentionally has no harness, repository, network, or version-control
integration. It manages only explicit filesystem paths.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator, Sequence

REQUIRED_FILES = (
    "INDEX.md",
    "architecture.md",
    "domain.md",
    "gotchas.md",
    "session-handoff.md",
)
TOPICS = ("architecture", "domain", "gotchas", "handoff")
DURABLE_TOPICS = ("architecture", "domain", "gotchas")
TOPIC_FILES = {
    "architecture": "architecture.md",
    "domain": "domain.md",
    "gotchas": "gotchas.md",
    "handoff": "session-handoff.md",
}
REQUIRED_HEADINGS = {
    "INDEX.md": ("# Project Memory Index",),
    "architecture.md": (
        "# Project Architecture & Patterns",
        "## Tech Stack & Core Dependencies",
        "## System Structure & Boundaries",
        "## Key Architectural Decisions",
        "## Permanent Design Invariants",
    ),
    "domain.md": (
        "# Domain Concepts & Invariants",
        "## Core Entities & Vocabulary",
        "## Domain Relationships",
    ),
    "gotchas.md": (
        "# Gotchas, Traps & Quirks",
        "## Critical Traps",
        "## Environment & Tooling Quirks",
    ),
    "session-handoff.md": (
        "# Session Handoff (Active Workstream)",
        "## Current Goal",
        "## State & Files in Progress",
        "## Dead Ends & What Failed",
        "## Immediate Next Step",
    ),
}

# Configuration Constants
INDEX_MAX_LINES = 40
DEFAULT_HANDOFF_FRESHNESS_DAYS = 7.0
LOCK_TIMEOUT_SECONDS = 5.0
STALE_LOCK_EXPIRY_SECONDS = 60.0

ARCHIVE_FILENAME_PATTERN = re.compile(r"^\d{4}-\d{2}(?:-\d{2})?-[a-z0-9_-]+\.md$")
ISO_DATE_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)?$"
)
MARKDOWN_LINK_PATTERN = re.compile(
    r"\[([^\]]*)\]\(([^)\s]+)(?:\s+[\"'][^\"']*[\"'])?\)"
)
MARKDOWN_HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$")

EXIT_OK = 0
EXIT_VALIDATION = 1
EXIT_USAGE = 2
EXIT_UNIMPLEMENTED = 3


class MemoryError(Exception):
    """A user-facing filesystem or validation error."""


@dataclass(frozen=True)
class Finding:
    severity: str  # "ERROR", "WARNING", "INFO", "OK"
    path: Path
    message: str
    line: int | None = None
    suggested_action: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "severity": self.severity,
            "path": str(self.path),
            "message": self.message,
        }
        if self.line is not None:
            data["line"] = self.line
        if self.suggested_action is not None:
            data["suggested_action"] = self.suggested_action
        return data


@dataclass
class Frontmatter:
    data: dict[str, Any]
    line_numbers: dict[str, int]
    raw_lines_count: int


class MemoryTransaction:
    """Lightweight filesystem staged transaction manager.

    Preserves original file content and unlinks newly created files if
    any staged write or post-mutation validation step fails.
    """

    def __init__(self, target_memory: Path) -> None:
        self.target_memory = target_memory
        self.original_contents: dict[Path, str] = {}
        self.created_paths: list[Path] = []
        self.modified_paths: list[Path] = []
        self.committed = False

    def stage_write(self, destination: Path, content: str) -> None:
        if destination.exists():
            if destination not in self.original_contents:
                self.original_contents[destination] = destination.read_text(
                    encoding="utf-8"
                )
            if destination not in self.modified_paths:
                self.modified_paths.append(destination)
        else:
            if destination not in self.created_paths:
                self.created_paths.append(destination)
        atomic_write_text(destination, content)

    def rollback(self) -> None:
        if self.committed:
            return
        for path, orig_content in self.original_contents.items():
            try:
                atomic_write_text(path, orig_content)
            except Exception:
                pass
        for path in self.created_paths:
            try:
                path.unlink(missing_ok=True)
            except Exception:
                pass

    def commit(self) -> None:
        self.committed = True


def default_template_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "templates" / "memory"


def canonical_project(path_value: str) -> Path:
    candidate = Path(path_value).expanduser()
    try:
        project = candidate.resolve(strict=True)
    except FileNotFoundError as exc:
        raise MemoryError(f"Project path does not exist: {candidate}") from exc
    if not project.is_dir():
        raise MemoryError(f"Project path is not a directory: {project}")
    return project


def memory_dir(project: Path) -> Path:
    return project / ".memory"


def resolve_template_dir(value: str | None) -> Path:
    configured = value or os.environ.get("MEMORY_TEMPLATES_DIR")
    template_dir = (
        Path(configured).expanduser() if configured else default_template_dir()
    )
    try:
        template_dir = template_dir.resolve(strict=True)
    except FileNotFoundError as exc:
        raise MemoryError(f"Template directory does not exist: {template_dir}") from exc
    if not template_dir.is_dir():
        raise MemoryError(f"Template path is not a directory: {template_dir}")
    missing = [name for name in REQUIRED_FILES if not (template_dir / name).is_file()]
    if missing:
        raise MemoryError(
            "Template directory is missing required files: " + ", ".join(missing)
        )
    return template_dir


def is_pid_alive(pid: int) -> bool:
    """Check if a process with given PID exists on the local system."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False


@contextmanager
def memory_lock(
    target: Path,
    timeout_seconds: float = LOCK_TIMEOUT_SECONDS,
    stale_expiry_seconds: float = STALE_LOCK_EXPIRY_SECONDS,
) -> Iterator[None]:
    """Acquire an exclusive project-local lock with stale lock recovery."""
    lock_path = target / ".memory.lock"
    deadline = time.monotonic() + timeout_seconds
    descriptor: int | None = None

    while descriptor is None:
        try:
            descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            # Inspect existing lock file for stale condition
            try:
                lock_stat = lock_path.stat()
                lock_age = time.time() - lock_stat.st_mtime
                content = lock_path.read_text(encoding="utf-8")
                lock_pid: int | None = None
                for line in content.splitlines():
                    if line.startswith("pid="):
                        try:
                            lock_pid = int(line.split("=", 1)[1].strip())
                        except ValueError:
                            pass
                is_stale = False
                if lock_pid is not None and not is_pid_alive(lock_pid):
                    is_stale = True
                elif lock_age > stale_expiry_seconds:
                    is_stale = True

                if is_stale:
                    lock_path.unlink(missing_ok=True)
                    continue
            except (OSError, UnicodeDecodeError):
                pass

            if time.monotonic() >= deadline:
                raise MemoryError(
                    f"Memory is locked: {lock_path}. Retry after the active writer finishes."
                )
            time.sleep(0.05)

    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as lock_file:
            descriptor = None
            lock_file.write(f"pid={os.getpid()}\n")
            lock_file.write(f"created_at={int(time.time())}\n")
        yield
    finally:
        if descriptor is not None:
            os.close(descriptor)
        try:
            lock_path.unlink(missing_ok=True)
        except OSError:
            pass


def atomic_write_text(destination: Path, content: str) -> None:
    """Atomically replace a text file using a sibling temporary file."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def copy_template(template: Path, destination: Path) -> None:
    atomic_write_text(destination, template.read_text(encoding="utf-8"))


def initial_memory_stage(project: Path, templates: Path) -> Path:
    stage = Path(tempfile.mkdtemp(prefix=".memory.init-", dir=project))
    try:
        (stage / "archive").mkdir()
        for filename in REQUIRED_FILES:
            copy_template(templates / filename, stage / filename)
        return stage
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def emit(payload: dict, output_format: str) -> None:
    if output_format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    for line in payload.get("messages", []):
        print(line)
    for finding in payload.get("findings", []):
        loc = str(finding["path"])
        if finding.get("line") is not None:
            loc = f"{loc}:{finding['line']}"
        msg = f"{finding['severity']}: {loc}: {finding['message']}"
        if finding.get("suggested_action"):
            msg += f" (Action: {finding['suggested_action']})"
        print(msg)
    for record in payload.get("records", []):
        print(f"--- {record['label']} ({record['path']}) ---")
        print(record["content"], end="" if record["content"].endswith("\n") else "\n")


def validate_date_string(date_str: str) -> bool:
    """Validate that a date string is in valid ISO 8601 format."""
    if not ISO_DATE_PATTERN.match(date_str):
        return False
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            datetime.strptime(date_str.split(".")[0].replace("Z", ""), fmt)
            return True
        except ValueError:
            continue
    try:
        datetime.fromisoformat(date_str)
        return True
    except ValueError:
        return False


def parse_frontmatter(
    content: str, path: Path
) -> tuple[Frontmatter | None, list[Finding]]:
    """Deterministic YAML frontmatter parser using standard library only."""
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, []

    findings: list[Finding] = []
    end_idx = -1
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break

    if end_idx == -1:
        findings.append(
            Finding(
                severity="ERROR",
                path=path,
                line=1,
                message="malformed frontmatter: opening '---' without matching closing delimiter",
                suggested_action="Close the frontmatter block with '---' on its own line.",
            )
        )
        return None, findings

    data: dict[str, Any] = {}
    line_numbers: dict[str, int] = {}
    seen_keys: set[str] = set()

    for line_num, line in enumerate(lines[1:end_idx], start=2):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in stripped:
            findings.append(
                Finding(
                    severity="ERROR",
                    path=path,
                    line=line_num,
                    message=f"malformed frontmatter line: '{stripped}' (expected 'key: value')",
                    suggested_action="Format metadata line as 'key: value'.",
                )
            )
            continue
        key_raw, val_raw = stripped.split(":", 1)
        key = key_raw.strip()
        val = val_raw.strip()

        if (val.startswith('"') and val.endswith('"')) or (
            val.startswith("'") and val.endswith("'")
        ):
            val = val[1:-1].strip()

        norm_key = key.lower().replace("-", "_").replace(" ", "_")
        if norm_key in seen_keys:
            findings.append(
                Finding(
                    severity="ERROR",
                    path=path,
                    line=line_num,
                    message=f"duplicate frontmatter key: '{key}'",
                    suggested_action=f"Remove duplicate key '{key}' from frontmatter.",
                )
            )
        else:
            seen_keys.add(norm_key)
            data[norm_key] = val
            line_numbers[norm_key] = line_num

    return Frontmatter(
        data=data, line_numbers=line_numbers, raw_lines_count=end_idx + 1
    ), findings


def apply_frontmatter_metadata(content: str, metadata: dict[str, Any]) -> str:
    """Deterministically insert or update YAML frontmatter with provided metadata."""
    if not metadata:
        return content

    lines = content.splitlines()
    if lines and lines[0].strip() == "---":
        end_idx = -1
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                end_idx = i
                break
        if end_idx != -1:
            existing_lines = lines[1:end_idx]
            body_lines = lines[end_idx + 1 :]
            updated_keys: set[str] = set()
            new_fm_lines: list[str] = []
            for eline in existing_lines:
                if ":" in eline:
                    k = eline.split(":", 1)[0].strip()
                    norm_k = k.lower().replace("-", "_").replace(" ", "_")
                    if norm_k in metadata:
                        new_fm_lines.append(f"{k}: {metadata[norm_k]}")
                        updated_keys.add(norm_k)
                        continue
                new_fm_lines.append(eline)
            for mk, mv in metadata.items():
                if mk not in updated_keys:
                    new_fm_lines.append(f"{mk}: {mv}")
            new_content = "---\n" + "\n".join(new_fm_lines) + "\n---\n"
            if body_lines:
                new_content += "\n".join(body_lines) + "\n"
            return new_content

    fm_lines = [f"{k}: {v}" for k, v in metadata.items()]
    return "---\n" + "\n".join(fm_lines) + "\n---\n\n" + content


def extract_markdown_links(content: str) -> list[tuple[int, str, str]]:
    """Extract (line_number, link_text, link_target) tuples from Markdown content."""
    links: list[tuple[int, str, str]] = []
    for line_num, line in enumerate(content.splitlines(), start=1):
        for match in MARKDOWN_LINK_PATTERN.finditer(line):
            link_text = match.group(1).strip()
            link_target = match.group(2).strip()
            links.append((line_num, link_text, link_target))
    return links


def detect_duplicate_or_conflict(
    target_content: str, title: str | None, content: str
) -> tuple[str | None, str | None]:
    """Deterministic duplicate and conflict detection."""
    clean_content = content.strip()
    if clean_content and clean_content in target_content:
        return (
            "duplicate",
            "exact duplicate content already exists in target topic file",
        )

    if title:
        clean_title = title.strip()
        if clean_title:
            escaped = re.escape(clean_title)
            title_pattern = re.compile(
                rf"(?:\[{escaped}\]|\*\*{escaped}\*\*|#{1, 6}\s+{escaped})",
                re.IGNORECASE,
            )
            if title_pattern.search(target_content):
                return (
                    "conflict",
                    f"deterministic conflict: entry with title/identifier '{clean_title}' already exists in target topic file with different content",
                )

    return None, None


def insert_into_topic(
    original_content: str,
    content_to_insert: str,
    section: str | None = None,
) -> str:
    """Deterministically insert content under a specified section heading or at the end of file."""
    lines = original_content.splitlines()
    clean_insert = content_to_insert.strip()

    if section:
        clean_sec = section.strip().lstrip("#").strip()
        sec_pattern = re.compile(rf"^#{{1,6}}\s+{re.escape(clean_sec)}\b", re.IGNORECASE)
        sec_idx = -1
        for i, line in enumerate(lines):
            if sec_pattern.match(line.strip()):
                sec_idx = i
                break

        if sec_idx != -1:
            # Find next heading of same or higher level, or end of file
            next_heading_idx = len(lines)
            for j in range(sec_idx + 1, len(lines)):
                if lines[j].strip().startswith("#"):
                    next_heading_idx = j
                    break

            before = lines[:next_heading_idx]
            after = lines[next_heading_idx:]
            return (
                "\n".join(before).rstrip()
                + "\n\n"
                + clean_insert
                + "\n\n"
                + "\n".join(after).lstrip()
            ).rstrip() + "\n"

    # Default: append at end
    return original_content.rstrip() + "\n\n" + clean_insert + "\n"


def load_input_payload(
    input_val: str | None, plan_val: str | None = None
) -> tuple[dict | None, str | None]:
    """Load and parse structured JSON or raw Markdown input."""
    target_val = input_val or plan_val
    if not target_val:
        return None, None

    raw_text = ""
    if target_val == "-":
        raw_text = sys.stdin.read()
    else:
        path = Path(target_val).expanduser()
        if not path.exists():
            raise MemoryError(f"Input file does not exist: {path}")
        if not path.is_file():
            raise MemoryError(f"Input path is not a file: {path}")
        try:
            raw_text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise MemoryError(f"Cannot read input file {path}: {exc}") from exc

    raw_text_stripped = raw_text.strip()
    if not raw_text_stripped:
        raise MemoryError("Input file is empty.")

    if raw_text_stripped.startswith("{") or raw_text_stripped.startswith("["):
        try:
            parsed = json.loads(raw_text)
            if isinstance(parsed, dict):
                return parsed, raw_text
        except json.JSONDecodeError as exc:
            raise MemoryError(f"Malformed JSON input in {target_val}: {exc}") from exc

    return None, raw_text


def initialize(
    project: Path, templates: Path, repair: bool, dry_run: bool
) -> tuple[int, dict]:
    target = memory_dir(project)
    payload: dict = {"operation": "init", "project": str(project), "messages": []}
    if not target.exists():
        if dry_run:
            payload["messages"].append(
                f"DRY-RUN: would create {target} from {templates}"
            )
            payload["messages"].append(
                "INFO: template .gitignore is deliberately not copied; privacy is user-managed."
            )
            return EXIT_OK, payload
        stage = initial_memory_stage(project, templates)
        try:
            try:
                os.replace(stage, target)
            except FileExistsError:
                shutil.rmtree(stage, ignore_errors=True)
                return initialize(project, templates, repair, dry_run)
        except BaseException:
            shutil.rmtree(stage, ignore_errors=True)
            raise
        payload["messages"].append(f"CREATED: {target}")
        for filename in REQUIRED_FILES:
            payload["messages"].append(f"CREATED: {target / filename}")
        payload["messages"].append(f"CREATED: {target / 'archive'}")
        payload["messages"].append(
            "INFO: template .gitignore is deliberately not copied; privacy is user-managed."
        )
        return EXIT_OK, payload

    if not target.is_dir():
        raise MemoryError(f"Memory path exists but is not a directory: {target}")
    missing = [name for name in REQUIRED_FILES if not (target / name).exists()]
    archive_missing = not (target / "archive").exists()
    payload["messages"].append(f"PRESERVED: existing memory directory {target}")
    for filename in REQUIRED_FILES:
        if filename not in missing:
            payload["messages"].append(f"PRESERVED: {target / filename}")
    if not archive_missing:
        payload["messages"].append(f"PRESERVED: {target / 'archive'}")
    payload["messages"].append(
        "INFO: template .gitignore is deliberately not copied; privacy is user-managed."
    )
    if not missing and not archive_missing:
        return EXIT_OK, payload
    if not repair:
        missing_paths = missing + (["archive"] if archive_missing else [])
        payload["messages"].append(
            "INCOMPLETE: missing "
            + ", ".join(missing_paths)
            + "; rerun with --repair to create only missing required paths."
        )
        return EXIT_VALIDATION, payload
    if dry_run:
        for name in missing:
            payload["messages"].append(f"DRY-RUN: would create {target / name}")
        if archive_missing:
            payload["messages"].append(f"DRY-RUN: would create {target / 'archive'}")
        return EXIT_OK, payload
    with memory_lock(target):
        if archive_missing and not (target / "archive").exists():
            (target / "archive").mkdir()
            payload["messages"].append(f"CREATED: {target / 'archive'}")
        for filename in missing:
            destination = target / filename
            if not destination.exists():
                copy_template(templates / filename, destination)
                payload["messages"].append(f"CREATED: {destination}")
            else:
                payload["messages"].append(f"PRESERVED: {destination}")
    return EXIT_OK, payload


def check_memory(
    project: Path,
    stale_days: float | None = None,
) -> tuple[int, dict]:
    """Deterministically validates project memory structure, headings, links, and archive."""
    target = memory_dir(project)
    findings: list[Finding] = []

    if stale_days is None:
        env_val = os.environ.get("MEMORY_HANDOFF_FRESHNESS_DAYS")
        if env_val:
            try:
                stale_days = float(env_val)
            except ValueError:
                stale_days = DEFAULT_HANDOFF_FRESHNESS_DAYS
        else:
            stale_days = DEFAULT_HANDOFF_FRESHNESS_DAYS

    # 1. Structure validation
    if not target.exists():
        findings.append(
            Finding(
                severity="ERROR",
                path=target,
                message="memory directory is missing",
                suggested_action=f"Run 'memory init {project}' to initialize project memory.",
            )
        )
        payload = {
            "operation": "check",
            "project": str(project),
            "findings": [f.to_dict() for f in findings],
        }
        return EXIT_VALIDATION, payload

    if not target.is_dir():
        findings.append(
            Finding(
                severity="ERROR",
                path=target,
                message="memory path exists but is not a directory (collision)",
                suggested_action="Remove or rename conflicting file and initialize .memory as a directory.",
            )
        )
        payload = {
            "operation": "check",
            "project": str(project),
            "findings": [f.to_dict() for f in findings],
        }
        return EXIT_VALIDATION, payload

    archive = target / "archive"
    if not archive.exists():
        findings.append(
            Finding(
                severity="ERROR",
                path=archive,
                message="required archive directory is missing",
                suggested_action=f"Run 'memory init {project} --repair' to create missing archive directory.",
            )
        )
    elif not archive.is_dir():
        findings.append(
            Finding(
                severity="ERROR",
                path=archive,
                message="archive path exists but is not a directory (collision)",
                suggested_action="Remove conflicting file and recreate archive directory.",
            )
        )

    # 2. Required files validation
    file_contents: dict[str, str] = {}
    for filename in REQUIRED_FILES:
        path = target / filename
        if not path.exists():
            findings.append(
                Finding(
                    severity="ERROR",
                    path=path,
                    message="required file is missing",
                    suggested_action=f"Run 'memory init {project} --repair' to restore missing template.",
                )
            )
            continue
        if not path.is_file():
            findings.append(
                Finding(
                    severity="ERROR",
                    path=path,
                    message="required path exists but is not a regular file (collision)",
                    suggested_action=f"Replace {filename} directory with standard file.",
                )
            )
            continue
        try:
            content = path.read_text(encoding="utf-8")
            file_contents[filename] = content
        except (OSError, UnicodeDecodeError) as exc:
            findings.append(
                Finding(
                    severity="ERROR",
                    path=path,
                    message=f"file is not readable UTF-8 text: {exc}",
                    suggested_action="Ensure file is encoded in valid UTF-8 text.",
                )
            )
            continue

        # Frontmatter validation if present on required file
        fm, fm_findings = parse_frontmatter(content, path)
        findings.extend(fm_findings)
        if fm:
            for date_key in ("created", "updated", "date", "archived_at"):
                if date_key in fm.data:
                    date_val = str(fm.data[date_key])
                    if not validate_date_string(date_val):
                        findings.append(
                            Finding(
                                severity="ERROR",
                                path=path,
                                line=fm.line_numbers.get(date_key),
                                message=f"invalid date format for '{date_key}': '{date_val}' (expected ISO 8601 YYYY-MM-DD)",
                                suggested_action=f"Update '{date_key}' to valid ISO 8601 date (e.g. 2026-08-28).",
                            )
                        )

        # Headings validation
        lines = content.splitlines()
        seen_headings: dict[str, int] = {}
        for line_num, line in enumerate(lines, start=1):
            heading_match = MARKDOWN_HEADING_PATTERN.match(line.strip())
            if heading_match:
                full_heading = line.strip()
                if full_heading in seen_headings:
                    first_line = seen_headings[full_heading]
                    findings.append(
                        Finding(
                            severity="ERROR",
                            path=path,
                            line=line_num,
                            message=f"duplicate identical heading: '{full_heading}' (first seen at line {first_line})",
                            suggested_action="Deduplicate or differentiate section headings.",
                        )
                    )
                else:
                    seen_headings[full_heading] = line_num

        for req_heading in REQUIRED_HEADINGS[filename]:
            if req_heading not in content:
                findings.append(
                    Finding(
                        severity="ERROR",
                        path=path,
                        line=1,
                        message=f"missing required section: {req_heading}",
                        suggested_action=f"Add required heading '{req_heading}' to {filename}.",
                    )
                )

        # 3. INDEX.md size limit validation
        if filename == "INDEX.md":
            line_count = len(lines)
            if line_count > INDEX_MAX_LINES:
                findings.append(
                    Finding(
                        severity="ERROR",
                        path=path,
                        line=INDEX_MAX_LINES + 1,
                        message=f"INDEX.md exceeds {INDEX_MAX_LINES} lines (contains {line_count} lines; maximum is {INDEX_MAX_LINES})",
                        suggested_action=f"Trim INDEX.md to {INDEX_MAX_LINES} lines or fewer. Keep detailed knowledge in topic files.",
                    )
                )

        # 7. Session handoff freshness validation
        if filename == "session-handoff.md":
            try:
                stat = path.stat()
                mtime_age_days = (time.time() - stat.st_mtime) / 86400.0
                if mtime_age_days > stale_days:
                    findings.append(
                        Finding(
                            severity="WARNING",
                            path=path,
                            message=f"session handoff has not been modified in {mtime_age_days:.1f} days (freshness threshold: {stale_days:.0f} days)",
                            suggested_action="Review active workstream and either update current goal or graduate completed work.",
                        )
                    )
            except OSError:
                pass

    # 6. Internal Markdown Reference validation across all memory files
    for filename, content in file_contents.items():
        src_path = target / filename
        links = extract_markdown_links(content)
        for line_num, link_text, link_target in links:
            # Ignore external URLs
            if re.match(
                r"^[a-zA-Z][a-zA-Z0-9+.-]*://", link_target
            ) or link_target.startswith("mailto:"):
                continue
            # Ignore in-page anchor-only links
            if link_target.startswith("#"):
                continue
            # Strip in-page anchors from target path
            clean_target = link_target.split("#", 1)[0]
            if not clean_target:
                continue

            resolved_path = (src_path.parent / clean_target).resolve()
            if not resolved_path.exists():
                findings.append(
                    Finding(
                        severity="ERROR",
                        path=src_path,
                        line=line_num,
                        message=f"broken internal reference: [{link_text}]({link_target}) (target does not exist: {resolved_path})",
                        suggested_action=f"Fix link target to point to an existing local file.",
                    )
                )

    # 5. Archive validation
    if archive.exists() and archive.is_dir():
        archive_entries = list(archive.iterdir())
        seen_archive_names: dict[str, Path] = {}

        for entry in sorted(archive_entries):
            if entry.name.startswith("."):
                continue
            if entry.is_dir():
                findings.append(
                    Finding(
                        severity="ERROR",
                        path=entry,
                        message=f"unexpected directory in archive: {entry.name}",
                        suggested_action="Remove nested directories from archive; archive entries must be flat Markdown files.",
                    )
                )
                continue

            # Check filename convention
            if not ARCHIVE_FILENAME_PATTERN.match(entry.name):
                findings.append(
                    Finding(
                        severity="ERROR",
                        path=entry,
                        message=f"invalid archive filename '{entry.name}'; expected 'YYYY-MM-DD-<topic>-<id>.md' or 'YYYY-MM-<topic>-<id>.md'",
                        suggested_action="Rename archive file following date-topic-uniqueness convention.",
                    )
                )

            # Check for case-insensitive collisions
            lower_name = entry.name.lower()
            if lower_name in seen_archive_names:
                findings.append(
                    Finding(
                        severity="ERROR",
                        path=entry,
                        message=f"archive filename collision with '{seen_archive_names[lower_name].name}' (case-insensitive collision)",
                        suggested_action="Ensure unique archive filenames across all filesystems.",
                    )
                )
            else:
                seen_archive_names[lower_name] = entry

            # Check archive file readability and frontmatter
            try:
                archive_content = entry.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                findings.append(
                    Finding(
                        severity="ERROR",
                        path=entry,
                        message=f"archive file is not readable UTF-8 text: {exc}",
                        suggested_action="Ensure archive file is valid UTF-8 text.",
                    )
                )
                continue

            afm, afm_findings = parse_frontmatter(archive_content, entry)
            findings.extend(afm_findings)
            if not afm:
                findings.append(
                    Finding(
                        severity="ERROR",
                        path=entry,
                        line=1,
                        message="archive file is missing required YAML frontmatter",
                        suggested_action="Add frontmatter with archive_date, source_topic, and superseded_by.",
                    )
                )
            else:
                # Required archive metadata: archive_date, source_topic, superseded_by
                archive_date = (
                    afm.data.get("archive_date")
                    or afm.data.get("date")
                    or afm.data.get("archived_at")
                )
                if not archive_date:
                    findings.append(
                        Finding(
                            severity="ERROR",
                            path=entry,
                            line=1,
                            message="archive frontmatter is missing required field: 'archive_date'",
                            suggested_action="Add 'archive_date: YYYY-MM-DD' to archive frontmatter.",
                        )
                    )
                elif not validate_date_string(str(archive_date)):
                    findings.append(
                        Finding(
                            severity="ERROR",
                            path=entry,
                            line=afm.line_numbers.get("archive_date")
                            or afm.line_numbers.get("date")
                            or afm.line_numbers.get("archived_at"),
                            message=f"invalid archive_date format: '{archive_date}' (expected ISO 8601 YYYY-MM-DD)",
                            suggested_action="Format archive_date as ISO 8601 (e.g. 2026-08-28).",
                        )
                    )

                source_topic = afm.data.get("source_topic") or afm.data.get("topic")
                if not source_topic:
                    findings.append(
                        Finding(
                            severity="ERROR",
                            path=entry,
                            line=1,
                            message="archive frontmatter is missing required field: 'source_topic'",
                            suggested_action="Add 'source_topic: <topic>' to archive frontmatter.",
                        )
                    )

                superseded_by = afm.data.get("superseded_by")
                if not superseded_by:
                    findings.append(
                        Finding(
                            severity="ERROR",
                            path=entry,
                            line=1,
                            message="archive frontmatter is missing required field: 'superseded_by'",
                            suggested_action="Add 'superseded_by: <identifier/decision>' to archive frontmatter.",
                        )
                    )
                else:
                    sup_str = str(superseded_by).strip()
                    if sup_str.lower() in (
                        "none",
                        "null",
                        "self",
                        entry.name.lower(),
                        entry.stem.lower(),
                    ):
                        findings.append(
                            Finding(
                                severity="ERROR",
                                path=entry,
                                line=afm.line_numbers.get("superseded_by"),
                                message=f"impossible supersession reference in 'superseded_by': '{superseded_by}'",
                                suggested_action="Provide a valid replacement decision, record identifier, or commit/PR reference.",
                            )
                        )

            # Check links inside archive files too
            archive_links = extract_markdown_links(archive_content)
            for line_num, link_text, link_target in archive_links:
                if (
                    re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", link_target)
                    or link_target.startswith("mailto:")
                    or link_target.startswith("#")
                ):
                    continue
                clean_target = link_target.split("#", 1)[0]
                if not clean_target:
                    continue
                resolved_path = (entry.parent / clean_target).resolve()
                if not resolved_path.exists():
                    findings.append(
                        Finding(
                            severity="ERROR",
                            path=entry,
                            line=line_num,
                            message=f"broken internal reference in archive: [{link_text}]({link_target}) (target does not exist: {resolved_path})",
                            suggested_action="Fix link target to point to an existing local file.",
                        )
                    )

    if not findings:
        findings.append(Finding("OK", target, "all project memory validations passed"))

    has_errors = any(item.severity == "ERROR" for item in findings)
    payload = {
        "operation": "check",
        "project": str(project),
        "findings": [f.to_dict() for f in findings],
    }
    return (EXIT_VALIDATION if has_errors else EXIT_OK), payload


def retrieve(
    project: Path,
    global_memory: Path,
    include_profile: bool,
    topics: Sequence[str],
) -> tuple[int, dict]:
    target = memory_dir(project)
    records: list[dict] = []

    def add_record(label: str, path: Path, required: bool = False) -> None:
        if not path.is_file():
            if required:
                raise MemoryError(f"Required retrieval file is missing: {path}")
            return
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise MemoryError(f"Cannot read {path}: {exc}") from exc
        records.append({"label": label, "path": str(path), "content": content})

    add_record("global-conventions", global_memory / "conventions.md")
    if include_profile:
        add_record("global-user-profile", global_memory / "user-profile.md")
    if not target.exists():
        return EXIT_OK, {
            "operation": "retrieve",
            "project": str(project),
            "messages": [f"INFO: no project memory at {target}"],
            "records": records,
        }
    if not target.is_dir():
        raise MemoryError(f"Memory path is not a directory: {target}")
    add_record("project-index", target / "INDEX.md", required=True)
    for topic in topics:
        add_record(f"project-{topic}", target / TOPIC_FILES[topic], required=True)
    return EXIT_OK, {
        "operation": "retrieve",
        "project": str(project),
        "records": records,
    }


def update_memory(
    project: Path,
    topic: str | None,
    input_data: tuple[dict | None, str | None],
    dry_run: bool = False,
) -> tuple[int, dict]:
    """Deterministically update a durable project memory topic."""
    target = memory_dir(project)
    if not target.is_dir():
        raise MemoryError(
            f"Project memory does not exist at {target}. Run 'memory init {project}' first."
        )

    json_payload, raw_text = input_data
    title: str | None = None
    section: str | None = None
    content: str | None = None
    metadata: dict[str, Any] | None = None

    if json_payload:
        topic = json_payload.get("topic") or topic
        title = json_payload.get("title")
        section = json_payload.get("section")
        content = json_payload.get("content")
        metadata = json_payload.get("metadata")
    elif raw_text:
        content = raw_text

    if not topic:
        raise MemoryError(
            "Missing durable destination topic. Specify --topic or define 'topic' in JSON."
        )
    if topic not in DURABLE_TOPICS:
        raise MemoryError(
            f"Invalid topic '{topic}'. Durable destination topic must be one of: {', '.join(DURABLE_TOPICS)}"
        )
    if not content or not content.strip():
        raise MemoryError(
            "Update content is empty. Provide non-empty content to update durable memory."
        )

    target_file = target / TOPIC_FILES[topic]
    if not target_file.is_file():
        raise MemoryError(f"Target topic file is missing: {target_file}")

    if dry_run:
        cur_content = target_file.read_text(encoding="utf-8")
        dup_kind, dup_msg = detect_duplicate_or_conflict(cur_content, title, content)
        if dup_kind:
            return EXIT_VALIDATION, {
                "operation": "update",
                "project": str(project),
                "topic": topic,
                "messages": [f"ERROR: {dup_msg}"],
            }
        return EXIT_OK, {
            "operation": "update",
            "project": str(project),
            "topic": topic,
            "target_file": str(target_file),
            "messages": [
                f"DRY-RUN: would update {target_file} with {len(content.splitlines())} lines under section '{section or 'default'}'"
            ],
        }

    with memory_lock(target):
        cur_content = target_file.read_text(encoding="utf-8")
        dup_kind, dup_msg = detect_duplicate_or_conflict(cur_content, title, content)
        if dup_kind:
            return EXIT_VALIDATION, {
                "operation": "update",
                "project": str(project),
                "topic": topic,
                "messages": [f"ERROR: {dup_msg}"],
            }

        new_content = insert_into_topic(cur_content, content, section)
        if metadata:
            new_content = apply_frontmatter_metadata(new_content, metadata)

        tx = MemoryTransaction(target)
        tx.stage_write(target_file, new_content)

        code, check_res = check_memory(project)
        if code != EXIT_OK:
            tx.rollback()
            return EXIT_VALIDATION, {
                "operation": "update",
                "project": str(project),
                "topic": topic,
                "target_file": str(target_file),
                "findings": check_res.get("findings", []),
                "messages": [
                    "ERROR: validation failed after update; changes rolled back."
                ],
            }
        tx.commit()

        return EXIT_OK, {
            "operation": "update",
            "project": str(project),
            "topic": topic,
            "target_file": str(target_file),
            "messages": [f"UPDATED: {target_file}"],
            "modified_files": [str(target_file)],
        }


def handoff_memory(
    project: Path,
    input_data: tuple[dict | None, str | None],
    dry_run: bool = False,
) -> tuple[int, dict]:
    """Deterministically write active continuation state to session-handoff.md."""
    target = memory_dir(project)
    if not target.is_dir():
        raise MemoryError(
            f"Project memory does not exist at {target}. Run 'memory init {project}' first."
        )

    json_payload, raw_text = input_data
    rendered_content: str = ""

    if json_payload:
        goal = json_payload.get("goal") or json_payload.get("current_goal")
        if not goal or not str(goal).strip():
            raise MemoryError("Missing required handoff field: 'goal'")

        files_raw = (
            json_payload.get("files_in_progress")
            or json_payload.get("modified_files")
            or json_payload.get("files")
            or []
        )
        if isinstance(files_raw, list):
            files_str = ", ".join(str(f) for f in files_raw) if files_raw else "None"
        else:
            files_str = str(files_raw).strip() or "None"

        build_raw = (
            json_payload.get("build_status")
            or json_payload.get("verification_status")
            or json_payload.get("state")
            or "In progress"
        )
        build_str = str(build_raw).strip()

        dead_ends_raw = (
            json_payload.get("dead_ends") or json_payload.get("what_failed") or []
        )
        if isinstance(dead_ends_raw, list):
            dead_ends_str = (
                ", ".join(str(d) for d in dead_ends_raw) if dead_ends_raw else "None"
            )
        else:
            dead_ends_str = str(dead_ends_raw).strip() or "None"

        next_step = json_payload.get("next_step") or json_payload.get(
            "immediate_next_step"
        )
        if not next_step or not str(next_step).strip():
            raise MemoryError("Missing required handoff field: 'next_step'")

        rendered_content = f"""# Session Handoff (Active Workstream)

> Short-term ephemeral state for AI agent continuity. Reset upon task completion.

## Current Goal
- {str(goal).strip()}

## State & Files in Progress
- Modified files: {files_str}
- Build / Test status: {build_str}

## Dead Ends & What Failed
- Avoid: {dead_ends_str}

## Immediate Next Step
- {str(next_step).strip()}
"""
    elif raw_text:
        rendered_content = raw_text
        for req_heading in REQUIRED_HEADINGS["session-handoff.md"]:
            if req_heading not in rendered_content:
                raise MemoryError(
                    f"Handoff markdown missing required section: '{req_heading}'"
                )
    else:
        raise MemoryError(
            "Missing handoff input. Provide a JSON plan or Markdown handoff file."
        )

    target_file = target / "session-handoff.md"

    if dry_run:
        return EXIT_OK, {
            "operation": "handoff",
            "project": str(project),
            "target_file": str(target_file),
            "messages": [
                f"DRY-RUN: would overwrite {target_file} with {len(rendered_content.splitlines())} lines"
            ],
        }

    with memory_lock(target):
        tx = MemoryTransaction(target)
        tx.stage_write(target_file, rendered_content)

        code, check_res = check_memory(project)
        if code != EXIT_OK:
            tx.rollback()
            return EXIT_VALIDATION, {
                "operation": "handoff",
                "project": str(project),
                "target_file": str(target_file),
                "findings": check_res.get("findings", []),
                "messages": [
                    "ERROR: validation failed after handoff update; changes rolled back."
                ],
            }
        tx.commit()

        return EXIT_OK, {
            "operation": "handoff",
            "project": str(project),
            "target_file": str(target_file),
            "messages": [f"UPDATED: {target_file}"],
            "modified_files": [str(target_file)],
        }


def graduate_memory(
    project: Path,
    input_data: tuple[dict | None, str | None],
    dry_run: bool = False,
    templates: Path | None = None,
) -> tuple[int, dict]:
    """Promote agent-selected handoff knowledge to durable topics and reset handoff."""
    target = memory_dir(project)
    if not target.is_dir():
        raise MemoryError(
            f"Project memory does not exist at {target}. Run 'memory init {project}' first."
        )

    json_payload, _ = input_data
    if not json_payload:
        raise MemoryError(
            "Graduation requires a structured JSON graduation plan (--plan)."
        )

    promotions = json_payload.get("promotions")
    if not isinstance(promotions, list) or not promotions:
        raise MemoryError("Graduation plan must contain a non-empty 'promotions' list.")

    reset_handoff = json_payload.get("reset_handoff", True)

    for i, promo in enumerate(promotions, start=1):
        if not isinstance(promo, dict):
            raise MemoryError(f"Promotion entry #{i} must be an object.")
        topic = promo.get("topic")
        if not topic or topic not in DURABLE_TOPICS:
            raise MemoryError(
                f"Promotion entry #{i} has invalid topic '{topic}'. Must be one of: {', '.join(DURABLE_TOPICS)}"
            )
        content = promo.get("content")
        if not content or not str(content).strip():
            raise MemoryError(f"Promotion entry #{i} has empty content.")

    handoff_file = target / "session-handoff.md"
    template_dir = resolve_template_dir(str(templates) if templates else None)
    template_handoff = (template_dir / "session-handoff.md").read_text(encoding="utf-8")

    if dry_run:
        planned_topics = [p.get("topic") for p in promotions]
        return EXIT_OK, {
            "operation": "graduate",
            "project": str(project),
            "messages": [
                f"DRY-RUN: would graduate {len(promotions)} promotion(s) to topics: {', '.join(planned_topics)}",
                f"DRY-RUN: would reset {handoff_file} to clean template: {reset_handoff}",
            ],
        }

    with memory_lock(target):
        # Stage mutations across durable files
        tx = MemoryTransaction(target)
        modified_files: list[Path] = []

        # Group and apply promotions per topic file
        for promo in promotions:
            topic = promo["topic"]
            title = promo.get("title")
            section = promo.get("section")
            content = str(promo["content"]).strip()
            metadata = promo.get("metadata")

            topic_file = target / TOPIC_FILES[topic]
            if not topic_file.is_file():
                tx.rollback()
                raise MemoryError(f"Target durable topic file is missing: {topic_file}")

            # Read current content (might be already modified in this tx)
            cur_content = topic_file.read_text(encoding="utf-8")
            dup_kind, dup_msg = detect_duplicate_or_conflict(
                cur_content, title, content
            )
            if dup_kind:
                tx.rollback()
                return EXIT_VALIDATION, {
                    "operation": "graduate",
                    "project": str(project),
                    "messages": [f"ERROR: {dup_msg} in topic '{topic}'"],
                }

            new_content = insert_into_topic(cur_content, content, section)
            if metadata:
                new_content = apply_frontmatter_metadata(new_content, metadata)

            tx.stage_write(topic_file, new_content)
            if topic_file not in modified_files:
                modified_files.append(topic_file)

        # Validate durable topic files first
        code, check_res = check_memory(project)
        if code != EXIT_OK:
            tx.rollback()
            return EXIT_VALIDATION, {
                "operation": "graduate",
                "project": str(project),
                "findings": check_res.get("findings", []),
                "messages": [
                    "ERROR: validation failed on durable files after promotion; graduation rolled back and handoff preserved."
                ],
            }

        # Only after durable promotions succeed and validate, reset handoff if requested
        if reset_handoff:
            tx.stage_write(handoff_file, template_handoff)
            if handoff_file not in modified_files:
                modified_files.append(handoff_file)

            code, check_res = check_memory(project)
            if code != EXIT_OK:
                tx.rollback()
                return EXIT_VALIDATION, {
                    "operation": "graduate",
                    "project": str(project),
                    "findings": check_res.get("findings", []),
                    "messages": [
                        "ERROR: validation failed after resetting handoff; graduation rolled back."
                    ],
                }

        tx.commit()

        return EXIT_OK, {
            "operation": "graduate",
            "project": str(project),
            "promotions_count": len(promotions),
            "modified_files": [str(p) for p in modified_files],
            "messages": [
                f"GRADUATED: {len(promotions)} item(s) to durable memory.",
                f"RESET: {handoff_file}"
                if reset_handoff
                else f"PRESERVED: {handoff_file}",
            ],
        }


def archive_memory(
    project: Path,
    topic: str | None,
    input_data: tuple[dict | None, str | None],
    superseded_by: str | None = None,
    dry_run: bool = False,
) -> tuple[int, dict]:
    """Archive an agent-selected obsolete record with provenance and remove it from active topic."""
    target = memory_dir(project)
    if not target.is_dir():
        raise MemoryError(
            f"Project memory does not exist at {target}. Run 'memory init {project}' first."
        )

    json_payload, raw_text = input_data
    title: str | None = None
    content: str | None = None
    reason: str | None = None
    archive_date = datetime.now().strftime("%Y-%m-%d")

    if json_payload:
        topic = json_payload.get("source_topic") or json_payload.get("topic") or topic
        title = json_payload.get("title")
        content = json_payload.get("content")
        superseded_by = json_payload.get("superseded_by") or superseded_by
        reason = json_payload.get("reason")
        if json_payload.get("archive_date"):
            archive_date = str(json_payload["archive_date"]).strip()
    elif raw_text:
        content = raw_text

    if not topic:
        raise MemoryError(
            "Missing source topic for archive. Specify --topic or 'source_topic' in plan."
        )
    if topic not in DURABLE_TOPICS:
        raise MemoryError(
            f"Invalid source topic '{topic}'. Must be one of: {', '.join(DURABLE_TOPICS)}"
        )
    if not superseded_by or not str(superseded_by).strip():
        raise MemoryError("Missing required provenance: 'superseded_by'.")
    sup_str = str(superseded_by).strip()
    if sup_str.lower() in ("none", "null", "self"):
        raise MemoryError(f"Invalid supersession reference: '{superseded_by}'.")
    if not content or not content.strip():
        raise MemoryError("Archive content is empty.")

    clean_content = content.strip()
    source_file = target / TOPIC_FILES[topic]
    if not source_file.is_file():
        raise MemoryError(f"Source topic file is missing: {source_file}")

    archive_dir_path = target / "archive"
    if not archive_dir_path.is_dir():
        raise MemoryError(f"Required archive directory is missing: {archive_dir_path}")

    # Generate unique archive filename
    slug_source = title or clean_content.splitlines()[0]
    slug = re.sub(r"[^a-z0-9]+", "-", slug_source.lower()).strip("-")
    if not slug:
        slug = "record"
    base_name = f"{archive_date}-{topic}-{slug}.md"

    # Case-insensitive collision check in archive
    existing_lower = {f.name.lower() for f in archive_dir_path.iterdir() if f.is_file()}
    candidate_name = base_name
    counter = 1
    while candidate_name.lower() in existing_lower:
        candidate_name = f"{archive_date}-{topic}-{slug}-{counter}.md"
        counter += 1

    archive_file = archive_dir_path / candidate_name

    archive_body = f"""---
archive_date: {archive_date}
source_topic: {topic}
superseded_by: {sup_str}
---

# Archived: {title or slug}

{clean_content}
"""

    if dry_run:
        cur_source = source_file.read_text(encoding="utf-8")
        if clean_content not in cur_source:
            return EXIT_VALIDATION, {
                "operation": "archive",
                "project": str(project),
                "messages": [
                    f"ERROR: content to archive was not found in source topic file '{source_file}'"
                ],
            }
        return EXIT_OK, {
            "operation": "archive",
            "project": str(project),
            "archive_file": str(archive_file),
            "source_topic_file": str(source_file),
            "messages": [
                f"DRY-RUN: would create archive record {archive_file}",
                f"DRY-RUN: would remove obsolete content from {source_file}",
            ],
        }

    with memory_lock(target):
        cur_source = source_file.read_text(encoding="utf-8")
        if clean_content not in cur_source:
            return EXIT_VALIDATION, {
                "operation": "archive",
                "project": str(project),
                "messages": [
                    f"ERROR: content to archive was not found in source topic file '{source_file}'"
                ],
            }

        # Remove whole lines (including their newline) so no blank line is left
        # between the neighbouring entries; fall back to a plain substring removal.
        if clean_content + "\n" in cur_source:
            new_source = cur_source.replace(clean_content + "\n", "")
        else:
            new_source = cur_source.replace(clean_content, "")
        new_source = re.sub(r"\n{3,}", "\n\n", new_source).rstrip() + "\n"

        tx = MemoryTransaction(target)
        tx.stage_write(archive_file, archive_body)
        tx.stage_write(source_file, new_source)

        code, check_res = check_memory(project)
        if code != EXIT_OK:
            tx.rollback()
            return EXIT_VALIDATION, {
                "operation": "archive",
                "project": str(project),
                "findings": check_res.get("findings", []),
                "messages": [
                    "ERROR: validation failed after archive mutation; changes rolled back."
                ],
            }
        tx.commit()

        return EXIT_OK, {
            "operation": "archive",
            "project": str(project),
            "archive_file": str(archive_file),
            "source_topic_file": str(source_file),
            "modified_files": [str(source_file)],
            "created_files": [str(archive_file)],
            "messages": [
                f"ARCHIVED: {source_file} -> {archive_file}",
                f"MODIFIED: {source_file} (removed obsolete entry)",
                f"SUPERSEDED BY: {sup_str}",
            ],
        }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="memory",
        description="Memory System v2 filesystem-only core (Phase 3: Lifecycle Mutation Operations).",
    )
    parser.add_argument(
        "--format", choices=("text", "json"), default="text", help="output format"
    )
    parser.add_argument(
        "--templates", help="memory template directory (defaults relative to this CLI)"
    )
    subparsers = parser.add_subparsers(dest="operation", required=True)

    init = subparsers.add_parser(
        "init", help="create or inspect project memory without overwriting content"
    )
    init.add_argument("project", help="existing project directory")
    init.add_argument(
        "--repair",
        action="store_true",
        help="create only missing required paths in existing memory",
    )
    init.add_argument(
        "--dry-run", action="store_true", help="report planned changes without writing"
    )

    check = subparsers.add_parser(
        "check", help="validate deterministic project-memory structure and safety"
    )
    check.add_argument("project", help="existing project directory")
    check.add_argument(
        "--stale-days",
        type=float,
        default=None,
        help=f"stale handoff freshness threshold in days (default: {DEFAULT_HANDOFF_FRESHNESS_DAYS})",
    )

    retrieve_parser = subparsers.add_parser(
        "retrieve", help="lazily retrieve selected memory files"
    )
    retrieve_parser.add_argument("project", help="existing project directory")
    retrieve_parser.add_argument(
        "--global-memory", help="global memory directory; defaults to ~/.agents/memory"
    )
    retrieve_parser.add_argument(
        "--profile", action="store_true", help="include global user-profile.md"
    )
    retrieve_parser.add_argument(
        "--topic",
        choices=TOPICS,
        action="append",
        default=[],
        help="project topic to include; repeatable",
    )

    update = subparsers.add_parser(
        "update",
        help="update an agent-selected durable topic",
        description="Update an agent-selected durable topic deterministically.",
    )
    update.add_argument("project", help="existing project directory")
    update.add_argument(
        "--topic", choices=DURABLE_TOPICS, help="durable destination topic"
    )
    update.add_argument("--input", help="agent-approved Markdown or JSON input file")
    update.add_argument(
        "--dry-run", action="store_true", help="report planned changes without writing"
    )

    handoff = subparsers.add_parser(
        "handoff",
        help="write agent-provided unfinished-work state",
        description="Write agent-provided unfinished-work state to session-handoff.md.",
    )
    handoff.add_argument("project", help="existing project directory")
    handoff.add_argument(
        "--input", help="agent-approved handoff Markdown or JSON input file"
    )
    handoff.add_argument(
        "--dry-run", action="store_true", help="report planned changes without writing"
    )

    graduate = subparsers.add_parser(
        "graduate",
        help="promote agent-selected handoff knowledge to durable topics",
        description="Apply an approved graduation plan before resetting handoff.",
    )
    graduate.add_argument("project", help="existing project directory")
    graduate.add_argument("--plan", help="agent-approved graduation plan JSON file")
    graduate.add_argument("--input", help="alias for --plan")
    graduate.add_argument(
        "--dry-run", action="store_true", help="report planned changes without writing"
    )

    archive = subparsers.add_parser(
        "archive",
        help="archive an agent-selected superseded record",
        description="Archive source content with supersession provenance and remove from active topic.",
    )
    archive.add_argument("project", help="existing project directory")
    archive.add_argument(
        "--topic", choices=DURABLE_TOPICS, help="superseded topic slug"
    )
    archive.add_argument(
        "--input", help="agent-approved archived Markdown or JSON input file"
    )
    archive.add_argument(
        "--superseded-by", help="replacement decision or record identifier"
    )
    archive.add_argument(
        "--dry-run", action="store_true", help="report planned changes without writing"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        project = canonical_project(args.project)
        templates = resolve_template_dir(args.templates)

        if args.operation == "init":
            code, payload = initialize(project, templates, args.repair, args.dry_run)
        elif args.operation == "check":
            code, payload = check_memory(project, stale_days=args.stale_days)
        elif args.operation == "retrieve":
            global_memory = (
                Path(args.global_memory).expanduser()
                if args.global_memory
                else Path.home() / ".agents" / "memory"
            )
            code, payload = retrieve(project, global_memory, args.profile, args.topic)
        elif args.operation == "update":
            input_data = load_input_payload(args.input)
            code, payload = update_memory(
                project, args.topic, input_data, dry_run=args.dry_run
            )
        elif args.operation == "handoff":
            input_data = load_input_payload(args.input)
            code, payload = handoff_memory(project, input_data, dry_run=args.dry_run)
        elif args.operation == "graduate":
            input_data = load_input_payload(args.input, args.plan)
            code, payload = graduate_memory(
                project, input_data, dry_run=args.dry_run, templates=templates
            )
        elif args.operation == "archive":
            input_data = load_input_payload(args.input)
            code, payload = archive_memory(
                project,
                args.topic,
                input_data,
                superseded_by=args.superseded_by,
                dry_run=args.dry_run,
            )
        else:
            code, payload = (
                EXIT_UNIMPLEMENTED,
                {
                    "operation": args.operation,
                    "project": str(project),
                    "messages": [f"NOT IMPLEMENTED: {args.operation}"],
                },
            )
    except MemoryError as exc:
        code, payload = EXIT_USAGE, {"messages": [f"ERROR: {exc}"]}
    emit(payload, args.format)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
