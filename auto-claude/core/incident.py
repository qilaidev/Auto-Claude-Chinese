"""
Incident capture helpers for production troubleshooting.

Writes structured crash reports under `.auto-claude/incidents/` so operators can
trace fatal failures even when stdout is incomplete or interleaved.
"""

from __future__ import annotations

import platform
import traceback
from datetime import datetime, timezone
from pathlib import Path

from core.file_io import atomic_write_json


def write_incident_report(
    *,
    project_dir: Path,
    component: str,
    error: Exception,
    context: dict | None = None,
) -> Path | None:
    """
    Write a JSON incident report for fatal errors.

    Args:
        project_dir: Project root.
        component: Component name, e.g. `build`, `qa`, `followup`.
        error: The captured exception.
        context: Optional additional context.

    Returns:
        Path to the incident report, or None if writing failed.
    """
    incidents_dir = Path(project_dir) / ".auto-claude" / "incidents"
    incidents_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc)
    filename = now.strftime("%Y%m%dT%H%M%SZ") + f"-{component}.json"
    report_path = incidents_dir / filename

    payload = {
        "timestamp": now.isoformat(),
        "component": component,
        "error": {
            "type": type(error).__name__,
            "message": str(error),
        },
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "traceback": traceback.format_exc(),
        "context": context or {},
    }

    try:
        atomic_write_json(report_path, payload, indent=2, ensure_ascii=False)
        return report_path
    except OSError:
        return None

