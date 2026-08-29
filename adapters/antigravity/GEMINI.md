# Antigravity Global Memory System & Engineering Rules

Read and strictly adhere to core operating rules from `~/ai-skills/rules/core.md`.

## Core Discipline
- Base all implementations on evidence from the active repository.
- Stop and ask the human owner for high-impact domain/architecture decisions (max 2 options + 1 recommendation).
- Maintain minimal invasive changes and preserve existing APIs.
- Do not perform opportunistic refactoring or modify unrelated files.

## Four-Layer Memory Architecture & Ownership Boundaries
1. **Native Harness Memory**: Platform-owned and non-authoritative. Supplementary ephemeral session state only.
2. **User Agent Memory**: `~/.agents/memory/` (`conventions.md` for universal engineering standards, `user-profile.md` for developer preferences).
3. **Project Memory**: `<project-root>/.memory/` (`INDEX.md`, topic files `architecture.md`, `domain.md`, `gotchas.md`, `session-handoff.md`, and cold storage `archive/`).
4. **Skills**: `~/ai-skills/` (source of truth), synchronized to `~/.agents/skills/` (and discovered at `~/.gemini/config/skills/`). Reusable procedures and cross-project workflows.

## Task Startup & Lazy Retrieval Protocol
At task startup, follow this strict lazy retrieval order:
1. **Determine Project Root**: Discover the workspace root path.
2. **Read Universal Conventions**: Always read `~/.agents/memory/conventions.md`.
3. **Read User Profile (Conditional)**: Read `~/.agents/memory/user-profile.md` only when specific user preferences or tooling choices are relevant.
4. **Detect Project Memory**: Check if `<project-root>/.memory/` exists in the active workspace.
5. **If Project Memory Exists**:
   - Read `.memory/INDEX.md` (<40 lines routing map).
   - Lazily read **only** the topic file(s) relevant to the current task (`architecture.md`, `domain.md`, `gotchas.md`, `session-handoff.md`).
   - **Archive Exclusion**: Never load `.memory/archive/` during normal startup retrieval. Do not load all memory files unconditionally.
6. **If Project Memory Does NOT Exist (New Project Behavior)**:
   - Recognize that project memory is not initialized.
   - **DO NOT silently or automatically create `.memory/`**.
   - Continue the task normally.
   - Initialize project memory only when explicitly requested by the user or when the agent determines initialization is appropriate and clearly communicates the action before proceeding.

## Project Memory Initialization
- When initializing project memory, invoke Memory Core via `memory init <project-root>` or `python3 ~/ai-skills/scripts/memory.py init <project-root>`.
- **Never** manually create `.memory/` directories or copy raw template files.
- Memory Core guarantees non-destructive, idempotent, validated, lock-safe, and atomic initialization.

## Skills & Project-Memory Skill Integration
- Shared skills are discovered dynamically from `~/.agents/skills/` and `~/.gemini/config/skills/`. Do not assume a hardcoded count.
- The `project-memory` skill provides the detailed procedural runbook for memory lifecycle operations. Load `project-memory` when performing non-trivial memory maintenance or onboarding.

## End-of-Task Memory Protocol
At the conclusion of work, classify and persist durable knowledge:
- **Nothing Durable Learned**: Do nothing.
- **Incomplete / In-Progress Work**: Record session state via `memory handoff` (updates `session-handoff.md`).
- **Durable Architecture Fact / ADR**: Update via `memory update --topic architecture`.
- **Durable Domain Concept / Invariant**: Update via `memory update --topic domain`.
- **Durable Gotcha / Trap / Bug Workaround**: Update via `memory update --topic gotchas`.
- **Superseded / Obsolete Knowledge**: Move to cold storage via `memory archive`.
- **Durable Handoff Knowledge**: Graduate to permanent topic files via `memory graduate`.
- **Reusable Generalized Procedure**: Propose creating a new skill under `~/ai-skills/` deliberately (do not auto-create skills).
- **Post-Mutation Validation**: Always run `memory check` after any memory modification.

## Failure Behavior & Strict Boundaries
- **Zero Direct File Mutations**: Never directly edit Markdown files in `.memory/` as a fallback. All mutations must use the Memory Core CLI or Python adapter.
- **Strict Error Propagation**: Never silently ignore Memory Core validation or lock failures.
- **No Bypass**: Never bypass validation, concurrency locks, atomic writes, or rollbacks.
- **Core Unavailable**: If Memory Core is unavailable, report the limitation explicitly. Do not invent alternate mutation behavior.

