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
import shutil
import tarfile
from datetime import datetime, timezone
from pathlib import Path

AUTO_BACKUP_DISABLE_ENV = "AUTO_CLAUDE_DISABLE_AUTO_BACKUP"
MAX_BACKUPS_ENV = "AUTO_CLAUDE_MAX_BACKUPS_PER_SPEC"
DEFAULT_MAX_BACKUPS = 20
_RESTORE_SAFE_ROOTS = {"spec", "worktree", "backup_metadata.json"}


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


def _resolve_archive_path(
    project_dir: Path, spec_name: str, archive: str | Path | None
) -> Path:
    """Resolve an archive path (explicit path or latest backup for spec)."""
    if archive:
        candidate = Path(archive)
        if candidate.is_absolute():
            archive_path = candidate
        else:
            archive_path = get_spec_backups_dir(project_dir, spec_name) / candidate
    else:
        backups = list_spec_backups(project_dir, spec_name)
        if not backups:
            raise FileNotFoundError(
                f"No backups found for spec '{spec_name}' in "
                f"{get_spec_backups_dir(project_dir, spec_name)}"
            )
        archive_path = backups[0]

    if not archive_path.exists() or not archive_path.is_file():
        raise FileNotFoundError(f"Backup archive not found: {archive_path}")
    return archive_path


def _validate_member(member: tarfile.TarInfo) -> None:
    """
    Validate archive member metadata to avoid traversal/link extraction attacks.
    """
    member_path = Path(member.name)
    if member_path.is_absolute() or ".." in member_path.parts:
        raise ValueError(f"Unsafe archive entry: {member.name}")

    top_level = member_path.parts[0] if member_path.parts else ""
    if top_level not in _RESTORE_SAFE_ROOTS:
        raise ValueError(f"Unexpected archive entry: {member.name}")

    # Explicitly reject link-like members to avoid writing outside restore_dir.
    if member.issym() or member.islnk():
        raise ValueError(f"Link entries are not allowed in backup: {member.name}")


def extract_spec_backup(
    project_dir: Path,
    spec_name: str,
    *,
    archive: str | Path | None = None,
    restore_dir: Path | None = None,
) -> Path:
    """
    Extract a spec backup archive into a dedicated restore directory.

    Args:
        project_dir: Project root directory.
        spec_name: Spec name.
        archive: Optional archive name/path. When omitted, restore latest backup.
        restore_dir: Optional extraction destination.

    Returns:
        Extraction directory path.
    """
    project_dir = Path(project_dir)
    archive_path = _resolve_archive_path(project_dir, spec_name, archive)

    if restore_dir is None:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        restore_dir = (
            project_dir
            / ".auto-claude"
            / "restores"
            / _sanitize_label(spec_name)
            / f"{timestamp}-{archive_path.stem.replace('.tar', '')}"
        )
    else:
        restore_dir = Path(restore_dir)

    # Recreate target to ensure deterministic contents.
    if restore_dir.exists():
        shutil.rmtree(restore_dir)
    restore_dir.mkdir(parents=True, exist_ok=True)

    with tarfile.open(archive_path, mode="r:gz") as tar:
        members = tar.getmembers()
        for member in members:
            _validate_member(member)
        tar.extractall(path=restore_dir, members=members)

    return restore_dir
