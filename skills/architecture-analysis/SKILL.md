---
name: architecture-analysis
description: Analyze and document the architecture, dependency graph, API contracts, and conventions of an existing repository without modifying code.
---

# Architecture Analysis Playbook

Use this skill when onboarding into a new codebase or indexing an existing repository.

## Analysis Steps
1. **Identify Technology Stack**: Inspect package manifests (`package.json`, `requirements.txt`, `Cargo.toml`, `go.mod`).
2. **Map Directory Layout**: Document top-level directory responsibilities and module boundaries.
3. **Map Data Flow & Contracts**: Trace requests from client UI -> API Router -> Service -> Database / External APIs.
4. **Document Conventions**: Note naming conventions, state management patterns, error handling paradigms, and test strategies.
5. **Summary Report**: Output an architecture summary with mermaid diagrams highlighting key components.
