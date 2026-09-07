import importlib.util
import json
import os
import stat
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "workspace_guard", ROOT / "scripts" / "workspace_guard.py"
)
workspace_guard = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules["workspace_guard"] = workspace_guard
SPEC.loader.exec_module(workspace_guard)


class ComputeDesiredModeTests(unittest.TestCase):
    """Tests for compute_desired_mode (write bit toggling)."""

    def test_make_writable_adds_owner_write(self):
        """Writable mode includes owner write bit."""
        current = 0o444
        desired = workspace_guard.compute_desired_mode(current, writable=True)
        self.assertTrue(desired & stat.S_IWUSR)
        # Other write bits should not be added
        self.assertFalse(desired & stat.S_IWGRP)
        self.assertFalse(desired & stat.S_IWOTH)

    def test_make_readable_strips_write_bits(self):
        """Readable mode removes all write bits."""
        current = 0o777
        desired = workspace_guard.compute_desired_mode(current, writable=False)
        self.assertFalse(desired & stat.S_IWUSR)
        self.assertFalse(desired & stat.S_IWGRP)
        self.assertFalse(desired & stat.S_IWOTH)
        # Read bits should be preserved
        self.assertTrue(desired & stat.S_IRUSR)
        self.assertTrue(desired & stat.S_IRGRP)
        self.assertTrue(desired & stat.S_IROTH)

    def test_executable_bit_preserved(self):
        """Execute bits are never stripped."""
        current = 0o755
        desired_ro = workspace_guard.compute_desired_mode(current, writable=False)
        desired_rw = workspace_guard.compute_desired_mode(current, writable=True)
        # Execute bits should be preserved in both cases
        self.assertTrue(desired_ro & stat.S_IXUSR)
        self.assertTrue(desired_rw & stat.S_IXUSR)

    def test_idempotent_writable(self):
        """Making writable mode twice is idempotent."""
        current = 0o555
        desired1 = workspace_guard.compute_desired_mode(current, writable=True)
        desired2 = workspace_guard.compute_desired_mode(desired1, writable=True)
        self.assertEqual(stat.S_IMODE(desired1), stat.S_IMODE(desired2))

    def test_idempotent_readable(self):
        """Making readable mode twice is idempotent."""
        current = 0o755
        desired1 = workspace_guard.compute_desired_mode(current, writable=False)
        desired2 = workspace_guard.compute_desired_mode(desired1, writable=False)
        self.assertEqual(stat.S_IMODE(desired1), stat.S_IMODE(desired2))


class IsStaleHolderTests(unittest.TestCase):
    """Tests for is_stale_holder (staleness detection)."""

    def test_fresh_holder_not_stale(self):
        """A recent holder is not stale."""
        now = time.time()
        holder = {
            "harness": "claude",
            "activated_at": now - 100,
            "hostname": "myhost",
            "pid": os.getpid(),
        }
        self.assertFalse(workspace_guard.is_stale_holder(holder, now))

    def test_expired_holder_is_stale(self):
        """A holder older than 12 hours is stale."""
        now = time.time()
        old_time = now - (13 * 60 * 60)
        holder = {
            "harness": "claude",
            "activated_at": old_time,
            "hostname": "myhost",
            "pid": os.getpid(),
        }
        self.assertTrue(workspace_guard.is_stale_holder(holder, now))

    def test_same_host_with_live_pid_not_stale(self):
        """A holder on the same host with a live PID is not stale."""
        now = time.time()
        holder = {
            "harness": "claude",
            "activated_at": now - 100,
            "hostname": os.uname().nodename,
            "pid": os.getpid(),
        }
        self.assertFalse(workspace_guard.is_stale_holder(holder, now))

    def test_same_host_with_dead_pid_trusted_if_fresh(self):
        """A recent holder on same host with dead PID is trusted (harness session keeps it alive)."""
        now = time.time()
        holder = {
            "harness": "claude",
            "activated_at": now - 100,
            "hostname": os.uname().nodename,
            "pid": 999999,  # Dead PID
        }
        # Should NOT be stale because activation is recent
        self.assertFalse(workspace_guard.is_stale_holder(holder, now))

    def test_different_host_with_dead_pid_is_stale(self):
        """A holder on a different host is checked for PID staleness."""
        now = time.time()
        holder = {
            "harness": "claude",
            "activated_at": now - 100,
            "hostname": "other-host",
            "pid": 999999,  # Dead PID
        }
        # Should be stale because we can't verify PID on different host
        self.assertTrue(workspace_guard.is_stale_holder(holder, now))


class PruneStaleHoldersTests(unittest.TestCase):
    """Tests for prune_stale_holders."""

    def test_remove_stale_only(self):
        """Stale holders are removed; fresh are kept."""
        now = time.time()
        fresh = {
            "harness": "claude",
            "activated_at": now - 100,
            "hostname": os.uname().nodename,
            "pid": os.getpid(),
        }
        stale = {
            "harness": "claude",
            "activated_at": now - (13 * 60 * 60),
            "hostname": os.uname().nodename,
            "pid": os.getpid(),
        }
        result = workspace_guard.prune_stale_holders([fresh, stale], now)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], fresh)


class MakeHolderTests(unittest.TestCase):
    """Tests for make_holder."""

    def test_make_holder_creates_valid_record(self):
        """make_holder creates a record with all required fields."""
        holder = workspace_guard.make_holder("claude", "session-123")
        self.assertEqual(holder["harness"], "claude")
        self.assertEqual(holder["session_id"], "session-123")
        self.assertIn("hostname", holder)
        self.assertIn("user", holder)
        self.assertIn("pid", holder)
        self.assertIn("activated_at", holder)
        self.assertEqual(holder["pid"], os.getpid())

    def test_make_holder_with_none_session_id(self):
        """make_holder accepts None as session_id."""
        holder = workspace_guard.make_holder("manual", None)
        self.assertIsNone(holder["session_id"])


class ComputeActivationTests(unittest.TestCase):
    """Tests for compute_activation."""

    def test_activation_from_empty_lock(self):
        """Activating an empty lock creates a holder and needs unlock."""
        new_record, needs_unlock = workspace_guard.compute_activation(
            None, "claude", "session-1"
        )
        self.assertEqual(new_record["status"], "active")
        self.assertEqual(len(new_record["holders"]), 1)
        self.assertTrue(needs_unlock)

    def test_same_harness_append_holder(self):
        """Activating the same harness appends a holder."""
        record = {
            "status": "active",
            "holders": [workspace_guard.make_holder("claude", "session-1")],
        }
        new_record, needs_unlock = workspace_guard.compute_activation(
            record, "claude", "session-2"
        )
        self.assertEqual(len(new_record["holders"]), 2)
        self.assertFalse(needs_unlock)  # Tree already had holders

    def test_different_harness_raises_without_force(self):
        """Different harness raises GuardError without --force."""
        record = {
            "status": "active",
            "holders": [workspace_guard.make_holder("codex", "session-1")],
        }
        with self.assertRaises(workspace_guard.GuardError):
            workspace_guard.compute_activation(record, "claude", "session-1")

    def test_force_overrides_different_harness(self):
        """--force clears existing holders from different harness."""
        record = {
            "status": "active",
            "holders": [workspace_guard.make_holder("codex", "session-1")],
        }
        new_record, needs_unlock = workspace_guard.compute_activation(
            record, "claude", "session-1", force=True
        )
        self.assertEqual(len(new_record["holders"]), 1)
        self.assertEqual(new_record["holders"][0]["harness"], "claude")
        # Tree was already unlocked by the previous holder, so no unlock needed
        self.assertFalse(needs_unlock)


class ComputeDeactivationTests(unittest.TestCase):
    """Tests for compute_deactivation."""

    def test_deactivate_by_session_id(self):
        """Deactivating by session_id removes only that holder."""
        record = {
            "status": "active",
            "holders": [
                workspace_guard.make_holder("claude", "session-1"),
                workspace_guard.make_holder("claude", "session-2"),
            ],
        }
        new_record, needs_lock = workspace_guard.compute_deactivation(
            record, session_id="session-1"
        )
        self.assertEqual(len(new_record["holders"]), 1)
        self.assertEqual(new_record["holders"][0]["session_id"], "session-2")
        self.assertFalse(needs_lock)  # Still has holder

    def test_deactivate_by_harness(self):
        """Deactivating by harness removes all holders of that harness."""
        record = {
            "status": "active",
            "holders": [
                workspace_guard.make_holder("claude", "session-1"),
                workspace_guard.make_holder("codex", "session-1"),
            ],
        }
        new_record, needs_lock = workspace_guard.compute_deactivation(
            record, harness="claude"
        )
        self.assertEqual(len(new_record["holders"]), 1)
        self.assertEqual(new_record["holders"][0]["harness"], "codex")
        self.assertFalse(needs_lock)  # Still has holder

    def test_deactivate_bare_clears_all(self):
        """Bare deactivate clears all holders."""
        record = {
            "status": "active",
            "holders": [
                workspace_guard.make_holder("claude", "session-1"),
                workspace_guard.make_holder("codex", "session-1"),
            ],
        }
        new_record, needs_lock = workspace_guard.compute_deactivation(record)
        self.assertEqual(len(new_record["holders"]), 0)
        self.assertEqual(new_record["status"], "locked")
        self.assertTrue(needs_lock)

    def test_deactivate_last_holder_locks(self):
        """Removing the last holder locks the tree."""
        record = {
            "status": "active",
            "holders": [workspace_guard.make_holder("claude", "session-1")],
        }
        new_record, needs_lock = workspace_guard.compute_deactivation(
            record, session_id="session-1"
        )
        self.assertTrue(needs_lock)
        self.assertEqual(new_record["status"], "locked")


class ApplyLockStateTests(unittest.TestCase):
    """Integration tests for apply_lock_state with real files."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        # Create test files
        (self.temp_path / "file.txt").write_text("test")
        (self.temp_path / "subdir").mkdir()
        (self.temp_path / "subdir" / "nested.txt").write_text("nested")
        # Create an executable script
        script = self.temp_path / "script.sh"
        script.write_text("#!/bin/bash\necho hello")
        os.chmod(script, 0o755)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_lock_strips_write_bits(self):
        """Locking strips write bits."""
        counts = workspace_guard.apply_lock_state(self.temp_path, writable=False)
        file_mode = (self.temp_path / "file.txt").stat().st_mode
        self.assertFalse(file_mode & stat.S_IWUSR)

    def test_unlock_restores_write_bits(self):
        """Unlocking restores write bits."""
        workspace_guard.apply_lock_state(self.temp_path, writable=False)
        counts = workspace_guard.apply_lock_state(self.temp_path, writable=True)
        file_mode = (self.temp_path / "file.txt").stat().st_mode
        self.assertTrue(file_mode & stat.S_IWUSR)

    def test_executable_bit_preserved_when_locked(self):
        """Execute bits are preserved when locking."""
        script = self.temp_path / "script.sh"
        original_mode = script.stat().st_mode
        workspace_guard.apply_lock_state(self.temp_path, writable=False)
        locked_mode = script.stat().st_mode
        # Execute bit should still be set
        self.assertTrue(locked_mode & stat.S_IXUSR)

    def test_exempt_paths_never_change(self):
        """Exempt paths are never modified."""
        exempt_file = self.temp_path / "exempt.txt"
        exempt_file.write_text("exempt")
        os.chmod(exempt_file, 0o644)
        original_mode = exempt_file.stat().st_mode

        workspace_guard.apply_lock_state(
            self.temp_path, writable=False, exempt={exempt_file}
        )
        after_mode = exempt_file.stat().st_mode
        self.assertEqual(
            stat.S_IMODE(original_mode), stat.S_IMODE(after_mode)
        )

    def test_idempotent_lock_unlock(self):
        """Locking/unlocking twice is idempotent."""
        workspace_guard.apply_lock_state(self.temp_path, writable=False)
        counts1 = workspace_guard.apply_lock_state(self.temp_path, writable=False)
        # Second call should report no changes
        self.assertEqual(counts1["changed"], 0)
        self.assertGreater(counts1["unchanged"], 0)


class ReadWriteLockTests(unittest.TestCase):
    """Tests for read_lock and write_lock."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.lock_file = Path(self.temp_dir.name) / "test.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_read_nonexistent_returns_none(self):
        """Reading a nonexistent lock file returns None."""
        result = workspace_guard.read_lock(self.lock_file)
        self.assertIsNone(result)

    def test_write_and_read_roundtrip(self):
        """Write and read produce the same data."""
        record = {"status": "active", "holders": []}
        workspace_guard.write_lock(self.lock_file, record)
        result = workspace_guard.read_lock(self.lock_file)
        self.assertEqual(result, record)

    def test_corrupt_json_raises(self):
        """Corrupt JSON raises GuardError."""
        self.lock_file.write_text("{not json")
        with self.assertRaises(workspace_guard.GuardError):
            workspace_guard.read_lock(self.lock_file)


class CmdCheckTests(unittest.TestCase):
    """Tests for cmd_check JSON output."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.lock_file = Path(self.temp_dir.name) / "lock.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_check_unlocked_outputs_allow(self):
        """cmd_check outputs allow when holders exist."""
        record = {
            "status": "active",
            "holders": [workspace_guard.make_holder("claude", "session-1")],
        }
        workspace_guard.write_lock(self.lock_file, record)

        args = mock.Mock(lock_file=self.lock_file, repo_root=Path("."))
        with mock.patch("sys.stdout", new_callable=lambda: mock.Mock()) as mock_stdout:
            import io

            captured_output = io.StringIO()
            with mock.patch("builtins.print", lambda x: captured_output.write(str(x))):
                workspace_guard.cmd_check(args)
                output_str = captured_output.getvalue()
                output_json = json.loads(output_str)
                self.assertEqual(
                    output_json["hookSpecificOutput"]["permissionDecision"],
                    "allow",
                )

    def test_check_locked_outputs_deny(self):
        """cmd_check outputs deny when no holders."""
        import io

        args = mock.Mock(lock_file=self.lock_file, repo_root=Path("."))
        captured_output = io.StringIO()
        with mock.patch("builtins.print", lambda x: captured_output.write(str(x))):
            workspace_guard.cmd_check(args)
            output_str = captured_output.getvalue()
            output_json = json.loads(output_str)
            self.assertEqual(
                output_json["hookSpecificOutput"]["permissionDecision"],
                "deny",
            )


if __name__ == "__main__":
    unittest.main()
