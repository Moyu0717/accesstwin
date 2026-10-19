"""Suppressed-demand detection (spec section 5.5).

Gravity model: for every residential → destination pair, the baseline (unconstrained) shortest path gets
expected flow  population_r × importance_d / dist_rd^1.5  on each edge it uses. Expected flows are scaled so
their total equals the total observed count over the CCTV-covered edges. An edge is flagged
**Suppressed demand** when observed / expected < 0.4 AND the edge — or a baseline route through it — has a
barrier (impassable for at least one persona) or an unverified segment. Edges without CCTV are never inferred.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import networkx as nx
import pandas as pd

from accesstwin.core.graph import destination_nodes, iter_edges, residential_nodes
from accesstwin.core.personas import Persona
from accesstwin.core.routing import baseline_route, edge_passable

SUPPRESSION_THRESHOLD = 0.4
DISTANCE_EXPONENT = 1.5


@dataclass
class EdgeDemand:
    edge_id: str
    cctv_id: str | None
    observed: float | None
    expected: float | None
    ratio: float | None
    barrier_edges: list[str] = field(default_factory=list)
    barrier_reasons: list[str] = field(default_factory=list)
    suppressed: bool = False
    status: str = "No CCTV coverage"


def edge_barriers(edge: dict, personas: dict[str, Persona]) -> list[str]:
    """Reasons this edge is a barrier: unverified, or impassable for at least one persona."""
    reasons = []
    if edge.get("status") == "unverified":
        reasons.append(f"{edge['id']}: unverified")
    for p in personas.values():
        ok, why = edge_passable(edge, p, include_unverified=True)
        if not ok:
            reasons.append(why)
    return reasons


def expected_flows(G: nx.MultiGraph) -> tuple[dict[str, float], dict[str, list[list[str]]]]:
    """Raw (unscaled) gravity flow per edge id, plus the baseline routes (edge-id lists) through each edge."""
    flows: dict[str, float] = {}
    routes: dict[str, list[list[str]]] = {}
    for r in residential_nodes(G):
        for d in destination_nodes(G):
            base = baseline_route(G, r["id"], d["id"])
            if not base:
                continue
            edges = base[1]
            dist = sum(float(e["length_m"]) for e in edges) or 1.0
            w = float(r.get("population", 0)) * float(d.get("importance", 0.5)) / dist ** DISTANCE_EXPONENT
            ids = [e["id"] for e in edges]
            for eid in ids:
                flows[eid] = flows.get(eid, 0.0) + w
                routes.setdefault(eid, []).append(ids)
    return flows, routes


def suppressed_demand(G: nx.MultiGraph, personas: dict[str, Persona], observed: dict[str, float]) -> list[EdgeDemand]:
    """`observed` maps cctv_id → pedestrian count (e.g. footfall.camera_counts())."""
    raw, routes = expected_flows(G)
    edges = {e["id"]: e for e in iter_edges(G)}
    covered = [e for e in edges.values() if e.get("cctv_id") and e["cctv_id"] in observed]
    total_obs = sum(float(observed[e["cctv_id"]]) for e in covered)
    total_raw = sum(raw.get(e["id"], 0.0) for e in covered)
    scale = total_obs / total_raw if total_raw else 0.0

    out: list[EdgeDemand] = []
    for eid, e in edges.items():
        cam = e.get("cctv_id")
        if not cam or cam not in observed:
            out.append(EdgeDemand(eid, cam, None, None, None,
                                  status="No CCTV coverage" if not cam else "Camera has no counts yet"))
            continue
        obs = float(observed[cam])
        exp = raw.get(eid, 0.0) * scale
        ratio = obs / exp if exp else None
        barrier_ids, reasons = [], []
        for eid2 in dict.fromkeys([eid] + [x for route in routes.get(eid, []) for x in route]):
            why = edge_barriers(edges[eid2], personas)
            if why:
                barrier_ids.append(eid2)
                reasons.extend(why)
        suppressed = ratio is not None and ratio < SUPPRESSION_THRESHOLD and bool(barrier_ids)
        if ratio is None:
            status = "Not on any shortest route (no expected flow)"
        elif suppressed:
            status = "Suppressed demand"
        else:
            status = "Below expected" if ratio < SUPPRESSION_THRESHOLD else "As expected"
        out.append(EdgeDemand(eid, cam, obs, exp, ratio, barrier_ids, list(dict.fromkeys(reasons)), suppressed, status))
    return out


def demand_frame(rows: list[EdgeDemand], covered_only: bool = True) -> pd.DataFrame:
    data = [{
        "edge": r.edge_id, "camera": r.cctv_id or "—", "observed": None if r.observed is None else round(r.observed),
        "expected": None if r.expected is None else round(r.expected),
        "ratio": None if r.ratio is None else round(r.ratio, 2), "status": r.status,
        "barriers on route": ", ".join(r.barrier_edges),
    } for r in rows if (r.cctv_id or not covered_only)]
    return pd.DataFrame(data)
