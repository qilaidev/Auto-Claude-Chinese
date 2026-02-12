"""
Auto Claude CLI - Main Entry Point
===================================

Command-line interface for the Auto Claude autonomous coding framework.
"""

import argparse
import os
import sys
from pathlib import Path

# Ensure parent directory is in path for imports (before other imports)
_PARENT_DIR = Path(__file__).parent.parent
if str(_PARENT_DIR) not in sys.path:
    sys.path.insert(0, str(_PARENT_DIR))

from core.logging_setup import configure_logging
from ui import (
    Icons,
    icon,
)

from .backup_commands import (
    handle_list_backups_command,
    handle_restore_backup_command,
)
from .build_commands import handle_build_command
from .doctor_commands import handle_doctor_command
from .followup_commands import handle_followup_command
from .spec_commands import print_specs_list
from .utils import (
    DEFAULT_MODEL,
    find_spec,
    get_project_dir,
    print_banner,
    setup_environment,
)
from .workspace_commands import (
    handle_cleanup_worktrees_command,
    handle_discard_command,
    handle_list_worktrees_command,
    handle_merge_command,
    handle_review_command,
)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Auto Claude Framework - Autonomous multi-session coding agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all specs
  python auto-claude/run.py --list

  # Run a specific spec (by number or full name)
  python auto-claude/run.py --spec 001
  python auto-claude/run.py --spec 001-initial-app

  # Workspace management (after build completes)
  python auto-claude/run.py --spec 001 --merge     # Add build to your project
  python auto-claude/run.py --spec 001 --review    # See what was built
  python auto-claude/run.py --spec 001 --discard   # Delete build (with confirmation)

  # Advanced options
  python auto-claude/run.py --spec 001 --direct       # Skip workspace isolation
  python auto-claude/run.py --spec 001 --isolated     # Force workspace isolation

  # Status checks
  python auto-claude/run.py --spec 001 --review-status  # Check human review status
  python auto-claude/run.py --spec 001 --qa-status      # Check QA validation status

Prerequisites:
  1. Create a spec first: claude /spec
  2. Authenticate via one of:
     - OAuth: run 'claude setup-token'
     - Third-party: set ANTHROPIC_AUTH_TOKEN or ANTHROPIC_API_KEY in ~/.claude/settings.json

Environment Variables:
  CLAUDE_CODE_OAUTH_TOKEN  OAuth token (run: claude setup-token)
  ANTHROPIC_AUTH_TOKEN     Third-party auth token (e.g. yunyi)
  ANTHROPIC_API_KEY        Third-party API key
  AUTO_BUILD_MODEL         Override default model (optional)
        """,
    )

    parser.add_argument(
        "--list",
        action="store_true",
        help="List all available specs and their status",
    )

    parser.add_argument(
        "--doctor",
        action="store_true",
        help="Run production preflight doctor checks",
    )

    parser.add_argument(
        "--doctor-strict",
        action="store_true",
        help="With --doctor: treat warnings as failures",
    )

    parser.add_argument(
        "--spec",
        type=str,
        default=None,
        help="Spec to run (e.g., '001' or '001-feature-name')",
    )

    parser.add_argument(
        "--project-dir",
        type=Path,
        default=None,
        help="Project directory (default: current working directory)",
    )

    parser.add_argument(
        "--max-iterations",
        type=int,
        default=None,
        help="Maximum number of agent sessions (default: unlimited)",
    )

    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help=f"Claude model to use (default: {DEFAULT_MODEL})",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output",
    )

    # Workspace options
    workspace_group = parser.add_mutually_exclusive_group()
    workspace_group.add_argument(
        "--isolated",
        action="store_true",
        help="Force building in isolated workspace (safer)",
    )
    workspace_group.add_argument(
        "--direct",
        action="store_true",
        help="Build directly in your project (no isolation)",
    )

    # Build management commands
    build_group = parser.add_mutually_exclusive_group()
    build_group.add_argument(
        "--merge",
        action="store_true",
        help="Merge an existing build into your project",
    )
    build_group.add_argument(
        "--review",
        action="store_true",
        help="Review what an existing build contains",
    )
    build_group.add_argument(
        "--discard",
        action="store_true",
        help="Discard an existing build (requires confirmation)",
    )

    # Merge options
    parser.add_argument(
        "--no-commit",
        action="store_true",
        help="With --merge: stage changes but don't commit (review in IDE first)",
    )
    parser.add_argument(
        "--merge-preview",
        action="store_true",
        help="Preview merge conflicts without actually merging (returns JSON)",
    )

    # QA options
    parser.add_argument(
        "--qa",
        action="store_true",
        help="Run QA validation loop on a completed build",
    )
    parser.add_argument(
        "--qa-status",
        action="store_true",
        help="Show QA validation status for a spec",
    )
    parser.add_argument(
        "--skip-qa",
        action="store_true",
        help="Skip automatic QA validation after build completes",
    )

    # Follow-up options
    parser.add_argument(
        "--followup",
        action="store_true",
        help="Add follow-up tasks to a completed spec (extends existing implementation plan)",
    )

    # Review options
    parser.add_argument(
        "--review-status",
        action="store_true",
        help="Show human review/approval status for a spec",
    )

    # Dev mode (deprecated)
    parser.add_argument(
        "--dev",
        action="store_true",
        help="[Deprecated] No longer has any effect - kept for compatibility",
    )

    # Non-interactive mode (for UI/automation)
    parser.add_argument(
        "--auto-continue",
        action="store_true",
        help="Non-interactive mode: auto-continue existing builds, skip prompts (for UI integration)",
    )

    # Worktree management
    parser.add_argument(
        "--list-worktrees",
        action="store_true",
        help="List all spec worktrees and their status",
    )
    parser.add_argument(
        "--cleanup-worktrees",
        action="store_true",
        help="Remove all spec worktrees and their branches (with confirmation)",
    )

    # Backup & restore operations
    parser.add_argument(
        "--list-backups",
        action="store_true",
        help="List available pre-delete backups for a spec",
    )
    parser.add_argument(
        "--restore-backup",
        action="store_true",
        help="Extract a backup archive for a spec into a restore directory",
    )
    parser.add_argument(
        "--backup-archive",
        type=str,
        default=None,
        help="Backup archive file name or absolute path (defaults to latest)",
    )
    parser.add_argument(
        "--restore-dir",
        type=Path,
        default=None,
        help="Directory to extract backup into (default: .auto-claude/restores/<spec>/...)",
    )

    # Force bypass
    parser.add_argument(
        "--force",
        action="store_true",
        help="Skip approval check and start build anyway (for debugging)",
    )

    # Base branch for worktree creation
    parser.add_argument(
        "--base-branch",
        type=str,
        default=None,
        help="Base branch for creating worktrees (default: auto-detect or current branch)",
    )

    return parser.parse_args()


def _ensure_default_logging_env(project_dir: Path) -> None:
    """Set a safe default operational log directory when none is configured."""
    if os.environ.get("AUTO_CLAUDE_LOG_FILE") or os.environ.get("AUTO_CLAUDE_LOG_DIR"):
        return

    os.environ["AUTO_CLAUDE_LOG_DIR"] = str(project_dir / ".auto-claude" / "logs")


def main() -> None:
    """Main CLI entry point."""
    # Set up environment first
    setup_environment()

    # Parse arguments
    args = parse_args()

    # Import debug functions after environment setup
    from debug import debug, debug_error, debug_section, debug_success

    debug_section("run.py", "Starting Auto-Claude Framework")
    debug("run.py", "Arguments parsed", args=vars(args))

    # Determine project directory
    project_dir = get_project_dir(args.project_dir)
    _ensure_default_logging_env(project_dir)
    configure_logging(project_dir)
    debug("run.py", f"Using project directory: {project_dir}")

    # Get model (with env var fallback)
    model = args.model or os.environ.get("AUTO_BUILD_MODEL", DEFAULT_MODEL)

    # Note: --dev flag is deprecated but kept for API compatibility
    if args.dev:
        print(
            f"\n{icon(Icons.GEAR)} Note: --dev flag is deprecated. All specs now use .auto-claude/specs/\n"
        )

    # Handle --list command
    if args.list:
        print_banner()
        print_specs_list(project_dir, args.dev)
        return

    # Handle --list-worktrees command
    if args.list_worktrees:
        handle_list_worktrees_command(project_dir)
        return

    # Handle --cleanup-worktrees command
    if args.cleanup_worktrees:
        handle_cleanup_worktrees_command(project_dir)
        return

    # Handle backup commands (require --spec)
    if args.list_backups or args.restore_backup:
        if not args.spec:
            print_banner()
            print("\nError: --spec is required for backup commands")
            print("\nUsage:")
            print("  python auto-claude/run.py --spec 001 --list-backups")
            print(
                "  python auto-claude/run.py --spec 001 --restore-backup --backup-archive <archive>"
            )
            sys.exit(1)

        spec_dir = find_spec(project_dir, args.spec, args.dev)
        if not spec_dir:
            print_banner()
            print(f"\nError: Spec '{args.spec}' not found")
            sys.exit(1)

        if args.list_backups:
            success = handle_list_backups_command(project_dir, spec_dir.name)
        else:
            success = handle_restore_backup_command(
                project_dir=project_dir,
                spec_name=spec_dir.name,
                archive=args.backup_archive,
                restore_dir=args.restore_dir,
            )
        if not success:
            sys.exit(1)
        return

    # Handle doctor command (spec optional)
    if args.doctor:
        spec_dir = None
        if args.spec:
            spec_dir = find_spec(project_dir, args.spec, args.dev)
            if not spec_dir:
                print_banner()
                print(f"\nWarning: Spec '{args.spec}' not found for doctor check.")
        success = handle_doctor_command(
            project_dir=project_dir,
            spec_dir=spec_dir,
            spec_identifier=args.spec,
            strict=args.doctor_strict,
        )
        if not success:
            sys.exit(1)
        return

    # Require --spec if not listing
    if not args.spec:
        print_banner()
        print("\nError: --spec is required")
        print("\nUsage:")
        print("  python auto-claude/run.py --list           # See all specs")
        print("  python auto-claude/run.py --spec 001       # Run a spec")
        print("\nCreate a new spec with:")
        print("  claude /spec")
        sys.exit(1)

    # Find the spec
    debug("run.py", "Finding spec", spec_identifier=args.spec, dev_mode=args.dev)
    spec_dir = find_spec(project_dir, args.spec, args.dev)
    if not spec_dir:
        debug_error("run.py", "Spec not found", spec=args.spec)
        print_banner()
        print(f"\nError: Spec '{args.spec}' not found")
        print("\nAvailable specs:")
        print_specs_list(project_dir, args.dev)
        sys.exit(1)

    debug_success("run.py", "Spec found", spec_dir=str(spec_dir))

    # Handle build management commands
    if args.merge_preview:
        from cli.workspace_commands import handle_merge_preview_command

        result = handle_merge_preview_command(project_dir, spec_dir.name)
        # Output as JSON for the UI to parse
        import json

        print(json.dumps(result))
        return

    if args.merge:
        success = handle_merge_command(
            project_dir, spec_dir.name, no_commit=args.no_commit
        )
        if not success:
            sys.exit(1)
        return

    if args.review:
        handle_review_command(project_dir, spec_dir.name)
        return

    if args.discard:
        handle_discard_command(project_dir, spec_dir.name)
        return

    # Handle QA commands
    if args.qa_status:
        from .qa_commands import handle_qa_status_command

        handle_qa_status_command(spec_dir)
        return

    if args.review_status:
        from .qa_commands import handle_review_status_command

        handle_review_status_command(spec_dir)
        return

    if args.qa:
        from .qa_commands import handle_qa_command

        handle_qa_command(
            project_dir=project_dir,
            spec_dir=spec_dir,
            model=model,
            verbose=args.verbose,
        )
        return

    # Handle --followup command
    if args.followup:
        handle_followup_command(
            project_dir=project_dir,
            spec_dir=spec_dir,
            model=model,
            verbose=args.verbose,
        )
        return

    # Normal build flow
    handle_build_command(
        project_dir=project_dir,
        spec_dir=spec_dir,
        model=model,
        max_iterations=args.max_iterations,
        verbose=args.verbose,
        force_isolated=args.isolated,
        force_direct=args.direct,
        auto_continue=args.auto_continue,
        skip_qa=args.skip_qa,
        force_bypass_approval=args.force,
        base_branch=args.base_branch,
    )


if __name__ == "__main__":
    main()
