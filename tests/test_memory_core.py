import importlib.util
import io
import json
import os
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "memory_core", ROOT / "scripts" / "memory.py"
)
memory = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules["memory_core"] = memory
SPEC.loader.exec_module(memory)


class MemoryCoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project = Path(self.temp_dir.name) / "project"
        self.project.mkdir()
        self.templates = ROOT / "templates" / "memory"

    def tearDown(self):
        self.temp_dir.cleanup()

    # --- Initialization Tests ---

    def test_init_creates_required_structure_and_is_idempotent(self):
        code, payload = memory.initialize(
            self.project, self.templates, repair=False, dry_run=False
        )
        self.assertEqual(code, memory.EXIT_OK)
        self.assertIn("CREATED", "\n".join(payload["messages"]))
        target = self.project / ".memory"
        self.assertTrue((target / "archive").is_dir())
        for filename in memory.REQUIRED_FILES:
            self.assertTrue((target / filename).is_file())
        self.assertFalse((target / ".gitignore").exists())

        marker = target / "domain.md"
        marker.write_text("preserved user content\n", encoding="utf-8")
        code, _ = memory.initialize(
            self.project, self.templates, repair=False, dry_run=False
        )
        self.assertEqual(code, memory.EXIT_OK)
        self.assertEqual(marker.read_text(encoding="utf-8"), "preserved user content\n")

    def test_init_requires_explicit_repair_for_missing_required_file(self):
        memory.initialize(self.project, self.templates, repair=False, dry_run=False)
        missing = self.project / ".memory" / "gotchas.md"
        missing.unlink()
        code, payload = memory.initialize(
            self.project, self.templates, repair=False, dry_run=False
        )
        self.assertEqual(code, memory.EXIT_VALIDATION)
        self.assertFalse(missing.exists())
        self.assertIn("--repair", "\n".join(payload["messages"]))

        code, _ = memory.initialize(
            self.project, self.templates, repair=True, dry_run=False
        )
        self.assertEqual(code, memory.EXIT_OK)
        self.assertTrue(missing.is_file())

    def test_init_dry_run_does_not_create_directory(self):
        code, payload = memory.initialize(
            self.project, self.templates, repair=False, dry_run=True
        )
        self.assertEqual(code, memory.EXIT_OK)
        self.assertFalse((self.project / ".memory").exists())
        self.assertTrue(
            any("DRY-RUN: would create" in msg for msg in payload["messages"])
        )

    def test_init_repair_dry_run_does_not_create_missing_files(self):
        memory.initialize(self.project, self.templates, repair=False, dry_run=False)
        missing = self.project / ".memory" / "gotchas.md"
        missing.unlink()
        code, payload = memory.initialize(
            self.project, self.templates, repair=True, dry_run=True
        )
        self.assertEqual(code, memory.EXIT_OK)
        self.assertFalse(missing.exists())
        self.assertTrue(
            any("DRY-RUN: would create" in msg for msg in payload["messages"])
        )

    # --- Structure Validation Tests ---

    def test_check_passes_on_valid_initialized_memory(self):
        memory.initialize(self.project, self.templates, repair=False, dry_run=False)
        code, payload = memory.check_memory(self.project)
        self.assertEqual(code, memory.EXIT_OK)
        self.assertEqual(payload["findings"][0]["severity"], "OK")

    def test_check_reports_missing_memory_directory(self):
        code, payload = memory.check_memory(self.project)
        self.assertEqual(code, memory.EXIT_VALIDATION)
        self.assertEqual(payload["findings"][0]["severity"], "ERROR")
        self.assertIn("memory directory is missing", payload["findings"][0]["message"])

    def test_check_reports_collision_when_memory_is_a_file(self):
        target = self.project / ".memory"
        target.write_text("not a directory\n", encoding="utf-8")
        code, payload = memory.check_memory(self.project)
        self.assertEqual(code, memory.EXIT_VALIDATION)
        self.assertTrue(any("collision" in f["message"] for f in payload["findings"]))

    def test_check_reports_missing_or_colliding_archive(self):
        memory.initialize(self.project, self.templates, repair=False, dry_run=False)
        archive_dir = self.project / ".memory" / "archive"
        archive_dir.rmdir()

        code, payload = memory.check_memory(self.project)
        self.assertEqual(code, memory.EXIT_VALIDATION)
        self.assertTrue(
            any(
                "archive directory is missing" in f["message"]
                for f in payload["findings"]
            )
        )

        # Collision: archive is a file
        archive_dir.write_text("file instead of dir\n", encoding="utf-8")
        code, payload = memory.check_memory(self.project)
        self.assertEqual(code, memory.EXIT_VALIDATION)
        self.assertTrue(
            any(
                "archive path exists but is not a directory" in f["message"]
                for f in payload["findings"]
            )
        )

    def test_check_reports_required_file_is_directory_collision(self):
        memory.initialize(self.project, self.templates, repair=False, dry_run=False)
        gotchas = self.project / ".memory" / "gotchas.md"
        gotchas.unlink()
        gotchas.mkdir()

        code, payload = memory.check_memory(self.project)
        self.assertEqual(code, memory.EXIT_VALIDATION)
        self.assertTrue(any("collision" in f["message"] for f in payload["findings"]))

    # --- Markdown Heading & Duplicate Tests ---

    def test_check_fails_on_missing_required_heading(self):
        memory.initialize(self.project, self.templates, repair=False, dry_run=False)
        arch = self.project / ".memory" / "architecture.md"
        arch.write_text(
            "# Custom Architecture without standard headings\n", encoding="utf-8"
        )
        code, payload = memory.check_memory(self.project)
        self.assertEqual(code, memory.EXIT_VALIDATION)
        self.assertTrue(
            any(
                "missing required section" in item["message"]
                for item in payload["findings"]
            )
        )

    def test_check_detects_duplicate_headings(self):
        memory.initialize(self.project, self.templates, repair=False, dry_run=False)
        arch = self.project / ".memory" / "architecture.md"
        content = arch.read_text(encoding="utf-8")
        # Duplicate a heading
        content += "\n## Key Architectural Decisions\nExtra content\n"
        arch.write_text(content, encoding="utf-8")

        code, payload = memory.check_memory(self.project)
        self.assertEqual(code, memory.EXIT_VALIDATION)
        dup_findings = [
            f
            for f in payload["findings"]
            if "duplicate identical heading" in f["message"]
        ]
        self.assertTrue(len(dup_findings) > 0)
        self.assertIsNotNone(dup_findings[0].get("line"))

    # --- INDEX.md Line Limit Tests ---

    def test_check_index_exact_limit_passes(self):
        memory.initialize(self.project, self.templates, repair=False, dry_run=False)
        index = self.project / ".memory" / "INDEX.md"
        # 40 lines total, containing required heading
        lines = ["# Project Memory Index"] + [f"- Line {i}" for i in range(2, 41)]
        index.write_text("\n".join(lines) + "\n", encoding="utf-8")

        code, payload = memory.check_memory(self.project)
        self.assertEqual(code, memory.EXIT_OK)

    def test_check_index_over_limit_fails(self):
        memory.initialize(self.project, self.templates, repair=False, dry_run=False)
        index = self.project / ".memory" / "INDEX.md"
        # 41 lines total
        lines = ["# Project Memory Index"] + [f"- Line {i}" for i in range(2, 42)]
        index.write_text("\n".join(lines) + "\n", encoding="utf-8")

        code, payload = memory.check_memory(self.project)
        self.assertEqual(code, memory.EXIT_VALIDATION)
        limit_findings = [
            f for f in payload["findings"] if "exceeds 40 lines" in f["message"]
        ]
        self.assertTrue(len(limit_findings) > 0)
        self.assertEqual(limit_findings[0]["line"], 41)
        self.assertIn("contains 41 lines", limit_findings[0]["message"])

    # --- Frontmatter Validation Tests ---

    def test_frontmatter_valid_on_topic_file(self):
        memory.initialize(self.project, self.templates, repair=False, dry_run=False)
        arch = self.project / ".memory" / "architecture.md"
        content = (
            "---\ncreated: 2026-08-28\nupdated: 2026-08-28\nsource: architecture-review\n---\n"
            + arch.read_text(encoding="utf-8")
        )
        arch.write_text(content, encoding="utf-8")

        code, payload = memory.check_memory(self.project)
        self.assertEqual(code, memory.EXIT_OK)

    def test_frontmatter_unclosed_delimiter(self):
        memory.initialize(self.project, self.templates, repair=False, dry_run=False)
        arch = self.project / ".memory" / "architecture.md"
        content = "---\ncreated: 2026-08-28\n# no closing delimiter\n" + arch.read_text(
            encoding="utf-8"
        )
        arch.write_text(content, encoding="utf-8")

        code, payload = memory.check_memory(self.project)
        self.assertEqual(code, memory.EXIT_VALIDATION)
        self.assertTrue(
            any("malformed frontmatter" in f["message"] for f in payload["findings"])
        )

    def test_frontmatter_invalid_date_format(self):
        memory.initialize(self.project, self.templates, repair=False, dry_run=False)
        arch = self.project / ".memory" / "architecture.md"
        content = "---\ncreated: invalid-date\n---\n" + arch.read_text(encoding="utf-8")
        arch.write_text(content, encoding="utf-8")

        code, payload = memory.check_memory(self.project)
        self.assertEqual(code, memory.EXIT_VALIDATION)
        self.assertTrue(
            any("invalid date format" in f["message"] for f in payload["findings"])
        )

    def test_frontmatter_duplicate_key(self):
        memory.initialize(self.project, self.templates, repair=False, dry_run=False)
        arch = self.project / ".memory" / "architecture.md"
        content = (
            "---\ncreated: 2026-08-28\ncreated: 2026-08-29\n---\n"
            + arch.read_text(encoding="utf-8")
        )
        arch.write_text(content, encoding="utf-8")

        code, payload = memory.check_memory(self.project)
        self.assertEqual(code, memory.EXIT_VALIDATION)
        self.assertTrue(
            any(
                "duplicate frontmatter key" in f["message"] for f in payload["findings"]
            )
        )

    # --- Archive Validation Tests ---

    def test_archive_valid_entry(self):
        memory.initialize(self.project, self.templates, repair=False, dry_run=False)
        entry = self.project / ".memory" / "archive" / "2026-08-28-architecture-v1.md"
        entry.write_text(
            "---\narchive_date: 2026-08-28\nsource_topic: architecture\nsuperseded_by: ADR-0002\n---\n# Superseded Architecture\nOld text.\n",
            encoding="utf-8",
        )

        code, payload = memory.check_memory(self.project)
        self.assertEqual(code, memory.EXIT_OK)

    def test_archive_missing_frontmatter(self):
        memory.initialize(self.project, self.templates, repair=False, dry_run=False)
        entry = self.project / ".memory" / "archive" / "2026-08-28-architecture-v1.md"
        entry.write_text("# Plain markdown without frontmatter\n", encoding="utf-8")

        code, payload = memory.check_memory(self.project)
        self.assertEqual(code, memory.EXIT_VALIDATION)
        self.assertTrue(
            any(
                "missing required YAML frontmatter" in f["message"]
                for f in payload["findings"]
            )
        )

    def test_archive_missing_required_fields(self):
        memory.initialize(self.project, self.templates, repair=False, dry_run=False)
        entry = self.project / ".memory" / "archive" / "2026-08-28-architecture-v1.md"
        entry.write_text(
            "---\narchive_date: 2026-08-28\n---\n# Incomplete frontmatter\n",
            encoding="utf-8",
        )

        code, payload = memory.check_memory(self.project)
        self.assertEqual(code, memory.EXIT_VALIDATION)
        self.assertTrue(
            any(
                "missing required field: 'source_topic'" in f["message"]
                for f in payload["findings"]
            )
        )
        self.assertTrue(
            any(
                "missing required field: 'superseded_by'" in f["message"]
                for f in payload["findings"]
            )
        )

    def test_archive_invalid_filename_convention(self):
        memory.initialize(self.project, self.templates, repair=False, dry_run=False)
        entry = self.project / ".memory" / "archive" / "bad_archive_name.md"
        entry.write_text(
            "---\narchive_date: 2026-08-28\nsource_topic: architecture\nsuperseded_by: ADR-0002\n---\n# Superseded\n",
            encoding="utf-8",
        )

        code, payload = memory.check_memory(self.project)
        self.assertEqual(code, memory.EXIT_VALIDATION)
        self.assertTrue(
            any("invalid archive filename" in f["message"] for f in payload["findings"])
        )

    def test_archive_impossible_supersession(self):
        memory.initialize(self.project, self.templates, repair=False, dry_run=False)
        entry = self.project / ".memory" / "archive" / "2026-08-28-architecture-v1.md"
        entry.write_text(
            "---\narchive_date: 2026-08-28\nsource_topic: architecture\nsuperseded_by: self\n---\n# Superseded\n",
            encoding="utf-8",
        )

        code, payload = memory.check_memory(self.project)
        self.assertEqual(code, memory.EXIT_VALIDATION)
        self.assertTrue(
            any("impossible supersession" in f["message"] for f in payload["findings"])
        )

    def test_archive_nested_directory_rejected(self):
        memory.initialize(self.project, self.templates, repair=False, dry_run=False)
        nested = self.project / ".memory" / "archive" / "nested_dir"
        nested.mkdir()

        code, payload = memory.check_memory(self.project)
        self.assertEqual(code, memory.EXIT_VALIDATION)
        self.assertTrue(
            any(
                "unexpected directory in archive" in f["message"]
                for f in payload["findings"]
            )
        )

    # --- Internal Markdown Link Validation Tests ---

    def test_link_validation_valid_relative_links(self):
        memory.initialize(self.project, self.templates, repair=False, dry_run=False)
        arch = self.project / ".memory" / "architecture.md"
        arch.write_text(
            arch.read_text(encoding="utf-8")
            + "\nSee [domain glossary](./domain.md) and [gotchas](gotchas.md).\n",
            encoding="utf-8",
        )

        code, payload = memory.check_memory(self.project)
        self.assertEqual(code, memory.EXIT_OK)

    def test_link_validation_broken_relative_link(self):
        memory.initialize(self.project, self.templates, repair=False, dry_run=False)
        arch = self.project / ".memory" / "architecture.md"
        arch.write_text(
            arch.read_text(encoding="utf-8")
            + "\nSee [broken](./nonexistent_file.md).\n",
            encoding="utf-8",
        )

        code, payload = memory.check_memory(self.project)
        self.assertEqual(code, memory.EXIT_VALIDATION)
        link_findings = [
            f
            for f in payload["findings"]
            if "broken internal reference" in f["message"]
        ]
        self.assertTrue(len(link_findings) > 0)
        self.assertIn("nonexistent_file.md", link_findings[0]["message"])

    def test_link_validation_ignores_external_urls_and_anchors(self):
        memory.initialize(self.project, self.templates, repair=False, dry_run=False)
        arch = self.project / ".memory" / "architecture.md"
        arch.write_text(
            arch.read_text(encoding="utf-8")
            + "\nExternal: [Google](https://google.com), [Email](mailto:user@test.com), [Anchor](#key-architectural-decisions).\n",
            encoding="utf-8",
        )

        code, payload = memory.check_memory(self.project)
        self.assertEqual(code, memory.EXIT_OK)

    # --- Session Handoff & Freshness Tests ---

    def test_handoff_stale_warning(self):
        memory.initialize(self.project, self.templates, repair=False, dry_run=False)
        handoff = self.project / ".memory" / "session-handoff.md"
        # Set mtime to 10 days ago
        old_time = time.time() - (10 * 86400)
        os.utime(handoff, (old_time, old_time))

        code, payload = memory.check_memory(self.project, stale_days=7.0)
        # Warning should NOT cause validation failure (exit code remains 0 if no errors)
        self.assertEqual(code, memory.EXIT_OK)
        warnings = [f for f in payload["findings"] if f["severity"] == "WARNING"]
        self.assertTrue(len(warnings) > 0)
        self.assertIn("freshness threshold", warnings[0]["message"])

    # --- Diagnostics & Formatting Tests ---

    def test_diagnostics_json_and_text_formatting(self):
        memory.initialize(self.project, self.templates, repair=False, dry_run=False)
        index = self.project / ".memory" / "INDEX.md"
        index.write_text(
            "\n".join(
                ["# Project Memory Index"] + [f"- Line {i}" for i in range(2, 45)]
            ),
            encoding="utf-8",
        )

        buffer_text = io.StringIO()
        with redirect_stdout(buffer_text):
            code = memory.main(["check", str(self.project)])
        self.assertEqual(code, memory.EXIT_VALIDATION)
        text_out = buffer_text.getvalue()
        self.assertIn("ERROR:", text_out)
        self.assertIn("INDEX.md:41:", text_out)
        self.assertIn("(Action:", text_out)

        buffer_json = io.StringIO()
        with redirect_stdout(buffer_json):
            code = memory.main(["--format", "json", "check", str(self.project)])
        self.assertEqual(code, memory.EXIT_VALIDATION)
        parsed = json.loads(buffer_json.getvalue())
        self.assertIn("findings", parsed)
        self.assertEqual(parsed["findings"][0]["severity"], "ERROR")
        self.assertEqual(parsed["findings"][0]["line"], 41)
        self.assertIsNotNone(parsed["findings"][0]["suggested_action"])

    def test_archive_case_insensitive_collision(self):
        memory.initialize(self.project, self.templates, repair=False, dry_run=False)
        archive_dir = self.project / ".memory" / "archive"
        entry1 = archive_dir / "2026-08-28-architecture-v1.md"
        entry1.write_text(
            "---\narchive_date: 2026-08-28\nsource_topic: architecture\nsuperseded_by: ADR-0002\n---\n# Superseded\n",
            encoding="utf-8",
        )

        orig_iterdir = Path.iterdir
        try:
            # Mock iterdir on archive to return colliding filenames
            colliding_path = archive_dir / "2026-08-28-ARCHITECTURE-v1.md"

            def mock_iter(path_obj):
                if path_obj == archive_dir:
                    return [entry1, colliding_path]
                return orig_iterdir(path_obj)

            Path.iterdir = mock_iter
            code, payload = memory.check_memory(self.project)
            self.assertEqual(code, memory.EXIT_VALIDATION)
            self.assertTrue(
                any("collision" in f["message"] for f in payload["findings"])
            )
        finally:
            Path.iterdir = orig_iterdir

    def test_archive_broken_internal_reference(self):
        memory.initialize(self.project, self.templates, repair=False, dry_run=False)
        entry = self.project / ".memory" / "archive" / "2026-08-28-architecture-v1.md"
        entry.write_text(
            "---\narchive_date: 2026-08-28\nsource_topic: architecture\nsuperseded_by: ADR-0002\n---\n# Arch\nSee [nonexistent](./missing.md)\n",
            encoding="utf-8",
        )
        code, payload = memory.check_memory(self.project)
        self.assertEqual(code, memory.EXIT_VALIDATION)
        self.assertTrue(
            any(
                "broken internal reference in archive" in f["message"]
                for f in payload["findings"]
            )
        )

    # --- Safety & Locking Tests ---

    def test_atomic_write_replaces_complete_content(self):
        destination = self.project / "value.md"
        memory.atomic_write_text(destination, "first\n")
        memory.atomic_write_text(destination, "second\n")
        self.assertEqual(destination.read_text(encoding="utf-8"), "second\n")

    def test_atomic_write_cleans_up_temporary_file_on_failure(self):
        destination = self.project / "test_cleanup.md"
        parent = destination.parent
        initial_files = set(parent.iterdir())

        class CustomWriteError(Exception):
            pass

        # Monkeypatch os.replace to raise an exception
        original_replace = os.replace
        try:

            def failing_replace(src, dst):
                raise CustomWriteError("simulated replacement failure")

            os.replace = failing_replace

            with self.assertRaises(CustomWriteError):
                memory.atomic_write_text(destination, "test content\n")

            # Check that no temporary files remain
            current_files = set(parent.iterdir())
            temp_files = [f for f in current_files if f.name.endswith(".tmp")]
            self.assertEqual(len(temp_files), 0)
        finally:
            os.replace = original_replace

    def test_initial_memory_stage_cleanup_on_failure(self):
        class StageError(Exception):
            pass

        original_copy = memory.copy_template
        try:

            def failing_copy(template, destination):
                raise StageError("simulated copy failure")

            memory.copy_template = failing_copy

            with self.assertRaises(StageError):
                memory.initial_memory_stage(self.project, self.templates)

            # Check no .memory.init-* directories remain in project
            init_dirs = list(self.project.glob(".memory.init-*"))
            self.assertEqual(len(init_dirs), 0)
        finally:
            memory.copy_template = original_copy

    def test_memory_lock_stale_lock_recovery(self):
        target = self.project / ".memory"
        target.mkdir(parents=True, exist_ok=True)
        lock_file = target / ".memory.lock"
        # Simulate stale lock from dead PID (PID 99999999 is nonexistent)
        lock_file.write_text("pid=99999999\ncreated_at=100000\n", encoding="utf-8")

        # Acquisition should safely recover stale lock without hanging
        with memory.memory_lock(target, timeout_seconds=1.0):
            self.assertTrue(lock_file.exists())
            content = lock_file.read_text(encoding="utf-8")
            self.assertIn(f"pid={os.getpid()}", content)
        self.assertFalse(lock_file.exists())

    # --- Retrieval Tests ---

    def test_retrieve_is_lazy_and_does_not_read_archive(self):
        memory.initialize(self.project, self.templates, repair=False, dry_run=False)
        global_memory = Path(self.temp_dir.name) / "global"
        global_memory.mkdir()
        (global_memory / "conventions.md").write_text("conventions\n", encoding="utf-8")
        (global_memory / "user-profile.md").write_text("profile\n", encoding="utf-8")
        archive = self.project / ".memory" / "archive" / "2026-08-28-architecture-v1.md"
        archive.write_text("archive-only\n", encoding="utf-8")

        code, payload = memory.retrieve(
            self.project, global_memory, include_profile=False, topics=["domain"]
        )
        self.assertEqual(code, memory.EXIT_OK)
        labels = [record["label"] for record in payload["records"]]
        self.assertEqual(
            labels, ["global-conventions", "project-index", "project-domain"]
        )
        self.assertNotIn("archive-only", json.dumps(payload))

    def test_retrieve_includes_profile_and_multiple_topics(self):
        memory.initialize(self.project, self.templates, repair=False, dry_run=False)
        global_memory = Path(self.temp_dir.name) / "global"
        global_memory.mkdir()
        (global_memory / "conventions.md").write_text("conventions\n", encoding="utf-8")
        (global_memory / "user-profile.md").write_text("profile\n", encoding="utf-8")

        code, payload = memory.retrieve(
            self.project,
            global_memory,
            include_profile=True,
            topics=["architecture", "gotchas"],
        )
        self.assertEqual(code, memory.EXIT_OK)
        labels = [r["label"] for r in payload["records"]]
        self.assertEqual(
            labels,
            [
                "global-conventions",
                "global-user-profile",
                "project-index",
                "project-architecture",
                "project-gotchas",
            ],
        )

    def test_retrieve_without_project_memory(self):
        global_memory = Path(self.temp_dir.name) / "global"
        global_memory.mkdir()
        (global_memory / "conventions.md").write_text("conventions\n", encoding="utf-8")

        code, payload = memory.retrieve(
            self.project, global_memory, include_profile=False, topics=[]
        )
        self.assertEqual(code, memory.EXIT_OK)
        self.assertEqual(len(payload["records"]), 1)
        self.assertEqual(payload["records"][0]["label"], "global-conventions")
        self.assertTrue(
            any("no project memory" in msg for msg in payload.get("messages", []))
        )

    # --- Phase 3: Update Tests ---

    def test_update_valid_json_plan(self):
        memory.initialize(self.project, self.templates, repair=False, dry_run=False)
        plan = {
            "operation": "update",
            "topic": "architecture",
            "title": "ADR-0003 Distributed Caching",
            "section": "Key Architectural Decisions",
            "content": "- **[ADR-0003]**: Use Redis for distributed token caching with 5-minute TTL.",
        }
        plan_file = Path(self.temp_dir.name) / "update_plan.json"
        plan_file.write_text(json.dumps(plan), encoding="utf-8")

        input_data = memory.load_input_payload(str(plan_file))
        code, payload = memory.update_memory(self.project, None, input_data)
        self.assertEqual(code, memory.EXIT_OK)
        self.assertEqual(payload["operation"], "update")
        arch_content = (self.project / ".memory" / "architecture.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("ADR-0003", arch_content)
        self.assertIn("Redis for distributed token caching", arch_content)

    def test_update_valid_markdown_file(self):
        memory.initialize(self.project, self.templates, repair=False, dry_run=False)
        md_file = Path(self.temp_dir.name) / "note.md"
        md_file.write_text(
            "- **[Token Quotas]**: Strict rate limits on auth endpoint.\n",
            encoding="utf-8",
        )

        input_data = memory.load_input_payload(str(md_file))
        code, payload = memory.update_memory(self.project, "gotchas", input_data)
        self.assertEqual(code, memory.EXIT_OK)
        gotchas_content = (self.project / ".memory" / "gotchas.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Token Quotas", gotchas_content)

    def test_update_with_section_and_metadata(self):
        memory.initialize(self.project, self.templates, repair=False, dry_run=False)
        plan = {
            "operation": "update",
            "topic": "domain",
            "title": "Tenant Isolation",
            "section": "Core Entities & Vocabulary",
            "content": "- **[Tenant Isolation]**: Isolated customer workspace partition.\n  - _Invariants_: Cross-tenant access forbidden.",
            "metadata": {
                "created": "2026-08-28",
                "updated": "2026-08-28",
                "source": "security-review",
            },
        }
        plan_file = Path(self.temp_dir.name) / "domain_plan.json"
        plan_file.write_text(json.dumps(plan), encoding="utf-8")

        input_data = memory.load_input_payload(str(plan_file))
        code, _ = memory.update_memory(self.project, None, input_data)
        self.assertEqual(code, memory.EXIT_OK)
        domain_content = (self.project / ".memory" / "domain.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Tenant Isolation", domain_content)
        self.assertIn("source: security-review", domain_content)

    def test_update_invalid_topic_rejected(self):
        memory.initialize(self.project, self.templates, repair=False, dry_run=False)
        plan = {"topic": "invalid_topic", "content": "Some text"}
        plan_file = Path(self.temp_dir.name) / "bad_plan.json"
        plan_file.write_text(json.dumps(plan), encoding="utf-8")

        input_data = memory.load_input_payload(str(plan_file))
        with self.assertRaises(memory.MemoryError) as cm:
            memory.update_memory(self.project, None, input_data)
        self.assertIn("Invalid topic", str(cm.exception))

    def test_update_empty_content_rejected(self):
        memory.initialize(self.project, self.templates, repair=False, dry_run=False)
        plan = {"topic": "architecture", "content": "   "}
        plan_file = Path(self.temp_dir.name) / "empty_plan.json"
        plan_file.write_text(json.dumps(plan), encoding="utf-8")

        input_data = memory.load_input_payload(str(plan_file))
        with self.assertRaises(memory.MemoryError) as cm:
            memory.update_memory(self.project, None, input_data)
        self.assertIn("empty", str(cm.exception))

    def test_update_exact_duplicate_rejected(self):
        memory.initialize(self.project, self.templates, repair=False, dry_run=False)
        plan = {
            "topic": "gotchas",
            "content": "- **[Database Locks]**: Avoid table locks in migrations.",
        }
        plan_file = Path(self.temp_dir.name) / "dup_plan.json"
        plan_file.write_text(json.dumps(plan), encoding="utf-8")

        input_data = memory.load_input_payload(str(plan_file))
        code1, _ = memory.update_memory(self.project, None, input_data)
        self.assertEqual(code1, memory.EXIT_OK)

        # Attempting identical update again must fail validation
        code2, payload2 = memory.update_memory(self.project, None, input_data)
        self.assertEqual(code2, memory.EXIT_VALIDATION)
        self.assertTrue(any("duplicate" in msg.lower() for msg in payload2["messages"]))

    def test_update_deterministic_conflict_rejected(self):
        memory.initialize(self.project, self.templates, repair=False, dry_run=False)
        plan1 = {
            "topic": "architecture",
            "title": "AuthService",
            "content": "- **[AuthService]**: Authenticates via JWT tokens.",
        }
        plan1_file = Path(self.temp_dir.name) / "plan1.json"
        plan1_file.write_text(json.dumps(plan1), encoding="utf-8")
        input1 = memory.load_input_payload(str(plan1_file))
        code1, _ = memory.update_memory(self.project, None, input1)
        self.assertEqual(code1, memory.EXIT_OK)

        # Attempting conflicting update with same title but different content
        plan2 = {
            "topic": "architecture",
            "title": "AuthService",
            "content": "- **[AuthService]**: Authenticates via Session Cookies only.",
        }
        plan2_file = Path(self.temp_dir.name) / "plan2.json"
        plan2_file.write_text(json.dumps(plan2), encoding="utf-8")
        input2 = memory.load_input_payload(str(plan2_file))
        code2, payload2 = memory.update_memory(self.project, None, input2)
        self.assertEqual(code2, memory.EXIT_VALIDATION)
        self.assertTrue(any("conflict" in msg.lower() for msg in payload2["messages"]))

    def test_update_malformed_json_input(self):
        memory.initialize(self.project, self.templates, repair=False, dry_run=False)
        bad_json = Path(self.temp_dir.name) / "bad.json"
        bad_json.write_text("{ unquoted_key: val ", encoding="utf-8")

        with self.assertRaises(memory.MemoryError) as cm:
            memory.load_input_payload(str(bad_json))
        self.assertIn("Malformed JSON", str(cm.exception))

    def test_update_validation_failure_rollback(self):
        memory.initialize(self.project, self.templates, repair=False, dry_run=False)
        orig_arch = (self.project / ".memory" / "architecture.md").read_text(
            encoding="utf-8"
        )

        # Plan contains a broken relative markdown link that will fail post-mutation validation
        plan = {
            "topic": "architecture",
            "content": "- Broken reference: [missing](./nonexistent_ref.md)\n",
        }
        plan_file = Path(self.temp_dir.name) / "broken_plan.json"
        plan_file.write_text(json.dumps(plan), encoding="utf-8")

        input_data = memory.load_input_payload(str(plan_file))
        code, payload = memory.update_memory(self.project, None, input_data)
        self.assertEqual(code, memory.EXIT_VALIDATION)
        self.assertTrue(
            any("rolled back" in msg for msg in payload.get("messages", []))
        )
        # Verify architecture.md was rolled back to original pristine state
        self.assertEqual(
            (self.project / ".memory" / "architecture.md").read_text(encoding="utf-8"),
            orig_arch,
        )

    def test_update_dry_run_does_not_modify_file(self):
        memory.initialize(self.project, self.templates, repair=False, dry_run=False)
        orig_arch = (self.project / ".memory" / "architecture.md").read_text(
            encoding="utf-8"
        )

        plan = {
            "topic": "architecture",
            "content": "- **[NewService]**: New service description.",
        }
        plan_file = Path(self.temp_dir.name) / "dry_plan.json"
        plan_file.write_text(json.dumps(plan), encoding="utf-8")

        input_data = memory.load_input_payload(str(plan_file))
        code, payload = memory.update_memory(
            self.project, None, input_data, dry_run=True
        )
        self.assertEqual(code, memory.EXIT_OK)
        self.assertTrue(any("DRY-RUN:" in msg for msg in payload["messages"]))
        self.assertEqual(
            (self.project / ".memory" / "architecture.md").read_text(encoding="utf-8"),
            orig_arch,
        )

    # --- Phase 3: Handoff Tests ---

    def test_handoff_valid_json_plan(self):
        memory.initialize(self.project, self.templates, repair=False, dry_run=False)
        plan = {
            "operation": "handoff",
            "goal": "Refactor token bucket algorithm",
            "files_in_progress": ["src/ratelimit.py", "tests/test_ratelimit.py"],
            "build_status": "Tests passing, lint clean",
            "dead_ends": ["Fixed window counter caused stampedes"],
            "next_step": "Benchmark under 10k rps load",
        }
        plan_file = Path(self.temp_dir.name) / "handoff.json"
        plan_file.write_text(json.dumps(plan), encoding="utf-8")

        input_data = memory.load_input_payload(str(plan_file))
        code, payload = memory.handoff_memory(self.project, input_data)
        self.assertEqual(code, memory.EXIT_OK)
        handoff_content = (self.project / ".memory" / "session-handoff.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Refactor token bucket algorithm", handoff_content)
        self.assertIn("src/ratelimit.py", handoff_content)
        self.assertIn("Benchmark under 10k rps load", handoff_content)

    def test_handoff_valid_markdown_file(self):
        memory.initialize(self.project, self.templates, repair=False, dry_run=False)
        md_text = """# Session Handoff (Active Workstream)

> Short-term ephemeral state for AI agent continuity. Reset upon task completion.

## Current Goal
- Implement OAuth2 PKCE flow

## State & Files in Progress
- Modified files: src/auth.py
- Build / Test status: In progress

## Dead Ends & What Failed
- Avoid: Client secret in frontend SPA

## Immediate Next Step
- Add test cases for code challenge verification
"""
        md_file = Path(self.temp_dir.name) / "handoff.md"
        md_file.write_text(md_text, encoding="utf-8")

        input_data = memory.load_input_payload(str(md_file))
        code, payload = memory.handoff_memory(self.project, input_data)
        self.assertEqual(code, memory.EXIT_OK)
        self.assertEqual(
            (self.project / ".memory" / "session-handoff.md").read_text(
                encoding="utf-8"
            ),
            md_text,
        )

    def test_handoff_replaces_previous_state(self):
        memory.initialize(self.project, self.templates, repair=False, dry_run=False)
        plan1 = {"goal": "First Goal", "next_step": "First Next Step"}
        f1 = Path(self.temp_dir.name) / "h1.json"
        f1.write_text(json.dumps(plan1), encoding="utf-8")
        memory.handoff_memory(self.project, memory.load_input_payload(str(f1)))

        plan2 = {"goal": "Second Goal", "next_step": "Second Next Step"}
        f2 = Path(self.temp_dir.name) / "h2.json"
        f2.write_text(json.dumps(plan2), encoding="utf-8")
        memory.handoff_memory(self.project, memory.load_input_payload(str(f2)))

        content = (self.project / ".memory" / "session-handoff.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Second Goal", content)
        self.assertNotIn("First Goal", content)

    def test_handoff_missing_required_fields_rejected(self):
        memory.initialize(self.project, self.templates, repair=False, dry_run=False)
        plan = {"files_in_progress": ["test.py"]}  # missing goal and next_step
        f = Path(self.temp_dir.name) / "bad_h.json"
        f.write_text(json.dumps(plan), encoding="utf-8")

        input_data = memory.load_input_payload(str(f))
        with self.assertRaises(memory.MemoryError) as cm:
            memory.handoff_memory(self.project, input_data)
        self.assertIn("Missing required handoff field", str(cm.exception))

    def test_handoff_dry_run_does_not_modify_file(self):
        memory.initialize(self.project, self.templates, repair=False, dry_run=False)
        orig_handoff = (self.project / ".memory" / "session-handoff.md").read_text(
            encoding="utf-8"
        )

        plan = {"goal": "Dry Goal", "next_step": "Dry Next Step"}
        f = Path(self.temp_dir.name) / "dry_h.json"
        f.write_text(json.dumps(plan), encoding="utf-8")

        input_data = memory.load_input_payload(str(f))
        code, payload = memory.handoff_memory(self.project, input_data, dry_run=True)
        self.assertEqual(code, memory.EXIT_OK)
        self.assertTrue(any("DRY-RUN:" in msg for msg in payload["messages"]))
        self.assertEqual(
            (self.project / ".memory" / "session-handoff.md").read_text(
                encoding="utf-8"
            ),
            orig_handoff,
        )

    # --- Phase 3: Graduate Tests ---

    def test_graduate_valid_multi_topic_promotions_and_resets_handoff(self):
        memory.initialize(self.project, self.templates, repair=False, dry_run=False)
        # Put active state in handoff first
        handoff_plan = {"goal": "Finish user billing feature", "next_step": "Merge PR"}
        hf = Path(self.temp_dir.name) / "hf.json"
        hf.write_text(json.dumps(handoff_plan), encoding="utf-8")
        memory.handoff_memory(self.project, memory.load_input_payload(str(hf)))

        grad_plan = {
            "operation": "graduate",
            "source": "session-handoff.md",
            "promotions": [
                {
                    "topic": "architecture",
                    "title": "Billing Engine",
                    "section": "System Structure & Boundaries",
                    "content": "- `src/billing/...`: Handles Stripe webhook reconciliation and tax calculation.",
                },
                {
                    "topic": "gotchas",
                    "title": "Stripe Webhook Idempotency",
                    "section": "Critical Traps",
                    "content": "- **[Stripe Webhook Idempotency]**: Stripe may retry webhooks up to 72 hours; deduplicate by event_id.",
                },
                {
                    "topic": "domain",
                    "title": "Subscription Lifecycle",
                    "section": "Core Entities & Vocabulary",
                    "content": "- **[Subscription Lifecycle]**: Recurring billing agreement.\n  - _Invariants_: Active status requires valid payment method.",
                },
            ],
            "reset_handoff": True,
        }
        gf = Path(self.temp_dir.name) / "graduate.json"
        gf.write_text(json.dumps(grad_plan), encoding="utf-8")

        input_data = memory.load_input_payload(str(gf))
        code, payload = memory.graduate_memory(
            self.project, input_data, templates=self.templates
        )
        self.assertEqual(code, memory.EXIT_OK)
        self.assertEqual(payload["promotions_count"], 3)

        # Check durable files updated
        arch = (self.project / ".memory" / "architecture.md").read_text(
            encoding="utf-8"
        )
        gotchas = (self.project / ".memory" / "gotchas.md").read_text(encoding="utf-8")
        domain = (self.project / ".memory" / "domain.md").read_text(encoding="utf-8")
        handoff = (self.project / ".memory" / "session-handoff.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("src/billing/...", arch)
        self.assertIn("Stripe Webhook Idempotency", gotchas)
        self.assertIn("Subscription Lifecycle", domain)
        # Handoff was reset to template
        self.assertNotIn("Finish user billing feature", handoff)
        self.assertIn("Session Handoff (Active Workstream)", handoff)

    def test_graduate_preserves_handoff_when_reset_handoff_false(self):
        memory.initialize(self.project, self.templates, repair=False, dry_run=False)
        handoff_plan = {
            "goal": "Partial completion goal",
            "next_step": "Continue next phase",
        }
        hf = Path(self.temp_dir.name) / "hf.json"
        hf.write_text(json.dumps(handoff_plan), encoding="utf-8")
        memory.handoff_memory(self.project, memory.load_input_payload(str(hf)))

        grad_plan = {
            "operation": "graduate",
            "promotions": [
                {
                    "topic": "gotchas",
                    "title": "TLS Handshake Timeout",
                    "content": "- **[TLS Timeout]**: Upstream proxy timeout requires 30s keepalive.",
                }
            ],
            "reset_handoff": False,
        }
        gf = Path(self.temp_dir.name) / "grad_no_reset.json"
        gf.write_text(json.dumps(grad_plan), encoding="utf-8")

        input_data = memory.load_input_payload(str(gf))
        code, _ = memory.graduate_memory(
            self.project, input_data, templates=self.templates
        )
        self.assertEqual(code, memory.EXIT_OK)

        handoff = (self.project / ".memory" / "session-handoff.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Partial completion goal", handoff)

    def test_graduate_duplicate_promotion_rejected_and_rolls_back(self):
        memory.initialize(self.project, self.templates, repair=False, dry_run=False)
        promo = {
            "topic": "architecture",
            "content": "- **[Cache]**: Redis cluster caching layer.",
        }
        # First update architecture
        update_plan = Path(self.temp_dir.name) / "u.json"
        update_plan.write_text(json.dumps(promo), encoding="utf-8")
        memory.update_memory(
            self.project, None, memory.load_input_payload(str(update_plan))
        )

        # Put active goal in handoff
        handoff_plan = {"goal": "Handoff active goal", "next_step": "Next"}
        hf = Path(self.temp_dir.name) / "hf.json"
        hf.write_text(json.dumps(handoff_plan), encoding="utf-8")
        memory.handoff_memory(self.project, memory.load_input_payload(str(hf)))

        # Now graduate identical item
        grad_plan = {
            "promotions": [promo],
            "reset_handoff": True,
        }
        gf = Path(self.temp_dir.name) / "grad_dup.json"
        gf.write_text(json.dumps(grad_plan), encoding="utf-8")

        input_data = memory.load_input_payload(str(gf))
        code, payload = memory.graduate_memory(
            self.project, input_data, templates=self.templates
        )
        self.assertEqual(code, memory.EXIT_VALIDATION)
        self.assertTrue(any("duplicate" in msg.lower() for msg in payload["messages"]))

        # Check handoff was NOT reset
        handoff = (self.project / ".memory" / "session-handoff.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Handoff active goal", handoff)

    def test_graduate_validation_failure_rolls_back_all_files(self):
        memory.initialize(self.project, self.templates, repair=False, dry_run=False)
        orig_arch = (self.project / ".memory" / "architecture.md").read_text(
            encoding="utf-8"
        )
        orig_gotchas = (self.project / ".memory" / "gotchas.md").read_text(
            encoding="utf-8"
        )

        handoff_plan = {"goal": "Active Work", "next_step": "Next"}
        hf = Path(self.temp_dir.name) / "hf.json"
        hf.write_text(json.dumps(handoff_plan), encoding="utf-8")
        memory.handoff_memory(self.project, memory.load_input_payload(str(hf)))

        # Plan with 1 valid promotion and 1 invalid promotion (broken link)
        grad_plan = {
            "promotions": [
                {
                    "topic": "gotchas",
                    "content": "- **[Valid Gotcha]**: Valid text here.",
                },
                {
                    "topic": "architecture",
                    "content": "- Broken: [link](./missing_ref.md)",
                },
            ],
            "reset_handoff": True,
        }
        gf = Path(self.temp_dir.name) / "grad_fail.json"
        gf.write_text(json.dumps(grad_plan), encoding="utf-8")

        input_data = memory.load_input_payload(str(gf))
        code, payload = memory.graduate_memory(
            self.project, input_data, templates=self.templates
        )
        self.assertEqual(code, memory.EXIT_VALIDATION)

        # All files must be rolled back
        self.assertEqual(
            (self.project / ".memory" / "architecture.md").read_text(encoding="utf-8"),
            orig_arch,
        )
        self.assertEqual(
            (self.project / ".memory" / "gotchas.md").read_text(encoding="utf-8"),
            orig_gotchas,
        )
        handoff = (self.project / ".memory" / "session-handoff.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Active Work", handoff)

    def test_graduate_dry_run_does_not_modify_files(self):
        memory.initialize(self.project, self.templates, repair=False, dry_run=False)
        grad_plan = {
            "promotions": [
                {"topic": "domain", "content": "- **[Entity]**: Test entity."},
            ],
            "reset_handoff": True,
        }
        gf = Path(self.temp_dir.name) / "grad_dry.json"
        gf.write_text(json.dumps(grad_plan), encoding="utf-8")

        input_data = memory.load_input_payload(str(gf))
        code, payload = memory.graduate_memory(
            self.project, input_data, dry_run=True, templates=self.templates
        )
        self.assertEqual(code, memory.EXIT_OK)
        self.assertTrue(any("DRY-RUN:" in msg for msg in payload["messages"]))
        self.assertNotIn(
            "Test entity",
            (self.project / ".memory" / "domain.md").read_text(encoding="utf-8"),
        )

    # --- Phase 3: Archive Tests ---

    def test_archive_valid_entry_and_removes_from_source(self):
        memory.initialize(self.project, self.templates, repair=False, dry_run=False)
        # Add an entry to architecture.md
        arch_entry = "- **[Legacy Auth]**: Basic HTTP authentication headers."
        u_plan = {"topic": "architecture", "content": arch_entry}
        uf = Path(self.temp_dir.name) / "u_arch.json"
        uf.write_text(json.dumps(u_plan), encoding="utf-8")
        memory.update_memory(self.project, None, memory.load_input_payload(str(uf)))

        self.assertIn(
            arch_entry,
            (self.project / ".memory" / "architecture.md").read_text(encoding="utf-8"),
        )

        archive_plan = {
            "operation": "archive",
            "source_topic": "architecture",
            "title": "Legacy Auth Deprecated",
            "content": arch_entry,
            "superseded_by": "ADR-0002",
            "reason": "Replaced by OAuth2 PKCE",
            "archive_date": "2026-08-28",
        }
        af = Path(self.temp_dir.name) / "archive_plan.json"
        af.write_text(json.dumps(archive_plan), encoding="utf-8")

        input_data = memory.load_input_payload(str(af))
        code, payload = memory.archive_memory(self.project, None, input_data)
        self.assertEqual(code, memory.EXIT_OK)
        self.assertIn("ARCHIVED:", "\n".join(payload["messages"]))

        # Verify entry is removed from active architecture.md
        arch_after = (self.project / ".memory" / "architecture.md").read_text(
            encoding="utf-8"
        )
        self.assertNotIn(arch_entry, arch_after)

        # Verify archive record created and valid
        archive_dir = self.project / ".memory" / "archive"
        arch_files = list(archive_dir.glob("2026-08-28-architecture-*.md"))
        self.assertEqual(len(arch_files), 1)
        arch_file_content = arch_files[0].read_text(encoding="utf-8")
        self.assertIn("superseded_by: ADR-0002", arch_file_content)
        self.assertIn("source_topic: architecture", arch_file_content)
        self.assertIn(arch_entry, arch_file_content)

    def test_archive_unique_collision_free_filenames(self):
        memory.initialize(self.project, self.templates, repair=False, dry_run=False)
        entry1 = "- **[Trap 1]**: Memory leak in buffer pool."
        entry2 = "- **[Trap 2]**: Memory leak in worker pool."
        (self.project / ".memory" / "gotchas.md").write_text(
            (self.project / ".memory" / "gotchas.md").read_text(encoding="utf-8")
            + f"\n{entry1}\n{entry2}\n",
            encoding="utf-8",
        )

        plan1 = {
            "source_topic": "gotchas",
            "title": "Buffer Pool Leak",
            "content": entry1,
            "superseded_by": "PR-101",
            "archive_date": "2026-08-28",
        }
        f1 = Path(self.temp_dir.name) / "a1.json"
        f1.write_text(json.dumps(plan1), encoding="utf-8")
        code1, _ = memory.archive_memory(
            self.project, None, memory.load_input_payload(str(f1))
        )
        self.assertEqual(code1, memory.EXIT_OK)

        # Same title/date on second archive must generate unique non-colliding filename
        plan2 = {
            "source_topic": "gotchas",
            "title": "Buffer Pool Leak",
            "content": entry2,
            "superseded_by": "PR-102",
            "archive_date": "2026-08-28",
        }
        f2 = Path(self.temp_dir.name) / "a2.json"
        f2.write_text(json.dumps(plan2), encoding="utf-8")
        code2, _ = memory.archive_memory(
            self.project, None, memory.load_input_payload(str(f2))
        )
        self.assertEqual(code2, memory.EXIT_OK)

        archive_files = sorted(
            list((self.project / ".memory" / "archive").glob("*.md"))
        )
        self.assertEqual(len(archive_files), 2)
        self.assertNotEqual(archive_files[0].name, archive_files[1].name)

    def test_archive_missing_source_content_fails(self):
        memory.initialize(self.project, self.templates, repair=False, dry_run=False)
        plan = {
            "source_topic": "architecture",
            "title": "Ghost Entry",
            "content": "- Nonexistent content that is not in the file.",
            "superseded_by": "ADR-0005",
        }
        af = Path(self.temp_dir.name) / "ghost.json"
        af.write_text(json.dumps(plan), encoding="utf-8")

        input_data = memory.load_input_payload(str(af))
        code, payload = memory.archive_memory(self.project, None, input_data)
        self.assertEqual(code, memory.EXIT_VALIDATION)
        self.assertTrue(
            any("not found in source topic file" in msg for msg in payload["messages"])
        )

    def test_archive_invalid_superseded_by_rejected(self):
        memory.initialize(self.project, self.templates, repair=False, dry_run=False)
        plan = {
            "source_topic": "architecture",
            "content": "Some text",
            "superseded_by": "self",  # invalid self-supersession
        }
        af = Path(self.temp_dir.name) / "bad_sup.json"
        af.write_text(json.dumps(plan), encoding="utf-8")

        input_data = memory.load_input_payload(str(af))
        with self.assertRaises(memory.MemoryError) as cm:
            memory.archive_memory(self.project, None, input_data)
        self.assertIn("Invalid supersession", str(cm.exception))

    def test_archive_dry_run_does_not_modify_files(self):
        memory.initialize(self.project, self.templates, repair=False, dry_run=False)
        entry = "- **[Active Invariant]**: Database reads must be cached."
        (self.project / ".memory" / "architecture.md").write_text(
            (self.project / ".memory" / "architecture.md").read_text(encoding="utf-8")
            + f"\n{entry}\n",
            encoding="utf-8",
        )
        plan = {
            "source_topic": "architecture",
            "content": entry,
            "superseded_by": "ADR-0004",
        }
        af = Path(self.temp_dir.name) / "dry_arc.json"
        af.write_text(json.dumps(plan), encoding="utf-8")

        input_data = memory.load_input_payload(str(af))
        code, payload = memory.archive_memory(
            self.project, None, input_data, dry_run=True
        )
        self.assertEqual(code, memory.EXIT_OK)
        self.assertTrue(any("DRY-RUN:" in msg for msg in payload["messages"]))
        self.assertIn(
            entry,
            (self.project / ".memory" / "architecture.md").read_text(encoding="utf-8"),
        )
        self.assertEqual(
            len(list((self.project / ".memory" / "archive").glob("*.md"))), 0
        )

    # --- Phase 3: Concurrency & Lock Safety Tests ---

    def test_concurrent_mutation_lock_safety(self):
        memory.initialize(self.project, self.templates, repair=False, dry_run=False)
        target = self.project / ".memory"

        # Hold a lock artificially
        lock_file = target / ".memory.lock"
        lock_file.write_text(
            f"pid={os.getpid()}\ncreated_at={int(time.time())}\n", encoding="utf-8"
        )

        # Now try to run an update with short lock timeout (should fail with locked error)
        plan = {"topic": "architecture", "content": "- Entry"}
        pf = Path(self.temp_dir.name) / "lock_plan.json"
        pf.write_text(json.dumps(plan), encoding="utf-8")

        input_data = memory.load_input_payload(str(pf))
        orig_timeout = memory.LOCK_TIMEOUT_SECONDS
        try:
            memory.LOCK_TIMEOUT_SECONDS = 0.1
            with self.assertRaises(memory.MemoryError) as cm:
                memory.update_memory(self.project, None, input_data)
            self.assertIn("locked", str(cm.exception).lower())
        finally:
            memory.LOCK_TIMEOUT_SECONDS = orig_timeout
            lock_file.unlink(missing_ok=True)

    def test_mutation_reads_state_after_lock_acquisition(self):
        memory.initialize(self.project, self.templates, repair=False, dry_run=False)
        target_file = self.project / ".memory" / "gotchas.md"

        # Simulate another writer modifying the file right before lock is acquired
        plan = {
            "topic": "gotchas",
            "content": "- **[Trap X]**: Avoid X.",
        }
        pf = Path(self.temp_dir.name) / "trap_plan.json"
        pf.write_text(json.dumps(plan), encoding="utf-8")

        # First update modifies gotchas.md
        input_data = memory.load_input_payload(str(pf))
        code1, _ = memory.update_memory(self.project, None, input_data)
        self.assertEqual(code1, memory.EXIT_OK)

        # Second update with same content re-reads under lock and detects duplicate
        code2, payload2 = memory.update_memory(self.project, None, input_data)
        self.assertEqual(code2, memory.EXIT_VALIDATION)
        self.assertTrue(any("duplicate" in msg.lower() for msg in payload2["messages"]))

    def test_cli_dispatch_and_json_formatting(self):
        memory.initialize(self.project, self.templates, repair=False, dry_run=False)
        plan = {
            "topic": "gotchas",
            "title": "CLI Test Gotcha",
            "content": "- **[CLI Test]**: Validating JSON format CLI dispatch.",
        }
        pf = Path(self.temp_dir.name) / "cli_plan.json"
        pf.write_text(json.dumps(plan), encoding="utf-8")

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = memory.main(
                ["--format", "json", "update", str(self.project), "--input", str(pf)]
            )
        self.assertEqual(code, memory.EXIT_OK)
        parsed = json.loads(buffer.getvalue())
        self.assertEqual(parsed["operation"], "update")
        self.assertIn("modified_files", parsed)


    def test_insert_into_topic_places_content_under_named_section(self):
        original = (
            "# Title\n\n"
            "## First Section\n\n- existing first\n\n"
            "## Second Section\n\n- existing second\n"
        )
        result = memory.insert_into_topic(original, "- inserted", "First Section")
        self.assertLess(result.index("- inserted"), result.index("## Second Section"))
        self.assertGreater(result.index("- inserted"), result.index("- existing first"))

    def test_update_with_section_inserts_before_next_heading(self):
        memory.initialize(self.project, self.templates, repair=False, dry_run=False)
        plan = {
            "operation": "update",
            "topic": "architecture",
            "section": "Key Architectural Decisions",
            "content": "- **[ADR-9999 Placement Probe]**: Must land in this section.",
        }
        plan_file = Path(self.temp_dir.name) / "section_plan.json"
        plan_file.write_text(json.dumps(plan), encoding="utf-8")

        code, _ = memory.update_memory(
            self.project, None, memory.load_input_payload(str(plan_file))
        )
        self.assertEqual(code, memory.EXIT_OK)
        content = (self.project / ".memory" / "architecture.md").read_text(
            encoding="utf-8"
        )
        entry = content.index("ADR-9999 Placement Probe")
        self.assertGreater(entry, content.index("## Key Architectural Decisions"))
        self.assertLess(entry, content.index("## Permanent Design Invariants"))

    def test_archive_does_not_leave_blank_line_between_list_items(self):
        memory.initialize(self.project, self.templates, repair=False, dry_run=False)
        domain_file = self.project / ".memory" / "domain.md"
        entries = "- **[Alpha]**: first.\n- **[Beta]**: second.\n- **[Gamma]**: third."
        domain_file.write_text(
            domain_file.read_text(encoding="utf-8").rstrip() + "\n\n" + entries + "\n",
            encoding="utf-8",
        )
        archive_plan = {
            "operation": "archive",
            "source_topic": "domain",
            "title": "Beta retired",
            "content": "- **[Beta]**: second.",
            "superseded_by": "ADR-0002",
            "archive_date": "2026-09-26",
        }
        af = Path(self.temp_dir.name) / "archive_beta.json"
        af.write_text(json.dumps(archive_plan), encoding="utf-8")

        code, _ = memory.archive_memory(
            self.project, None, memory.load_input_payload(str(af))
        )
        self.assertEqual(code, memory.EXIT_OK)
        after = domain_file.read_text(encoding="utf-8")
        self.assertNotIn("[Beta]", after)
        self.assertIn("- **[Alpha]**: first.\n- **[Gamma]**: third.", after)


    def test_detect_conflict_matches_title_used_as_heading(self):
        existing = "# Topic\n\n## Billing Engine\n\n- Handles invoices.\n"
        kind, _ = memory.detect_duplicate_or_conflict(
            existing, "Billing Engine", "- Billing Engine now handles refunds."
        )
        self.assertEqual(kind, "conflict")
        kind, _ = memory.detect_duplicate_or_conflict(
            existing, "Search Service", "- New search entry."
        )
        self.assertIsNone(kind)


if __name__ == "__main__":
    unittest.main()
