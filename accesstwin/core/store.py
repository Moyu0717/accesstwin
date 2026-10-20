"""SQLite persistence (spec section 5.7): reports, verifications, footfall_runs, work_orders.

The base township JSON is never modified. Edge state changes live here and are applied
as an overlay when the graph is loaded:
- approving an obstacle report confirms a *specific* obstacle (fix pack X2): a physical fact (e.g. the
  recorded step, a broken surface) or a persona-specific obstruction (e.g. parked cars on a kerb ramp).
  It never closes the segment for everyone.
- verifying an edge as passable -> edge becomes `verified_accessible`; a verified repair (WO#) applies the
  upgrade's physical changes and clears the obstacles it resolves.
The most recent event per edge wins.

Per-session sandbox (fix pack X1): every Streamlit session gets its own SQLite file
(<state>/sessions/<session_id>.db) seeded from sample_reports.json, selected through a context variable —
config.DB_PATH is never changed. Outside a session (tests, CLI) config.DB_PATH is used.
"""
from __future__ import annotations

import contextvars
import json
import re
import sqlite3
import time
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
CREATE TABLE IF NOT EXISTS inspection_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    edge_id TEXT NOT NULL,
    note TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL
);
"""

REPORT_STATUSES = ("pending", "approved", "rejected")
WORK_ORDER_STATUSES = ("open", "in_progress", "done")


def _now() -> str:
    return datetime.now().isoformat(timespec="microseconds")


_SESSION_DB: contextvars.ContextVar[Path | None] = contextvars.ContextVar("accesstwin_session_db", default=None)
SESSION_MAX_AGE_S = 6 * 3600
_cleaned = False


def db_path() -> Path:
    return _SESSION_DB.get() or Path(config.DB_PATH)


def sessions_dir() -> Path:
    return Path(config.STATE_DIR) / "sessions"


def use_session(session_id: str | None) -> Path | None:
    """Point this script run at the session's own DB (seeded on first use). None → shared config.DB_PATH."""
    global _cleaned
    if not session_id:
        _SESSION_DB.set(None)
        return None
    safe = re.sub(r"[^A-Za-z0-9_-]", "", session_id)[:64] or "anon"
    path = sessions_dir() / f"{safe}.db"
    if not _cleaned:  # best-effort cleanup of stale sandboxes, once per process
        _cleaned = True
        cleanup_sessions()
    _SESSION_DB.set(path)
    if not path.exists():
        init_db(seed=True)
    return path


def cleanup_sessions(max_age_s: float = SESSION_MAX_AGE_S) -> int:
    d = sessions_dir()
    if not d.exists():
        return 0
    n, now = 0, time.time()
    for f in d.glob("*.db"):
        try:
            if now - f.stat().st_mtime > max_age_s:
                f.unlink()
                n += 1
        except OSError:
            pass
    return n


def session_uploads_dir() -> Path:
    """Uploads are per session too (same stem as the session DB)."""
    cur = _SESSION_DB.get()
    return Path(config.UPLOADS_DIR) / (cur.stem if cur else "shared")


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
        photo = f"data/photos/{s['photo']}" if s.get("photo") else None
        rid = add_report(s["edge_id"], s["reporter_role"], photo, ai)
        if s.get("status") in ("approved", "rejected"):
            set_report_status(rid, s["status"])
    return len(seeds)


def reset_demo() -> None:
    """Wipe all runtime data and re-seed the sample reports ("Reset demo data" button)."""
    with connect() as conn:
        conn.executescript(SCHEMA)
        for table in ("reports", "verifications", "footfall_runs", "work_orders", "inspection_requests"):
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

WO_NOTE_PREFIX = "WO#"  # verification note prefix linking an on-site check to a completed work order


def _upgrade_changes() -> dict[str, tuple[str, dict]]:
    """upgrade_id -> (edge_id, physical attribute changes) for upgrades that modify an existing segment."""
    try:
        with open(config.UPGRADES_PATH, encoding="utf-8") as f:
            ups = json.load(f)
    except (OSError, ValueError):
        return {}
    return {u["id"]: (u["edge_id"], {k: v for k, v in u.get("changes", {}).items() if k != "status"})
            for u in ups if u.get("edge_id")}


# Approved report type → what it confirms (fix pack X2; documented in DECISIONS).
OBSTACLE_RULES: dict[str, dict] = {
    "high_curb": {"kind": "fact"},
    "missing_ramp": {"kind": "fact"},
    "blocked_ramp": {"kind": "obstruction", "personas": ["wheelchair", "stroller"],
                     "text": "kerb ramp obstructed by parked vehicles"},
    "narrow_path": {"kind": "obstruction", "personas": ["wheelchair", "stroller"],
                    "text": "temporary obstruction narrows the path"},
    "broken_surface": {"kind": "fact", "attrs": {"surface": "broken"}},
    "flooding": {"kind": "obstruction", "personas": ["wheelchair", "elderly", "stroller", "visually_impaired"],
                 "text": "temporary flooding"},
    "no_tactile": {"kind": "fact", "attrs": {"tactile_paving": False}},
    "other": {"kind": "inspection"},
    "none": {"kind": "inspection"},
}


def obstacle_from_report(report_id: int, ai: dict) -> tuple[dict, dict]:
    """(obstacle record, physical attribute changes) for an approved report."""
    otype = (ai or {}).get("obstacle_type", "other")
    rule = OBSTACLE_RULES.get(otype, OBSTACLE_RULES["other"])
    personas = list(rule.get("personas", []))
    if rule["kind"] == "obstruction" and otype in ("blocked_ramp", "narrow_path") and (ai or {}).get("affected_personas"):
        personas = [p for p in ai["affected_personas"] if p in OBSTACLE_RULES["flooding"]["personas"]] or personas
    ob = {"report_id": report_id, "type": otype, "kind": rule["kind"], "personas": personas,
          "text": rule.get("text", otype.replace("_", " "))}
    return ob, dict(rule.get("attrs", {}))


def _upgrade_resolves() -> dict[str, list[str]]:
    try:
        with open(config.UPGRADES_PATH, encoding="utf-8") as f:
            return {u["id"]: list(u.get("resolves", [])) for u in json.load(f)}
    except (OSError, ValueError):
        return {}


def get_overlay() -> dict[str, dict]:
    """edge_id -> attribute overlay from approved reports, verifications and verified repairs (latest event wins).

    A passable verification whose note starts with "WO#<id>" also applies that work order's physical changes
    (e.g. the step removed by a kerb ramp), so a completed and verified repair really changes routing.
    """
    events: list[tuple[str, str, dict]] = []
    repairs = _upgrade_changes()
    resolves = _upgrade_resolves()
    with connect() as conn:
        conn.executescript(SCHEMA)
        orders = {r["id"]: r["upgrade_id"] for r in conn.execute("SELECT id, upgrade_id FROM work_orders WHERE status='done'")}
        for r in conn.execute("SELECT id, edge_id, ai_json, decided_at FROM reports WHERE status='approved'"):
            ob, attrs = obstacle_from_report(int(r["id"]), json.loads(r["ai_json"] or "{}"))
            ob["confirmed_at"] = (r["decided_at"] or "")[:10]
            events.append((r["decided_at"] or "", r["edge_id"], {**attrs, "_add_obstacle": ob}))
        for r in conn.execute("SELECT edge_id, result, note, created_at FROM verifications"):
            status = "verified_accessible" if r["result"] == "passable" else "blocked"
            attrs = {"status": status}
            note = r["note"] or ""
            if status == "verified_accessible" and note.startswith(WO_NOTE_PREFIX):
                try:
                    oid = int(note[len(WO_NOTE_PREFIX):].split()[0])
                except (ValueError, IndexError):
                    oid = None
                upgrade_id = orders.get(oid, "")
                edge_changes = repairs.get(upgrade_id)
                if edge_changes and edge_changes[0] == r["edge_id"]:
                    attrs = {**edge_changes[1], "status": status, "_resolve": resolves.get(upgrade_id, [])}
            events.append((r["created_at"], r["edge_id"], attrs))
    overlay: dict[str, dict] = {}
    for _ts, edge_id, attrs in sorted(events, key=lambda e: e[0]):
        cur = dict(overlay.get(edge_id, {}))
        attrs = dict(attrs)
        add = attrs.pop("_add_obstacle", None)
        resolve = attrs.pop("_resolve", None)
        cur.update(attrs)  # facts and repairs persist; status follows the latest event
        obs = list(cur.get("obstacles", []))
        if add:
            obs.append(add)
            if add["kind"] == "inspection":
                cur["needs_inspection"] = True
        if resolve is not None:
            obs = [o for o in obs if o["type"] not in resolve]
        if obs or "obstacles" in cur:
            cur["obstacles"] = obs
        overlay[edge_id] = cur
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


# ---- footfall runs ---------------------------------------------------------

def add_footfall_run(video_name: str, cctv_id: str | None, total_in: int, total_out: int,
                     buckets_json: str, manual_count: int | None, mock: int) -> int:
    with connect() as conn:
        conn.executescript(SCHEMA)
        cur = conn.execute(
            "INSERT INTO footfall_runs (video_name, cctv_id, total_in, total_out, buckets_json, manual_count, mock, created_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (video_name, cctv_id, int(total_in), int(total_out), buckets_json,
             None if manual_count is None else int(manual_count), int(mock), _now()),
        )
        return int(cur.lastrowid)


def list_footfall_runs() -> list[dict]:
    with connect() as conn:
        conn.executescript(SCHEMA)
        return [dict(r) for r in conn.execute("SELECT * FROM footfall_runs ORDER BY id").fetchall()]


def verify_work_order(order_id: int, verifier_role: str, note: str = "") -> int | None:
    """Mark a work order done and record the on-site verification that applies its physical change."""
    edge = _upgrade_changes()
    with connect() as conn:
        conn.executescript(SCHEMA)
        row = conn.execute("SELECT upgrade_id FROM work_orders WHERE id=?", (order_id,)).fetchone()
    if row is None or row["upgrade_id"] not in edge:
        return None
    set_work_order_status(order_id, "done")
    return add_verification(edge[row["upgrade_id"]][0], verifier_role, "passable",
                            f"{WO_NOTE_PREFIX}{order_id} {note}".strip())


# ---- site inspection requests (X4) --------------------------------------------

def add_inspection_request(edge_id: str, note: str = "") -> int:
    with connect() as conn:
        conn.executescript(SCHEMA)
        cur = conn.execute("INSERT INTO inspection_requests (edge_id, note, status, created_at) VALUES (?,?,?,?)",
                           (edge_id, note, "pending", _now()))
        return int(cur.lastrowid)


def list_inspection_requests(edge_id: str | None = None) -> list[dict]:
    with connect() as conn:
        conn.executescript(SCHEMA)
        q = "SELECT * FROM inspection_requests" + (" WHERE edge_id=?" if edge_id else "") + " ORDER BY id"
        return [dict(r) for r in conn.execute(q, (edge_id,) if edge_id else ()).fetchall()]
