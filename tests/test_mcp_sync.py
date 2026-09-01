import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "mcp_sync", ROOT / "scripts" / "mcp_sync.py"
)
mcp_sync = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules["mcp_sync"] = mcp_sync
SPEC.loader.exec_module(mcp_sync)


STDIO_SERVER = {
    "name": "example",
    "transport": "stdio",
    "command": "npx",
    "args": ["-y", "@example/mcp-server"],
    "env": {"FOO": "bar"},
}

HTTP_SERVER = {
    "name": "remote-example",
    "transport": "http",
    "url": "https://example.com/mcp",
}


class ManifestLoadingTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.manifest_path = Path(self.temp_dir.name) / "servers.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    def _write(self, data):
        self.manifest_path.write_text(json.dumps(data), encoding="utf-8")

    def test_missing_manifest_raises(self):
        with self.assertRaises(mcp_sync.ManifestError):
            mcp_sync.load_manifest(self.manifest_path)

    def test_empty_servers_list_is_valid(self):
        self._write({"servers": []})
        self.assertEqual(mcp_sync.load_manifest(self.manifest_path), [])

    def test_invalid_json_raises(self):
        self.manifest_path.write_text("{not json", encoding="utf-8")
        with self.assertRaises(mcp_sync.ManifestError):
            mcp_sync.load_manifest(self.manifest_path)

    def test_duplicate_names_rejected(self):
        self._write({"servers": [STDIO_SERVER, STDIO_SERVER]})
        with self.assertRaises(mcp_sync.ManifestError):
            mcp_sync.load_manifest(self.manifest_path)

    def test_stdio_without_command_rejected(self):
        bad = {"name": "x", "transport": "stdio"}
        self._write({"servers": [bad]})
        with self.assertRaises(mcp_sync.ManifestError):
            mcp_sync.load_manifest(self.manifest_path)

    def test_http_without_url_rejected(self):
        bad = {"name": "x", "transport": "http"}
        self._write({"servers": [bad]})
        with self.assertRaises(mcp_sync.ManifestError):
            mcp_sync.load_manifest(self.manifest_path)

    def test_invalid_transport_rejected(self):
        bad = {"name": "x", "transport": "carrier-pigeon", "command": "y"}
        self._write({"servers": [bad]})
        with self.assertRaises(mcp_sync.ManifestError):
            mcp_sync.load_manifest(self.manifest_path)

    def test_valid_manifest_loads(self):
        self._write({"servers": [STDIO_SERVER, HTTP_SERVER]})
        servers = mcp_sync.load_manifest(self.manifest_path)
        self.assertEqual(len(servers), 2)


class HarnessFilterTests(unittest.TestCase):
    def test_no_harnesses_key_means_all(self):
        result = mcp_sync.servers_for_harness([STDIO_SERVER], "claude")
        self.assertEqual(result, [STDIO_SERVER])

    def test_explicit_harnesses_filters(self):
        scoped = {**STDIO_SERVER, "harnesses": ["opencode"]}
        self.assertEqual(mcp_sync.servers_for_harness([scoped], "claude"), [])
        self.assertEqual(mcp_sync.servers_for_harness([scoped], "opencode"), [scoped])


class TransformTests(unittest.TestCase):
    def test_claude_stdio_transform(self):
        entry = mcp_sync._claude_transform(STDIO_SERVER)
        self.assertEqual(entry["command"], "npx")
        self.assertEqual(entry["args"], ["-y", "@example/mcp-server"])
        self.assertEqual(entry["env"], {"FOO": "bar"})
        self.assertEqual(entry["_managedBy"], "ai-skills")

    def test_claude_http_transform(self):
        entry = mcp_sync._claude_transform(HTTP_SERVER)
        self.assertEqual(entry["type"], "http")
        self.assertEqual(entry["url"], "https://example.com/mcp")

    def test_opencode_stdio_transform_merges_command_and_args(self):
        entry = mcp_sync._opencode_transform(STDIO_SERVER)
        self.assertEqual(entry["type"], "local")
        self.assertEqual(entry["command"], ["npx", "-y", "@example/mcp-server"])
        self.assertEqual(entry["environment"], {"FOO": "bar"})

    def test_opencode_remote_transform(self):
        entry = mcp_sync._opencode_transform(HTTP_SERVER)
        self.assertEqual(entry["type"], "remote")
        self.assertEqual(entry["url"], "https://example.com/mcp")


class ComputeSyncTests(unittest.TestCase):
    def test_add_new_entry(self):
        new_config, changes = mcp_sync.compute_sync({}, "mcpServers", {"a": {"_managedBy": "ai-skills"}})
        self.assertEqual(changes["a"], "ADD")
        self.assertEqual(new_config["mcpServers"]["a"]["_managedBy"], "ai-skills")

    def test_unchanged_entry(self):
        entry = {"_managedBy": "ai-skills", "command": "x"}
        existing = {"mcpServers": {"a": entry}}
        new_config, changes = mcp_sync.compute_sync(existing, "mcpServers", {"a": entry})
        self.assertEqual(changes["a"], "UNCHANGED")

    def test_update_entry(self):
        existing = {"mcpServers": {"a": {"_managedBy": "ai-skills", "command": "old"}}}
        new_config, changes = mcp_sync.compute_sync(
            existing, "mcpServers", {"a": {"_managedBy": "ai-skills", "command": "new"}}
        )
        self.assertEqual(changes["a"], "UPDATE")
        self.assertEqual(new_config["mcpServers"]["a"]["command"], "new")

    def test_remove_stale_managed_entry(self):
        existing = {"mcpServers": {"a": {"_managedBy": "ai-skills", "command": "x"}}}
        new_config, changes = mcp_sync.compute_sync(existing, "mcpServers", {})
        self.assertEqual(changes["a"], "REMOVE")
        self.assertNotIn("a", new_config["mcpServers"])

    def test_never_touches_unmanaged_entry_with_same_name(self):
        hand_added = {"command": "hand-added", "note": "do not touch"}
        existing = {"mcpServers": {"a": hand_added}}
        new_config, changes = mcp_sync.compute_sync(
            existing, "mcpServers", {"a": {"_managedBy": "ai-skills", "command": "managed"}}
        )
        self.assertEqual(changes["a"], "SKIPPED (unmanaged entry with same name already exists)")
        self.assertEqual(new_config["mcpServers"]["a"], hand_added)

    def test_unmanaged_entries_with_other_names_untouched(self):
        hand_added = {"command": "hand-added"}
        existing = {"mcpServers": {"other": hand_added}}
        new_config, changes = mcp_sync.compute_sync(
            existing, "mcpServers", {"a": {"_managedBy": "ai-skills", "command": "x"}}
        )
        self.assertEqual(new_config["mcpServers"]["other"], hand_added)
        self.assertEqual(new_config["mcpServers"]["a"]["_managedBy"], "ai-skills")

    def test_preserves_unrelated_top_level_keys(self):
        existing = {"mcpServers": {}, "someOtherAppSetting": {"nested": True}}
        new_config, _ = mcp_sync.compute_sync(existing, "mcpServers", {"a": {"_managedBy": "ai-skills"}})
        self.assertEqual(new_config["someOtherAppSetting"], {"nested": True})


class SyncHarnessDryRunTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = Path(self.temp_dir.name) / "claude.json"
        self._orig_registry_entry = mcp_sync.HARNESS_REGISTRY["claude"]
        mcp_sync.HARNESS_REGISTRY["claude"] = {
            **self._orig_registry_entry,
            "config_path": self.config_path,
        }

    def tearDown(self):
        mcp_sync.HARNESS_REGISTRY["claude"] = self._orig_registry_entry
        self.temp_dir.cleanup()

    def test_dry_run_does_not_write_file(self):
        result = mcp_sync.sync_harness("claude", [STDIO_SERVER], Path("unused"), apply=False)
        self.assertFalse(result["applied"])
        self.assertFalse(self.config_path.exists())
        self.assertEqual(result["changes"]["example"], "ADD")

    def test_apply_writes_file_and_backs_up_existing(self):
        self.config_path.write_text(json.dumps({"mcpServers": {}}), encoding="utf-8")
        result = mcp_sync.sync_harness("claude", [STDIO_SERVER], Path("unused"), apply=True)
        self.assertTrue(result["applied"])
        self.assertIsNotNone(result["backup_path"])
        self.assertTrue(Path(result["backup_path"]).exists())
        written = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.assertEqual(written["mcpServers"]["example"]["command"], "npx")

    def test_apply_with_no_changes_does_not_write(self):
        # First sync writes the managed entry; second sync with identical
        # manifest should be a no-op (no new backup, file untouched).
        mcp_sync.sync_harness("claude", [STDIO_SERVER], Path("unused"), apply=True)
        mtime_before = self.config_path.stat().st_mtime
        result = mcp_sync.sync_harness("claude", [STDIO_SERVER], Path("unused"), apply=True)
        self.assertFalse(result["applied"])
        self.assertEqual(self.config_path.stat().st_mtime, mtime_before)

    def test_skipped_name_collision_does_not_trigger_a_write(self):
        # A hand-added, unmanaged entry sharing a name with a manifest server
        # must be left alone -- and, critically, must not itself count as a
        # reason to rewrite/back up an otherwise-unchanged config file.
        hand_added = {"command": "hand-added-by-user"}
        self.config_path.write_text(
            json.dumps({"mcpServers": {"example": hand_added}}), encoding="utf-8"
        )
        mtime_before = self.config_path.stat().st_mtime
        result = mcp_sync.sync_harness("claude", [STDIO_SERVER], Path("unused"), apply=True)
        self.assertFalse(result["applied"])
        self.assertIsNone(result["backup_path"])
        self.assertEqual(self.config_path.stat().st_mtime, mtime_before)
        untouched = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.assertEqual(untouched["mcpServers"]["example"], hand_added)


class ResolveServerEnvTests(unittest.TestCase):
    def test_server_without_env_passes_through_unchanged(self):
        server = {"name": "x", "transport": "stdio", "command": "npx"}
        self.assertIs(mcp_sync.resolve_server_env(server), server)

    def test_non_placeholder_value_passes_through(self):
        server = {**STDIO_SERVER, "env": {"LOG_LEVEL": "debug"}}
        resolved = mcp_sync.resolve_server_env(server)
        self.assertEqual(resolved["env"]["LOG_LEVEL"], "debug")

    def test_placeholder_resolved_from_environment(self):
        server = {**STDIO_SERVER, "env": {"TOKEN": "${AI_SKILLS_TEST_TOKEN}"}}
        with mock.patch.dict("os.environ", {"AI_SKILLS_TEST_TOKEN": "secret-value"}):
            resolved = mcp_sync.resolve_server_env(server)
        self.assertEqual(resolved["env"]["TOKEN"], "secret-value")

    def test_missing_placeholder_var_raises(self):
        server = {**STDIO_SERVER, "env": {"TOKEN": "${AI_SKILLS_DEFINITELY_UNSET_VAR}"}}
        with self.assertRaises(mcp_sync.ManifestError):
            mcp_sync.resolve_server_env(server)

    def test_original_server_dict_never_mutated(self):
        server = {**STDIO_SERVER, "env": {"TOKEN": "${AI_SKILLS_TEST_TOKEN}"}}
        with mock.patch.dict("os.environ", {"AI_SKILLS_TEST_TOKEN": "secret-value"}):
            mcp_sync.resolve_server_env(server)
        self.assertEqual(server["env"]["TOKEN"], "${AI_SKILLS_TEST_TOKEN}")


class SecretsNeverWrittenToHarnessConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = Path(self.temp_dir.name) / "claude.json"
        self._orig_registry_entry = mcp_sync.HARNESS_REGISTRY["claude"]
        mcp_sync.HARNESS_REGISTRY["claude"] = {
            **self._orig_registry_entry,
            "config_path": self.config_path,
        }

    def tearDown(self):
        mcp_sync.HARNESS_REGISTRY["claude"] = self._orig_registry_entry
        self.temp_dir.cleanup()

    def test_written_config_has_resolved_value_not_placeholder(self):
        server = {**STDIO_SERVER, "env": {"TOKEN": "${AI_SKILLS_TEST_TOKEN}"}}
        with mock.patch.dict("os.environ", {"AI_SKILLS_TEST_TOKEN": "real-secret"}):
            mcp_sync.sync_harness("claude", [server], Path("unused"), apply=True)
        written = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.assertEqual(written["mcpServers"]["example"]["env"]["TOKEN"], "real-secret")
        self.assertNotIn("${AI_SKILLS_TEST_TOKEN}", self.config_path.read_text(encoding="utf-8"))

    def test_dry_run_still_requires_var_to_be_set(self):
        server = {**STDIO_SERVER, "env": {"TOKEN": "${AI_SKILLS_DEFINITELY_UNSET_VAR}"}}
        with self.assertRaises(mcp_sync.ManifestError):
            mcp_sync.sync_harness("claude", [server], Path("unused"), apply=False)


if __name__ == "__main__":
    unittest.main()
