"""V2 planning workspace acceptance tests (plan §8 stage A, execution brief §6).

Covers: the E7 view model comes from the core, scenario isolation (Preview ramp never writes), cross-page
number consistency (Network / Compare / Deliver), E22 "Not assessed" with no invented benefit, HTML escaping,
text contrast, persona labels and the CAM_03 display. Uses the isolated temp DB from conftest.py.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from accesstwin import config
from accesstwin.core import report, store
from accesstwin.core.demand import OFF_ROUTE, demand_frame, suppressed_demand
from accesstwin.core.footfall import camera_counts
from accesstwin.core.graph import find_edge, load_graph
from accesstwin.core.personas import load_personas
from accesstwin.core.routing import route
from accesstwin.core.scoring import compute_scores
from accesstwin.core.simulation import apply_upgrades, load_upgrades, rank_upgrades
from accesstwin.ui import cached, theme
from accesstwin.ui import components as ui
from accesstwin.ui import workspace as ws
from accesstwin.ui.i18n import LABELS, t

ROOT = Path(__file__).resolve().parent.parent
PAGES = {p.name.split("_")[0]: str(p) for p in (ROOT / "pages").glob("*.py")}
PERSONAS = load_personas()


# ---------- helpers ----------

def _page(key: str, **state) -> AppTest:
    at = AppTest.from_file(PAGES[key], default_timeout=90)
    for k, v in state.items():
        at.session_state[k] = v
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    return at


def _text(at: AppTest) -> str:
    parts = [m.value for m in at.markdown] + [c.value for c in at.caption]
    parts += [i.value for i in at.info] + [w.value for w in at.warning]
    return "\n".join(str(p) for p in parts)


def _md(at: AppTest) -> str:
    return "\n".join(m.value for m in at.markdown)


def _keys(at: AppTest) -> set:
    return {b.key for b in at.button}


def _path_length(G, edge_ids) -> float:
    return sum(float(find_edge(G, eid)["length_m"]) for eid in edge_ids)


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""


@pytest.fixture(autouse=True)
def _fresh_demo():
    store.reset_demo()
    yield


# ---------- 1. E7 view model comes from the core ----------

def test_e7_view_model_comes_from_the_core():
    okey = ui.overlay_key()
    loc = ws.find_location(okey, "E7")
    assert loc is not None and loc.edge_id == "E7"
    assert loc.label == "Clinic approach"  # display name only; raw id stays visible in the UI
    assert loc.kind == "barrier"
    assert loc.condition_value == "15" and loc.condition_unit == "cm"
    # The recorded value is the core edge attribute, not a copied prototype string.
    assert float(find_edge(load_graph(), "E7")["curb_height_cm"]) == float(loc.condition_value)
    assert "wheelchair" in loc.affected and "stroller" in loc.affected
    assert "elderly" not in loc.affected  # older adult persona allows a 15 cm step
    assert loc.origin == "R1" and loc.dest == "D_CLINIC"


def test_e7_journey_lengths_equal_routing_results():
    okey = ui.overlay_key()
    G = load_graph()
    loc = ws.find_location(okey, "E7")
    wheel = PERSONAS["wheelchair"]

    base = cached.journey(okey, (), loc.origin, loc.dest, "wheelchair")
    direct = route(G, loc.origin, loc.dest, wheel)
    assert base.direct_reachable is False
    assert base.baseline_length_m == pytest.approx(direct.baseline_length_m)
    assert base.length_m == pytest.approx(direct.length_m)
    # Lengths are the sums of the recorded edge lengths on the chosen paths (nothing typed in by hand).
    assert direct.baseline_length_m == pytest.approx(_path_length(G, direct.baseline_edges))
    assert direct.length_m == pytest.approx(_path_length(G, direct.edges))

    up = loc.upgrade
    assert up is not None and up["id"] == "U1" and up["edge_id"] == "E7"
    G2 = apply_upgrades(G, [up])
    direct2 = route(G2, loc.origin, loc.dest, wheel)
    scen = cached.journey(okey, (up["id"],), loc.origin, loc.dest, "wheelchair")
    assert scen.direct_reachable is True
    assert scen.length_m == pytest.approx(direct2.length_m)
    assert scen.length_m == pytest.approx(_path_length(G2, direct2.edges))
    assert scen.length_m < base.length_m


def test_workspace_and_view_pages_carry_no_prototype_literals():
    # Numbers from the design prototype (app.js / PNGs) must not be typed into the app.
    sources = [Path(ws.__file__), Path(PAGES["0"]), Path(PAGES["8"]), Path(PAGES["9"])]
    for src in sources:
        text = src.read_text(encoding="utf-8")
        for literal in ("54.6", "63.3", "1.1 km", "+8.7"):
            assert literal not in text, (src.name, literal)


# ---------- 2. scenario isolation ----------

def test_preview_ramp_is_session_only_and_return_restores_baseline():
    overlay_before = store.get_overlay()
    reports_before = store.list_reports()
    work_before = store.list_work_orders()
    verif_before = store.list_verifications()
    db_path = Path(config.DB_PATH)
    db_hash_before = _file_hash(db_path)

    at = _page("0")
    assert "Simulated" not in _md(at)
    at.button(key="ws_preview_top").click().run()
    assert not at.exception, [e.message for e in at.exception]
    assert "Simulated" in _md(at)
    assert "ws_return_top" in _keys(at)

    assert store.get_overlay() == overlay_before
    assert store.list_reports() == reports_before
    assert store.list_work_orders() == work_before
    assert store.list_verifications() == verif_before
    assert find_edge(load_graph(), "E7")["has_step"] is True
    assert _file_hash(db_path) == db_hash_before

    at.button(key="ws_return_top").click().run()
    assert not at.exception, [e.message for e in at.exception]
    assert "ws_preview_top" in _keys(at)
    assert "at-chip sim" not in _md(at)
    assert "Baseline" in _md(at)
    assert store.get_overlay() == overlay_before
    assert find_edge(load_graph(), "E7")["has_step"] is True


# ---------- 3. cross-page consistency ----------

def test_access_score_is_identical_on_network_compare_and_deliver():
    okey = ui.overlay_key()
    G, P = load_graph(), load_personas()
    loc = ws.find_location(okey, "E7")
    rows = ws.compare_rows(okey, loc, "wheelchair")
    d, _ = cached.scenario(okey, (loc.upgrade["id"],))

    # Core agreement: baseline is the scoring result; scenario is the simulated comparison.
    assert d.index_before == pytest.approx(compute_scores(G, P).index)
    score_row = rows[0]
    assert score_row["assessment"] == t("access_score")
    assert score_row["baseline"] == f"{d.index_before:.1f} /100"
    assert score_row["scenario"] == f"{d.index_after:.1f} /100"
    assert score_row["change"] == f"{d.index_delta:+.1f}"

    # Compare page shows the same strings in its aligned table and its side score.
    cmp_at = _page("8")
    table = next(m.value for m in cmp_at.markdown if "class='at-cmp'" in m.value)
    assert f"<td>{score_row['baseline']}</td>" in table
    assert f"<td class='sc'>{score_row['scenario']}</td>" in table
    assert f"<td>{score_row['change']}</td>" in table

    # Network: after Preview ramp, the Access Score block shows the simulated value and change.
    net = _page("0")
    net.button(key="ws_preview_top").click().run()
    assert not net.exception
    net_html = _md(net)
    shown = re.search(r"class='at-score'>([\d.]+)<small> /100</small>", net_html)
    assert shown and shown.group(1) == f"{d.index_after:.1f}"
    assert f"{d.index_delta:+.1f} points" in net_html

    # Deliver page table and the HTML brief built from the same scenario section.
    dl = _page("9")
    dl_table = next(m.value for m in dl.markdown if "class='at-cmp'" in m.value)
    assert f"<td class='sc'>{score_row['scenario']}</td>" in dl_table
    section = {"location": f"{loc.label} ({loc.edge_id})", "upgrade": loc.upgrade["title"], "rows": rows,
               "steps": [], "version": cached.data_version(okey)}
    doc = cached.brief_html(okey, ws.counts_key(), "operate", ws.reports_key(), ws.scenario_json(section))
    assert f"{d.index_before:.1f} /100" in doc
    assert f"{d.index_after:.1f} /100" in doc
    assert f"{d.index_delta:+.1f}" in doc
    assert "Simulated" in doc


# ---------- 4. E22: Not assessed, no invented benefit ----------

def test_e22_is_not_assessed_and_has_no_scenario_or_benefit():
    okey = ui.overlay_key()
    loc = ws.find_location(okey, "E22")
    assert loc is not None and loc.edge_id == "E22"
    assert loc.kind == "inspection"
    assert loc.status_text == "Needs inspection"
    assert loc.condition_value == "1.50" and loc.condition_unit == "m"
    assert loc.upgrade is None
    assert ws.compare_rows(okey, loc, "wheelchair") == []

    at = _page("0")
    at.button(key="ws_row_E22").click().run()  # 2A-2: priority rows are buttons, clicking selects the segment
    assert not at.exception, [e.message for e in at.exception]
    keys = _keys(at)
    assert "ws_preview_top" not in keys and "ws_preview_bottom" not in keys
    text = _md(at)
    assert t("not_assessed") in text
    assert "Needs inspection" in text
    assert "1.50" in text
    for invented in ("Newly reachable", "Estimated residents", "Simulated", "Proposed scenario"):
        assert invented not in text, invented

    cmp_at = _page("8", ws_ctx={"segment": "E22", "scenario": ()})
    assert "no proposal yet" in _text(cmp_at)
    assert not any("class='at-cmp'" in m.value for m in cmp_at.markdown)

    dl = _page("9", ws_ctx={"segment": "E22", "scenario": ()})
    assert t("not_assessed") in _text(dl)
    assert not any("class='at-cmp'" in m.value for m in dl.markdown)


# ---------- 5. HTML escaping ----------

def test_esc_escapes_markup():
    assert ws.esc("<script>") == "&lt;script&gt;"
    assert "<script>" not in ws.esc("<script>")
    assert ws.esc('"q" & <b>') == "&quot;q&quot; &amp; &lt;b&gt;"


def test_card_escapes_its_title_when_rendered():
    at = AppTest.from_string(
        "from accesstwin.ui import components as ui\n"
        "ui.card('<b>x</b>', 'y')\n"
    ).run()
    assert not at.exception, [e.message for e in at.exception]
    bodies = [m.value for m in at.markdown]
    assert any("&lt;b&gt;" in b for b in bodies)
    assert not any("<b>x</b>" in b for b in bodies)


def test_rows_table_html_escapes_cell_text():
    rows = [{"assessment": "<img src=x onerror=alert(1)>", "baseline": "<b>1</b>", "scenario": "a & b",
             "change": "+1.0", "source": "<i>s</i>"}]
    out = ws.rows_table_html(rows)
    assert "<img" not in out
    assert "&lt;img src=x onerror=alert(1)&gt;" in out
    assert "&lt;b&gt;1&lt;/b&gt;" in out
    assert "a &amp; b" in out
    assert "&lt;i&gt;s&lt;/i&gt;" in out


# ---------- 6. contrast ----------

def test_text_token_pairs_meet_wcag_aa():
    ratios = {(fg, bg): theme.contrast(fg, bg) for fg, bg in theme.TEXT_PAIRS}
    summary = "; ".join(f"{fg} on {bg} = {r:.2f}" for (fg, bg), r in ratios.items())
    failing = [k for k, r in ratios.items() if r < 4.5]
    assert not failing, summary


def test_text_on_chip_and_tag_backgrounds_meet_wcag_aa():
    # Foreground/background pairs used by the chips, the comparison table and the status bar (theme.css).
    pairs = [("accent-strong", "#F6EEE6"), ("state-pending", "#F6F2E6"), ("accent-strong", "#F6F0E6"),
             ("text-secondary", "#F6F7F0"), ("#4F5A44", "#EEEFE7")]
    ratios = {(fg, bg): theme.contrast(fg, bg) for fg, bg in pairs}
    summary = "; ".join(f"{fg} on {bg} = {r:.2f}" for (fg, bg), r in ratios.items())
    assert all(r >= 4.5 for r in ratios.values()), summary


def test_white_on_accent_strong_meets_wcag_aa():
    ratio = theme.contrast("#FFFFFF", "accent-strong")
    assert ratio >= 4.5, f"white on accent-strong = {ratio:.2f}"


# ---------- 7. persona labels ----------

def test_persona_labels_are_consistent_everywhere():
    raw = json.loads(Path(config.PERSONAS_PATH).read_text(encoding="utf-8"))
    assert raw["elderly"]["label"] == "Older adult"
    assert raw["visually_impaired"]["label"] == "Low vision"
    assert PERSONAS["elderly"].label == "Older adult"
    assert PERSONAS["visually_impaired"].label == "Low vision"

    assert LABELS["en"]["p_elderly"] == "Older adult"
    assert LABELS["en"]["p_visually_impaired"] == "Low vision"
    assert LABELS["en"]["p_short_elderly"] == "Older adult"
    assert LABELS["en"]["p_short_visually_impaired"] == "Low vision"

    assert ui.PERSONA_SHORT["elderly"] == "Older adult"
    assert ui.PERSONA_SHORT["visually_impaired"] == "Low vision"
    assert ui.persona_short("elderly").endswith("Older adult")
    assert ui.persona_short("visually_impaired").endswith("Low vision")


def test_planning_brief_persona_rows_use_the_same_labels():
    G, P = load_graph(), load_personas()
    ranking = rank_upgrades(G, load_upgrades(), P)
    demand = suppressed_demand(G, P, camera_counts())
    doc = report.brief_html(G, P, compute_scores(G, P), ranking, demand, store.list_reports(), mode="operate")
    assert "<td>Older adult</td>" in doc
    assert "<td>Low vision</td>" in doc
    assert "<td>Elderly</td>" not in doc
    assert "<td>Visually impaired</td>" not in doc


# ---------- 8. CAM_03 display ----------

def test_cam03_off_route_display_is_unchanged():
    assert OFF_ROUTE == "No modelled demand (off-route)"
    rows = suppressed_demand(load_graph(), PERSONAS, camera_counts())
    frame = demand_frame(rows)
    cam = frame[frame["camera"] == "CAM_03"]
    assert len(cam) == 1
    row = cam.iloc[0]
    assert row["segment"] == "E11"
    assert row["status"] == OFF_ROUTE
    assert row["expected"] == "—" and row["ratio"] == "—"
