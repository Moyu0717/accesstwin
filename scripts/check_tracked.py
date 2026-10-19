"""Fail if git tracks anything outside the public allowlist, or if a tracked file looks like it holds an API key.

Run before every commit/push and in CI:  python scripts/check_tracked.py
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

ALLOWED_FILES = {
    "app.py",
    ".streamlit/config.toml",
    ".streamlit/secrets.toml.example",
    "requirements.txt",
    "requirements-cv.txt",
    "requirements-dev.txt",
    ".env.example",
    ".gitignore",
    ".gitattributes",
    "README.md",
    "pytest.ini",
    ".github/workflows/tests.yml",
    ".github/workflows/pages.yml",
    "scripts/precompute_footfall.py",
    "scripts/check_tracked.py",
    "scripts/build_stlite_site.py",
}
ALLOWED_DIRS = ("pages/", "accesstwin/", "data/", "tests/")
FORBIDDEN_IN_DATA = (".db", ".mp4", ".mov", ".avi", ".pt")
MAX_BYTES = 2_000_000  # small demo assets only

SECRET = re.compile(
    r"gsk_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9_-]{20,}|GROQ_API_KEY *= *\"?[A-Za-z0-9_-]{8,}|api_key *= *\"[A-Za-z0-9_-]{8,}"
)
PLACEHOLDER = "paste-your-key-here"


def tracked_files() -> list[str]:
    out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True).stdout
    return [p for p in out.decode("utf-8").split("\0") if p]


def problems(paths: list[str]) -> list[str]:
    errs = []
    for p in paths:
        if p not in ALLOWED_FILES and not p.startswith(ALLOWED_DIRS):
            errs.append(f"not in allowlist: {p}")
            continue
        if p.startswith("data/") and p.lower().endswith(FORBIDDEN_IN_DATA):
            errs.append(f"runtime/large file type in data/: {p}")
        f = ROOT / p
        if not f.is_file():
            continue
        if f.stat().st_size > MAX_BYTES:
            errs.append(f"file larger than {MAX_BYTES // 1_000_000} MB: {p}")
        if p == "scripts/check_tracked.py":
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue  # binary asset
        for line in text.splitlines():
            if SECRET.search(line) and PLACEHOLDER not in line:
                errs.append(f"possible secret in {p}")
                break
    return errs


def main() -> int:
    paths = tracked_files()
    errs = problems(paths)
    for e in errs:
        print("FAIL:", e)
    if errs:
        return 1
    print(f"check_tracked: OK ({len(paths)} tracked files, all allowlisted, no secrets)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
