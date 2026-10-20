"""M4 end-to-end through the real pages: report -> approve -> edge blocked -> route recomputes."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from accesstwin.core import store
from accesstwin.core.graph import find_edge, load_graph

ROOT = Path(__file__).resolve().parent.parent
PAGES = {p.name.split("_")[0]: str(p) for p in (ROOT / "pages").glob("*.py")}


def _run(page: str) -> AppTest:
    at = AppTest.from_file(PAGES[page], default_timeout=60)
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    return at


def _route_page(persona: str) -> AppTest:
    at = AppTest.from_file(PAGES["1"], default_timeout=60)
    at.session_state["persona"] = persona
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    return at


def test_report_approve_confirms_obstacle_and_reroutes():
    store.reset_demo()
    # 1. Report Obstacle page: pick the curb sample photo, mock AI says high_curb, submit on E7.
    at = _run("2")
    at.radio(key="ro_src").set_value("Use a sample photo").run()
    at.selectbox(key="ro_sample").set_value("kerb_high_granite_step.jpg").run()
    assert any("Suggested type: high curb" in m.value for m in at.markdown)
    at.selectbox(key="ro_edge").set_value("E7").run()
    at.radio(key="ro_role").set_value("resident").run()
    at.button(key="ro_submit").click().run()
    assert not at.exception
    rid = max(r["id"] for r in store.list_reports("pending") if r["edge_id"] == "E7")
    assert find_edge(load_graph(), "E7")["status"] == "verified_accessible"

    # 2. Verification Queue: approve -> the 15 cm step is confirmed as an obstacle (X2); E7 is not closed for everyone.
    at = _run("3")
    at.button(key=f"vq_ok_{rid}").click().run()
    assert not at.exception
    assert any("E7" in s.value for s in at.success)
    e7 = find_edge(load_graph(), "E7")
    assert e7["status"] == "verified_accessible"
    assert [o["type"] for o in e7["obstacles"]] == ["high_curb"]

    # 3. Route Planner as an older adult: the step is passable, so the 450 m direct route stays and no reason names E7.
    elderly = _route_page("elderly")
    text = " ".join(m.body for m in elderly.markdown)
    assert "Direct route usable" in text
    assert "E7: blocked" not in text
    assert "E7: step" not in text
    metrics = {m.label: m.value for m in elderly.metric}
    assert metrics["Distance"] == "450 m"
    assert float(metrics["Detour ratio"].rstrip("×")) == pytest.approx(1.0)

    # 4. Route Planner as a wheelchair user: still detours, and the reason names the step.
    wheel = _route_page("wheelchair")
    assert "E7: step 15 cm" in " ".join(m.body for m in wheel.markdown)
    detour = next(m.value for m in wheel.metric if m.label == "Detour ratio")
    assert float(detour.rstrip("×")) >= 2.0


def test_approve_flash_does_not_claim_segment_is_blocked():
    store.reset_demo()
    rid = max(r["id"] for r in store.list_reports("pending") if r["edge_id"] == "E7")
    at = _run("3")
    at.button(key=f"vq_ok_{rid}").click().run()
    assert not at.exception
    assert not any("now blocked" in s.value for s in at.success)


def test_verify_unverified_edge():
    store.reset_demo()
    at = _run("3")
    at.selectbox(key="vq_edge").set_value("E9").run()
    at.radio(key="vq_result").set_value("passable").run()
    at.button(key="vq_verify").click().run()
    assert not at.exception
    assert find_edge(load_graph(), "E9")["status"] == "verified_accessible"


def test_simulator_work_order():
    store.reset_demo()
    at = _run("5")
    assert any(m.label == "Access Score" for m in at.metric)
    at.button(key="sim_wo_btn").click().run()
    assert not at.exception
    assert len(store.list_work_orders()) == 1
