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
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

AUTO_BACKUP_DISABLE_ENV = "AUTO_CLAUDE_DISABLE_AUTO_BACKUP"
MAX_BACKUPS_ENV = "AUTO_CLAUDE_MAX_BACKUPS_PER_SPEC"
DEFAULT_MAX_BACKUPS = 20
ALLOWED_BACKUP_TOP_LEVELS = {"spec", "worktree", "backup_metadata.json"}


@dataclass
class BackupRestoreResult:
    """Result of restoring a spec backup archive."""

    archive_path: Path
    restored_paths: list[Path]
    skipped_paths: list[Path]


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


def _preferred_spec_dir(project_dir: Path, spec_name: str) -> Path:
    """Return preferred target path for restored spec data."""
    existing = _resolve_spec_dir(project_dir, spec_name)
    if existing:
        return existing
    return project_dir / ".auto-claude" / "specs" / spec_name


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


def read_backup_metadata(archive_path: Path) -> dict | None:
    """Read metadata from a backup archive."""
    archive_path = Path(archive_path)

    try:
        with tarfile.open(archive_path, mode="r:gz") as tar:
            member = tar.getmember("backup_metadata.json")
            metadata_file = tar.extractfile(member)
            if metadata_file is None:
                return None
            with metadata_file:
                return json.loads(metadata_file.read().decode("utf-8"))
    except (OSError, tarfile.TarError, KeyError, json.JSONDecodeError, UnicodeDecodeError):
        return None


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


def _normalize_backup_member(member_name: str) -> tuple[str, Path] | None:
    """Map an archive member to a logical backup component and relative path."""
    member_path = PurePosixPath(member_name)
    if member_path.is_absolute():
        raise ValueError(f"Backup entry must be relative: {member_name}")

    if any(part == ".." for part in member_path.parts):
        raise ValueError(f"Backup entry contains parent traversal: {member_name}")

    if not member_path.parts:
        return None

    top_level = member_path.parts[0]
    if top_level not in ALLOWED_BACKUP_TOP_LEVELS:
        raise ValueError(f"Unexpected backup entry: {member_name}")

    if top_level == "backup_metadata.json":
        return None

    relative = Path(*member_path.parts[1:]) if len(member_path.parts) > 1 else Path()
    return top_level, relative


def _is_within_directory(path: Path, root: Path) -> bool:
    """Return whether `path` is inside `root` after resolution."""
    resolved_root = root.resolve()
    resolved_path = path.resolve()
    return resolved_path == resolved_root or resolved_root in resolved_path.parents


def _remove_path(path: Path) -> None:
    """Remove file system path regardless of file type."""
    if path.is_dir():
        shutil.rmtree(path)
        return
    path.unlink()


def _resolve_backup_archive(project_dir: Path, spec_name: str, archive: Path | None) -> Path:
    """Resolve backup archive path with latest-backup fallback."""
    if archive is not None:
        archive_path = Path(archive)
    else:
        backups = list_spec_backups(project_dir, spec_name)
        if not backups:
            raise FileNotFoundError(
                f"No backups found for spec '{spec_name}'."
            )
        archive_path = backups[0]

    if not archive_path.is_absolute():
        archive_path = project_dir / archive_path

    if not archive_path.exists() or not archive_path.is_file():
        raise FileNotFoundError(f"Backup archive not found: {archive_path}")

    return archive_path


def restore_spec_backup(
    project_dir: Path,
    spec_name: str,
    *,
    archive: Path | None = None,
    overwrite: bool = False,
) -> BackupRestoreResult:
    """
    Restore spec/worktree data from a backup archive.

    When `archive` is omitted, the newest backup for the spec is used.
    Existing destinations are skipped unless `overwrite=True`.
    """
    project_dir = Path(project_dir)
    archive_path = _resolve_backup_archive(project_dir, spec_name, archive)

    metadata = read_backup_metadata(archive_path)
    if metadata:
        metadata_spec = str(metadata.get("spec_name", "")).strip()
        if metadata_spec and metadata_spec != spec_name:
            raise ValueError(
                "Backup spec mismatch: "
                f"archive belongs to '{metadata_spec}', requested '{spec_name}'."
            )

    targets = {
        "spec": _preferred_spec_dir(project_dir, spec_name),
        "worktree": project_dir / ".worktrees" / spec_name,
    }

    component_members: dict[str, list[tuple[tarfile.TarInfo, Path]]] = {
        "spec": [],
        "worktree": [],
    }

    with tarfile.open(archive_path, mode="r:gz") as tar:
        for member in tar.getmembers():
            normalized = _normalize_backup_member(member.name)
            if normalized is None:
                continue

            component, relative_path = normalized
            component_members[component].append((member, relative_path))

        components_present = {
            name for name, members in component_members.items() if members
        }
        if not components_present:
            raise ValueError(f"Backup archive has no restorable data: {archive_path}")

        components_to_restore: set[str] = set()
        skipped_paths: list[Path] = []

        for component in components_present:
            target_root = targets[component]
            if target_root.exists():
                if overwrite:
                    _remove_path(target_root)
                    components_to_restore.add(component)
                else:
                    skipped_paths.append(target_root)
            else:
                components_to_restore.add(component)

        restored_paths: list[Path] = []

        for component in components_to_restore:
            target_root = targets[component]
            target_root.mkdir(parents=True, exist_ok=True)

            for member, relative_path in component_members[component]:
                destination = (
                    target_root if relative_path == Path() else target_root / relative_path
                )

                if not _is_within_directory(destination, target_root):
                    raise ValueError(
                        f"Unsafe backup entry outside target directory: {member.name}"
                    )

                if member.isdir():
                    destination.mkdir(parents=True, exist_ok=True)
                    continue

                if member.issym() or member.islnk():
                    raise ValueError(
                        f"Backup entry uses unsupported link type: {member.name}"
                    )

                if not member.isfile():
                    raise ValueError(
                        f"Backup entry uses unsupported file type: {member.name}"
                    )

                destination.parent.mkdir(parents=True, exist_ok=True)
                source_file = tar.extractfile(member)
                if source_file is None:
                    raise ValueError(f"Could not read backup entry: {member.name}")

                with source_file, open(destination, "wb") as target_file:
                    shutil.copyfileobj(source_file, target_file)

            restored_paths.append(target_root)

    return BackupRestoreResult(
        archive_path=archive_path,
        restored_paths=restored_paths,
        skipped_paths=skipped_paths,
    )
