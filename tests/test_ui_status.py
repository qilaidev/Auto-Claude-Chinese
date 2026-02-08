#!/usr/bin/env python3
"""
Tests for UI status compatibility behavior.
"""

from ui.status import BuildState, BuildStatus


def test_build_status_from_dict_unknown_state_falls_back_to_idle():
    data = {
        "active": True,
        "spec": "001-sample",
        "state": "unknown_future_state",
    }

    status = BuildStatus.from_dict(data)
    assert status.state == BuildState.IDLE


def test_build_status_from_dict_known_state_kept():
    data = {
        "active": True,
        "spec": "001-sample",
        "state": "qa",
    }

    status = BuildStatus.from_dict(data)
    assert status.state == BuildState.QA

