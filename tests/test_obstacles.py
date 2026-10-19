"""Photo obstacle detection (spec section 5.6): mock presets and AI JSON parsing."""
from __future__ import annotations

import json

import pytest

from accesstwin.core import obstacles


@pytest.mark.parametrize(
    "filename, expected",
    [
        ("curb_high_step.png", "high_curb"),
        ("ramp_blocked_car.png", "blocked_ramp"),
        ("path_crack_broken.png", "broken_surface"),
    ],
)
def test_mock_presets_by_filename_keyword(filename, expected):
    res = obstacles.analyze_photo(b"", filename)
    assert res["obstacle_type"] == expected
    assert res["source"] == "mock"


def test_mock_curb_has_onsite_measurements():
    res = obstacles.analyze_photo(b"", "curb_high_step.png")
    assert res["needs_onsite_measurement"]
    assert res["source"] == "mock"


def test_mock_unknown_filename_defaults_to_other_low_confidence():
    res = obstacles.analyze_photo(b"", "random.jpg")
    assert res["obstacle_type"] == "other"
    assert res["confidence"] == pytest.approx(0.3)
    assert res["source"] == "mock"


def _payload(**overrides) -> str:
    data = {
        "obstacle_type": "high_curb",
        "severity": "high",
        "affected_personas": ["wheelchair", "stroller"],
        "confidence": 0.8,
        "visible_evidence": "Raised kerb.",
        "needs_onsite_measurement": ["curb height"],
    }
    data.update(overrides)
    return json.dumps(data)


def test_parse_valid_json_returns_dict():
    parsed = obstacles.parse_ai_json(_payload())
    assert isinstance(parsed, dict)
    assert parsed["obstacle_type"] == "high_curb"
    assert parsed["severity"] == "high"
    assert parsed["affected_personas"] == ["wheelchair", "stroller"]
    assert parsed["confidence"] == pytest.approx(0.8)
    assert parsed["needs_onsite_measurement"] == ["curb height"]


def test_parse_json_inside_code_fence_returns_dict():
    text = "```json\n" + _payload() + "\n```"
    parsed = obstacles.parse_ai_json(text)
    assert isinstance(parsed, dict)
    assert parsed["obstacle_type"] == "high_curb"


def test_parse_invalid_obstacle_type_returns_none():
    assert obstacles.parse_ai_json(_payload(obstacle_type="pothole_dragon")) is None


def test_parse_invalid_severity_returns_none():
    assert obstacles.parse_ai_json(_payload(severity="extreme")) is None


def test_parse_garbage_returns_none():
    assert obstacles.parse_ai_json("this is not json at all") is None
    assert obstacles.parse_ai_json("{not: valid json}") is None
    assert obstacles.parse_ai_json("") is None


def test_parse_clamps_confidence_to_unit_interval():
    assert obstacles.parse_ai_json(_payload(confidence=1.7))["confidence"] == 1.0
    assert obstacles.parse_ai_json(_payload(confidence=-0.4))["confidence"] == 0.0


def test_parse_filters_unknown_personas():
    parsed = obstacles.parse_ai_json(_payload(affected_personas=["wheelchair", "astronaut", "elderly"]))
    assert parsed["affected_personas"] == ["wheelchair", "elderly"]
