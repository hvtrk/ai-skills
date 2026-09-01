# ADR 0003: v3.0 Landmark Scope — Pipeline Composability, Memory Linter, MCP Sync

## Status
Accepted

## Context

ADR 0001 and ADR 0002 established the two-tier memory architecture. `session-handoff.md` (2026-08-29 workstream) proposed expanding v3.0 beyond memory/skill updates into a landmark release covering three additional concerns:

1. Whether the Spec-to-Execution pipeline (`grill-with-docs` → `to-spec` → `to-tickets` → `tdd`) should be composable or orchestrated.
2. How deep a Memory Health Linter (`/memory-lint`) should check.
3. Whether `setup.sh`'s harness sync should grow to cover MCP server configs, not just skills.

These were open questions blocking further spec work. This ADR records the decisions reached.

## Decision

### 1. Spec-to-Execution pipeline stays composable, not orchestrated

`grill-with-docs`, `to-spec`, `to-tickets`, and `tdd` remain independent, user-triggered skills. No unified `/pipeline` orchestrator is introduced.

Rationale: matches the repo's existing "lean, on-demand, zero context bloat" philosophy (see README "What's New in v3.0"). The user must be able to stop after `/to-spec`, skip `/to-tickets` for small changes, or re-enter `/grill-with-docs` mid-stream without an orchestration layer deciding stage transitions on their behalf. An orchestrator would add a new component to maintain for a workflow that four separately-invoked skills already cover.

### 2. `/memory-lint` is structural-only

The linter validates only what `scripts/memory.py check` already validates deterministically:
- `INDEX.md` line count (< 40 lines)
- Required files present (`INDEX.md`, `domain.md`, `architecture.md`, `gotchas.md`, `session-handoff.md`)
- Frontmatter validity on durable/archive records
- `session-handoff.md` freshness

`/memory-lint` is a reporting/UX wrapper around the existing `memory.py check` command, not a new validation engine. It does **not** attempt dead-link detection or code-drift detection (cross-referencing `architecture.md`/`domain.md` claims against actual source) — both were considered and deferred as out of scope for this release.

Rationale: `memory.py check` is already deterministic and zero-false-positive. Link and drift checking require cross-referencing content that changes shape per project (arbitrary link targets, arbitrary source layouts) and risk false positives on ordinary refactors. Keep the linter trustworthy before making it thorough.

### 3. MCP sync extends `setup.sh`'s existing harness registry

MCP server manifests become a second declarative resource type synced by `setup.sh`, alongside skills, using the same per-harness adapter pattern already implemented for Antigravity / Claude Code / OpenCode / Global Agents. No separate `mcp-sync` tool is introduced.

Rationale: reuses the harness registry and adapter abstraction (`adapters/{claude,antigravity,codex,cursor,generic}/`) that already resolves per-harness destination paths and symlink/copy semantics for skills. A second standalone tool would duplicate that resolution logic for no isolation benefit — MCP config and skill sync have the same shape of problem (declare once, fan out per harness).

## Consequences

- **Positive**: v3.0 scope stays bounded to extending proven patterns (adapters, `memory.py check`) rather than introducing new orchestration or validation surfaces. Lower implementation and maintenance cost.
- **Trade-offs**: Deep memory drift detection (code vs. `.memory/*.md` claims) remains unimplemented — a future ADR should revisit this once structural linting has been in use long enough to justify the added complexity. Pipeline stages still require the user to manually invoke each next step; there is no automatic hand-off between `to-spec` and `to-tickets`.

## Follow-up work

1. ~~Implement `/memory-lint` skill as a thin wrapper/report around `python3 scripts/memory.py check <project>`.~~ **Done** — [skills/memory-lint/SKILL.md](../../skills/memory-lint/SKILL.md).
2. ~~Extend `setup.sh`'s harness registry to declare and sync MCP server manifests per harness.~~ **Done** — [mcp/README.md](../../mcp/README.md), `scripts/mcp_sync.py`, `setup.sh --sync-mcp [--apply]`. (Extends `setup.sh`'s registry pattern directly; the per-harness Python `adapters/*/adapter.py` modules are a separate, Memory-Core-specific contract and were correctly left untouched.)
3. ~~Update `README.md` "Available Skills Suite" and harness registry docs once (1) and (2) land.~~ **Done**.
