"""Codex UI review, phase 1 (UI-01..UI-05): placeholder removal, example-photo labelling, explicit photo choice,
resident role control, map key labels / extent / legend, street-map flag and the fragment sandbox re-bind.

Every page test starts from a fresh demo DB in the isolated temp DB from conftest.py. No test touches the network.
"""
from __future__ import annotations

import functools
import json
import re
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from accesstwin import config
from accesstwin.core import report, store
from accesstwin.core.demand import suppressed_demand
from accesstwin.core.footfall import camera_counts
from accesstwin.core.graph import load_graph
from accesstwin.core.obstacles import PLACEHOLDER_PHOTOS
from accesstwin.core.personas import load_personas
from accesstwin.core.scoring import compute_scores
from accesstwin.core.simulation import load_upgrades, rank_upgrades, recommend_bundle
from accesstwin.ui import components as ui
from accesstwin.ui import guide
from accesstwin.ui import theme
from accesstwin.ui import workspace as ws
from accesstwin.ui.map_view import legend_html, map_html

ROOT = Path(__file__).resolve().parent.parent
PAGES = {p.name.split("_")[0]: str(p) for p in (ROOT / "pages").glob("*.py")}
PLACEHOLDER_NAMES = {
    "curb_high_step.png", "dark_path_night.png", "gravel_path_school.png",
    "path_crack_broken.png", "ramp_blocked_car.png",
}
KERB = "kerb_high_granite_step.jpg"
EXAMPLE_EXPANDER = "Example photos — not taken at these locations"
DEMO_EXPANDER = "Demo settings (for trying the demo only)"
INTERNAL_STATUS_WORDS = ("verified_accessible", "unverified", "verified", "blocked", "impassable", "has_step")


# ---------- helpers ----------

def _page(key: str, **state) -> AppTest:
    at = AppTest.from_file(PAGES[key], default_timeout=90)
    for k, v in state.items():
        at.session_state[k] = v
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    return at


def _walk(node):
    """Every element of an AppTest block in document order (depth first)."""
    yield node
    for child in getattr(node, "children", {}).values():
        yield from _walk(child)


def _images(at: AppTest) -> list[str]:
    """Captions of every st.image element on the page (AppTest exposes them as UnknownElement 'imgs')."""
    out: list[str] = []
    for n in _walk(at.main):
        if getattr(n, "type", None) == "imgs":
            out.extend(im.caption for im in n.proto.imgs)
    return out


def _seq(at: AppTest) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for n in _walk(at.main):
        kind = getattr(n, "type", None)
        if kind in ("markdown", "caption"):
            out.append((kind, str(n.value)))
    return out


def _markdown(at: AppTest) -> str:
    return "\n".join(m.value for m in at.markdown)


def _raw_html(at: AppTest) -> str:
    return "\n".join(m.value for m in at.markdown if m.proto.allow_html)


def _buttons(at: AppTest) -> set[str]:
    return {b.key for b in at.button if b.key}


def _expander(at: AppTest, label: str):
    return next((e for e in at.expander if e.label == label), None)


def _seed_reports(edge: str | None = None) -> list[dict]:
    return [r for r in store.list_reports() if (r.get("ai") or {}).get("source") == "seed"
            and (edge is None or r["edge_id"] == edge)]


def _credited_names() -> list[str]:
    return sorted(n for n in ui.photo_credits() if (config.PHOTOS_DIR / n).exists())


def _bounds(html: str) -> list[list[float]]:
    """Every fitBounds([[lat, lon], [lat, lon]], ...) bounds in a rendered map, as floats."""
    found = re.findall(r"fitBounds\((\[\[[^\]]*\],\s*\[[^\]]*\]\])", html)
    assert found, "no fitBounds call in the map"
    parsed = [json.loads(b) for b in found]
    assert all(b == parsed[0] for b in parsed), "map calls fitBounds with different bounds"
    return parsed[0]


def _township_nodes() -> dict:
    with open(config.DATA_DIR / "township.json", encoding="utf-8") as f:
        return {n["id"]: n for n in json.load(f)["nodes"]}


# ---------- A. Report page: nothing chosen by default, analysis needs a chosen photo ----------

def test_report_page_starts_with_no_photo_and_no_example_image():
    store.reset_demo()
    at = _page("2")
    assert at.radio(key="ro_src").value == "No photo"
    assert at.radio(key="ro_src").options == ["No photo", "Upload a photo", "Use an example photo"]
    assert _expander(at, EXAMPLE_EXPANDER) is None, "the example gallery must not show before it is chosen"
    assert not _images(at), "no image may be rendered before a photo is chosen"
    assert not any(k.startswith("ro_pick_") for k in _buttons(at))
    assert "ro_analyse" not in _buttons(at)
    assert not any("data:image" in m.value for m in at.markdown), "no thumbnail HTML before a choice"


def test_example_source_opens_collapsed_gallery_with_no_selection():
    store.reset_demo()
    at = _page("2")
    at.radio(key="ro_src").set_value("Use an example photo").run()
    gallery = _expander(at, EXAMPLE_EXPANDER)
    assert gallery is not None, "example gallery expander missing"
    assert not _images(at), "choosing the source alone must not show a selected photo"
    sel = at.selectbox(key="ro_sample")
    assert sel.value is None, "no example photo may be pre-selected"
    assert sel.proto.placeholder == "Choose an example photo"
    assert "ro_analyse" not in _buttons(at)


def test_analyse_needs_a_selected_photo():
    store.reset_demo()
    at = _page("2")
    # Nothing chosen: no analyse button.
    assert "ro_analyse" not in _buttons(at)
    # Example source chosen but no photo picked: still no analyse button.
    at.radio(key="ro_src").set_value("Use an example photo").run()
    assert "ro_analyse" not in _buttons(at)
    # Upload source chosen without a file: no analyse button either.
    at.radio(key="ro_src").set_value("Upload a photo").run()
    assert "ro_analyse" not in _buttons(at)
    # Picking an example makes the analyse button appear; it does not analyse by itself.
    at.radio(key="ro_src").set_value("Use an example photo").run()
    at.button(key=f"ro_pick_{KERB}").click().run()
    assert at.selectbox(key="ro_sample").value == KERB
    assert "ro_analyse" in _buttons(at)
    assert not any("Suggested type" in m.value for m in at.markdown)


def test_selected_example_image_caption_carries_example_label_and_credit():
    store.reset_demo()
    at = _page("2")
    at.radio(key="ro_src").set_value("Use an example photo").run()
    at.button(key=f"ro_pick_{KERB}").click().run()
    captions = _images(at)
    assert captions, "the selected example photo is not shown"
    assert captions[0] == f"{ui.example_label()} · {ui.photo_credit_line(KERB)}"


def test_example_gallery_captions_carry_label_next_to_credit():
    store.reset_demo()
    at = _page("2")
    at.radio(key="ro_src").set_value("Use an example photo").run()
    captions = [c.value for c in at.caption]
    for name in _credited_names():
        expected = f"{ui.example_label()} · {ui.photo_credit_line(name)}"
        assert expected in captions, name
        assert f"ro_pick_{name}" in _buttons(at), name


def test_resident_form_has_no_role_control_outside_demo_expander():
    store.reset_demo()
    at = _page("2")
    role_radios = [r for r in at.radio if r.key == "ro_role"]
    assert len(role_radios) == 1
    demo = _expander(at, DEMO_EXPANDER)
    assert demo is not None, "demo settings expander missing"
    assert "ro_role" in [r.key for r in demo.radio]
    assert role_radios[0].value == "resident"
    # No other radio offers the resident/guard choice, and the resident form is named as resident.
    assert not [r for r in at.radio if r.key != "ro_role" and {"resident", "guard"} & set(r.options)]
    assert "Report as (demo role)" not in _markdown(at)
    assert "as resident" in " ".join(c.value for c in at.caption)


def test_location_selectbox_never_shows_internal_status_words():
    store.reset_demo()
    at = _page("2")
    options = at.selectbox(key="ro_edge").options
    assert len(options) >= 20, "every walkway segment should be offered"
    for label in options:
        for word in INTERNAL_STATUS_WORDS:
            assert word not in label.lower(), (label, word)
        assert " · " in label and "→" in label, label  # "E7 · from → to" form, residents see place names
    assert any(label.startswith("E7 · ") for label in options)


def test_sidebar_profile_rules_render_as_key_value_html_not_json():
    store.reset_demo()
    at = _page("2")
    assert not [n for n in _walk(at.main) if getattr(n, "type", None) == "json"]
    kv = [m.value for m in at.markdown if "at-kv" in m.value and "Steps allowed" in m.value]
    assert kv, "profile rules are not rendered as key/value rows"


# ---------- B. placeholder PNGs are gone and nothing points at them ----------

def test_no_placeholder_png_exists_on_disk():
    for name in PLACEHOLDER_NAMES:
        assert not (config.PHOTOS_DIR / name).exists(), name
    assert not [p.name for p in config.PHOTOS_DIR.glob("*.png")]
    assert PLACEHOLDER_PHOTOS == set()


def test_no_placeholder_is_referenced_by_sample_reports():
    with open(config.SAMPLE_REPORTS_PATH, encoding="utf-8") as f:
        seeds = json.load(f)
    credits = ui.photo_credits()
    for s in seeds:
        photo = s.get("photo")
        assert photo not in PLACEHOLDER_NAMES, s["id"]
        if photo:
            assert (config.PHOTOS_DIR / photo).exists(), (s["id"], photo)
            assert photo in credits, (s["id"], photo)


def test_no_placeholder_is_referenced_by_the_guide():
    text_fields = []
    for stop in guide.STOPS:
        text_fields += [stop.page, stop.title, stop.look, stop.do]
        text_fields += [json.dumps(stop.preset_next, ensure_ascii=False)]
    blob = "\n".join(text_fields)
    for name in PLACEHOLDER_NAMES:
        assert name not in blob, name
    # The guided preset photo is a real, credited example.
    presets = [s.preset_next.get("ro_sample") for s in guide.STOPS if s.preset_next.get("ro_sample")]
    assert presets == [KERB]
    assert (config.PHOTOS_DIR / KERB).exists() and KERB in ui.photo_credits()


# ---------- C. example photos carry the example label (UI-05) ----------

def test_network_hero_labels_example_photo_next_to_its_credit():
    store.reset_demo()
    at = _page("0")
    html = _markdown(at)
    name = KERB
    assert ui.photo_credit_line(name) in html
    assert ui.example_label() in html, "example badge missing from the Network evidence hero"
    # The badge sits in the same hero block, above the caption and credit line.
    hero_start = html.index("at-hero'>")
    badge = html.index("class='at-example'", hero_start)
    credit = html.index("class='at-hero-credit'", hero_start)
    assert hero_start < badge < credit


def test_queue_detail_labels_example_photo_under_the_photo():
    store.reset_demo()
    seeds = [r for r in _seed_reports() if r["status"] == "pending" and r.get("photo_path")]
    assert seeds, "no pending seed report with a photo to check"
    for r in seeds:
        at = _page("3")
        at.button(key=f"vq_row_{r['id']}").click().run()
        assert not at.exception
        seq = _seq(at)
        name = Path(r["photo_path"]).name
        assert name in ui.photo_credits(), name
        badge = next(i for i, (k, v) in enumerate(seq) if k == "markdown" and "class='at-example'" in v)
        credit = next(i for i, (k, v) in enumerate(seq) if k == "caption" and v == ui.photo_credit_line(name))
        assert badge < credit, name
        assert ui.example_label() in seq[badge][1], name


def test_brief_evidence_captions_label_example_photos():
    store.reset_demo()
    seed_edges = sorted({r["edge_id"] for r in _seed_reports()})
    assert seed_edges
    captions = [t["caption"] for edge in seed_edges for t in ws.evidence_thumbs(edge)]
    examples = [c for c in captions if c.startswith("Example report #")]
    seeds_with_photo = [r for r in _seed_reports() if r.get("photo_path")]
    assert len(examples) == len(seeds_with_photo) >= 3
    for cap in examples:
        name = next(n for n in ui.photo_credits() if ui.photo_credit_line(n) in cap)
        assert ui.example_label() in cap, cap
        assert cap.index(ui.example_label()) < cap.index(ui.photo_credit_line(name)), cap
    # A resident report with a credited photo is still an example photo, but not an "Example report".
    assert not [c for c in captions if c.startswith("Report #") and ui.example_label() not in c]


def test_brief_document_shows_example_label_with_evidence():
    store.reset_demo()
    G, personas = load_graph(), load_personas()
    ranking = rank_upgrades(G, load_upgrades(), personas)
    bundle = recommend_bundle(G, load_upgrades(), personas, ranking=ranking)
    demand = suppressed_demand(G, personas, camera_counts())
    scenario = {"location": "Clinic approach (E7)", "upgrade": "Low-cost kerb ramp", "version": "test",
                "rows": [], "steps": [], "evidence": ws.evidence_thumbs("E7")}
    doc = report.brief_html(G, personas, compute_scores(G, personas), ranking, demand, store.list_reports(),
                            "operate", bundle, scenario=scenario)
    assert "<h3>Evidence</h3>" in doc
    assert ui.example_label() in doc
    assert ui.photo_credit_line(KERB) in doc


def test_uploaded_photo_is_not_labelled_as_an_example():
    hashed = "3f9a1c0b7d2e.jpg"
    assert not ui.is_example_photo(hashed)
    assert ui.photo_credit_line(hashed) == "Uploaded in this session"
    assert ui.is_example_photo(KERB)


# ---------- D. seed reports are labelled "Example report" (UI-05) ----------

def test_network_labels_seed_report_as_example_report():
    store.reset_demo()
    seed = next(r for r in _seed_reports("E7"))
    at = _page("0")
    html = _markdown(at)
    assert f"Example report #{seed['id']} · Pending review" in html
    assert "Example report · Resident" in html  # the caption under the photo names the example too


def test_network_labels_resident_report_as_plain_report():
    store.reset_demo()
    rep_id = store.add_report("E7", "resident", "data/photos/pavement_cracked_broken.jpg",
                              {"obstacle_type": "other"})
    at = _page("0")
    html = _markdown(at)
    assert f"Report #{rep_id} · Pending review" in html
    assert f"Example report #{rep_id}" not in html


def test_queue_labels_seed_reports_as_example_report():
    store.reset_demo()
    seeds = [r for r in _seed_reports() if r["status"] == "pending"]
    assert seeds
    for r in seeds:
        at = _page("3")
        at.button(key=f"vq_row_{r['id']}").click().run()
        assert "<span class='at-chip syn'>Example report</span>" in _markdown(at), r["id"]


def test_queue_does_not_label_resident_report_as_example():
    store.reset_demo()
    rid = store.submit_report("E9", "resident", "Gap in the path", None,
                              {"obstacle_type": "other", "severity": "low", "affected_personas": [],
                               "confidence": 0.0, "visible_evidence": "", "needs_onsite_measurement": []},
                              None, "k-phase1-queue")["id"]
    at = _page("3")
    at.button(key=f"vq_row_{rid}").click().run()
    html = _markdown(at)
    assert "Example report" not in html
    assert "Pending review" in html


# ---------- E. theme: captions are legible (UI-01) ----------

def test_caption_opacity_rule_present_in_theme_css():
    css = theme.css()
    assert re.search(r'\[data-testid="stCaptionContainer"\]\s*\{\s*opacity:\s*1\s*!important\s*\}', css)


# ---------- F. map: key labels, fit extent, phone CSS, legend (UI-02) ----------

def test_map_key_nodes_mark_exactly_those_labels_key():
    nodes = _township_nodes()
    labelled = [n for n, d in nodes.items() if d.get("type") in ("residential", "destination")]
    keys = ["R1", "D_CLINIC"]
    html = map_html(json.dumps({}), key_nodes_key=json.dumps(keys))
    classes = re.findall(r'"className": "(at-lbl[^"]*)"', html)
    assert len(classes) == len(labelled)
    assert classes.count("at-lbl key") == len(keys)
    assert classes.count("at-lbl") == len(labelled) - len(keys)


def test_map_without_key_nodes_has_no_key_labels():
    html = map_html(json.dumps({}))
    classes = re.findall(r'"className": "(at-lbl[^"]*)"', html)
    assert classes and "at-lbl key" not in classes


def _flat(bounds) -> list[float]:
    return [float(x) for pair in bounds for x in pair]


def test_map_fit_key_changes_the_fitbounds_extent():
    nodes = _township_nodes()
    default = _bounds(map_html(json.dumps({})))
    fit = ["R1", "D_CLINIC"]
    lats = [nodes[n]["lat"] for n in fit]
    lons = [nodes[n]["lon"] for n in fit]
    expected = [[min(lats), min(lons)], [max(lats), max(lons)]]
    fitted = _bounds(map_html(json.dumps({}), fit_key=json.dumps(fit)))
    assert fitted != default
    assert _flat(fitted) == pytest.approx(_flat(expected))
    # Whole-network bounds cover every node.
    all_lats = [d["lat"] for d in nodes.values()]
    all_lons = [d["lon"] for d in nodes.values()]
    assert _flat(default) == pytest.approx(_flat([[min(all_lats), min(all_lons)], [max(all_lats), max(all_lons)]]))


def test_phone_css_hides_non_key_labels():
    html = map_html(json.dumps({}), key_nodes_key=json.dumps(["R1"]))
    assert re.search(r"@media \(max-width: 600px\)\s*\{\s*\.at-lbl:not\(\.key\)\s*\{\s*display:\s*none",
                     html), "phone rule hiding non-key labels is missing"


def test_legend_html_escapes_text():
    out = legend_html([("2px solid red", "<img src=x onerror=alert(1)>")], "<script>x</script>")
    assert "<img" not in out and "<script" not in out
    assert "&lt;img src=x onerror=alert(1)&gt;" in out
    assert "&lt;script&gt;x&lt;/script&gt;" in out


def test_legend_html_escapes_style_attribute():
    out = legend_html([('2px solid red" onmouseover="alert(1)', "Route")])
    assert 'onmouseover="' not in out
    assert "&quot;" in out


def test_network_does_not_pass_legend_into_the_map():
    src = Path(PAGES["0"]).read_text(encoding="utf-8")
    assert "legend_key" not in src
    assert "legend_html(" in src, "the Network legend must be rendered outside the map"


# ---------- G. street map toggle only behind the dev flag (ISSUE-14) ----------

def test_network_hides_street_map_toggle_without_env_flag(monkeypatch):
    monkeypatch.delenv("ACCESSTWIN_DEV_STREETMAP", raising=False)
    store.reset_demo()
    at = _page("0")
    assert "ws_street" not in [t.key for t in at.toggle]


def test_network_hides_street_map_toggle_when_flag_is_zero(monkeypatch):
    monkeypatch.setenv("ACCESSTWIN_DEV_STREETMAP", "0")
    store.reset_demo()
    at = _page("0")
    assert "ws_street" not in [t.key for t in at.toggle]


def test_network_shows_street_map_toggle_with_env_flag(monkeypatch):
    monkeypatch.setenv("ACCESSTWIN_DEV_STREETMAP", "1")
    store.reset_demo()
    at = _page("0")
    toggle = next(t for t in at.toggle if t.key == "ws_street")
    assert toggle.value is False  # off by default: the street tiles are never drawn unless the user switches them on


# ---------- H. fragment wrapper re-binds the sandbox before the body (X1) ----------

def test_fragment_wrapper_calls_use_session_before_the_body(monkeypatch):
    monkeypatch.setattr(st, "fragment", lambda func: func)
    calls: list[tuple] = []
    monkeypatch.setattr(store, "use_session", lambda sid: calls.append(("bind", sid)))
    monkeypatch.setattr(ui, "session_id", lambda: "sess-phase1")

    def body(x):
        calls.append(("body", x))
        return x * 2

    wrapped = ui.fragment(body)
    assert wrapped(3) == 6
    assert calls == [("bind", "sess-phase1"), ("body", 3)]
    assert wrapped.__name__ == "body" and wrapped.__wrapped__ is body


def test_pages_use_the_ui_fragment_wrapper_for_fragments():
    for key in ("1", "4", "5", "6"):
        src = Path(PAGES[key]).read_text(encoding="utf-8")
        assert "@ui.fragment" in src, PAGES[key]
        assert "st.fragment" not in src, PAGES[key]
