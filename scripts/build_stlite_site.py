"""Build the browser-only mirror (stlite on GitHub Pages) into _site/.

The whole Streamlit app runs in the visitor's browser (Pyodide/WebAssembly) in Mock mode — no server, no
quota, no sleeping, and no API key ever shipped. Only runtime files are copied; _site/ is git-ignored and is
built by .github/workflows/pages.yml on every push to main.

    .venv\\Scripts\\python.exe scripts\\build_stlite_site.py
    .venv\\Scripts\\python.exe -m http.server 8765 --directory _site
"""
from __future__ import annotations

import json
import shutil
import sys
import tomllib
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "_site"

# Pinned: released 2026-09-23 (>= 2 weeks old when chosen), bundles Streamlit 1.62.0 on Python 3.13 (Pyodide).
STLITE_VERSION = "1.9.2"
# Pyodide-available subset of requirements.txt (no groq / python-dotenv / CV — the browser is always Mock).
REQUIREMENTS = ["networkx", "pandas", "plotly", "folium", "pillow", "sqlite3"]  # sqlite3 is a loadable Pyodide module

RUNTIME_FILES = ["app.py"]  # .streamlit/config.toml is passed as streamlitConfig: Pages artifacts drop dot-folders
RUNTIME_DIRS = ["pages", "accesstwin", "data"]
DATA_SKIP = {"uploads", "accesstwin.db"}
SKIP_SUFFIXES = {".pyc", ".db", ".mp4", ".mov", ".avi", ".pt"}

FAVICON = ("data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'>"
           "<text y='.9em' font-size='90'>♿</text></svg>")

INDEX = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no" />
  <title>AccessTwin</title>
  <link rel="icon" href="__FAVICON__" />
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@stlite/browser@__VERSION__/build/stlite.css" />
  <style>
    #at-loading {font-family: system-ui, sans-serif; color: #1F2937; max-width: 560px; margin: 18vh auto; padding: 0 16px; text-align: center;}
    #at-loading h1 {color: #0F766E; margin-bottom: 6px;}
    #at-loading p {color: #4B5563;}
  </style>
</head>
<body>
  <div id="at-loading">
    <h1>♿ AccessTwin</h1>
    <p><b>Loading AccessTwin in your browser… first load about 30 s (up to a minute on slow networks).</b></p>
    <p>Python is starting inside this page (no server). Demo mode: the photo AI uses the demo classifier and
       footfall shows the bundled sample results. Later visits are faster.</p>
  </div>
  <noscript>AccessTwin runs Python in your browser and needs JavaScript enabled.</noscript>
  <div id="root"></div>
  <script type="module">
    import { mount } from "https://cdn.jsdelivr.net/npm/@stlite/browser@__VERSION__/build/stlite.js";
    const files = __FILES__;
    mount(
      {
        requirements: __REQUIREMENTS__,
        entrypoint: "app.py",
        files: files,
        streamlitConfig: __CONFIG__,
      },
      document.getElementById("root"),
    );
    // Hide the loading note once Streamlit has painted its first element.
    const hide = () => { const el = document.getElementById("at-loading"); if (el) el.remove(); };
    const obs = new MutationObserver(() => {
      if (document.querySelector("[data-testid='stApp'], [data-testid='stMain']")) { hide(); obs.disconnect(); }
    });
    obs.observe(document.body, { childList: true, subtree: true });
  </script>
</body>
</html>
"""


def streamlit_config() -> dict:
    """Flatten .streamlit/config.toml into stlite's dotted streamlitConfig form (theme + client settings)."""
    with open(ROOT / ".streamlit" / "config.toml", "rb") as f:
        raw = tomllib.load(f)
    flat = {f"{section}.{key}": value for section, opts in raw.items() for key, value in opts.items()}
    flat.pop("server.runOnSave", None)  # no server in the browser
    flat["client.toolbarMode"] = "viewer"
    return flat


def _ignore(directory: str, names: list[str]) -> set[str]:
    skip = {n for n in names if n == "__pycache__" or Path(n).suffix in SKIP_SUFFIXES or n.startswith(".")}
    if Path(directory).resolve() == (ROOT / "data").resolve():
        skip |= {n for n in names if n in DATA_SKIP}
    return skip


def build(out: Path = OUT) -> list[str]:
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for rel in RUNTIME_FILES:
        dst = out / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, dst)
    for rel in RUNTIME_DIRS:
        shutil.copytree(ROOT / rel, out / rel, ignore=_ignore)
    paths = sorted(p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file())
    files = {p: {"url": "./" + quote(p)} for p in paths}  # emoji page names are URL-encoded
    html = (INDEX.replace("__VERSION__", STLITE_VERSION).replace("__FAVICON__", FAVICON)
            .replace("__FILES__", json.dumps(files, ensure_ascii=False, indent=2))
            .replace("__REQUIREMENTS__", json.dumps(REQUIREMENTS))
            .replace("__CONFIG__", json.dumps(streamlit_config())))
    (out / "index.html").write_text(html, encoding="utf-8", newline="\n")
    return paths


def main() -> int:
    paths = build()
    size = sum((OUT / p).stat().st_size for p in paths)
    print(f"Built {OUT} — {len(paths)} app files ({size / 1024:.0f} KB) + index.html, stlite {STLITE_VERSION}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
