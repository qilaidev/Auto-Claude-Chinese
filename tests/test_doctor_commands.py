#!/usr/bin/env python3
"""
Tests for preflight doctor checks.
"""

import subprocess

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
