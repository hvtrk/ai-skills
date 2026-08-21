---
name: project-bootstrap
description: Fast and clean bootstrapping of new software projects following standard fullstack architecture and conventions.
---

# Project Bootstrap Playbook

Use this skill when creating a new full-stack repository or bootstrapping a greenfield project.

## Standard Initialization Sequence
1. **Clarify Requirements**: Determine stack choices (e.g. Next.js App Router + FastAPI + PostgreSQL + Redis).
2. **Scaffold Folder Structure**:
   - `frontend/`: Next.js, Tailwind CSS, TypeScript, TanStack Query.
   - `backend/`: FastAPI, SQLModel, Uvicorn, Layered API routes.
3. **Environment & Configuration**:
   - Create `.env.example` with required configuration keys.
   - Setup `Dockerfile` and `docker-compose.yml` for local development.
4. **Baseline Healthcheck**: Implement `/api/health` and basic frontend landing page to confirm connectivity.
5. **Connect AI Skills**: Run `~/ai-skills/setup.sh` to immediately enable all development skills.
