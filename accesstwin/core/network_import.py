"""Design mode: import a draft walkway network from two CSV files (P1-4).

nodes.csv    id,name,type,lat,lon,population,vulnerable_share,category,importance
segments.csv id,from,to,length_m,surface,has_step,curb_height_cm,max_slope_pct,width_cm,
             tactile_paving,covered,lit_at_night,status,cctv_id

Structural rules come from validate.py (types, allowed values, unique ids, endpoints). The demo-only storyline
checks (node counts, Route A, ...) do not apply to imported networks. Nothing is persisted.
"""
from __future__ import annotations

import csv
import io

from accesstwin import config
from accesstwin.core.validate import (
    DESTINATION_KEYS, EDGE_KEYS, NODE_KEYS, NODE_TYPES, RESIDENTIAL_KEYS, STATUSES, SURFACES, _check_types,
)

SAMPLE_DIR = config.DATA_DIR / "sample_network"
NODE_COLUMNS = ["id", "name", "type", "lat", "lon", "population", "vulnerable_share", "category", "importance"]
SEGMENT_COLUMNS = ["id", "from", "to", "length_m", "surface", "has_step", "curb_height_cm", "max_slope_pct",
                   "width_cm", "tactile_paving", "covered", "lit_at_night", "status", "cctv_id"]
_NUM = {"lat", "lon", "population", "vulnerable_share", "importance", "length_m", "curb_height_cm",
        "max_slope_pct", "width_cm"}
_BOOL = {"has_step", "tactile_paving", "covered", "lit_at_night"}
_TRUE, _FALSE = {"true", "1", "yes", "y"}, {"false", "0", "no", "n", ""}


def _coerce(row: dict, where: str, errors: list[str]) -> dict:
    out: dict = {}
    for k, v in row.items():
        if k is None:
            continue
        k, v = k.strip(), (v or "").strip()
        if k in _NUM:
            if v == "":
                continue
            try:
                out[k] = float(v) if "." in v or "e" in v.lower() else int(v)
            except ValueError:
                errors.append(f"{where}: '{k}' must be a number (got '{v}')")
        elif k in _BOOL:
            if v.lower() in _TRUE:
                out[k] = True
            elif v.lower() in _FALSE:
                out[k] = False
            else:
                errors.append(f"{where}: '{k}' must be true/false (got '{v}')")
        else:
            out[k] = v or None
    return out


def parse_network(nodes_csv: str, segments_csv: str, name: str = "Imported draft network") -> tuple[dict, list[str]]:
    """Return (township dict, errors). An empty error list means the network can be analysed."""
    errors: list[str] = []
    nodes = [_coerce(r, f"nodes.csv row {i + 2}", errors) for i, r in enumerate(csv.DictReader(io.StringIO(nodes_csv)))]
    edges = [_coerce(r, f"segments.csv row {i + 2}", errors) for i, r in enumerate(csv.DictReader(io.StringIO(segments_csv)))]
    if not nodes:
        errors.append("nodes.csv: no rows")
    if not edges:
        errors.append("segments.csv: no rows")

    ids: set[str] = set()
    for n in nodes:
        where = f"node {n.get('id')}"
        _check_types(n, NODE_KEYS, where, errors)
        if n.get("id") in ids:
            errors.append(f"{where}: duplicate id")
        ids.add(n.get("id"))
        if n.get("type") not in NODE_TYPES:
            errors.append(f"{where}: type '{n.get('type')}' not allowed ({', '.join(sorted(NODE_TYPES))})")
        elif n["type"] == "residential":
            _check_types(n, RESIDENTIAL_KEYS, where, errors)
        elif n["type"] == "destination":
            _check_types(n, DESTINATION_KEYS, where, errors)
    if not any(n.get("type") == "residential" for n in nodes):
        errors.append("nodes.csv: needs at least one residential node")
    if not any(n.get("type") == "destination" for n in nodes):
        errors.append("nodes.csv: needs at least one destination node")

    seg_ids: set[str] = set()
    for e in edges:
        where = f"segment {e.get('id')}"
        e.setdefault("cctv_id", None)
        e.setdefault("status", "unverified")
        _check_types(e, EDGE_KEYS, where, errors)
        if e.get("id") in seg_ids:
            errors.append(f"{where}: duplicate id")
        seg_ids.add(e.get("id"))
        if e.get("surface") not in SURFACES:
            errors.append(f"{where}: surface '{e.get('surface')}' not allowed ({', '.join(sorted(SURFACES))})")
        if e.get("status") not in STATUSES:
            errors.append(f"{where}: status '{e.get('status')}' not allowed")
        for end in ("from", "to"):
            if e.get(end) not in ids:
                errors.append(f"{where}: '{end}' node '{e.get(end)}' does not exist")
    data = {"meta": {"name": name, "crs": "WGS84", "fictional": True}, "nodes": nodes, "edges": edges}
    return data, errors


def sample_csvs() -> tuple[str, str]:
    return ((SAMPLE_DIR / "nodes.csv").read_text(encoding="utf-8"),
            (SAMPLE_DIR / "segments.csv").read_text(encoding="utf-8"))


def template_csvs() -> tuple[str, str]:
    return ",".join(NODE_COLUMNS) + "\n", ",".join(SEGMENT_COLUMNS) + "\n"
