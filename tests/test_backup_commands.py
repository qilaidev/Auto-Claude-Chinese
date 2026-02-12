#!/usr/bin/env python3
"""
Tests for CLI backup commands.
"""

from pathlib import Path

from cli.backup_commands import handle_restore_backup_command
from core.backup import create_spec_backup


def test_restore_backup_command_supports_restore_dir_outside_project(
    temp_git_repo: Path, temp_dir: Path
):
    spec_name = "010-backup-command"
    spec_dir = temp_git_repo / ".auto-claude" / "specs" / spec_name
    spec_dir.mkdir(parents=True)
    (spec_dir / "spec.md").write_text("# spec\n", encoding="utf-8")

    archive = create_spec_backup(temp_git_repo, spec_name, reason="manual-restore")
    assert archive is not None

    external_restore_dir = temp_dir / "external-restore-target"
    success = handle_restore_backup_command(
        project_dir=temp_git_repo,
        spec_name=spec_name,
        archive=archive.name,
        restore_dir=external_restore_dir,
    )

    assert success is True
    assert (external_restore_dir / "spec" / "spec.md").exists()
