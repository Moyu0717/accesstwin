"""Validate the demo data files against ACCESSTWIN_BUILD_SPEC.md section 4.

Run with: python -m accesstwin.core.validate
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import networkx as nx

from accesstwin.config import (
    PERSONAS_PATH,
    PHOTOS_DIR,
    SAMPLE_REPORTS_PATH,
    TOWNSHIP_PATH,
    UPGRADES_PATH,
)

SURFACES = {"good", "cracked", "broken", "gravel"}
STATUSES = {"verified_accessible", "blocked", "unverified"}
COST_TIERS = {"low", "medium", "high"}
REPORT_ROLES = {"resident", "guard"}
REPORT_STATUSES = {"pending", "approved"}
NODE_TYPES = {"residential", "destination", "junction"}

NODE_KEYS = {"id": str, "name": str, "type": str, "lat": (int, float), "lon": (int, float)}
RESIDENTIAL_KEYS = {"population": (int, float), "vulnerable_share": (int, float)}
DESTINATION_KEYS = {"category": str, "importance": (int, float)}

EDGE_KEYS = {
    "id": str, "from": str, "to": str, "length_m": (int, float),
    "surface": str, "has_step": bool, "curb_height_cm": (int, float),
    "max_slope_pct": (int, float), "width_cm": (int, float),
    "tactile_paving": bool, "covered": bool, "lit_at_night": bool,
    "status": str,
}  # cctv_id is str or None, checked separately

PERSONA_KEYS = {
    "label", "allow_step", "max_curb_cm", "max_slope_pct", "min_width_cm",
    "bad_surfaces", "max_trip_m", "prefers_covered", "needs_tactile", "equity_weight",
}

CATEGORY_IMPORTANCE = {
    "clinic": 1.0,
    "bus_stop": 0.9,
    "school": 0.8,
    "grocery": 0.7,
    "park": 0.5,
}

UPGRADE_KEYS = {"id": str, "title": str, "cost_tier": str, "design_mode_only": bool, "rationale": str}

REPORT_KEYS = {
    "id": str, "edge_id": str, "reporter_role": str, "photo": str,
    "obstacle_type": str, "note": str, "status": str,
}


def _load(path: Path, errors: list[str]):
    if not path.exists():
        errors.append(f"missing file: {path.name}")
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"cannot parse {path.name}: {exc}")
        return None


def _check_types(obj: dict, spec: dict, where: str, errors: list[str]) -> None:
    for key, typ in spec.items():
        if key not in obj:
            errors.append(f"{where}: missing key '{key}'")
        elif not isinstance(obj[key], typ):
            errors.append(f"{where}: key '{key}' has wrong type")


def _check_edge_fields(edge: dict, where: str, errors: list[str]) -> None:
    _check_types(edge, EDGE_KEYS, where, errors)
    if "cctv_id" not in edge:
        errors.append(f"{where}: missing key 'cctv_id'")
    elif edge["cctv_id"] is not None and not isinstance(edge["cctv_id"], str):
        errors.append(f"{where}: 'cctv_id' must be a string or null")
    if edge.get("surface") is not None and edge.get("surface") not in SURFACES:
        errors.append(f"{where}: surface '{edge.get('surface')}' not allowed")
    if edge.get("status") is not None and edge.get("status") not in STATUSES:
        errors.append(f"{where}: status '{edge.get('status')}' not allowed")


def _check_township(data, errors: list[str]) -> tuple[list[dict], list[dict]]:
    if not isinstance(data, dict):
        errors.append("township.json: top level must be an object")
        return [], []
    meta = data.get("meta", {})
    for key in ("name", "crs", "fictional"):
        if key not in meta:
            errors.append(f"township.json: meta missing '{key}'")

    nodes = data.get("nodes", [])
    edges = data.get("edges", [])
    if not isinstance(nodes, list) or not isinstance(edges, list):
        errors.append("township.json: 'nodes' and 'edges' must be lists")
        return [], []

    if not 14 <= len(nodes) <= 18:
        errors.append(f"township.json: {len(nodes)} nodes (expected 14-18)")
    if not 20 <= len(edges) <= 26:
        errors.append(f"township.json: {len(edges)} edges (expected 20-26)")

    node_ids: set[str] = set()
    for i, node in enumerate(nodes):
        where = f"node[{i}]"
        if not isinstance(node, dict):
            errors.append(f"{where}: must be an object")
            continue
        _check_types(node, NODE_KEYS, where, errors)
        nid = node.get("id")
        if isinstance(nid, str):
            where = f"node {nid}"
            if nid in node_ids:
                errors.append(f"{where}: duplicate node id")
            node_ids.add(nid)
        ntype = node.get("type")
        if ntype not in NODE_TYPES:
            errors.append(f"{where}: type '{ntype}' not allowed")
        if ntype == "residential":
            _check_types(node, RESIDENTIAL_KEYS, where, errors)
        elif ntype == "destination":
            _check_types(node, DESTINATION_KEYS, where, errors)

    residential = [n for n in nodes if isinstance(n, dict) and n.get("type") == "residential"]
    if not any(isinstance(n.get("vulnerable_share"), (int, float)) and n["vulnerable_share"] >= 0.4
               for n in residential):
        errors.append("township.json: no residential node with vulnerable_share >= 0.4")

    destinations = {n.get("category"): n for n in nodes
                    if isinstance(n, dict) and n.get("type") == "destination"}
    for cat, imp in CATEGORY_IMPORTANCE.items():
        if cat not in destinations:
            errors.append(f"township.json: missing destination category '{cat}'")
        elif destinations[cat].get("importance") != imp:
            errors.append(f"township.json: '{cat}' importance should be {imp}")

    edge_ids: set[str] = set()
    for i, edge in enumerate(edges):
        where = f"edge[{i}]"
        if not isinstance(edge, dict):
            errors.append(f"{where}: must be an object")
            continue
        _check_edge_fields(edge, where, errors)
        eid = edge.get("id")
        if isinstance(eid, str):
            where = f"edge {eid}"
            if eid in edge_ids:
                errors.append(f"{where}: duplicate edge id")
            edge_ids.add(eid)
        for end in ("from", "to"):
            if edge.get(end) not in node_ids:
                errors.append(f"{where}: '{end}' node '{edge.get(end)}' does not exist")

    unverified = sum(1 for e in edges if isinstance(e, dict) and e.get("status") == "unverified")
    blocked = sum(1 for e in edges if isinstance(e, dict) and e.get("status") == "blocked")
    with_cctv = sum(1 for e in edges if isinstance(e, dict) and e.get("cctv_id"))
    if unverified < 3:
        errors.append(f"township.json: {unverified} unverified edges (need >= 3)")
    # Fix pack X2: barriers come from approved obstacle reports, not from a closed status in the base data.
    if blocked < 1 and not _seed_has_approved_obstruction():
        errors.append("township.json: no blocked edge and no approved obstruction report in the seed")
    if with_cctv < 3:
        errors.append(f"township.json: {with_cctv} edges with cctv_id (need >= 3)")

    _check_storyline(nodes, edges, errors)
    return nodes, edges


def _seed_has_approved_obstruction() -> bool:
    try:
        with open(SAMPLE_REPORTS_PATH, encoding="utf-8") as f:
            seeds = json.load(f)
    except (OSError, ValueError):
        return False
    return any(r.get("status") == "approved" and r.get("obstacle_type") in ("blocked_ramp", "narrow_path", "flooding")
               for r in seeds)


def _check_storyline(nodes: list[dict], edges: list[dict], errors: list[str]) -> None:
    by_id = {e["id"]: e for e in edges if isinstance(e, dict) and "id" in e}
    if "E7" not in by_id:
        errors.append("storyline: edge E7 missing")
        return

    def build(filter_fn) -> nx.Graph:
        g = nx.Graph()
        g.add_nodes_from(n["id"] for n in nodes if isinstance(n, dict) and "id" in n)
        for e in edges:
            if not isinstance(e, dict) or not filter_fn(e):
                continue
            if e.get("from") in g and e.get("to") in g:
                g.add_edge(e["from"], e["to"], weight=e["length_m"], eid=e["id"])
        return g

    def path_edge_ids(g: nx.Graph, path: list[str]) -> list[str]:
        return [g[a][b]["eid"] for a, b in zip(path, path[1:])]

    full = build(lambda e: True)
    try:
        route_a = nx.shortest_path(full, "R1", "D_CLINIC", weight="weight")
    except nx.NetworkXNoPath:
        errors.append("storyline: no path R1 -> D_CLINIC")
        return
    a_edges = path_edge_ids(full, route_a)
    if "E7" not in a_edges:
        errors.append(f"storyline: shortest R1 -> D_CLINIC {a_edges} does not contain E7")
    e7 = by_id["E7"]
    if e7.get("has_step") is not True or e7.get("curb_height_cm") != 15:
        errors.append("storyline: E7 must have has_step true and curb_height_cm 15")
    path_cctv = [eid for eid in a_edges if by_id.get(eid, {}).get("cctv_id")]
    if not path_cctv:
        errors.append("storyline: no cctv edge on the shortest R1 -> D_CLINIC path")
    len_a = sum(by_id[eid]["length_m"] for eid in a_edges if eid in by_id)

    def accessible(e: dict) -> bool:
        return (not e.get("has_step")
                and e.get("status") not in {"unverified", "blocked"}
                and e.get("surface") not in {"broken", "gravel"})

    avoid = build(accessible)
    try:
        route_b = nx.shortest_path(avoid, "R1", "D_CLINIC", weight="weight")
    except nx.NetworkXNoPath:
        errors.append("storyline: no accessible route R1 -> D_CLINIC (Route B)")
        return
    len_b = sum(by_id[eid]["length_m"] for eid in path_edge_ids(avoid, route_b))
    if len_b < 2 * len_a:
        errors.append(f"storyline: Route B {len_b} m is less than 2x Route A {len_a} m")


def _check_personas(data, errors: list[str]) -> None:
    if not isinstance(data, dict):
        errors.append("personas.json: top level must be an object")
        return
    for name, persona in data.items():
        if not isinstance(persona, dict):
            errors.append(f"persona {name}: must be an object")
            continue
        missing = PERSONA_KEYS - set(persona)
        if missing:
            errors.append(f"persona {name}: missing keys {sorted(missing)}")


def _check_upgrades(data, edge_ids: set[str], node_ids: set[str], errors: list[str]) -> None:
    if not isinstance(data, list):
        errors.append("upgrades.json: top level must be a list")
        return
    if not 6 <= len(data) <= 8:
        errors.append(f"upgrades.json: {len(data)} candidates (expected 6-8)")
    seen: set[str] = set()
    for i, up in enumerate(data):
        where = f"upgrade[{i}]"
        if not isinstance(up, dict):
            errors.append(f"{where}: must be an object")
            continue
        _check_types(up, UPGRADE_KEYS, where, errors)
        uid = up.get("id")
        if isinstance(uid, str):
            where = f"upgrade {uid}"
            if uid in seen:
                errors.append(f"{where}: duplicate id")
            seen.add(uid)
        if up.get("cost_tier") not in COST_TIERS:
            errors.append(f"{where}: cost_tier '{up.get('cost_tier')}' not allowed")
        has_edge = "edge_id" in up
        has_new = "new_edge" in up
        if has_edge == has_new:
            errors.append(f"{where}: needs exactly one of edge_id or new_edge")
        if has_edge:
            if up["edge_id"] not in edge_ids:
                errors.append(f"{where}: edge_id '{up['edge_id']}' does not exist")
            if not isinstance(up.get("changes"), dict) or not up["changes"]:
                errors.append(f"{where}: 'changes' must be a non-empty object")
        if has_new:
            ne = up["new_edge"]
            if not isinstance(ne, dict):
                errors.append(f"{where}: new_edge must be an object")
                continue
            _check_edge_fields(ne, f"{where} new_edge", errors)
            if ne.get("id") in edge_ids:
                errors.append(f"{where}: new_edge id '{ne.get('id')}' clashes with an existing edge")
            for end in ("from", "to"):
                if ne.get(end) not in node_ids:
                    errors.append(f"{where}: new_edge '{end}' node '{ne.get(end)}' does not exist")


def _check_reports(data, edge_ids: set[str], errors: list[str]) -> None:
    if not isinstance(data, list):
        errors.append("sample_reports.json: top level must be a list")
        return
    if not 4 <= len(data) <= 6:
        errors.append(f"sample_reports.json: {len(data)} reports (expected 4-6)")
    seen: set[str] = set()
    for i, rep in enumerate(data):
        where = f"report[{i}]"
        if not isinstance(rep, dict):
            errors.append(f"{where}: must be an object")
            continue
        _check_types(rep, REPORT_KEYS, where, errors)
        rid = rep.get("id")
        if isinstance(rid, str):
            where = f"report {rid}"
            if rid in seen:
                errors.append(f"{where}: duplicate id")
            seen.add(rid)
        if rep.get("edge_id") not in edge_ids:
            errors.append(f"{where}: edge_id '{rep.get('edge_id')}' does not exist")
        if rep.get("reporter_role") not in REPORT_ROLES:
            errors.append(f"{where}: reporter_role '{rep.get('reporter_role')}' not allowed")
        if rep.get("status") not in REPORT_STATUSES:
            errors.append(f"{where}: status '{rep.get('status')}' not allowed")
        photo = rep.get("photo")
        if isinstance(photo, str) and not (PHOTOS_DIR / photo).is_file():
            errors.append(f"{where}: photo '{photo}' not found in {PHOTOS_DIR.name}/")


def validate_all() -> list[str]:
    errors: list[str] = []
    township = _load(TOWNSHIP_PATH, errors)
    personas = _load(PERSONAS_PATH, errors)
    upgrades = _load(UPGRADES_PATH, errors)
    reports = _load(SAMPLE_REPORTS_PATH, errors)

    nodes: list[dict] = []
    edges: list[dict] = []
    if township is not None:
        nodes, edges = _check_township(township, errors)
    edge_ids = {e.get("id") for e in edges if isinstance(e, dict)}
    node_ids = {n.get("id") for n in nodes if isinstance(n, dict)}

    if personas is not None:
        _check_personas(personas, errors)
    if upgrades is not None:
        _check_upgrades(upgrades, edge_ids, node_ids, errors)
    if reports is not None:
        _check_reports(reports, edge_ids, errors)
    return errors


def main() -> int:
    errors = validate_all()
    for err in errors:
        print(f"ERROR: {err}")
    if errors:
        print(f"FAILED: {len(errors)} error(s)")
        return 1
    print("OK: township, personas, upgrades and sample reports are valid and the storyline holds")
    return 0


if __name__ == "__main__":
    sys.exit(main())
