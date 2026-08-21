---
name: nextjs-frontend
description: Next.js App Router and React component builder with Tailwind CSS, Framer Motion animations, TanStack Query integration, and accessibility best practices.
---

# Next.js Frontend Component & Route Builder

Use this skill when building modern React 19 / Next.js (App Router) pages, components, and hooks.

## Guidelines & Best Practices

### 1. Component Separation (Server vs Client)
- **Server Components (RSC)**: Default for data fetching, static layout, and SEO. Keep async operations on the server where possible.
- **Client Components (`'use client'`)**: Use only when requiring state (`useState`, `useReducer`), browser APIs, Framer Motion animations, or event handlers (`onClick`, `onChange`).

### 2. Styling & Motion
- Use **Tailwind CSS** semantic utilities. Avoid arbitrary unstandardized color values when theme variables exist.
- Use **Motion / Framer Motion** (`motion.div`, `AnimatePresence`) for entrance animations, hover micro-interactions, and layout transitions.
- Ensure responsive design across mobile (`sm:`), tablet (`md:`), and desktop (`lg:`, `xl:`).

### 3. State Management & Data Fetching
- Use `@tanstack/react-query` for asynchronous server state management.
- Wrap mutations with `useMutation` and automatically invalidate relevant query keys on success.
- Use clean TypeScript interfaces for all props and data contracts.

### 4. Resilient UI States
Every data-driven component must handle all 4 UI states:
1. **Loading**: Skeleton placeholder or smooth spinner.
2. **Empty**: Contextual message when list/data is empty.
3. **Error**: User-friendly error message with retry capability.
4. **Success**: The fully rendered interactive UI.
