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
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from core.file_io import atomic_write_json

ALERT_WEBHOOK_URL_ENV = "AUTO_CLAUDE_ALERT_WEBHOOK_URL"
ALERT_TIMEOUT_ENV = "AUTO_CLAUDE_ALERT_TIMEOUT_SECONDS"
DEFAULT_ALERT_TIMEOUT_SECONDS = 3.0
ERROR_MESSAGE_MAX_CHARS = 500


def _float_env(name: str, default: float) -> float:
    """Read positive float env var with fallback."""
    value = os.environ.get(name)
    if not value:
        return default

    try:
        parsed = float(value)
    except ValueError:
        return default

    if parsed <= 0:
        return default
    return parsed


def _truncate_error_message(message: str) -> str:
    """Trim long messages to keep alert payload lightweight."""
    if len(message) <= ERROR_MESSAGE_MAX_CHARS:
        return message
    return message[:ERROR_MESSAGE_MAX_CHARS] + "…"


def _build_alert_payload(
    *,
    timestamp: str,
    component: str,
    error: Exception,
    project_dir: Path,
    report_path: Path,
    context: dict | None,
) -> dict:
    """Build sanitized alert payload for webhook delivery."""
    payload = {
        "event": "auto_claude_incident",
        "timestamp": timestamp,
        "component": component,
        "error": {
            "type": type(error).__name__,
            "message": _truncate_error_message(str(error)),
        },
        "project_dir": str(project_dir),
        "incident_report": str(report_path),
    }

    if context:
        payload["context"] = context

    return payload


def _send_alert_webhook(url: str, payload: dict, timeout_seconds: float) -> bool:
    """Send incident alert to webhook endpoint (best effort)."""
    try:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    except (TypeError, ValueError):
        return False

    request = urllib.request.Request(
        url=url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return 200 <= response.status < 300
    except (ValueError, OSError, urllib.error.URLError):
        return False


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

        webhook_url = os.environ.get(ALERT_WEBHOOK_URL_ENV, "").strip()
        if webhook_url:
            timeout_seconds = _float_env(
                ALERT_TIMEOUT_ENV,
                DEFAULT_ALERT_TIMEOUT_SECONDS,
            )
            webhook_payload = _build_alert_payload(
                timestamp=payload["timestamp"],
                component=component,
                error=error,
                project_dir=Path(project_dir),
                report_path=report_path,
                context=context,
            )
            _send_alert_webhook(webhook_url, webhook_payload, timeout_seconds)

        return report_path
    except OSError:
        return None
