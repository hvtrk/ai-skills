# AI Engineering Skills Hub (`ai-skills`)

A centralized, portable, and ultra-lean AI skills repository for modern software engineering workflows.

Designed for high performance, zero context bloat, and universal compatibility across **Antigravity**, **Claude Code**, **OpenCode / Codex**, and **Cursor / Windsurf**.

---

## ⚡ Key Highlights

- **Zero Context Bloat**: Universal operating principles are kept ultra-compact (`rules/core.md` < 40 lines). All playbooks and specialized guides are packaged as on-demand skills (`SKILL.md`) that load dynamically only when triggered.
- **Zero-Copy Setup**: No more copy-pasting `.agents/` directories into every project repository. Global symlinks enable all agent harnesses to access your skills from anywhere.
- **Cross-Agent Compatible**: Works out-of-the-box across Google Antigravity, Anthropic Claude Code, OpenAI Codex / OpenCode, and Cursor.
- **1-Command Portability**: Clone once on any new system and run `./setup.sh` to instantly activate all skills.

---

## 🚀 Quickstart

### 1. New Machine Setup
```bash
# Clone the repository
git clone git@github.com:hvtrk/ai-skill-rules.git ~/ai-skills

# Run the installer
cd ~/ai-skills
chmod +x setup.sh
./setup.sh
```

### 2. Optional: Link into a Specific Project
If a specific repository requires local `.agents/skills` or `.cursorrules`:
```bash
cd ~/ai-skills
./setup.sh --project /path/to/my-project
```

---

## 📁 Repository Structure

```text
~/ai-skills/
├── README.md                  # Documentation and setup guide
├── setup.sh                   # Automated multi-agent symlinker & installer
├── rules/
│   └── core.md                # Ultra-compact universal engineering rules (<40 lines)
├── skills/
│   ├── fullstack-feature/     # End-to-end FastAPI + Next.js feature scaffolding
│   ├── fastapi-backend/       # Layered API: public/protected/service/repository
│   ├── nextjs-frontend/       # React 19, App Router, Tailwind v4, TanStack Query
│   ├── db-migration-schema/   # SQLModel schemas, PostgreSQL migrations & indexing
│   ├── codebase-audit-pre-push/# Pre-push git cleaner, secret scanner, and hygiene
│   ├── performance-optimizer/ # Profiling, database indexes, API latency, memoization
│   ├── systematic-debugging/  # 6-phase debugging loop & common pattern fixes
│   ├── improve-codebase-architecture/# Architectural friction scanner & seam creation
│   ├── redesign-existing-projects/   # UI/UX aesthetic audit & visual restyling
│   ├── code-review/           # Architecture consistency & PR review playbook
│   ├── project-bootstrap/     # Greenfield repository bootstrapping
│   ├── architecture-analysis/ # Codebase indexing & dependency mapping
│   └── skill-creator/         # Meta-skill for authoring and registering skills
└── adapters/
    ├── claude/                # Claude Code integration templates
    ├── antigravity/           # Antigravity config mapping
    └── cursor/                # Cursor IDE / Windsurf rules fallback
```

---

## 🛠 Available Skills Suite (13 Skills)

| Skill | Trigger / Command | Domain & Description |
| :--- | :--- | :--- |
| **`fullstack-feature`** | `/fullstack-feature` | Scaffolds end-to-end feature connecting FastAPI backend with Next.js frontend UI & TanStack Query. |
| **`fastapi-backend`** | `/fastapi-backend` | Generates layered FastAPI endpoints (`public.py`, `protected.py`, `service.py`, `repository.py`). |
| **`nextjs-frontend`** | `/nextjs-frontend` | Builds React 19 / Next.js App Router components with Tailwind v4 and Motion animations. |
| **`db-migration-schema`** | `/db-migration-schema` | Guides SQLModel schema creation, PostgreSQL relationships, and safe migrations. |
| **`codebase-audit-pre-push`** | `/codebase-audit-pre-push` | Sanitizes repo, removes junk files, checks secret leaks, and verifies pre-push git hygiene. |
| **`performance-optimizer`** | `/performance-optimizer` | Measures and eliminates bottlenecks in DB queries, API latency, and frontend rendering. |
| **`systematic-debugging`** | `/debug`, `/bug-hunter`, `/diagnose` | Disciplined 6-phase root-cause debugging loop with fast feedback loop creation. |
| **`improve-codebase-architecture`**| `/improve-codebase-architecture` | Deepens shallow modules, eliminates architectural friction, and establishes testable seams. |
| **`redesign-existing-projects`** | `/redesign-existing-projects` | Overhauls and modernizes UI styling, typography, color palettes, and micro-interactions. |
| **`code-review`** | `/code-review` | Thorough review for architectural consistency, security, and release readiness. |
| **`project-bootstrap`** | `/project-bootstrap` | Initializes a clean full-stack repository with boilerplate architecture. |
| **`architecture-analysis`** | `/architecture-analysis` | Analyzes codebase structure, data flows, and creates architecture documentation. |
| **`skill-creator`** | `/create-skill`, `/skill-creator` | Authors, converts, and automatically registers new on-demand skills across agent harnesses. |

---

## ➕ Adding or Improving Skills

To add a new skill:
1. Use `/create-skill` or create a directory under `skills/<new-skill-name>/`.
2. Add a `SKILL.md` file with standard YAML frontmatter (`name`, `description`).
3. Run `./setup.sh` to update symlinks across all agent harnesses.
4. Commit and push your changes to GitHub (`git push origin master`).

---

## 📄 License
MIT License. Maintained by Rahul (@hvtrk).
