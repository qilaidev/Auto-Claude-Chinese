"""
CLI Utilities
==============

Shared utility functions for the Auto Claude CLI.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

# Ensure parent directory is in path for imports (before other imports)
_PARENT_DIR = Path(__file__).parent.parent
if str(_PARENT_DIR) not in sys.path:
    sys.path.insert(0, str(_PARENT_DIR))

from core.auth import get_auth_token, get_auth_token_source
from dotenv import load_dotenv
from graphiti_config import get_graphiti_status
from init import init_auto_claude_dir
from ui import (
    Icons,
    bold,
    box,
    icon,
    muted,
)

# Configuration
DEFAULT_MODEL = "claude-opus-4-5-20251101"


def get_specs_dir(project_dir: Path, dev_mode: bool = False) -> Path:
    """Return the spec directory path under .auto-claude/."""
    del dev_mode
    init_auto_claude_dir(project_dir)
    return project_dir / ".auto-claude" / "specs"


def setup_environment() -> Path:
    """
    Set up the environment and return the script directory.

    Returns:
        Path to the auto-claude directory
    """
    # Add auto-claude directory to path for imports
    script_dir = Path(__file__).parent.parent.resolve()
    sys.path.insert(0, str(script_dir))

    # Load .env file - check both auto-claude/ and dev/auto-claude/ locations
    env_file = script_dir / ".env"
    dev_env_file = script_dir.parent / "dev" / "auto-claude" / ".env"
    if env_file.exists():
        load_dotenv(env_file)
    elif dev_env_file.exists():
        load_dotenv(dev_env_file)

    return script_dir


def find_spec(
    project_dir: Path, spec_identifier: str, dev_mode: bool = False
) -> Path | None:
    """
    Find a spec by number or full name.

    Args:
        project_dir: Project root directory
        spec_identifier: Either "001" or "001-feature-name"
        dev_mode: If True, use dev/auto-claude/specs/

    Returns:
        Path to spec folder, or None if not found
    """
    specs_dir = get_specs_dir(project_dir, dev_mode)

    if not specs_dir.exists():
        return None

    # Try exact match first
    exact_path = specs_dir / spec_identifier
    if exact_path.exists() and (exact_path / "spec.md").exists():
        return exact_path

    # Try matching by number prefix
    for spec_folder in specs_dir.iterdir():
        if spec_folder.is_dir() and spec_folder.name.startswith(spec_identifier + "-"):
            if (spec_folder / "spec.md").exists():
                return spec_folder

    return None


def _has_command(command: str) -> bool:
    """Check if a command is available on PATH."""
    return shutil.which(command) is not None


def _is_git_repo(project_dir: Path) -> bool:
    """Check if a directory is inside a git work tree."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode == 0 and result.stdout.strip() == "true"
    except OSError:
        return False


def validate_environment(spec_dir: Path, project_dir: Path | None = None) -> bool:
    """
    Validate that the environment is set up correctly.

    Args:
        spec_dir: Spec directory path
        project_dir: Project root directory (for git checks)

    Returns:
        True if valid, False otherwise (with error messages printed)
    """
    valid = True

    # Check for required CLI tools
    if not _has_command("git"):
        print("Error: git is not installed or not on PATH.")
        print("Install Git: https://git-scm.com/downloads")
        valid = False
    elif project_dir and not _is_git_repo(project_dir):
        print("Error: project directory is not a git repository.")
        print(f"Path: {project_dir}")
        print("Initialize git:")
        print("  git init")
        valid = False

    if not _has_command("claude"):
        print("Error: Claude Code CLI ('claude') not found on PATH.")
        print("Install: npm install -g @anthropic-ai/claude-code")
        valid = False

    # Enforce writable project directory early to avoid runtime failures.
    if project_dir:
        try:
            project_dir.mkdir(parents=True, exist_ok=True)
            probe = project_dir / ".auto-claude" / ".write-check"
            probe.parent.mkdir(parents=True, exist_ok=True)
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
        except OSError as e:
            print("Error: project directory is not writable for Auto Claude.")
            print(f"Path: {project_dir}")
            print(f"Reason: {e}")
            valid = False

    # Check for auth token (OAuth, ANTHROPIC_AUTH_TOKEN, or ANTHROPIC_API_KEY)
    if not get_auth_token():
        print("Error: No auth token found")
        print("\nAuto Claude requires authentication.")
        print("Supported methods:")
        print("  - OAuth: run 'claude setup-token'")
        print("  - Third-party: set ANTHROPIC_AUTH_TOKEN or ANTHROPIC_API_KEY in ~/.claude/settings.json")
        valid = False
    else:
        # Show which auth source is being used
        source = get_auth_token_source()
        if source:
            print(f"Auth: {source}")

        # Show custom base URL if set
        base_url = os.environ.get("ANTHROPIC_BASE_URL")
        if base_url:
            print(f"API Endpoint: {base_url}")

    # Check for spec.md in spec directory
    spec_file = spec_dir / "spec.md"
    if not spec_file.exists():
        print(f"\nError: spec.md not found in {spec_dir}")
        valid = False

    # Validate critical write targets inside spec directory.
    try:
        spec_dir.mkdir(parents=True, exist_ok=True)
        spec_probe = spec_dir / ".write-check"
        spec_probe.write_text("ok", encoding="utf-8")
        spec_probe.unlink(missing_ok=True)
    except OSError as e:
        print(f"\nError: spec directory is not writable: {spec_dir}")
        print(f"Reason: {e}")
        valid = False

    # Check Linear integration (optional but show status)
    if os.environ.get("LINEAR_API_KEY"):
        print("Linear integration: ENABLED")
        try:
            from linear_integration import LinearManager

            linear_manager = LinearManager(spec_dir, spec_dir.parent.parent)
            if linear_manager.is_initialized:
                summary = linear_manager.get_progress_summary()
                print(f"  Project: {summary.get('project_name', 'Unknown')}")
                print(
                    f"  Issues: {summary.get('mapped_subtasks', 0)}/{summary.get('total_subtasks', 0)} mapped"
                )
            else:
                print("  Status: Will be initialized during planner session")
        except Exception as linear_error:
            print(
                "  Status: unavailable "
                f"({type(linear_error).__name__}: {linear_error})"
            )
    else:
        print("Linear integration: DISABLED (set LINEAR_API_KEY to enable)")

    # Check Graphiti integration (optional but show status)
    graphiti_status = get_graphiti_status()
    if graphiti_status["available"]:
        print("Graphiti memory: ENABLED")
        print(f"  Database: {graphiti_status['database']}")
        print(f"  Host: {graphiti_status['host']}:{graphiti_status['port']}")
    elif graphiti_status["enabled"]:
        print(
            f"Graphiti memory: CONFIGURED but unavailable ({graphiti_status['reason']})"
        )
    else:
        print("Graphiti memory: DISABLED (set GRAPHITI_ENABLED=true to enable)")

    print()
    return valid


def print_banner() -> None:
    """Print the Auto-Claude banner."""
    content = [
        bold(f"{icon(Icons.LIGHTNING)} AUTO-BUILD FRAMEWORK"),
        "",
        "Autonomous Multi-Session Coding Agent",
        muted("Subtask-Based Implementation with Phase Dependencies"),
    ]
    print()
    print(box(content, width=70, style="heavy"))


def get_project_dir(provided_dir: Path | None) -> Path:
    """
    Determine the project directory.

    Args:
        provided_dir: User-provided project directory (or None)

    Returns:
        Resolved project directory path
    """
    if provided_dir:
        return provided_dir.resolve()

    project_dir = Path.cwd()

    # Auto-detect if running from within auto-claude directory (the source code)
    if project_dir.name == "auto-claude" and (project_dir / "run.py").exists():
        # Running from within auto-claude/ source directory, go up 1 level
        project_dir = project_dir.parent

    return project_dir
