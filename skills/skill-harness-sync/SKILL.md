---
name: skill-harness-sync
description: >-
  Synchronizes, audits, and curates AI engineering skills across all agent harnesses
  (Google Antigravity, Claude Code, OpenCode/Codex, and global ~/.agents/skills).
  Use whenever newly installed skills from 'npx skills add' need to be imported into ~/ai-skills,
  audited for quality, or synced across all machine-wide agent configurations.
---

# Skill & Harness Synchronizer (`skill-harness-sync`)

Provides an automated workflow to import, audit, migrate, and distribute skills from local harnesses (like `~/.agents/skills/` populated by `npx skills add`) into the central version-controlled repository (`~/ai-skills`), and symlink them across all active AI coding environments.

---

## Supported Harnesses & Global Paths

| Harness | Global Skills Path | Project-Level Skills Path |
| :--- | :--- | :--- |
| **Google Antigravity** | `~/.gemini/config/skills/` | `<repo>/.agents/skills/` |
| **Claude Code** | `~/.claude/skills/` | `<repo>/.claude/skills/` or `<repo>/.agents/skills/` |
| **OpenCode / Codex** | `~/.config/opencode/skills/` | `<repo>/.agents/skills/` |
| **Global Agent Harness** | `~/.agents/skills/` | `<repo>/.agents/skills/` |

---

## Workflow: Importing & Syncing New Skills

### Step 1: Detect Newly Added Skills
When you install skills using package managers (e.g. `npx skills add <source> -g`), they are deposited directly in `~/.agents/skills/`.

Run the synchronizer in discovery mode:
```bash
~/ai-skills/setup.sh --status
```
or import unmanaged skills:
```bash
~/ai-skills/setup.sh --import
```

### Step 2: Audit & Curate
Inspect newly discovered skills:
1. Verify `SKILL.md` has valid YAML frontmatter (`name`, `description`).
2. Check for duplicate capabilities with existing skills in `~/ai-skills/skills/`.
3. Check for external dependencies or scripts in `scripts/` or `references/`.

### Step 3: Centralize & Sync Globally
Run the global synchronizer:
```bash
~/ai-skills/setup.sh --global
```
This will:
- Link all curated skills into Antigravity, Claude Code, OpenCode, and `~/.agents/skills`.
- Clean up any stale or dead symlinks.

### Step 4: Version Control
Commit newly added skills to the `ai-skills` git repository so they are backed up and synced to your other development machines:
```bash
cd ~/ai-skills
git add skills/
git commit -m "feat(skills): add <skill-name>"
git push
```
