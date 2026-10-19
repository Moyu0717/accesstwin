"""Planner Dashboard via Streamlit AppTest (spec section 7, M7)."""
from pathlib import Path

from streamlit.testing.v1 import AppTest

from accesstwin.core import store

ROOT = Path(__file__).resolve().parent.parent
DASHBOARD = str(next((ROOT / "pages").glob("6_*.py")))


def _metric(at, label):
    for m in at.metric:
        if m.label == label:
            return m
    raise AssertionError(f"metric {label!r} not found")


def _download_buttons(at):
    try:
        return list(at.get("download_button"))
    except Exception:
        return []


def test_dashboard_renders_with_suppressed_segment_and_exports():
    store.reset_demo()
    at = AppTest.from_file(DASHBOARD, default_timeout=90)
    at.run()
    assert not at.exception, [e.message for e in at.exception]

    assert int(_metric(at, "Suppressed-demand segments").value) >= 1

    assert len(_download_buttons(at)) >= 3


def test_design_mode_shows_pre_construction_info():
    store.reset_demo()
    at = AppTest.from_file(DASHBOARD, default_timeout=90)
    at.run()
    assert not at.exception, [e.message for e in at.exception]

    at.radio(key="dash_mode").set_value("design").run()
    assert not at.exception, [e.message for e in at.exception]
    assert any("Pre-construction review" in i.value for i in at.info)
