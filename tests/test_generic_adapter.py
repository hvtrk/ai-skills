"""Unit tests for Phase 4: Generic Harness Integration Contract.

Tests verify project root discovery, memory core discovery, global/project memory discovery,
skill discovery, capability detection, operation invocation, failure propagation, lazy retrieval,
archive exclusion, harness independence, and zero direct memory file mutation by the adapter.
"""

from __future__ import annotations

import ast
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

# Add repository root to path for imports
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapters.generic import (
    REQUIRED_PROJECT_MEMORY_FILES,
    SUPPORTED_OPERATIONS,
    CapabilityReport,
    CapabilityStatus,
    Finding,
    GenericMemoryAdapter,
    OperationResult,
)


class GenericAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name).resolve()

        self.project_dir = (self.base_path / "test_project").resolve()
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

        self.adapter = GenericMemoryAdapter(
            project_root=self.project_dir,
            memory_core_path=self.core_script,
            global_memory_path=self.global_dir,
            skills_root=self.skills_source,
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    # -------------------------------------------------------------------------
    # A. Project Root Discovery Tests (Non-Git)
    # -------------------------------------------------------------------------

    def test_project_root_discovery_order(self):
        # 1. Harness hint takes top priority
        hint_path = (self.base_path / "hint_project").resolve()
        self.assertEqual(self.adapter.get_project_root(hint_path), hint_path)

        # 2. Explicit constructor argument
        self.assertEqual(self.adapter.get_project_root(), self.project_dir)

        # 3. Environment variables PROJECT_ROOT / WORKSPACE_ROOT
        clean_adapter = GenericMemoryAdapter()
        env_project = (self.base_path / "env_project").resolve()
        with mock.patch.dict(os.environ, {"PROJECT_ROOT": str(env_project)}):
            self.assertEqual(clean_adapter.get_project_root(), env_project)

        with mock.patch.dict(
            os.environ, {"WORKSPACE_ROOT": str(env_project)}, clear=True
        ):
            self.assertEqual(clean_adapter.get_project_root(), env_project)

        # 4. Config dictionary
        cfg_adapter = GenericMemoryAdapter(config={"project_root": str(env_project)})
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(cfg_adapter.get_project_root(), env_project)

        # 5. CWD Fallback
        fallback_adapter = GenericMemoryAdapter()
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(fallback_adapter.get_project_root(), Path.cwd().resolve())

    # -------------------------------------------------------------------------
    # B. Memory Core Discovery Tests
    # -------------------------------------------------------------------------

    def test_memory_core_discovery_order(self):
        # 1. Explicit path passed to constructor
        self.assertEqual(self.adapter.get_memory_core(), self.core_script)

        # 2. Environment variable MEMORY_CORE_PATH / MEMORY_EXECUTABLE
        custom_core = (self.base_path / "custom_memory.py").resolve()
        custom_core.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
        with mock.patch.dict(os.environ, {"MEMORY_CORE_PATH": str(custom_core)}):
            adapter_env = GenericMemoryAdapter()
            self.assertEqual(adapter_env.get_memory_core(), custom_core)

        # 3. Executable named 'memory' on PATH
        with mock.patch("shutil.which", return_value=str(custom_core)):
            adapter_path = GenericMemoryAdapter()
            self.assertEqual(adapter_path.get_memory_core(), custom_core)

        # 4. Missing core returns None
        with (
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch("shutil.which", return_value=None),
        ):
            empty_adapter = GenericMemoryAdapter(
                memory_core_path=self.base_path / "nonexistent.py"
            )
            self.assertIsNone(empty_adapter.get_memory_core())

    # -------------------------------------------------------------------------
    # C. Global Memory Discovery Tests
    # -------------------------------------------------------------------------

    def test_global_memory_discovery(self):
        self.assertEqual(self.adapter.get_global_memory(), self.global_dir)

        # Environment variable override
        custom_global = (self.base_path / "override_global").resolve()
        with mock.patch.dict(os.environ, {"GLOBAL_MEMORY_PATH": str(custom_global)}):
            ad = GenericMemoryAdapter()
            self.assertEqual(ad.get_global_memory(), custom_global)

    # -------------------------------------------------------------------------
    # D & G. Project Memory Discovery & Missing/Partial Project Memory
    # -------------------------------------------------------------------------

    def test_project_memory_discovery_and_uninitialized_state(self):
        proj_mem = self.adapter.get_project_memory()
        self.assertEqual(proj_mem, self.project_dir / ".memory")

        # Before initialization: project memory is uninitialized (not fatal error)
        caps = self.adapter.get_capabilities()
        self.assertEqual(caps.project_memory, CapabilityStatus.NOT_INITIALIZED)
        self.assertFalse(caps.project_memory_initialized)
        self.assertIsNone(caps.project_memory_path)

        # Initialize project memory using adapter
        init_res = self.adapter.init(templates=self.templates_dir)
        self.assertTrue(init_res.success)
        self.assertEqual(init_res.exit_code, 0)

        # After initialization: project memory is AVAILABLE
        caps_after = self.adapter.get_capabilities()
        self.assertEqual(caps_after.project_memory, CapabilityStatus.AVAILABLE)
        self.assertTrue(caps_after.project_memory_initialized)
        self.assertEqual(caps_after.project_memory_path, proj_mem)

        # Partial/corrupted state: delete one required file
        (proj_mem / "gotchas.md").unlink()
        caps_partial = self.adapter.get_capabilities()
        self.assertEqual(caps_partial.project_memory, CapabilityStatus.PARTIAL)
        self.assertFalse(caps_partial.project_memory_initialized)

    # -------------------------------------------------------------------------
    # E & I. Skill Discovery & Missing Skills
    # -------------------------------------------------------------------------

    def test_skill_discovery(self):
        src, synced = self.adapter.get_skill_root()
        self.assertEqual(src, self.skills_source)

        # When skills directory is missing
        empty_adapter = GenericMemoryAdapter(skills_root=self.base_path / "no_skills")
        with mock.patch.dict(os.environ, {}, clear=True):
            src_none, _ = empty_adapter.get_skill_root()
            self.assertEqual(src_none, (self.base_path / "no_skills").resolve())

    # -------------------------------------------------------------------------
    # F, H, J. Capability Detection Matrix
    # -------------------------------------------------------------------------

    def test_capability_detection_matrix(self):
        # 1. Fully available environment
        init_res = self.adapter.init(templates=self.templates_dir)
        self.assertTrue(init_res.success)
        caps = self.adapter.get_capabilities()
        self.assertEqual(caps.memory_core, CapabilityStatus.AVAILABLE)
        self.assertEqual(caps.global_memory, CapabilityStatus.AVAILABLE)
        self.assertEqual(caps.project_memory, CapabilityStatus.AVAILABLE)
        self.assertTrue(caps.conventions_available)
        self.assertTrue(caps.user_profile_available)
        self.assertEqual(caps.available_operations, list(SUPPORTED_OPERATIONS))

        # 2. Missing global memory
        empty_global_adapter = GenericMemoryAdapter(
            project_root=self.project_dir,
            memory_core_path=self.core_script,
            global_memory_path=self.base_path / "nonexistent_global",
            skills_root=self.skills_source,
        )
        caps_no_global = empty_global_adapter.get_capabilities()
        self.assertEqual(caps_no_global.global_memory, CapabilityStatus.UNAVAILABLE)
        self.assertFalse(caps_no_global.conventions_available)

        # 3. Missing memory core
        no_core_adapter = GenericMemoryAdapter(
            project_root=self.project_dir,
            memory_core_path=self.base_path / "nonexistent_core.py",
            global_memory_path=self.global_dir,
            skills_root=self.skills_source,
        )
        with mock.patch("shutil.which", return_value=None):
            caps_no_core = no_core_adapter.get_capabilities()
            self.assertEqual(caps_no_core.memory_core, CapabilityStatus.UNAVAILABLE)
            self.assertEqual(caps_no_core.available_operations, [])

    # -------------------------------------------------------------------------
    # K, L. Operation Invocation & Structured JSON Output
    # -------------------------------------------------------------------------

    def test_operations_lifecycle_invocation(self):
        # 1. Init
        init_res = self.adapter.init(templates=self.templates_dir)
        self.assertTrue(init_res.success)
        self.assertEqual(init_res.operation, "init")
        self.assertEqual(init_res.exit_code, 0)
        self.assertIn("data", init_res.to_dict())

        # 2. Check
        check_res = self.adapter.check()
        self.assertTrue(check_res.success)
        self.assertEqual(check_res.exit_code, 0)
        self.assertTrue(any(f.severity == "OK" for f in check_res.findings))

        # 3. Retrieve
        ret_res = self.adapter.retrieve(
            topics=["architecture"], profile=True, global_memory=self.global_dir
        )
        self.assertTrue(ret_res.success)
        self.assertEqual(ret_res.operation, "retrieve")
        record_labels = [r["label"] for r in ret_res.data.get("records", [])]
        self.assertIn("project-architecture", record_labels)
        self.assertIn("global-conventions", record_labels)
        self.assertIn("global-user-profile", record_labels)

        # 4. Update
        update_payload = {
            "operation": "update",
            "topic": "architecture",
            "title": "ADR-0010 Generic Contract",
            "section": "Key Architectural Decisions",
            "content": "- **ADR-0010**: All harnesses must use generic contract.",
        }
        update_res = self.adapter.update(input_payload=update_payload)
        self.assertTrue(update_res.success)
        self.assertEqual(update_res.exit_code, 0)

        # 5. Handoff
        handoff_payload = {
            "operation": "handoff",
            "goal": "Verify generic adapter contract",
            "files_in_progress": ["adapters/generic/adapter.py"],
            "build_status": "All tests green",
            "dead_ends": ["None"],
            "next_step": "Complete Phase 4 report",
        }
        handoff_res = self.adapter.handoff(input_payload=handoff_payload)
        self.assertTrue(handoff_res.success)
        self.assertEqual(handoff_res.exit_code, 0)

        # 6. Graduate
        grad_plan = {
            "operation": "graduate",
            "source": "session-handoff.md",
            "promotions": [
                {
                    "topic": "gotchas",
                    "title": "Subprocess JSON output",
                    "section": "Critical Traps",
                    "content": "- Always pass --format json when calling core CLI.",
                }
            ],
        }
        grad_res = self.adapter.graduate(plan_payload=grad_plan)
        self.assertTrue(grad_res.success)
        self.assertEqual(grad_res.exit_code, 0)

        # 7. Archive
        archive_payload = {
            "title": "ADR-0010 Generic Contract",
            "section": "Key Architectural Decisions",
            "content": "- **ADR-0010**: All harnesses must use generic contract.",
        }
        arch_res = self.adapter.archive(
            topic="architecture",
            input_payload=archive_payload,
            superseded_by="ADR-0011",
        )
        self.assertTrue(arch_res.success)
        self.assertEqual(arch_res.exit_code, 0)

    # -------------------------------------------------------------------------
    # M. Failure Propagation
    # -------------------------------------------------------------------------

    def test_failure_propagation_on_invalid_operation(self):
        # 1. Invocation without core executable returns error code 127
        broken_adapter = GenericMemoryAdapter(
            project_root=self.project_dir,
            memory_core_path=self.base_path / "nonexistent_core.py",
        )
        with mock.patch("shutil.which", return_value=None):
            fail_res = broken_adapter.check()
            self.assertFalse(fail_res.success)
            self.assertEqual(fail_res.exit_code, 127)
            self.assertTrue(any(f.severity == "ERROR" for f in fail_res.findings))

        # 2. Check on uninitialized project returns non-zero exit code
        empty_proj = (self.base_path / "empty_proj").resolve()
        empty_proj.mkdir()
        uninit_adapter = GenericMemoryAdapter(
            project_root=empty_proj,
            memory_core_path=self.core_script,
        )
        uninit_check = uninit_adapter.check()
        self.assertFalse(uninit_check.success)
        self.assertNotEqual(uninit_check.exit_code, 0)
        self.assertTrue(any(f.severity == "ERROR" for f in uninit_check.findings))

        # 3. Invalid payload (missing required field in handoff)
        self.adapter.init(templates=self.templates_dir)
        invalid_handoff = {"operation": "handoff", "goal": "Missing next step"}
        bad_handoff_res = self.adapter.handoff(input_payload=invalid_handoff)
        self.assertFalse(bad_handoff_res.success)
        self.assertNotEqual(bad_handoff_res.exit_code, 0)

    # -------------------------------------------------------------------------
    # N. No Direct Memory Mutation by Adapter
    # -------------------------------------------------------------------------

    def test_no_direct_memory_mutation_by_adapter(self):
        # Mock run_memory_operation to ensure adapter helper methods do not touch files
        test_adapter = GenericMemoryAdapter(
            project_root=self.project_dir,
            memory_core_path=self.core_script,
        )

        with mock.patch.object(test_adapter, "run_memory_operation") as mock_op:
            mock_op.return_value = OperationResult(
                operation="update",
                success=True,
                exit_code=0,
                project=str(self.project_dir),
            )
            test_adapter.update(
                topic="gotchas",
                input_payload={"title": "Test", "content": "Sample"},
            )
            mock_op.assert_called_once()
            # Verify no .memory directory was directly created by python code in adapter
            self.assertFalse((self.project_dir / ".memory").exists())

    # -------------------------------------------------------------------------
    # O. Harness Independence
    # -------------------------------------------------------------------------

    def test_harness_independence(self):
        import adapters.generic.adapter as ga_module

        adapter_file = Path(ga_module.__file__)
        tree = ast.parse(adapter_file.read_text(encoding="utf-8"))

        imported_modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported_modules.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imported_modules.add(node.module.split(".")[0])

        allowed_stdlib = {
            "__future__",
            "json",
            "os",
            "shutil",
            "subprocess",
            "sys",
            "tempfile",
            "dataclasses",
            "enum",
            "pathlib",
            "typing",
        }
        self.assertTrue(
            imported_modules.issubset(allowed_stdlib),
            f"Disallowed imports found: {imported_modules - allowed_stdlib}",
        )

    # -------------------------------------------------------------------------
    # P & Q. Lazy Retrieval Protocol & Archive Exclusion
    # -------------------------------------------------------------------------

    def test_startup_retrieval_protocol_and_archive_exclusion(self):
        self.adapter.init(templates=self.templates_dir)

        # Plan with no topic selection: reads conventions and INDEX.md only
        plan_default = self.adapter.get_startup_retrieval_plan()
        self.assertTrue(plan_default["archive_excluded"])
        self.assertIn(
            str(self.global_dir / "conventions.md"), plan_default["files_to_read"]
        )
        self.assertIn(
            str(self.project_dir / ".memory" / "INDEX.md"),
            plan_default["files_to_read"],
        )
        self.assertNotIn(
            str(self.project_dir / ".memory" / "architecture.md"),
            plan_default["files_to_read"],
        )
        self.assertNotIn(
            str(self.global_dir / "user-profile.md"), plan_default["files_to_read"]
        )

        # Plan with profile and architecture topic
        plan_arch = self.adapter.get_startup_retrieval_plan(
            profile=True, topics=["architecture"]
        )
        self.assertIn(
            str(self.global_dir / "user-profile.md"), plan_arch["files_to_read"]
        )
        self.assertIn(
            str(self.project_dir / ".memory" / "architecture.md"),
            plan_arch["files_to_read"],
        )
        self.assertNotIn(
            str(self.project_dir / ".memory" / "domain.md"), plan_arch["files_to_read"]
        )
        self.assertNotIn(
            str(self.project_dir / ".memory" / "archive"), plan_arch["files_to_read"]
        )

    def test_instruction_delivery(self):
        general_inst = self.adapter.get_instructions()
        self.assertIn("Memory System v2", general_inst)
        startup_inst = self.adapter.get_instructions(topic="startup")
        self.assertIn("STARTUP RETRIEVAL PROTOCOL", startup_inst)
        end_inst = self.adapter.get_instructions(topic="end_of_task")
        self.assertIn("END-OF-TASK PROTOCOL", end_inst)


if __name__ == "__main__":
    unittest.main()
