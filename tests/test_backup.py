#!/usr/bin/env python3
"""
Tests for backup helpers.
"""

import json
import io
import shutil
import tarfile

import pytest

from core.backup import (
    create_spec_backup,
    list_spec_backups,
    restore_spec_backup,
)


def test_create_spec_backup_includes_spec_and_worktree(temp_git_repo):
    spec_name = "001-backup-test"

    spec_dir = temp_git_repo / ".auto-claude" / "specs" / spec_name
    spec_dir.mkdir(parents=True)
    (spec_dir / "spec.md").write_text("# spec\n", encoding="utf-8")

    worktree_dir = temp_git_repo / ".worktrees" / spec_name
    worktree_dir.mkdir(parents=True)
    (worktree_dir / "feature.py").write_text("print('ok')\n", encoding="utf-8")

    archive_path = create_spec_backup(temp_git_repo, spec_name, reason="discard")

    assert archive_path is not None
    assert archive_path.exists()

    with tarfile.open(archive_path, mode="r:gz") as tar:
        names = tar.getnames()
        assert "spec/spec.md" in names
        assert "worktree/feature.py" in names
        assert "backup_metadata.json" in names

        metadata_file = tar.extractfile("backup_metadata.json")
        assert metadata_file is not None
        metadata = json.loads(metadata_file.read().decode("utf-8"))
        assert metadata["spec_name"] == spec_name
        assert metadata["reason"] == "discard"


def test_create_spec_backup_returns_none_when_no_data(temp_git_repo):
    result = create_spec_backup(temp_git_repo, "999-missing", reason="discard")
    assert result is None


def test_create_spec_backup_prunes_old_archives(temp_git_repo, monkeypatch):
    spec_name = "002-backup-prune"
    spec_dir = temp_git_repo / ".auto-claude" / "specs" / spec_name
    spec_dir.mkdir(parents=True)
    (spec_dir / "spec.md").write_text("# spec\n", encoding="utf-8")

    monkeypatch.setenv("AUTO_CLAUDE_MAX_BACKUPS_PER_SPEC", "1")

    first = create_spec_backup(temp_git_repo, spec_name, reason="one")
    second = create_spec_backup(temp_git_repo, spec_name, reason="two")

    assert first is not None
    assert second is not None

    backups = list_spec_backups(temp_git_repo, spec_name)
    assert len(backups) == 1
    assert backups[0].name.endswith("-two.tar.gz")


def test_restore_spec_backup_restores_spec_and_worktree(temp_git_repo):
    spec_name = "003-backup-restore"

    spec_dir = temp_git_repo / ".auto-claude" / "specs" / spec_name
    spec_dir.mkdir(parents=True)
    (spec_dir / "spec.md").write_text("# before\n", encoding="utf-8")

    worktree_dir = temp_git_repo / ".worktrees" / spec_name
    worktree_dir.mkdir(parents=True)
    (worktree_dir / "app.py").write_text("print('before')\n", encoding="utf-8")

    archive = create_spec_backup(temp_git_repo, spec_name, reason="test")
    assert archive is not None

    # Remove original directories to simulate destructive action.
    shutil.rmtree(spec_dir)
    shutil.rmtree(worktree_dir)

    result = restore_spec_backup(temp_git_repo, spec_name, archive=archive)

    assert result.archive_path == archive
    assert spec_dir in result.restored_paths
    assert worktree_dir in result.restored_paths
    assert result.skipped_paths == []
    assert (spec_dir / "spec.md").read_text(encoding="utf-8") == "# before\n"
    assert (worktree_dir / "app.py").read_text(encoding="utf-8") == "print('before')\n"


def test_restore_spec_backup_skips_existing_paths_without_overwrite(temp_git_repo):
    spec_name = "004-backup-restore-skip"

    spec_dir = temp_git_repo / ".auto-claude" / "specs" / spec_name
    spec_dir.mkdir(parents=True)
    (spec_dir / "spec.md").write_text("# old\n", encoding="utf-8")

    archive = create_spec_backup(temp_git_repo, spec_name, reason="test")
    assert archive is not None

    (spec_dir / "spec.md").write_text("# current\n", encoding="utf-8")

    result = restore_spec_backup(temp_git_repo, spec_name, archive=archive)
    assert result.restored_paths == []
    assert spec_dir in result.skipped_paths
    assert (spec_dir / "spec.md").read_text(encoding="utf-8") == "# current\n"


def test_restore_spec_backup_overwrites_existing_paths(temp_git_repo):
    spec_name = "005-backup-restore-overwrite"

    spec_dir = temp_git_repo / ".auto-claude" / "specs" / spec_name
    spec_dir.mkdir(parents=True)
    (spec_dir / "spec.md").write_text("# archived\n", encoding="utf-8")

    archive = create_spec_backup(temp_git_repo, spec_name, reason="test")
    assert archive is not None

    (spec_dir / "spec.md").write_text("# modified\n", encoding="utf-8")

    result = restore_spec_backup(
        temp_git_repo,
        spec_name,
        archive=archive,
        overwrite=True,
    )

    assert spec_dir in result.restored_paths
    assert result.skipped_paths == []
    assert (spec_dir / "spec.md").read_text(encoding="utf-8") == "# archived\n"


def test_restore_spec_backup_rejects_unsafe_archive_entry(temp_git_repo):
    spec_name = "006-backup-unsafe"
    backup_dir = temp_git_repo / ".auto-claude" / "backups" / spec_name
    backup_dir.mkdir(parents=True)
    archive = backup_dir / "20260101T000000Z-unsafe.tar.gz"

    with tarfile.open(archive, mode="w:gz") as tar:
        info = tarfile.TarInfo(name="../escape.txt")
        payload = b"unsafe"
        info.size = len(payload)
        tar.addfile(info, fileobj=io.BytesIO(payload))

    with pytest.raises(ValueError, match="parent traversal"):
        restore_spec_backup(temp_git_repo, spec_name, archive=archive)


def test_restore_spec_backup_rejects_symlink_entries(temp_git_repo):
    spec_name = "007-backup-unsafe-symlink"
    backup_dir = temp_git_repo / ".auto-claude" / "backups" / spec_name
    backup_dir.mkdir(parents=True)
    archive = backup_dir / "20260101T000001Z-unsafe-symlink.tar.gz"

    with tarfile.open(archive, mode="w:gz") as tar:
        link = tarfile.TarInfo(name="spec/malicious-link")
        link.type = tarfile.SYMTYPE
        link.linkname = "../../outside"
        tar.addfile(link)

    with pytest.raises(ValueError, match="unsupported link type"):
        restore_spec_backup(temp_git_repo, spec_name, archive=archive)
