"""Accessibility Gap Index tests (spec sections 5.2 and 7, M3)."""
from __future__ import annotations

import pytest

from accesstwin.core.graph import build_graph, load_township
from accesstwin.core.personas import load_personas
from accesstwin.core.scoring import compute_scores, detour_penalty, pair_score


@pytest.fixture(scope="module")
def G():
    return build_graph(load_township())


@pytest.fixture(scope="module")
def personas():
    return load_personas()


@pytest.fixture(scope="module")
def result(G, personas):
    return compute_scores(G, personas)


# ---------- detour penalty ----------


def test_detour_penalty_no_detour_is_zero():
    assert detour_penalty(1.0) == 0


def test_detour_penalty_double_is_half():
    assert detour_penalty(2.0) == pytest.approx(0.5)


def test_detour_penalty_capped_at_one():
    assert detour_penalty(5.0) == 1


def test_detour_penalty_none_is_one():
    assert detour_penalty(None) == 1.0


# ---------- township / persona index ----------


def test_index_within_0_to_100(result):
    assert 0.0 <= result.index <= 100.0


def test_persona_index_has_all_four_personas(result):
    assert set(result.persona_index) == {"wheelchair", "elderly", "stroller", "visually_impaired"}
    for v in result.persona_index.values():
        assert 0.0 <= v <= 100.0


def test_wheelchair_index_below_elderly_index(result):
    assert result.persona_index["wheelchair"] < result.persona_index["elderly"]


# ---------- gap matrix and unreachable pairs ----------


def test_gap_matrix_shape_is_4x4(G, result):
    df = result.gap_matrix(G)
    assert df.shape == (4, 4)


def test_unreachable_pairs_non_empty(result):
    assert len(result.unreachable_pairs) > 0


def test_unreachable_pairs_include_wheelchair_grocery(result):
    hits = [p for p in result.unreachable_pairs if p.category == "grocery" and p.persona == "wheelchair"]
    assert hits, "expected wheelchair grocery gap (E12 broken + E20 blocked)"


# ---------- pair score: R1 -> clinic, wheelchair ----------


def test_pair_score_r1_wheelchair_clinic_reachable(G, personas):
    ps = pair_score(G, "R1", personas["wheelchair"], "clinic")
    assert ps.reachable is True
    assert ps.reach == 1.0


def test_pair_score_r1_wheelchair_clinic_detour_ratio(G, personas):
    ps = pair_score(G, "R1", personas["wheelchair"], "clinic")
    assert ps.detour_ratio == pytest.approx(1100 / 450, rel=0.01)
