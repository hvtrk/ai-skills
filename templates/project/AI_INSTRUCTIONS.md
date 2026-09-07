# Project AI Agent Instructions

Read and strictly adhere to core operating rules from `~/ai-skills/rules/core.md` and universal conventions from `~/.agents/memory/conventions.md`.

- Base all implementations on evidence from this repository.
- Stop and ask the human owner for high-impact domain/architecture decisions (max 2 options + 1 recommendation).
- Maintain minimal invasive changes and preserve existing APIs.
- Two-Tier Memory: before starting work, read `.memory/INDEX.md` in this project root and lazily load only the topic files (`domain.md`, `architecture.md`, `gotchas.md`, `session-handoff.md`) relevant to the current task. Never load `.memory/archive/` by default.
- If `.memory/` does not exist, continue normally — do not silently create it.
- Skills are available globally (`~/.claude/skills/`, `~/.gemini/config/skills/`, `~/.codex/skills/`) — load the appropriate `<skill-name>/SKILL.md` on-demand rather than reinventing a workflow.
