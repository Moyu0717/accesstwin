"""Photo obstacle detection (spec 5.6 + addendum B): Groq vision when a key is set, otherwise Mock.

AI output is only ever a *suggestion pending review*; graph state changes only after a guard/admin approves.
"""
from __future__ import annotations

import base64
import io
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
# Generated stand-in images shipped with the demo; shown as "Illustration (placeholder)" until real photos land.
PLACEHOLDER_PHOTOS = {"curb_high_step.png", "dark_path_night.png", "gravel_path_school.png",
                      "path_crack_broken.png", "ramp_blocked_car.png"}

_MOCK_PRESETS: list[tuple[tuple[str, ...], dict]] = [
    # Negative example first: "ok_ramp_*" must not match the "ramp" rule below.
    (("ok_", "good_"), {"obstacle_type": "none", "severity": "low", "affected_personas": [], "confidence": 0.7,
                        "visible_evidence": "Ramp / path appears usable (no obstacle recognised).",
                        "needs_onsite_measurement": ["slope"]}),
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
    (("gravel",), {"obstacle_type": "broken_surface", "severity": "medium", "affected_personas": ["wheelchair", "stroller"],
                   "confidence": 0.68, "visible_evidence": "Loose gravel surface — hard to roll on.",
                   "needs_onsite_measurement": []}),
    (("dark", "night", "unlit"), {"obstacle_type": "other", "severity": "medium",
                                  "affected_personas": ["elderly", "visually_impaired"], "confidence": 0.6,
                                  "visible_evidence": "Path looks poorly lit at night (safety concern).",
                                  "needs_onsite_measurement": ["lighting level"]}),
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


MAX_SIDE_PX = 1024
JPEG_QUALITY = 85
TIMEOUT_S = 30
UNAVAILABLE_NOTICE = "AI temporarily unavailable — using demo classifier"


def preprocess_image(image_bytes: bytes) -> bytes:
    """RGB JPEG, longest side ≤ 1024 px, quality 85 — keeps requests small (addendum B.1)."""
    from PIL import Image

    with Image.open(io.BytesIO(image_bytes)) as img:
        img = img.convert("RGB")
        img.thumbnail((MAX_SIDE_PX, MAX_SIDE_PX))
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=JPEG_QUALITY)
    return out.getvalue()


def _groq_client():
    from groq import Groq  # imported lazily so Mock mode never needs the SDK

    return Groq(api_key=config.groq_api_key(), timeout=TIMEOUT_S, max_retries=0)


def _groq_call(jpeg_bytes: bytes, client=None) -> str:
    client = client or _groq_client()
    data_url = "data:image/jpeg;base64," + base64.b64encode(jpeg_bytes).decode("ascii")
    messages = [{"role": "user", "content": [
        {"type": "text", "text": PROMPT},
        {"type": "image_url", "image_url": {"url": data_url}},
    ]}]
    kwargs = dict(model=config.groq_vision_model(), messages=messages, temperature=0.2)
    try:
        resp = client.chat.completions.create(response_format={"type": "json_object"}, **kwargs)
    except Exception as exc:
        # Some models reject JSON mode with images: retry with the strict "JSON only" prompt alone.
        if getattr(exc, "status_code", None) == 400:
            resp = client.chat.completions.create(**kwargs)
        else:
            raise
    return resp.choices[0].message.content or ""


def _is_transient(exc: Exception) -> bool:
    """429 / timeouts / connection errors → fall back to the demo classifier with a notice."""
    status = getattr(exc, "status_code", None)
    name = type(exc).__name__
    return status == 429 or "Timeout" in name or "Connection" in name or "RateLimit" in name


def analyze_photo(image_bytes: bytes, filename: str, mime_type: str = "image/jpeg", client=None) -> dict:
    """Return the suggestion (spec 5.6 schema) plus `source` ("mock" | "groq" | "manual_required") and `model`.

    Groq path: invalid JSON → retry once → Mock result + manual dropdown (source "manual_required").
    429 / network / timeout → Mock result with `notice`. Never raises.
    """
    if config.vision_provider() != "groq":
        return {**mock_analyze(filename), "model": "demo classifier"}
    model = config.groq_vision_model()
    try:
        jpeg = preprocess_image(image_bytes)
    except Exception:
        return {**mock_analyze(filename), "model": "demo classifier", "notice": "Could not read the image file."}
    for _attempt in range(2):
        try:
            parsed = parse_ai_json(_groq_call(jpeg, client))
        except Exception as exc:
            reason = UNAVAILABLE_NOTICE if _is_transient(exc) else f"{UNAVAILABLE_NOTICE} ({type(exc).__name__})"
            return {**mock_analyze(filename), "model": "demo classifier", "notice": reason}
        if parsed:
            return {**parsed, "source": "groq", "model": model}
    return {**mock_analyze(filename), "source": "manual_required", "model": model,
            "notice": "The AI reply was not valid JSON twice — please choose the category manually."}
