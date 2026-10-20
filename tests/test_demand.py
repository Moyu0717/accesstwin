"""Suppressed-demand detection (spec section 5.5, M7)."""
from __future__ import annotations

import pytest

from accesstwin.core import store
from accesstwin.core.demand import suppressed_demand
from accesstwin.core.footfall import camera_counts
from accesstwin.core.graph import build_graph, load_township
from accesstwin.core.personas import load_personas


@pytest.fixture(scope="module")
def G():
    return build_graph(load_township())


@pytest.fixture(scope="module")
def P():
    return load_personas()


@pytest.fixture(scope="module")
def counts():
    store.reset_demo()
    return camera_counts()


@pytest.fixture(scope="module")
def demand(G, P, counts):
    return suppressed_demand(G, P, counts)


def _by_id(rows):
    return {r.edge_id: r for r in rows}


def test_at_least_one_suppressed_edge(demand):
    assert any(d.suppressed for d in demand)


def test_e7_on_route_a_is_suppressed(demand):
    e7 = _by_id(demand)["E7"]
    assert e7.cctv_id == "CAM_02"
    assert e7.suppressed is True
    assert e7.status == "Suppressed demand"
    assert e7.ratio is not None and e7.ratio < 0.4
    assert "E7" in e7.barrier_edges


def test_edges_without_cctv_are_never_inferred(demand):
    uncovered = [d for d in demand if d.cctv_id is None]
    assert uncovered, "demo township should contain edges without CCTV"
    for d in uncovered:
        assert d.status == "No CCTV coverage"
        assert d.observed is None
        assert d.expected is None
        assert d.ratio is None
        assert d.suppressed is False


def test_expected_scaled_to_total_observed(demand):
    covered = [d for d in demand if d.cctv_id and d.observed is not None]
    total_obs = sum(d.observed for d in covered)
    total_exp = sum(d.expected for d in covered)
    assert total_exp == pytest.approx(total_obs, rel=1e-6)


def test_raising_camera_count_clears_suppression(G, P, counts):
    boosted = {**counts, "CAM_02": 2000}
    e7 = _by_id(suppressed_demand(G, P, boosted))["E7"]
    assert e7.suppressed is False
    assert e7.status != "Suppressed demand"


def test_camera_missing_from_observed_has_no_counts(G, P, counts):
    partial = {k: v for k, v in counts.items() if k != "CAM_02"}
    e7 = _by_id(suppressed_demand(G, P, partial))["E7"]
    assert e7.status == "No counts yet"
    assert e7.observed is None
    assert e7.suppressed is False
