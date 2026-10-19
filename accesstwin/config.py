"""Central configuration: .env loading, mock switch, paths and scoring coefficients."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # python-dotenv is optional at runtime
    load_dotenv = None

ROOT = Path(__file__).resolve().parent.parent
if load_dotenv is not None:
    load_dotenv(ROOT / ".env")

DATA_DIR = ROOT / "data"
PHOTOS_DIR = DATA_DIR / "photos"
VIDEOS_DIR = DATA_DIR / "videos"
TOWNSHIP_PATH = DATA_DIR / "township.json"
PERSONAS_PATH = DATA_DIR / "personas.json"
UPGRADES_PATH = DATA_DIR / "upgrades.json"
SAMPLE_REPORTS_PATH = DATA_DIR / "sample_reports.json"
FOOTFALL_PRECOMPUTED_PATH = DATA_DIR / "footfall_precomputed.json"


def get_secret(name: str, default: str | None = None) -> str | None:
    """st.secrets (Streamlit Cloud) → environment / .env → default. Never raises."""
    try:
        import streamlit as st

        if name in st.secrets:
            return str(st.secrets[name]).strip()
    except Exception:  # no secrets.toml, or not running under Streamlit
        pass
    value = os.environ.get(name)
    return value.strip() if value is not None else default


def _writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def state_dir() -> Path:
    """Where runtime state (SQLite DB, uploads) lives.

    ACCESSTWIN_STATE_DIR wins; otherwise the repo's data/ folder when writable (local runs), else
    <tempdir>/accesstwin (read-only or shared cloud checkouts). Runtime state is disposable demo data.
    """
    explicit = get_secret("ACCESSTWIN_STATE_DIR")
    if explicit:
        return Path(explicit)
    if _writable(DATA_DIR):
        return DATA_DIR
    return Path(tempfile.gettempdir()) / "accesstwin"


STATE_DIR = state_dir()


def resolve_path(p: str | Path) -> Path:
    """Stored paths are repo-relative POSIX strings, or absolute for uploads in the state dir."""
    p = Path(p)
    return p if p.is_absolute() else ROOT / p

UPLOADS_DIR = STATE_DIR / "uploads"
DB_PATH = Path(get_secret("ACCESSTWIN_DB") or str(STATE_DIR / "accesstwin.db"))

# Vision AI (addendum B). Model ids are checked against Groq's docs, never guessed — see DECISIONS.md.
DEFAULT_GROQ_VISION_MODEL = "qwen/qwen3.8-27b"


def groq_api_key() -> str:
    return get_secret("GROQ_API_KEY", "") or ""


def groq_vision_model() -> str:
    return get_secret("GROQ_VISION_MODEL", "") or DEFAULT_GROQ_VISION_MODEL


def force_mock() -> bool:
    """ACCESSTWIN_MOCK=1 forces Mock for everything; unset/0 uses real providers where keys exist."""
    return (get_secret("ACCESSTWIN_MOCK", "") or "").lower() in {"1", "true", "yes"}


def vision_provider() -> str:
    """'groq' | 'mock'. VISION_PROVIDER may force one; default is groq when a key exists."""
    if force_mock():
        return "mock"
    wanted = (get_secret("VISION_PROVIDER", "") or "").lower()
    if wanted == "mock":
        return "mock"
    return "groq" if groq_api_key() else "mock"


def mock_mode() -> bool:
    """True when the photo AI runs on the demo classifier (no key, or Mock forced)."""
    return vision_provider() == "mock"


# Routing penalties (section 4.2 / 5.1)
PENALTY_UNCOVERED = 0.30  # prefers_covered personas
PENALTY_NO_TACTILE = 0.50  # needs_tactile personas
PENALTY_CRACKED = 0.20  # any persona on cracked surface

# Upgrade ROI (section 5.3)
BENEFIT_INDEX_COEF = 10.0
BENEFIT_PAIR_COEF = 3.0
BENEFIT_BENEFICIARY_DIVISOR = 100.0
COST_TIER_WEIGHTS = {"low": 1.0, "medium": 2.5, "high": 5.0}
