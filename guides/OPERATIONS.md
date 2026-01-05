# Operations and Production Readiness

This guide covers the minimum operational practices to keep Auto Claude stable
for long-term use without changing its architecture.

## Scope

- **CLI users**: `auto-claude/` is the runtime.
- **Desktop UI users**: `auto-claude-ui/` wraps the CLI; Python backend still runs.

## Baseline Requirements

- Git installed and the target project is a git repo.
- Python 3.10+ for the backend.
- Node.js 20+ for the Desktop UI (optional).
- Docker Desktop only if you enable Graphiti memory (optional).

## Configuration Baseline

- Required: Claude Code OAuth token via `claude setup-token` or `CLAUDE_CODE_OAUTH_TOKEN`.
- Optional logging for production troubleshooting:
  - `AUTO_CLAUDE_LOG_FILE=/var/log/auto-claude/auto-claude.log`
  - `AUTO_CLAUDE_LOG_DIR=.auto-claude/logs`
  - `AUTO_CLAUDE_LOG_LEVEL=INFO`
  - `AUTO_CLAUDE_LOG_MAX_BYTES=5242880`
  - `AUTO_CLAUDE_LOG_BACKUPS=3`
- Optional GitHub proxy for updater/source downloads (when direct GitHub access is blocked):
  - `AUTO_CLAUDE_GITHUB_PROXY=https://mirror.ghproxy.com`
  - Set `AUTO_CLAUDE_DISABLE_PROXY_FALLBACK=true` to disable built-in fallback.
- Debug-only logging (use sparingly in production):
  - `DEBUG=true`
  - `DEBUG_LEVEL=1|2|3`
  - `DEBUG_LOG_FILE=auto-claude/debug.log`

## Observability (What to Check)

- **Build status file**: `.auto-claude-status` in the project root.
- **Per-spec logs**: `.auto-claude/specs/<spec>/task_logs.json`.
- **Desktop UI main logs**: OS log directory (Auto-Claude/main.log).
- **Optional runtime log** (if enabled): `AUTO_CLAUDE_LOG_FILE` or `AUTO_CLAUDE_LOG_DIR`.

## Health Checks

Basic checks before running a build:

```bash
git rev-parse --is-inside-work-tree
claude --version
python3 --version
```

Graphiti memory (optional):

```bash
docker ps --filter name=auto-claude-falkordb
docker ps --filter name=auto-claude-graphiti-mcp
```

## Backup and Restore

### Backup (minimal)

- **Specs and local memory**: back up `.auto-claude/` in your project root.
- **Worktrees** (optional): `.worktrees/` if you want to keep in-progress builds.

```bash
tar -czf auto-claude-backup.tgz .auto-claude .worktrees
```

### Backup Graphiti (optional)

```bash
docker run --rm \
  -v falkordb_data:/data \
  -v "$PWD":/backup \
  busybox tar -czf /backup/falkordb_data.tgz /data
```

### Restore Graphiti (optional)

```bash
docker run --rm \
  -v falkordb_data:/data \
  -v "$PWD":/backup \
  busybox sh -c "rm -rf /data/* && tar -xzf /backup/falkordb_data.tgz -C /"
```

## Rollback and Recovery

- **Discard a build worktree**:
  ```bash
  python auto-claude/run.py --spec <spec-id> --discard
  ```
- **Revert merged changes**: use normal git revert/reset on your target branch.
- **Spec state reset** (last resort): remove the spec directory under
  `.auto-claude/specs/<spec-id>/` and recreate the spec.

## Security Baseline

- Run secret scanning before releases:
  ```bash
  ./auto-claude/scan-for-secrets --all-files
  ```
- Customize `.secretsignore` for known false positives in this repo.
- Never commit real tokens to `.env` or source files.

## Incident Notes

- If builds crash, check the optional log file and the per-spec
  `task_logs.json` for the last phase.
- If statusline is stuck, delete `.auto-claude-status` and restart the build.
