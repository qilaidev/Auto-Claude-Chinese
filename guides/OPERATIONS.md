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
  - `AUTO_CLAUDE_ALERT_WEBHOOK_URL=<https webhook>` (optional fatal-incident alert)
  - `AUTO_CLAUDE_ALERT_TIMEOUT_SECONDS=3`
- Merge and backup safety rails:
  - `AUTO_CLAUDE_ALLOW_DIRTY_MERGE=false` (default) blocks `--merge` when git working tree is dirty.
  - `AUTO_CLAUDE_DISABLE_AUTO_BACKUP=false` (default) creates pre-delete
    backup archives before `--discard` / `--cleanup-worktrees`.
  - `AUTO_CLAUDE_MAX_BACKUPS_PER_SPEC=20` controls backup retention per spec.
  - `AUTO_CLAUDE_STATUS_STALE_HOURS=6` defines when an active `.auto-claude-status`
    should be treated as stale.
  - `AUTO_CLAUDE_DOCTOR_MIN_FREE_MB=1024` warns when free disk space is low.
  - `AUTO_CLAUDE_DOCTOR_FAIL_FREE_MB=256` fails preflight when free disk space is critically low.
- Optional GitHub proxy for updater/source downloads
  (when direct GitHub access is blocked):
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
  - Desktop UI will prefer `requirements.lock` over `requirements.txt` if present.

## Observability (What to Check)

- **Build status file**: `.auto-claude-status` in the project root.
- **Per-spec logs**: `.auto-claude/specs/<spec>/task_logs.json`.
- **Incident reports (fatal errors)**: `.auto-claude/incidents/*.json`.
- **Optional incident webhook alert**: set `AUTO_CLAUDE_ALERT_WEBHOOK_URL`.
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

`--doctor` now includes additional production guardrails:

- Disk capacity threshold checks (warn/fail with configurable MB limits)
- Stale active status detection for `.auto-claude-status`
- Merge lock visibility (`.auto-claude/.locks/merge-*.lock` stale/active)
- Incident webhook hygiene (HTTPS + timeout sanity)
- Backup retention env validation

If doctor reports stale state/locks:

```bash
# 1) verify no active build is running
ps aux | grep "auto-claude/run.py"

# 2) clear stale status marker (safe when no active run)
rm -f .auto-claude-status

# 3) clear stale merge lock files (safe when no merge running)
rm -f .auto-claude/.locks/merge-*.lock
```

CI baseline:

- `.github/workflows/ci.yml` runs `python auto-claude/run.py --doctor --doctor-strict`.
- It also runs focused readiness tests:
  - `tests/test_doctor_commands.py`
  - `tests/test_backup.py`
  - `tests/test_backup_commands.py`
  - `tests/test_incident.py`
  - `tests/test_workspace_merge_safety.py`
  - `tests/test_file_io.py`

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

Auto backup behavior for destructive commands:

- `python auto-claude/run.py --spec <spec-id> --discard` now creates a backup archive by default.
- `python auto-claude/run.py --cleanup-worktrees` now creates per-spec backups by default.
- Disable only when necessary: `AUTO_CLAUDE_DISABLE_AUTO_BACKUP=true`.

List and inspect backups from CLI:

```bash
python auto-claude/run.py --spec <spec-id> --list-backups
```

Restore from an auto-backup archive:

```bash
# Restore latest archive for spec (prompts for confirmation)
python auto-claude/run.py --spec <spec-id> --restore-backup

# Restore a specific archive path
python auto-claude/run.py --spec <spec-id> --restore-backup \
  --backup-archive .auto-claude/backups/<spec>/<archive>.tar.gz

# Overwrite existing spec/worktree data (non-interactive)
python auto-claude/run.py --spec <spec-id> --restore-backup --overwrite-existing --yes
```

Manual extraction (for forensic/debug use) remains available:

```bash
mkdir -p restore-spec
tar -xzf .auto-claude/backups/<spec>/<archive>.tar.gz -C restore-spec
```

Archive contents:

- `spec/` (spec state, logs, QA artifacts)
- `worktree/` (worktree snapshot, if present)
- `backup_metadata.json` (timestamp/reason metadata)

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
