#!/usr/bin/env python3
"""
Tests for backup helpers.
"""

import json
import tarfile

from core.backup import create_spec_backup, list_spec_backups


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

