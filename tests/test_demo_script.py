"""M8 acceptance: the 3-minute demo script (docs/DEMO_SCRIPT.md) runs end-to-end in Mock mode without errors."""
from pathlib import Path

from streamlit.testing.v1 import AppTest

from accesstwin import config
from accesstwin.core import store

ROOT = Path(__file__).resolve().parent.parent
PAGES = {p.name.split("_")[0]: str(p) for p in (ROOT / "pages").glob("*.py")}


def _page(path: str, **state) -> AppTest:
    at = AppTest.from_file(path, default_timeout=90)
    for k, v in state.items():
        at.session_state[k] = v
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    return at


def _ranking(at: AppTest):
    return next(d.value for d in at.dataframe if "roi" in getattr(d.value, "columns", []))


def _text(at: AppTest) -> str:
    return " ".join(m.body for m in at.markdown)


def test_full_demo_script_mock_mode():
    assert config.mock_mode()
    store.reset_demo()

    # 0:00 Home — headline index and wheelchair under 50.
    home = _page(str(ROOT / "app.py"))
    values = {m.label: m.value for m in home.metric}
    assert values["Gap Index"].endswith("/ 100")
    assert int(values["♿ Wheelchair"]) < 50
    assert "Top 3 critical gaps" in " ".join(h.value for h in home.subheader)

    # 0:30 Route Planner — elderly direct, wheelchair blocked at E7 with a 2×+ fallback.
    elderly = _page(PAGES["1"], persona="elderly")
    assert "Direct route usable" in _text(elderly)
    wheel = _page(PAGES["1"], persona="wheelchair")
    assert "E7: step 15 cm" in _text(wheel)
    detour = next(m.value for m in wheel.metric if m.label == "Detour ratio")
    assert float(detour.rstrip("×")) >= 2.0

    # 1:00 Evidence — curb photo -> high_curb suggestion -> submit -> guard approves.
    rep = _page(PAGES["2"])
    rep.radio(key="ro_src").set_value("Use a sample photo").run()
    rep.selectbox(key="ro_sample").set_value("curb_high_step.png").run()
    assert "Suggested type: high curb" in _text(rep)
    rep.selectbox(key="ro_edge").set_value("E7").run()
    rep.button(key="ro_submit").click().run()
    assert not rep.exception
    rid = max(r["id"] for r in store.list_reports("pending"))
    queue = _page(PAGES["3"])
    queue.button(key=f"vq_ok_{rid}").click().run()
    assert not queue.exception
    assert store.get_overlay()["E7"]["status"] == "blocked"
    # ... and the Footfall page shows E7 far below expected: suppressed demand.
    ff = _page(PAGES["4"])
    ff.button(key="ff_run").click().run()
    assert not ff.exception
    assert "Suppressed demand on E7" in _text(ff)

    # 1:30 Decide — reset, U1 preselected, index rises, U1 is #1 in the ROI ranking, work order created.
    store.reset_demo()
    sim = _page(PAGES["5"])
    metrics = {m.label: m for m in sim.metric}
    assert metrics["Township index"].delta.startswith("+")
    assert int(metrics["New trips"].value) > 0
    assert _ranking(sim).iloc[0]["id"] == "U1"
    sim.button(key="sim_wo_btn").click().run()
    assert not sim.exception and store.list_work_orders()

    # 2:30 Scale — Design mode shows the pre-construction header and the design-only upgrade U4.
    sim.radio(key="sim_mode").set_value("design").run()
    assert not sim.exception
    assert any("Pre-construction review" in i.value for i in sim.info)
    assert "U4" in _ranking(sim)["id"].tolist()

    # 2:30 Dashboard — suppressed demand flagged, Planning Brief exported, Design mode header.
    dash = _page(PAGES["6"])
    assert int(next(m.value for m in dash.metric if m.label == "Suppressed-demand segments")) >= 1
    dash.radio(key="dash_mode").set_value("design").run()
    assert not dash.exception
    assert any("Pre-construction review" in i.value for i in dash.info)
