"""
Validation Module
=================

Spec validation with auto-fix capabilities.
"""

from datetime import datetime
from pathlib import Path

from core.file_io import atomic_write_json


def create_minimal_research(spec_dir: Path, reason: str = "No research needed") -> Path:
    """Create minimal research.json file (atomic write)."""
    research_file = spec_dir / "research.json"

    atomic_write_json(
        research_file,
        {
            "integrations_researched": [],
            "research_skipped": True,
            "reason": reason,
            "created_at": datetime.now().isoformat(),
        },
        indent=2,
    )

    return research_file


def create_minimal_critique(
    spec_dir: Path, reason: str = "Critique not required"
) -> Path:
    """Create minimal critique_report.json file (atomic write)."""
    critique_file = spec_dir / "critique_report.json"

    atomic_write_json(
        critique_file,
        {
            "issues_found": [],
            "no_issues_found": True,
            "critique_summary": reason,
            "created_at": datetime.now().isoformat(),
        },
        indent=2,
    )

    return critique_file


def create_empty_hints(spec_dir: Path, enabled: bool, reason: str) -> Path:
    """Create empty graph_hints.json file (atomic write)."""
    hints_file = spec_dir / "graph_hints.json"

    atomic_write_json(
        hints_file,
        {
            "enabled": enabled,
            "reason": reason,
            "hints": [],
            "created_at": datetime.now().isoformat(),
        },
        indent=2,
    )

    return hints_file
