#!/usr/bin/env python3
"""
Tests for preflight doctor checks.
"""

import json
import subprocess
from collections import namedtuple
from datetime import datetime, timedelta, timezone

from cli.doctor_commands import run_preflight_checks
from core.backup import create_spec_backup


def _status_by_name(checks):
    return {check.name: check.status for check in checks}


def test_doctor_reports_missing_spec_when_identifier_not_resolved(temp_git_repo):
    checks = run_preflight_checks(
        project_dir=temp_git_repo,
        spec_dir=None,
        spec_identifier="999-missing",
    )
    statuses = _status_by_name(checks)
    assert statuses["spec_lookup"] == "fail"


def test_doctor_reports_spec_checks_when_spec_present(temp_git_repo, monkeypatch):
    monkeypatch.setenv("AUTO_CLAUDE_DISABLE_AUTO_BACKUP", "1")
    monkeypatch.setenv("AUTO_CLAUDE_ALLOW_DIRTY_MERGE", "true")

    spec_dir = temp_git_repo / ".auto-claude" / "specs" / "001-doctor"
    spec_dir.mkdir(parents=True)
    (spec_dir / "spec.md").write_text("# test\n", encoding="utf-8")

    checks = run_preflight_checks(
        project_dir=temp_git_repo,
        spec_dir=spec_dir,
        spec_identifier="001-doctor",
    )
    statuses = _status_by_name(checks)

    assert statuses["spec_file"] == "pass"
    assert statuses["spec_write"] == "pass"
    assert statuses["auto_backup"] == "warn"
    assert statuses["merge_guard"] == "warn"


def test_doctor_detects_invalid_status_file(temp_git_repo):
    status_file = temp_git_repo / ".auto-claude-status"
    status_file.write_text("not-json", encoding="utf-8")

    checks = run_preflight_checks(project_dir=temp_git_repo)
    statuses = _status_by_name(checks)

    assert statuses["status_file"] == "warn"
    assert statuses["status_activity"] == "warn"


def test_doctor_warns_when_logging_not_configured(temp_git_repo, monkeypatch):
    monkeypatch.delenv("AUTO_CLAUDE_LOG_FILE", raising=False)
    monkeypatch.delenv("AUTO_CLAUDE_LOG_DIR", raising=False)

    checks = run_preflight_checks(project_dir=temp_git_repo)
    statuses = _status_by_name(checks)
    assert statuses["logging"] == "warn"


def test_doctor_passes_logging_when_log_dir_configured(temp_git_repo, monkeypatch):
    monkeypatch.setenv("AUTO_CLAUDE_LOG_DIR", ".auto-claude/logs")

    checks = run_preflight_checks(project_dir=temp_git_repo)
    statuses = _status_by_name(checks)
    assert statuses["logging"] == "pass"


def test_doctor_warns_branch_namespace_conflict(temp_git_repo):
    # Simulate conflicting branch name that blocks auto-claude/* namespace.
    subprocess.run(
        ["git", "checkout", "-b", "auto-claude"],
        cwd=temp_git_repo,
        capture_output=True,
        check=True,
    )

    checks = run_preflight_checks(project_dir=temp_git_repo)
    statuses = _status_by_name(checks)
    assert statuses["branch_namespace"] == "warn"


def test_doctor_checks_backup_integrity(temp_git_repo):
    spec_name = "001-backup-health"
    spec_dir = temp_git_repo / ".auto-claude" / "specs" / spec_name
    spec_dir.mkdir(parents=True)
    (spec_dir / "spec.md").write_text("# spec\n", encoding="utf-8")

    create_spec_backup(temp_git_repo, spec_name, reason="doctor")

    checks = run_preflight_checks(
        project_dir=temp_git_repo,
        spec_dir=spec_dir,
        spec_identifier=spec_name,
    )
    statuses = _status_by_name(checks)
    assert statuses["backup_integrity"] == "pass"


def test_doctor_warns_for_stale_active_status(temp_git_repo, monkeypatch):
    monkeypatch.setenv("AUTO_CLAUDE_STATUS_STALE_HOURS", "1")
    stale_time = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()

    status_file = temp_git_repo / ".auto-claude-status"
    status_file.write_text(
        json.dumps({"active": True, "last_update": stale_time}),
        encoding="utf-8",
    )

    checks = run_preflight_checks(project_dir=temp_git_repo)
    statuses = _status_by_name(checks)

    assert statuses["status_file"] == "pass"
    assert statuses["status_activity"] == "warn"


def test_doctor_warns_for_http_incident_webhook(temp_git_repo, monkeypatch):
    monkeypatch.setenv("AUTO_CLAUDE_ALERT_WEBHOOK_URL", "http://example.com/alert")

    checks = run_preflight_checks(project_dir=temp_git_repo)
    statuses = _status_by_name(checks)

    assert statuses["alert_webhook"] == "warn"


def test_doctor_warns_for_invalid_backup_retention(temp_git_repo, monkeypatch):
    monkeypatch.setenv("AUTO_CLAUDE_MAX_BACKUPS_PER_SPEC", "invalid")

    checks = run_preflight_checks(project_dir=temp_git_repo)
    statuses = _status_by_name(checks)

    assert statuses["backup_retention"] == "warn"


def test_doctor_warns_for_stale_merge_lock_file(temp_git_repo):
    lock_dir = temp_git_repo / ".auto-claude" / ".locks"
    lock_dir.mkdir(parents=True)
    (lock_dir / "merge-001-test.lock").write_text("not-a-pid", encoding="utf-8")

    checks = run_preflight_checks(project_dir=temp_git_repo)
    statuses = _status_by_name(checks)

    assert statuses["merge_lock"] == "warn"


def test_doctor_fails_when_disk_space_is_below_fail_threshold(
    temp_git_repo,
    monkeypatch,
):
    DiskUsage = namedtuple("DiskUsage", ["total", "used", "free"])
    mocked_usage = DiskUsage(
        total=200 * 1024 * 1024,
        used=170 * 1024 * 1024,
        free=30 * 1024 * 1024,
    )

    monkeypatch.setattr("cli.doctor_commands.shutil.disk_usage", lambda _: mocked_usage)
    monkeypatch.setenv("AUTO_CLAUDE_DOCTOR_MIN_FREE_MB", "100")
    monkeypatch.setenv("AUTO_CLAUDE_DOCTOR_FAIL_FREE_MB", "50")

    checks = run_preflight_checks(project_dir=temp_git_repo)
    statuses = _status_by_name(checks)

    assert statuses["disk_space"] == "fail"
