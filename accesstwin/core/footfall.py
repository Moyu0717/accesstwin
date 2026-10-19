"""Anonymous CCTV footfall counting (spec 5.4 + addendum C.1).

Modes (chosen automatically):
- live:        local only; cv2 + ultralytics + supervision import AND not force_mock().
- precomputed: bundled sample clip results from data/footfall_precomputed.json (cloud default).
- mock:        any uploaded video when live CV is unavailable; deterministic from sha256 of the bytes.

Privacy: frames and crops are never written to disk and only aggregate counts are returned.
The sole exception: an uploaded video may be written to a NamedTemporaryFile (live mode only, because
OpenCV needs a path) and is always deleted in a finally block.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from accesstwin import config

OCCLUSION_NOTE = "Occlusion and dense crowds cause under-counting; treat counts as a lower bound."
BUCKET_S = 10
# A clip is mapped to a daily figure as (in + out) * (86400 / duration_s) * DAILY_SCALE.
# The 0.1 factor reflects that a short clip is not representative of a whole day of traffic.
DAILY_SCALE = 0.1


@dataclass
class FootfallResult:
    name: str = ""
    inbound: int = 0
    outbound: int = 0
    frames_processed: int = 0
    fps_effective: float = 0.0
    occlusion_note: str = OCCLUSION_NOTE
    buckets: list = field(default_factory=list)
    mode: str = "mock"
    mock: bool = True
    duration_s: float = 0.0

    @property
    def total(self) -> int:
        return self.inbound + self.outbound

    def to_dict(self) -> dict:
        return {
            "name": self.name, "in": self.inbound, "out": self.outbound, "total": self.total,
            "frames_processed": self.frames_processed, "fps_effective": self.fps_effective,
            "occlusion_note": self.occlusion_note, "buckets": self.buckets,
            "mode": self.mode, "mock": self.mock, "duration_s": self.duration_s,
        }

    def __getitem__(self, key: str):
        return self.to_dict()[key]


def cv_available() -> bool:
    """True when live CV can run: cv2 + ultralytics + supervision import and Mock is not forced."""
    if config.force_mock():
        return False
    try:
        import cv2  # noqa: F401
        import supervision  # noqa: F401
        import ultralytics  # noqa: F401
    except Exception:
        return False
    return True


def detect_mode(is_sample: bool) -> str:
    if cv_available():
        return "live"
    return "precomputed" if is_sample else "mock"


# ---- precomputed ------------------------------------------------------------

def load_precomputed() -> dict:
    with open(config.FOOTFALL_PRECOMPUTED_PATH, encoding="utf-8") as f:
        return json.load(f)


def sample_result() -> FootfallResult:
    clip = load_precomputed()["sample_clip"]
    return FootfallResult(
        name=clip["name"], inbound=int(clip["in"]), outbound=int(clip["out"]),
        frames_processed=int(clip["frames_processed"]), fps_effective=float(clip["fps_effective"]),
        buckets=[dict(b) for b in clip["buckets"]], mode="precomputed", mock=True,
        duration_s=float(clip.get("duration_s", 30)),
    )


def camera_counts() -> dict[str, int]:
    """cctv_id -> daily pedestrian count. Precomputed/synthetic base, overridden only by real-CV runs
    (mock == 0): total_in + total_out of the latest run per camera, scaled to a day by
    86400 / clip_duration_s * DAILY_SCALE (duration = number of 10-s buckets * 10)."""
    counts = {k: int(v) for k, v in load_precomputed().get("camera_daily_counts", {}).items()}
    try:
        from accesstwin.core import store

        runs = store.list_footfall_runs()
    except Exception:
        return counts
    latest: dict[str, dict] = {}
    for r in runs:
        if not r.get("mock") and r.get("cctv_id"):
            latest[r["cctv_id"]] = r  # ordered by id, so the last wins
    for cam, r in latest.items():
        try:
            n_buckets = max(1, len(json.loads(r.get("buckets_json") or "[]")))
        except ValueError:
            n_buckets = 3
        duration = n_buckets * BUCKET_S
        counts[cam] = int(round(((r["total_in"] or 0) + (r["total_out"] or 0)) * 86400 / duration * DAILY_SCALE))
    return counts


def error_pct(auto_total: int, manual_count: int) -> float | None:
    if not manual_count:
        return None
    return abs(auto_total - manual_count) / manual_count * 100.0


# ---- mock -------------------------------------------------------------------

def _as_bytes(src) -> bytes:
    if isinstance(src, (bytes, bytearray)):
        return bytes(src)
    return Path(src).read_bytes()


def _mock_count(data: bytes, name: str) -> FootfallResult:
    seed = int.from_bytes(hashlib.sha256(data).digest()[:8], "big")
    rng = random.Random(seed)
    n_buckets = rng.randint(3, 6)
    buckets = [{"t_start_s": i * BUCKET_S, "in": rng.randint(2, 11), "out": rng.randint(1, 9)}
               for i in range(n_buckets)]
    duration = n_buckets * BUCKET_S
    fps = round(rng.uniform(8.0, 12.0), 1)
    return FootfallResult(
        name=name, inbound=sum(b["in"] for b in buckets), outbound=sum(b["out"] for b in buckets),
        frames_processed=int(duration * fps), fps_effective=fps, buckets=buckets,
        mode="mock", mock=True, duration_s=float(duration),
    )


# ---- live -------------------------------------------------------------------

def _live_count(src, line_y_frac: float, sample_every: int, name: str) -> FootfallResult:
    import time

    import cv2
    import numpy as np
    import supervision as sv
    from ultralytics import YOLO

    tmp_path = None
    path = None
    try:
        if isinstance(src, (bytes, bytearray)):
            # OpenCV needs a path for video decoding; the temp file is removed in `finally`.
            tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
            try:
                tmp.write(bytes(src))
            finally:
                tmp.close()
            tmp_path = tmp.name
            path = tmp_path
        else:
            path = str(src)

        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            raise ValueError("Could not open video")
        try:
            src_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            y = int(height * line_y_frac)
            line = sv.LineZone(start=sv.Point(0, y), end=sv.Point(width, y))
            tracker = sv.ByteTrack(frame_rate=max(1, int(src_fps / sample_every)))
            model = YOLO("yolov8n.pt")  # CPU; weights fetched locally, never committed
            per_bucket: dict[int, list[int]] = {}
            prev_in = prev_out = 0
            idx = processed = 0
            t0 = time.perf_counter()
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                idx += 1
                if (idx - 1) % sample_every:
                    continue
                res = model(frame, classes=[0], device="cpu", verbose=False)[0]
                dets = sv.Detections.from_ultralytics(res)
                dets = tracker.update_with_detections(dets)
                line.trigger(dets)
                processed += 1
                b = int(((idx - 1) / src_fps) // BUCKET_S)
                row = per_bucket.setdefault(b, [0, 0])
                row[0] += int(line.in_count) - prev_in
                row[1] += int(line.out_count) - prev_out
                prev_in, prev_out = int(line.in_count), int(line.out_count)
                del frame, res, dets  # in-memory only
            elapsed = max(time.perf_counter() - t0, 1e-6)
            duration = idx / src_fps
        finally:
            cap.release()
        n = max(per_bucket) + 1 if per_bucket else 0
        buckets = [{"t_start_s": i * BUCKET_S, "in": per_bucket.get(i, [0, 0])[0],
                    "out": per_bucket.get(i, [0, 0])[1]} for i in range(n)]
        _ = np  # numpy is a transitive requirement of the stack
        return FootfallResult(
            name=name, inbound=int(line.in_count), outbound=int(line.out_count),
            frames_processed=processed, fps_effective=round(processed / elapsed, 2), buckets=buckets,
            mode="live", mock=False, duration_s=round(duration, 1),
        )
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


def count_video(video_bytes_or_path, line_y_frac: float = 0.5, sample_every: int = 3,
                name: str = "uploaded video") -> FootfallResult:
    """Count people crossing a horizontal line. Live when CV is available, else deterministic mock."""
    if cv_available():
        return _live_count(video_bytes_or_path, line_y_frac, max(1, int(sample_every)), name)
    return _mock_count(_as_bytes(video_bytes_or_path), name)
