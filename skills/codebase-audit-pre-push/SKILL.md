---
name: codebase-audit-pre-push
description: Deep audit before git push or pull request. Deletes junk files, checks for secret leaks, removes dead code/debug statements, and validates production readiness.
---

# Pre-Push Codebase Audit & Sanitization

Run this playbook before pushing code to GitHub or preparing a release to ensure the repository is clean, secure, and production-ready.

## 1. Junk File & Build Artifact Cleanup
Scan for and remove unnecessary files that must not enter git history:
- **OS Files**: `.DS_Store`, `Thumbs.db`, `desktop.ini`
- **Logs**: `*.log`, `npm-debug.log*`, `yarn-error.log*`
- **Temp & Cache**: `*.tmp`, `*.temp`, `*.swp`, `.pytest_cache/`, `.ruff_cache/`
- **Build / Runtime Artifacts**: `dist/`, `build/`, `.next/`, `__pycache__/`, `*.pyc`
- **Coverage & Test Dumps**: `coverage/`, `.nyc_output/`, `test-results/`
- **Scratch Notes**: Uncommitted scratchpads, temporary debug files.

## 2. Secrets & Credential Leak Scanning (CRITICAL BLOCKER)
- Verify `.env` files are never tracked in git (ensure `.env.example` exists without secrets).
- Scan for hardcoded credentials, API keys (`sk_...`, `AIza...`), private keys (`*.pem`, `*.key`), and service account tokens.
- If any secret is detected, immediately stop and alert the user.

## 3. Code Hygiene & Dead Code Removal
- **Console / Debug Artifacts**: Remove untagged `console.log`, `print()`, `debugger`, `test.only`.
- **Dead Code**: Remove commented-out code blocks, unused imports, uncalled private helpers, and unreachable code.
- **Naming & Magic Values**: Replace magic numbers/strings with named constants; ensure descriptive variable names.
- **Type Safety**: Eliminate unnecessary `any` types in TypeScript; ensure correct parameter typing in Python.

## 4. Security & Safety Checklist
- [ ] No raw SQL string concatenation (parameterized queries only).
- [ ] No command injection vectors (`exec` / `eval` with unsanitized inputs).
- [ ] Authentication & authorization checks enforced on server-side endpoints.
- [ ] Input schemas strictly validated at API boundaries.

## 5. Git & Verification Sanity
- Run repository build and test commands (`npm run build`, `npm run lint`, `pytest`).
- Check `git status` to ensure only intended changes are staged.
