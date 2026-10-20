"""Fix pack V2 R1 X1 (per-session demo sandbox) and X2 (approval confirms a specific obstacle).

Every test runs against its own temp state dir; config.DB_PATH / STATE_DIR are monkeypatched, never the real data.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from accesstwin import config
from accesstwin.core import store
from accesstwin.core.graph import build_graph, find_edge, load_graph, load_township
from accesstwin.core.personas import load_personas
from accesstwin.core.routing import edge_passable, route
from accesstwin.core.scoring import compute_scores
from accesstwin.core.simulation import apply_upgrade, load_upgrades, unresolved_obstacles
from accesstwin.core.validate import validate_all

ROOT = Path(__file__).resolve().parent.parent
PAGES = {p.name.split("_")[0]: str(p) for p in (ROOT / "pages").glob("*.py")}
P = load_personas()
WHEEL, ELDER, STROLLER, VI = P["wheelchair"], P["elderly"], P["stroller"], P["visually_impaired"]
ALL = [WHEEL, ELDER, STROLLER, VI]


# ---------- fixtures and helpers ----------


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """Isolated state dir. Startup cleanup is disabled here; cleanup has its own test."""
    state = tmp_path / "state"
    monkeypatch.setattr(config, "STATE_DIR", state)
    monkeypatch.setattr(config, "UPLOADS_DIR", state / "uploads")
    monkeypatch.setattr(config, "DB_PATH", state / "shared.db")
    monkeypatch.setattr(store, "_cleaned", True)
    yield state
    store._SESSION_DB.set(None)  # never leak a session selection into other tests


@pytest.fixture
def db(sandbox):
    """Shared (non-session) DB without seed rows."""
    store.use_session(None)
    store.init_db(seed=False)
    return config.DB_PATH


@pytest.fixture
def seeded(sandbox):
    """Shared (non-session) DB with the sample reports seeded."""
    store.use_session(None)
    store.init_db(seed=True)
    return config.DB_PATH


def _approve_new(edge_id: str, otype: str, personas: list[str] | None = None) -> int:
    ai = {"obstacle_type": otype, "affected_personas": personas or []}
    rid = store.add_report(edge_id, "resident", None, ai)
    store.set_report_status(rid, "approved")
    return rid


def _pending_id(edge_id: str) -> int:
    return next(r["id"] for r in store.list_reports("pending") if r["edge_id"] == edge_id)


def _approved_edges() -> list[str]:
    return sorted(r["edge_id"] for r in store.list_reports(status="approved"))


def _obstacle_types(edge: dict) -> list[str]:
    return [o["type"] for o in edge.get("obstacles", []) or []]


def _upgrade(uid: str) -> dict:
    return next(u for u in load_upgrades() if u["id"] == uid)


# =====================================================================================
# X1: per-session sandbox
# =====================================================================================


def test_x1_two_sessions_are_isolated(sandbox):
    store.use_session("alpha")
    rid = _pending_id("E7")
    store.set_report_status(rid, "approved")
    assert _obstacle_types(store.get_overlay()["E7"]) == ["high_curb"]

    path_a = store.db_path()
    path_b = store.use_session("beta")
    assert path_a != path_b  # two distinct DB files
    b_e7 = [r for r in store.list_reports("pending") if r["edge_id"] == "E7"]
    assert [r["id"] for r in b_e7] == [rid]  # still pending in B
    assert "E7" not in store.get_overlay()  # no E7 obstacle in B

    store.use_session("alpha")
    assert rid in [r["id"] for r in store.list_reports(status="approved")]
    assert _obstacle_types(store.get_overlay()["E7"]) == ["high_curb"]


def test_x1_first_visit_seeds_the_story(seeded):
    ref_overlay = store.get_overlay()  # reference: the shared seed DB
    store.use_session("visitor-1")

    reports = store.list_reports()
    assert len(reports) == 5
    sr1 = [r for r in reports if r["edge_id"] == "E7"]
    assert len(sr1) == 1 and sr1[0]["status"] == "pending"
    assert sr1[0]["ai"]["obstacle_type"] == "high_curb"

    overlay = store.get_overlay()
    assert overlay == ref_overlay
    assert _obstacle_types(overlay["E20"]) == ["blocked_ramp"]
    assert overlay["E20"]["obstacles"][0]["kind"] == "obstruction"
    assert overlay["E20"]["obstacles"][0]["personas"] == ["wheelchair", "stroller"]
    assert overlay["E21"]["needs_inspection"] is True
    assert "E7" not in overlay  # SR1 is still pending on a first visit

    G = load_graph()
    wheel = route(G, "R1", "D_CLINIC", WHEEL)
    assert wheel.length_m == pytest.approx(1100)
    assert wheel.direct_reachable is False

    expected = compute_scores(build_graph(load_township(), ref_overlay), P).index
    assert compute_scores(G, P).index == pytest.approx(expected)


def test_x1_reset_demo_only_resets_the_current_session(seeded):
    store.use_session("A")
    store.set_report_status(_pending_id("E7"), "approved")
    store.use_session("B")
    store.set_report_status(_pending_id("E12"), "approved")

    store.use_session("A")
    store.reset_demo()
    assert _approved_edges() == ["E20", "E21"]  # A is back to the seed
    assert "E7" not in store.get_overlay()

    store.use_session("B")
    assert _approved_edges() == ["E12", "E20", "E21"]  # B keeps its own approval
    assert _pending_id("E7") is not None


def test_x1_cleanup_removes_only_stale_session_dbs(sandbox):
    assert store.SESSION_MAX_AGE_S == 6 * 3600
    store.use_session("old")
    store.use_session("fresh")
    old = store.sessions_dir() / "old.db"
    fresh = store.sessions_dir() / "fresh.db"
    assert old.exists() and fresh.exists()

    stale = time.time() - 7 * 3600
    os.utime(old, (stale, stale))
    assert store.cleanup_sessions() == 1
    assert not old.exists()
    assert fresh.exists()


def test_x1_uploads_dir_is_per_session(sandbox):
    store.use_session("A")
    dir_a = store.session_uploads_dir()
    store.use_session("B")
    dir_b = store.session_uploads_dir()
    assert dir_a != dir_b
    assert dir_a.parent == dir_b.parent == Path(config.UPLOADS_DIR)
    store.use_session(None)
    assert store.session_uploads_dir() == Path(config.UPLOADS_DIR) / "shared"


def test_x1_use_session_none_falls_back_to_config_db(sandbox):
    assert store.use_session(None) is None
    assert store.db_path() == Path(config.DB_PATH)
    store.init_db(seed=False)
    store.add_report("E7", "resident", None, {})
    assert Path(config.DB_PATH).exists()
    assert not store.sessions_dir().exists() or not any(store.sessions_dir().glob("*.db"))


def test_x1_session_id_is_sanitised_into_the_sessions_dir(sandbox):
    path = store.use_session("../../evil?id")
    assert path.parent == store.sessions_dir()
    assert path.name == "evilid.db"


def test_x1_apptest_instances_share_one_default_session_id(sandbox, monkeypatch):
    """Documents a test-harness limit: every AppTest instance reports the same Streamlit session id, so with the
    real session_id() they all land in one sandbox file. Real browser visitors each get their own id."""
    monkeypatch.setenv("ACCESSTWIN_SESSION_SANDBOX", "1")
    page = PAGES["3"]
    a = AppTest.from_file(page, default_timeout=60)
    a.run()
    b = AppTest.from_file(page, default_timeout=60)
    b.run()
    assert not a.exception and not b.exception
    assert len(list(store.sessions_dir().glob("*.db"))) == 1
    a.button(key="vq_ok_1").click().run()
    b.run()
    assert not any(btn.key == "vq_ok_1" for btn in b.button)  # shared sandbox: B sees A's approval


def test_x1_two_apptest_visitors_have_separate_queues(sandbox, monkeypatch):
    """Page-level isolation: each AppTest instance gets its own session id (its own st.session_state), which the
    sandbox maps to its own DB. The id is injected here because AppTest does not expose a per-instance id."""
    import uuid

    import streamlit as st

    from accesstwin.ui import components

    monkeypatch.setenv("ACCESSTWIN_SESSION_SANDBOX", "1")
    monkeypatch.setattr(components, "session_id",
                        lambda: st.session_state.setdefault("_test_sid", uuid.uuid4().hex))
    page = PAGES["3"]
    a = AppTest.from_file(page, default_timeout=60)
    a.run()
    b = AppTest.from_file(page, default_timeout=60)
    b.run()
    assert not a.exception and not b.exception
    assert any(btn.key == "vq_ok_1" for btn in a.button)  # SR1 (E7) pending in A
    assert any(btn.key == "vq_ok_1" for btn in b.button)  # and in B

    a.button(key="vq_ok_1").click().run()
    assert not a.exception
    assert not any(btn.key == "vq_ok_1" for btn in a.button)  # gone from A's pending list

    b.run()
    assert not b.exception
    assert any(btn.key == "vq_ok_1" for btn in b.button)  # B still sees SR1 pending
    assert len(list(store.sessions_dir().glob("*.db"))) >= 2  # one DB file per visitor


# =====================================================================================
# X2: approval confirms a specific obstacle
# =====================================================================================


def test_x2_approving_sr1_keeps_older_adult_and_low_vision_direct_route(seeded):
    G_before = load_graph()
    before = {k: route(G_before, "R1", "D_CLINIC", P[k]) for k in ("elderly", "visually_impaired")}
    store.set_report_status(_pending_id("E7"), "approved")
    G_after = load_graph()
    for key, res_before in before.items():
        res = route(G_after, "R1", "D_CLINIC", P[key])
        assert res.reachable is True
        assert res.direct_reachable is True
        assert res.edges == ["E1", "E5", "E7"]
        assert res.edges == res_before.edges
        assert res.length_m == pytest.approx(450)
        assert res.reason is None


def test_x2_approving_sr1_blocks_only_wheelchair_and_stroller_by_the_step(seeded):
    store.set_report_status(_pending_id("E7"), "approved")
    G = load_graph()
    for key in ("wheelchair", "stroller"):
        res = route(G, "R1", "D_CLINIC", P[key])
        assert res.direct_reachable is False
        assert "E7" in (res.reason or "") and "step 15 cm" in res.reason
        assert "E7" not in res.edges
    e7 = find_edge(G, "E7")
    # Inspector-facing physical fact stays the recorded step, never "Blocked".
    assert e7["has_step"] is True
    assert e7["curb_height_cm"] == 15
    assert e7["status"] != "blocked"


def test_x2_approved_blocked_ramp_obstructs_wheelchair_and_stroller_only(db):
    rid = _approve_new("E20", "blocked_ramp", ["wheelchair", "stroller"])
    e20 = find_edge(load_graph(), "E20")
    for key in ("wheelchair", "stroller"):
        ok, reason = edge_passable(e20, P[key])
        assert ok is False
        assert "obstructed by parked vehicles (report #" in reason
        assert reason.endswith(f"(report #{rid})")
    for key in ("elderly", "visually_impaired"):
        assert edge_passable(e20, P[key])[0] is True
    assert e20["status"] == "verified_accessible"


def test_x2_approved_broken_surface_sets_surface_broken(db):
    _approve_new("E2", "broken_surface")
    e2 = find_edge(load_graph(), "E2")
    assert e2["surface"] == "broken"
    for persona in ALL:
        ok, reason = edge_passable(e2, persona)
        assert ok is False
        assert "broken surface" in reason


def test_x2_approved_other_flags_inspection_without_routing_change(seeded):
    G_before = load_graph()
    before = {k: route(G_before, "R1", "D_CLINIC", P[k]) for k in P}
    _approve_new("E7", "other")  # SR1 stays pending; only the "other" report is approved
    G_after = load_graph()
    e7 = find_edge(G_after, "E7")
    assert e7["needs_inspection"] is True
    assert _obstacle_types(e7) == ["other"]
    assert e7["status"] == "verified_accessible"
    for key, res_before in before.items():
        res = route(G_after, "R1", "D_CLINIC", P[key])
        assert res.edges == res_before.edges
        assert res.length_m == pytest.approx(res_before.length_m)
        assert res.reachable is res_before.reachable
        assert res.direct_reachable is res_before.direct_reachable


def test_x2_approved_flooding_blocks_all_four_personas(db):
    rid = _approve_new("E2", "flooding")
    e2 = find_edge(load_graph(), "E2")
    for persona in ALL:
        ok, reason = edge_passable(e2, persona)
        assert ok is False
        assert "temporary flooding" in reason
        assert reason.endswith(f"(report #{rid})")


def test_x2_u1_resolves_the_high_curb_on_e7(seeded):
    store.set_report_status(_pending_id("E7"), "approved")
    G = load_graph()
    assert _obstacle_types(find_edge(G, "E7")) == ["high_curb"]
    H = apply_upgrade(G, _upgrade("U1"))
    e7 = find_edge(H, "E7")
    assert e7["has_step"] is False
    assert e7["curb_height_cm"] == 0
    assert _obstacle_types(e7) == []
    res = route(H, "R1", "D_CLINIC", WHEEL)
    assert res.direct_reachable is True
    assert res.length_m == pytest.approx(450)
    assert find_edge(G, "E7")["has_step"] is True  # the base scenario graph is not mutated


def test_x2_u1_does_not_resolve_a_blocked_ramp_on_e7(db):
    _approve_new("E7", "high_curb")
    rid = _approve_new("E7", "blocked_ramp", ["wheelchair", "stroller"])
    G = load_graph()
    U1 = _upgrade("U1")
    assert [o["type"] for o in unresolved_obstacles(G, U1)] == ["blocked_ramp"]

    H = apply_upgrade(G, U1)
    e7 = find_edge(H, "E7")
    assert _obstacle_types(e7) == ["blocked_ramp"]
    assert e7["has_step"] is False  # the ramp is built, the parked cars remain
    res = route(H, "R1", "D_CLINIC", WHEEL)
    assert res.direct_reachable is False
    assert f"obstructed by parked vehicles (report #{rid})" in (res.reason or "")


def test_x2_verified_u1_work_order_clears_only_the_resolved_high_curb(db):
    _approve_new("E7", "high_curb")
    _approve_new("E7", "blocked_ramp", ["wheelchair", "stroller"])
    oid = store.add_work_order("U1")
    assert store.verify_work_order(oid, "guard", "ramp built") is not None

    e7 = find_edge(load_graph(), "E7")
    assert _obstacle_types(e7) == ["blocked_ramp"]
    assert e7["has_step"] is False
    assert edge_passable(e7, WHEEL)[0] is False
    assert edge_passable(e7, ELDER)[0] is True


def test_x2_validate_all_has_no_errors():
    assert validate_all() == []
