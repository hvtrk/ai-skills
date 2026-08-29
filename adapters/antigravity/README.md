# Antigravity Memory Adapter & Global Bootstrap

**Concrete Google Antigravity Harness Integration for Memory System v2**  
*Authority: ADR 0002 — Memory System v2*

---

## 1. Supported Integration Mechanism

The **Antigravity Adapter** provides concrete integration for Google Antigravity agent harnesses by translating Antigravity environment parameters and instruction channels into the **Generic Adapter Contract** (`adapters/generic/adapter.py`).

### Key Architectural Boundaries & Characteristics
- **Dependency Direction**: `Antigravity -> Antigravity Adapter -> Generic Contract -> Memory Core -> Local Filesystem`
- **Zero Native Memory Synchronization**: Antigravity-native memory remains platform-owned, supplementary, and non-authoritative. The adapter does not read, write, or mirror native memory stores.
- **Zero Version Control Dependencies**: Works independently of Git branches, commits, or hooks.
- **Strict Delegation**: All filesystem mutations, locking, and validations are performed exclusively by the Memory Core (`scripts/memory.py`).

---

## 2. Global Memory Bootstrap & Discovery Architecture

To ensure Memory System v2 operates **out-of-the-box** for all new projects opened in Antigravity without requiring manual project-level rule files, global discovery is established through synchronized rules:

### Locations & Precedence
- **Source of Truth**: `~/ai-skills/adapters/antigravity/GEMINI.md`
- **Global Installation Targets**:
  - `~/.gemini/config/rules/memory.md`: Global rule directory discovered across all Antigravity workspaces.
  - `~/.gemini/GEMINI.md`: Root global rule file inspected during harness startup.
- **Project-Level Fallbacks**:
  - `<project-root>/GEMINI.md`
  - `<project-root>/AGENTS.md`
  - `<project-root>/.agents/rules.md`
- **Memory Core**: `~/ai-skills/scripts/memory.py` (or system `memory` executable on PATH).

### Installation & Synchronization
Run the central synchronizer:
```bash
# Synchronize Antigravity skills and global rules
./setup.sh --antigravity

# Or synchronize across all harnesses
./setup.sh --global
```
The installation is **fully idempotent** and preserves existing user configuration files.

---

## 3. Four-Layer Memory Architecture

The global instructions communicate four distinct, non-overlapping storage layers:

1. **Native Harness Memory**: Platform-owned and non-authoritative ephemeral state.
2. **User Agent Memory**: `~/.agents/memory/` (`conventions.md` for universal coding standards, `user-profile.md` for developer preferences).
3. **Project Memory**: `<project-root>/.memory/` (`INDEX.md`, topic files `architecture.md`, `domain.md`, `gotchas.md`, `session-handoff.md`, and cold storage `archive/`).
4. **Skills**: `~/ai-skills/` (source of truth), synchronized to `~/.agents/skills/` and `~/.gemini/config/skills/`.

---

## 4. Discovery Rules & Precedence

### A. Project Root Discovery
1. Explicit harness hint passed to `get_project_root(harness_hint)`
2. Explicit `project_root` passed at adapter initialization
3. Environment variables: `ANTIGRAVITY_PROJECT_ROOT`, `ANTIGRAVITY_WORKSPACE_ROOT`, `GEMINI_PROJECT_ROOT`
4. Standard environment variables: `PROJECT_ROOT`, `WORKSPACE_ROOT`
5. Adapter configuration dict `project_root`
6. Fallback: `Path.cwd().resolve()`

### B. Memory Core Discovery
1. Explicit `memory_core_path` passed to adapter
2. Environment variables: `MEMORY_CORE_PATH`, `MEMORY_EXECUTABLE`
3. Executable named `memory` found on system `PATH`
4. Repository relative: `scripts/memory.py`
5. Fallback configuration `memory_core_path`

### C. Global Memory Discovery
- Location: `~/.agents/memory/` (override via `GLOBAL_MEMORY_PATH` or `AGENTS_MEMORY_PATH`)
- Files: `conventions.md` and `user-profile.md`

### D. Project Memory Discovery & New Project Handling
- Location: `<project-root>/.memory/`
- When `<project-root>/.memory/` does NOT exist:
  - The agent detects that project memory is uninitialized.
  - The agent **MUST NOT** silently create `.memory/`.
  - The task continues normally.
  - Project memory is initialized only when explicitly requested or deemed appropriate and communicated.
  - Initialization is performed strictly via `memory init <project-root>` (or `python3 ~/ai-skills/scripts/memory.py init <project-root>`).

### E. Skill Discovery
- Source of truth: `~/ai-skills/` (or `AI_SKILLS_ROOT`)
- Synced location: `~/.agents/skills/` (and `~/.gemini/config/skills`)
- Dynamic discovery: Do not assume a hardcoded count.
- The `project-memory` skill provides the detailed procedural lifecycle guide.

---

## 5. Startup & End-of-Task Lifecycle Protocols

### Startup Retrieval Protocol (Lazy)
1. Determine project root.
2. Read `~/.agents/memory/conventions.md` for universal engineering conventions.
3. Read `~/.agents/memory/user-profile.md` only when specific user preferences are required.
4. Detect if `<project-root>/.memory/` exists.
5. If present, read `.memory/INDEX.md` (<40 lines).
6. Lazily read only the required topic file:
   - `architecture.md`: ADRs, system boundaries, technology choices
   - `domain.md`: Business vocabulary, entities, invariants
   - `gotchas.md`: Traps, workarounds, non-obvious fixes
   - `session-handoff.md`: Resuming incomplete prior work
7. Exclude `.memory/archive/` from normal startup retrieval.

### End-of-Task Protocol
When concluding work:
- **No durable knowledge**: Do nothing.
- **Incomplete work**: Record continuation state via `adapter.handoff(project, input_payload={...})`.
- **Durable architecture knowledge**: Update via `adapter.update(project, topic="architecture", input_payload={...})`.
- **Durable domain knowledge**: Update via `adapter.update(project, topic="domain", input_payload={...})`.
- **Durable bug trap / gotcha**: Update via `adapter.update(project, topic="gotchas", input_payload={...})`.
- **Superseded record**: Move to cold storage via `adapter.archive(project, topic="...", input_payload={...}, superseded_by="...")`.
- **Durable handoff knowledge**: Graduate to durable memory via `adapter.graduate(project, plan_payload={...})`.
- **Generalized procedure**: Propose new reusable skill under `~/ai-skills/`.
- **Always run check**: Execute `adapter.check(project)` after every mutation.

---

## 6. Operation Invocation & Failure Handling

Operations are executed via structured CLI invocations against the Memory Core using `--format json`.

```python
from adapters.antigravity import AntigravityMemoryAdapter

adapter = AntigravityMemoryAdapter()

# Initializing project memory
result = adapter.init(project="/path/to/project")
if not result.success:
    for finding in result.findings:
        print(f"[{finding.severity}] {finding.message}")

# Updating domain memory
result = adapter.update(
    project="/path/to/project",
    topic="domain",
    input_payload={
        "operation": "update",
        "topic": "domain",
        "title": "Core Entities",
        "section": "Ubiquitous Language & Core Entities",
        "content": "- **Workspace**: Top-level root containing user repositories."
    }
)
```

### Failure Propagation
- Non-zero exit codes from the Memory Core are preserved directly in `OperationResult.exit_code`.
- Diagnostic messages and structured `Finding` objects are parsed and returned to the caller.
- The adapter never swallows errors or performs silent rollbacks without reporting them.
- Never directly edit Markdown files as a fallback when Memory Core operations fail.

---

## 7. Limitations & Boundaries
- **No Direct File Editing**: The adapter contains no logic to directly parse or modify Markdown files.
- **No Git Integration**: Versioning and commit management must be handled independently.
- **No Automatic Semantic Classification**: The agent remains responsible for deciding what knowledge to retain and when to graduate it.


