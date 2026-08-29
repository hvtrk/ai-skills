"""Codex Harness Adapter for Memory System v2.

Provides concrete integration between the Codex / OpenCode agent harness and
Memory System v2 by extending the Generic Adapter Contract.

Dependency Direction:
    Codex -> Codex Adapter -> Generic Adapter Contract -> Memory Core -> Filesystem

Authority: ADR 0002.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from adapters.generic.adapter import (
    GenericMemoryAdapter,
)


class CodexMemoryAdapter(GenericMemoryAdapter):
    """Concrete Codex harness adapter for Memory System v2.

    Implements Codex-specific project root resolution, instruction discovery,
    and capability inspection while strictly delegating all mutations,
    validation, and locking to the Memory Core via GenericMemoryAdapter.
    """

    def __init__(
        self,
        project_root: str | Path | None = None,
        memory_core_path: str | Path | None = None,
        global_memory_path: str | Path | None = None,
        skills_root: str | Path | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            project_root=project_root,
            memory_core_path=memory_core_path,
            global_memory_path=global_memory_path,
            skills_root=skills_root,
            config=config,
        )

    def get_project_root(self, harness_hint: str | Path | None = None) -> Path:
        """Discover the project root path with Codex-specific precedence.

        Resolution order (non-Git):
        1. Explicit harness hint passed into method.
        2. Explicit project root provided at adapter instantiation.
        3. Codex-specific environment variables (`CODEX_PROJECT_ROOT`, `CODEX_WORKSPACE_ROOT`, `OPENCODE_PROJECT_ROOT`).
        4. Standard environment variables (`PROJECT_ROOT`, `WORKSPACE_ROOT`).
        5. Adapter configuration (`project_root`).
        6. Current working directory (`Path.cwd()`).
        """
        if harness_hint:
            return Path(harness_hint).resolve()
        if self._explicit_project_root:
            return self._explicit_project_root

        # Codex / OpenCode specific environment variables
        codex_env = (
            os.environ.get("CODEX_PROJECT_ROOT")
            or os.environ.get("CODEX_WORKSPACE_ROOT")
            or os.environ.get("OPENCODE_PROJECT_ROOT")
        )
        if codex_env:
            return Path(codex_env).resolve()

        # Standard environment variables
        env_root = os.environ.get("PROJECT_ROOT") or os.environ.get("WORKSPACE_ROOT")
        if env_root:
            return Path(env_root).resolve()

        cfg_root = self._config.get("project_root")
        if cfg_root:
            return Path(cfg_root).resolve()

        return Path.cwd().resolve()

    def get_instructions(self, topic: str | None = None) -> str:
        """Deliver Codex-formatted memory protocol instructions."""
        if topic == "startup":
            return (
                "CODEX STARTUP RETRIEVAL PROTOCOL:\n"
                "1. Determine project root.\n"
                "2. Read ~/.agents/memory/conventions.md (universal rules & preferences).\n"
                "3. Read ~/.agents/memory/user-profile.md (only when user preferences relevant).\n"
                "4. Check if <project-root>/.memory/ exists.\n"
                "5. If present, read .memory/INDEX.md (<40 lines routing index).\n"
                "6. Lazily read ONLY the relevant topic file (architecture.md, domain.md, gotchas.md, session-handoff.md).\n"
                "7. Do NOT read .memory/archive/ during normal startup.\n"
            )
        if topic == "end_of_task":
            return (
                "CODEX END-OF-TASK PROTOCOL:\n"
                "After completing work, evaluate if knowledge should be retained:\n"
                "- Case A (Nothing durable): Take no action.\n"
                "- Case B (Incomplete work): Update session-handoff.md via `memory handoff`.\n"
                "- Case C (Durable architecture): Update architecture.md via `memory update --topic architecture`.\n"
                "- Case D (Durable domain concept): Update domain.md via `memory update --topic domain`.\n"
                "- Case E (Durable gotcha/trap): Update gotchas.md via `memory update --topic gotchas`.\n"
                "- Case F (Superseded knowledge): Archive obsolete record via `memory archive`.\n"
                "- Case G (Durable handoff knowledge): Graduate to durable memory via `memory graduate`.\n"
                "- Case H (Generalized procedure): Propose reusable skill under ~/ai-skills/.\n"
                "Always run `memory check` after mutating project memory.\n"
            )
        return (
            "# Codex Memory System v2 Protocol\n\n"
            "## Storage Layers\n"
            "- Global User Memory: ~/.agents/memory/ (conventions.md, user-profile.md)\n"
            "- Project Memory: <project-root>/.memory/ (INDEX.md, architecture.md, domain.md, gotchas.md, session-handoff.md, archive/)\n"
            "- Skills: ~/ai-skills/ (source of truth), ~/.agents/skills/ (synced)\n\n"
            "## Core Operating Rules\n"
            "1. Lazy Retrieval: Read INDEX.md first; load topic files strictly on demand.\n"
            "2. Archive Exclusion: Never load .memory/archive/ into active prompts.\n"
            "3. Agent Guided Semantics: Memory Core handles atomic writes, validation, and locks.\n"
            "4. No Direct Mutations: Invoke Memory Core CLI operations; never edit memory files manually.\n"
            "5. Check After Mutate: Run validation check after every update, handoff, graduate, or archive.\n"
        )
