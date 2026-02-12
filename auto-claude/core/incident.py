"""
Incident capture helpers for production troubleshooting.

Writes structured crash reports under `.auto-claude/incidents/` so operators can
trace fatal failures even when stdout is incomplete or interleaved.
"""

from __future__ import annotations

import json
import os
import platform
import traceback
from datetime import datetime, timezone
from pathlib import Path
from urllib import error, request

from core.file_io import atomic_write_json

INCIDENT_WEBHOOK_URL_ENV = "AUTO_CLAUDE_INCIDENT_WEBHOOK_URL"
INCIDENT_WEBHOOK_TIMEOUT_ENV = "AUTO_CLAUDE_INCIDENT_WEBHOOK_TIMEOUT_SECONDS"
DEFAULT_WEBHOOK_TIMEOUT_SECONDS = 3.0


def _webhook_timeout_seconds() -> float:
    """Read webhook timeout from environment with safe fallback."""
    value = os.environ.get(INCIDENT_WEBHOOK_TIMEOUT_ENV)
    if not value:
        return DEFAULT_WEBHOOK_TIMEOUT_SECONDS
    try:
        parsed = float(value)
    except ValueError:
        return DEFAULT_WEBHOOK_TIMEOUT_SECONDS
    return parsed if parsed > 0 else DEFAULT_WEBHOOK_TIMEOUT_SECONDS


def _emit_incident_webhook(payload: dict) -> None:
    """
    Best-effort webhook notification for incident alerts.

    Never raises to callers.
    """
    webhook_url = os.environ.get(INCIDENT_WEBHOOK_URL_ENV, "").strip()
    if not webhook_url:
        return

    webhook_payload = {
        "event": "auto_claude_incident",
        "timestamp": payload.get("timestamp"),
        "component": payload.get("component"),
        "error_type": payload.get("error", {}).get("type"),
        "error_message": payload.get("error", {}).get("message"),
        "python_version": payload.get("python_version"),
        "platform": payload.get("platform"),
    }

    body = json.dumps(webhook_payload, ensure_ascii=False).encode("utf-8")
    http_request = request.Request(
        webhook_url,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )

    try:
        with request.urlopen(http_request, timeout=_webhook_timeout_seconds()):
            pass
    except (error.URLError, TimeoutError, OSError, ValueError):
        # Keep incident persistence path reliable even when alerting fails.
        return


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
        _emit_incident_webhook(payload)
        return report_path
    except OSError:
        return None
