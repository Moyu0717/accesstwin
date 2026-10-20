"""SQLite store + overlay (spec section 5.7, M4 acceptance). Every test uses an isolated temp DB."""
from __future__ import annotations

import json

import pytest

from accesstwin import config
from accesstwin.core import store
from accesstwin.core.graph import build_graph, find_edge, load_graph, load_township
from accesstwin.core.personas import load_personas
from accesstwin.core.routing import edge_passable, route

PERSONAS = load_personas()
ELDER = PERSONAS["elderly"]


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    store.init_db(seed=False)
    return tmp_path / "t.db"


@pytest.fixture
def seeded_db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    store.init_db(seed=True)
    return tmp_path / "t.db"


# ---------- M4 acceptance: report -> approve -> blocked -> route recomputes ----------


def test_pending_report_does_not_change_overlay(db):
    store.add_report("E7", "resident", None, {"obstacle_type": "high_curb"})
    assert "E7" not in store.get_overlay()
    G = load_graph(with_overlay=True)
    assert find_edge(G, "E7")["status"] == "verified_accessible"


def test_approved_report_confirms_obstacle_and_route_recomputes(db):
    """X2: approval confirms the specific obstacle (a 15 cm step). It no longer closes E7 for everyone."""
    G0 = load_graph(with_overlay=False)
    before = route(G0, "R1", "D_CLINIC", ELDER)
    assert before.reachable
    assert "E7" in before.edges
    assert before.length_m == pytest.approx(450)

    rid = store.add_report("E7", "resident", None, {"obstacle_type": "high_curb"})
    store.set_report_status(rid, "approved")

    entry = store.get_overlay()["E7"]
    assert entry["status"] != "blocked"
    assert [o["type"] for o in entry["obstacles"]] == ["high_curb"]
    assert entry["obstacles"][0]["kind"] == "fact"
    G1 = load_graph(with_overlay=True)
    assert find_edge(G1, "E7")["status"] == "verified_accessible"

    # Older adults can use the step: their direct route is unchanged.
    after = route(G1, "R1", "D_CLINIC", ELDER)
    assert "E7" in after.edges
    assert after.length_m == pytest.approx(450)
    # Wheelchair users are stopped by the recorded step, so they take the detour.
    wheel = route(G1, "R1", "D_CLINIC", PERSONAS["wheelchair"])
    assert "E7" not in wheel.edges
    assert wheel.length_m > 450


def test_rejected_report_leaves_no_overlay(db):
    rid = store.add_report("E7", "resident", None, {})
    store.set_report_status(rid, "rejected")
    assert "E7" not in store.get_overlay()
    assert find_edge(load_graph(with_overlay=True), "E7")["status"] == "verified_accessible"


def test_base_json_is_never_modified(db):
    rid = store.add_report("E7", "resident", None, {"obstacle_type": "high_curb"})
    store.set_report_status(rid, "approved")
    overlaid = find_edge(load_graph(with_overlay=True), "E7")
    assert [o["type"] for o in overlaid["obstacles"]] == ["high_curb"]
    base = build_graph(load_township())
    assert find_edge(base, "E7")["status"] == "verified_accessible"
    assert "obstacles" not in find_edge(base, "E7")
    assert find_edge(base, "E7")["has_step"] is True


# ---------- verification overlay ----------


def test_verification_passable_sets_verified_accessible(db):
    store.add_verification("E9", "guard", "passable", "note")
    assert store.get_overlay()["E9"]["status"] == "verified_accessible"


def test_verification_makes_unverified_route_reachable(db):
    G0 = load_graph(with_overlay=False)
    assert find_edge(G0, "E9")["status"] == "unverified"
    before = route(G0, "R3", "D_PARK", ELDER, include_unverified=False)
    assert before.reachable is False

    store.add_verification("E9", "guard", "passable")
    after = route(load_graph(with_overlay=True), "R3", "D_PARK", ELDER, include_unverified=False)
    assert after.reachable is True
    assert "E9" in after.edges


def test_latest_event_wins_approve_after_verify_keeps_status_and_adds_obstruction(db):
    """X2: a later approved obstruction sets the obstacle for the listed personas; status is not closed for everyone."""
    store.add_verification("E9", "guard", "passable")
    assert store.get_overlay()["E9"]["status"] == "verified_accessible"
    rid = store.add_report("E9", "resident", None, {"obstacle_type": "blocked_ramp",
                                                   "affected_personas": ["wheelchair", "stroller"]})
    store.set_report_status(rid, "approved")
    entry = store.get_overlay()["E9"]
    assert entry["status"] == "verified_accessible"
    assert [o["type"] for o in entry["obstacles"]] == ["blocked_ramp"]
    G = load_graph(with_overlay=True)
    assert edge_passable(find_edge(G, "E9"), PERSONAS["wheelchair"])[0] is False
    assert edge_passable(find_edge(G, "E9"), ELDER)[0] is True


def test_latest_event_wins_verify_after_approve_keeps_confirmed_obstacle(db):
    """A plain passable verification sets the status but never removes a confirmed obstacle (only a
    verified repair whose upgrade resolves that type does)."""
    rid = store.add_report("E7", "resident", None, {"obstacle_type": "high_curb"})
    store.set_report_status(rid, "approved")
    assert [o["type"] for o in store.get_overlay()["E7"]["obstacles"]] == ["high_curb"]
    store.add_verification("E7", "guard", "passable", "looked at it")
    entry = store.get_overlay()["E7"]
    assert entry["status"] == "verified_accessible"
    assert [o["type"] for o in entry["obstacles"]] == ["high_curb"]
    assert edge_passable(find_edge(load_graph(with_overlay=True), "E7"), PERSONAS["wheelchair"])[0] is False


def test_not_passable_verification_blocks(db):
    store.add_verification("E9", "guard", "not_passable")
    assert store.get_overlay()["E9"]["status"] == "blocked"


def test_invalid_verification_result_raises(db):
    with pytest.raises(ValueError):
        store.add_verification("E9", "guard", "maybe")


# ---------- reports validation ----------


def test_add_report_bad_status_raises(db):
    with pytest.raises(ValueError):
        store.add_report("E7", "resident", None, {}, status="bogus")


def test_set_report_status_bad_status_raises(db):
    rid = store.add_report("E7", "resident", None, {})
    with pytest.raises(ValueError):
        store.set_report_status(rid, "nope")


def test_report_ai_json_round_trips(db):
    ai = {"obstacle_type": "high_curb", "confidence": 0.82}
    store.add_report("E7", "resident", "data/uploads/x.png", ai)
    (row,) = store.list_reports()
    assert row["ai"] == ai
    assert row["status"] == "pending"
    assert row["photo_path"] == "data/uploads/x.png"


# ---------- work orders ----------


def test_work_order_lifecycle(db):
    oid = store.add_work_order("U1")
    orders = store.list_work_orders()
    assert len(orders) == 1
    assert orders[0]["id"] == oid
    assert orders[0]["upgrade_id"] == "U1"
    assert orders[0]["status"] == "open"

    store.set_work_order_status(oid, "done")
    assert store.list_work_orders()[0]["status"] == "done"


def test_work_order_invalid_status_raises(db):
    oid = store.add_work_order("U1")
    with pytest.raises(ValueError):
        store.set_work_order_status(oid, "closed")


# ---------- seeding and reset ----------


def test_init_db_seed_true_seeds_sample_reports(seeded_db):
    sample = json.loads(config.SAMPLE_REPORTS_PATH.read_text(encoding="utf-8"))
    assert len(store.list_reports()) == len(sample)


def test_seeded_approved_reports_are_approved(seeded_db):
    sample = json.loads(config.SAMPLE_REPORTS_PATH.read_text(encoding="utf-8"))
    expected_approved = sorted(s["edge_id"] for s in sample if s["status"] == "approved")
    got_approved = sorted(r["edge_id"] for r in store.list_reports(status="approved"))
    assert got_approved == expected_approved


def test_reset_demo_clears_runtime_data_and_reseeds(seeded_db):
    store.add_verification("E9", "guard", "passable")
    store.add_work_order("U1")
    store.add_report("E7", "resident", None, {})

    store.reset_demo()

    sample = json.loads(config.SAMPLE_REPORTS_PATH.read_text(encoding="utf-8"))
    assert store.list_verifications() == []
    assert store.list_work_orders() == []
    assert len(store.list_reports()) == len(sample)
    assert "E9" not in store.get_overlay()
    assert all(r["status"] in ("pending", "approved", "rejected") for r in store.list_reports())
    expected_approved = sorted(s["edge_id"] for s in sample if s["status"] == "approved")
    assert sorted(r["edge_id"] for r in store.list_reports(status="approved")) == expected_approved
