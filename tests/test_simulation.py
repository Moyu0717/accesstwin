"""What-if simulation and upgrade ROI tests (spec sections 5.3 and 7, M3)."""
from __future__ import annotations

import pytest

from accesstwin import config
from accesstwin.core.graph import build_graph, find_edge, load_township
from accesstwin.core.personas import load_personas
from accesstwin.core.scoring import compute_scores
from accesstwin.core.simulation import (
    apply_upgrade,
    apply_upgrades,
    benefit,
    compare,
    load_upgrades,
    rank_upgrades,
)


@pytest.fixture(scope="module")
def G():
    return build_graph(load_township())


@pytest.fixture(scope="module")
def personas():
    return load_personas()


@pytest.fixture(scope="module")
def upgrades():
    return load_upgrades()


@pytest.fixture(scope="module")
def by_id(upgrades):
    return {u["id"]: u for u in upgrades}


@pytest.fixture(scope="module")
def before(G, personas):
    return compute_scores(G, personas)


@pytest.fixture(scope="module")
def u1_delta(G, personas, before, by_id):
    G2 = apply_upgrade(G, by_id["U1"])
    return compare(G, G2, personas, before)


@pytest.fixture(scope="module")
def ranked_operate(G, upgrades, personas):
    return rank_upgrades(G, upgrades, personas, mode="operate")


@pytest.fixture(scope="module")
def ranked_design(G, upgrades, personas):
    return rank_upgrades(G, upgrades, personas, mode="design")


# ---------- single upgrade effect (U1: kerb ramp at E7) ----------


def test_u1_raises_wheelchair_persona_index(u1_delta):
    assert u1_delta.persona_after["wheelchair"] > u1_delta.persona_before["wheelchair"]


def test_u1_has_newly_reachable_pairs(u1_delta):
    assert len(u1_delta.newly_reachable) > 0


# ---------- ranking ----------


def test_rank_operate_puts_u1_in_top_two(ranked_operate):
    top2 = ranked_operate.head(2)["id"].tolist()
    assert "U1" in top2


def test_rank_operate_excludes_design_mode_only_u4(ranked_operate):
    assert "U4" not in ranked_operate["id"].tolist()


def test_rank_design_includes_u4(ranked_design):
    assert "U4" in ranked_design["id"].tolist()


def test_rank_roi_equals_benefit_over_cost_weight(ranked_operate):
    for _, row in ranked_operate.iterrows():
        assert row["cost_weight"] == config.COST_TIER_WEIGHTS[row["cost_tier"]]
        assert row["roi"] == pytest.approx(row["benefit"] / row["cost_weight"], abs=0.02)


def test_rank_is_sorted_by_roi_descending(ranked_operate):
    rois = ranked_operate["roi"].tolist()
    assert rois == sorted(rois, reverse=True)


def test_benefit_matches_formula_for_u1(u1_delta):
    expected = (
        u1_delta.index_delta * config.BENEFIT_INDEX_COEF
        + len(u1_delta.newly_reachable) * config.BENEFIT_PAIR_COEF
        + u1_delta.beneficiaries / config.BENEFIT_BENEFICIARY_DIVISOR
    )
    assert benefit(u1_delta) == pytest.approx(expected, rel=1e-9)


def test_benefit_formula_matches_ranked_row_within_rounding(ranked_operate, u1_delta):
    row = ranked_operate[ranked_operate["id"] == "U1"].iloc[0]
    expected = (
        u1_delta.index_delta * config.BENEFIT_INDEX_COEF
        + len(u1_delta.newly_reachable) * config.BENEFIT_PAIR_COEF
        + u1_delta.beneficiaries / config.BENEFIT_BENEFICIARY_DIVISOR
    )
    assert row["benefit"] == pytest.approx(expected, abs=0.1)


# ---------- non-mutation and assume_verified ----------


def test_apply_upgrade_does_not_mutate_original(G, by_id):
    assert find_edge(G, "E7")["has_step"] is True
    apply_upgrade(G, by_id["U1"])
    assert find_edge(G, "E7")["has_step"] is True


def test_simulated_upgraded_edge_is_verified_accessible(G, by_id):
    H = apply_upgrade(G, by_id["U1"], assume_verified=True)
    edge = find_edge(H, "E7")
    assert edge["status"] == "verified_accessible"
    assert edge["has_step"] is False


# ---------- combined scenario ----------


def test_combined_u1_u2_index_delta_at_least_each_alone(G, personas, before, by_id):
    alone_u1 = compare(G, apply_upgrade(G, by_id["U1"]), personas, before).index_delta
    alone_u2 = compare(G, apply_upgrade(G, by_id["U2"]), personas, before).index_delta
    combined = compare(G, apply_upgrades(G, [by_id["U1"], by_id["U2"]]), personas, before).index_delta
    assert combined >= alone_u1 - 1e-9
    assert combined >= alone_u2 - 1e-9


# ---------- explanations ----------


def test_explanations_non_empty(ranked_operate):
    assert all(isinstance(t, str) and t.strip() for t in ranked_operate["explanation"])


def test_u1_explanation_mentions_wheelchair_and_clinic(ranked_operate):
    text = ranked_operate[ranked_operate["id"] == "U1"].iloc[0]["explanation"].lower()
    assert "wheelchair" in text
    assert "clinic" in text


def test_u7_lighting_has_no_effect(G, personas, before, by_id):
    d = compare(G, apply_upgrade(G, by_id["U7"]), personas, before)
    assert d.index_delta == pytest.approx(0.0, abs=1e-9)
    assert "no measurable change" in d.explanation
