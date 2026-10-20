"""Photo licence, provenance, size and seed-report checks for data/photos (X5).

Every bundled photo that is shown to users must be openly licensed, credited in data/photos/credits.json,
small enough to ship (<= 300 KB, longest side <= 1280 px) and free of EXIF metadata. Seed reports must point
at credited photos, and the offline mock classifier must read each seed photo as the seed's obstacle type.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from PIL import Image

from accesstwin import config
from accesstwin.core.obstacles import analyze_photo, mock_analyze
from accesstwin.ui import components as ui

PHOTOS = config.PHOTOS_DIR
CREDITS_PATH = PHOTOS / "credits.json"
ALLOWED_LICENCES = {
    "CC0",
    "CC BY 2.0", "CC BY 3.0", "CC BY 4.0",
    "CC BY-SA 2.0", "CC BY-SA 3.0", "CC BY-SA 4.0",
}
MAX_BYTES = 300 * 1024
MAX_SIDE = 1280
OLD_NEWS_NAME = re.compile(r"_0[1-8]\.jpg$")
COMMONS_FILE_PREFIX = "https://commons.wikimedia.org/wiki/File:"


def _credits() -> dict:
    return json.loads(CREDITS_PATH.read_text(encoding="utf-8"))["photos"]


def _seed_reports() -> list[dict]:
    return json.loads(config.SAMPLE_REPORTS_PATH.read_text(encoding="utf-8"))


CREDITED = sorted(_credits())


# ---------- credits.json shape and licence ----------

def test_credits_file_has_note_and_photos_map():
    doc = json.loads(CREDITS_PATH.read_text(encoding="utf-8"))
    assert isinstance(doc.get("note"), str) and doc["note"].strip()
    assert isinstance(doc.get("photos"), dict) and doc["photos"]


@pytest.mark.parametrize("name", CREDITED)
def test_credited_photo_has_author_and_allowed_licence(name):
    entry = _credits()[name]
    assert isinstance(entry.get("author"), str) and entry["author"].strip(), name
    assert entry.get("licence") in ALLOWED_LICENCES, (name, entry.get("licence"))


@pytest.mark.parametrize("name", CREDITED)
def test_credited_photo_links_to_a_commons_file_page(name):
    entry = _credits()[name]
    assert entry.get("url", "").startswith(COMMONS_FILE_PREFIX), (name, entry.get("url"))
    assert entry.get("source") == "Wikimedia Commons", name


@pytest.mark.parametrize("name", CREDITED)
def test_credited_photo_records_what_was_changed(name):
    changes = _credits()[name].get("changes")
    assert isinstance(changes, str) and changes.strip(), name


# ---------- files on disk ----------

@pytest.mark.parametrize("name", CREDITED)
def test_credited_file_exists(name):
    assert (PHOTOS / name).is_file(), name


def test_every_bundled_jpg_is_credited():
    jpgs = sorted(p.name for p in PHOTOS.glob("*") if p.suffix.lower() in {".jpg", ".jpeg"})
    assert jpgs, "no bundled jpg photos"
    assert set(jpgs) == set(CREDITED)


@pytest.mark.parametrize("name", CREDITED)
def test_credited_file_is_small_enough(name):
    size = (PHOTOS / name).stat().st_size
    assert size <= MAX_BYTES, (name, size)


@pytest.mark.parametrize("name", CREDITED)
def test_credited_file_longest_side_is_at_most_1280px(name):
    with Image.open(PHOTOS / name) as img:
        assert max(img.size) <= MAX_SIDE, (name, img.size)


@pytest.mark.parametrize("name", CREDITED)
def test_credited_file_has_no_exif(name):
    with Image.open(PHOTOS / name) as img:
        exif = img.getexif()
    assert len(exif) == 0, (name, dict(exif))


def test_no_old_news_style_names_remain():
    leftovers = [p.name for p in PHOTOS.iterdir() if OLD_NEWS_NAME.search(p.name)]
    assert leftovers == [], leftovers


# ---------- caption wording ----------

@pytest.mark.parametrize("name", CREDITED)
def test_caption_names_author_and_licence(name):
    entry = _credits()[name]
    caption = ui.photo_caption(name)
    assert caption.startswith(entry["label"]), caption
    assert f"Photo: {entry['author']}, {entry['licence']}" in caption, caption
    assert "(Wikimedia Commons)" in caption


# ---------- seed reports ----------

def test_seed_reports_reference_credited_photos_on_disk():
    seeds = _seed_reports()
    assert seeds, "sample_reports.json is empty"
    credits = _credits()
    for rep in seeds:
        photo = rep.get("photo")
        assert photo, rep["id"]
        assert (PHOTOS / photo).is_file(), (rep["id"], photo)
        assert photo in credits, (rep["id"], photo)


# Seed obstacle type -> the mock families it may map to (SR1 is a kerb, so missing_ramp is an acceptable family too).
SEED_FAMILY = {
    "high_curb": {"high_curb", "missing_ramp"},
    "blocked_ramp": {"blocked_ramp"},
    "broken_surface": {"broken_surface"},
}


@pytest.mark.parametrize("rep_id", ["SR1", "SR2", "SR3"])
def test_mock_analysis_of_seed_photo_matches_seed_type(rep_id):
    rep = next(r for r in _seed_reports() if r["id"] == rep_id)
    family = SEED_FAMILY[rep["obstacle_type"]]
    path = PHOTOS / rep["photo"]
    result = analyze_photo(path.read_bytes(), rep["photo"])
    assert result["source"] == "mock"
    assert result["obstacle_type"] in family, (rep_id, rep["photo"], result["obstacle_type"])
    # The filename-level classifier agrees with the full pipeline.
    assert mock_analyze(rep["photo"])["obstacle_type"] in family


@pytest.mark.parametrize("name", ["ok_kerb_ramp_tactile_corner.jpg", "ok_tactile_paving_platform.jpg"])
def test_ok_photos_mock_to_none(name):
    assert (PHOTOS / name).is_file(), name
    assert analyze_photo((PHOTOS / name).read_bytes(), name)["obstacle_type"] == "none"
    assert mock_analyze(name)["obstacle_type"] == "none"
