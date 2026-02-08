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

