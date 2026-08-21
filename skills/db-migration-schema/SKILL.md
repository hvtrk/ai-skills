---
name: db-migration-schema
description: SQLModel & PostgreSQL schema design, relationships, indexing, and migration playbook. Use when designing models, altering tables, or writing database migrations.
---

# Database Schema & Migration Playbook

Use this skill when creating or modifying SQLModel entities, database tables, indexes, and migrations.

## 1. Schema Design Principles
- Use explicit field types, defaults, and nullable constraints with SQLModel `Field(...)`.
- Always include `id` (UUID or autoincrement integer), `created_at`, and `updated_at` timestamps.
- Add database indexes on frequently queried columns (e.g. `foreign_keys`, `slug`, `status`, `user_id`).
- Define foreign key relationships explicitly with cascade rules.

## 2. Safe Migration Workflow
1. **Define SQLModel entity**: Add or update model class in `backend/models/`.
2. **Generate / Write Migration**:
   - Create safe, idempotent SQL or Alembic migration steps.
   - For column renames or non-null additions on existing tables: provide default values or multi-step migration to prevent downtime.
3. **Update Seed Data**: Ensure `backend/init_db.py` or seed scripts remain consistent.
4. **Test Rollback**: Verify that changes can be rolled back safely without data corruption.
