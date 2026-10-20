"""Round 2B store rules for resident reports: receipt tokens, idempotent submit, triage, Track my report.

Uses an isolated temp DB per test (same pattern as test_store.py).
"""
from __future__ import annotations

import re
import sqlite3

import pytest

from accesstwin import config
from accesstwin.core import store
from accesstwin.core.graph import find_edge, load_graph

TOKEN_RE = re.compile(r"AT-[ABCDEFGHJKLMNPQRSTUVWXYZ23456789]{4}-[ABCDEFGHJKLMNPQRSTUVWXYZ23456789]{4}")
AI_HIGH = {"obstacle_type": "high_curb", "severity": "high", "affected_personas": ["wheelchair"],
           "confidence": 0.8, "visible_evidence": "step", "needs_onsite_measurement": []}


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    store.init_db(seed=False)
    return tmp_path / "t.db"


def _submit(key, desc="A step at the entrance", edge="E7", photo=None):
    return store.submit_report(edge, "resident", desc, photo, dict(AI_HIGH), None, key)


# ---------- tokens ----------

def test_new_token_format_and_unambiguous_alphabet():
    tokens = [store.new_token() for _ in range(500)]
    assert all(TOKEN_RE.fullmatch(t) for t in tokens)
    assert not any(ch in "01IO" for t in tokens for ch in t)
    assert len(set(tokens)) == len(tokens)


def test_tokens_are_unique_in_db_and_unique_index_exists(db):
    ids = [store.add_report("E7", "resident", None, AI_HIGH, description=f"d{i}") for i in range(40)]
    tokens = [store.get_report(i)["token"] for i in ids]
    assert len(set(tokens)) == 40 and all(TOKEN_RE.fullmatch(t) for t in tokens)
    with store.connect() as conn:
        idx = conn.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='ux_reports_token'").fetchone()
    assert idx is not None


def test_get_report_by_token_rejects_malformed_codes(db):
    store.add_report("E7", "resident", None, AI_HIGH, description="x")
    for bad in ["", None, "AT-123", "XX-ABCD-EFGH", "AT-ABCD-EFGHI", "AT-ABCD_EFGH", "AT-ABCD-EFG", "1234567890"]:
        assert store.get_report_by_token(bad) is None, bad


def test_get_report_by_token_is_case_insensitive_and_trims(db):
    rid = store.add_report("E7", "resident", None, AI_HIGH, description="x")
    token = store.get_report(rid)["token"]
    assert store.get_report_by_token(token.lower())["id"] == rid
    assert store.get_report_by_token("  " + token + " ")["id"] == rid
    assert store.get_report_by_token("AT-AAAA-AAAA") is None  # well-formed but unknown


# ---------- idempotent submit ----------

def test_same_idem_key_twice_gives_one_row(db):
    first = _submit("key-1")
    second = _submit("key-1")
    assert first["created"] is True and second["created"] is False
    assert first["id"] == second["id"]
    assert len([r for r in store.list_reports() if r["idem_key"] == "key-1"]) == 1


def test_different_idem_keys_give_two_rows(db):
    a, b = _submit("key-a"), _submit("key-b")
    assert a["id"] != b["id"]
    assert len(store.list_reports()) == 2


def test_submit_needs_description_or_photo(db):
    with pytest.raises(ValueError):
        _submit("k-empty", desc="")
    with pytest.raises(ValueError):
        _submit("k-blank", desc="   ")
    assert store.list_reports() == []
    ok = _submit("k-photo-only", desc="", photo="data/photos/curb_high_step.png")
    assert ok["photo_path"] == "data/photos/curb_high_step.png" and ok["description"] == ""


def test_submit_requires_idem_key(db):
    with pytest.raises(ValueError):
        store.submit_report("E7", "resident", "text", None, dict(AI_HIGH), None, "")


# ---------- triage ----------

def test_accept_approves_and_confirms_obstacle_but_does_not_close_for_everyone(db):
    rid = _submit("k-accept")["id"]
    r = store.triage_report(rid, "accept")
    assert (r["status"], r["triage"]) == ("approved", "accepted") and r["decided_at"]
    e7 = find_edge(load_graph(with_overlay=True), "E7")
    assert [o["type"] for o in e7["obstacles"]] == ["high_curb"]
    assert e7["status"] == "verified_accessible"  # confirmed obstacle, not a closure


def test_request_info_needs_reason_stays_pending_and_is_not_in_overlay(db):
    rid = _submit("k-info")["id"]
    with pytest.raises(ValueError):
        store.triage_report(rid, "request_info", reason="   ")
    r = store.triage_report(rid, "request_info", reason="a photo of the kerb")
    assert (r["status"], r["triage"], r["reason"]) == ("pending", "needs_information", "a photo of the kerb")
    assert [x["id"] for x in store.list_reports("pending")] == [rid]
    assert "E7" not in store.get_overlay()


def test_duplicate_links_to_root_and_rejects_self_or_missing(db):
    a, b, c = (_submit(f"k-d-{n}")["id"] for n in "abc")
    with pytest.raises(ValueError):
        store.triage_report(a, "duplicate", duplicate_of=a)
    with pytest.raises(ValueError):
        store.triage_report(a, "duplicate", duplicate_of=99999)
    with pytest.raises(ValueError):
        store.triage_report(a, "duplicate", duplicate_of=None)
    rb = store.triage_report(b, "duplicate", duplicate_of=a)
    assert (rb["status"], rb["triage"], rb["duplicate_of"]) == ("rejected", "duplicate", a)
    rc = store.triage_report(c, "duplicate", duplicate_of=b)  # b is itself a duplicate: link to the root
    assert rc["duplicate_of"] == a
    assert "E7" not in store.get_overlay()


def test_reject_needs_reason(db):
    rid = _submit("k-rej")["id"]
    with pytest.raises(ValueError):
        store.triage_report(rid, "reject", reason="")
    assert store.get_report(rid)["status"] == "pending"
    r = store.triage_report(rid, "reject", reason="not on a walkway")
    assert (r["status"], r["triage"], r["reason"]) == ("rejected", "rejected", "not on a walkway")


def test_unknown_triage_action_and_report_raise(db):
    rid = _submit("k-bad")["id"]
    with pytest.raises(ValueError):
        store.triage_report(rid, "delete")
    with pytest.raises(ValueError):
        store.triage_report(99999, "accept")


# ---------- resident answers a request for information ----------

def test_add_report_info_only_when_needs_information(db):
    rep = _submit("k-addinfo")
    token = rep["token"]
    before = store.get_report(rep["id"])["description"]
    store.add_report_info(token, "extra detail")  # not requested: nothing changes
    assert store.get_report(rep["id"])["description"] == before
    store.triage_report(rep["id"], "request_info", reason="how high is the kerb?")
    store.add_report_info(token, "about 15 cm")
    r = store.get_report(rep["id"])
    assert r["triage"] is None and r["status"] == "pending"
    assert r["description"].startswith(before) and "about 15 cm" in r["description"]


def test_add_report_info_ignores_empty_text_and_unknown_code(db):
    rep = _submit("k-addinfo-2")
    store.triage_report(rep["id"], "request_info", reason="more detail")
    store.add_report_info(rep["token"], "   ")
    assert store.get_report(rep["id"])["triage"] == "needs_information"
    assert store.add_report_info("AT-AAAA-AAAA", "x") is None


# ---------- report_state wording ----------

def test_report_state_texts_make_no_time_promises(db):
    promise = re.compile(r"\b(\d+|one|two|three|a few|several)\s*(hours?|hrs?|days?|weeks?|minutes?|mins?)\b"
                         r"|\bwithin\b|\bsoon\b|\bby (tomorrow|monday|tuesday|wednesday|thursday|friday)\b"
                         r"|\bguarantee", re.I)
    rep = _submit("k-states")
    rid = rep["id"]
    states = [store.report_state(store.get_report(rid))]
    store.triage_report(rid, "request_info", reason="a photo")
    states.append(store.report_state(store.get_report(rid)))
    store.add_report_info(rep["token"], "a photo")
    states.append(store.report_state(store.get_report(rid)))
    rid2 = _submit("k-states-2")["id"]
    store.triage_report(rid2, "accept")
    states.append(store.report_state(store.get_report(rid2)))
    rid3 = _submit("k-states-3")["id"]
    store.triage_report(rid3, "reject", reason="not a walkway")
    states.append(store.report_state(store.get_report(rid3)))
    rid4 = _submit("k-states-4")["id"]
    store.triage_report(rid4, "duplicate", duplicate_of=rid)
    states.append(store.report_state(store.get_report(rid4)))
    assert len({s for s, _ in states}) >= 5
    for state, nxt in states:
        assert not promise.search(state + " " + nxt), (state, nxt)


# ---------- legacy DB migration ----------

def test_legacy_reports_table_gets_new_columns_in_place(tmp_path, monkeypatch):
    legacy = tmp_path / "legacy.db"
    conn = sqlite3.connect(legacy)
    conn.executescript(
        """
        CREATE TABLE reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            edge_id TEXT NOT NULL,
            reporter_role TEXT NOT NULL,
            photo_path TEXT,
            ai_json TEXT,
            status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','approved','rejected')),
            created_at TEXT NOT NULL,
            decided_at TEXT);
        INSERT INTO reports (edge_id, reporter_role, photo_path, ai_json, status, created_at, decided_at)
        VALUES ('E7', 'resident', NULL, '{"obstacle_type": "high_curb", "severity": "high"}', 'approved',
                '2025-01-01T00:00:00', '2025-01-01T00:00:00');
        """
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(config, "DB_PATH", legacy)

    old = store.list_reports()
    assert len(old) == 1 and old[0]["edge_id"] == "E7"
    assert TOKEN_RE.fullmatch(old[0]["token"]) and old[0]["ai_original"] is None  # legacy rows get a code
    assert store.get_report_by_token(old[0]["token"])["id"] == old[0]["id"]
    with store.connect(legacy) as c:
        cols = {row[1] for row in c.execute("PRAGMA table_info(reports)")}
    assert {"token", "description", "ai_original_json", "triage", "duplicate_of", "reason", "idem_key"} <= cols
    # the migrated DB works with the new functions, and the old approved row still confirms its obstacle
    new = _submit("k-legacy")
    assert TOKEN_RE.fullmatch(new["token"])
    assert store.get_report_by_token(new["token"])["id"] == new["id"]
    assert [o["type"] for o in store.get_overlay()["E7"]["obstacles"]] == ["high_curb"]


def test_decided_report_cannot_be_triaged_again(db):
    rid = store.add_report("E7", "resident", None, {"obstacle_type": "high_curb"}, description="step")
    store.triage_report(rid, "accept")
    with pytest.raises(ValueError):
        store.triage_report(rid, "reject", reason="changed my mind")
    assert store.get_report(rid)["status"] == "approved"
    assert any(o["type"] == "high_curb" for o in store.get_overlay()["E7"]["obstacles"])
