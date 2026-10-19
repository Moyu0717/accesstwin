"""Photo obstacle detection (spec section 5.6): Gemini Vision when a key is set, otherwise Mock.

AI output is only ever a *suggestion pending review*; graph state changes only after a guard/admin approves.
"""
from __future__ import annotations

import json
import re

from accesstwin import config

OBSTACLE_TYPES = ["high_curb", "missing_ramp", "blocked_ramp", "broken_surface", "narrow_path",
                  "no_tactile", "flooding", "other", "none"]
SEVERITIES = ["low", "medium", "high"]
PERSONA_KEYS = ["wheelchair", "elderly", "stroller", "visually_impaired"]

PROMPT = (
    "You are helping a township property team triage walkway accessibility reports. Look at the photo and "
    "respond with JSON ONLY (no markdown, no prose) matching exactly this schema:\n"
    '{"obstacle_type": "high_curb|missing_ramp|blocked_ramp|broken_surface|narrow_path|no_tactile|flooding|other|none",\n'
    ' "severity": "low|medium|high",\n'
    ' "affected_personas": ["wheelchair", "elderly", "stroller", "visually_impaired"],\n'
    ' "confidence": 0.0,\n'
    ' "visible_evidence": "short description",\n'
    ' "needs_onsite_measurement": ["curb height", "slope"]}\n'
    "Do not identify people or read licence plates. If unsure, use \"other\" with low confidence."
)

# filename keyword -> preset Mock result (checked in order)
_MOCK_PRESETS: list[tuple[tuple[str, ...], dict]] = [
    (("blocked",), {"obstacle_type": "blocked_ramp", "severity": "high", "affected_personas": ["wheelchair", "stroller"],
                    "confidence": 0.78, "visible_evidence": "Kerb ramp appears obstructed (e.g. parked vehicle or bins).",
                    "needs_onsite_measurement": ["clear width"]}),
    (("curb", "kerb", "step"), {"obstacle_type": "high_curb", "severity": "high",
                                "affected_personas": ["wheelchair", "stroller", "elderly"], "confidence": 0.82,
                                "visible_evidence": "Raised kerb / step edge with no visible ramp.",
                                "needs_onsite_measurement": ["curb height", "slope"]}),
    (("ramp",), {"obstacle_type": "missing_ramp", "severity": "medium", "affected_personas": ["wheelchair", "stroller"],
                 "confidence": 0.7, "visible_evidence": "Crossing point without a dropped kerb.",
                 "needs_onsite_measurement": ["curb height", "slope"]}),
    (("crack", "broken", "pothole"), {"obstacle_type": "broken_surface", "severity": "medium",
                                      "affected_personas": ["wheelchair", "stroller", "elderly", "visually_impaired"],
                                      "confidence": 0.75, "visible_evidence": "Cracked or broken paving with uneven edges.",
                                      "needs_onsite_measurement": ["level difference"]}),
    (("flood", "puddle"), {"obstacle_type": "flooding", "severity": "medium",
                           "affected_personas": ["wheelchair", "stroller", "elderly"], "confidence": 0.65,
                           "visible_evidence": "Standing water on the walkway.", "needs_onsite_measurement": ["drainage"]}),
    (("narrow",), {"obstacle_type": "narrow_path", "severity": "medium", "affected_personas": ["wheelchair", "stroller"],
                   "confidence": 0.66, "visible_evidence": "Path narrowed by an obstruction.",
                   "needs_onsite_measurement": ["clear width"]}),
    (("tactile",), {"obstacle_type": "no_tactile", "severity": "low", "affected_personas": ["visually_impaired"],
                    "confidence": 0.6, "visible_evidence": "No tactile paving at the crossing.",
                    "needs_onsite_measurement": []}),
]
_MOCK_DEFAULT = {"obstacle_type": "other", "severity": "low", "affected_personas": [], "confidence": 0.3,
                 "visible_evidence": "No specific obstacle recognised (mock).", "needs_onsite_measurement": []}


def mock_analyze(filename: str) -> dict:
    name = (filename or "").lower()
    for keys, preset in _MOCK_PRESETS:
        if any(k in name for k in keys):
            return {**preset, "source": "mock"}
    return {**_MOCK_DEFAULT, "source": "mock"}


def parse_ai_json(text: str) -> dict | None:
    """Parse and validate the model's JSON. Returns None when it does not match the schema."""
    if not text:
        return None
    m = re.search(r"\{.*\}", text, re.S)  # tolerate ```json fences
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    if data.get("obstacle_type") not in OBSTACLE_TYPES or data.get("severity") not in SEVERITIES:
        return None
    try:
        conf = float(data.get("confidence", 0))
    except (TypeError, ValueError):
        return None
    personas = [p for p in data.get("affected_personas", []) if p in PERSONA_KEYS]
    needs = data.get("needs_onsite_measurement", [])
    return {
        "obstacle_type": data["obstacle_type"],
        "severity": data["severity"],
        "affected_personas": personas,
        "confidence": max(0.0, min(1.0, conf)),
        "visible_evidence": str(data.get("visible_evidence", ""))[:300],
        "needs_onsite_measurement": [str(x) for x in needs] if isinstance(needs, list) else [],
    }


def _gemini_call(image_bytes: bytes, mime_type: str) -> str:
    from google import genai  # imported lazily; optional at runtime
    from google.genai import types

    client = genai.Client(api_key=config.GEMINI_API_KEY)
    resp = client.models.generate_content(
        model=config.GEMINI_MODEL,
        contents=[types.Part.from_bytes(data=image_bytes, mime_type=mime_type), PROMPT],
        config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.1),
    )
    return resp.text or ""


def analyze_photo(image_bytes: bytes, filename: str, mime_type: str = "image/jpeg") -> dict:
    """Return the AI suggestion dict with a `source` key: "mock", "gemini" or "manual_required".

    Gemini path (M5, needs GEMINI_API_KEY + GEMINI_MODEL): parse failure → retry once → still failing →
    {"source": "manual_required"} so the UI shows a manual category dropdown.
    """
    if config.mock_mode() or not config.GEMINI_MODEL:
        return mock_analyze(filename)
    last_error = None
    for _attempt in range(2):
        try:
            parsed = parse_ai_json(_gemini_call(image_bytes, mime_type))
        except Exception as exc:  # network / quota / SDK errors
            last_error = str(exc)
            parsed = None
        if parsed:
            return {**parsed, "source": "gemini"}
    return {**_MOCK_DEFAULT, "source": "manual_required", "error": last_error or "unparseable response"}
