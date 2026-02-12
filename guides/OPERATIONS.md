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
  - `AUTO_CLAUDE_INCIDENT_WEBHOOK_URL=<your-webhook-url>` (optional, incident push)
  - `AUTO_CLAUDE_INCIDENT_WEBHOOK_TIMEOUT_SECONDS=3`
- Merge and backup safety rails:
  - `AUTO_CLAUDE_ALLOW_DIRTY_MERGE=false` (default) blocks `--merge` when git working tree is dirty.
  - `AUTO_CLAUDE_DISABLE_AUTO_BACKUP=false` (default) creates pre-delete backup archives before `--discard` / `--cleanup-worktrees`.
  - `AUTO_CLAUDE_MAX_BACKUPS_PER_SPEC=20` controls backup retention per spec.
- Optional GitHub proxy for updater/source downloads (when direct GitHub access is blocked):
  - `AUTO_CLAUDE_GITHUB_PROXY=https://mirror.ghproxy.com`
  - Set `AUTO_CLAUDE_DISABLE_PROXY_FALLBACK=true` to disable built-in fallback.
- Optional container image pinning (recommended for long-term stability):
  - `FALKORDB_IMAGE=falkordb/falkordb:<version>`
  - `GRAPHITI_MCP_IMAGE=falkordb/graphiti-knowledge-graph-mcp:<version>`
  - For Desktop UI one-click start: `AUTO_CLAUDE_FALKORDB_IMAGE=falkordb/falkordb:<version>`
- Debug-only logging (use sparingly in production):
  - `DEBUG=true`
  - `DEBUG_LEVEL=1|2|3`
  - `DEBUG_LOG_FILE=auto-claude/debug.log`
- Dependency pinning (optional but recommended for production):
  - Create `auto-claude/requirements.lock` and keep it in sync with releases.
  - Refresh lock with: `./scripts/update-requirements-lock.sh`
  - Desktop UI will prefer `requirements.lock` over `requirements.txt` if present.

## Observability (What to Check)

- **Build status file**: `.auto-claude-status` in the project root.
- **Per-spec logs**: `.auto-claude/specs/<spec>/task_logs.json`.
- **Incident reports (fatal errors)**: `.auto-claude/incidents/*.json`.
- **Pre-delete backups**: `.auto-claude/backups/<spec>/*.tar.gz`.
- **Desktop UI main logs**: OS log directory (`main.log`).
- **Desktop UI task logs** (per spec): `.auto-claude/specs/<spec>/logs/latest.log`.
- **Optional runtime log** (if enabled): `AUTO_CLAUDE_LOG_FILE` or `AUTO_CLAUDE_LOG_DIR`.

## Data Locations (Desktop UI)

Desktop UI data is stored under `app.getPath('userData')`:

- **macOS**: `~/Library/Application Support/Auto Claude/`
- **Windows**: `%APPDATA%\\Auto Claude\\`
- **Linux**: `~/.config/Auto Claude/`

Key subfolders:

- `store/projects.json` — project list and settings
- `settings.json` — app settings
- `auto-claude-source/` — downloaded backend override (used by auto-updater)
- `sessions/` and `terminal-sessions.json` — terminal recovery data

## Health Checks

Basic checks before running a build:

```bash
git rev-parse --is-inside-work-tree
claude --version
python3 --version
```

Recommended full preflight (built-in):

```bash
# Project-level readiness
python auto-claude/run.py --doctor

# Spec-level readiness (includes spec lookup + write checks)
python auto-claude/run.py --doctor --spec <spec-id>

# CI strict mode (warnings fail)
python auto-claude/run.py --doctor --doctor-strict
```

Release blocking gate (recommended before every production release):

```bash
./scripts/release-gate.sh
```

Graphiti memory (optional):

```bash
docker ps --filter name=auto-claude-falkordb
docker ps --filter name=auto-claude-graphiti-mcp
```

### Production Gate (Recommended Before Release)

Run the built-in production gate script from repo root:

```bash
./scripts/ops/production-ready-check.sh
```

This script executes:

1. `--doctor --doctor-strict` preflight
2. secrets scan (`scan-for-secrets --all-files`)
3. critical regression tests for production paths (`auto-claude/`, worktree safety, backup/restore, security)

Run only the production test suite (without doctor/secrets scan):

```bash
./scripts/ops/run-production-tests.sh
```

Local emergency override (not for release): allow doctor warnings while workspace is dirty

```bash
AUTO_CLAUDE_READY_ALLOW_DIRTY=true ./scripts/ops/production-ready-check.sh
```

> Why not full test suite by default?  
> This repository includes legacy/experimental areas and cross-layout compatibility tests.
> The production gate focuses on release-blocking checks for `auto-claude/` + `auto-claude-ui/`.

## Backup and Restore

### Backup (minimal)

- **Specs and local memory**: back up `.auto-claude/` in your project root.
- **Worktrees** (optional): `.worktrees/` if you want to keep in-progress builds.

```bash
tar -czf auto-claude-backup.tgz .auto-claude .worktrees
```

Auto backup behavior for destructive commands:

- `python auto-claude/run.py --spec <spec-id> --discard` now creates a backup archive by default.
- `python auto-claude/run.py --cleanup-worktrees` now creates per-spec backups by default.
- Disable only when necessary: `AUTO_CLAUDE_DISABLE_AUTO_BACKUP=true`.

Restore from an auto-backup archive:

```bash
# 查看某个 spec 可用备份（按时间倒序）
python auto-claude/run.py --spec <spec-id> --list-backups

# 恢复最新备份（默认提取到 .auto-claude/restores/<spec>/...）
python auto-claude/run.py --spec <spec-id> --restore-backup

# 恢复指定备份到指定目录
python auto-claude/run.py --spec <spec-id> --restore-backup \
  --backup-archive <archive-name>.tar.gz \
  --restore-dir ./restore-spec
```

The extracted folder contains:

- `spec/` (spec state, logs, QA artifacts)
- `worktree/` (worktree snapshot, if present)
- `backup_metadata.json` (timestamp/reason metadata)

> 恢复命令默认是**非破坏性提取**：先解包到恢复目录，确认无误后再手动拷回线上路径。

### Backup Desktop UI data (recommended for production use)

Back up the Desktop UI `userData` directory (see paths above).

- **macOS**:
  ```bash
  tar -czf auto-claude-ui-userdata.tgz ~/Library/Application\ Support/Auto\ Claude
  ```
- **Windows (PowerShell)**:
  ```powershell
  Compress-Archive -Path "$env:APPDATA\\Auto Claude" -DestinationPath auto-claude-ui-userdata.zip
  ```
- **Linux**:
  ```bash
  tar -czf auto-claude-ui-userdata.tgz ~/.config/Auto\ Claude
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
- **Desktop UI backend rollback** (packaged app):
  - Delete `auto-claude-source/` under the Desktop UI `userData` directory to
    revert to the bundled backend on next launch.
  - If a backup exists (`.auto-claude-source.backup`), you can restore it by
    renaming it to `auto-claude-source`.

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
