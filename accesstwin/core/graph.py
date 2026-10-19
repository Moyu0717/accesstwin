"""Load township.json into a NetworkX MultiGraph (base JSON + optional SQLite overlay)."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Iterator

import networkx as nx

from accesstwin import config

EDGE_DEFAULTS: dict[str, Any] = {
    "surface": "good",
    "has_step": False,
    "curb_height_cm": 0,
    "max_slope_pct": 0,
    "width_cm": 150,
    "tactile_paving": False,
    "covered": False,
    "lit_at_night": True,
    "status": "unverified",
    "cctv_id": None,
}


def load_township(path: Path | str | None = None) -> dict:
    with open(path or config.TOWNSHIP_PATH, encoding="utf-8") as f:
        return json.load(f)


def build_graph(data: dict, overlay: dict[str, dict] | None = None) -> nx.MultiGraph:
    """Build the graph. `overlay` maps edge_id -> attribute changes (never written back to JSON)."""
    G = nx.MultiGraph(meta=data.get("meta", {}))
    for node in data["nodes"]:
        G.add_node(node["id"], **node)
    for raw in data["edges"]:
        add_edge(G, raw)
    if overlay:
        for edge_id, changes in overlay.items():
            set_edge_attrs(G, edge_id, changes)
    return G


def add_edge(G: nx.MultiGraph, raw: dict) -> None:
    attrs = {**EDGE_DEFAULTS, **copy.deepcopy(raw)}
    G.add_edge(attrs["from"], attrs["to"], key=attrs["id"], **attrs)


def load_graph(with_overlay: bool = True, path: Path | str | None = None) -> nx.MultiGraph:
    """Graph at load time = base JSON + SQLite overlay (section 5.7)."""
    overlay = None
    if with_overlay:
        from accesstwin.core import store  # local import: store is optional for pure-logic callers

        overlay = store.get_overlay()
    return build_graph(load_township(path), overlay)


def iter_edges(G: nx.MultiGraph) -> Iterator[dict]:
    for _u, _v, _k, data in G.edges(keys=True, data=True):
        yield data


def find_edge(G: nx.MultiGraph, edge_id: str) -> dict | None:
    for data in iter_edges(G):
        if data["id"] == edge_id:
            return data
    return None


def set_edge_attrs(G: nx.MultiGraph, edge_id: str, changes: dict) -> bool:
    for u, v, k in G.edges(keys=True):
        if k == edge_id:
            G.edges[u, v, k].update(changes)
            return True
    return False


def residential_nodes(G: nx.MultiGraph) -> list[dict]:
    return [d for _, d in G.nodes(data=True) if d.get("type") == "residential"]


def destination_nodes(G: nx.MultiGraph, category: str | None = None) -> list[dict]:
    return [
        d
        for _, d in G.nodes(data=True)
        if d.get("type") == "destination" and (category is None or d.get("category") == category)
    ]


def categories(G: nx.MultiGraph) -> dict[str, float]:
    """category -> importance (max importance among destinations of that category)."""
    out: dict[str, float] = {}
    for d in destination_nodes(G):
        out[d["category"]] = max(out.get(d["category"], 0.0), float(d.get("importance", 0.5)))
    return out


def node_name(G: nx.MultiGraph, node_id: str) -> str:
    return G.nodes[node_id].get("name", node_id) if node_id in G else node_id
