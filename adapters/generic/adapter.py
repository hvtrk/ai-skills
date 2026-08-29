"""Generic Harness Integration Contract for Memory System v2.

This module defines the harness-independent adapter contract that connects any
filesystem-capable agent harness (Codex, Antigravity, Claude, Cursor, Gemini, etc.)
to the Memory System Core without coupling the Core to any harness or version-control system.

Dependency Direction:
    Harness -> Adapter -> Generic Memory Contract -> Memory Core -> Filesystem

Authority: ADR 0002.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Sequence


class CapabilityStatus(str, Enum):
    """Status classification for memory subsystem capabilities."""

    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    NOT_INITIALIZED = "NOT_INITIALIZED"
    PARTIAL = "PARTIAL"


@dataclass(frozen=True)
class Finding:
    """Diagnostic finding reported by Memory Core validation."""

    severity: str  # "ERROR", "WARNING", "INFO", "OK"
    path: str
    message: str
    line: int | None = None
    suggested_action: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Finding:
        return cls(
            severity=data.get("severity", "INFO"),
            path=str(data.get("path", "")),
            message=data.get("message", ""),
            line=data.get("line"),
            suggested_action=data.get("suggested_action"),
        )

    def to_dict(self) -> dict[str, Any]:
        res: dict[str, Any] = {
            "severity": self.severity,
            "path": self.path,
            "message": self.message,
        }
        if self.line is not None:
            res["line"] = self.line
        if self.suggested_action is not None:
            res["suggested_action"] = self.suggested_action
        return res


@dataclass(frozen=True)
class OperationResult:
    """Structured result returned from a Memory Core operation."""

    operation: str
    success: bool
    exit_code: int
    project: str | None = None
    messages: list[str] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)
    raw_output: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation": self.operation,
            "success": self.success,
            "exit_code": self.exit_code,
            "project": self.project,
            "messages": self.messages,
            "findings": [f.to_dict() for f in self.findings],
            "data": self.data,
            "raw_output": self.raw_output,
        }


@dataclass(frozen=True)
class CapabilityReport:
    """Comprehensive status of all memory subsystems for the current environment."""

    memory_core: CapabilityStatus
    memory_core_path: Path | None
    global_memory: CapabilityStatus
    global_memory_path: Path | None
    conventions_available: bool
    user_profile_available: bool
    project_memory: CapabilityStatus
    project_memory_initialized: bool
    project_memory_path: Path | None
    skills: CapabilityStatus
    skills_source_path: Path | None
    skills_synced_path: Path | None
    available_operations: list[str]
    status_summary: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "memory_core": self.memory_core.value,
            "memory_core_path": str(self.memory_core_path)
            if self.memory_core_path
            else None,
            "global_memory": self.global_memory.value,
            "global_memory_path": str(self.global_memory_path)
            if self.global_memory_path
            else None,
            "conventions_available": self.conventions_available,
            "user_profile_available": self.user_profile_available,
            "project_memory": self.project_memory.value,
            "project_memory_initialized": self.project_memory_initialized,
            "project_memory_path": str(self.project_memory_path)
            if self.project_memory_path
            else None,
            "skills": self.skills.value,
            "skills_source_path": str(self.skills_source_path)
            if self.skills_source_path
            else None,
            "skills_synced_path": str(self.skills_synced_path)
            if self.skills_synced_path
            else None,
            "available_operations": self.available_operations,
            "status_summary": self.status_summary,
        }


REQUIRED_PROJECT_MEMORY_FILES = (
    "INDEX.md",
    "architecture.md",
    "domain.md",
    "gotchas.md",
    "session-handoff.md",
)
SUPPORTED_OPERATIONS = (
    "init",
    "check",
    "retrieve",
    "update",
    "handoff",
    "graduate",
    "archive",
)


class GenericMemoryAdapter:
    """Generic harness-independent adapter for Memory System v2.

    Implements discovery, capability inspection, instruction delivery,
    and structured operation execution against the Memory Core without
    violating filesystem boundaries or imposing harness dependencies.
    """

    def __init__(
        self,
        project_root: str | Path | None = None,
        memory_core_path: str | Path | None = None,
        global_memory_path: str | Path | None = None,
        skills_root: str | Path | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        self._explicit_project_root = (
            Path(project_root).resolve() if project_root else None
        )
        self._explicit_memory_core_path = (
            Path(memory_core_path).resolve() if memory_core_path is not None else None
        )
        self._explicit_global_memory_path = (
            Path(global_memory_path).resolve()
            if global_memory_path is not None
            else None
        )
        self._explicit_skills_root = (
            Path(skills_root).resolve() if skills_root is not None else None
        )
        self._config = config or {}

    # -------------------------------------------------------------------------
    # Discovery Rules
    # -------------------------------------------------------------------------

    def get_project_root(self, harness_hint: str | Path | None = None) -> Path:
        """Discover the project root path.

        Resolution order (non-Git):
        1. Explicit harness hint passed into method.
        2. Explicit project root provided at adapter instantiation.
        3. Environment variable `PROJECT_ROOT` or `WORKSPACE_ROOT`.
        4. Adapter configuration (`project_root`).
        5. Current working directory (`Path.cwd()`).
        """
        if harness_hint:
            return Path(harness_hint).resolve()
        if self._explicit_project_root:
            return self._explicit_project_root

        env_root = os.environ.get("PROJECT_ROOT") or os.environ.get("WORKSPACE_ROOT")
        if env_root:
            return Path(env_root).resolve()

        cfg_root = self._config.get("project_root")
        if cfg_root:
            return Path(cfg_root).resolve()

        return Path.cwd().resolve()

    def get_memory_core(self) -> Path | None:
        """Discover the Memory Core executable.

        Resolution order:
        1. Explicit path passed to adapter instance (validated if set).
        2. Environment variable `MEMORY_CORE_PATH` or `MEMORY_EXECUTABLE`.
        3. Executable named `memory` found on PATH.
        4. Repository-relative `scripts/memory.py` relative to skill root, adapter, or cwd.
        5. Fallback configured path in adapter config.
        """
        if self._explicit_memory_core_path is not None:
            return (
                self._explicit_memory_core_path
                if self._explicit_memory_core_path.is_file()
                else None
            )

        env_core = os.environ.get("MEMORY_CORE_PATH") or os.environ.get(
            "MEMORY_EXECUTABLE"
        )
        if env_core:
            p = Path(env_core).resolve()
            if p.is_file() and (os.access(p, os.X_OK) or p.suffix == ".py"):
                return p

        which_memory = shutil.which("memory")
        if which_memory:
            return Path(which_memory).resolve()

        # Check repository-relative paths
        candidates: list[Path] = []
        if self._explicit_skills_root:
            candidates.append(self._explicit_skills_root / "scripts" / "memory.py")

        # Current file is in adapters/generic/adapter.py -> repo root is parents[2]
        repo_root = Path(__file__).resolve().parents[2]
        candidates.append(repo_root / "scripts" / "memory.py")
        candidates.append(Path.cwd().resolve() / "scripts" / "memory.py")

        cfg_core = self._config.get("memory_core_path")
        if cfg_core:
            candidates.append(Path(cfg_core).resolve())

        for candidate in candidates:
            if candidate.is_file():
                return candidate.resolve()

        return None

    def get_global_memory(self) -> Path | None:
        """Locate the User Agent Memory directory (~/.agents/memory/ or override)."""
        if self._explicit_global_memory_path is not None:
            return self._explicit_global_memory_path

        env_global = os.environ.get("GLOBAL_MEMORY_PATH") or os.environ.get(
            "AGENTS_MEMORY_PATH"
        )
        if env_global:
            return Path(env_global).resolve()

        cfg_global = self._config.get("global_memory_path")
        if cfg_global:
            return Path(cfg_global).resolve()

        default_global = Path.home() / ".agents" / "memory"
        return default_global.resolve()

    def get_project_memory(self, project_root: str | Path | None = None) -> Path:
        """Locate the Project Memory path (<project-root>/.memory/)."""
        root = self.get_project_root(project_root)
        return root / ".memory"

    def get_skill_root(self) -> tuple[Path | None, Path | None]:
        """Locate the shared skill system.

        Returns (source_of_truth_path, synced_agent_skills_path).
        Source of truth defaults to ~/ai-skills/ (or repo root / config).
        Synced location defaults to ~/.agents/skills/.
        """
        source_root: Path | None = None
        if self._explicit_skills_root is not None:
            source_root = self._explicit_skills_root
        else:
            env_source = os.environ.get("AI_SKILLS_ROOT") or os.environ.get(
                "SKILLS_SOURCE_ROOT"
            )
            if env_source:
                source_root = Path(env_source).resolve()
            else:
                cfg_source = self._config.get("skills_source_root")
                if cfg_source:
                    source_root = Path(cfg_source).resolve()
                else:
                    repo_root = Path(__file__).resolve().parents[2]
                    if (repo_root / "skills").is_dir():
                        source_root = repo_root
                    else:
                        default_skills = Path.home() / "ai-skills"
                        if default_skills.is_dir():
                            source_root = default_skills

        synced_root: Path | None = None
        env_synced = os.environ.get("AGENTS_SKILLS_PATH")
        if env_synced:
            synced_root = Path(env_synced).resolve()
        else:
            cfg_synced = self._config.get("skills_synced_root")
            if cfg_synced:
                synced_root = Path(cfg_synced).resolve()
            else:
                default_synced = Path.home() / ".agents" / "skills"
                if default_synced.is_dir():
                    synced_root = default_synced

        return source_root, synced_root

    # -------------------------------------------------------------------------
    # Capability Discovery
    # -------------------------------------------------------------------------

    def get_capabilities(
        self, project_root: str | Path | None = None
    ) -> CapabilityReport:
        """Inspect and report the availability of all memory subsystems."""
        summary: dict[str, str] = {}

        # 1. Memory Core
        core_path = self.get_memory_core()
        if core_path and core_path.exists():
            core_status = CapabilityStatus.AVAILABLE
            summary["memory_core"] = f"Available at {core_path}"
        else:
            core_status = CapabilityStatus.UNAVAILABLE
            summary["memory_core"] = "Memory Core executable unavailable"

        # 2. Global Memory
        global_path = self.get_global_memory()
        conv_file = global_path / "conventions.md" if global_path else None
        prof_file = global_path / "user-profile.md" if global_path else None

        has_conv = bool(conv_file and conv_file.is_file())
        has_prof = bool(prof_file and prof_file.is_file())

        if global_path and global_path.is_dir() and (has_conv or has_prof):
            global_status = CapabilityStatus.AVAILABLE
            summary["global_memory"] = f"Available at {global_path}"
        elif global_path and global_path.is_dir():
            global_status = CapabilityStatus.PARTIAL
            summary["global_memory"] = (
                f"Directory exists at {global_path} but standard files missing"
            )
        else:
            global_status = CapabilityStatus.UNAVAILABLE
            summary["global_memory"] = "Global memory directory unavailable"

        # 3. Project Memory
        proj_mem = self.get_project_memory(project_root)
        if proj_mem.is_dir():
            existing_files = [
                f for f in REQUIRED_PROJECT_MEMORY_FILES if (proj_mem / f).is_file()
            ]
            has_archive = (proj_mem / "archive").is_dir()
            if (
                len(existing_files) == len(REQUIRED_PROJECT_MEMORY_FILES)
                and has_archive
            ):
                proj_status = CapabilityStatus.AVAILABLE
                proj_initialized = True
                summary["project_memory"] = f"Initialized at {proj_mem}"
            else:
                proj_status = CapabilityStatus.PARTIAL
                proj_initialized = False
                summary["project_memory"] = (
                    f"Incomplete structure at {proj_mem} ({len(existing_files)}/{len(REQUIRED_PROJECT_MEMORY_FILES)} files)"
                )
        else:
            proj_status = CapabilityStatus.NOT_INITIALIZED
            proj_initialized = False
            summary["project_memory"] = f"Not initialized (missing {proj_mem})"

        # 4. Skills
        source_skills, synced_skills = self.get_skill_root()
        if source_skills and (source_skills / "skills").is_dir():
            skills_status = CapabilityStatus.AVAILABLE
            summary["skills"] = f"Available at {source_skills}"
        elif synced_skills and synced_skills.is_dir():
            skills_status = CapabilityStatus.AVAILABLE
            summary["skills"] = f"Available at {synced_skills}"
        else:
            skills_status = CapabilityStatus.UNAVAILABLE
            summary["skills"] = "Skills repository unavailable"

        # Available operations: depend on Memory Core availability
        ops = (
            list(SUPPORTED_OPERATIONS)
            if core_status == CapabilityStatus.AVAILABLE
            else []
        )

        return CapabilityReport(
            memory_core=core_status,
            memory_core_path=core_path,
            global_memory=global_status,
            global_memory_path=global_path,
            conventions_available=has_conv,
            user_profile_available=has_prof,
            project_memory=proj_status,
            project_memory_initialized=proj_initialized,
            project_memory_path=proj_mem if proj_mem.exists() else None,
            skills=skills_status,
            skills_source_path=source_skills,
            skills_synced_path=synced_skills,
            available_operations=ops,
            status_summary=summary,
        )

    # -------------------------------------------------------------------------
    # Protocols & Instruction Delivery
    # -------------------------------------------------------------------------

    def get_instructions(self, topic: str | None = None) -> str:
        """Deliver standard generic memory protocol instructions to an agent."""
        if topic == "startup":
            return (
                "GENERIC STARTUP RETRIEVAL PROTOCOL:\n"
                "1. Determine project root.\n"
                "2. Read ~/.agents/memory/conventions.md (universal guidelines).\n"
                "3. Read ~/.agents/memory/user-profile.md (only when user preferences relevant).\n"
                "4. Check if <project-root>/.memory/ exists.\n"
                "5. If present, read .memory/INDEX.md (<40 lines routing index).\n"
                "6. Lazily read ONLY the relevant topic file (architecture.md, domain.md, gotchas.md, session-handoff.md).\n"
                "7. Do NOT read .memory/archive/ during normal startup.\n"
            )
        if topic == "end_of_task":
            return (
                "GENERIC END-OF-TASK PROTOCOL:\n"
                "After completing work, evaluate if knowledge should be retained:\n"
                "- Case A (Nothing durable): Take no action.\n"
                "- Case B (Incomplete work): Update session-handoff.md via `memory handoff`.\n"
                "- Case C (Durable architecture): Update architecture.md via `memory update`.\n"
                "- Case D (Durable domain concept): Update domain.md via `memory update`.\n"
                "- Case E (Durable gotcha/trap): Update gotchas.md via `memory update`.\n"
                "- Case F (Superseded knowledge): Archive obsolete record via `memory archive`.\n"
                "- Case G (Generalized procedure): Propose reusable skill under ~/ai-skills/.\n"
                "Always run `memory check` after mutating project memory.\n"
            )
        return (
            "# Memory System v2 Generic Harness Protocol\n\n"
            "## Storage Layers\n"
            "- Global User Memory: ~/.agents/memory/ (conventions.md, user-profile.md)\n"
            "- Project Memory: <project-root>/.memory/ (INDEX.md, architecture.md, domain.md, gotchas.md, session-handoff.md, archive/)\n"
            "- Skills: ~/ai-skills/ (source of truth), ~/.agents/skills/ (synced)\n\n"
            "## Core Rules\n"
            "1. Lazy Retrieval: Read INDEX.md first; load topic files strictly on demand.\n"
            "2. Agent Decides Semantics: Core handles atomic writes, validation, and locks.\n"
            "3. No Direct Mutations: Invoke Memory Core operations; never edit memory files manually.\n"
            "4. Check After Mutate: Run validation check after every update or handoff.\n"
        )

    def get_startup_retrieval_plan(
        self,
        project_root: str | Path | None = None,
        profile: bool = False,
        topics: Sequence[str] | None = None,
    ) -> dict[str, Any]:
        """Generate a structured retrieval plan according to lazy retrieval rules."""
        proj_root = self.get_project_root(project_root)
        proj_mem = proj_root / ".memory"
        global_mem = self.get_global_memory()

        files_to_read: list[Path] = []
        if global_mem and (global_mem / "conventions.md").is_file():
            files_to_read.append((global_mem / "conventions.md").resolve())
        if profile and global_mem and (global_mem / "user-profile.md").is_file():
            files_to_read.append((global_mem / "user-profile.md").resolve())

        if proj_mem.is_dir() and (proj_mem / "INDEX.md").is_file():
            files_to_read.append((proj_mem / "INDEX.md").resolve())
            if topics:
                for topic in topics:
                    t_filename = (
                        "session-handoff.md" if topic == "handoff" else f"{topic}.md"
                    )
                    t_path = (proj_mem / t_filename).resolve()
                    if t_path.is_file() and t_path not in files_to_read:
                        files_to_read.append(t_path)

        return {
            "project_root": str(proj_root),
            "project_memory_exists": proj_mem.is_dir(),
            "selected_topics": list(topics or []),
            "include_profile": profile,
            "files_to_read": [str(p) for p in files_to_read],
            "archive_excluded": True,
        }

    # -------------------------------------------------------------------------
    # Operation Invocation & Failure Propagation
    # -------------------------------------------------------------------------

    def run_memory_operation(
        self,
        operation: str,
        project: str | Path | None = None,
        args: list[str] | None = None,
        json_input: dict[str, Any] | None = None,
        input_file: str | Path | None = None,
        templates: str | Path | None = None,
        extra_flags: list[str] | None = None,
    ) -> OperationResult:
        """Invoke a Memory Core operation deterministically via structured CLI.

        This method NEVER modifies memory files directly. It delegates all
        filesystem mutations, validations, and locking to the Memory Core,
        and strictly propagates non-zero exits and validation errors.
        """
        core_path = self.get_memory_core()
        if not core_path:
            return OperationResult(
                operation=operation,
                success=False,
                exit_code=127,
                project=str(project) if project else None,
                messages=["ERROR: Memory Core executable not found."],
                findings=[
                    Finding(
                        severity="ERROR",
                        path="",
                        message="Memory Core executable could not be discovered.",
                        suggested_action="Ensure scripts/memory.py or MEMORY_CORE_PATH is set.",
                    )
                ],
            )

        proj_path = self.get_project_root(project)
        cmd: list[str] = []

        if core_path.suffix == ".py":
            cmd = [sys.executable, str(core_path)]
        else:
            cmd = [str(core_path)]

        # Global CLI flags (before subcommand)
        cmd.extend(["--format", "json"])
        if templates:
            cmd.extend(["--templates", str(Path(templates).resolve())])

        cmd.extend([operation, str(proj_path)])

        temp_input_path: Path | None = None
        try:
            if json_input is not None:
                tmp = tempfile.NamedTemporaryFile(
                    mode="w", suffix=".json", delete=False, encoding="utf-8"
                )
                json.dump(json_input, tmp, indent=2)
                tmp.close()
                temp_input_path = Path(tmp.name)
                flag = "--plan" if operation == "graduate" else "--input"
                cmd.extend([flag, str(temp_input_path)])
            elif input_file is not None:
                flag = "--plan" if operation == "graduate" else "--input"
                cmd.extend([flag, str(Path(input_file).resolve())])

            if args:
                cmd.extend(args)
            if extra_flags:
                cmd.extend(extra_flags)

            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
            )

            raw_stdout = proc.stdout.strip()
            raw_stderr = proc.stderr.strip()
            raw_output = raw_stdout or raw_stderr

            messages: list[str] = []
            findings: list[Finding] = []
            payload_data: dict[str, Any] = {}

            if raw_stdout:
                try:
                    parsed = json.loads(raw_stdout)
                    if isinstance(parsed, dict):
                        payload_data = parsed
                        messages = parsed.get("messages", [])
                        for item in parsed.get("findings", []):
                            if isinstance(item, dict):
                                findings.append(Finding.from_dict(item))
                except json.JSONDecodeError:
                    messages = [raw_stdout]
            elif raw_stderr:
                messages = [raw_stderr]

            success = proc.returncode == 0 and not any(
                f.severity == "ERROR" for f in findings
            )

            return OperationResult(
                operation=operation,
                success=success,
                exit_code=proc.returncode,
                project=str(proj_path),
                messages=messages,
                findings=findings,
                data=payload_data,
                raw_output=raw_output,
            )
        finally:
            if temp_input_path and temp_input_path.exists():
                try:
                    temp_input_path.unlink()
                except OSError:
                    pass

    # -------------------------------------------------------------------------
    # High-Level Operation Helpers
    # -------------------------------------------------------------------------

    def init(
        self,
        project: str | Path | None = None,
        repair: bool = False,
        dry_run: bool = False,
        templates: str | Path | None = None,
    ) -> OperationResult:
        """Initialize or repair project memory structure."""
        flags: list[str] = []
        if repair:
            flags.append("--repair")
        if dry_run:
            flags.append("--dry-run")
        return self.run_memory_operation(
            "init", project=project, templates=templates, extra_flags=flags
        )

    def check(
        self,
        project: str | Path | None = None,
        stale_days: float | None = None,
    ) -> OperationResult:
        """Run deterministic structure and freshness validation."""
        flags: list[str] = []
        if stale_days is not None:
            flags.extend(["--stale-days", str(stale_days)])
        return self.run_memory_operation("check", project=project, extra_flags=flags)

    def retrieve(
        self,
        project: str | Path | None = None,
        profile: bool = False,
        topics: Sequence[str] | None = None,
        global_memory: str | Path | None = None,
    ) -> OperationResult:
        """Perform lazy retrieval of selected memory topics."""
        flags: list[str] = []
        if profile:
            flags.append("--profile")
        g_mem = global_memory or self.get_global_memory()
        if g_mem:
            flags.extend(["--global-memory", str(Path(g_mem).resolve())])
        if topics:
            for t in topics:
                flags.extend(["--topic", t])
        return self.run_memory_operation("retrieve", project=project, extra_flags=flags)

    def update(
        self,
        project: str | Path | None = None,
        topic: str | None = None,
        input_payload: dict[str, Any] | None = None,
        input_file: str | Path | None = None,
        dry_run: bool = False,
    ) -> OperationResult:
        """Update a durable memory topic under lock and validation."""
        flags: list[str] = []
        if topic:
            flags.extend(["--topic", topic])
        if dry_run:
            flags.append("--dry-run")
        return self.run_memory_operation(
            "update",
            project=project,
            json_input=input_payload,
            input_file=input_file,
            extra_flags=flags,
        )

    def handoff(
        self,
        project: str | Path | None = None,
        input_payload: dict[str, Any] | None = None,
        input_file: str | Path | None = None,
        dry_run: bool = False,
    ) -> OperationResult:
        """Write session handoff state under lock."""
        flags: list[str] = []
        if dry_run:
            flags.append("--dry-run")
        return self.run_memory_operation(
            "handoff",
            project=project,
            json_input=input_payload,
            input_file=input_file,
            extra_flags=flags,
        )

    def graduate(
        self,
        project: str | Path | None = None,
        plan_payload: dict[str, Any] | None = None,
        plan_file: str | Path | None = None,
        dry_run: bool = False,
    ) -> OperationResult:
        """Apply approved graduation plan and reset handoff."""
        flags: list[str] = []
        if dry_run:
            flags.append("--dry-run")
        return self.run_memory_operation(
            "graduate",
            project=project,
            json_input=plan_payload,
            input_file=plan_file,
            extra_flags=flags,
        )

    def archive(
        self,
        project: str | Path | None = None,
        topic: str | None = None,
        input_payload: dict[str, Any] | None = None,
        input_file: str | Path | None = None,
        superseded_by: str | None = None,
        dry_run: bool = False,
    ) -> OperationResult:
        """Archive a superseded record with provenance."""
        flags: list[str] = []
        if topic:
            flags.extend(["--topic", topic])
        if superseded_by:
            flags.extend(["--superseded-by", superseded_by])
        if dry_run:
            flags.append("--dry-run")
        return self.run_memory_operation(
            "archive",
            project=project,
            json_input=input_payload,
            input_file=input_file,
            extra_flags=flags,
        )
