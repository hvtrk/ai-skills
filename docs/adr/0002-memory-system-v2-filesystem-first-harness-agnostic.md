# ADR 0002: Memory System v2 — Filesystem-First, Harness-Agnostic Memory

## Status
Accepted

## Context

ADR 0001 established a two-tier Markdown memory model, but its implementation audit found that several lifecycle and integration claims were procedural guidance rather than implemented behavior. In particular, platform-native memory, user memory, project memory, and reusable skills require explicit ownership boundaries. The system must remain portable across filesystem-capable agent harnesses without coupling its core to any one harness or to version control.

This ADR supersedes ADR 0001 where its decisions conflict with the boundaries and lifecycle defined below.

## Decision

### 1. Establish four independent memory layers

1. **Native harness memory** is platform-owned. Codex native memory, and the native memory of every other harness, is automatic and independent. It is supplementary, non-authoritative for project knowledge, and outside the Memory System's control. The Memory System must not read, write, mirror, synchronize, or depend on it.
2. **User Agent Memory** lives at `~/.agents/memory/`. It contains stable, cross-project knowledge about the user and consistent agent behavior. `user-profile.md` and `conventions.md` are both retrieval sources. User memory must never be copied automatically into a project.
3. **Project Memory** lives at `<project-root>/.memory/`. It is durable, portable project knowledge shared by compatible agents and conversations working in that project.
4. **Skills** have their source of truth in `~/ai-skills/` and are discovered at `~/.agents/skills/` and/or a harness-specific skill location. Skills contain reusable procedures and workflows, not project-specific facts.

### 2. Standardize the project-memory format

Project memory has this required filesystem structure:

```text
.memory/
├── INDEX.md
├── architecture.md
├── domain.md
├── gotchas.md
├── session-handoff.md
└── archive/
```

- `INDEX.md` is a small routing index, not a knowledge dump.
- `architecture.md`, `domain.md`, and `gotchas.md` contain durable project knowledge.
- `session-handoff.md` contains short-lived unfinished-work and continuation state; it is not a permanent log.
- `archive/` contains superseded durable knowledge and is excluded from normal retrieval.

The core format is plain Markdown, with YAML frontmatter only where lightweight provenance is useful. Durable records may record created or updated date and source/context. Archive records must record archive date, source topic, and `superseded-by`. Archive filenames use date, topic, and a uniqueness component rather than `YYYY-MM-topic` alone.

### 3. Route knowledge to its narrowest appropriate scope

| Knowledge | Destination |
| --- | --- |
| Stable user preferences and global engineering conventions | `~/.agents/memory/` |
| Durable project knowledge | `<project-root>/.memory/` |
| Temporary unfinished work | `<project-root>/.memory/session-handoff.md` |
| Deliberately generalized reusable procedure | `~/ai-skills/` |
| Native harness context | Owned entirely by that harness |
| Disposable information | Nowhere |

Agents must not blindly duplicate information across stores. A project-specific solution belongs in project memory first. It may become a skill only after deliberate generalization removes project-specific assumptions and establishes a reusable procedure.

### 4. Define an explicit lifecycle and operation boundary

The lifecycle is:

```text
initialize → retrieve → work → classify knowledge → update or handoff
           → graduate or archive where appropriate → validate
```

Agents make semantic decisions: whether knowledge is worth retaining, its correct destination, whether it contradicts existing knowledge, and whether a project solution is reusable. Deterministic tooling provides filesystem handling, formatting, metadata, atomic writes, validation, and lightweight concurrency protection.

The canonical operations are `memory init`, `memory check`, `memory retrieve`, `memory update`, `memory handoff`, `memory graduate`, and `memory archive`. Naming these operations does not claim that command handlers or automation already exist.

- **Initialize** validates arguments, safely creates missing required paths, deliberately handles hidden files, preserves existing user content, is idempotent, and never silently overwrites. An existing `.memory/` directory is preserved and reported; repair of missing files is explicit.
- **Retrieve** is lazy: read global conventions; read the user profile when relevant; detect project memory; read `INDEX.md`; then read only relevant topic files. Archive is excluded unless explicitly requested.
- **Update** safely changes durable knowledge without blind appends, detects deterministic duplicates or suspicious conflicts where practical, and retains useful provenance.
- **Handoff** records enough current goal, state, verification status, blockers, and immediate next action for another agent or conversation to continue. It must not become a permanent dumping ground.
- **Graduate** deliberately promotes durable handoff knowledge to `architecture.md`, `domain.md`, or `gotchas.md`. It resets the handoff only after the durable updates succeed and validate. Graduation is agent-guided, not automatic unless a future implementation explicitly enforces it.
- **Archive** preserves a superseded record with provenance and a unique date-and-topic filename, while removing obsolete knowledge from active retrieval.
- **Check** validates and reports; it does not silently rewrite user memory.

### 5. Require deterministic validation and lightweight concurrency safety

`memory check` must validate required files and sections, `INDEX.md` size, malformed frontmatter, broken internal references, archive metadata, invalid or stale handoff structure, and deterministically detectable duplicate or suspicious entries. Findings are reported as errors, warnings, or information; validation does not rewrite memory by default.

Writers use lightweight project-local lock files and atomic replacement of temporary files in the destination directory. Concurrent initialization and updates must preserve existing complete files and report conflicts rather than overwrite them. Readers may read while writers update because writes are atomic. The system does not use a database, daemon, vector store, embeddings, external service, or network dependency.

### 6. Make privacy explicit without prescribing version control

Project memory has three explicit privacy modes:

1. **tracked/team**: memory is intended for shared project use;
2. **local/private**: memory is intended to remain local to the user's workspace;
3. **excluded/sensitive**: sensitive information must not be persisted in project memory.

Initialization must require or report an explicit privacy choice for new memory, but the Memory System must not decide how those files are committed, ignored, merged, backed up, or otherwise versioned.

Git and version control are outside the scope of the Memory System. It must not inspect branches, create commits, merge or cherry-pick files, use Git hooks, synchronize branches, automatically version memory, or require a Git repository. The user manages persistence and version-control policy independently. Project memory is portable filesystem data regardless of that policy.

### 7. Separate the harness-independent core from thin adapters

The Memory System Core must not depend on Codex, Antigravity, Claude, Cursor, Gemini, an IDE, or any harness-native memory system. Harness-specific behavior belongs only in thin adapters. An adapter may define instruction discovery, project-root discovery, skill discovery, operation invocation, and harness-specific startup integration.

Adapters must not redefine memory storage, routing, lifecycle, validation, or file format. The intended conceptual layout is:

```text
adapters/
├── codex/
├── antigravity/
├── claude/
├── cursor/
└── generic/
```

This layout is a contract, not a requirement to implement every adapter immediately. No adapter may claim Codex-specific or other harness-specific integration until it is implemented.

### 8. Preserve existing memory during migration

Migration to v2 preserves `~/.agents/memory/user-profile.md`, `~/.agents/memory/conventions.md`, existing `.memory/` directories and content, existing skills, and existing templates. Existing memory is checked and reported before any explicit repair; it is never destroyed or silently rewritten. Legacy content remains usable where compatible while future tooling adopts the v2 operation and validation contract.

## Consequences

- **Positive**: Project knowledge is portable, reviewable, and shared through a stable filesystem format; global preferences remain isolated; skills remain reusable rather than becoming fact stores; and adapters can support multiple harnesses without format drift.
- **Trade-offs**: Agents retain semantic responsibility, concurrent conflicts cannot always be merged automatically, and lifecycle behavior is not automatic until concrete tooling implements it.
- **Boundary**: This decision intentionally excludes native-harness memory integration and all version-control behavior from the Memory System.
