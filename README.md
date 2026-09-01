# AI Engineering Skills Hub (`ai-skills`) — v3.0

[![Version](https://img.shields.io/badge/version-3.0.0-blue.svg)](https://github.com/hvtrk/ai-skill-rules)
[![Architecture](https://img.shields.io/badge/architecture-two--tier--memory-green.svg)](https://github.com/hvtrk/ai-skill-rules)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A centralized, portable, and ultra-lean AI skills repository for modern software engineering workflows.

Designed for high performance and zero context bloat. The Memory System Core is filesystem-only and harness-independent; harness adapters are separate work.

---

## ⚡ What's New in v3.0

| Feature | v2.0 | v3.0 (Current) |
| :--- | :--- | :--- |
| **Memory Architecture** | Global skills only (stateless across sessions) | **Two-Tier Persistent Memory**: Machine-wide conventions (`~/.agents/memory/`) + isolated workspace memory (`.memory/`) |
| **Context Management** | Full repo inspection per task | **Hierarchical Level-0 Router (`.memory/INDEX.md` <40 lines)**; topic files loaded on-demand |
| **Session Continuity** | Chat transcript dependent | **Dedicated ephemeral `session-handoff.md`** for agent-guided continuation and graduation |
| **Project Isolation** | No local memory standard | **Strict project workspace boundary** with user-managed persistence policy |
| **Compaction & Anti-Drift** | Manual | **Append-and-replace compaction** with cold storage `.memory/archive/` (prevents hallucinating on obsolete notes) |
| **Curated Suite** | 28 skills | **32 skills** including `project-memory`, `memory-lint`, `grill-with-docs`, and `wayfinder` |

---

## 🧠 System Architecture

```mermaid
flowchart TD
    subgraph GlobalTier["Global Tier (Machine-Wide & Agnostic)"]
        GP["~/.agents/memory/user-profile.md<br/>(Developer Profile, Tools, OS)"]
        GC["~/.agents/memory/conventions.md<br/>(Universal Coding Ethos & Styling)"]
        GS["~/ai-skills/skills/<br/>(32 Curated On-Demand Skills)"]
    end

    subgraph Harnesses["Harness Adapters & Integration"]
        AG["Antigravity (~/.gemini/config/skills, ~/.gemini/GEMINI.md)"]
        CC["Claude Code (~/.claude/skills, CLAUDE.md)"]
        OC["OpenCode (~/.config/opencode/skills)"]
        CR["Cursor / Windsurf (.cursorrules)"]
        GA["Global Agents (~/.agents/skills)"]
    end

    subgraph ProjectWorkspace["Project Workspace (<project-root>)"]
        IDX[".memory/INDEX.md<br/>(Fast Level-0 Router <40 lines)"]
        DOM[".memory/domain.md<br/>(Domain Concepts & Glossary)"]
        ARC[".memory/architecture.md<br/>(Tech Stack & ADR Links)"]
        GOT[".memory/gotchas.md<br/>(Resolved Traps & Environment Quirks)"]
        SES[".memory/session-handoff.md<br/>(Ephemeral Task State)"]
        ACH[".memory/archive/...<br/>(Cold Storage for Superseded Records)"]
    end

    GlobalTier --> Harnesses
    Harnesses -->|1. Reads Index| IDX
    IDX -.->|2. Loads ONLY if relevant| DOM
    IDX -.->|2. Loads ONLY if relevant| ARC
    IDX -.->|2. Loads ONLY if relevant| GOT
    IDX -.->|2. Loads if resuming| SES

    classDef global fill:#1e293b,stroke:#38bdf8,stroke-width:2px,color:#fff;
    classDef harness fill:#0f172a,stroke:#818cf8,stroke-width:2px,color:#fff;
    classDef project fill:#1e1e38,stroke:#10b981,stroke-width:2px,color:#fff;
    class GP,GC,GS global;
    class AG,CC,OC,CR,GA harness;
    class IDX,DOM,ARC,GOT,SES,ACH project;
```

---

## 🚀 Quickstart

### 1. Global Installation (1 Command)
```bash
# Clone the repository
git clone git@github.com:hvtrk/ai-skill-rules.git ~/ai-skills

# Run the installer (seeds ~/.agents/memory and links all harnesses)
cd ~/ai-skills
chmod +x setup.sh
./setup.sh --global
```
*The installer seeds global defaults and links configured skill destinations across Antigravity, Claude Code, OpenCode, and `~/.agents/skills/`.*

### 2. Antigravity-Specific Setup
To install skills and configure global rules specifically for Google Antigravity:
```bash
~/ai-skills/setup.sh --antigravity
```
*Installs symlinks into `~/.gemini/config/skills/` and configures `~/.gemini/config/rules/memory.md` & `~/.gemini/GEMINI.md`.*

### 3. Initialize Memory in a Project Workspace
To bootstrap the `.memory/` structure into any project safely via Memory Core:
```bash
# From ~/ai-skills:
./setup.sh --memory-init /path/to/my-project

# Or from anywhere via project flag:
~/ai-skills/setup.sh --project /path/to/my-project
```
*(Idempotent: If `.memory/` already exists, existing documentation is safely preserved.)*

### 4. Check Sync & Memory Status
```bash
~/ai-skills/setup.sh --status
```

### 5. Importing New Skills from `npx skills add`
```bash
~/ai-skills/setup.sh --import
~/ai-skills/setup.sh --global
```

### 6. MCP Multi-Harness Sync
Declare MCP servers once in `mcp/servers.json`, then sync them to each harness's own config format (`~/.claude.json`, OpenCode's `opencode.json`, Antigravity's `mcp.json`). See [mcp/README.md](mcp/README.md) for the manifest schema and safety model (dry-run by default; only entries this tool created are ever touched).
```bash
~/ai-skills/setup.sh --sync-mcp            # dry-run preview, writes nothing
~/ai-skills/setup.sh --sync-mcp --apply    # write for real
```

---

## 🗂 Memory Management & Usage Guide

The memory architecture solves context window exhaustion and cross-project pollution using a **Hierarchical (Option C)** retrieval model. For full details on the lifecycle, see the [Project Memory Lifecycle Guide](docs/project-memory-lifecycle-guide.md) and [ADR-0002](docs/adr/0002-memory-system-v2-filesystem-first-harness-agnostic.md).

### 1. The Two Tiers

| Tier | Path | Purpose |
| :--- | :--- | :--- |
| **Global Memory** | `~/.agents/memory/` | Machine-wide developer profile (`user-profile.md`) and universal coding conventions (`conventions.md`). |
| **Project Memory** | `<project-root>/.memory/` | Workspace-specific domain terms, tech stack patterns, gotchas, and session handoffs. |

### 2. File Taxonomy in `<project-root>/.memory/`

```text
.memory/
├── INDEX.md              # Compact Level-0 router (<40 lines). Always read first.
├── domain.md             # Core business entities, glossary, ubiquitous language.
├── architecture.md       # Tech stack, module boundaries, data flows, key ADR links.
├── gotchas.md            # Non-obvious edge cases, environment quirks, resolved traps.
├── session-handoff.md    # Ephemeral active state: goal, dead-ends, next steps.
└── archive/              # Cold storage: superseded decisions (never queried in daily work).
```

### 3. Memory Core Operations (Phase 3: Lifecycle Mutations)
 
- `python3 ~/ai-skills/scripts/memory.py init <project>`: Safely initializes project memory without overwriting existing files.
- `python3 ~/ai-skills/scripts/memory.py check <project>`: Validates deterministic project-memory structure, headings, INDEX limit, frontmatter, archive metadata, local links, and handoff freshness.
- `python3 ~/ai-skills/scripts/memory.py retrieve <project> [--profile] [--topic <topic>]`: Performs lazy, explicit retrieval of memory files.
- `python3 ~/ai-skills/scripts/memory.py update <project> --input plan.json`: Atomically updates an agent-selected durable topic under lock with duplicate and conflict prevention.
- `python3 ~/ai-skills/scripts/memory.py handoff <project> --input handoff.json`: Writes agent-provided unfinished-work and continuation state.
- `python3 ~/ai-skills/scripts/memory.py graduate <project> --plan plan.json`: Transactionally promotes handoff knowledge to durable topic files and resets the handoff template upon validation.
- `python3 ~/ai-skills/scripts/memory.py archive <project> --input archive.json`: Archives an agent-selected superseded record with provenance frontmatter into `.memory/archive/`.
 
### 4. Persistence Policy
 
Memory System v2 does not inspect or manage version control. The user decides whether `.memory/` is shared, local, ignored, backed up, or otherwise persisted. The optional `.gitignore` template is intentionally not applied by the Memory Core.

---

## 🛠 Available Skills Suite (32 Curated Skills)

| Category | Skill | Trigger / Command | Description |
| :--- | :--- | :--- | :--- |
| **Memory** | `project-memory` | `memory` | Guides two-tier memory; Memory Core CLI implements init, validation check, retrieval, updates, handoffs, graduation, and archiving. |
| **Memory** | `memory-lint` | `/memory-lint` | Structural health check for `.memory/` (INDEX size, required files, frontmatter, handoff freshness); reports `scripts/memory.py check` findings in plain language. |
| **Fullstack** | `fullstack-feature` | `/fullstack-feature` | Scaffolds end-to-end features connecting FastAPI backend with Next.js frontend UI & TanStack Query. |
| **Backend** | `fastapi-backend` | `/fastapi-backend` | Generates layered FastAPI endpoints (`public.py`, `protected.py`, `service.py`, `repository.py`). |
| **Frontend** | `nextjs-frontend` | `/nextjs-frontend` | Builds React 19 / Next.js App Router components with Tailwind v4 and Motion animations. |
| **Database** | `db-migration-schema` | `/db-migration-schema` | Guides SQLModel schema creation, PostgreSQL relationships, and safe migrations. |
| **Database** | `supabase` | `/supabase` | Supabase database, auth, SSR, storage, vectors, edge functions, and CLI workflows. |
| **Database** | `supabase-postgres-best-practices` | `postgres optimization` | Postgres query profiling, index strategies, connection limits, and RLS security. |
| **UI Design** | `design-it` | `/design-it` | 30 production UI aesthetics (Bento, Neomorphism, Brutalism, Minimal, Glassmorphism, etc.). |
| **UI Design** | `redesign-existing-projects` | `/redesign-existing-projects` | Overhauls and modernizes UI styling, typography, color palettes, and micro-interactions. |
| **Quality** | `codebase-audit-pre-push` | `/codebase-audit-pre-push` | Sanitizes repo, removes junk files, checks secret leaks, and verifies pre-push hygiene. |
| **Quality** | `performance-optimizer` | `/performance-optimizer` | Measures and eliminates bottlenecks in DB queries, API latency, and frontend rendering. |
| **Quality** | `systematic-debugging` | `/debug`, `/bug-hunter` | Disciplined 6-phase root-cause debugging loop with fast feedback loop creation. |
| **Quality** | `logic-lens` | `/logic-lens` | Deep formal reasoning and logical verification of edge cases, security, and contracts. |
| **Quality** | `code-review` | `/code-review` | Thorough review for architectural consistency, security, and release readiness. |
| **Architecture** | `improve-codebase-architecture`| `/improve-codebase-architecture` | Deepens shallow modules, eliminates architectural friction, and establishes testable seams. |
| **Architecture** | `architecture-analysis` | `/architecture-analysis` | Analyzes codebase structure, data flows, and creates architecture documentation. |
| **Architecture** | `domain-modeling` | `/domain-modeling` | Builds and sharpens domain models, CONTEXT.md, and Architectural Decision Records (ADRs). |
| **Architecture** | `grill-with-docs` | `/grill-me`, `/grill-with-docs` | Relentless interview to sharpen a plan or design, generating ADRs and glossary docs iteratively. |
| **Engineering** | `tdd` | `/tdd` | Test-driven development red-green-refactor cycle with unit and integration tests. |
| **Engineering** | `prototype` | `/prototype` | Builds throwaway prototypes to flesh out state/business logic or UI variations. |
| **Engineering** | `to-spec` | `/to-spec` | Synthesizes chat conversation into actionable technical specifications. |
| **Engineering** | `to-tickets` | `/to-tickets` | Breaks down plans/specs into tracer-bullet tickets with dependency edges. |
| **Engineering** | `wayfinder` | `/wayfinder` | Charts large-scale initiatives as a shared map of decision tickets on issue trackers. |
| **Engineering** | `project-bootstrap` | `/project-bootstrap` | Initializes a clean full-stack repository with boilerplate architecture. |
| **Engineering** | `technical-change-tracker` | `/track-changes` | Structured JSON change logs and state machine handoffs between agent sessions. |
| **Agent Tooling** | `skill-creator` | `/create-skill` | Authors, converts, and automatically registers new on-demand skills. |
| **Agent Tooling** | `skill-harness-sync` | `/skill-harness-sync` | Audits, imports from `npx skills add`, and synchronizes across all agent harnesses. |
| **Agent Tooling** | `skill-development` | `skill development` | Best practices for building robust Claude Code plugins and tool workflows. |
| **Agent Tooling** | `skill-check` | `/skill-check` | Validates skills against the agentskills specification to catch structural issues. |
| **Agent Tooling** | `writing-for-agents` | `writing for agents` | Rules and guidelines for authoring agent instruction files (`AGENTS.md`, `CLAUDE.md`). |
| **Agent Tooling** | `mcp-integration` | `mcp integration` | Guidance for connecting and configuring Model Context Protocol servers. |

---

## 🌿 Version History & Branching Strategy

This repository maintains versioned release branches:

- **`master`** — Production default branch containing the active release (v3.0).
- **`v_3`** — Active v3 development branch (Two-Tier Hierarchical Markdown Memory Architecture).
- **`v_2`** — Modular on-demand skills architecture snapshot.
- **`v_1`** — Legacy snapshot containing the original `.agents/` monolithic rules and playbooks.

> [!IMPORTANT]
> **Branching Rule**: All changes, additions, and documentation updates MUST be committed to the development branch (e.g. `v_3`) first and then merged into `master`. No direct commits or pushes to `master`.

---

## 📄 License
MIT License. Maintained by Rahul ([@hvtrk](https://github.com/hvtrk)).
