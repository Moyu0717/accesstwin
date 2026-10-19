"""SQLite persistence (spec section 5.7): reports, verifications, footfall_runs, work_orders.

The base township JSON is never modified. Edge state changes live here and are applied
as an overlay when the graph is loaded:
- approving an obstacle report  -> edge becomes `blocked`
- verifying an edge as passable -> edge becomes `verified_accessible`
The most recent event per edge wins.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator

from accesstwin import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    edge_id TEXT NOT NULL,
    reporter_role TEXT NOT NULL,
    photo_path TEXT,
    ai_json TEXT,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','approved','rejected')),
    created_at TEXT NOT NULL,
    decided_at TEXT
);
CREATE TABLE IF NOT EXISTS verifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    edge_id TEXT NOT NULL,
    verifier_role TEXT NOT NULL,
    result TEXT NOT NULL CHECK (result IN ('passable','not_passable')),
    note TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS footfall_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_name TEXT,
    cctv_id TEXT,
    total_in INTEGER,
    total_out INTEGER,
    buckets_json TEXT,
    manual_count INTEGER,
    mock INTEGER,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS work_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    upgrade_id TEXT,
    report_id INTEGER,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','in_progress','done')),
    created_at TEXT NOT NULL
);
"""

REPORT_STATUSES = ("pending", "approved", "rejected")
WORK_ORDER_STATUSES = ("open", "in_progress", "done")


def _now() -> str:
    return datetime.now().isoformat(timespec="microseconds")


def db_path() -> Path:
    return Path(config.DB_PATH)


@contextmanager
def connect(path: Path | str | None = None) -> Iterator[sqlite3.Connection]:
    p = Path(path) if path else db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(p)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(seed: bool = True) -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)
        empty = conn.execute("SELECT COUNT(*) FROM reports").fetchone()[0] == 0
    if seed and empty:
        seed_sample_reports()


def seed_sample_reports(path: Path | str | None = None) -> int:
    p = Path(path or config.SAMPLE_REPORTS_PATH)
    if not p.exists():
        return 0
    with open(p, encoding="utf-8") as f:
        seeds = json.load(f)
    for s in seeds:
        ai = {
            "obstacle_type": s.get("obstacle_type", "other"),
            "severity": s.get("severity", "medium"),
            "affected_personas": s.get("affected_personas", []),
            "confidence": s.get("confidence", 0.7),
            "visible_evidence": s.get("note", ""),
            "needs_onsite_measurement": s.get("needs_onsite_measurement", []),
            "source": "seed",
        }
        photo = str(Path("data") / "photos" / s["photo"]) if s.get("photo") else None
        rid = add_report(s["edge_id"], s["reporter_role"], photo, ai)
        if s.get("status") in ("approved", "rejected"):
            set_report_status(rid, s["status"])
    return len(seeds)


def reset_demo() -> None:
    """Wipe all runtime data and re-seed the sample reports ("Reset demo data" button)."""
    with connect() as conn:
        conn.executescript(SCHEMA)
        for table in ("reports", "verifications", "footfall_runs", "work_orders"):
            conn.execute(f"DELETE FROM {table}")
        conn.execute("DELETE FROM sqlite_sequence")
    seed_sample_reports()


# ---- reports ---------------------------------------------------------------

def add_report(edge_id: str, reporter_role: str, photo_path: str | None, ai: dict | None,
               status: str = "pending") -> int:
    if status not in REPORT_STATUSES:
        raise ValueError(f"bad status {status}")
    with connect() as conn:
        conn.executescript(SCHEMA)
        cur = conn.execute(
            "INSERT INTO reports (edge_id, reporter_role, photo_path, ai_json, status, created_at) "
            "VALUES (?,?,?,?,?,?)",
            (edge_id, reporter_role, photo_path, json.dumps(ai or {}), status, _now()),
        )
        return int(cur.lastrowid)


def set_report_status(report_id: int, status: str) -> None:
    if status not in REPORT_STATUSES:
        raise ValueError(f"bad status {status}")
    with connect() as conn:
        conn.execute("UPDATE reports SET status=?, decided_at=? WHERE id=?", (status, _now(), report_id))


def list_reports(status: str | None = None) -> list[dict]:
    with connect() as conn:
        conn.executescript(SCHEMA)
        if status:
            rows = conn.execute("SELECT * FROM reports WHERE status=? ORDER BY id", (status,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM reports ORDER BY id").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["ai"] = json.loads(d.get("ai_json") or "{}")
        out.append(d)
    return out


# ---- verifications ---------------------------------------------------------

def add_verification(edge_id: str, verifier_role: str, result: str, note: str = "") -> int:
    if result not in ("passable", "not_passable"):
        raise ValueError(f"bad result {result}")
    with connect() as conn:
        conn.executescript(SCHEMA)
        cur = conn.execute(
            "INSERT INTO verifications (edge_id, verifier_role, result, note, created_at) VALUES (?,?,?,?,?)",
            (edge_id, verifier_role, result, note, _now()),
        )
        return int(cur.lastrowid)


def list_verifications() -> list[dict]:
    with connect() as conn:
        conn.executescript(SCHEMA)
        return [dict(r) for r in conn.execute("SELECT * FROM verifications ORDER BY id").fetchall()]


# ---- overlay ---------------------------------------------------------------

def get_overlay() -> dict[str, dict]:
    """edge_id -> {"status": ...} from approved reports and verifications (latest event wins)."""
    events: list[tuple[str, str, str]] = []
    with connect() as conn:
        conn.executescript(SCHEMA)
        for r in conn.execute("SELECT edge_id, decided_at FROM reports WHERE status='approved'"):
            events.append((r["decided_at"] or "", r["edge_id"], "blocked"))
        for r in conn.execute("SELECT edge_id, result, created_at FROM verifications"):
            status = "verified_accessible" if r["result"] == "passable" else "blocked"
            events.append((r["created_at"], r["edge_id"], status))
    overlay: dict[str, dict] = {}
    for _ts, edge_id, status in sorted(events):
        overlay[edge_id] = {"status": status}
    return overlay


# ---- work orders -----------------------------------------------------------

def add_work_order(upgrade_id: str | None = None, report_id: int | None = None) -> int:
    with connect() as conn:
        conn.executescript(SCHEMA)
        cur = conn.execute(
            "INSERT INTO work_orders (upgrade_id, report_id, status, created_at) VALUES (?,?,?,?)",
            (upgrade_id, report_id, "open", _now()),
        )
        return int(cur.lastrowid)


def set_work_order_status(order_id: int, status: str) -> None:
    if status not in WORK_ORDER_STATUSES:
        raise ValueError(f"bad status {status}")
    with connect() as conn:
        conn.execute("UPDATE work_orders SET status=? WHERE id=?", (status, order_id))


def list_work_orders() -> list[dict]:
    with connect() as conn:
        conn.executescript(SCHEMA)
        return [dict(r) for r in conn.execute("SELECT * FROM work_orders ORDER BY id").fetchall()]
