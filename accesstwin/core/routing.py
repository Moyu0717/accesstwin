"""Persona filtering + shortest path (spec section 5.1)."""
from __future__ import annotations

from dataclasses import dataclass, field

import networkx as nx

from accesstwin import config
from accesstwin.core.graph import iter_edges
from accesstwin.core.personas import Persona


def edge_passable(edge: dict, persona: Persona, include_unverified: bool = False) -> tuple[bool, str | None]:
    """Return (passable, reason). The reason names the edge and the specific cause."""
    eid = edge["id"]
    status = edge.get("status", "unverified")
    if status == "blocked":
        return False, f"{eid}: closed (explicit full closure)"
    for ob in edge.get("obstacles", []) or []:
        if ob.get("kind") == "obstruction" and persona.key in ob.get("personas", []):
            return False, f"{eid}: {ob.get('text', ob.get('type'))} (report #{ob.get('report_id')})"
    if status == "unverified" and not include_unverified:
        return False, f"{eid}: unverified — pending on-site verification"
    curb = float(edge.get("curb_height_cm", 0) or 0)
    if edge.get("has_step") and not persona.allow_step:
        return False, f"{eid}: step {curb:g} cm > {persona.label.lower()} limit {persona.max_curb_cm:g} cm"
    if curb > persona.max_curb_cm:
        kind = "step" if edge.get("has_step") else "curb"
        return False, f"{eid}: {kind} {curb:g} cm > {persona.label.lower()} limit {persona.max_curb_cm:g} cm"
    slope = float(edge.get("max_slope_pct", 0) or 0)
    if slope > persona.max_slope_pct:
        return False, f"{eid}: slope {slope:g}% > {persona.label.lower()} limit {persona.max_slope_pct:g}%"
    width = float(edge.get("width_cm", 999) or 999)
    if width < persona.min_width_cm:
        return False, f"{eid}: width {width:g} cm < {persona.label.lower()} minimum {persona.min_width_cm:g} cm"
    surface = edge.get("surface", "good")
    if surface in persona.bad_surfaces:
        return False, f"{eid}: {surface} surface unsuitable for {persona.label.lower()}"
    return True, None


def edge_cost(edge: dict, persona: Persona) -> float:
    """Base = length_m, plus persona penalties (uncovered +30%, no tactile +50%, cracked +20%)."""
    factor = 1.0
    if persona.prefers_covered and not edge.get("covered"):
        factor += config.PENALTY_UNCOVERED
    if persona.needs_tactile and not edge.get("tactile_paving"):
        factor += config.PENALTY_NO_TACTILE
    if edge.get("surface") == "cracked":
        factor += config.PENALTY_CRACKED
    return float(edge["length_m"]) * factor


def persona_subgraph(G: nx.MultiGraph, persona: Persona, include_unverified: bool = False) -> nx.MultiGraph:
    H = nx.MultiGraph(**G.graph)
    H.add_nodes_from(G.nodes(data=True))
    for edge in iter_edges(G):
        ok, _ = edge_passable(edge, persona, include_unverified)
        if ok:
            H.add_edge(edge["from"], edge["to"], key=edge["id"], **edge, cost=edge_cost(edge, persona))
    return H


@dataclass
class RouteResult:
    origin: str
    dest: str
    persona: str
    reachable: bool
    path: list[str] = field(default_factory=list)
    edges: list[str] = field(default_factory=list)
    length_m: float = 0.0
    cost: float = 0.0
    unverified_edges: list[str] = field(default_factory=list)
    covered_ratio: float = 0.0
    reason: str | None = None
    baseline_path: list[str] = field(default_factory=list)
    baseline_edges: list[str] = field(default_factory=list)
    baseline_length_m: float = 0.0
    detour_ratio: float | None = None
    within_max_trip: bool = False
    baseline_blockers: list[str] = field(default_factory=list)
    direct_reachable: bool = False  # can this persona use the unconstrained shortest route?


def _shortest(G: nx.MultiGraph, origin: str, dest: str, weight: str) -> tuple[list[str], list[dict]] | None:
    """Dijkstra on a MultiGraph; returns node path and the chosen (cheapest) parallel edges."""
    simple = nx.Graph()
    simple.add_nodes_from(G.nodes)
    for u, v, data in G.edges(data=True):
        w = float(data[weight])
        if not simple.has_edge(u, v) or w < simple[u][v]["w"]:
            simple.add_edge(u, v, w=w, data=data)
    try:
        path = nx.dijkstra_path(simple, origin, dest, weight="w")
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None
    return path, [simple[a][b]["data"] for a, b in zip(path, path[1:])]


def baseline_route(G: nx.MultiGraph, origin: str, dest: str) -> tuple[list[str], list[dict]] | None:
    """Unconstrained shortest path by length (all edges, any status)."""
    return _shortest(G, origin, dest, "length_m")


def route(
    G: nx.MultiGraph, origin: str, dest: str, persona: Persona, include_unverified: bool = False
) -> RouteResult:
    res = RouteResult(origin=origin, dest=dest, persona=persona.key, reachable=False)
    base = baseline_route(G, origin, dest)
    if base:
        res.baseline_path = base[0]
        res.baseline_edges = [e["id"] for e in base[1]]
        res.baseline_length_m = sum(float(e["length_m"]) for e in base[1])
        for e in base[1]:
            ok, why = edge_passable(e, persona, include_unverified)
            if not ok:
                res.baseline_blockers.append(why)
        res.direct_reachable = not res.baseline_blockers
        # Even when a detour exists, `reason` explains why the direct route fails (e.g. "E7: step ...").
        res.reason = res.baseline_blockers[0] if res.baseline_blockers else None

    if origin == dest:
        res.reachable, res.path, res.within_max_trip, res.detour_ratio = True, [origin], True, 1.0
        res.direct_reachable, res.reason = True, None
        return res

    found = _shortest(persona_subgraph(G, persona, include_unverified), origin, dest, "cost")
    if not found:
        if not base:
            res.reason = "No path exists in the network between these points."
        elif not res.baseline_blockers:
            res.reason = "No passable path for this persona."
        return res

    path, edges = found
    res.reachable = True
    res.path = path
    res.edges = [e["id"] for e in edges]
    res.length_m = sum(float(e["length_m"]) for e in edges)
    res.cost = sum(float(e["cost"]) for e in edges)
    res.unverified_edges = [e["id"] for e in edges if e.get("status") == "unverified"]
    covered = sum(float(e["length_m"]) for e in edges if e.get("covered"))
    res.covered_ratio = covered / res.length_m if res.length_m else 0.0
    res.detour_ratio = res.length_m / res.baseline_length_m if res.baseline_length_m else 1.0
    res.within_max_trip = res.length_m <= persona.max_trip_m
    return res
