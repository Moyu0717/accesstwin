"""Smoke-test every Streamlit page headlessly with AppTest (no browser needed)."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parent.parent
PAGES = [ROOT / "app.py", *sorted((ROOT / "pages").glob("*.py"))]


@pytest.mark.parametrize("page", PAGES, ids=lambda p: p.name.encode("ascii", "ignore").decode())
def test_page_renders_without_exception(page):
    at = AppTest.from_file(str(page), default_timeout=60)
    at.run()
    assert not at.exception, [e.message for e in at.exception]
