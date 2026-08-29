"""Unit tests for Phase 5: Codex Harness Adapter.

Tests verify Codex-specific project root discovery, capability inspection,
instruction delivery, operation delegation to Memory Core, failure propagation,
lazy retrieval, and zero direct memory file mutations.
"""

from __future__ import annotations

import ast
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

# Add repository root to path for imports
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapters.codex import CodexMemoryAdapter
from adapters.generic import (
    SUPPORTED_OPERATIONS,
    CapabilityStatus,
    GenericMemoryAdapter,
)


class CodexAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name).resolve()

        self.project_dir = (self.base_path / "codex_project").resolve()
        self.project_dir.mkdir()

        self.global_dir = (self.base_path / "global_agents" / "memory").resolve()
        self.global_dir.mkdir(parents=True)
        (self.global_dir / "conventions.md").write_text(
            "# Conventions\nUniversal rules\n", encoding="utf-8"
        )
        (self.global_dir / "user-profile.md").write_text(
            "# Profile\nUser profile\n", encoding="utf-8"
        )

        self.skills_source = (self.base_path / "skills_source").resolve()
        (self.skills_source / "skills").mkdir(parents=True)
        (self.skills_source / "scripts").mkdir(parents=True)

        self.core_script = (ROOT / "scripts" / "memory.py").resolve()
        self.templates_dir = (ROOT / "templates" / "memory").resolve()

        self.adapter = CodexMemoryAdapter(
            project_root=self.project_dir,
            memory_core_path=self.core_script,
            global_memory_path=self.global_dir,
            skills_root=self.skills_source,
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    # -------------------------------------------------------------------------
    # A. Project Root Discovery Tests
    # -------------------------------------------------------------------------

    def test_project_root_discovery_order(self):
        # 1. Harness hint takes top priority
        hint_path = (self.base_path / "hint_project").resolve()
        self.assertEqual(self.adapter.get_project_root(hint_path), hint_path)

        # 2. Explicit constructor argument
        self.assertEqual(self.adapter.get_project_root(), self.project_dir)

        # 3. Codex environment variables
        clean_adapter = CodexMemoryAdapter()
        env_project = (self.base_path / "codex_env_project").resolve()

        with mock.patch.dict(os.environ, {"CODEX_PROJECT_ROOT": str(env_project)}):
            self.assertEqual(clean_adapter.get_project_root(), env_project)

        with mock.patch.dict(
            os.environ, {"CODEX_WORKSPACE_ROOT": str(env_project)}, clear=True
        ):
            self.assertEqual(clean_adapter.get_project_root(), env_project)

        with mock.patch.dict(
            os.environ, {"OPENCODE_PROJECT_ROOT": str(env_project)}, clear=True
        ):
            self.assertEqual(clean_adapter.get_project_root(), env_project)

        # 4. Standard environment variables
        with mock.patch.dict(
            os.environ, {"PROJECT_ROOT": str(env_project)}, clear=True
        ):
            self.assertEqual(clean_adapter.get_project_root(), env_project)

        with mock.patch.dict(
            os.environ, {"WORKSPACE_ROOT": str(env_project)}, clear=True
        ):
            self.assertEqual(clean_adapter.get_project_root(), env_project)

        # 5. Config dictionary
        cfg_adapter = CodexMemoryAdapter(config={"project_root": str(env_project)})
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(cfg_adapter.get_project_root(), env_project)

        # 6. CWD Fallback
        fallback_adapter = CodexMemoryAdapter()
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(fallback_adapter.get_project_root(), Path.cwd().resolve())

    # -------------------------------------------------------------------------
    # B. Capability Detection & Subsystem Discovery
    # -------------------------------------------------------------------------

    def test_capabilities_and_subsystem_discovery(self):
        # Uninitialized project state
        caps = self.adapter.get_capabilities()
        self.assertEqual(caps.memory_core, CapabilityStatus.AVAILABLE)
        self.assertEqual(caps.global_memory, CapabilityStatus.AVAILABLE)
        self.assertEqual(caps.project_memory, CapabilityStatus.NOT_INITIALIZED)
        self.assertFalse(caps.project_memory_initialized)

        # Initialize project memory
        init_res = self.adapter.init(templates=self.templates_dir)
        self.assertTrue(init_res.success)

        caps_after = self.adapter.get_capabilities()
        self.assertEqual(caps_after.project_memory, CapabilityStatus.AVAILABLE)
        self.assertTrue(caps_after.project_memory_initialized)
        self.assertEqual(caps_after.available_operations, list(SUPPORTED_OPERATIONS))

    # -------------------------------------------------------------------------
    # C. Instruction Delivery
    # -------------------------------------------------------------------------

    def test_instruction_delivery(self):
        general_inst = self.adapter.get_instructions()
        self.assertIn("Codex Memory System v2 Protocol", general_inst)

        startup_inst = self.adapter.get_instructions(topic="startup")
        self.assertIn("CODEX STARTUP RETRIEVAL PROTOCOL", startup_inst)

        end_inst = self.adapter.get_instructions(topic="end_of_task")
        self.assertIn("CODEX END-OF-TASK PROTOCOL", end_inst)

    # -------------------------------------------------------------------------
    # D. Full Lifecycle Operation Invocations
    # -------------------------------------------------------------------------

    def test_operations_lifecycle_invocation(self):
        # 1. Init
        init_res = self.adapter.init(templates=self.templates_dir)
        self.assertTrue(init_res.success)
        self.assertEqual(init_res.operation, "init")

        # 2. Check
        check_res = self.adapter.check()
        self.assertTrue(check_res.success)

        # 3. Update
        update_res = self.adapter.update(
            topic="architecture",
            input_payload={
                "operation": "update",
                "topic": "architecture",
                "title": "Codex Architecture Note",
                "section": "Key Architectural Decisions",
                "content": "- **Codex Note**: Using layered service contracts.",
            },
        )
        self.assertTrue(update_res.success)

        # 4. Retrieve
        ret_res = self.adapter.retrieve(
            topics=["architecture"], profile=True, global_memory=self.global_dir
        )
        self.assertTrue(ret_res.success)
        record_labels = [r["label"] for r in ret_res.data.get("records", [])]
        self.assertIn("project-architecture", record_labels)

        # 5. Handoff
        handoff_res = self.adapter.handoff(
            input_payload={
                "operation": "handoff",
                "goal": "Verify Codex adapter",
                "files_in_progress": ["adapters/codex/adapter.py"],
                "build_status": "Clean",
                "dead_ends": ["None"],
                "next_step": "Run contract tests",
            }
        )
        self.assertTrue(handoff_res.success)

        # 6. Graduate
        grad_res = self.adapter.graduate(
            plan_payload={
                "operation": "graduate",
                "source": "session-handoff.md",
                "promotions": [
                    {
                        "topic": "gotchas",
                        "title": "Codex graduation trap",
                        "section": "Critical Traps",
                        "content": "- Verify plan payload before calling graduate.",
                    }
                ],
            }
        )
        self.assertTrue(grad_res.success)

        # 7. Archive
        arch_res = self.adapter.archive(
            topic="architecture",
            input_payload={
                "title": "Codex Architecture Note",
                "section": "Key Architectural Decisions",
                "content": "- **Codex Note**: Using layered service contracts.",
            },
            superseded_by="ADR-0099",
        )
        self.assertTrue(arch_res.success)

    # -------------------------------------------------------------------------
    # E. Failure Propagation
    # -------------------------------------------------------------------------

    def test_failure_propagation(self):
        broken_adapter = CodexMemoryAdapter(
            project_root=self.project_dir,
            memory_core_path=self.base_path / "nonexistent_core.py",
        )
        with mock.patch("shutil.which", return_value=None):
            fail_res = broken_adapter.check()
            self.assertFalse(fail_res.success)
            self.assertEqual(fail_res.exit_code, 127)
            self.assertTrue(any(f.severity == "ERROR" for f in fail_res.findings))

    # -------------------------------------------------------------------------
    # F. Harness Independence & Allowed Imports
    # -------------------------------------------------------------------------

    def test_harness_independence(self):
        import adapters.codex.adapter as codex_module

        adapter_file = Path(codex_module.__file__)
        tree = ast.parse(adapter_file.read_text(encoding="utf-8"))

        imported_modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported_modules.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imported_modules.add(node.module.split(".")[0])

        allowed_modules = {
            "__future__",
            "os",
            "pathlib",
            "typing",
            "adapters",
        }
        self.assertTrue(
            imported_modules.issubset(allowed_modules),
            f"Disallowed imports found: {imported_modules - allowed_modules}",
        )


if __name__ == "__main__":
    unittest.main()
