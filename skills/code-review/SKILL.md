---
name: code-review
description: Comprehensive code review, architectural consistency check, PR inspection, and production-readiness validation.
---

# Code Review & Architecture Validation Playbook

Use this skill when reviewing code, checking pull requests, or validating release readiness.

## Review Dimensions

### 1. Architectural Consistency
- Does the code follow established project structure and layering?
- Are concerns separated (e.g., no database logic in API routers, no API logic in UI components)?
- Are shared utilities placed in standard shared directories rather than duplicated?

### 2. Evidence-Based Correctness & Scope
- Does the implementation solve the approved requirement without scope creep?
- Were unnecessary files or opportunistic refactoring avoided?
- Are all edge cases (nulls, empty lists, connection drops) handled?

### 3. Security & Reliability
- Are inputs validated at the boundary?
- Are database queries parameterized against SQL injection?
- Are authentication and authorization checks enforced on protected endpoints?
- Are sensitive keys/tokens kept out of code and client bundles?

### 4. Performance & Caching
- Are database queries indexed? No N+1 query patterns.
- Are expensive queries cached in Redis where applicable?
- Are React components re-rendering efficiently?

## Review Output Format
Provide a concise, categorized summary:
- **Critical / Blocker**: Bugs, security vulnerabilities, or architectural violations that must be fixed.
- **Improvement**: Suggestions for readability, performance, or typing.
- **Verdict**: `Approved`, `Changes Requested`, or `Needs Discussion`.
