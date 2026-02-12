#!/usr/bin/env python3
"""
Tests for backup helpers.
"""

import json
import io
import tarfile

from core.backup import create_spec_backup, extract_spec_backup, list_spec_backups


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


def test_extract_spec_backup_uses_latest_archive(temp_git_repo):
    spec_name = "003-backup-restore"
    spec_dir = temp_git_repo / ".auto-claude" / "specs" / spec_name
    spec_dir.mkdir(parents=True)
    (spec_dir / "spec.md").write_text("# spec\n", encoding="utf-8")

    archive_path = create_spec_backup(temp_git_repo, spec_name, reason="discard")
    assert archive_path is not None

    restore_dir = extract_spec_backup(temp_git_repo, spec_name)

    restored_spec = restore_dir / "spec" / "spec.md"
    restored_metadata = restore_dir / "backup_metadata.json"
    assert restored_spec.exists()
    assert restored_spec.read_text(encoding="utf-8") == "# spec\n"
    assert restored_metadata.exists()


def test_extract_spec_backup_rejects_unsafe_paths(temp_git_repo):
    spec_name = "004-backup-unsafe"
    backup_dir = temp_git_repo / ".auto-claude" / "backups" / spec_name
    backup_dir.mkdir(parents=True)
    malicious_archive = backup_dir / "20260101T000000Z-unsafe-discard.tar.gz"

    with tarfile.open(malicious_archive, mode="w:gz") as tar:
        info = tarfile.TarInfo("../../etc/passwd")
        payload = b"bad"
        info.size = len(payload)
        tar.addfile(info, fileobj=io.BytesIO(payload))

    try:
        extract_spec_backup(temp_git_repo, spec_name, archive=malicious_archive)
    except ValueError as exc:
        assert "Unsafe archive entry" in str(exc)
    else:
        raise AssertionError("Expected ValueError for unsafe archive member")


def test_extract_spec_backup_rejects_symlink_entries(temp_git_repo):
    spec_name = "005-backup-symlink"
    backup_dir = temp_git_repo / ".auto-claude" / "backups" / spec_name
    backup_dir.mkdir(parents=True)
    symlink_archive = backup_dir / "20260101T000000Z-symlink-discard.tar.gz"

    with tarfile.open(symlink_archive, mode="w:gz") as tar:
        info = tarfile.TarInfo("spec/link-out")
        info.type = tarfile.SYMTYPE
        info.linkname = "../../outside"
        tar.addfile(info)

    try:
        extract_spec_backup(temp_git_repo, spec_name, archive=symlink_archive)
    except ValueError as exc:
        assert "Link entries are not allowed" in str(exc)
    else:
        raise AssertionError("Expected ValueError for symlink archive member")
