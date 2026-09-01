# MCP Multi-Harness Sync

Canonical, harness-agnostic MCP server declarations, synced out to each agent
harness's own config format the same way `skills/` is synced out via
`setup.sh`'s `HARNESS_REGISTRY`. See ADR 0003.

## Source of truth

`mcp/servers.json` is the single canonical list. Each entry:

```json
{
  "name": "example-server",
  "transport": "stdio",
  "command": "npx",
  "args": ["-y", "@example/mcp-server"],
  "env": {},
  "harnesses": ["claude", "opencode", "antigravity"]
}
```

- `transport`: `"stdio"` (local process) or `"http"` / `"sse"` (remote — use `url` instead of `command`/`args`).
- `harnesses`: which harnesses to sync this server to. Omit to sync to all registered harnesses.

## Secrets: never commit a real value

`mcp/servers.json` is git-tracked and shared across machines. **Never put a real API key, token, or password in `env`.** Instead reference it by name with `${VAR_NAME}`:

```json
{
  "name": "github",
  "transport": "stdio",
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-github"],
  "env": { "GITHUB_TOKEN": "${GITHUB_TOKEN}" }
}
```

`scripts/mcp_sync.py` resolves `${VAR_NAME}` from the local shell environment only at sync time, and only in memory — the committed manifest never contains the real value, and `sync`/`list` never print resolved secrets back out. If the variable isn't set locally, `sync` fails with a clear error instead of writing an empty or literal `"${VAR_NAME}"` string into your harness config. Non-placeholder `env` values (e.g. `"LOG_LEVEL": "debug"`) pass through unchanged — the placeholder rule only applies to values you actually want kept out of git.

## Sync destinations (per harness)

| Harness | Config file | Key |
| :--- | :--- | :--- |
| Claude Code | `~/.claude.json` | top-level `mcpServers` |
| OpenCode | `~/.config/opencode/opencode.json` | top-level `mcp` |
| Google Antigravity | `~/.gemini/config/mcp.json` | top-level `mcpServers` |

These are **best-effort conventions**, not verified against every harness's live schema — the same way this repo's existing `~/.gemini/config/skills` and `~/.gemini/config/rules/memory.md` paths are this project's own convention rather than a documented Google spec. Verify against your installed harness version before relying on `--apply`.

## Safety model

`scripts/mcp_sync.py` never overwrites a harness config file wholesale:

1. It only ever touches entries under the destination key that carry `"_managedBy": "ai-skills"` — hand-added servers in the same file are left untouched.
2. A managed entry no longer present in `mcp/servers.json` is removed on sync (so removing a server from the manifest and re-syncing cleans it up), but only if it still carries the `_managedBy` tag.
3. Every write is preceded by a timestamped backup of the target file (`<file>.bak.<timestamp>`).
4. Default mode is `--dry-run` (prints the diff, writes nothing). Real writes require `--apply`.

## Usage

```bash
# Preview what would change across all harnesses (default; no writes)
python3 scripts/mcp_sync.py sync --all

# Apply for real, one harness at a time
python3 scripts/mcp_sync.py sync claude --apply

# Apply for real, all harnesses
python3 scripts/mcp_sync.py sync --all --apply
```

Or via `setup.sh`:

```bash
./setup.sh --sync-mcp            # dry-run preview across all harnesses
./setup.sh --sync-mcp --apply    # apply for real
```
