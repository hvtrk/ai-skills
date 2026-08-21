---
name: improve-codebase-architecture
description: Identifies architectural friction, eliminates leaky abstractions, and refactors shallow modules into deep, well-encapsulated boundaries without breaking external contracts.
---

# Codebase Architecture Improvement & Refactoring

Use this skill when refactoring complex modules, reducing coupling, improving testability, or modernizing codebase structure.

## Core Architectural Principles
- **Deep Modules**: Prefer modules with simple, clean interfaces that hide significant internal complexity.
- **Locality**: Code that changes together should live together. Avoid scattering single logical concepts across dozens of micro-files.
- **The Deletion Test**: When considering an abstraction, ask: *"Would deleting it concentrate complexity in a clear place, or just move it around?"*
- **Clear Seams**: Interfaces should represent natural boundaries for testing and modular replacement.

## Refactoring Workflow
1. **Analyze Friction Points**:
   - Trace areas where a simple feature requires touching 5+ different directories.
   - Locate "shallow" modules where the interface is as complicated as the implementation.
   - Identify circular dependencies and god objects.
2. **Design Target Interfaces**:
   - Define minimal, expressive contracts.
   - Ensure backward compatibility with existing consumers or provide a clear migration path.
3. **Execute Incremental Refactoring**:
   - Move code behind the new seam step-by-step.
   - Run tests continuously after each incremental change.
4. **Validate Testability**:
   - Verify that the deepened module can be tested cleanly through its public interface without heavy mocking.
