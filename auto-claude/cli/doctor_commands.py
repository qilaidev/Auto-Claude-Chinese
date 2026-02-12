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
from pathlib import Path

from core.auth import get_auth_token, get_auth_token_source
from core.backup import is_auto_backup_enabled
from ui import (
    Icons,
    bold,
    box,
    icon,
    muted,
)


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


def _resolve_log_file_path(project_dir: Path) -> Path | None:
    """Resolve configured operational log file path, if logging is enabled."""
    log_file = os.environ.get("AUTO_CLAUDE_LOG_FILE", "").strip()
    log_dir = os.environ.get("AUTO_CLAUDE_LOG_DIR", "").strip()
    if not log_file and not log_dir:
        return None

    path = Path(log_file) if log_file else Path(log_dir) / "auto-claude.log"
    if not path.is_absolute():
        path = project_dir / path
    return path


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
        add("python", "pass", f"Python {sys.version_info.major}.{sys.version_info.minor}")
    else:
        add("python", "fail", "Python 3.10+ required")

    has_git = _has_command("git")
    add("git", "pass" if has_git else "fail", "git is available" if has_git else "git not found on PATH")

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
        "project state directory writable" if project_ok else f"project not writable ({project_reason})",
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

    # Operational posture
    if in_git_repo and _is_git_dirty(project_dir):
        add("git_clean", "warn", "working tree has local changes")
    else:
        add("git_clean", "pass", "working tree is clean")

    status_file = project_dir / ".auto-claude-status"
    if status_file.exists():
        try:
            json.loads(status_file.read_text(encoding="utf-8"))
            add("status_file", "pass", "status file is valid JSON")
        except (OSError, json.JSONDecodeError):
            add("status_file", "warn", "status file exists but is invalid JSON")
    else:
        add("status_file", "pass", "status file not present (will be created at runtime)")

    log_path = _resolve_log_file_path(project_dir)
    if log_path is not None:
        log_dir_ok, log_dir_reason = _probe_writable(log_path.parent)
        if log_dir_ok:
            add("logging", "pass", f"operational file logging is configured ({log_path})")
        else:
            add(
                "logging",
                "fail",
                f"operational log directory is not writable ({log_dir_reason})",
            )
    else:
        add("logging", "warn", "operational file logging is not configured")

    allow_dirty = os.environ.get("AUTO_CLAUDE_ALLOW_DIRTY_MERGE", "").strip().lower()
    if allow_dirty in {"1", "true", "yes", "on"}:
        add("merge_guard", "warn", "dirty merge protection is disabled")
    else:
        add("merge_guard", "pass", "dirty merge protection is enabled")

    if is_auto_backup_enabled():
        add("auto_backup", "pass", "auto backup before destructive actions is enabled")
    else:
        add("auto_backup", "warn", "auto backup before destructive actions is disabled")

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
