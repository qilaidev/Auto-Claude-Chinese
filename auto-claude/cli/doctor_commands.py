"""
Production preflight doctor command.

Provides a lightweight readiness checklist for production operation without
changing application behavior.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from core.auth import get_auth_token, get_auth_token_source
from core.backup import is_auto_backup_enabled, list_spec_backups, read_backup_metadata
from ui import (
    Icons,
    bold,
    box,
    icon,
    muted,
)

DEFAULT_DOCTOR_WARN_FREE_MB = 1024
DEFAULT_DOCTOR_FAIL_FREE_MB = 256
DEFAULT_STATUS_STALE_HOURS = 6


def _safe_int_env(name: str, default: int) -> int:
    """Read integer env var with fallback."""
    value = os.environ.get(name)
    if not value:
        return default

    try:
        return int(value)
    except ValueError:
        return default


def _safe_float_env(name: str, default: float) -> float:
    """Read positive float env var with fallback."""
    value = os.environ.get(name)
    if not value:
        return default

    try:
        parsed = float(value)
    except ValueError:
        return default

    if parsed <= 0:
        return default
    return parsed


def _format_size_mb(size_bytes: int) -> str:
    """Format bytes to human-readable megabytes."""
    return f"{size_bytes / (1024 * 1024):.0f}MB"


def _check_disk_space(project_dir: Path) -> tuple[str, str]:
    """Check available disk space for project filesystem."""
    try:
        usage = shutil.disk_usage(project_dir)
    except OSError as exc:
        return "warn", f"could not read disk usage ({exc})"

    warn_threshold_mb = _safe_int_env(
        "AUTO_CLAUDE_DOCTOR_MIN_FREE_MB",
        DEFAULT_DOCTOR_WARN_FREE_MB,
    )
    fail_threshold_mb = _safe_int_env(
        "AUTO_CLAUDE_DOCTOR_FAIL_FREE_MB",
        DEFAULT_DOCTOR_FAIL_FREE_MB,
    )

    if warn_threshold_mb <= 0:
        warn_threshold_mb = DEFAULT_DOCTOR_WARN_FREE_MB
    if fail_threshold_mb <= 0:
        fail_threshold_mb = DEFAULT_DOCTOR_FAIL_FREE_MB

    if fail_threshold_mb > warn_threshold_mb:
        fail_threshold_mb, warn_threshold_mb = warn_threshold_mb, fail_threshold_mb

    free_mb = usage.free / (1024 * 1024)
    message = (
        f"free {free_mb:.0f}MB / total {_format_size_mb(usage.total)} "
        f"(warn<{warn_threshold_mb}MB, fail<{fail_threshold_mb}MB)"
    )

    if free_mb < fail_threshold_mb:
        return "fail", f"disk space critically low: {message}"
    if free_mb < warn_threshold_mb:
        return "warn", f"disk space low: {message}"
    return "pass", f"disk capacity healthy: {message}"


def _check_merge_locks(project_dir: Path) -> tuple[str, str]:
    """Check for active or stale merge lock files."""
    lock_dir = project_dir / ".auto-claude" / ".locks"
    if not lock_dir.exists():
        return "pass", "no merge locks present"

    lock_files = sorted(lock_dir.glob("merge-*.lock"))
    if not lock_files:
        return "pass", "no merge locks present"

    active_locks: list[str] = []
    stale_locks: list[str] = []

    for lock_file in lock_files:
        try:
            pid = int(lock_file.read_text(encoding="utf-8").strip())
            try:
                os.kill(pid, 0)
                active_locks.append(lock_file.name)
            except (OSError, ProcessLookupError):
                stale_locks.append(lock_file.name)
        except (OSError, ValueError):
            stale_locks.append(lock_file.name)

    if stale_locks:
        preview = ", ".join(stale_locks[:3])
        suffix = "..." if len(stale_locks) > 3 else ""
        return "warn", f"stale merge lock(s) detected: {preview}{suffix}"

    preview = ", ".join(active_locks[:3])
    suffix = "..." if len(active_locks) > 3 else ""
    return "warn", f"active merge lock(s) present: {preview}{suffix}"


def _parse_iso_datetime(value: str) -> datetime | None:
    """Parse ISO datetime from status files."""
    candidate = value.strip()
    if not candidate:
        return None

    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"

    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        local_tz = datetime.now().astimezone().tzinfo
        parsed = parsed.replace(tzinfo=local_tz)
    return parsed.astimezone(timezone.utc)


def _check_status_activity(status_data: dict) -> tuple[str, str]:
    """Check whether status file indicates a stale active run."""
    is_active = bool(status_data.get("active"))
    if not is_active:
        return "pass", "no active build recorded"

    timestamp = str(status_data.get("last_update", "")).strip()
    if not timestamp:
        return "warn", "status file marks active build but last_update is missing"

    parsed = _parse_iso_datetime(timestamp)
    if parsed is None:
        return "warn", "status file marks active build but last_update is invalid"

    now_utc = datetime.now(timezone.utc)
    age_seconds = max((now_utc - parsed).total_seconds(), 0)
    stale_hours = _safe_int_env("AUTO_CLAUDE_STATUS_STALE_HOURS", DEFAULT_STATUS_STALE_HOURS)
    if stale_hours <= 0:
        stale_hours = DEFAULT_STATUS_STALE_HOURS

    age_hours = age_seconds / 3600
    if age_hours >= stale_hours:
        return "warn", f"active build status appears stale ({age_hours:.1f}h old)"

    if age_seconds < 120:
        return "pass", "active build status is fresh (<2m)"

    if age_seconds < 3600:
        return "pass", f"active build status is fresh ({age_seconds / 60:.0f}m old)"

    return "pass", f"active build status is fresh ({age_hours:.1f}h old)"


def _check_alert_webhook_config() -> tuple[str, str]:
    """Validate optional incident webhook configuration."""
    webhook = os.environ.get("AUTO_CLAUDE_ALERT_WEBHOOK_URL", "").strip()
    if not webhook:
        return "pass", "incident webhook alert is disabled"

    parsed = urlparse(webhook)
    if parsed.scheme.lower() != "https":
        return "warn", "incident webhook should use HTTPS"

    if not parsed.netloc:
        return "warn", "incident webhook URL is missing host"

    timeout_seconds = _safe_float_env("AUTO_CLAUDE_ALERT_TIMEOUT_SECONDS", 3.0)
    if timeout_seconds < 1.0:
        return "warn", "incident webhook timeout is very low (<1s)"

    return "pass", f"incident webhook configured ({parsed.netloc}, timeout={timeout_seconds:.1f}s)"


def _check_backup_retention_config() -> tuple[str, str]:
    """Validate backup retention environment variable."""
    raw_value = os.environ.get("AUTO_CLAUDE_MAX_BACKUPS_PER_SPEC")
    if raw_value is None or not raw_value.strip():
        return "pass", "backup retention uses default (20 archives/spec)"

    try:
        parsed = int(raw_value)
    except ValueError:
        return "warn", "AUTO_CLAUDE_MAX_BACKUPS_PER_SPEC is not an integer"

    if parsed <= 0:
        return "warn", "AUTO_CLAUDE_MAX_BACKUPS_PER_SPEC should be > 0"

    return "pass", f"backup retention configured ({parsed} archives/spec)"


@dataclass
class DoctorCheck:
    """Single preflight check result."""

    name: str
    status: str
    message: str


def _has_command(command: str) -> bool:
    """Return whether command exists on PATH."""
    return shutil.which(command) is not None


def _is_git_repo(project_dir: Path) -> bool:
    """Return whether directory is inside a git repository."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return False
    return result.returncode == 0 and result.stdout.strip() == "true"


def _is_git_dirty(project_dir: Path) -> bool:
    """Return whether git working tree has local changes."""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return False

    if result.returncode != 0:
        return False
    return bool(result.stdout.strip())


def _has_branch_namespace_conflict(project_dir: Path) -> bool:
    """Return whether `auto-claude` branch blocks `auto-claude/*` namespace."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", "auto-claude"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return False
    return result.returncode == 0


def _probe_writable(dir_path: Path) -> tuple[bool, str]:
    """Probe whether directory is writable by creating and deleting a temp file."""
    probe_file = dir_path / ".doctor-write-check"
    try:
        dir_path.mkdir(parents=True, exist_ok=True)
        probe_file.write_text("ok", encoding="utf-8")
        probe_file.unlink(missing_ok=True)
        return True, "writable"
    except OSError as exc:
        return False, str(exc)


def _check_backup_integrity(project_dir: Path, spec_name: str) -> tuple[str, str]:
    """Check whether the latest backup archive is readable and matches spec."""
    backups = list_spec_backups(project_dir, spec_name)
    if not backups:
        return "warn", "no backup archive found for this spec"

    latest = backups[0]
    metadata = read_backup_metadata(latest)
    if metadata is None:
        return "fail", f"latest backup unreadable: {latest.name}"

    metadata_spec = str(metadata.get("spec_name", "")).strip()
    if metadata_spec and metadata_spec != spec_name:
        return (
            "fail",
            "latest backup metadata spec mismatch "
            f"({metadata_spec} != {spec_name})",
        )

    contents = metadata.get("contents", [])
    if not contents:
        return "warn", f"latest backup missing contents metadata: {latest.name}"

    return "pass", f"latest backup readable: {latest.name}"


def run_preflight_checks(
    project_dir: Path,
    spec_dir: Path | None = None,
    spec_identifier: str | None = None,
) -> list[DoctorCheck]:
    """
    Run production preflight checks.

    Args:
        project_dir: Project root path.
        spec_dir: Resolved spec path, if provided.
        spec_identifier: Raw `--spec` input for lookup validation.

    Returns:
        List of check results.
    """
    checks: list[DoctorCheck] = []

    def add(name: str, status: str, message: str) -> None:
        checks.append(DoctorCheck(name=name, status=status, message=message))

    # Runtime baseline
    if sys.version_info >= (3, 10):
        add(
            "python",
            "pass",
            f"Python {sys.version_info.major}.{sys.version_info.minor}",
        )
    else:
        add("python", "fail", "Python 3.10+ required")

    has_git = _has_command("git")
    add(
        "git",
        "pass" if has_git else "fail",
        "git is available" if has_git else "git not found on PATH",
    )

    has_claude = _has_command("claude")
    add(
        "claude_cli",
        "pass" if has_claude else "fail",
        "claude CLI is available" if has_claude else "claude CLI not found on PATH",
    )

    in_git_repo = has_git and _is_git_repo(project_dir)
    add(
        "git_repo",
        "pass" if in_git_repo else "fail",
        "project is a git repository"
        if in_git_repo
        else "project is not a git repository",
    )

    if in_git_repo and _has_branch_namespace_conflict(project_dir):
        add(
            "branch_namespace",
            "warn",
            "branch 'auto-claude' exists and may block creating auto-claude/* worktree branches",
        )
    else:
        add(
            "branch_namespace",
            "pass",
            "no auto-claude branch namespace conflict detected",
        )

    # Authentication baseline
    token = get_auth_token()
    if token:
        source = get_auth_token_source() or "unknown source"
        add("auth", "pass", f"auth token available ({source})")
    else:
        add("auth", "fail", "no auth token found")

    # Filesystem safety
    project_ok, project_reason = _probe_writable(project_dir / ".auto-claude")
    add(
        "project_write",
        "pass" if project_ok else "fail",
        "project state directory writable"
        if project_ok
        else f"project not writable ({project_reason})",
    )

    incident_ok, incident_reason = _probe_writable(
        project_dir / ".auto-claude" / "incidents"
    )
    add(
        "incident_write",
        "pass" if incident_ok else "fail",
        "incident directory writable"
        if incident_ok
        else f"incident directory not writable ({incident_reason})",
    )

    backup_ok, backup_reason = _probe_writable(project_dir / ".auto-claude" / "backups")
    add(
        "backup_write",
        "pass" if backup_ok else "fail",
        "backup directory writable"
        if backup_ok
        else f"backup directory not writable ({backup_reason})",
    )

    disk_status, disk_message = _check_disk_space(project_dir)
    add("disk_space", disk_status, disk_message)

    # Operational posture
    if in_git_repo and _is_git_dirty(project_dir):
        add("git_clean", "warn", "working tree has local changes")
    else:
        add("git_clean", "pass", "working tree is clean")

    status_file = project_dir / ".auto-claude-status"
    if status_file.exists():
        status_data: dict | None = None
        try:
            status_data = json.loads(status_file.read_text(encoding="utf-8"))
            add("status_file", "pass", "status file is valid JSON")
        except (OSError, json.JSONDecodeError):
            add("status_file", "warn", "status file exists but is invalid JSON")

        if isinstance(status_data, dict):
            activity_status, activity_message = _check_status_activity(status_data)
            add("status_activity", activity_status, activity_message)
        else:
            add(
                "status_activity",
                "warn",
                "status activity check skipped because status file is invalid",
            )
    else:
        add("status_file", "pass", "status file not present (will be created at runtime)")
        add("status_activity", "pass", "no status file yet")

    has_log_config = bool(
        os.environ.get("AUTO_CLAUDE_LOG_FILE") or os.environ.get("AUTO_CLAUDE_LOG_DIR")
    )
    if has_log_config:
        add("logging", "pass", "operational file logging is configured")
    else:
        add("logging", "warn", "operational file logging is not configured")

    alert_status, alert_message = _check_alert_webhook_config()
    add("alert_webhook", alert_status, alert_message)

    allow_dirty = os.environ.get("AUTO_CLAUDE_ALLOW_DIRTY_MERGE", "").strip().lower()
    if allow_dirty in {"1", "true", "yes", "on"}:
        add("merge_guard", "warn", "dirty merge protection is disabled")
    else:
        add("merge_guard", "pass", "dirty merge protection is enabled")

    lock_status, lock_message = _check_merge_locks(project_dir)
    add("merge_lock", lock_status, lock_message)

    if is_auto_backup_enabled():
        add("auto_backup", "pass", "auto backup before destructive actions is enabled")
    else:
        add("auto_backup", "warn", "auto backup before destructive actions is disabled")

    retention_status, retention_message = _check_backup_retention_config()
    add("backup_retention", retention_status, retention_message)

    # Optional spec-level checks
    if spec_identifier and spec_dir is None:
        add("spec_lookup", "fail", f"spec '{spec_identifier}' not found")

    if spec_dir:
        spec_file = spec_dir / "spec.md"
        if spec_file.exists():
            add("spec_file", "pass", f"spec file present ({spec_file.name})")
        else:
            add("spec_file", "fail", "spec.md not found in spec directory")

        spec_ok, spec_reason = _probe_writable(spec_dir)
        add(
            "spec_write",
            "pass" if spec_ok else "fail",
            "spec directory writable"
            if spec_ok
            else f"spec directory not writable ({spec_reason})",
        )

        backup_status, backup_message = _check_backup_integrity(project_dir, spec_dir.name)
        add("backup_integrity", backup_status, backup_message)

    return checks


def _summarize(checks: list[DoctorCheck]) -> tuple[int, int, int]:
    """Return pass/warn/fail counts."""
    passed = sum(1 for check in checks if check.status == "pass")
    warned = sum(1 for check in checks if check.status == "warn")
    failed = sum(1 for check in checks if check.status == "fail")
    return passed, warned, failed


def handle_doctor_command(
    project_dir: Path,
    spec_dir: Path | None = None,
    spec_identifier: str | None = None,
    strict: bool = False,
) -> bool:
    """
    Execute preflight doctor and print a human-friendly report.

    Args:
        project_dir: Project root path.
        spec_dir: Optional resolved spec path.
        spec_identifier: Raw `--spec` argument for lookup validation.
        strict: Treat warnings as failures for exit status.

    Returns:
        True when checks pass according to strictness.
    """
    checks = run_preflight_checks(
        project_dir=project_dir,
        spec_dir=spec_dir,
        spec_identifier=spec_identifier,
    )

    print()
    content = [
        bold(f"{icon(Icons.SHIELD)} PRODUCTION PREFLIGHT DOCTOR"),
        muted(f"Project: {project_dir}"),
    ]
    if spec_identifier:
        content.append(muted(f"Spec: {spec_identifier}"))
    print(box(content, width=76, style="heavy"))

    status_to_icon = {
        "pass": Icons.SUCCESS,
        "warn": Icons.WARNING,
        "fail": Icons.ERROR,
    }

    for check in checks:
        label = check.status.upper().ljust(4)
        print(f"  {icon(status_to_icon[check.status])} [{label}] {check.name}: {check.message}")

    passed, warned, failed = _summarize(checks)
    print()
    print(
        f"Summary: {icon(Icons.SUCCESS)} {passed} passed, "
        f"{icon(Icons.WARNING)} {warned} warnings, "
        f"{icon(Icons.ERROR)} {failed} failures"
    )

    if strict and warned > 0:
        print(muted("Strict mode enabled: warnings are treated as failures."))

    success = failed == 0 and (not strict or warned == 0)
    print()
    if success:
        print(f"{icon(Icons.SUCCESS)} Doctor check passed.")
    else:
        print(f"{icon(Icons.WARNING)} Doctor check requires attention.")

    return success
