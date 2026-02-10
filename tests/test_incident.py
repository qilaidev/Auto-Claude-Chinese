#!/usr/bin/env python3
"""
Tests for incident report helpers.
"""

import json
from unittest.mock import patch

from core.incident import write_incident_report


def test_write_incident_report_creates_json(temp_dir):
    try:
        raise RuntimeError("boom")
    except RuntimeError as err:
        report_path = write_incident_report(
            project_dir=temp_dir,
            component="qa",
            error=err,
            context={"spec": "001-test"},
        )

    assert report_path is not None
    assert report_path.exists()

    data = json.loads(report_path.read_text(encoding="utf-8"))
    assert data["component"] == "qa"
    assert data["error"]["type"] == "RuntimeError"
    assert data["error"]["message"] == "boom"
    assert data["context"]["spec"] == "001-test"
    assert "RuntimeError: boom" in data["traceback"]


def test_write_incident_report_sends_webhook_when_configured(temp_dir, monkeypatch):
    monkeypatch.setenv("AUTO_CLAUDE_ALERT_WEBHOOK_URL", "https://example.com/hook")
    monkeypatch.setenv("AUTO_CLAUDE_ALERT_TIMEOUT_SECONDS", "2")

    captured = {}

    def fake_send(url, payload, timeout_seconds):
        captured["url"] = url
        captured["payload"] = payload
        captured["timeout_seconds"] = timeout_seconds
        return True

    with patch("core.incident._send_alert_webhook", side_effect=fake_send):
        try:
            raise ValueError("webhook-test")
        except ValueError as err:
            report_path = write_incident_report(
                project_dir=temp_dir,
                component="build",
                error=err,
                context={"spec": "002-webhook"},
            )

    assert report_path is not None
    assert captured["url"] == "https://example.com/hook"
    assert captured["timeout_seconds"] == 2.0
    assert captured["payload"]["event"] == "auto_claude_incident"
    assert captured["payload"]["component"] == "build"
    assert captured["payload"]["error"]["type"] == "ValueError"
    assert captured["payload"]["context"]["spec"] == "002-webhook"
