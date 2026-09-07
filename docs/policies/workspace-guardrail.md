# Workspace Activation Guardrail Policy

## Overview

The `ai-skills` repository is protected by an **OS-level workspace lock** that enforces read-only state at rest. Only the active harness session can make changes. This policy prevents indirect edits through symlinked skill paths from other projects and harnesses.

**See [ADR 0004](../adr/0004-workspace-activation-guardrail.md) for the design rationale and decision context.**

## What's Locked

When the workspace is locked, the following operations are **blocked**:

- Any file write (including source edits via editor or IDE)
- Any directory modification (creating, deleting, or renaming files)
- Git commits and index modifications
- Symlink target edits (key risk: indirect edits from linked skills in other projects)

**Preserved**: Read and execute permissions on all files and directories remain intact. You can always:
- Read files and directories
- Run scripts and executables
- Check status with `python3 scripts/workspace_guard.py status`

## Activating the Workspace

### Claude Code (automatic)

When you open this repository in Claude Code:
1. The `SessionStart` hook automatically runs (defined in `.claude/settings.json`)
2. The workspace is activated for your session
3. You can edit files freely
4. When you close the session, `SessionEnd` hook deactivates the workspace

**No manual action required.**

### Codex CLI

To activate the workspace for Codex CLI, run:

```bash
python3 scripts/workspace_guard.py activate --harness codex
```

To deactivate when done:

```bash
python3 scripts/workspace_guard.py deactivate --harness codex
```

### Antigravity

To activate the workspace for Antigravity, run:

```bash
python3 scripts/workspace_guard.py activate --harness antigravity
```

To deactivate when done:

```bash
python3 scripts/workspace_guard.py deactivate --harness antigravity
```

### Manual Activation (Command Line Edits)

If you need to edit files directly in your terminal/editor:

```bash
python3 scripts/workspace_guard.py activate --harness manual
```

Then edit or commit as needed. When done:

```bash
python3 scripts/workspace_guard.py deactivate --harness manual
```

## Checking Lock Status

To see the current lock state and active holders:

```bash
python3 scripts/workspace_guard.py status
```

For JSON output (useful for scripts):

```bash
python3 scripts/workspace_guard.py status --json
```

## Concurrent Sessions

You can have multiple Claude Code windows open on this repository simultaneously. Each window's `SessionStart` hook adds a holder with its own `session_id`. The workspace remains **unlocked** until the last window is closed.

Example:
```
window1 SessionStart → holder added, tree unlocked
window2 SessionStart → another holder added, tree still unlocked
window1 SessionEnd   → holder removed, tree still unlocked
window2 SessionEnd   → last holder removed, tree locked
```

## First-Clone Bootstrap

When you first `git clone` this repository, the `.workspace-lock.json` file does not exist, and the tree is **writable** (git does not preserve permission bits). After any deactivation, the tree becomes read-only. On the next activation, it unlocks again.

**First-time setup checklist:**

1. Clone the repository:
   ```bash
   git clone https://github.com/your-org/ai-skills.git
   cd ai-skills
   ```

2. Run setup.sh to initialize your harnesses:
   ```bash
   ./setup.sh --global
   ```

3. The first `deactivate` (or simply opening/closing Claude Code) will lock the tree.

4. On next activation, the lock engages and works normally.

## If the Lock Gets Stuck

If the workspace appears locked but you believe no session is active, check:

```bash
python3 scripts/workspace_guard.py status --json
```

Look for holders that are **stale**:
- Older than 12 hours → automatically cleaned up on next activate/deactivate
- From a dead PID on your machine → cleaned up on next activate/deactivate
- From a different machine with a dead PID → kept for 12 hours (cross-machine safety margin)

To force-clear all holders (emergency only):

```bash
python3 scripts/workspace_guard.py deactivate
```

This removes all holders and locks the tree. Then:

```bash
python3 scripts/workspace_guard.py activate --harness manual
```

## Never Bypass the Lock

Do **not**:
- Manually chmod the tree to bypass the lock
- Disable hooks in `.claude/settings.json`
- Delete `.workspace-lock.json`

These are symlink-safety mechanisms. Bypassing them defeats the purpose and opens the repo to silent corruption from indirect edits through shared skills.

If you find yourself wanting to bypass the lock, instead:
1. Check `python3 scripts/workspace_guard.py status`
2. Activate for your harness as described above
3. Ask for help in team channels if the lock seems stuck

## Support

For questions or issues:
1. Check the lock status: `python3 scripts/workspace_guard.py status`
2. Review this policy and [ADR 0004](../adr/0004-workspace-activation-guardrail.md)
3. Reach out to the repository maintainer

## Related Documentation

- [ADR 0004: Workspace Activation Guardrail](../adr/0004-workspace-activation-guardrail.md) — Design decision and rationale
- [Root instruction files](../../) — `CLAUDE.md`, `AGENTS.md`, `GEMINI.md` (brief pointers to this policy)
- [`scripts/workspace_guard.py`](../../scripts/workspace_guard.py) — Implementation (see module docstring)
