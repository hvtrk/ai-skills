---
name: skill-creator
description: Create, author, and register new on-demand skills (SKILL.md) or convert legacy workflows into modular skills. Triggers on /create-skill, /skill-creator.
---

# Skill Creator & Migration Playbook

Use this skill to author new on-demand AI skills or convert legacy workflow markdown files into standardized Agent Skills.

## 1. Skill Specification Standards
Every skill in `skills/<skill-name>/` must follow this structure:
```text
skills/<skill-name>/
├── SKILL.md           # [Required] Main instruction file with YAML frontmatter
├── references/        # [Optional] Detailed documentation or domain references
├── templates/         # [Optional] Code scaffolding templates
└── scripts/           # [Optional] Helper scripts or automation
```

### Standard YAML Frontmatter
```markdown
---
name: <skill-name>
description: <Concise 1-2 sentence description explaining what the skill does and the exact keywords/intents that should trigger it>
---

# <Skill Title>

## When to Use This Skill
- Clear trigger conditions...

## Step-by-Step Instructions
1. ...
2. ...

## Checklist & Verification
- [ ] ...
```

## 2. Authoring Workflow
1. **Check for Overlaps**: Search existing skills in `~/ai-skills/skills/` to ensure the new skill does not duplicate or conflict with existing domains.
2. **Draft `SKILL.md`**: Keep instructions concise, actionable, and structured with checklists.
3. **Add References or Templates**: Place large reference guides or boilerplate files in subfolders (`references/`, `templates/`) so they load only on demand.
4. **Register Globally**: Run `~/ai-skills/setup.sh` to immediately symlink the new skill across Antigravity, Claude Code, OpenCode/Codex, and Cursor.
5. **Test Discovery**: Trigger the skill via `/<skill-name>` or semantic chat prompts.
