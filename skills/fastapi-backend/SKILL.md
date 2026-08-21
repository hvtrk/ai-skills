---
name: fastapi-backend
description: FastAPI backend service and endpoint generator adhering strictly to layered separation (router, service, repository, schemas, models) with SQLModel, PostgreSQL, and Redis caching.
---

# FastAPI Backend Architecture & Endpoint Generator

Use this skill when creating or modifying backend services and endpoints in FastAPI.

## Layered Organization Standards
Every feature in `backend/api/routes/<feature_name>/` must maintain strict separation:

```text
feature_name/
├── __init__.py        # Exposes routers
├── public.py          # Public HTTP endpoints (read-only, public data)
├── protected.py       # Protected HTTP endpoints (auth required, admin CRUD)
├── service.py         # Business logic, caching, external APIs
└── repository.py      # Database CRUD operations via SQLModel session
```

## Layer Responsibilities

### 1. Router Layer (`public.py` / `protected.py`)
- Define HTTP methods, status codes, query/path parameters, and request body.
- Handle dependency injection (`SessionDep`, `CurrentUserDep`).
- Call service methods and return response schemas.
- **NEVER** write SQL queries or complex business rules in routers.

### 2. Service Layer (`service.py`)
- Encapsulate all business logic and validation rules.
- Coordinate multiple repositories if needed.
- Manage caching (Redis get/set/invalidate) and background jobs.
- Raise domain/HTTP exceptions when validation fails.
- **NEVER** inspect raw HTTP request objects.

### 3. Repository Layer (`repository.py`)
- Pure data access and persistence layer.
- Execute SQLModel/SQLAlchemy queries (`select`, `exec`, `add`, `commit`, `refresh`).
- Handle filtering, sorting, pagination, and transactional consistency.

## Standard Workflow
1. Define or update SQLModel models in `backend/models/` or schemas.
2. Implement repository CRUD functions in `repository.py`.
3. Implement business logic and validation in `service.py`.
4. Expose endpoints in `public.py` and/or `protected.py`.
5. Register router in `backend/api/routes/__init__.py` or `backend/main.py`.
6. Verify endpoints via OpenAPI docs or automated test suites.
