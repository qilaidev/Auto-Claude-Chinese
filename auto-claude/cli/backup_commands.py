"""
Backup Commands
===============

CLI commands for backup discovery and restore extraction.
"""

from pathlib import Path

from core.backup import extract_spec_backup, list_spec_backups
from ui import print_status


def handle_list_backups_command(project_dir: Path, spec_name: str) -> bool:
    """
    List available backup archives for a spec.

    Args:
        project_dir: Project root directory.
        spec_name: Spec name.

    Returns:
        True when at least one backup exists, otherwise False.
    """
    backups = list_spec_backups(project_dir, spec_name)
    if not backups:
        print()
        print_status(f"No backups found for spec '{spec_name}'.", "warning")
        return False

    print()
    print_status(f"Backups for '{spec_name}' (newest first):", "info")
    for idx, archive in enumerate(backups, start=1):
        rel = archive.relative_to(project_dir)
        print(f"  {idx:>2}. {rel}")
    return True


def handle_restore_backup_command(
    project_dir: Path,
    spec_name: str,
    archive: str | None = None,
    restore_dir: Path | None = None,
) -> bool:
    """
    Extract a backup archive to a restore directory.

    Args:
        project_dir: Project root directory.
        spec_name: Spec name.
        archive: Optional archive file name/path.
        restore_dir: Optional restore destination.

    Returns:
        True when extraction succeeds, otherwise False.
    """
    try:
        extracted = extract_spec_backup(
            project_dir=project_dir,
            spec_name=spec_name,
            archive=archive,
            restore_dir=restore_dir,
        )
    except (FileNotFoundError, OSError, ValueError) as exc:
        print()
        print_status(f"Restore failed: {exc}", "error")
        return False

    print()
    print_status("Backup extracted successfully.", "success")
    try:
        display_path = extracted.relative_to(project_dir)
    except ValueError:
        # restore_dir may be outside project root (absolute path chosen by operator)
        display_path = extracted

    print_status(f"Restore directory: {display_path}", "info")
    print_status(
        "Inspect files first, then copy back to live locations if needed.",
        "info",
    )
    return True
