#!/usr/bin/env python3
"""
Tests for incident report helpers.
"""

import json

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


def test_write_incident_report_emits_webhook_when_configured(temp_dir, monkeypatch):
    captured = {}

    def fake_urlopen(req, timeout=0):  # noqa: ANN001
        captured["url"] = req.full_url
        captured["timeout"] = timeout
        captured["method"] = req.get_method()
        captured["body"] = json.loads(req.data.decode("utf-8"))

        class _Response:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):  # noqa: ANN001
                return False

        return _Response()

    monkeypatch.setenv("AUTO_CLAUDE_INCIDENT_WEBHOOK_URL", "https://example.com/hook")
    monkeypatch.setenv("AUTO_CLAUDE_INCIDENT_WEBHOOK_TIMEOUT_SECONDS", "2.5")
    monkeypatch.setattr("core.incident.request.urlopen", fake_urlopen)

    try:
        raise ValueError("webhook-test")
    except ValueError as err:
        report_path = write_incident_report(
            project_dir=temp_dir,
            component="build",
            error=err,
        )

    assert report_path is not None
    assert captured["url"] == "https://example.com/hook"
    assert captured["timeout"] == 2.5
    assert captured["method"] == "POST"
    assert captured["body"]["event"] == "auto_claude_incident"
    assert captured["body"]["component"] == "build"
    assert captured["body"]["error_type"] == "ValueError"


def test_write_incident_report_ignores_webhook_failures(temp_dir, monkeypatch):
    def failing_urlopen(req, timeout=0):  # noqa: ANN001, ARG001
        raise OSError("network down")

    monkeypatch.setenv("AUTO_CLAUDE_INCIDENT_WEBHOOK_URL", "https://example.com/hook")
    monkeypatch.setattr("core.incident.request.urlopen", failing_urlopen)

    try:
        raise RuntimeError("still-persist")
    except RuntimeError as err:
        report_path = write_incident_report(
            project_dir=temp_dir,
            component="qa",
            error=err,
        )

    assert report_path is not None
    assert report_path.exists()
