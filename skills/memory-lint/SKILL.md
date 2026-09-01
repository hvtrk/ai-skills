---
name: memory-lint
description: Validate a project's .memory/ structure (INDEX size, required files, frontmatter, handoff freshness) and report findings in plain language. Use when the user says "lint memory", "check memory health", "/memory-lint", or before trusting stale-looking .memory/ files.
---

# Memory Lint

A structural health check for a project's two-tier memory (ADR 0001, ADR 0002). This skill does **not** implement its own validation logic — it runs the existing deterministic `scripts/memory.py check` command and turns its output into a readable report. See ADR 0003 for why this stays structural-only (no dead-link or code-drift detection).

## When to use

- User says "lint memory", "check memory health", "/memory-lint", or "is .memory/ healthy".
- Before relying on `.memory/*.md` claims in a project that hasn't been touched in a while.
- After running `python3 scripts/memory.py init/update/handoff/graduate/archive`, as a sanity check.

## Process

1. Determine the target project directory:
   - Use the path the user gave, or the current project root if none was given.
2. Run the check:
   ```bash
   python3 ~/ai-skills/scripts/memory.py --format json check <project> [--stale-days N]
   ```
   Default `--stale-days` is 7; pass a different value only if the user asks for a different freshness threshold.
3. Parse the JSON `findings` array. Each finding has `severity` (`OK`, `WARN`, or `ERROR`), `path`, and `message`.
4. Report to the user:
   - If every finding is `OK`: state memory is structurally healthy, in one line.
   - If there are `WARN`/`ERROR` findings: list each with its path and message, grouped by severity, most severe first.
5. Do not attempt to fix findings automatically — report them and let the user decide (a `WARN` on `session-handoff.md` freshness may be intentional, an `ERROR` on missing `INDEX.md` needs `memory.py init`).

## What this does NOT check

- Dead links inside `.memory/*.md` files (e.g. an ADR link that no longer resolves).
- Drift between `architecture.md`/`domain.md` claims and the actual codebase (renamed files, removed modules).

Both were considered and explicitly deferred in ADR 0003 to keep this linter deterministic and false-positive-free. If the user wants either, point them at ADR 0003's "Follow-up work" section rather than improvising ad hoc checks.

## Example

```
User: /memory-lint

→ python3 ~/ai-skills/scripts/memory.py --format json check .

Memory structurally healthy: all project memory validations passed.
```

```
User: /memory-lint ~/code/some-stale-project

→ python3 ~/ai-skills/scripts/memory.py --format json check ~/code/some-stale-project

2 issues found:
  WARN  .memory/session-handoff.md: handoff is 19 days old (stale threshold: 7 days)
  ERROR .memory/INDEX.md: exceeds 40 lines (52 lines)
```
