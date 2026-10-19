"""Persona routing: edge passability, edge cost, and route results (spec section 7, M2)."""
from __future__ import annotations

import pytest

from accesstwin.core.graph import build_graph, find_edge, load_township
from accesstwin.core.personas import load_personas
from accesstwin.core.routing import edge_cost, edge_passable, route

PERSONAS = load_personas()
WHEEL = PERSONAS["wheelchair"]
ELDER = PERSONAS["elderly"]
STROLLER = PERSONAS["stroller"]
VI = PERSONAS["visually_impaired"]
ALL = [WHEEL, ELDER, STROLLER, VI]


@pytest.fixture(scope="module")
def G():
    return build_graph(load_township())


# ---------- route: wheelchair / stroller fallback (M2 storyline) ----------


def test_wheelchair_direct_route_blocked_by_e7(G):
    res = route(G, "R1", "D_CLINIC", WHEEL)
    assert res.direct_reachable is False
    assert res.reason is not None
    assert "E7" in res.reason
    assert "step 15 cm" in res.reason


def test_wheelchair_fallback_is_long_uncovered_and_avoids_e7(G):
    res = route(G, "R1", "D_CLINIC", WHEEL)
    assert res.reachable is True
    assert res.detour_ratio is not None and res.detour_ratio >= 2
    assert res.covered_ratio < 0.5
    assert "E7" not in res.edges


def test_stroller_same_storyline_as_wheelchair(G):
    res = route(G, "R1", "D_CLINIC", STROLLER)
    assert res.direct_reachable is False
    assert "E7" in (res.reason or "")
    assert res.reachable is True
    assert res.detour_ratio is not None and res.detour_ratio >= 2
    assert res.covered_ratio < 0.5
    assert "E7" not in res.edges


# ---------- route: elderly direct route ----------


def test_elderly_reaches_clinic_directly_via_e1_e5_e7(G):
    res = route(G, "R1", "D_CLINIC", ELDER)
    assert res.reachable is True
    assert res.direct_reachable is True
    assert res.edges == ["E1", "E5", "E7"]
    assert res.length_m == 450
    assert res.reason is None


# ---------- route: include_unverified toggle ----------


def test_r3_to_park_unreachable_for_elderly_by_default(G):
    res = route(G, "R3", "D_PARK", ELDER)
    assert res.reachable is False
    assert res.reason is not None
    assert "E9" in res.reason
    assert "unverified" in res.reason


def test_r3_to_park_reachable_with_include_unverified(G):
    res = route(G, "R3", "D_PARK", ELDER, include_unverified=True)
    assert res.reachable is True
    assert "E9" in res.edges
    assert "E9" in res.unverified_edges


def test_include_unverified_toggle_changes_result(G):
    default = route(G, "R3", "D_PARK", ELDER)
    relaxed = route(G, "R3", "D_PARK", ELDER, include_unverified=True)
    assert default.reachable != relaxed.reachable


# ---------- edge_passable ----------


def test_blocked_edge_e20_not_passable_for_any_persona(G):
    edge = find_edge(G, "E20")
    for persona in ALL:
        assert edge_passable(edge, persona)[0] is False
        assert edge_passable(edge, persona, include_unverified=True)[0] is False


def test_unverified_e9_passable_only_with_include_unverified(G):
    edge = find_edge(G, "E9")
    for persona in ALL:
        assert edge_passable(edge, persona, include_unverified=False)[0] is False
        assert edge_passable(edge, persona, include_unverified=True)[0] is True


def test_broken_surface_e12_fails_all_four_personas(G):
    edge = find_edge(G, "E12")
    for persona in ALL:
        ok, reason = edge_passable(edge, persona)
        assert ok is False
        assert "E12" in reason


def test_gravel_e21_fails_wheelchair_but_passes_elderly(G):
    edge = find_edge(G, "E21")
    ok_w, reason_w = edge_passable(edge, WHEEL)
    assert ok_w is False
    assert "E21" in reason_w
    assert edge_passable(edge, ELDER)[0] is True


def test_steep_e23_fails_wheelchair_stroller_elderly_passes_vi(G):
    edge = find_edge(G, "E23")
    for persona in (WHEEL, STROLLER, ELDER):
        ok, reason = edge_passable(edge, persona)
        assert ok is False
        assert "slope" in reason
    assert edge_passable(edge, VI)[0] is True


def test_step_e7_fails_wheelchair_and_stroller_passes_elderly(G):
    edge = find_edge(G, "E7")
    assert edge_passable(edge, WHEEL)[0] is False
    assert edge_passable(edge, STROLLER)[0] is False
    assert edge_passable(edge, ELDER)[0] is True


# ---------- edge_cost ----------


def test_elderly_uncovered_edge_costs_1_3x_length(G):
    edge = find_edge(G, "E2")  # uncovered, good surface, no tactile
    assert edge["covered"] is False
    assert edge_cost(edge, ELDER) == pytest.approx(edge["length_m"] * 1.3)


def test_visually_impaired_non_tactile_edge_costs_1_5x_length(G):
    edge = find_edge(G, "E2")  # no tactile paving
    assert edge["tactile_paving"] is False
    assert edge_cost(edge, VI) == pytest.approx(edge["length_m"] * 1.5)


def test_cracked_e24_adds_20_percent(G):
    edge = find_edge(G, "E24")
    assert edge["surface"] == "cracked"
    # Wheelchair has no covered/tactile penalty, so only the cracked surface applies.
    assert edge_cost(edge, WHEEL) == pytest.approx(edge["length_m"] * 1.2)
