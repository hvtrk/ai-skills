# Codex Agent Engineering Rules

Read and strictly adhere to core operating rules from `~/ai-skills/rules/core.md`.

## Core Discipline
- Base all implementations on evidence from the active repository.
- Stop and ask the human owner for high-impact domain/architecture decisions (max 2 options + 1 recommendation).
- Maintain minimal invasive changes and preserve existing APIs.
- Do not perform opportunistic refactoring or modify unrelated files.

## Two-Tier Memory System v2
1. **Startup**: Read universal conventions from `~/.agents/memory/conventions.md`. Read `~/.agents/memory/user-profile.md` only when user preferences are relevant.
2. **Project Context**: If `<project-root>/.memory/` exists, read `.memory/INDEX.md` (<40 lines). Lazily load specific topic files (`architecture.md`, `domain.md`, `gotchas.md`, `session-handoff.md`) only when relevant.
3. **Archive Exclusion**: Never load `.memory/archive/` during normal startup.
4. **Mutations**: Never edit Markdown files directly. Invoke Memory Core operations (`init`, `check`, `retrieve`, `update`, `handoff`, `graduate`, `archive`).
5. **Post-Mutation**: Always execute `memory check` after mutating project memory.

## Skills Integration
- Reusable procedures and cross-project workflows are located in `~/ai-skills/` and synced to `~/.agents/skills/`.
- Load relevant skills on-demand using standard SKILL.md instructions.

