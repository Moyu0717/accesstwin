"""Browser-only mirror (stlite on GitHub Pages): browser guard, site build, allowlist and Pages workflow.

No test starts a browser, a server or the network. The build is run into tmp_path only.
"""
from __future__ import annotations

import builtins
import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

from accesstwin import config
from accesstwin.core import footfall
from accesstwin.core.obstacles import analyze_photo

ROOT = Path(__file__).resolve().parent.parent
BUILD_SCRIPT = ROOT / "scripts" / "build_stlite_site.py"
CHECK_SCRIPT = ROOT / "scripts" / "check_tracked.py"
PAGES_YML = ROOT / ".github" / "workflows" / "pages.yml"
SAMPLE_PHOTO = ROOT / "data" / "photos" / "kerb_high_granite_step.jpg"
GSK_KEY = re.compile(r"gsk_[A-Za-z0-9]{20,}")


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


build_mod = _load("build_stlite_site", BUILD_SCRIPT)
check_mod = _load("check_tracked", CHECK_SCRIPT)


@pytest.fixture
def browser(monkeypatch):
    """Pretend to be Pyodide/stlite, with a live-looking Groq key present to prove it is ignored."""
    monkeypatch.setattr(config.sys, "platform", "emscripten")
    monkeypatch.delenv("ACCESSTWIN_MOCK", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "test-not-a-real-key")
    monkeypatch.delenv("VISION_PROVIDER", raising=False)
    return monkeypatch


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    out = tmp_path_factory.mktemp("stlite") / "site"
    paths = build_mod.build(out)
    return out, paths


def _html(out: Path) -> str:
    return (out / "index.html").read_text(encoding="utf-8")


def _files_map(html: str) -> dict:
    start = html.index("const files = ") + len("const files = ")
    obj, _end = json.JSONDecoder().raw_decode(html[start:])
    return obj


# ---- browser guard ----------------------------------------------------------

def test_in_browser_true_under_emscripten(browser):
    assert config.in_browser() is True


def test_force_mock_true_in_browser_even_with_key(browser):
    assert config.force_mock() is True


def test_vision_provider_mock_in_browser(browser):
    assert config.vision_provider() == "mock"
    assert config.mock_mode() is True


def test_state_dir_is_tmp_in_browser(browser):
    assert config.state_dir() == Path("/tmp/accesstwin")


def test_cv_unavailable_in_browser(browser):
    assert footfall.cv_available() is False


def test_analyze_photo_mock_in_browser_never_imports_groq(browser):
    browser.delitem(sys.modules, "groq", raising=False)
    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "groq" or name.startswith("groq."):
            raise AssertionError("groq must not be imported in the browser mirror")
        return real_import(name, *args, **kwargs)

    browser.setattr(builtins, "__import__", guarded_import)
    result = analyze_photo(SAMPLE_PHOTO.read_bytes(), SAMPLE_PHOTO.name, "image/png")
    assert result["source"] == "mock"
    assert "notice" not in result
    assert "groq" not in sys.modules


def test_guard_is_back_off_on_real_platform(monkeypatch):
    monkeypatch.setattr(config.sys, "platform", "win32")
    assert config.in_browser() is False


def test_real_platform_with_key_selects_groq(monkeypatch):
    """Control: without the browser guard the same environment does select the Groq path."""
    monkeypatch.setattr(config.sys, "platform", "win32")
    monkeypatch.delenv("ACCESSTWIN_MOCK", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "test-not-a-real-key")
    monkeypatch.delenv("VISION_PROVIDER", raising=False)
    assert config.force_mock() is False
    assert config.vision_provider() == "groq"


# ---- build_stlite_site.build() ----------------------------------------------

def test_index_html_exists_and_pins_stlite(site):
    out, _ = site
    html = _html(out)
    v = build_mod.STLITE_VERSION
    assert (out / "index.html").is_file()
    assert f"@stlite/browser@{v}/build/stlite.js" in html
    assert f"@stlite/browser@{v}/build/stlite.css" in html
    assert "@stlite/browser@latest" not in html


def test_index_html_shell_markup(site):
    out, _ = site
    html = _html(out)
    assert "Loading AccessTwin in your browser" in html
    assert "<noscript>" in html
    assert "<title>AccessTwin</title>" in html
    assert 'entrypoint: "app.py"' in html or '"app.py"' in html


def test_files_map_contains_runtime_files(site):
    out, _ = site
    files = _files_map(_html(out))
    assert "app.py" in files
    for page in (ROOT / "pages").glob("*.py"):
        assert f"pages/{page.name}" in files, page.name
    assert "accesstwin/core/store.py" in files
    assert "data/township.json" in files


def test_files_map_urls_relative_and_encoded(site):
    out, _ = site
    files = _files_map(_html(out))
    for key, entry in files.items():
        url = entry["url"]
        assert url.startswith("./"), key
        assert not url.startswith("./."), key
        assert all(ord(ch) < 128 for ch in url), f"raw non-ASCII in url: {url}"
    page_urls = [e["url"] for k, e in files.items() if k.startswith("pages/")]
    assert page_urls
    # Emoji page names are percent-encoded; plain-ASCII V2 pages (8_Compare, 9_Deliver) stay readable.
    assert any("%F0%9F" in u for u in page_urls)  # emoji page names (e.g. the route planner icon)
    ascii_pages = [u for u in page_urls if u.endswith(("8_Compare.py", "9_Deliver.py"))]
    assert len(ascii_pages) == 2, page_urls
    assert all("%" not in u for u in ascii_pages), ascii_pages


def test_every_mapped_file_exists_in_output(site):
    out, _ = site
    for key in _files_map(_html(out)):
        assert (out / key).is_file(), key


def test_no_dot_folders_in_output(site):
    out, paths = site
    for p in paths:
        assert not any(part.startswith(".") for part in p.split("/")), p


def test_excluded_material_absent_from_output(site):
    out, paths = site
    names = {Path(p).name for p in paths}
    parts = [set(p.split("/")) for p in paths]
    assert not any(n.endswith(".db") for n in names)
    assert not any("uploads" in s for s in parts)
    assert ".env" not in names and not any(n.startswith(".env") for n in names)
    assert "CODEX_HANDOFF.md" not in names
    assert not any(p.startswith(("docs/", "reference/")) for p in paths)
    assert not any(s & {"docs", "reference"} for s in parts)


def test_requirements_pyodide_subset():
    reqs = set(build_mod.REQUIREMENTS)
    assert {"sqlite3", "folium"} <= reqs
    for banned in ("groq", "python-dotenv", "opencv", "opencv-python", "ultralytics"):
        assert banned not in reqs


def test_streamlit_config_flattened_without_server_run_on_save():
    cfg = build_mod.streamlit_config()
    assert "theme.primaryColor" in cfg
    assert "server.runOnSave" not in cfg
    assert cfg["client.toolbarMode"] == "viewer"


def test_no_groq_key_pattern_in_output(site):
    out, paths = site
    for p in paths + ["index.html"]:
        text = (out / p).read_bytes().decode("utf-8", errors="ignore")
        assert not GSK_KEY.search(text), p


# ---- check_tracked ----------------------------------------------------------

def test_check_tracked_accepts_pages_files():
    assert check_mod.problems([".github/workflows/pages.yml", "scripts/build_stlite_site.py"]) == []


def test_check_tracked_rejects_site_output():
    errs = check_mod.problems(["_site/index.html"])
    assert errs and any("allowlist" in e for e in errs)


# ---- pages.yml --------------------------------------------------------------

def test_pages_workflow_text():
    text = PAGES_YML.read_text(encoding="utf-8")
    assert re.search(r"on:\s*\n\s*push:\s*\n\s*branches:\s*\[main\]", text)
    assert re.search(r"permissions:[\s\S]*pages:\s*write", text)
    assert re.search(r"permissions:[\s\S]*id-token:\s*write", text)
    assert "python scripts/build_stlite_site.py" in text
    assert "actions/upload-pages-artifact" in text
    assert "actions/deploy-pages" in text
    assert re.search(r"path:\s*_site", text)
