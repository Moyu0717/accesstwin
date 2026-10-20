"""Regression tests for fix pack F1-F3: static cached maps, pinned deps, lean repo guard, safe pages, cache reset."""
import json
import re
import sys
from pathlib import Path

import streamlit
from streamlit.testing.v1 import AppTest

from accesstwin.core import store
from accesstwin.core.graph import build_graph, iter_edges, load_township
from accesstwin.ui.map_view import UPGRADED_COLOUR, map_html

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import check_tracked  # noqa: E402



def _map(**kw) -> str:
    args = dict(overlay_key="{}")
    args.update(kw)
    return map_html(**args)


# ---- F3: map_html -----------------------------------------------------------

def test_map_html_is_leaflet_html_string():
    html = _map()
    assert isinstance(html, str)
    assert "leaflet" in html.lower()


def test_map_html_hides_edge_id_labels_by_default_and_shows_them_on_request():
    assert "font-size:9px" not in _map()
    assert "font-size:9px" in _map(show_ids=True)


def test_map_html_draws_route_polyline_with_its_node_coordinates():
    G = build_graph(load_township(), None)
    edge = next(iter(iter_edges(G)))
    a, b = G.nodes[edge["from"]], G.nodes[edge["to"]]
    colour = "#7C3AED"
    # Route runs to->from, so the rendered coordinate pair is reversed relative to the base edge polyline.
    route = [[edge["to"], edge["from"]], colour, False, "test route"]
    html = _map(routes_key=json.dumps([route]))
    assert colour in html
    lat_lon = (f"[{float(b['lat'])!r}, {float(b['lon'])!r}]", f"[{float(a['lat'])!r}, {float(a['lon'])!r}]")
    assert lat_lon[0] in html and lat_lon[1] in html


def test_map_html_applies_highlight_after_upgrade():
    # V2 plan-view palette: the upgraded segment is drawn in UPGRADED_COLOUR (was amber #F59E0B).
    html = _map(upgrades_key='["U1"]', highlight_key='["E7"]')
    assert UPGRADED_COLOUR in html
    assert "#F59E0B" not in html


def test_map_html_draws_circle_marker_for_circles_key():
    base = _map()
    html = _map(circles_key=json.dumps([["E7", 12, "#123456", "tip"]]))
    assert "#123456" in html
    assert "#123456" not in base
    assert html.count("L.circleMarker(") > base.count("L.circleMarker(")


def test_map_html_is_cached_and_deterministic():
    kwargs = dict(overlay_key="{}", persona_key="wheelchair", routes_key="[]", highlight_key='["E7"]')
    first = map_html(**kwargs)
    second = map_html(**kwargs)
    assert first == second


def test_no_streamlit_folium_import_in_app_pages_or_package():
    pattern = re.compile(r"^\s*(import|from)\s+(streamlit_folium|st_folium)\b", re.MULTILINE)
    sources = [ROOT / "app.py", *(ROOT / "pages").glob("*.py"), *(ROOT / "accesstwin").rglob("*.py")]
    offenders = [str(p.relative_to(ROOT)) for p in sources if pattern.search(p.read_text(encoding="utf-8"))]
    assert offenders == []


# ---- F2 / F1: dependency pins --------------------------------------------

def _requirement_lines(name: str) -> list[str]:
    return [ln.strip() for ln in (ROOT / name).read_text(encoding="utf-8").splitlines()
            if ln.strip() and not ln.strip().startswith("#")]


def test_requirements_pin_streamlit_below_1_56():
    specs = [ln for ln in _requirement_lines("requirements.txt") if re.match(r"streamlit\s*[<>=~!]", ln)]
    assert len(specs) == 1
    assert "<1.56" in specs[0]


def test_requirements_have_no_pytest_or_streamlit_folium():
    lines = [ln.lower() for ln in _requirement_lines("requirements.txt")]
    assert not any(ln.startswith("pytest") for ln in lines)
    assert not any(ln.startswith("streamlit-folium") for ln in lines)


def test_requirements_dev_includes_runtime_and_pytest():
    lines = _requirement_lines("requirements-dev.txt")
    assert "-r requirements.txt" in lines
    assert any(ln.lower().startswith("pytest") for ln in lines)


def test_installed_streamlit_is_below_1_56():
    major, minor = (int(x) for x in streamlit.__version__.split(".")[:2])
    assert (major, minor) < (1, 56), streamlit.__version__


# ---- F1.3: tracked-file guard -------------------------------------------

def test_check_tracked_allowlisted_paths_pass():
    paths = ["app.py", "requirements.txt", "pytest.ini", "README.md", "pages/1_🧭_Route_Planner.py",
             "accesstwin/ui/map_view.py", "tests/test_fixpack.py", "data/township.json"]
    assert check_tracked.problems(paths) == []


def test_check_tracked_flags_internal_and_runtime_files():
    flagged = ["docs/RUN_LOG.md", "reference/x.md", ".claude/agents/a.md", "AGENTS.md", "CLAUDE.md"]
    errs = check_tracked.problems(flagged)
    assert len(errs) == len(flagged)
    assert all(e.startswith("not in allowlist") for e in errs)


def test_check_tracked_flags_database_in_data():
    errs = check_tracked.problems(["data/accesstwin.db"])
    assert any("data/accesstwin.db" in e for e in errs)


def test_check_tracked_main_passes_on_real_repo():
    assert check_tracked.main() == 0


# ---- F2.3: run_page never lets an exception blank the page ------------

def test_run_page_shows_error_instead_of_raising():
    script = (
        "import streamlit as st\n"
        "from accesstwin.ui.components import run_page\n"
        "def boom():\n"
        "    raise ValueError('kaboom')\n"
        "run_page(boom)\n"
        "st.write('script completed')\n"
    )
    at = AppTest.from_string(script, default_timeout=60)
    at.run()
    assert at.error and at.error[0].value
    assert len(at.exception) >= 1
    assert any("kaboom" in e.value for e in at.exception)
    assert any("script completed" in m.value for m in at.markdown)


# ---- F3.6: Reset demo data restores the seed (X1: reset is scoped to this session; no global caches) ----

def test_reset_demo_data_restores_seeded_overlay():
    store.reset_demo()
    seeded = store.get_overlay()
    # X2 seed: approved SR2 obstructs E20 for wheelchair/stroller; approved SR5 ("other") flags E21 for inspection.
    assert [o["type"] for o in seeded["E20"]["obstacles"]] == ["blocked_ramp"]
    assert seeded["E21"]["needs_inspection"] is True
    pending = [r for r in store.list_reports("pending") if r["edge_id"] not in seeded]
    assert pending, "seed data should contain a pending report on a non-seeded edge"
    report = pending[0]
    store.set_report_status(report["id"], "approved")
    assert store.get_overlay() != seeded

    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60)
    at.run()
    assert not at.exception
    buttons = [b for b in at.sidebar.button if b.label == "Reset demo data"]
    assert buttons, "sidebar 'Reset demo data' button not found"
    buttons[0].click().run()

    assert not at.exception
    assert store.get_overlay() == seeded


# ---- F3.8: .streamlit/config.toml ----------------------------------------

def test_streamlit_config_has_lean_settings():
    import tomllib

    cfg = tomllib.loads((ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8"))
    assert cfg["server"]["runOnSave"] is False
    assert "headless" not in cfg.get("server", {})
    assert cfg["browser"]["gatherUsageStats"] is False
    assert cfg["client"]["toolbarMode"] == "minimal"
