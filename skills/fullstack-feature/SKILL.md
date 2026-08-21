---
name: fullstack-feature
description: End-to-end full-stack feature scaffolding connecting FastAPI backend (layered architecture) with Next.js frontend (App Router, TanStack Query, Tailwind CSS). Use when implementing or extending full-stack features.
---

# Full-Stack Feature Scaffolding

Follow this step-by-step playbook to implement an end-to-end fullstack feature connecting FastAPI and Next.js.

## 1. Architecture Alignment & Evidence Inspection
- Check existing backend routes in `backend/api/routes/` and database models.
- Check existing frontend routes in `frontend/app/` (or `frontend/src/`) and UI components.
- Establish the data contract (Pydantic models in FastAPI <-> TypeScript interfaces in Next.js).

## 2. Backend Layered Implementation
Create `backend/api/routes/<feature_name>/`:
- `__init__.py`: Export public router (`from .public import router as public_router`) and/or protected router (`from .protected import router as protected_router`).
- `public.py` / `protected.py`: HTTP endpoint routing, request validation, response serialization. Keep routers thin.
- `service.py`: Business logic, coordinating repository operations, caching (Redis), external notifications (Resend/GCS).
- `repository.py`: CRUD operations and database persistence using SQLModel / SQLAlchemy session.
- Register routers explicitly in `backend/api/routes/__init__.py` or `backend/main.py`.

## 3. Frontend Implementation
- Define TypeScript types matching the backend schemas.
- Implement data-fetching hooks using `@tanstack/react-query` (`useQuery`, `useMutation`).
- Create UI components with Tailwind CSS and Framer Motion for smooth interactions.
- Provide loading states (skeletons), error boundaries, and empty state fallbacks.
- Add admin studio / dashboard views if applicable under `frontend/app/(admin)/(protected)/studio/<feature_name>/`.

## 4. Verification & Consistency Checklist
- [ ] Backend routes return expected status codes (200, 201, 400, 404, 401, 403).
- [ ] TypeScript interfaces match Pydantic schemas exactly.
- [ ] Query cache invalidation occurs properly on mutations (`queryClient.invalidateQueries`).
- [ ] No direct SQL/DB calls in routers or frontend components.
