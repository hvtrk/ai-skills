# Codex Memory Adapter

**Concrete Codex & OpenCode Harness Integration for Memory System v2**  
*Authority: ADR 0002 — Memory System v2*

---

## 1. Supported Integration Mechanism

The **Codex Adapter** provides concrete integration for Codex and OpenCode agent harnesses by translating Codex environment parameters and instruction channels into the **Generic Adapter Contract** (`adapters/generic/adapter.py`).

### Key Characteristics
- **Dependency Direction**: `Codex -> Codex Adapter -> Generic Contract -> Memory Core -> Local Filesystem`
- **Zero Native Memory Synchronization**: Codex-native memory remains platform-owned, supplementary, and non-authoritative. The adapter does not read, write, or mirror native memory stores.
- **Zero Version Control Dependencies**: Works independently of Git branches, commits, or hooks.
- **Strict Delegation**: All filesystem mutations, locking, and validations are performed exclusively by the Memory Core (`scripts/memory.py`).

---

## 2. Installation & Configuration

### Python Package Usage
```python
from adapters.codex import CodexMemoryAdapter

# Initialize adapter (auto-discovers environment)
adapter = CodexMemoryAdapter()

# Check capabilities
caps = adapter.get_capabilities(project_root="/path/to/project")
print(caps.memory_core)       # CapabilityStatus.AVAILABLE
print(caps.project_memory)    # CapabilityStatus.AVAILABLE | NOT_INITIALIZED | PARTIAL
```

### Instruction Setup
Codex agents discover operating instructions via `AGENTS.md`:
- Symlink or include `adapters/codex/AGENTS.md` in the user's Codex instruction search path (e.g., repository root or `~/.codex/AGENTS.md`).

---

## 3. Discovery Rules & Resolution Precedence

### A. Project Root Discovery
1. Explicit harness hint passed to `get_project_root(harness_hint)`
2. Explicit `project_root` passed at adapter initialization
3. Environment variables: `CODEX_PROJECT_ROOT`, `CODEX_WORKSPACE_ROOT`, `OPENCODE_PROJECT_ROOT`
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
- Files: `conventions.md` (universal engineering standards) and `user-profile.md` (user preferences)

### D. Project Memory Discovery
- Location: `<project-root>/.memory/`
- Files: `INDEX.md`, `architecture.md`, `domain.md`, `gotchas.md`, `session-handoff.md`, and `archive/` directory.
- Uninitialized projects report `CapabilityStatus.NOT_INITIALIZED` without error.

### E. Skill Discovery
- Source of truth: `~/ai-skills/` (or `AI_SKILLS_ROOT`)
- Synced location: `~/.agents/skills/` (or `AGENTS_SKILLS_PATH`)
- Reusable workflows and procedures are shared seamlessly across all harnesses.

---

## 4. Startup & End-of-Task Lifecycle Protocols

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
- **Generalized procedure**: Propose new reusable skill in `~/ai-skills/`.
- **Always run check**: Execute `adapter.check(project)` after every mutation.

---

## 5. Operation Invocation & Failure Handling

Operations are executed via structured CLI invocations against the Memory Core using `--format json`.

```python
# Initializing project memory
result = adapter.init(project="/path/to/project")
if not result.success:
    for finding in result.findings:
        print(f"[{finding.severity}] {finding.message}")

# Updating architectural memory
result = adapter.update(
    project="/path/to/project",
    topic="architecture",
    input_payload={
        "operation": "update",
        "topic": "architecture",
        "title": "ADR-0005 Auth Service",
        "section": "Key Architectural Decisions",
        "content": "- **[ADR-0005]**: Use JWT tokens with asymmetric signing."
    }
)
```

### Failure Propagation
- Non-zero exit codes from the Memory Core are preserved directly in `OperationResult.exit_code`.
- Diagnostic messages and structured `Finding` objects are parsed and returned to the caller.
- The adapter never swallows errors or performs silent rollbacks without reporting them.

---

## 6. Limitations & Boundaries
- **No Direct File Editing**: The adapter contains no logic to directly parse or modify Markdown files.
- **No Git Integration**: Versioning and commit management must be handled independently.
- **No Automatic Semantic Classification**: The agent remains responsible for deciding what knowledge to retain and when to graduate it.

