"""Footfall analytics: modes, mock determinism, privacy (no files written), precomputed data, page."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from accesstwin import config
from accesstwin.core import footfall, store

ROOT = Path(__file__).resolve().parent.parent
PAGE = next((ROOT / "pages").glob("4_*Footfall*.py"))


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    store.init_db(seed=False)


@pytest.fixture
def no_cv(monkeypatch):
    monkeypatch.setattr(footfall, "cv_available", lambda: False)


def test_mock_deterministic(no_cv):
    a = footfall.count_video(b"clip-one")
    b = footfall.count_video(b"clip-one")
    c = footfall.count_video(b"clip-two-different")
    assert a.to_dict() == b.to_dict()
    assert a.mock and a.mode == "mock"
    assert (a.inbound, a.outbound, a.buckets) != (c.inbound, c.outbound, c.buckets)
    assert 3 <= len(a.buckets) <= 6


def test_buckets_sum(no_cv):
    for payload in (b"a", b"bb", b"ccc"):
        r = footfall.count_video(payload)
        assert sum(x["in"] for x in r.buckets) == r.inbound
        assert sum(x["out"] for x in r.buckets) == r.outbound
        assert r["total"] == r.inbound + r.outbound


def test_precomputed_file_valid():
    d = footfall.load_precomputed()
    assert d["synthetic"] is True and d["note"]
    c = d["sample_clip"]
    assert sum(b["in"] for b in c["buckets"]) == c["in"]
    assert sum(b["out"] for b in c["buckets"]) == c["out"]
    assert c["in"] + c["out"] == c["total"]


def test_camera_counts_cam02_low(db):
    cc = footfall.camera_counts()
    assert cc["CAM_02"] == min(cc.values()) and cc["CAM_02"] < 0.2 * cc["CAM_01"]


def test_camera_counts_only_real_runs_override(db):
    buckets = json.dumps([{"t_start_s": 0, "in": 1, "out": 1}] * 3)
    store.add_footfall_run("m", "CAM_02", 500, 500, buckets, None, 1)
    assert footfall.camera_counts()["CAM_02"] == 40
    store.add_footfall_run("r", "CAM_02", 10, 10, buckets, None, 0)
    assert footfall.camera_counts()["CAM_02"] == round(20 * 86400 / 30 * footfall.DAILY_SCALE)


def test_error_pct():
    assert footfall.error_pct(42, 45) == pytest.approx(100 * 3 / 45)
    assert footfall.error_pct(10, 0) is None


def test_detect_mode(monkeypatch):
    monkeypatch.setattr(footfall, "cv_available", lambda: False)
    assert footfall.detect_mode(True) == "precomputed"
    assert footfall.detect_mode(False) == "mock"
    monkeypatch.setattr(footfall, "cv_available", lambda: True)
    assert footfall.detect_mode(False) == "live"


def _snapshot(*dirs: Path) -> set[str]:
    return {str(p) for d in dirs for p in Path(d).rglob("*") if p.is_file()}


def test_no_frames_written(no_cv, tmp_path, monkeypatch):
    from PIL import Image

    def boom(*a, **k):
        raise AssertionError("image/frame write attempted")

    monkeypatch.setattr(Image.Image, "save", boom)
    try:
        import cv2

        monkeypatch.setattr(cv2, "imwrite", boom)
    except ImportError:
        pass
    monkeypatch.chdir(tmp_path)
    watched = [tmp_path, config.STATE_DIR]
    before = _snapshot(*watched)
    footfall.count_video(b"some video bytes")
    assert footfall.sample_result().total == 42
    assert _snapshot(*watched) == before


def test_page_default_and_run(db):
    at = AppTest.from_file(str(PAGE), default_timeout=60)
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    at.button(key="ff_run").click().run()
    assert not at.exception, [e.message for e in at.exception]
    runs = store.list_footfall_runs()
    assert len(runs) == 1 and runs[0]["cctv_id"] == "CAM_01" and runs[0]["mock"] == 1
