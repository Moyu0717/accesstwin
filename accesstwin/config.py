"""Central configuration: .env loading, mock switch, paths and scoring coefficients."""
from __future__ import annotations

import os
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
UPLOADS_DIR = DATA_DIR / "uploads"
TOWNSHIP_PATH = DATA_DIR / "township.json"
PERSONAS_PATH = DATA_DIR / "personas.json"
UPGRADES_PATH = DATA_DIR / "upgrades.json"
SAMPLE_REPORTS_PATH = DATA_DIR / "sample_reports.json"
DB_PATH = Path(os.getenv("ACCESSTWIN_DB", str(DATA_DIR / "accesstwin.db")))

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "").strip()


def mock_mode() -> bool:
    """Mock is on when ACCESSTWIN_MOCK=1 or when no Gemini key is configured."""
    flag = os.getenv("ACCESSTWIN_MOCK", "1").strip().lower() in {"1", "true", "yes"}
    return flag or not GEMINI_API_KEY


# Routing penalties (section 4.2 / 5.1)
PENALTY_UNCOVERED = 0.30  # prefers_covered personas
PENALTY_NO_TACTILE = 0.50  # needs_tactile personas
PENALTY_CRACKED = 0.20  # any persona on cracked surface

# Upgrade ROI (section 5.3)
BENEFIT_INDEX_COEF = 10.0
BENEFIT_PAIR_COEF = 3.0
BENEFIT_BENEFICIARY_DIVISOR = 100.0
COST_TIER_WEIGHTS = {"low": 1.0, "medium": 2.5, "high": 5.0}
