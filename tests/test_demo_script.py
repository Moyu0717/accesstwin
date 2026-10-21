"""M8 acceptance: the 3-minute demo script (docs/DEMO_SCRIPT.md) runs end-to-end in Mock mode without errors."""
import re
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


def _download_labels(at: AppTest) -> list[str]:
    """Download buttons are not exposed by AppTest; read their labels from the protobuf element."""
    return [str(el.proto.label) for el in at.get("download_button")]


def test_full_demo_script_mock_mode():
    assert config.mock_mode()
    store.reset_demo()

    # 0:00 Network (V2 workspace) — E7 "Clinic approach" selected first, reference path interrupted,
    # wheelchair Access Score bar under 50, Access Score shown as the headline index.
    home = _page(PAGES["0"])
    net_html = "\n".join(m.value for m in home.markdown)
    assert "Clinic approach" in _text(home)
    assert "Shortest reference path" in net_html
    assert "Access Score" in net_html
    # 2A-2: the priority list is a column of buttons (ws_row_<edge>), the first row is E7.
    row_labels = [b.label for b in home.button if b.key and b.key.startswith("ws_row_")]
    assert row_labels and row_labels[0].startswith("**01 · ")
    assert "Clinic approach" in row_labels[0] and "E7" in row_labels[0]
    wheel_bar = re.search(r"<span>Wheelchair</span>.*?at-num'>([\d.]+)</span>", net_html, re.S)
    assert wheel_bar and float(wheel_bar.group(1)) < 50

    # 0:30 Route Planner — elderly direct, wheelchair blocked at E7 with a 2×+ fallback.
    elderly = _page(PAGES["1"], persona="elderly")
    assert "Direct route usable" in _text(elderly)
    wheel = _page(PAGES["1"], persona="wheelchair")
    assert "E7: step 15 cm" in _text(wheel)
    # 2A-3: the ratio is stated in the conclusion text ("The usable route is 2.4× the reference.").
    detour = re.search(r"usable route is ([\d.]+)× the reference", _text(wheel))
    assert detour and float(detour.group(1)) >= 2.0

    # 1:00 Evidence — curb photo -> high_curb suggestion -> submit -> guard approves.
    rep = _page(PAGES["2"])
    rep.radio(key="ro_src").set_value("Use an example photo").run()
    rep.selectbox(key="ro_sample").set_value("kerb_high_granite_step.jpg").run()
    rep.button(key="ro_analyse").click().run()  # 2B: analysis only on the explicit click
    assert "Suggested type: high curb" in _text(rep)
    rep.selectbox(key="ro_edge").set_value("E7").run()
    rep.button(key="ro_submit").click().run()
    assert not rep.exception
    rid = max(r["id"] for r in store.list_reports("pending"))
    queue = _page(PAGES["3"])
    queue.button(key=f"vq_row_{rid}").click().run()  # 2B: select the report, then accept it
    queue.button(key=f"vq_ok_{rid}").click().run()
    assert not queue.exception
    # X2: approval confirms the 15 cm step as an obstacle; E7 is not closed for everyone.
    assert [o["type"] for o in store.get_overlay()["E7"]["obstacles"]] == ["high_curb"]
    assert "blocked" != store.get_overlay()["E7"].get("status")
    # ... and the Footfall page shows E7 far below expected: suppressed demand.
    ff = _page(PAGES["4"])
    ff.button(key="ff_run").click().run()
    assert not ff.exception
    assert "Suppressed demand on E7" in _text(ff)

    # 1:30 Decide — reset, U1 preselected, index rises, U1 is #1 in the priority ranking, work order created.
    store.reset_demo()
    sim = _page(PAGES["5"])
    metrics = {m.label: m for m in sim.metric}
    assert metrics["Access Score"].delta.startswith("+")
    assert int(metrics["Newly reachable (modelled)"].value) > 0
    assert _ranking(sim).iloc[0]["id"] == "U1"
    sim.button(key="sim_wo_btn").click().run()
    assert not sim.exception and store.list_work_orders()

    # 1:45 Compare — same Baseline / Scenario snapshot: Access Score row with a positive change, one aligned table.
    cmp_page = _page(PAGES["8"])
    table = next(m.value for m in cmp_page.markdown if "class='at-cmp'" in m.value)
    access_row = re.search(r"<tr><td>Access Score</td>.*?</tr>", table)
    assert access_row, "Access Score row missing from the Compare table"
    assert re.search(r"<td>\+\d+\.\d</td>", access_row.group(0))
    assert "Simulated" in table or "Model" in table

    # 2:00 Deliver — the study brief is offered as a download for the same snapshot.
    deliver = _page(PAGES["9"])
    labels = _download_labels(deliver)
    assert "Download study brief (HTML) ↓" in labels
    assert "Download comparison (CSV) ↓" in labels

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
