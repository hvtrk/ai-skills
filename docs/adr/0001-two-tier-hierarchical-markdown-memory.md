# ADR 0001: Two-Tier Hierarchical Markdown Memory Architecture

## Status
Accepted

## Context
AI coding agents across different harnesses (Antigravity, Claude Code, Cursor, OpenCode/Codex) operate with global skill libraries but lack isolated, persistent workspace context across sessions. Storing full chat histories causes prompt bloat, high token costs, and context contamination across unrelated projects.

## Decision
1. Implement a **Two-Tier Memory Model**:
   - **Global Tier (`~/.agents/memory/`)**: Machine-wide preferences and universal coding conventions (`user-profile.md`, `conventions.md`).
   - **Project Tier (`<project-root>/.memory/`)**: Workspace-specific domain concepts, architectural patterns, gotchas, and session handoffs.
2. Use **Hierarchical Retrieval (Option C)**:
   - Agents read only `.memory/INDEX.md` (< 40 lines) on startup.
   - Specific detailed memory files (`domain.md`, `architecture.md`, `gotchas.md`, `session-handoff.md`) are loaded lazily on demand.
3. Use **Zero-Dependency Markdown**:
   - Stored in plain markdown files without external vector DBs or daemon processes.
   - Allows optional git tracking (personal projects) or `.gitignore` (client/private projects).
4. Implement **Append-and-Replace Compaction**:
   - Active memory files hold only current invariants. Superseded records are relocated to `.memory/archive/` and excluded from everyday prompt retrieval.
   - Short-term session insights in `session-handoff.md` graduate to permanent records upon task completion.

## Consequences
- **Positive**: Zero token waste on irrelevant historical context; absolute isolation between client/personal projects; universal compatibility across all LLM agents.
- **Trade-offs**: Requires disciplined agent rules to update `.memory/` when conventions change or tasks conclude.

