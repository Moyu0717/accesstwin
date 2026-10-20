"""Round 2 part 2A acceptance tests (branch v2-2a): wording, headings, Network Inspector order, Route Planner
report action, single-hue charts.

Covers: (a) banned terms in everything a user can read (every page, Network and Compare with the U1 scenario,
the brief HTML and the upgrade explanations), (b) no heading starts with an emoji, (c) Network Inspector order for
E7 and the "Scenario action" heading, (d) Route Planner wheelchair Block A -> Clinic conclusion and the report
action, (e) the Dashboard heatmap and Simulator bars are not RdYlGn / multi-hue.
Uses the isolated temp DB and mock mode from conftest.py.
"""
from __future__ import annotations

import colorsys
import html as htmllib
import json
import re
from pathlib import Path

import pyarrow as pa
import pytest
from streamlit.testing.v1 import AppTest
from streamlit.testing.v1.element_tree import (
    Block, ButtonGroup, Button, Code, Dataframe, HeadingBase, AlertBase, Json, Markdown, Metric, Multiselect,
    Radio, Selectbox, Toggle, UnknownElement,
)

from accesstwin.core import report, store
from accesstwin.core.demand import suppressed_demand
from accesstwin.core.footfall import camera_counts
from accesstwin.core.graph import load_graph
from accesstwin.core.personas import load_personas
from accesstwin.core.scoring import compute_scores
from accesstwin.core.simulation import load_upgrades, rank_upgrades, recommend_bundle
from accesstwin.ui import cached
from accesstwin.ui import components as ui
from accesstwin.ui import workspace as ws

ROOT = Path(__file__).resolve().parent.parent
PAGES = {p.name.split("_")[0]: str(p) for p in (ROOT / "pages").glob("*.py")}
BANNED = re.compile(r"\b(trips|resident[–-]persona|wheelchair index|roi)\b", re.IGNORECASE)
EMOJI_START = re.compile("^[\U0001F000-\U0001FAFF☀-➿⬀-⯿️‍]")


# ---------- helpers ----------

def _page(key: str, **state) -> AppTest:
    at = AppTest.from_file(PAGES[key], default_timeout=90)
    for k, v in state.items():
        at.session_state[k] = v
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    return at


def _walk(app):
    """Every element in document order, containers included (expanders are read for their labels).
    The root is AppTest's element tree (`_tree`); AppTest itself exposes no public children."""
    def rec(node):
        for _, child in sorted(node.children.items()):
            yield child
            if isinstance(child, Block):
                yield from rec(child)

    yield from rec(getattr(app, "_tree", app))


def _df_texts(el) -> list[str]:
    """Column headers as the user sees them (column_config label wins over the raw column name) and string cells."""
    try:
        cfg = json.loads(el.proto.columns or "{}")
    except (ValueError, AttributeError):
        cfg = {}
    try:  # the arrow schema has the column names even when AppTest cannot decode the frame (mixed-type columns)
        names = [str(n) for n in pa.ipc.open_stream(el.proto.arrow_data.data).schema.names]
    except Exception:
        names = []
    out = []
    try:
        df = el.value
    except Exception:
        df = None
    if not names and df is not None:
        names = [str(c) for c in df.columns]
    out += [str(cfg.get(n, {}).get("label", n)) for n in names if n != "_index"]
    if df is not None and hasattr(df, "astype"):
        out += [str(v) for v in df.astype(str).values.ravel()[:400]]
    return out


def _plotly_texts(spec: dict) -> list[str]:
    out = []

    def grab(d):
        t = d.get("title") if isinstance(d, dict) else None
        if isinstance(t, dict):
            t = t.get("text")
        if isinstance(t, str):
            out.append(t)

    lay = spec.get("layout", {})
    grab(lay)
    for ax in ("xaxis", "yaxis"):
        grab(lay.get(ax, {}))
    grab(lay.get("legend", {}))
    grab(lay.get("coloraxis", {}).get("colorbar", {}))
    out += [str(tr["name"]) for tr in spec.get("data", []) if tr.get("name")]
    return out


def _rendered(at) -> list[str]:
    """Everything a user can read on the page: markdown, captions, headings, metric labels and values, buttons,
    expander labels, alerts, widget labels and options, dataframe headers and cells, chart titles, graph labels."""
    out: list[str] = []
    for el in _walk(at):
        if isinstance(el, Block):
            if el.type == "expander":
                out.append(str(el.label))
            continue
        if isinstance(el, (Markdown, HeadingBase, AlertBase, Code)):
            out.append(str(el.value))
        elif isinstance(el, Metric):
            out += [str(el.label), str(el.value), str(el.delta or "")]
        elif isinstance(el, Button):
            out.append(str(el.label))
        elif isinstance(el, (Radio, Selectbox, Multiselect, ButtonGroup, Toggle)):
            out.append(str(getattr(el, "label", "") or ""))
            out += [str(o) for o in (getattr(el, "options", None) or [])]
        elif isinstance(el, Dataframe):
            out += _df_texts(el)
        elif isinstance(el, Json):
            out.append(str(el.value))
        elif isinstance(el, UnknownElement):
            if el.type == "download_button":
                out.append(str(el.proto.label))
            elif el.type == "plotly_chart":
                out += _plotly_texts(json.loads(el.proto.spec))
            elif el.type == "graphviz_chart":
                # Node/edge labels are what is drawn; the DOT identifiers are not shown.
                out += [m.replace("\\n", " ") for m in re.findall(r'label="([^"]*)"', el.proto.spec)]
    return out


def _html_text(doc: str) -> str:
    doc = re.sub(r"<style.*?</style>", " ", doc, flags=re.S | re.I)
    doc = re.sub(r"<[^>]+>", " ", doc)
    return htmllib.unescape(doc)


def _banned_hits(texts) -> list[str]:
    return [f"{m.group(0)!r} in {s[:120]!r}" for s in texts for m in BANNED.finditer(s)]


def _md(at) -> str:
    return "\n".join(str(m.value) for m in at.markdown)


def _fact(at, label: str) -> str | None:
    m = re.search(rf"<div class='at-muted'>{re.escape(label)}</div><div class='at-big'[^>]*>([^<]*)</div>", _md(at))
    return m.group(1) if m else None


def _sequence(at) -> list[tuple]:
    """Markdown/heading text and buttons in document order: ("text", value) or ("button", key, label)."""
    seq = []
    for el in _walk(at):
        if isinstance(el, (Markdown, HeadingBase)):
            seq.append(("text", str(el.value)))
        elif isinstance(el, Button):
            seq.append(("button", el.key, str(el.label)))
    return seq


def _first(seq, start: int, pred):
    for i in range(start, len(seq)):
        if pred(seq[i]):
            return i
    return None


@pytest.fixture(autouse=True)
def _fresh_demo():
    store.reset_demo()
    yield


# ---------- (a) banned terms ----------

def _plain(at):
    return at


def _click(key):
    def go(at):
        at.button(key=key).click().run()
        return at
    return go


def _radio(key, value):
    def go(at):
        at.radio(key=key).set_value(value).run()
        return at
    return go


# (name, page key, how to prepare the page). The U1 scenario is switched on with the Network "Preview ramp" button
# and on Compare with the Scenario map view.
SCENARIOS = [
    ("network", "0", _plain),
    ("network-u1-scenario", "0", _click("ws_preview_top")),
    ("network-guided-demo", "0", _click("guide_start")),
    ("route-planner", "1", _plain),
    ("report-obstacle", "2", _plain),
    ("verification-queue", "3", _plain),
    ("footfall", "4", _plain),
    ("simulator", "5", _plain),
    ("simulator-design", "5", _radio("sim_mode", "design")),
    ("dashboard", "6", _plain),
    ("dashboard-design", "6", _radio("dash_mode", "design")),
    ("about", "7", _plain),
    ("compare", "8", _plain),
    ("compare-u1-scenario", "8", _radio("cmp_view", "Scenario")),
    ("deliver", "9", _plain),
]


@pytest.mark.parametrize("name, page, prepare", SCENARIOS, ids=[s[0] for s in SCENARIOS])
def test_no_banned_terms_in_rendered_text(name, page, prepare):
    at = prepare(_page(page))
    assert not at.exception, [e.message for e in at.exception]
    texts = _rendered(at)
    assert len(texts) > 5, "the scan collected almost nothing; the walker is broken"
    assert not _banned_hits(texts), _banned_hits(texts)


def test_banned_term_scanner_catches_each_banned_term_and_passes_the_new_wording():
    for bad in ["3 trips a day", "resident–persona trips", "resident-persona", "a Wheelchair index", "ROI", "roi"]:
        assert _banned_hits([bad]), bad
    for good in ["Access Score — Wheelchair", "upgrade priority score", "estimated residents (model)",
                 "newly reachable combinations (modelled)"]:
        assert not _banned_hits([good]), good


def test_banned_term_scan_reads_dataframe_headers_and_chart_titles():
    # Guards the scanner itself: the labels checked above really are collected from the rendered elements.
    sim = _rendered(_page("5"))
    assert "upgrade priority score" in sim  # dataframe header from column_config
    assert "Upgrade priority score" in sim  # plotly axis title
    assert "barriers on route" in _rendered(_page("4"))  # demand table header on Footfall


def test_simulator_metric_labels_do_not_say_wheelchair_index():
    # Explicit guard for the metric the scan above reports: the per-profile metric must use "Access Score — <profile>".
    at = _page("5")
    labels = [m.label for m in at.metric]
    assert not [x for x in labels if BANNED.search(x)], labels


def test_brief_html_has_no_banned_terms():
    G, P = load_graph(), load_personas()
    scores = compute_scores(G, P)
    upgrades = load_upgrades()
    ranking = rank_upgrades(G, upgrades, P)
    bundle = recommend_bundle(G, upgrades, P, ranking=ranking)
    demand = suppressed_demand(G, P, camera_counts())
    reports = store.list_reports()
    operate = report.brief_html(G, P, scores, ranking, demand, reports, "operate", bundle)
    design = report.brief_html(G, P, scores, ranking, demand, reports, "design", bundle)
    for name, doc in (("operate", operate), ("design", design)):
        text = _html_text(doc)
        assert not _banned_hits([text]), (name, _banned_hits([text]))


def test_study_brief_html_has_no_banned_terms():
    okey = ui.overlay_key()
    loc = ws.find_location(okey, "E7")
    rows = ws.compare_rows(okey, loc, "wheelchair")
    section = {"location": f"{loc.label} ({loc.edge_id})", "upgrade": loc.upgrade["title"], "rows": rows,
               "steps": [], "version": cached.data_version(okey), "evidence": ws.evidence_thumbs(loc.edge_id)}
    doc = cached.brief_html(okey, ws.counts_key(), "operate", ws.reports_key(), ws.scenario_json(section))
    assert not _banned_hits([_html_text(doc)]), _banned_hits([_html_text(doc)])


def test_upgrade_explanations_have_no_banned_terms():
    G, P = load_graph(), load_personas()
    upgrades = load_upgrades()
    texts: list[str] = []
    for mode in ("operate", "design"):
        ranking = rank_upgrades(G, upgrades, P)
        texts += [str(x) for x in ranking["explanation"].tolist()]
    bundle = recommend_bundle(G, upgrades, P, ranking=rank_upgrades(G, upgrades, P))
    if bundle is not None:
        texts.append(bundle.explanation)
    for u in upgrades:
        texts += [str(u[k]) for k in ("title", "rationale") if isinstance(u.get(k), str)]
    assert texts
    assert not _banned_hits(texts), _banned_hits(texts)


# ---------- (b) no heading starts with an emoji ----------

def _headings(at) -> list[str]:
    out = []
    for el in _walk(at):
        if isinstance(el, (HeadingBase,)):
            out.append(str(el.value))
        elif isinstance(el, Markdown):
            v = str(el.value).strip()
            if v.startswith("#"):
                out.append(v.lstrip("#").strip())
            out += [re.sub(r"<[^>]+>", "", h).strip() for h in re.findall(r"<h[1-6][^>]*>(.*?)</h[1-6]>", v, re.S)]
    return out


@pytest.mark.parametrize("name, page, prepare", SCENARIOS, ids=[s[0] for s in SCENARIOS])
def test_no_page_title_or_subheader_starts_with_an_emoji(name, page, prepare):
    at = prepare(_page(page))
    heads = [h for h in _headings(at) if h]
    assert heads, "no headings collected; the heading scan is broken"
    bad = [h for h in heads if EMOJI_START.match(h)]
    assert not bad, bad


# ---------- (c) Network Inspector order for E7 ----------

INSPECTOR_MARK = "<span class='at-ws-inspector'></span>"


def test_network_inspector_shows_evidence_before_action_and_condition_for_e7():
    at = _page("0")
    seq = _sequence(at)
    start = _first(seq, 0, lambda x: x[0] == "text" and INSPECTOR_MARK in x[1])
    assert start is not None, "Inspector marker not found"
    hero = _first(seq, start, lambda x: x[0] == "text" and "at-hero-cap" in x[1])
    cond = _first(seq, start, lambda x: x[0] == "text" and "Existing condition" in x[1])
    action = _first(seq, start, lambda x: x[0] == "button" and x[1] == "ws_preview_top")
    assert hero is not None and cond is not None and action is not None
    assert hero < cond, "evidence hero must precede 'Existing condition'"
    assert hero < action, "evidence hero must precede the action button"

    # The hero carries the newest photo's chip, caption and the Wikimedia credit line.
    photos = [r for r in ws.edge_evidence("E7") if r["photo"]]
    newest = photos[0]
    hero_html = seq[hero][1]
    assert f"Report #{newest['id']} · Pending review" in hero_html
    assert ui.photo_credit_line(newest["photo"].name) in htmllib.unescape(hero_html)
    assert ui.photo_credit_line(newest["photo"].name).startswith("Photo: ")
    assert ui.photo_credit_line(newest["photo"].name).endswith("Wikimedia Commons")

    # Baseline heading reads "Next action"; the enlarge control is a button in the hero.
    inspector_text = [x[1] for x in seq[start:] if x[0] == "text"]
    assert any("Next action" in t for t in inspector_text)
    assert any(b[1] == "ws_enlarge_E7" for b in seq[start:] if b[0] == "button")


def test_network_inspector_says_scenario_action_in_scenario_mode():
    at = _page("0")
    at.button(key="ws_preview_top").click().run()
    assert not at.exception
    seq = _sequence(at)
    start = _first(seq, 0, lambda x: x[0] == "text" and INSPECTOR_MARK in x[1])
    inspector_text = [x[1] for x in seq[start:] if x[0] == "text"]
    assert any("Scenario action" in t for t in inspector_text)
    assert not any("Next action" in t for t in inspector_text)
    # 2A-1 scenario hero keeps the same order: evidence before the scenario 'Return to baseline' button.
    hero = _first(seq, start, lambda x: x[0] == "text" and "at-hero-cap" in x[1])
    ret = _first(seq, start, lambda x: x[0] == "button" and x[1] == "ws_return_top")
    assert hero is not None and ret is not None and hero < ret


def test_network_inspector_without_photo_offers_report_and_inspection_buttons():
    at = _page("0")
    at.button(key="ws_row_E22").click().run()
    assert not at.exception
    text = _md(at)
    assert "No photo evidence yet" in text
    keys = {b.key for b in at.button}
    assert {"ws_report_E22", "ws_inspect_E22"} <= keys


def test_network_scenario_score_line_is_one_sentence():
    at = _page("0")
    at.button(key="ws_preview_top").click().run()
    text = _md(at)
    assert re.search(r"\+\d+\.\d points vs baseline \d+\.\d · simulated", text)
    # The old separate "Baseline X · Simulated Y" line is gone.
    assert not re.search(r"Baseline \d+\.\d\s*·\s*Simulated", text)


# ---------- (d) Route Planner ----------

def _route_planner(origin: str, dest: str, persona: str) -> AppTest:
    at = AppTest.from_file(PAGES["1"], default_timeout=90)
    at.session_state["persona"] = persona
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    at.selectbox(key="rp_origin").set_value(origin).run()
    at.selectbox(key="rp_dest").set_value(dest).run()
    assert not at.exception, [e.message for e in at.exception]
    return at


def test_wheelchair_block_a_to_clinic_says_detour_needed_with_1_1_km():
    at = _route_planner("R1", "D_CLINIC", "wheelchair")
    text = _md(at)
    assert "Detour needed · 1.1 km" in text
    assert _fact(at, "Distance") == "1.1 km"
    assert _fact(at, "Reference path") == "450 m"
    assert not at.metric, "facts are HTML now; the page must not use st.metric"


def test_route_planner_report_button_names_the_blocking_segment_and_queues_it():
    at = _route_planner("R1", "D_CLINIC", "wheelchair")
    btn = at.button(key="rp_report")
    assert btn.label == "Report an obstacle on this route (E7)"
    btn.click().run()
    assert not at.exception, [e.message for e in at.exception]
    # The preset is applied on the next run (guide.apply_pending); the Report form then opens on E7.
    assert at.session_state["ro_edge"] == "E7"


def test_report_page_honours_the_queued_edge_preset():
    rep = AppTest.from_file(PAGES["2"], default_timeout=90)
    rep.session_state["guide_pending"] = {"ro_edge": "E7", "ro_src": "Use a sample photo"}
    rep.run()
    assert not rep.exception, [e.message for e in rep.exception]
    assert rep.selectbox(key="ro_edge").value == "E7"


def test_compare_all_profiles_table_uses_plain_values():
    at = _route_planner("R1", "D_CLINIC", "wheelchair")
    df = next(d.value for d in at.dataframe if "profile" in getattr(d.value, "columns", []))
    rows = {r["profile"]: r for r in df.to_dict("records")}
    assert rows["Wheelchair"]["direct route"] == "interrupted"
    assert rows["Wheelchair"]["reachable"] == "yes"
    assert rows["Older adult"]["direct route"] == "usable"
    assert set(df["direct route"]) <= {"usable", "interrupted"}
    assert set(df["reachable"]) <= {"yes", "no"}
    assert "Compare all profiles for this trip" in [e.label for e in at.expander]


# ---------- (e) single-hue charts ----------

def _hsv(hex_colour: str) -> tuple[float, float, float]:
    h = hex_colour.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return colorsys.rgb_to_hsv(r, g, b)


def test_dashboard_heatmap_is_not_rdylgn_and_stays_in_the_teal_family():
    source = Path(PAGES["6"]).read_text(encoding="utf-8")
    assert "RdYlGn" not in source
    at = _page("6")
    heat = [json.loads(el.proto.spec) for el in at.get("plotly_chart")]
    heat = [s for s in heat if any(t.get("type") == "heatmap" for t in s.get("data", []))]
    assert len(heat) == 1, "expected exactly one gap heatmap"
    spec = heat[0]
    assert "RdYlGn" not in json.dumps(spec)
    scale = spec["layout"]["coloraxis"]["colorscale"]
    assert len(scale) >= 2
    for _, colour in scale:
        hue, sat, _ = _hsv(colour)
        if sat >= 0.15:  # near-white stops have no meaningful hue; saturated stops must be teal
            assert 150 <= hue * 360 <= 200, (colour, hue * 360)


def test_simulator_bars_are_single_hue():
    at = _page("5")
    bars = []
    for el in at.get("plotly_chart"):
        spec = json.loads(el.proto.spec)
        bars += [t["marker"]["color"] for t in spec.get("data", []) if t.get("type") == "bar" and "marker" in t]
    colours = [c for c in bars if isinstance(c, str) and c.startswith("#")]
    assert colours, "no bar colours found in the Upgrade Simulator chart"
    hues = [_hsv(c)[0] * 360 for c in colours if _hsv(c)[1] >= 0.15]
    assert hues and max(hues) - min(hues) < 15, colours
    assert "RdYlGn" not in Path(PAGES["5"]).read_text(encoding="utf-8")
