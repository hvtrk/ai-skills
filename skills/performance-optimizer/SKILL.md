---
name: performance-optimizer
description: Identifies, profiles, and eliminates performance bottlenecks across database queries, backend APIs, and frontend rendering. Focuses on measurement-first improvements.
---

# Performance Optimization Playbook

Use this skill when diagnosing slow operations, high API latencies, slow database queries, or sluggish frontend rendering.

## Core Rule: Measure First, Fix Second
Never optimize based on intuition. Always capture a baseline measurement before touching code.

## 1. Database Query Optimization
- **N+1 Queries**: Replace loop-based queries with relational `JOIN`s, batch loading, or `selectinload`.
- **Missing Indexes**: Run `EXPLAIN ANALYZE` on slow queries. Add B-tree indexes on frequently filtered (`WHERE`), joined (`FOREIGN KEY`), or sorted (`ORDER BY`) columns.
- **Column Pruning**: Avoid `SELECT *`. Select only required fields.
- **Pagination**: Ensure list endpoints enforce `limit` and cursor/offset pagination.

## 2. Backend & API Latency
- **Parallel Asynchronous Operations**: Use `asyncio.gather` (Python) or `Promise.all` (Node/TS) for independent network or database calls.
- **Caching Layer**: Cache expensive, read-heavy query results in Redis or in-memory caches with clear TTL and invalidation strategies.
- **Payload Compression & Streaming**: Enable gzip/brotli compression; stream large file downloads or report generation.

## 3. Frontend & React/Next.js Optimization
- **Prevent Unnecessary Re-renders**: Memoize heavy components (`React.memo`) and expensive computations (`useMemo`).
- **Bundle Size & Code Splitting**: Lazy-load heavy components (`React.lazy` / `dynamic`) and import only specific modular utilities.
- **Image & Media Optimization**: Use modern WebP/AVIF formats, responsive `srcset`, explicit dimensions to prevent layout shifts (CLS), and `loading="lazy"`.

## 4. Verification
- Measure post-optimization execution time.
- Verify that output, functionality, and edge-case behavior remain identical.
