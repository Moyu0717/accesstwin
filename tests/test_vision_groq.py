"""Tests for the Groq vision path (addendum B): preprocessing, JSON parsing, provider selection, fallbacks.

No test calls the real Groq API. Every Groq-path test injects a fake client via analyze_photo(client=...).
The only exception is the opt-in `live` test, which is skipped unless a key exists in the project's .env.
"""
from __future__ import annotations

import base64
import io
import json
from types import SimpleNamespace

import pytest
from PIL import Image

from accesstwin import config
from accesstwin.core import obstacles
from accesstwin.core.obstacles import (
    OBSTACLE_TYPES,
    UNAVAILABLE_NOTICE,
    analyze_photo,
    parse_ai_json,
    preprocess_image,
)

VALID_REPLY = {
    "obstacle_type": "high_curb",
    "severity": "high",
    "affected_personas": ["wheelchair", "stroller"],
    "confidence": 0.8,
    "visible_evidence": "Raised kerb with no ramp.",
    "needs_onsite_measurement": ["curb height"],
}
SCHEMA_KEYS = {
    "obstacle_type", "severity", "affected_personas", "confidence", "visible_evidence",
    "needs_onsite_measurement",
}


def _png_bytes(size, mode="RGBA", color=(200, 30, 30, 128)) -> bytes:
    buf = io.BytesIO()
    Image.new(mode, size, color).save(buf, format="PNG")
    return buf.getvalue()


class StatusError(Exception):
    """Stand-in for an SDK error carrying an HTTP status code."""

    def __init__(self, status_code: int):
        super().__init__(f"HTTP {status_code}")
        self.status_code = status_code


class APITimeoutError(Exception):
    """Named like the Groq SDK timeout error; no status code."""


class FakeGroqClient:
    """Mimics client.chat.completions.create(**kwargs). Items are reply strings or exceptions to raise.

    The last item repeats once the list is exhausted. Every call's kwargs are recorded in `calls`.
    """

    def __init__(self, *responses):
        self._responses = list(responses)
        self.calls: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        item = self._responses[min(len(self.calls) - 1, len(self._responses) - 1)]
        if isinstance(item, Exception):
            raise item
        message = SimpleNamespace(content=item)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


@pytest.fixture
def groq_env(monkeypatch):
    """Force vision_provider() == 'groq' with a dummy key. Never a real key."""
    monkeypatch.delenv("ACCESSTWIN_MOCK", raising=False)
    monkeypatch.delenv("VISION_PROVIDER", raising=False)
    monkeypatch.delenv("GROQ_VISION_MODEL", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "test-not-a-real-key")
    assert config.vision_provider() == "groq"
    return monkeypatch


# ---------------------------------------------------------------- preprocess_image

def test_preprocess_resizes_large_rgba_png_to_rgb_jpeg_max_1024():
    out = preprocess_image(_png_bytes((3000, 2000)))
    img = Image.open(io.BytesIO(out))
    assert img.format == "JPEG"
    assert img.mode == "RGB"
    assert max(img.size) == 1024
    assert img.size == (1024, 683)  # aspect ratio kept (3000x2000 -> 1024x682/683)


def test_preprocess_does_not_upscale_small_image():
    out = preprocess_image(_png_bytes((200, 100)))
    img = Image.open(io.BytesIO(out))
    assert img.format == "JPEG"
    assert img.mode == "RGB"
    assert img.size == (200, 100)


# ---------------------------------------------------------------- parse_ai_json

def test_parse_accepts_prose_before_and_after_json():
    text = 'Sure, here is the assessment:\n' + json.dumps(VALID_REPLY) + '\nLet me know if you need more.'
    parsed = parse_ai_json(text)
    assert parsed is not None
    assert parsed["obstacle_type"] == "high_curb"
    assert parsed["severity"] == "high"
    assert set(parsed) == SCHEMA_KEYS


def test_parse_accepts_json_code_fence():
    text = "```json\n" + json.dumps(VALID_REPLY, indent=2) + "\n```"
    parsed = parse_ai_json(text)
    assert parsed is not None
    assert parsed["affected_personas"] == ["wheelchair", "stroller"]


def test_parse_accepts_plain_fence_with_trailing_text():
    text = "```\n" + json.dumps(VALID_REPLY) + "\n```\nDone."
    assert parse_ai_json(text)["confidence"] == pytest.approx(0.8)


@pytest.mark.parametrize("text", [
    "",
    "no json at all",
    "{not valid json}",
    json.dumps({**VALID_REPLY, "obstacle_type": "pothole_galaxy"}),
    json.dumps({**VALID_REPLY, "severity": "catastrophic"}),
    json.dumps({k: v for k, v in VALID_REPLY.items() if k != "obstacle_type"}),
])
def test_parse_returns_none_for_invalid_output(text):
    assert parse_ai_json(text) is None


def test_parse_filters_unknown_personas_and_clamps_confidence():
    text = json.dumps({**VALID_REPLY, "affected_personas": ["wheelchair", "pilot"], "confidence": 5})
    parsed = parse_ai_json(text)
    assert parsed["affected_personas"] == ["wheelchair"]
    assert parsed["confidence"] == 1.0
    assert all(t in OBSTACLE_TYPES for t in [parsed["obstacle_type"]])


# ---------------------------------------------------------------- provider selection

def test_mock_forced_with_key_selects_mock(monkeypatch):
    monkeypatch.setenv("ACCESSTWIN_MOCK", "1")
    monkeypatch.setenv("GROQ_API_KEY", "test-not-a-real-key")
    assert config.vision_provider() == "mock"
    assert config.mock_mode() is True


def test_key_without_mock_flag_selects_groq(monkeypatch):
    monkeypatch.delenv("ACCESSTWIN_MOCK", raising=False)
    monkeypatch.delenv("VISION_PROVIDER", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "test-not-a-real-key")
    assert config.vision_provider() == "groq"
    assert config.mock_mode() is False


def test_no_key_selects_mock(monkeypatch):
    monkeypatch.delenv("ACCESSTWIN_MOCK", raising=False)
    monkeypatch.delenv("VISION_PROVIDER", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "")
    assert config.vision_provider() == "mock"


def test_vision_provider_mock_overrides_key(monkeypatch):
    monkeypatch.delenv("ACCESSTWIN_MOCK", raising=False)
    monkeypatch.setenv("VISION_PROVIDER", "mock")
    monkeypatch.setenv("GROQ_API_KEY", "test-not-a-real-key")
    assert config.vision_provider() == "mock"


def test_default_vision_model_when_unset(monkeypatch):
    monkeypatch.delenv("GROQ_VISION_MODEL", raising=False)
    assert config.groq_vision_model() == config.DEFAULT_GROQ_VISION_MODEL


def test_get_secret_returns_default_when_missing(monkeypatch):
    monkeypatch.delenv("ACCESSTWIN_TEST_MISSING_SECRET", raising=False)
    assert config.get_secret("ACCESSTWIN_TEST_MISSING_SECRET", "fallback") == "fallback"
    assert config.get_secret("ACCESSTWIN_TEST_MISSING_SECRET") is None


# ---------------------------------------------------------------- analyze_photo (fake client)

def test_valid_reply_returns_groq_result_and_sends_expected_request(groq_env):
    client = FakeGroqClient(json.dumps(VALID_REPLY))
    result = analyze_photo(_png_bytes((640, 480)), "curb.png", "image/png", client=client)

    assert result["source"] == "groq"
    assert result["model"] == config.groq_vision_model()
    assert SCHEMA_KEYS <= set(result)
    assert "notice" not in result

    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["temperature"] == 0.2
    assert call["response_format"] == {"type": "json_object"}
    assert call["model"] == config.groq_vision_model()
    parts = call["messages"][0]["content"]
    image_parts = [p for p in parts if p.get("type") == "image_url"]
    assert len(image_parts) == 1
    url = image_parts[0]["image_url"]["url"]
    assert url.startswith("data:image/jpeg;base64,")
    raw = base64.b64decode(url.split(",", 1)[1])
    assert Image.open(io.BytesIO(raw)).format == "JPEG"


def test_status_400_on_json_mode_falls_back_without_response_format(groq_env):
    client = FakeGroqClient(StatusError(400), json.dumps(VALID_REPLY))
    result = analyze_photo(_png_bytes((64, 64)), "curb.png", "image/png", client=client)

    assert result["source"] == "groq"
    assert "notice" not in result
    assert len(client.calls) == 2
    assert "response_format" in client.calls[0]
    assert "response_format" not in client.calls[1]


def test_status_429_falls_back_to_mock_with_notice_and_never_raises(groq_env):
    client = FakeGroqClient(StatusError(429))
    result = analyze_photo(_png_bytes((64, 64)), "curb_high.png", "image/png", client=client)

    assert result["notice"] == UNAVAILABLE_NOTICE
    assert result["source"] == "mock"
    assert result["obstacle_type"] in OBSTACLE_TYPES


def test_timeout_error_falls_back_to_mock_with_notice(groq_env):
    client = FakeGroqClient(APITimeoutError("timed out"))
    result = analyze_photo(_png_bytes((64, 64)), "curb.png", "image/png", client=client)

    assert result["notice"].startswith(UNAVAILABLE_NOTICE)
    assert result["source"] == "mock"


def test_two_invalid_replies_give_manual_required(groq_env):
    client = FakeGroqClient("I cannot see anything useful.", "still not json")
    result = analyze_photo(_png_bytes((64, 64)), "curb.png", "image/png", client=client)

    assert result["source"] == "manual_required"
    assert result.get("notice")
    assert len(client.calls) == 2


def test_bad_image_bytes_return_mock_with_notice_without_calling_api(groq_env):
    client = FakeGroqClient(json.dumps(VALID_REPLY))
    result = analyze_photo(b"not an image", "curb.png", "image/png", client=client)

    assert result["source"] == "mock"
    assert result.get("notice")
    assert client.calls == []


def test_mock_mode_never_touches_client(monkeypatch):
    monkeypatch.setenv("ACCESSTWIN_MOCK", "1")
    client = FakeGroqClient(json.dumps(VALID_REPLY))
    result = analyze_photo(_png_bytes((64, 64)), "ramp_blocked_car.png", "image/png", client=client)

    assert result["source"] == "mock"
    assert result["obstacle_type"] == "blocked_ramp"
    assert client.calls == []


# ---------------------------------------------------------------- opt-in live test

def _project_env_key() -> str:
    from dotenv import dotenv_values

    env_file = config.ROOT / ".env"
    if not env_file.exists():
        return ""
    return (dotenv_values(env_file).get("GROQ_API_KEY") or "").strip()


@pytest.mark.live
def test_live_groq_vision_on_sample_photo(monkeypatch):
    key = _project_env_key()
    if not key:
        pytest.skip("GROQ_API_KEY not set in .env; live test skipped")

    photo = config.PHOTOS_DIR / "kerb_high_granite_step.jpg"
    if not photo.exists():
        pytest.skip("sample photo missing")

    monkeypatch.delenv("ACCESSTWIN_MOCK", raising=False)
    monkeypatch.delenv("VISION_PROVIDER", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", key)  # value is never printed
    assert config.vision_provider() == "groq"

    result = analyze_photo(photo.read_bytes(), photo.name, "image/jpeg")

    assert result["source"] == "groq", result.get("notice")
    assert SCHEMA_KEYS <= set(result)
    assert result["obstacle_type"] in OBSTACLE_TYPES
    assert result["severity"] in {"low", "medium", "high"}
    assert 0.0 <= result["confidence"] <= 1.0


# ---------------------------------------------------------------- Round 2B: analysis is explicit (no call on render)

def test_report_page_renders_and_picks_sample_without_calling_groq(groq_env, monkeypatch):
    """With a key present, the Report page must not call the vision API until "Analyse photo" is clicked."""
    from streamlit.testing.v1 import AppTest

    calls: list[int] = []

    def recording_groq_call(jpeg_bytes, client=None):
        calls.append(len(jpeg_bytes))
        return json.dumps(VALID_REPLY)

    monkeypatch.setattr(obstacles, "_groq_call", recording_groq_call)
    page = config.ROOT / "pages" / next(p.name for p in (config.ROOT / "pages").glob("2_*.py"))
    at = AppTest.from_file(str(page), default_timeout=90)
    at.run()
    at.radio(key="ro_src").set_value("Use an example photo").run()
    at.selectbox(key="ro_sample").set_value("kerb_high_granite_step.jpg").run()
    assert not at.exception
    assert calls == [], "the vision API was called without a click"
    at.button(key="ro_analyse").click().run()
    assert not at.exception
    assert len(calls) == 1
    assert any("Groq ·" in m.value for m in at.markdown)


def test_report_page_source_calls_analyze_only_inside_the_analyse_button():
    """Static guard: the only analyze_photo(image_bytes ...) call in the Report page sits after the ro_analyse button."""
    page = next((config.ROOT / "pages").glob("2_*.py"))
    src = page.read_text(encoding="utf-8")
    assert src.count("analyze_photo(image_bytes") == 1
    button = src.index('if st.button("Analyse photo", key="ro_analyse"):')
    assert button < src.index("analyze_photo(image_bytes")
