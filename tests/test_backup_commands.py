#!/usr/bin/env python3
"""
Tests for backup CLI command helpers.
"""

from cli.backup_commands import resolve_backup_spec_name
from cli.main import parse_args


def _assert_parse_error(args: list[str]) -> None:
    from unittest.mock import patch

    with patch("sys.argv", args):
        try:
            parse_args()
        except SystemExit as exc:
            assert exc.code == 2
            return

    raise AssertionError("Expected parser failure")


def test_resolve_backup_spec_uses_spec_dir_when_available(temp_git_repo):
    spec_dir = temp_git_repo / ".auto-claude" / "specs" / "001-feature"
    spec_dir.mkdir(parents=True)

    resolved = resolve_backup_spec_name(
        project_dir=temp_git_repo,
        spec_identifier="001",
        resolved_spec_dir=spec_dir,
    )

    assert resolved == "001-feature"


def test_resolve_backup_spec_accepts_exact_backup_name(temp_git_repo):
    backup_dir = temp_git_repo / ".auto-claude" / "backups" / "002-task"
    backup_dir.mkdir(parents=True)

    resolved = resolve_backup_spec_name(
        project_dir=temp_git_repo,
        spec_identifier="002-task",
        resolved_spec_dir=None,
    )

    assert resolved == "002-task"


def test_resolve_backup_spec_matches_unique_numeric_prefix(temp_git_repo):
    (temp_git_repo / ".auto-claude" / "backups" / "003-abc").mkdir(parents=True)

    resolved = resolve_backup_spec_name(
        project_dir=temp_git_repo,
        spec_identifier="003",
        resolved_spec_dir=None,
    )

    assert resolved == "003-abc"


def test_resolve_backup_spec_raises_on_ambiguous_numeric_prefix(temp_git_repo):
    (temp_git_repo / ".auto-claude" / "backups" / "004-a").mkdir(parents=True)
    (temp_git_repo / ".auto-claude" / "backups" / "004-b").mkdir(parents=True)

    try:
        resolve_backup_spec_name(
            project_dir=temp_git_repo,
            spec_identifier="004",
            resolved_spec_dir=None,
        )
    except ValueError as exc:
        assert "ambiguous" in str(exc)
        return

    raise AssertionError("Expected ValueError for ambiguous numeric backup spec")


def test_resolve_backup_spec_falls_back_to_raw_identifier(temp_git_repo):
    resolved = resolve_backup_spec_name(
        project_dir=temp_git_repo,
        spec_identifier="plain-spec",
        resolved_spec_dir=None,
    )

    assert resolved == "plain-spec"


def test_resolve_backup_spec_rejects_empty_identifier(temp_git_repo):
    try:
        resolve_backup_spec_name(
            project_dir=temp_git_repo,
            spec_identifier="   ",
            resolved_spec_dir=None,
        )
    except ValueError as exc:
        assert "cannot be empty" in str(exc)
        return

    raise AssertionError("Expected ValueError for empty spec identifier")


def test_parse_args_rejects_list_backups_with_backup_archive():
    _assert_parse_error(
        [
            "run.py",
            "--spec",
            "001",
            "--list-backups",
            "--backup-archive",
            "a.tar.gz",
        ]
    )


def test_parse_args_rejects_restore_backup_with_qa_flag():
    _assert_parse_error(
        ["run.py", "--spec", "001", "--restore-backup", "--qa"]
    )


def test_parse_args_allows_restore_backup_with_archive():
    from unittest.mock import patch

    with patch(
        "sys.argv",
        [
            "run.py",
            "--spec",
            "001",
            "--restore-backup",
            "--backup-archive",
            "a.tar.gz",
            "--overwrite-existing",
            "--yes",
        ],
    ):
        args = parse_args()
    assert args.restore_backup is True
    assert args.backup_archive is not None
    assert str(args.backup_archive) == "a.tar.gz"


def test_parse_args_rejects_restore_backup_with_merge_flag():
    _assert_parse_error(
        ["run.py", "--spec", "001", "--restore-backup", "--merge"]
    )
