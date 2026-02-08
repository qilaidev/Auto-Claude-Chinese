#!/usr/bin/env python3
"""
Tests for merge safety guards.
"""

from workspace import merge_existing_build


def test_merge_existing_build_blocks_dirty_worktree(temp_git_repo):
    spec_name = "001-dirty-merge"
    worktree_path = temp_git_repo / ".worktrees" / spec_name
    worktree_path.mkdir(parents=True)

    # Dirty main working tree
    (temp_git_repo / "README.md").write_text("changed\n", encoding="utf-8")

    result = merge_existing_build(temp_git_repo, spec_name)
    assert result is False

