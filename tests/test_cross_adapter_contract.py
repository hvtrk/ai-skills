"""Cross-Adapter Contract Equivalence Tests for Phase 5.

Asserts that CodexMemoryAdapter and AntigravityMemoryAdapter expose identical
capabilities, interfaces, protocols, and behavioral semantics against the
Generic Adapter Contract.
"""

from __future__ import annotations

import inspect
import sys
import tempfile
import unittest
from pathlib import Path

# Add repository root to path for imports
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapters.antigravity import AntigravityMemoryAdapter
from adapters.codex import CodexMemoryAdapter
from adapters.generic import (
    SUPPORTED_OPERATIONS,
    CapabilityReport,
    CapabilityStatus,
    GenericMemoryAdapter,
    OperationResult,
)


class CrossAdapterContractTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name).resolve()

        self.project_dir = (self.base_path / "shared_project").resolve()
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

        self.codex_adapter = CodexMemoryAdapter(
            project_root=self.project_dir,
            memory_core_path=self.core_script,
            global_memory_path=self.global_dir,
            skills_root=self.skills_source,
        )

        self.antigravity_adapter = AntigravityMemoryAdapter(
            project_root=self.project_dir,
            memory_core_path=self.core_script,
            global_memory_path=self.global_dir,
            skills_root=self.skills_source,
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    # -------------------------------------------------------------------------
    # 1. Interface & Inheritance Parity
    # -------------------------------------------------------------------------

    def test_adapter_inheritance_and_signatures(self):
        self.assertTrue(issubclass(CodexMemoryAdapter, GenericMemoryAdapter))
        self.assertTrue(issubclass(AntigravityMemoryAdapter, GenericMemoryAdapter))

        # Check public method signatures parity
        generic_methods = {
            name: inspect.signature(getattr(GenericMemoryAdapter, name))
            for name in dir(GenericMemoryAdapter)
            if not name.startswith("_")
        }

        codex_methods = {
            name: inspect.signature(getattr(CodexMemoryAdapter, name))
            for name in dir(CodexMemoryAdapter)
            if not name.startswith("_")
        }

        antigravity_methods = {
            name: inspect.signature(getattr(AntigravityMemoryAdapter, name))
            for name in dir(AntigravityMemoryAdapter)
            if not name.startswith("_")
        }

        self.assertEqual(set(codex_methods.keys()), set(generic_methods.keys()))
        self.assertEqual(set(antigravity_methods.keys()), set(generic_methods.keys()))

    # -------------------------------------------------------------------------
    # 2. Capability Detection Equivalence
    # -------------------------------------------------------------------------

    def test_capability_detection_equivalence(self):
        codex_caps = self.codex_adapter.get_capabilities()
        ag_caps = self.antigravity_adapter.get_capabilities()

        # Both should report NOT_INITIALIZED before init
        self.assertEqual(codex_caps.memory_core, ag_caps.memory_core)
        self.assertEqual(codex_caps.global_memory, ag_caps.global_memory)
        self.assertEqual(codex_caps.project_memory, ag_caps.project_memory)
        self.assertEqual(
            codex_caps.project_memory_initialized, ag_caps.project_memory_initialized
        )
        self.assertEqual(codex_caps.skills, ag_caps.skills)
        self.assertEqual(codex_caps.available_operations, ag_caps.available_operations)

        # Initialize via Generic Memory Core (using Codex adapter)
        self.codex_adapter.init(templates=self.templates_dir)

        # Both should now report AVAILABLE for project_memory
        codex_caps_after = self.codex_adapter.get_capabilities()
        ag_caps_after = self.antigravity_adapter.get_capabilities()

        self.assertEqual(codex_caps_after.project_memory, CapabilityStatus.AVAILABLE)
        self.assertEqual(ag_caps_after.project_memory, CapabilityStatus.AVAILABLE)
        self.assertTrue(codex_caps_after.project_memory_initialized)
        self.assertTrue(ag_caps_after.project_memory_initialized)
        self.assertEqual(
            codex_caps_after.available_operations, ag_caps_after.available_operations
        )

    # -------------------------------------------------------------------------
    # 3. Protocol & Startup Plan Equivalence
    # -------------------------------------------------------------------------

    def test_startup_retrieval_plan_equivalence(self):
        self.codex_adapter.init(templates=self.templates_dir)

        codex_plan = self.codex_adapter.get_startup_retrieval_plan(
            topics=["architecture", "gotchas"], profile=True
        )
        ag_plan = self.antigravity_adapter.get_startup_retrieval_plan(
            topics=["architecture", "gotchas"], profile=True
        )

        self.assertEqual(codex_plan["project_root"], ag_plan["project_root"])
        self.assertEqual(codex_plan["selected_topics"], ag_plan["selected_topics"])
        self.assertEqual(codex_plan["files_to_read"], ag_plan["files_to_read"])
        self.assertEqual(codex_plan["archive_excluded"], ag_plan["archive_excluded"])
        self.assertTrue(codex_plan["archive_excluded"])


if __name__ == "__main__":
    unittest.main()
