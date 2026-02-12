#!/usr/bin/env python3
"""
Tests for preflight doctor checks.
"""

from pathlib import Path

from cli.doctor_commands import run_preflight_checks
from core import logging_setup
from core.logging_setup import configure_logging


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


def test_doctor_fails_when_log_dir_is_not_writable_target(temp_git_repo, monkeypatch):
    invalid_log_dir = temp_git_repo / "not-a-directory"
    invalid_log_dir.write_text("occupied-by-file\n", encoding="utf-8")
    monkeypatch.setenv("AUTO_CLAUDE_LOG_DIR", str(invalid_log_dir))

    checks = run_preflight_checks(project_dir=temp_git_repo)
    statuses = _status_by_name(checks)
    assert statuses["logging"] == "fail"


def test_configure_logging_degrades_gracefully_when_handler_open_fails(
    temp_git_repo, monkeypatch
):
    monkeypatch.setenv("AUTO_CLAUDE_LOG_DIR", ".auto-claude/logs")

    def _raise_open_error(*_args, **_kwargs):
        raise OSError("permission denied")

    monkeypatch.setattr(logging_setup, "RotatingFileHandler", _raise_open_error)
    result = configure_logging(project_dir=Path(temp_git_repo))
    assert result is None
