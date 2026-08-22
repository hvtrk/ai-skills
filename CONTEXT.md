# Project Memory System

A two-tier, zero-dependency memory framework separating machine-wide developer conventions from workspace-scoped domain knowledge.

## Language

**Global Memory**:
Machine-wide markdown files in `~/.agents/memory/` storing project-agnostic developer preferences, styling ethos, and tool conventions.
_Avoid_: Global settings, user profile, dotfiles.

**Project Memory**:
A repository-scoped directory (`.memory/`) storing domain concepts, architectural choices, gotchas, and active task state for a specific project.
_Avoid_: Local cache, project docs, context dump.

**Memory Index**:
A compact routing file (`.memory/INDEX.md`) containing one-line summaries and pointers to detailed topic files.
_Avoid_: Table of contents, summary doc.

**Session Handoff**:
Short-term ephemeral state recording the active goal, dead ends, and immediate next steps for the next agent session.
_Avoid_: Scratchpad, task log, changelog.

**Memory Graduation**:
The promotion of temporary session learnings into permanent entries in `architecture.md` or `gotchas.md`.
_Avoid_: Merging, committing, syncing.

**Memory Compaction**:
The removal of obsolete entries and the rewriting of verbose historical logs into concise, bulleted invariants.
_Avoid_: Pruning, trashing, cleanup.

