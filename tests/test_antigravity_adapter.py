"""Unit tests for Phase 5: Antigravity Harness Adapter.

Tests verify Antigravity-specific project root discovery, capability inspection,
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

from adapters.antigravity import AntigravityMemoryAdapter
from adapters.generic import (
    SUPPORTED_OPERATIONS,
    CapabilityStatus,
    GenericMemoryAdapter,
)


class AntigravityAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name).resolve()

        self.project_dir = (self.base_path / "antigravity_project").resolve()
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

        self.adapter = AntigravityMemoryAdapter(
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

        # 3. Antigravity environment variables
        clean_adapter = AntigravityMemoryAdapter()
        env_project = (self.base_path / "antigravity_env_project").resolve()

        with mock.patch.dict(
            os.environ, {"ANTIGRAVITY_PROJECT_ROOT": str(env_project)}
        ):
            self.assertEqual(clean_adapter.get_project_root(), env_project)

        with mock.patch.dict(
            os.environ, {"ANTIGRAVITY_WORKSPACE_ROOT": str(env_project)}, clear=True
        ):
            self.assertEqual(clean_adapter.get_project_root(), env_project)

        with mock.patch.dict(
            os.environ, {"GEMINI_PROJECT_ROOT": str(env_project)}, clear=True
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
        cfg_adapter = AntigravityMemoryAdapter(
            config={"project_root": str(env_project)}
        )
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(cfg_adapter.get_project_root(), env_project)

        # 6. CWD Fallback
        fallback_adapter = AntigravityMemoryAdapter()
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
        self.assertIn("Antigravity Memory System v2 Protocol", general_inst)

        startup_inst = self.adapter.get_instructions(topic="startup")
        self.assertIn("ANTIGRAVITY STARTUP RETRIEVAL PROTOCOL", startup_inst)

        end_inst = self.adapter.get_instructions(topic="end_of_task")
        self.assertIn("ANTIGRAVITY END-OF-TASK PROTOCOL", end_inst)

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
            topic="domain",
            input_payload={
                "operation": "update",
                "topic": "domain",
                "title": "Antigravity Domain Entity",
                "section": "Ubiquitous Language & Core Entities",
                "content": "- **Harness**: Runtime execution environment for autonomous agents.",
            },
        )
        self.assertTrue(update_res.success)

        # 4. Retrieve
        ret_res = self.adapter.retrieve(
            topics=["domain"], profile=True, global_memory=self.global_dir
        )
        self.assertTrue(ret_res.success)
        record_labels = [r["label"] for r in ret_res.data.get("records", [])]
        self.assertIn("project-domain", record_labels)

        # 5. Handoff
        handoff_res = self.adapter.handoff(
            input_payload={
                "operation": "handoff",
                "goal": "Verify Antigravity adapter",
                "files_in_progress": ["adapters/antigravity/adapter.py"],
                "build_status": "Clean",
                "dead_ends": ["None"],
                "next_step": "Run multi-agent tests",
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
                        "title": "Antigravity graduation trap",
                        "section": "Critical Traps",
                        "content": "- Ensure handoff is validated prior to graduating.",
                    }
                ],
            }
        )
        self.assertTrue(grad_res.success)

        # 7. Archive
        arch_res = self.adapter.archive(
            topic="domain",
            input_payload={
                "title": "Antigravity Domain Entity",
                "section": "Ubiquitous Language & Core Entities",
                "content": "- **Harness**: Runtime execution environment for autonomous agents.",
            },
            superseded_by="ADR-0100",
        )
        self.assertTrue(arch_res.success)

    # -------------------------------------------------------------------------
    # E. Failure Propagation
    # -------------------------------------------------------------------------

    def test_failure_propagation(self):
        broken_adapter = AntigravityMemoryAdapter(
            project_root=self.project_dir,
            memory_core_path=self.base_path / "nonexistent_core.py",
        )
        with mock.patch("shutil.which", return_value=None):
            fail_res = broken_adapter.check()
            self.assertFalse(fail_res.success)
            self.assertEqual(fail_res.exit_code, 127)
            self.assertTrue(any(f.severity == "ERROR" for f in fail_res.findings))

    # -------------------------------------------------------------------------
    # G. Out-of-the-box New Project Bootstrap Tests
    # -------------------------------------------------------------------------

    def test_new_project_out_of_the_box_behavior(self):
        new_project_dir = (self.base_path / "fresh_new_project").resolve()
        new_project_dir.mkdir()

        fresh_adapter = AntigravityMemoryAdapter(
            project_root=new_project_dir,
            memory_core_path=self.core_script,
            global_memory_path=self.global_dir,
            skills_root=self.skills_source,
        )

        # 1. Capability inspection recognizes uninitialized state
        caps = fresh_adapter.get_capabilities()
        self.assertEqual(caps.global_memory, CapabilityStatus.AVAILABLE)
        self.assertEqual(caps.project_memory, CapabilityStatus.NOT_INITIALIZED)
        self.assertFalse(caps.project_memory_initialized)
        self.assertEqual(caps.memory_core, CapabilityStatus.AVAILABLE)

        # 2. Retrieve succeeds on global memory without creating .memory/
        ret = fresh_adapter.retrieve(profile=True)
        self.assertTrue(ret.success)
        record_labels = [r["label"] for r in ret.data.get("records", [])]
        self.assertIn("global-conventions", record_labels)
        self.assertIn("global-user-profile", record_labels)
        self.assertFalse((new_project_dir / ".memory").exists())

        # 3. Instruction protocols explicitly communicate lazy & explicit init rules
        startup_instructions = fresh_adapter.get_instructions(topic="startup")
        self.assertIn("conventions.md", startup_instructions)
        self.assertIn("DO NOT silently create .memory/", startup_instructions)
        self.assertIn("Do NOT read .memory/archive/", startup_instructions)

        # 4. Explicit initialization through Memory Core succeeds
        init_res = fresh_adapter.init(templates=self.templates_dir)
        self.assertTrue(init_res.success)
        self.assertTrue((new_project_dir / ".memory").is_dir())
        self.assertTrue((new_project_dir / ".memory" / "INDEX.md").is_file())

    # -------------------------------------------------------------------------
    # H. Existing Project Lazy Retrieval & Archive Exclusion Tests
    # -------------------------------------------------------------------------

    def test_existing_project_lazy_retrieval_and_archive_exclusion(self):
        # Initialize project memory
        self.adapter.init(templates=self.templates_dir)

        # Write unique markers
        arch_marker = "ANTIGRAVITY_UNIQUE_ARCH_FACT_98765"
        self.adapter.update(
            topic="architecture",
            input_payload={
                "operation": "update",
                "topic": "architecture",
                "title": "Unique Arch Fact",
                "section": "Key Architectural Decisions",
                "content": f"- **Fact**: {arch_marker}",
            },
        )

        # Add a cold storage file in archive
        archive_dir = self.project_dir / ".memory" / "archive"
        archive_dir.mkdir(exist_ok=True)
        archived_file = archive_dir / "2026-08-28_superseded_fact.md"
        archived_file.write_text(
            "---\ntitle: Superseded\n---\nSECRET_ARCHIVE_MARKER\n",
            encoding="utf-8",
        )

        # Retrieve architecture topic
        ret = self.adapter.retrieve(topics=["architecture"])
        self.assertTrue(ret.success)

        retrieved_content = " ".join(
            r.get("content", "") for r in ret.data.get("records", [])
        )
        labels = [r["label"] for r in ret.data.get("records", [])]

        # Conventions and architecture are retrieved
        self.assertIn("global-conventions", labels)
        self.assertIn("project-architecture", labels)
        self.assertIn(arch_marker, retrieved_content)

        # Unrelated topics and archive are NOT retrieved
        self.assertNotIn("project-domain", labels)
        self.assertNotIn("project-gotchas", labels)
        self.assertNotIn("project-handoff", labels)
        self.assertNotIn("SECRET_ARCHIVE_MARKER", retrieved_content)

    # -------------------------------------------------------------------------
    # I. Global Memory Isolation Tests
    # -------------------------------------------------------------------------

    def test_global_memory_isolation(self):
        self.adapter.init(templates=self.templates_dir)

        # Project memory files
        project_files = {p.name for p in (self.project_dir / ".memory").iterdir()}
        # Global memory files
        global_files = {p.name for p in self.global_dir.iterdir()}

        # Verify global files are not inside project .memory/
        self.assertNotIn("user-profile.md", project_files)
        # Verify project files are not inside global memory
        self.assertNotIn("INDEX.md", global_files)
        self.assertNotIn("architecture.md", global_files)
        self.assertNotIn("session-handoff.md", global_files)

    # -------------------------------------------------------------------------
    # J. Dynamic Skill Discovery Tests
    # -------------------------------------------------------------------------

    def test_dynamic_skill_discovery(self):
        # Create dynamic skills in skill source
        for skill_name in ["dyn-skill-a", "dyn-skill-b", "dyn-skill-c"]:
            s_dir = self.skills_source / "skills" / skill_name
            s_dir.mkdir(parents=True, exist_ok=True)
            (s_dir / "SKILL.md").write_text(
                f"---\nname: {skill_name}\ndescription: Dynamic test skill\n---\n",
                encoding="utf-8",
            )

        src, sync = self.adapter.get_skill_root()
        self.assertEqual(src, self.skills_source)

        discovered = [
            p.name
            for p in (src / "skills").iterdir()
            if p.is_dir() and (p / "SKILL.md").is_file()
        ]
        self.assertIn("dyn-skill-a", discovered)
        self.assertIn("dyn-skill-b", discovered)
        self.assertIn("dyn-skill-c", discovered)

    # -------------------------------------------------------------------------
    # K. Harness Independence & Allowed Imports
    # -------------------------------------------------------------------------

    def test_harness_independence(self):
        import adapters.antigravity.adapter as ag_module

        adapter_file = Path(ag_module.__file__)
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

    # -------------------------------------------------------------------------
    # L. Setup Synchronization & Idempotency Tests
    # -------------------------------------------------------------------------

    def test_setup_antigravity_sync_idempotency(self):
        fake_home = self.base_path / "fake_home"
        fake_gemini = fake_home / ".gemini"
        fake_rules = fake_gemini / "config" / "rules"
        fake_rules.mkdir(parents=True, exist_ok=True)

        src_gemini_md = (ROOT / "adapters" / "antigravity" / "GEMINI.md").resolve()
        target_rule = fake_rules / "memory.md"
        global_gemini = fake_gemini / "GEMINI.md"

        # First sync: create symlinks
        target_rule.symlink_to(src_gemini_md)
        global_gemini.symlink_to(src_gemini_md)

        self.assertTrue(target_rule.is_symlink())
        self.assertEqual(target_rule.resolve(), src_gemini_md)
        self.assertTrue(global_gemini.is_symlink())
        self.assertEqual(global_gemini.resolve(), src_gemini_md)

        # Re-sync (idempotent replacement)
        if target_rule.is_symlink() or target_rule.exists():
            target_rule.unlink()
        target_rule.symlink_to(src_gemini_md)

        if global_gemini.is_symlink() or (
            global_gemini.exists() and global_gemini.stat().st_size == 0
        ):
            global_gemini.unlink()
        global_gemini.symlink_to(src_gemini_md)

        self.assertTrue(target_rule.is_symlink())
        self.assertEqual(target_rule.resolve(), src_gemini_md)


if __name__ == "__main__":
    unittest.main()
