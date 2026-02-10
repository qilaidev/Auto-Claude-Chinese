"""
Backup Commands
===============

CLI commands for backup discovery and restoration.
"""

from __future__ import annotations

import re
from pathlib import Path

from core.backup import (
    create_spec_backup,
    list_spec_backups,
    read_backup_metadata,
    restore_spec_backup,
)
from ui import (
    Icons,
    bold,
    box,
    highlight,
    icon,
    info,
    muted,
    print_status,
    success,
    warning,
)


def _available_backup_specs(project_dir: Path) -> list[str]:
    """Return available spec backup directories."""
    backups_root = project_dir / ".auto-claude" / "backups"
    if not backups_root.exists():
        return []

    return sorted(path.name for path in backups_root.iterdir() if path.is_dir())


def resolve_backup_spec_name(
    project_dir: Path,
    spec_identifier: str,
    resolved_spec_dir: Path | None = None,
) -> str:
    """
    Resolve a spec identifier for backup operations.

    Priority:
    1. Use resolved spec dir name when available.
    2. Exact backup directory name match.
    3. Numeric ID prefix match (e.g. `001` -> `001-feature`) when unique.
    4. Fall back to the raw identifier.
    """
    if resolved_spec_dir is not None:
        return resolved_spec_dir.name

    normalized = spec_identifier.strip()
    if not normalized:
        raise ValueError("Spec identifier cannot be empty.")

    available_specs = _available_backup_specs(project_dir)
    if normalized in available_specs:
        return normalized

    if re.fullmatch(r"\d+", normalized):
        matches = [
            name for name in available_specs if name.startswith(f"{normalized}-")
        ]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            choices = ", ".join(matches)
            raise ValueError(
                f"Spec '{normalized}' is ambiguous for backups. Use one of: {choices}"
            )

    return normalized


def handle_list_backups_command(project_dir: Path, spec_name: str) -> bool:
    """
    List backup archives for a spec.

    Args:
        project_dir: Project root directory.
        spec_name: Resolved spec name.

    Returns:
        True when command executed successfully.
    """
    archives = list_spec_backups(project_dir, spec_name)

    print()
    content = [
        bold(f"{icon(Icons.FILE)} BACKUP ARCHIVES"),
        muted(f"Spec: {spec_name}"),
    ]
    print(box(content, width=76, style="heavy"))

    if not archives:
        print()
        print_status("No backups found for this spec.", "info")
        print(muted("Backups are created automatically before discard/cleanup actions."))
        return True

    for index, archive_path in enumerate(archives, start=1):
        try:
            display_path = archive_path.relative_to(project_dir)
        except ValueError:
            display_path = archive_path

        metadata = read_backup_metadata(archive_path)
        if metadata:
            timestamp = metadata.get("timestamp", "unknown time")
            reason = metadata.get("reason", "unknown")
            contents = metadata.get("contents", [])
            contents_text = ", ".join(contents) if contents else "unknown"
            print(
                f"  {index:>2}. {display_path}"
                f"\n      reason={reason} time={timestamp} contents={contents_text}"
            )
        else:
            print(
                f"  {index:>2}. {display_path}"
                "\n      metadata=unreadable (archive may be corrupted)"
            )

    print()
    print(info(f"{icon(Icons.INFO)} Newest backup is listed first."))
    return True


def _confirm_restore(spec_name: str, archive: Path, overwrite: bool) -> bool:
    """Prompt user for restore confirmation."""
    print()
    content = [
        bold(f"{icon(Icons.WARNING)} RESTORE BACKUP"),
        "",
        f"Spec: {spec_name}",
        f"Archive: {archive}",
    ]

    if overwrite:
        content.extend(
            [
                "",
                warning("Overwrite mode enabled: existing spec/worktree data will be replaced."),
            ]
        )

    print(box(content, width=76, style="heavy"))
    print()
    print(f"Type {highlight('restore')} to continue: ", end="")

    try:
        return input().strip().lower() == "restore"
    except KeyboardInterrupt:
        print()
        return False


def handle_restore_backup_command(
    project_dir: Path,
    spec_name: str,
    *,
    archive: Path | None = None,
    overwrite: bool = False,
    auto_confirm: bool = False,
) -> bool:
    """
    Restore spec/worktree data from backup archive.

    Args:
        project_dir: Project root directory.
        spec_name: Resolved spec name.
        archive: Optional archive path. When omitted, use latest.
        overwrite: Replace existing destination paths.
        auto_confirm: Skip interactive confirmation.

    Returns:
        True when restore succeeds.
    """
    archives = list_spec_backups(project_dir, spec_name)
    if archive is None:
        if not archives:
            print()
            print_status(f"No backups found for '{spec_name}'.", "error")
            return False
        selected_archive = archives[0]
    else:
        selected_archive = archive
        if not selected_archive.is_absolute():
            selected_archive = project_dir / selected_archive

    if overwrite:
        safety_backup = create_spec_backup(project_dir, spec_name, reason="pre-restore")
        if safety_backup:
            try:
                display_backup = safety_backup.relative_to(project_dir)
            except ValueError:
                display_backup = safety_backup
            print()
            print_status(
                f"Safety backup created before overwrite: {display_backup}",
                "info",
            )

    if not auto_confirm and not _confirm_restore(spec_name, selected_archive, overwrite):
        print()
        print_status("Restore cancelled.", "info")
        return False

    try:
        result = restore_spec_backup(
            project_dir,
            spec_name,
            archive=selected_archive,
            overwrite=overwrite,
        )
    except (FileNotFoundError, ValueError, OSError) as exc:
        print()
        print_status(f"Restore failed: {exc}", "error")
        return False

    print()
    print(success(f"{icon(Icons.SUCCESS)} Restore completed."))

    try:
        display_archive = result.archive_path.relative_to(project_dir)
    except ValueError:
        display_archive = result.archive_path
    print(muted(f"Archive used: {display_archive}"))

    if result.restored_paths:
        for path in result.restored_paths:
            try:
                display_path = path.relative_to(project_dir)
            except ValueError:
                display_path = path
            print(f"  - Restored: {display_path}")

    if result.skipped_paths:
        print()
        skipped_hint = (
            f"{icon(Icons.WARNING)} Skipped existing paths "
            "(use --overwrite-existing to replace):"
        )
        print(
            warning(skipped_hint)
        )
        for path in result.skipped_paths:
            try:
                display_path = path.relative_to(project_dir)
            except ValueError:
                display_path = path
            print(f"  - {display_path}")

        if not result.restored_paths:
            return False

    return True
