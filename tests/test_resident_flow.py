"""Round 2B resident flow through the real pages: report -> receipt -> track -> triage (plan §5).

Every test starts from a fresh demo DB (store.reset_demo) in the isolated temp DB from conftest.py.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from accesstwin import config
from accesstwin.core import obstacles, store
from accesstwin.core.graph import find_edge, load_graph

ROOT = Path(__file__).resolve().parent.parent
PAGES = {p.name.split("_")[0]: str(p) for p in (ROOT / "pages").glob("*.py")}
KERB = "kerb_high_granite_step.jpg"
TOKEN_RE = re.compile(r"AT-[A-Z0-9]{4}-[A-Z0-9]{4}")
AI_HIGH = {"obstacle_type": "high_curb", "severity": "high", "affected_personas": ["wheelchair"],
           "confidence": 0.8, "visible_evidence": "a 15 cm step", "needs_onsite_measurement": ["height"]}


def _page(key: str, **state) -> AppTest:
    at = AppTest.from_file(PAGES[key], default_timeout=90)
    for k, v in state.items():
        at.session_state[k] = v
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    return at


def _html(at: AppTest) -> str:
    return "\n".join(m.value for m in at.markdown)


def _raw_html(at: AppTest) -> list[str]:
    """Markdown elements that Streamlit renders as raw HTML (unsafe_allow_html=True)."""
    return [m.value for m in at.markdown if m.proto.allow_html]


def _triage_keys(at: AppTest) -> list[str]:
    return [b.key for b in at.button if b.key and b.key.startswith("vq_")]


def _submit(at: AppTest) -> int:
    at.button(key="ro_submit").click().run()
    assert not at.exception, [e.message for e in at.exception]
    assert "ro_receipt" in at.session_state, "submit did not produce a receipt"
    return at.session_state["ro_receipt"]


def _submit_report(key: str, edge: str = "E7", desc: str = "A step at the entrance", ai: dict | None = None) -> dict:
    return store.submit_report(edge, "resident", desc, None, dict(ai or AI_HIGH), None, key)


@pytest.fixture
def counting_analyse(monkeypatch):
    """Spy on analyze_photo; the page re-imports it on every run, so the module attribute is what it sees."""
    calls: list[str] = []
    real = obstacles.analyze_photo

    def spy(image_bytes, filename, mime_type="image/jpeg", client=None):
        calls.append(filename)
        return real(image_bytes, filename, mime_type, client)

    monkeypatch.setattr(obstacles, "analyze_photo", spy)
    return calls


# ---------- report page: explicit analysis, no-photo submit, retries, AI failure ----------

def test_photo_is_not_analysed_until_analyse_is_clicked(counting_analyse):
    store.reset_demo()
    at = _page("2")
    at.radio(key="ro_src").set_value("Use an example photo").run()
    at.button(key=f"ro_pick_{KERB}").click().run()
    at.selectbox(key="ro_sample").set_value(KERB).run()
    assert counting_analyse == []  # selecting or picking a sample is not analysis
    assert not any("Suggested type" in m.value for m in at.markdown)
    at.button(key="ro_analyse").click().run()
    assert counting_analyse == [KERB]
    at.run()  # later reruns reuse the cached suggestion, they do not analyse again
    assert counting_analyse == [KERB]


def test_submit_without_photo_with_description_creates_receipt():
    store.reset_demo()
    at = _page("2")
    at.selectbox(key="ro_edge").set_value("E7").run()
    at.text_area(key="ro_desc").set_value("The kerb at the clinic entrance is too high for my wheelchair.").run()
    rid = _submit(at)
    r = store.get_report(rid)
    assert r["photo_path"] is None
    assert r["description"].startswith("The kerb at the clinic entrance")
    assert r["ai_original"] is None
    assert r["status"] == "pending"
    assert TOKEN_RE.fullmatch(r["token"])


def test_submit_with_neither_description_nor_photo_is_refused_and_keeps_input():
    store.reset_demo()
    before = len(store.list_reports())
    at = _page("2")
    at.button(key="ro_submit").click().run()
    assert not at.exception
    assert "ro_receipt" not in at.session_state
    assert len(store.list_reports()) == before
    assert any("Add a short description" in e.value for e in at.error)


def test_retry_with_same_draft_creates_one_report():
    store.reset_demo()
    at = _page("2")
    at.text_area(key="ro_desc").set_value("Gap in the footpath near the bus stop").run()
    first = _submit(at)
    draft = at.session_state["ro_draft"]
    # Simulate a resent form: a fresh page load that still carries the same draft id, so the same key is sent again.
    again = _page("2", ro_draft=draft)
    again.text_area(key="ro_desc").set_value("Gap in the footpath near the bus stop").run()
    second = _submit(again)
    assert second == first
    rows = [r for r in store.list_reports() if r.get("idem_key") == draft]
    assert len(rows) == 1


def test_ai_failure_keeps_description_and_allows_manual_category(monkeypatch):
    store.reset_demo()
    notice = "The AI reply was not valid JSON twice — please choose the category manually."

    def failing(image_bytes, filename, mime_type="image/jpeg", client=None):
        return {**obstacles.mock_analyze(filename), "source": "manual_required", "model": "test", "notice": notice}

    monkeypatch.setattr(obstacles, "analyze_photo", failing)
    at = _page("2")
    at.radio(key="ro_src").set_value("Use an example photo").run()
    at.selectbox(key="ro_sample").set_value(KERB).run()
    at.text_area(key="ro_desc").set_value("Step at the clinic entrance").run()
    at.button(key="ro_analyse").click().run()
    assert not at.exception
    assert any(notice in w.value for w in at.warning)
    assert at.text_area(key="ro_desc").value == "Step at the clinic entrance"
    type_box = next(s for s in at.selectbox if s.key and s.key.startswith("ro_manual_type_"))
    type_box.set_value("missing_ramp").run()
    rid = _submit(at)
    r = store.get_report(rid)
    assert r["ai"]["obstacle_type"] == "missing_ramp"
    assert r["ai_original"]["source"] == "manual_required"
    assert r["description"] == "Step at the clinic entrance"


# ---------- regression: the category after "Analyse photo" (coordinator fix) ----------

def test_submit_after_analyse_without_touching_category_keeps_suggestion():
    store.reset_demo()
    at = _page("2")
    at.radio(key="ro_src").set_value("Use an example photo").run()
    at.selectbox(key="ro_sample").set_value(KERB).run()
    at.button(key="ro_analyse").click().run()
    assert any("Suggested type: high curb" in m.value for m in at.markdown)
    rid = _submit(at)
    r = store.get_report(rid)
    assert r["ai"]["obstacle_type"] == "high_curb"
    assert r["ai_original"]["obstacle_type"] == "high_curb"
    assert r["ai"]["edited"] is False


def test_changing_category_after_analyse_is_saved_and_original_kept():
    store.reset_demo()
    at = _page("2")
    at.radio(key="ro_src").set_value("Use an example photo").run()
    at.selectbox(key="ro_sample").set_value(KERB).run()
    at.button(key="ro_analyse").click().run()
    type_box = next(s for s in at.selectbox if s.key and s.key.startswith("ro_manual_type_"))
    type_box.set_value("blocked_ramp").run()
    rid = _submit(at)
    r = store.get_report(rid)
    assert r["ai"]["obstacle_type"] == "blocked_ramp"
    assert r["ai"]["edited"] is True
    assert r["ai_original"]["obstacle_type"] == "high_curb"


# ---------- receipt and Track my report ----------

def test_receipt_code_is_found_by_track_page_in_any_case():
    store.reset_demo()
    at = _page("2")
    at.text_area(key="ro_desc").set_value("Broken paving slab").run()
    rid = _submit(at)
    token = store.get_report(rid)["token"]
    assert token in _html(at)
    track = _page("10")
    track.text_input(key="tr_code").set_value(token.lower()).run()
    assert not track.exception
    assert not track.error
    assert token in _html(track)
    assert "Submitted — waiting for review" in _html(track)


def test_track_page_prefills_code_from_last_receipt():
    store.reset_demo()
    rid = _submit_report("k-prefill")["id"]
    token = store.get_report(rid)["token"]
    track = _page("10", ro_receipt=rid)
    assert track.text_input(key="tr_code").value == token


def test_track_page_unknown_code_shows_error():
    store.reset_demo()
    track = _page("10")
    track.text_input(key="tr_code").set_value("AT-ZZZZ-ZZZZ").run()
    assert not track.exception
    assert any("No report with this code" in e.value for e in track.error)


def test_resident_pages_expose_no_accept_or_reject_buttons():
    store.reset_demo()
    rep = _submit_report("k-resident")
    track = _page("10")
    track.text_input(key="tr_code").set_value(rep["token"]).run()
    for at in (_page("2"), track, _page("1")):
        assert not _triage_keys(at)


# ---------- verification queue: triage decisions ----------

def test_queue_reject_without_reason_shows_error_and_changes_nothing():
    store.reset_demo()
    rid = _submit_report("k-reject-noreason", edge="E9", desc="Gap in path")["id"]
    at = _page("3")
    at.button(key=f"vq_row_{rid}").click().run()
    at.button(key=f"vq_no_{rid}").click().run()
    assert not at.exception
    assert any("reason" in e.value.lower() for e in at.error)
    assert store.get_report(rid)["status"] == "pending"


def test_queue_reject_with_reason_is_recorded():
    store.reset_demo()
    rid = _submit_report("k-reject-reason", edge="E9", desc="Gap in path")["id"]
    at = _page("3")
    at.button(key=f"vq_row_{rid}").click().run()
    at.text_input(key=f"vq_reason_{rid}").set_value("not on a walkway").run()
    at.button(key=f"vq_no_{rid}").click().run()
    assert not at.exception
    r = store.get_report(rid)
    assert (r["status"], r["triage"], r["reason"]) == ("rejected", "rejected", "not on a walkway")
    assert not store.get_overlay().get("E9", {}).get("obstacles")


def test_request_information_hides_report_from_overlay_and_track_answer_returns_it():
    store.reset_demo()
    rep = _submit_report("k-info", edge="E9", desc="Kerb near the shop")
    rid = rep["id"]
    at = _page("3")
    at.button(key=f"vq_row_{rid}").click().run()
    at.text_input(key=f"vq_need_{rid}").set_value("a photo of the kerb").run()
    at.button(key=f"vq_info_{rid}").click().run()
    assert not at.exception
    r = store.get_report(rid)
    assert (r["status"], r["triage"]) == ("pending", "needs_information")
    assert "E9" not in store.get_overlay()

    track = _page("10")
    track.text_input(key="tr_code").set_value(rep["token"]).run()
    assert "More information requested" in _html(track)
    track.text_area(key="tr_more").set_value("Photo: the kerb is about 15 cm, see description").run()
    track.button(key="tr_send").click().run()
    assert not track.exception
    r = store.get_report(rid)
    assert r["triage"] is None
    assert "Photo: the kerb is about 15 cm" in r["description"]
    assert "Submitted — waiting for review" in _html(track)


def test_mark_duplicate_links_to_main_report_without_map_change():
    store.reset_demo()
    main = _submit_report("k-dup-main", edge="E7", desc="Step one")["id"]
    dup = _submit_report("k-dup-copy", edge="E7", desc="Same step again")["id"]
    at = _page("3")
    at.button(key=f"vq_row_{dup}").click().run()
    at.selectbox(key=f"vq_dup_main_{dup}").set_value(main).run()
    at.button(key=f"vq_dup_{dup}").click().run()
    assert not at.exception
    r = store.get_report(dup)
    assert (r["status"], r["triage"], r["duplicate_of"]) == ("rejected", "duplicate", main)
    assert not store.get_overlay().get("E7", {}).get("obstacles")
    track = _page("10")
    track.text_input(key="tr_code").set_value(r["token"]).run()
    assert f"Linked to report #{main}" in _html(track)


# ---------- escaping: user and AI text is never raw HTML ----------

PAYLOAD = '<script>alert("x")</script><img src=x onerror="alert(2)">'


def test_user_text_with_script_is_escaped_on_track_and_queue():
    store.reset_demo()
    at = _page("2")
    at.text_area(key="ro_desc").set_value(PAYLOAD).run()
    rid = _submit(at)
    rep = store.get_report(rid)
    track = _page("10")
    track.text_input(key="tr_code").set_value(rep["token"]).run()
    for run_at in (track, _page("3")):
        if run_at is not track:
            run_at.button(key=f"vq_row_{rid}").click().run()
        raw = " ".join(_raw_html(run_at)).lower()
        assert "<script" not in raw and "<img" not in raw
    assert "&lt;script&gt;" in " ".join(_raw_html(track))


def test_reason_text_with_script_is_escaped_on_track():
    store.reset_demo()
    rep = _submit_report("k-esc-reason", edge="E9", desc="Gap")
    at = _page("3")
    at.button(key=f"vq_row_{rep['id']}").click().run()
    at.text_input(key=f"vq_need_{rep['id']}").set_value(PAYLOAD).run()
    at.button(key=f"vq_info_{rep['id']}").click().run()
    track = _page("10")
    track.text_input(key="tr_code").set_value(rep["token"]).run()
    raw = " ".join(_raw_html(track)).lower()
    assert "<script" not in raw and "<img" not in raw


def test_ai_text_with_script_is_not_rendered_as_html(monkeypatch):
    store.reset_demo()

    def hostile(image_bytes, filename, mime_type="image/jpeg", client=None):
        return {**obstacles.mock_analyze(filename), "source": "groq", "model": "test",
                "visible_evidence": PAYLOAD, "obstacle_type": "high_curb"}

    monkeypatch.setattr(obstacles, "analyze_photo", hostile)
    at = _page("2")
    at.radio(key="ro_src").set_value("Use an example photo").run()
    at.selectbox(key="ro_sample").set_value(KERB).run()
    at.button(key="ro_analyse").click().run()
    assert not at.exception
    # The example gallery legitimately renders trusted <img> thumbnails as raw HTML, so only the AI text is checked:
    # the hostile payload must never appear in raw HTML, and it must show up as escaped text in the suggestion.
    raw = " ".join(_raw_html(at))
    assert PAYLOAD not in raw and "onerror=\"alert(2)\"" not in raw
    shown_as_text = [m.value for m in at.markdown if not m.proto.allow_html]
    assert any("<script" in v and "Visible evidence" in v for v in shown_as_text)
