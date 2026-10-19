"""Graph loading, overlay isolation, and node/edge helpers (spec section 7, M2)."""
from __future__ import annotations

import copy

from accesstwin.core.graph import (
    build_graph,
    categories,
    destination_nodes,
    find_edge,
    load_township,
    residential_nodes,
)
from accesstwin.core.personas import load_personas


def test_base_graph_has_16_nodes_and_24_edges():
    G = build_graph(load_township())
    assert G.number_of_nodes() == 16
    assert G.number_of_edges() == 24


def test_overlay_changes_edge_but_base_data_is_not_mutated():
    data = load_township()
    snapshot = copy.deepcopy(data)

    overlaid = build_graph(data, {"E7": {"status": "blocked"}})
    assert find_edge(overlaid, "E7")["status"] == "blocked"

    # A fresh build from the same JSON must not see the overlay.
    fresh = build_graph(data)
    assert find_edge(fresh, "E7")["status"] == "verified_accessible"

    # The source dict itself must be untouched.
    assert data == snapshot


def test_find_edge_returns_none_for_unknown_id():
    G = build_graph(load_township())
    assert find_edge(G, "E999") is None


def test_residential_and_destination_helpers():
    G = build_graph(load_township())
    assert {n["id"] for n in residential_nodes(G)} == {"R1", "R2", "R3", "R4"}
    assert {n["id"] for n in destination_nodes(G)} == {
        "D_CLINIC",
        "D_BUS",
        "D_SCHOOL",
        "D_GROCERY",
        "D_PARK",
    }
    assert {n["id"] for n in destination_nodes(G, "clinic")} == {"D_CLINIC"}


def test_categories_report_max_importance_per_category():
    G = build_graph(load_township())
    cats = categories(G)
    assert cats["clinic"] == 1.0
    assert cats["park"] == 0.5
    assert set(cats) == {"clinic", "bus_stop", "school", "grocery", "park"}


def test_load_personas_returns_four_keyed_personas():
    personas = load_personas()
    assert set(personas) == {"wheelchair", "elderly", "stroller", "visually_impaired"}
    assert personas["wheelchair"].allow_step is False
    assert personas["elderly"].allow_step is True
    assert personas["visually_impaired"].needs_tactile is True
