# Generic Harness Integration Contract

**Specification & Contract Guide for Filesystem-Capable Agent Harnesses**  
*Authority: ADR 0002 — Memory System v2*

---

## 1. Purpose

The **Generic Harness Adapter** defines the contract and reference implementation for connecting any AI agent harness (e.g., Codex, Antigravity, Claude Code, Cursor, Gemini CLI, Windsurf, custom agents) to **Memory System v2**.

All agent harnesses share the exact same:
- Memory storage directory structures (`~/.agents/memory/` and `<project-root>/.memory/`)
- Plain Markdown format with structured YAML frontmatter
- Two-tier lazy retrieval lifecycle
- Validation rules and invariants
- Deterministic operation semantics
- Skill architecture

The adapter is a thin translation layer: it translates harness environment context into the generic Memory System contract and delegates all filesystem mutations, locking, and validation to the **Memory Core** (`scripts/memory.py`).

---

## 2. Dependency Direction

The architecture enforces a strict unidirectional dependency graph:

```text
┌────────────────────────────────────────────────────────┐
│             Harness (Codex / Antigravity / Claude)     │
└──────────────────────────┬─────────────────────────────┘
                           │ (environment & lifecycle events)
                           ▼
┌────────────────────────────────────────────────────────┐
│             Generic Memory Adapter Contract            │
└──────────────────────────┬─────────────────────────────┘
                           │ (CLI invocation --format json)
                           ▼
┌────────────────────────────────────────────────────────┐
│             Memory Core (scripts/memory.py)            │
└──────────────────────────┬─────────────────────────────┘
                           │ (atomic writes, locks, validation)
                           ▼
┌────────────────────────────────────────────────────────┐
│             Local Filesystem                           │
└────────────────────────────────────────────────────────┘
```

**Prohibited Dependencies:**
- Memory Core MUST NOT import, detect, or depend on any agent harness.
- Memory Core and Generic Adapter MUST NOT depend on Git, version control, or network services.

---

## 3. Adapter Responsibilities vs. Non-Responsibilities

### Responsibilities
1. **Project Root Discovery**: Determine the target project root deterministically without Git.
2. **Memory Subsystem Discovery**: Locate global user memory (`~/.agents/memory/`) and project memory (`<project-root>/.memory/`).
3. **Skill Discovery**: Locate the skills source of truth (`~/ai-skills/`) and synced distribution path (`~/.agents/skills/`).
4. **Memory Core Discovery**: Locate the `memory` executable or `scripts/memory.py`.
5. **Capability Inspection**: Report whether each subsystem is `AVAILABLE`, `UNAVAILABLE`, `NOT_INITIALIZED`, or `PARTIAL`.
6. **Instruction Delivery**: Provide standard startup and end-of-task lifecycle protocols to the agent.
7. **Operation Invocation**: Execute Memory Core operations (`init`, `check`, `retrieve`, `update`, `handoff`, `graduate`, `archive`) using `--format json`.
8. **Failure Propagation**: Transparently surface exit codes, error messages, and validation findings to the calling agent.

### Non-Responsibilities (Forbidden)
- **NO Direct Memory Mutation**: The adapter never writes or edits Markdown memory files directly.
- **NO Bypassing Validation**: Never bypass `memory check` or ignore non-zero exit codes.
- **NO Silent Retries**: Never silently swallow errors or retry destructive operations.
- **NO Automatic Initialization**: Missing project memory is reported as `NOT_INITIALIZED`, not created automatically without explicit agent/user request.
- **NO Version Control**: Never run Git commands, check branches, create commits, or manage git hooks.
- **NO Native Harness Coupling**: Never read/write platform-specific native memory stores.

---

## 4. Discovery Rules & Deterministic Resolution Orders

### A. Project Root Discovery
Project root discovery does **not** rely on Git:
1. **Explicit Parameter**: Harness-provided workspace root hint.
2. **Adapter Instantiation Parameter**: `project_root` provided at adapter initialization.
3. **Environment Variables**: `PROJECT_ROOT` or `WORKSPACE_ROOT`.
4. **Adapter Configuration**: Config dict `project_root`.
5. **Fallback**: Current working directory (`Path.cwd()`).

### B. Memory Core Discovery
1. **Explicit Parameter**: Path provided at adapter initialization.
2. **Environment Variables**: `MEMORY_CORE_PATH` or `MEMORY_EXECUTABLE`.
3. **System PATH**: Binary named `memory` found via system search (`PATH`).
4. **Repository Relative**: `scripts/memory.py` relative to skill root, adapter package, or cwd.
5. **Configuration Fallback**: Config dict `memory_core_path`.

### C. Global Memory Discovery
- Location: `~/.agents/memory/` (or `GLOBAL_MEMORY_PATH` / `AGENTS_MEMORY_PATH`).
- Standard files:
  - `conventions.md`: Universal coding ethos, styling, and engineering guidelines (always read on startup).
  - `user-profile.md`: Developer profile, OS, and tool preferences (read on-demand).

### D. Project Memory Discovery
- Location: `<project-root>/.memory/`
- Standard structure:
  ```text
  .memory/
  ├── INDEX.md              # Compact Level-0 routing index (<40 lines)
  ├── architecture.md       # Stack, boundaries, decisions, invariants
  ├── domain.md             # Core entities, ubiquitous vocabulary, relationships
  ├── gotchas.md            # Traps, non-obvious quirks, resolved blockers
  ├── session-handoff.md    # Ephemeral active workstream state
  └── archive/              # Superseded historical records (cold storage)
  ```
- If `.memory/` does not exist, status is `NOT_INITIALIZED`. It is not created automatically.

### E. Skill Discovery
- **Source of Truth**: `~/ai-skills/` (or `AI_SKILLS_ROOT` / `SKILLS_SOURCE_ROOT`).
- **Synced Distribution**: `~/.agents/skills/` (or `AGENTS_SKILLS_PATH`).
- Skills contain reusable procedures and workflows, never project-specific facts.

---

## 5. Capability Detection

The adapter inspects the environment and reports capability states:

```python
from adapters.generic import GenericMemoryAdapter, CapabilityStatus

adapter = GenericMemoryAdapter()
capabilities = adapter.get_capabilities(project_root="/path/to/project")

print(capabilities.memory_core)       # CapabilityStatus.AVAILABLE
print(capabilities.project_memory)    # CapabilityStatus.AVAILABLE | NOT_INITIALIZED | PARTIAL
print(capabilities.available_operations) # ['init', 'check', 'retrieve', 'update', 'handoff', 'graduate', 'archive']
```

| Subsystem | State | Meaning |
| :--- | :--- | :--- |
| `memory_core` | `AVAILABLE` | Core executable is discovered and operational. |
| `memory_core` | `UNAVAILABLE` | Memory Core could not be found. Operations are disabled. |
| `global_memory` | `AVAILABLE` | Global directory exists with standard markdown files. |
| `global_memory` | `UNAVAILABLE` | Global directory does not exist. |
| `project_memory` | `AVAILABLE` | All 5 standard files and `archive/` exist. |
| `project_memory` | `NOT_INITIALIZED` | Project has no `.memory/` directory (valid normal state). |
| `project_memory` | `PARTIAL` | Directory exists but required files are missing (requires `--repair`). |
| `skills` | `AVAILABLE` | Skill repository is accessible. |

---

## 6. Startup Retrieval Protocol (Lazy Retrieval)

To minimize context window consumption, agents follow **Hierarchical Lazy Retrieval**:

```text
1. Identify project root.
2. Read ~/.agents/memory/conventions.md (universal guidelines).
3. Read ~/.agents/memory/user-profile.md (ONLY if user preferences are relevant).
4. Check if <project-root>/.memory/ exists.
   ├── If NO: proceed with normal work without project memory.
   └── If YES:
       5. Read .memory/INDEX.md (<40 lines routing index).
       6. Identify which durable topic is relevant to the immediate task.
       7. Lazily read ONLY that topic file:
          - architecture.md: for tech stack, system structure, ADRs.
          - domain.md: for entities, business vocabulary, invariants.
          - gotchas.md: for bug hunting, non-obvious traps, quirks.
          - session-handoff.md: when resuming prior interrupted work.
8. NEVER load .memory/archive/ during startup.
```

---

## 7. End-of-Task Protocol

When completing a task, the agent evaluates the knowledge gained:

| Scenario | Action | Tooling Operation |
| :--- | :--- | :--- |
| **Case A**: Nothing durable learned | Do nothing | None |
| **Case B**: Work is incomplete | Write active workstream state | `memory handoff` |
| **Case C**: Durable architectural decision | Record tech stack or ADR decision | `memory update --topic architecture` |
| **Case D**: Durable domain concept | Record entity or business invariant | `memory update --topic domain` |
| **Case E**: Durable bug trap / gotcha | Record non-obvious quirk / blocker fix | `memory update --topic gotchas` |
| **Case F**: Existing record superseded | Archive obsolete note with reason | `memory archive --topic <topic> --superseded-by <id>` |
| **Case G**: Reusable procedure discovered | Deliberately generalize procedure into skill | Add / update skill in `~/ai-skills/` |

**Post-Mutation Rule**: Always run `memory check` after any write operation to verify memory invariants.

---

## 8. Operation Invocation Contract

Operations are executed via structured subprocess calls to the Memory Core using `--format json`.

### Supported Operations
- `adapter.init(project, repair=False, dry_run=False)`
- `adapter.check(project, stale_days=7.0)`
- `adapter.retrieve(project, profile=False, topics=['architecture'])`
- `adapter.update(project, topic='architecture', input_payload={...})`
- `adapter.handoff(project, input_payload={...})`
- `adapter.graduate(project, plan_payload={...})`
- `adapter.archive(project, topic='gotchas', input_payload={...}, superseded_by='...')`

### Structured Return Value (`OperationResult`)
Every operation returns a typed `OperationResult`:

```json
{
  "operation": "update",
  "success": true,
  "exit_code": 0,
  "project": "/path/to/project",
  "messages": ["UPDATED: architecture.md (section: Key Architectural Decisions)"],
  "findings": [],
  "data": {
    "operation": "update",
    "topic": "architecture",
    "status": "success"
  },
  "raw_output": "{\n  \"operation\": \"update\", ...\n}"
}
```

---

## 9. Failure Propagation Behavior

Failures in Memory Core (validation errors, corrupted structures, lock timeouts, missing files) are never swallowed:
1. `exit_code != 0` is preserved.
2. `success` is set to `False`.
3. Validation findings (with `severity: ERROR`, `line`, `message`, `suggested_action`) are parsed into `Finding` objects.
4. The caller agent can inspect `result.findings` and take corrective action or notify the user.

---

## 10. Harness Independence Guarantees

The generic integration layer is verified to be completely independent:
- Zero dependencies outside Python standard library (`pathlib`, `json`, `subprocess`, `dataclasses`, `os`, `shutil`, `tempfile`, `enum`).
- No Git CLI invocations or `.git` repository parsing.
- No network connections or remote services.
- Tested entirely within isolated temporary directories.

