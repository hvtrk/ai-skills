# ADR 0004: Workspace Activation Guardrail — OS-Level Access Control

## Status
Accepted

## Context

The `ai-skills` repository contains shared skills and adapters symlinked into other projects via `setup.sh --project <dir>`. An agent working in a different project can unknowingly edit files that resolve back to this repository through symlinks, creating a security and consistency risk: edits appear local but modify shared infrastructure.

Today, there is no enforcement mechanism preventing this:
- No git hooks that guard against commits during symlink scenarios
- No convention-based guardrail (instructions to "check lock state") can intercept cross-project writes
- No access control at the filesystem level

The core risk is not "an agent directly opens this repo and edits it" — that is visible and consentable. The risk is **indirect edits through symlinked skill paths** from a different harness session working in a different project.

## Decision

### 1. Enforce read-only state at rest via OS-level chmod

The repository tree is read-only when no active harness session is present. Only the active session can make changes. This applies to all writes regardless of:
- Which session/harness initiated the write
- Whether the write is direct or through a symlink
- Whether the write is a source file edit or a git commit

Read-only enforcement is the only mechanism that reliably intercepts symlink-based writes regardless of which harness is doing the writing.

### 2. Holder-list lock model with concurrent session support

Lock state is stored in `.workspace-lock.json` (machine-local, git-ignored) containing a list of active "holders" — each harness session that has activated the lock. A holder contains:
- `harness`: the harness name (`claude`, `codex`, `antigravity`, `manual`)
- `session_id`: optional session identifier (for detecting concurrent windows on the same harness)
- `hostname`, `user`, `pid`, `activated_at`: lifecycle metadata for staleness detection

The tree is writable if **any** live holder exists. It is read-only if the holder list is empty or contains only stale holders.

Staleness detection:
- Holders older than 12 hours are automatically pruned as expired
- Holders on the same machine whose PID is no longer running are trusted (the activation subprocess exits, but the harness session keeps the lock live until SessionEnd)
- Holders on different machines with dead PIDs are considered stale (orphaned cross-machine locks)

Concurrency support (multiple Claude Code windows open on this repo):
- Each window's SessionStart hook adds a new holder (same harness, different `session_id`)
- SessionEnd hook removes only that holder by `session_id`, leaving sibling sessions intact
- The tree remains writable until the last holder is removed

### 3. `.git/` is included in the chmod scope

The `.git/` directory must also be read-only when the repo is locked. Otherwise, `git commit` would succeed even when the tree is locked (because commit needs write access to `.git/index`, `.git/refs/`, `.git/logs/`, and the `.git/objects/` directory itself).

Implication: a locked repo cannot be committed to, even by the user directly.

### 4. Claude Code uses automatic activation; Codex and Antigravity use manual commands

**Claude Code**: Uses native `SessionStart` and `SessionEnd` hooks in `.claude/settings.json` to automatically activate/deactivate when this repo becomes the open project. Activation is transparent to the user.

**Codex and Antigravity**: No confirmed session hook system. Users must manually run:
```bash
python3 scripts/workspace_guard.py activate --harness codex
python3 scripts/workspace_guard.py deactivate --harness codex
```

The OS-level chmod is the real backstop that prevents edits regardless of harness compliance. Manual activation is documented in root instruction files (`AGENTS.md`, `GEMINI.md`), and the OS lock enforces it if forgotten.

### 5. PreToolUse hook outputs JSON for blocking decision, not exit codes

Claude Code's hook architecture uses JSON output (`hookSpecificOutput.permissionDecision`) to control blocking, not exit codes. The `workspace_guard.py check` command outputs:
```json
{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow"}}
```
when the tree is unlocked, and:
```json
{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": "..."}}
```
when locked.

### 6. Root instruction files point to a single canonical policy doc

Three root files (`CLAUDE.md`, `AGENTS.md`, `GEMINI.md`) each point to a single canonical policy document at `docs/policies/workspace-guardrail.md`. This avoids tri-plicating documentation and drift.

## Consequences

- **Positive**: 
  - Symlink-based indirect edits are fully blocked, regardless of which harness is doing the writing
  - No git hooks required, no convention-based guardrail that can be forgotten
  - Supports concurrent harness sessions (e.g., two Claude Code windows)
  - Transparent automatic activation for Claude Code users
  - Low ongoing maintenance (Python script, two shell functions, one JSON settings file)
  
- **Trade-offs**: 
  - A locked repo cannot be edited even by the user directly on the command line; unlocking requires `activate --harness manual`
  - Fresh clones from git are writable until `deactivate` is run once (git does not preserve permission bits)
  - Cross-machine access is discouraged but not impossible (a holder on a different machine may have a stale PID; it will be pruned after 12 hours or on the next activate/deactivate)
  
- **Boundary**: 
  - This ADR does **not** reopen ADR 0002 (which bans git hooks as a Memory System lifecycle mechanism). This guardrail is a distinct concern (repo-wide access control) implemented via harness-native hooks and direct `chmod`, with no `.git/hooks/*` script installed.

## Implementation

See `scripts/workspace_guard.py` for the lock state machine, `scripts/mcp_sync.py` for the harness adapter pattern, `setup.sh` for global harness registry + `sync_codex_extra`, and `docs/policies/workspace-guardrail.md` for user-facing policy and first-clone bootstrap notes.
