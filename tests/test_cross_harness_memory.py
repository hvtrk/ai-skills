"""Cross-Harness Multi-Agent Memory Interchange Tests for Phase 5.

Simulates multi-agent cross-harness collaboration on a shared repository
using temporary projects:
- Step 1: Codex adapter initializes project memory.
- Step 2: Codex adapter writes an architecture entry.
- Step 3: Codex adapter writes a gotcha.
- Step 4: Antigravity adapter retrieves project memory (discovers Codex entries).
- Step 5: Antigravity adapter creates a session handoff.
- Step 6: Codex adapter retrieves session handoff (discovers Antigravity handoff).
- Step 7: Codex adapter graduates durable knowledge and resets handoff.
- Step 8: Antigravity adapter retrieves updated project memory (verifies consistent consolidated state).
- Step 9: Verify shared skill architecture across both adapters.

Authority: ADR 0002.
"""

from __future__ import annotations

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
from adapters.generic import CapabilityStatus


class CrossHarnessMemoryInterchangeTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name).resolve()

        self.project_dir = (self.base_path / "collab_project").resolve()
        self.project_dir.mkdir()

        self.global_dir = (self.base_path / "global_agents" / "memory").resolve()
        self.global_dir.mkdir(parents=True)
        (self.global_dir / "conventions.md").write_text(
            "# Conventions\nUniversal coding conventions.\n", encoding="utf-8"
        )
        (self.global_dir / "user-profile.md").write_text(
            "# Profile\nDeveloper profile.\n", encoding="utf-8"
        )

        self.skills_source = (self.base_path / "ai-skills").resolve()
        (self.skills_source / "skills" / "sample-skill").mkdir(parents=True)
        (self.skills_source / "skills" / "sample-skill" / "SKILL.md").write_text(
            "---\nname: sample-skill\ndescription: Test skill\n---\n",
            encoding="utf-8",
        )
        (self.skills_source / "scripts").mkdir(parents=True)

        self.synced_skills = (self.base_path / "global_agents" / "skills").resolve()
        (self.synced_skills / "sample-skill").mkdir(parents=True)
        (self.synced_skills / "sample-skill" / "SKILL.md").write_text(
            "---\nname: sample-skill\ndescription: Test skill\n---\n",
            encoding="utf-8",
        )

        self.core_script = (ROOT / "scripts" / "memory.py").resolve()
        self.templates_dir = (ROOT / "templates" / "memory").resolve()

        self.codex = CodexMemoryAdapter(
            project_root=self.project_dir,
            memory_core_path=self.core_script,
            global_memory_path=self.global_dir,
            skills_root=self.skills_source,
        )

        self.antigravity = AntigravityMemoryAdapter(
            project_root=self.project_dir,
            memory_core_path=self.core_script,
            global_memory_path=self.global_dir,
            skills_root=self.skills_source,
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_full_cross_harness_lifecycle_simulation(self):
        # ---------------------------------------------------------------------
        # STEP 1: Codex adapter initializes project memory
        # ---------------------------------------------------------------------
        init_res = self.codex.init(templates=self.templates_dir)
        self.assertTrue(init_res.success, f"Codex init failed: {init_res.messages}")
        self.assertTrue((self.project_dir / ".memory").is_dir())
        self.assertTrue((self.project_dir / ".memory" / "INDEX.md").is_file())

        # ---------------------------------------------------------------------
        # STEP 2: Codex adapter writes an architecture entry
        # ---------------------------------------------------------------------
        arch_payload = {
            "operation": "update",
            "topic": "architecture",
            "title": "ADR-0020 Event Driven Core",
            "section": "Key Architectural Decisions",
            "content": "- **[ADR-0020]**: Core events must use structured schema envelopes.",
        }
        update_arch_res = self.codex.update(input_payload=arch_payload)
        self.assertTrue(
            update_arch_res.success,
            f"Codex update arch failed: {update_arch_res.messages}",
        )

        # ---------------------------------------------------------------------
        # STEP 3: Codex adapter writes a gotcha
        # ---------------------------------------------------------------------
        gotcha_payload = {
            "operation": "update",
            "topic": "gotchas",
            "title": "Subprocess Timeout Quirk",
            "section": "Critical Traps",
            "content": "- Subprocesses must explicitly set capture_output=True to prevent pipe blocking.",
        }
        update_gotcha_res = self.codex.update(input_payload=gotcha_payload)
        self.assertTrue(
            update_gotcha_res.success,
            f"Codex update gotcha failed: {update_gotcha_res.messages}",
        )

        # ---------------------------------------------------------------------
        # STEP 4: Antigravity adapter retrieves project memory & discovers Codex entries
        # ---------------------------------------------------------------------
        ag_ret_arch = self.antigravity.retrieve(topics=["architecture"])
        self.assertTrue(
            ag_ret_arch.success,
            f"Antigravity retrieve arch failed: {ag_ret_arch.messages}",
        )
        arch_records = ag_ret_arch.data.get("records", [])
        arch_record = next(
            (r for r in arch_records if r["label"] == "project-architecture"),
            None,
        )
        self.assertIsNotNone(arch_record)
        self.assertIn(
            "Core events must use structured schema envelopes", arch_record["content"]
        )

        ag_ret_gotchas = self.antigravity.retrieve(topics=["gotchas"])
        self.assertTrue(ag_ret_gotchas.success)
        gotcha_records = ag_ret_gotchas.data.get("records", [])
        gotcha_record = next(
            (r for r in gotcha_records if r["label"] == "project-gotchas"),
            None,
        )
        self.assertIsNotNone(gotcha_record)
        self.assertIn("capture_output=True", gotcha_record["content"])

        # ---------------------------------------------------------------------
        # STEP 5: Antigravity creates a session handoff
        # ---------------------------------------------------------------------
        handoff_payload = {
            "operation": "handoff",
            "goal": "Refactor async task worker pool",
            "files_in_progress": ["src/workers/pool.py", "tests/test_pool.py"],
            "build_status": "All unit tests pass; stress test pending",
            "dead_ends": ["Thread pool caused GIL thrashing"],
            "next_step": "Promote worker pool architecture to durable memory",
        }
        ag_handoff_res = self.antigravity.handoff(input_payload=handoff_payload)
        self.assertTrue(
            ag_handoff_res.success,
            f"Antigravity handoff failed: {ag_handoff_res.messages}",
        )

        # ---------------------------------------------------------------------
        # STEP 6: Codex retrieves the handoff and sees Antigravity's in-progress state
        # ---------------------------------------------------------------------
        codex_ret_handoff = self.codex.retrieve(topics=["handoff"])
        self.assertTrue(codex_ret_handoff.success)
        handoff_records = codex_ret_handoff.data.get("records", [])
        handoff_record = next(
            (r for r in handoff_records if r["label"] == "project-handoff"),
            None,
        )
        self.assertIsNotNone(handoff_record)
        self.assertIn("Refactor async task worker pool", handoff_record["content"])
        self.assertIn("src/workers/pool.py", handoff_record["content"])
        self.assertIn(
            "Promote worker pool architecture to durable memory",
            handoff_record["content"],
        )

        # ---------------------------------------------------------------------
        # STEP 7: Codex graduates the durable knowledge
        # ---------------------------------------------------------------------
        graduation_plan = {
            "operation": "graduate",
            "source": "session-handoff.md",
            "promotions": [
                {
                    "topic": "architecture",
                    "title": "Async Worker Pool Architecture",
                    "section": "System Structure & Boundaries",
                    "content": "- `src/workers/pool.py`: Process-based worker pool for high-throughput tasks.",
                },
                {
                    "topic": "gotchas",
                    "title": "Python GIL in Async Workers",
                    "section": "Critical Traps",
                    "content": "- Heavy CPU tasks in async workers must use multiprocessing, not threading.",
                },
            ],
            "reset_handoff": True,
        }
        codex_grad_res = self.codex.graduate(plan_payload=graduation_plan)
        self.assertTrue(
            codex_grad_res.success,
            f"Codex graduate failed: {codex_grad_res.messages}",
        )

        # Verify session handoff was reset cleanly
        handoff_file_content = (
            self.project_dir / ".memory" / "session-handoff.md"
        ).read_text(encoding="utf-8")
        self.assertNotIn("Refactor async task worker pool", handoff_file_content)

        # ---------------------------------------------------------------------
        # STEP 8: Antigravity retrieves the resulting memory & verifies identical state
        # ---------------------------------------------------------------------
        ag_final_arch = self.antigravity.retrieve(topics=["architecture"])
        self.assertTrue(ag_final_arch.success)
        final_arch_content = next(
            r["content"]
            for r in ag_final_arch.data.get("records", [])
            if r["label"] == "project-architecture"
        )
        self.assertIn("src/workers/pool.py", final_arch_content)

        ag_final_gotchas = self.antigravity.retrieve(topics=["gotchas"])
        self.assertTrue(ag_final_gotchas.success)
        final_gotchas_content = next(
            r["content"]
            for r in ag_final_gotchas.data.get("records", [])
            if r["label"] == "project-gotchas"
        )
        self.assertIn("multiprocessing", final_gotchas_content)

        # Check passes cleanly on final state from both adapters
        self.assertTrue(self.codex.check().success)
        self.assertTrue(self.antigravity.check().success)

    def test_shared_skill_architecture_discovery(self):
        # ---------------------------------------------------------------------
        # STEP 9: Verify shared skill architecture discovery
        # ---------------------------------------------------------------------
        codex_src, codex_sync = self.codex.get_skill_root()
        ag_src, ag_sync = self.antigravity.get_skill_root()

        self.assertEqual(codex_src, ag_src)
        self.assertEqual(codex_src, self.skills_source)

        codex_caps = self.codex.get_capabilities()
        ag_caps = self.antigravity.get_capabilities()

        self.assertEqual(codex_caps.skills, CapabilityStatus.AVAILABLE)
        self.assertEqual(ag_caps.skills, CapabilityStatus.AVAILABLE)


if __name__ == "__main__":
    unittest.main()
