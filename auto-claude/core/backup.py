"""
Backup helpers for production-safe operations.

This module provides lightweight, local filesystem backups for spec/worktree
data before destructive operations (discard/cleanup). The goal is to make
rollback easy without introducing external dependencies.
"""

from __future__ import annotations

import io
import json
import os
import re
import tarfile
from datetime import datetime, timezone
from pathlib import Path

AUTO_BACKUP_DISABLE_ENV = "AUTO_CLAUDE_DISABLE_AUTO_BACKUP"
MAX_BACKUPS_ENV = "AUTO_CLAUDE_MAX_BACKUPS_PER_SPEC"
DEFAULT_MAX_BACKUPS = 20


def is_auto_backup_enabled() -> bool:
    """Return whether automatic pre-delete backup is enabled."""
    value = os.environ.get(AUTO_BACKUP_DISABLE_ENV, "").strip().lower()
    return value not in {"1", "true", "yes", "on"}


def _safe_int_env(name: str, default: int) -> int:
    """Read a positive integer environment variable with fallback."""
    value = os.environ.get(name)
    if not value:
        return default

    try:
        parsed = int(value)
    except ValueError:
        return default

    if parsed <= 0:
        return default
    return parsed


def _sanitize_label(value: str) -> str:
    """Sanitize labels used in file names."""
    sanitized = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip())
    return sanitized.strip("-_.") or "unknown"


def _resolve_spec_dir(project_dir: Path, spec_name: str) -> Path | None:
    """Resolve spec directory across supported layouts."""
    candidates = [
        project_dir / ".auto-claude" / "specs" / spec_name,
        project_dir / "auto-claude" / "specs" / spec_name,
    ]

    for candidate in candidates:
        if candidate.exists() and candidate.is_dir():
            return candidate
    return None


def get_spec_backups_dir(project_dir: Path, spec_name: str) -> Path:
    """Return backup directory path for a specific spec."""
    return project_dir / ".auto-claude" / "backups" / _sanitize_label(spec_name)


def list_spec_backups(project_dir: Path, spec_name: str) -> list[Path]:
    """List backup archives for a spec from newest to oldest."""
    backup_dir = get_spec_backups_dir(project_dir, spec_name)
    if not backup_dir.exists():
        return []

    archives = sorted(backup_dir.glob("*.tar.gz"), key=lambda path: path.name)
    return list(reversed(archives))


def _prune_old_backups(backup_dir: Path) -> None:
    """Remove older backups beyond retention threshold."""
    max_backups = _safe_int_env(MAX_BACKUPS_ENV, DEFAULT_MAX_BACKUPS)
    archives = sorted(backup_dir.glob("*.tar.gz"), key=lambda path: path.name)
    to_delete = archives[:-max_backups]

    for archive in to_delete:
        try:
            archive.unlink()
        except OSError:
            continue


def create_spec_backup(project_dir: Path, spec_name: str, reason: str) -> Path | None:
    """
    Create a compressed backup archive for one spec.

    Args:
        project_dir: Project root directory.
        spec_name: Spec name used in `.auto-claude/specs/<spec_name>`.
        reason: Backup reason, e.g. `discard` or `cleanup`.

    Returns:
        Path to created archive, or None when there is no data to back up.
    """
    project_dir = Path(project_dir)
    spec_dir = _resolve_spec_dir(project_dir, spec_name)
    worktree_dir = project_dir / ".worktrees" / spec_name

    backup_items: list[tuple[Path, str]] = []
    if spec_dir and spec_dir.exists():
        backup_items.append((spec_dir, "spec"))
    if worktree_dir.exists():
        backup_items.append((worktree_dir, "worktree"))

    if not backup_items:
        return None

    backup_dir = get_spec_backups_dir(project_dir, spec_name)
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive_name = (
        f"{timestamp}-{_sanitize_label(spec_name)}-{_sanitize_label(reason)}.tar.gz"
    )
    archive_path = backup_dir / archive_name

    metadata = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "spec_name": spec_name,
        "reason": reason,
        "project_dir": str(project_dir),
        "contents": [label for _, label in backup_items],
    }

    with tarfile.open(archive_path, mode="w:gz") as tar:
        for source, label in backup_items:
            tar.add(source, arcname=label)

        metadata_bytes = json.dumps(metadata, indent=2, ensure_ascii=False).encode(
            "utf-8"
        )
        metadata_info = tarfile.TarInfo("backup_metadata.json")
        metadata_info.size = len(metadata_bytes)
        metadata_info.mtime = int(datetime.now(timezone.utc).timestamp())
        tar.addfile(metadata_info, io.BytesIO(metadata_bytes))

    _prune_old_backups(backup_dir)
    return archive_path

