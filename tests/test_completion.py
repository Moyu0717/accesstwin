"""Completion review acceptance tests (reference/ACCESSTWIN_COMPLETION_REVIEW.md, Definition of done).

Covers: number consistency, sample-photo gallery, CAM_03 display, recommended bundle, work-order -> verification
flow, CSV design-mode import, language fallback, guided demo, accessibility cues and navigation.
Every test that touches the SQLite store uses an isolated temp DB (see conftest.py / test_store.py).
"""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from accesstwin import config
from accesstwin.core import network_import, report, store
from accesstwin.core.demand import OFF_ROUTE, demand_frame, suppressed_demand
from accesstwin.core.footfall import camera_counts
from accesstwin.core.graph import load_graph
from accesstwin.core.obstacles import PLACEHOLDER_PHOTOS, analyze_photo, mock_analyze
from accesstwin.core.personas import load_personas
from accesstwin.core.routing import route
from accesstwin.core.scoring import compute_scores
from accesstwin.core.simulation import (
    DEFAULT_BUNDLE_BUDGET, load_upgrades, rank_upgrades, recommend_bundle,
)
from accesstwin.ui import cached
from accesstwin.ui import components as ui
from accesstwin.ui import guide
from accesstwin.ui.i18n import LABELS, t
from accesstwin.ui import theme
from accesstwin.ui.map_view import IMPASSABLE_DASH, STATUS_COLOURS, STATUS_DASH, map_html

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


def _metric(at: AppTest, label: str):
    return next(m for m in at.metric if m.label == label)


def _text(at: AppTest) -> str:
    parts = [m.value for m in at.markdown] + [s.value for s in at.subheader] + [c.value for c in at.caption]
    parts += [i.value for i in at.info] + [s.value for s in at.success] + [w.value for w in at.warning]
    return "\n".join(str(p) for p in parts)


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "completion.db")
    store.init_db(seed=False)
    return tmp_path / "completion.db"


# ---------- 1. number consistency ----------

def _expected_gap_index() -> float:
    return round(compute_scores(load_graph(), load_personas()).index)


def test_overview_and_dashboard_show_the_same_gap_index():
    # V2 rename: "Gap Index" is now "Access Score" (higher is better). The Network page draws the score in HTML
    # (workspace.score_block) with one decimal; the Dashboard metric uses zero decimals.
    store.reset_demo()
    expected = _expected_gap_index()

    overview = _page("0")
    overview_html = "\n".join(m.value for m in overview.markdown)
    shown = re.findall(r"class='at-score'>(\d+\.\d)<small> /100", overview_html)
    assert shown, "Access Score block not found on the Network page"
    assert round(float(shown[0])) == expected

    dash = _page("6")
    dash_value = _metric(dash, "Access Score").value
    assert int(dash_value.split("/")[0]) == expected
    assert round(float(shown[0])) == int(dash_value.split("/")[0])


def test_simulator_before_index_matches_gap_index():
    store.reset_demo()
    full = compute_scores(load_graph(), load_personas()).index
    sim = _page("5")
    # The bundle card's "Package: Access Score" shows "+x (from before)"; the scenario card shows "+x".
    bundle_m = next(m for m in sim.metric if m.label == "Package: Access Score")
    scenario_m = next(m for m in sim.metric if m.label == "Access Score")
    assert "(from" in bundle_m.delta
    bundle_before = float(bundle_m.delta.split("(from ")[1].rstrip(")"))
    assert round(bundle_before) == round(full) == _expected_gap_index()
    # Scenario (default U1): after - delta gives "before" to within the 1-dp rounding of both values.
    before_from_page = float(scenario_m.value) - float(scenario_m.delta)
    assert abs(before_from_page - full) <= 0.11
    assert round(before_from_page) == round(full) == _expected_gap_index()
    # The cached scenario agrees with the raw computation.
    d, _ = cached.scenario(json.dumps(store.get_overlay(), sort_keys=True), ("U1",))
    assert round(d.index_before) == _expected_gap_index()


# ---------- 2. sample-photo gallery ----------

def _sample_names() -> list[str]:
    return sorted(p.name for p in config.PHOTOS_DIR.glob("*") if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"})


def test_report_page_has_a_pick_button_per_sample_photo():
    store.reset_demo()
    at = _page("2")
    # 2B: the gallery buttons only SELECT a sample; the gallery is shown once "Use an example photo" is chosen.
    at.radio(key="ro_src").set_value("Use an example photo").run()
    keys = {b.key: b for b in at.button}
    names = _sample_names()
    assert names, "bundled sample photos are missing"
    credits = ui.photo_credits()
    gallery = [n for n in names if n in credits] or names  # credited photos replace placeholders in the gallery
    for name in gallery:
        assert f"ro_pick_{name}" in keys, name
        assert keys[f"ro_pick_{name}"].label == "Use this photo"
    # Selecting is not analysing, and analysis needs a selected photo: no analyse button until one is picked.
    assert "ro_analyse" not in keys
    assert not any("Suggested type" in m.value for m in at.markdown)
    # every gallery photo that is third-party carries its author and licence in the caption (credits.json v2)
    for name in gallery:
        if name in credits:
            assert f"Photo: {credits[name]['author']}, {credits[name]['licence']}" in ui.photo_caption(name)


def test_clicking_blocked_ramp_sample_shows_suggestion():
    store.reset_demo()
    at = _page("2")
    key = "pavement_blocked_parked_cars.jpg"
    assert key in ui.photo_credits()
    at.radio(key="ro_src").set_value("Use an example photo").run()
    at.button(key=f"ro_pick_{key}").click().run()
    assert not at.exception
    # 2B: picking a photo does not analyse it; the suggestion appears after "Analyse photo" is clicked.
    assert not any("Suggested type" in m.value for m in at.markdown)
    at.button(key="ro_analyse").click().run()
    assert not at.exception
    assert any("Suggested type: blocked ramp" in m.value for m in at.markdown)


def test_placeholder_photo_captions_are_labelled_as_illustrations():
    # UI-03: the generated placeholder PNGs were removed, so the placeholder set is empty and no bundled photo is
    # labelled as an illustration. Every bundled photo is a credited Wikimedia example instead.
    assert PLACEHOLDER_PHOTOS == set()
    assert not any(n in PLACEHOLDER_PHOTOS for n in _sample_names())
    for name in _sample_names():
        assert not ui.photo_caption(name).startswith("Illustration (placeholder)"), name
    # A non-placeholder photo must not be labelled as one.
    assert not ui.photo_caption("ok_ramp_x.jpg").startswith("Illustration (placeholder)")


@pytest.mark.parametrize("filename, expected", [
    ("ok_ramp_x.jpg", "none"),
    ("gravel_path_test.jpg", "broken_surface"),
    ("dark_path_test.jpg", "other"),
    ("flood_drain.jpg", "flooding"),
    ("tactile_crossing.jpg", "no_tactile"),
])
def test_mock_keyword_table(filename, expected):
    assert mock_analyze(filename)["obstacle_type"] == expected


def test_arbitrary_upload_in_mock_mode_is_never_a_30_percent_result():
    # AppTest cannot inject a file into st.file_uploader (Streamlit 1.55), so the upload branch is checked by:
    # (a) the classifier's raw answer for an unknown filename, (b) the page source that gates it.
    assert config.mock_mode()
    raw = analyze_photo(b"not-a-real-image", "random_site_photo.jpg")
    assert raw["source"] == "mock"
    page_src = Path(PAGES["2"]).read_text(encoding="utf-8")
    # V2 polish: the card title no longer carries an emoji (the title text itself is unchanged).
    assert 'ui.card("Demo classifier"' in page_src
    assert "🧪" not in page_src
    assert "demo_guess = is_upload and source == \"mock\"" in page_src
    assert "\"confidence\": 0.0" in page_src  # the 0.3 guess is overwritten before display
    assert "Real AI analysis (Groq) runs on the hosted version" in page_src


# ---------- 3. CAM_03 display ----------

def test_cam03_off_route_row_shows_dashes_not_zero():
    store.reset_demo()
    rows = suppressed_demand(load_graph(), PERSONAS, camera_counts())
    frame = demand_frame(rows)
    e11 = frame[frame["segment"] == "E11"].iloc[0]
    assert e11["camera"] == "CAM_03"
    assert e11["status"] == OFF_ROUTE
    assert e11["expected"] == "—"
    assert e11["ratio"] == "—"


def test_exactly_one_suppressed_segment_and_it_is_e7():
    store.reset_demo()
    rows = suppressed_demand(load_graph(), PERSONAS, camera_counts())
    assert [r.edge_id for r in rows if r.suppressed] == ["E7"]


# ---------- 4. recommended package ----------

def test_recommend_bundle_default_budget_picks_u1_and_u2():
    store.reset_demo()
    G, U = load_graph(), load_upgrades()
    b = recommend_bundle(G, U, PERSONAS)
    assert b is not None
    assert b.upgrade_ids == ["U1", "U2"]
    assert b.cost_weight == pytest.approx(3.5)
    assert b.budget == DEFAULT_BUNDLE_BUDGET
    assert b.cost_weight <= DEFAULT_BUNDLE_BUDGET
    assert b.delta.index_after > b.delta.index_before
    assert b.delta.index_before == pytest.approx(compute_scores(G, PERSONAS).index)
    assert set(b.delta.beneficiaries_by_persona) == set(PERSONAS) and len(PERSONAS) == 4
    assert sum(b.delta.beneficiaries_by_persona.values()) == pytest.approx(b.delta.beneficiaries)


def test_recommend_bundle_budget_limits():
    store.reset_demo()
    G, U = load_graph(), load_upgrades()
    ranking = rank_upgrades(G, U, PERSONAS)
    only_u1 = recommend_bundle(G, U, PERSONAS, budget=1.0, ranking=ranking)
    assert only_u1 is not None and only_u1.upgrade_ids == ["U1"]
    assert recommend_bundle(G, U, PERSONAS, budget=0.5, ranking=ranking) is None


def test_simulator_shows_recommended_package():
    store.reset_demo()
    at = _page("5")
    assert "Recommended package" in _text(at)


def test_planning_brief_contains_recommended_package():
    store.reset_demo()
    G, U = load_graph(), load_upgrades()
    ranking = rank_upgrades(G, U, PERSONAS)
    bundle = recommend_bundle(G, U, PERSONAS, ranking=ranking)
    demand = suppressed_demand(G, PERSONAS, camera_counts())
    html_doc = report.brief_html(G, PERSONAS, compute_scores(G, PERSONAS), ranking, demand,
                                 store.list_reports(), "operate", bundle)
    assert "Recommended package" in html_doc
    assert "U1 + U2" in html_doc


# ---------- 5. work order -> verification flow (isolated DB) ----------

def _wheelchair_route():
    return route(load_graph(), "R1", "D_CLINIC", PERSONAS["wheelchair"])


def test_work_order_verification_repairs_e7_and_keeps_status_accessible(isolated_db):
    e7 = lambda: next(e for e in load_graph().edges(keys=True, data=True) if e[2] == "E7")[3]

    oid = store.add_work_order("U1")
    assert e7()["has_step"] is True
    assert _wheelchair_route().direct_reachable is False

    vid = store.verify_work_order(oid, "guard", "checked")
    assert isinstance(vid, int)
    (order,) = store.list_work_orders()
    assert order["status"] == "done"
    note = store.list_verifications()[-1]["note"]
    assert note.startswith(f"WO#{oid}")

    edge = e7()
    assert edge["has_step"] is False
    assert edge["curb_height_cm"] == 0
    assert edge["status"] == "verified_accessible"
    res = _wheelchair_route()
    assert res.direct_reachable is True
    assert res.length_m == pytest.approx(450)

    # X2: the repair clears the approved high_curb obstacle it resolves (U1 resolves high_curb).
    rid = store.add_report("E7", "resident", None, {"obstacle_type": "high_curb"})
    store.set_report_status(rid, "approved")
    assert [o["type"] for o in e7()["obstacles"]] == ["high_curb"]  # confirmed again after the repair
    assert e7()["status"] == "verified_accessible"  # never "blocked" for everyone (X2)


def test_reapproved_step_after_repair_reopens_the_route(isolated_db):
    e7 = lambda: next(e for e in load_graph().edges(keys=True, data=True) if e[2] == "E7")[3]
    oid = store.add_work_order("U1")
    store.verify_work_order(oid, "guard", "checked")
    assert e7()["has_step"] is False

    rid = store.add_report("E7", "resident", None, {"obstacle_type": "high_curb"})
    store.set_report_status(rid, "approved")
    assert e7()["has_step"] is True
    assert _wheelchair_route().direct_reachable is False


def test_verify_nonexistent_work_order_returns_none(isolated_db):
    assert store.verify_work_order(9999, "guard") is None
    assert store.list_work_orders() == []


def test_dashboard_work_order_board_progresses(isolated_db):
    oid = store.add_work_order("U1")
    at = _page("6")
    at.button(key=f"wo_start_{oid}").click().run()
    assert not at.exception
    assert store.list_work_orders()[0]["status"] == "in_progress"

    at.button(key=f"wo_done_{oid}").click().run()
    assert not at.exception
    assert store.list_work_orders()[0]["status"] == "done"

    at.button(key=f"wo_verify_{oid}").click().run()
    assert not at.exception
    assert any(v["note"].startswith(f"{store.WO_NOTE_PREFIX}{oid}") for v in store.list_verifications())
    assert store.get_overlay()["E7"]["status"] == "verified_accessible"


# ---------- 6. CSV import (design mode) ----------

def test_sample_network_imports_cleanly():
    data, errors = network_import.parse_network(*network_import.sample_csvs())
    assert errors == []
    assert len(data["nodes"]) >= 10


def test_templates_have_the_documented_headers():
    tn, ts = network_import.template_csvs()
    assert tn.strip().split(",") == network_import.NODE_COLUMNS
    assert ts.strip().split(",") == network_import.SEGMENT_COLUMNS


def _sample_lines():
    nodes, segs = network_import.sample_csvs()
    return nodes.splitlines(), segs.splitlines()


@pytest.mark.parametrize("label, mutate, needle", [
    ("non-numeric lat",
     lambda n, s: ([l.replace("3.1900,101.5100", "north,101.5100") for l in n], s),
     "'lat' must be a number"),
    ("unknown node type",
     lambda n, s: ([l.replace(",residential,", ",spaceship,", 1) if l.startswith("H1,") else l for l in n], s),
     "type 'spaceship' not allowed"),
    ("missing segment endpoint",
     lambda n, s: (n, [l.replace("S1,H1,K1,", "S1,H1,K9,", 1) for l in s]),
     "'to' node 'K9' does not exist"),
    ("bad surface",
     lambda n, s: (n, [l.replace("S1,H1,K1,120,good", "S1,H1,K1,120,mud", 1) for l in s]),
     "surface 'mud' not allowed"),
    ("duplicate node id",
     lambda n, s: (n + [n[-1]], s),
     "duplicate id"),
    ("no residential node",
     lambda n, s: ([l for l in n if ",residential," not in l], s),
     "needs at least one residential node"),
])
def test_bad_csv_inputs_are_reported(label, mutate, needle):
    nodes, segs = _sample_lines()
    n, s = mutate(list(nodes), list(segs))
    _, errors = network_import.parse_network("\n".join(n) + "\n", "\n".join(s) + "\n")
    assert errors, label
    assert any(needle in e for e in errors), (label, errors)


def test_dashboard_design_mode_runs_pre_construction_review():
    store.reset_demo()
    at = _page("6")
    at.radio(key="dash_mode").set_value("design").run()
    assert not at.exception
    assert any("Pre-construction review: import a draft walkway network" in s.value for s in at.subheader)
    assert "Draft Access Score" in [m.label for m in at.metric]


# ---------- 7. language ----------

NAV_KEYS = [k for k in LABELS["en"] if k.startswith("nav_")]


def test_nav_keys_exist_in_all_languages():
    assert NAV_KEYS, "no nav_* keys in English"
    for lang in ("ms", "zh"):
        missing = [k for k in NAV_KEYS if k not in LABELS[lang]]
        assert not missing, (lang, missing)


def test_translation_lookup_and_fallbacks():
    assert t("nav_overview", "zh") == "总览"
    assert t("definitely_not_a_key", "en") == "definitely_not_a_key"
    assert "app_title" not in LABELS["ms"]
    assert t("app_title", "ms") == "AccessTwin"


def test_overview_renders_in_bahasa_malaysia():
    store.reset_demo()
    at = AppTest.from_file(PAGES["0"], default_timeout=90)
    at.session_state["lang"] = "ms"
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    assert at.button(key="guide_start").label == t("guide_start", "ms")


# ---------- 8. guided demo ----------

def test_guided_demo_has_seven_stops_covering_script_steps_in_order():
    assert len(guide.STOPS) == 7
    steps = [s.script_step for s in guide.STOPS]
    assert steps == sorted(steps)
    assert set(steps) == {1, 2, 3, 4, 5}
    assert steps[0] == 1 and steps[-1] == 5
    # V2 flow: the tour ends on the Deliver stage (study brief), after Compare.
    assert guide.STOPS[-1].page == "pages/9_Deliver.py"
    assert guide.STOPS[-2].page == "pages/8_Compare.py"


def test_guided_demo_start_and_exit_on_overview():
    store.reset_demo()
    at = _page("0")
    at.button(key="guide_start").click().run()
    assert not at.exception
    assert "Guided demo · Step 1/5" in _text(at)

    at.button(key="guide_exit").click().run()
    assert not at.exception
    assert "Guided demo · Step" not in _text(at)
    assert at.button(key="guide_start").label == t("guide_start")


# ---------- 9. accessibility ----------

def test_status_colours_are_v2_tokens_with_non_colour_cues():
    # Colours come from the V2 tokens (theme.TOKENS), not the old Okabe-Ito palette.
    assert STATUS_COLOURS["blocked"] == theme.TOKENS["state-blocked"]
    assert STATUS_COLOURS["unverified"] == theme.TOKENS["state-unknown"]
    assert STATUS_COLOURS["verified_accessible"] == theme.TOKENS["network-line"]
    # Distinct statuses use distinct colours.
    assert len(set(STATUS_COLOURS.values())) == len(STATUS_COLOURS)
    # Status is never colour alone: unverified is dashed, impassable-for-profile is dotted, blocked has a glyph.
    assert STATUS_DASH["unverified"] == "6 8"
    assert STATUS_DASH["verified_accessible"] is None and STATUS_DASH["blocked"] is None
    assert IMPASSABLE_DASH == "2 6"
    base = map_html(json.dumps({}))
    assert f'"dashArray": "{STATUS_DASH["unverified"]}"' in base
    # E7 (verified, step 15 cm) is impassable for a wheelchair user: drawn dotted in the impassable colour.
    wheel = map_html(json.dumps({}), persona_key="wheelchair")
    assert f'"dashArray": "{IMPASSABLE_DASH}"' in wheel
    assert f'"dashArray": "{IMPASSABLE_DASH}"' not in base
    # Blocked segment keeps its ✖ glyph and label in the rendered map.
    blocked = map_html(json.dumps({"E20": {"status": "blocked"}}))
    # folium JSON-escapes the glyph inside the script tag (literal backslash-u sequence).
    assert "E20: blocked" in blocked and ("✖" in blocked or "\\u2716" in blocked)


def test_blocked_segment_gets_a_non_colour_marker_in_map_html():
    blocked = map_html(json.dumps({"E20": {"status": "blocked"}}))
    # folium JSON-escapes the marker inside the script tag, so accept the literal glyph or its ✖ escape.
    assert "✖" in blocked or "\\u2716" in blocked
    assert "E20: blocked" in blocked
    assert STATUS_COLOURS["blocked"] in blocked

    # Contrast case: with E20 verified there is no blocked segment and no ✖ marker at all.
    clear = map_html(json.dumps({"E20": {"status": "verified_accessible"}}))
    assert "E20: blocked" not in clear
    assert "✖" not in clear and "\\u2716" not in clear


def test_about_page_has_accessibility_section_and_planned_items():
    at = _page("7")
    text = _text(at)
    assert "Accessibility of this app" in text
    assert "planned" in text


# ---------- 10. navigation ----------

def _app_nav_list() -> list[ast.Tuple]:
    tree = ast.parse((ROOT / "app.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t_, ast.Name) and t_.id == "NAV" for t_ in node.targets):
            return node.value.elts
    raise AssertionError("NAV list not found in app.py")


def test_app_registers_eleven_pages_with_network_first_and_hidden_nav():
    src = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "st.navigation(" in src and "st.Page(" in src
    assert 'position="hidden"' in src  # V2 project bar replaces the default page list
    nav = _app_nav_list()
    assert len(nav) == 11  # 2B adds Track my report (nav_track) as the last page
    assert nav[-1].elts[1].value == "nav_track"
    assert nav[0].elts[1].value == "stage_network"
    assert [e.elts[1].value for e in nav[1:3]] == ["stage_compare", "stage_deliver"]
    for entry in nav:
        assert (ROOT / entry.elts[0].value).exists(), entry.elts[0].value
