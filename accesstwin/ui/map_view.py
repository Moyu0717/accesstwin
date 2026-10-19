"""Folium layers: segment colours, routes, report markers (spec section 6 colour rules)."""
from __future__ import annotations

from typing import Iterable

import folium
import networkx as nx

from accesstwin.core.graph import iter_edges
from accesstwin.core.personas import Persona
from accesstwin.core.routing import edge_passable

STATUS_COLOURS = {"verified_accessible": "#16A34A", "blocked": "#DC2626", "unverified": "#9CA3AF"}
CATEGORY_ICONS = {
    "clinic": ("plus-sign", "red"),
    "bus_stop": ("road", "darkblue"),
    "school": ("book", "purple"),
    "grocery": ("shopping-cart", "orange"),
    "park": ("tree-conifer", "green"),
}


def _coords(G: nx.MultiGraph, node_id: str) -> tuple[float, float]:
    n = G.nodes[node_id]
    return float(n["lat"]), float(n["lon"])


def edge_line(G: nx.MultiGraph, edge: dict) -> list[tuple[float, float]]:
    return [_coords(G, edge["from"]), _coords(G, edge["to"])]


def edge_midpoint(G: nx.MultiGraph, edge: dict) -> tuple[float, float]:
    (a, b), (c, d) = edge_line(G, edge)
    return (a + c) / 2, (b + d) / 2


def _edge_tooltip(edge: dict, why: str | None) -> str:
    bits = [
        f"<b>{edge['id']}</b> · {edge['length_m']} m · {edge.get('status')}",
        f"surface {edge.get('surface')}, curb {edge.get('curb_height_cm')} cm, slope {edge.get('max_slope_pct')}%",
        f"{'covered' if edge.get('covered') else 'uncovered'}, {'lit' if edge.get('lit_at_night') else 'unlit at night'}"
        f"{', tactile' if edge.get('tactile_paving') else ''}{', step' if edge.get('has_step') else ''}",
    ]
    if edge.get("cctv_id"):
        bits.append(f"📹 {edge['cctv_id']}")
    if why:
        bits.append(f"<span style='color:#DC2626'>✖ {why}</span>")
    return "<br>".join(bits)


def base_map(
    G: nx.MultiGraph,
    persona: Persona | None = None,
    include_unverified: bool = False,
    highlight_edges: Iterable[str] = (),
    pending_reports: Iterable[dict] = (),
    zoom: int = 16,
) -> folium.Map:
    lats = [float(d["lat"]) for _, d in G.nodes(data=True)]
    lons = [float(d["lon"]) for _, d in G.nodes(data=True)]
    m = folium.Map(location=[sum(lats) / len(lats), sum(lons) / len(lons)], zoom_start=zoom,
                   tiles="OpenStreetMap", control_scale=True)
    highlight = set(highlight_edges)

    for edge in iter_edges(G):
        status = edge.get("status", "unverified")
        colour = STATUS_COLOURS.get(status, "#9CA3AF")
        why = None
        weight, dash, opacity = 5, None, 0.85
        if status == "unverified":
            dash = "6 8"
        if persona is not None and status != "blocked":
            ok, why = edge_passable(edge, persona, include_unverified)
            if not ok and status != "unverified":
                colour, weight = "#DC2626", 2  # impassable for this persona: thin red
        if edge["id"] in highlight:
            weight, opacity = 9, 1.0
            colour = "#F59E0B"
        folium.PolyLine(
            edge_line(G, edge), color=colour, weight=weight, opacity=opacity, dash_array=dash,
            tooltip=folium.Tooltip(_edge_tooltip(edge, why)),
        ).add_to(m)
        lat, lon = edge_midpoint(G, edge)
        folium.map.Marker(
            [lat, lon],
            icon=folium.DivIcon(html=f"<div style='font-size:9px;color:#374151;font-weight:600'>{edge['id']}</div>"),
        ).add_to(m)

    for nid, d in G.nodes(data=True):
        loc = [float(d["lat"]), float(d["lon"])]
        if d.get("type") == "residential":
            folium.Marker(loc, tooltip=f"{d['name']} · pop {d.get('population')} · vulnerable {d.get('vulnerable_share', 0):.0%}",
                          icon=folium.Icon(color="cadetblue", icon="home")).add_to(m)
        elif d.get("type") == "destination":
            icon, colour = CATEGORY_ICONS.get(d.get("category"), ("star", "gray"))
            folium.Marker(loc, tooltip=f"{d['name']} ({d.get('category')})",
                          icon=folium.Icon(color=colour, icon=icon)).add_to(m)
        else:
            folium.CircleMarker(loc, radius=3, color="#374151", fill=True, tooltip=d.get("name", nid)).add_to(m)

    for r in pending_reports:
        edge = next((e for e in iter_edges(G) if e["id"] == r["edge_id"]), None)
        if edge is None:
            continue
        folium.CircleMarker(
            edge_midpoint(G, edge), radius=9, color="#EA580C", fill=True, fill_color="#FB923C", fill_opacity=0.9,
            tooltip=f"Pending report #{r['id']} on {r['edge_id']}: {r.get('ai', {}).get('obstacle_type', '?')}",
        ).add_to(m)
    return m


def add_route(m: folium.Map, G: nx.MultiGraph, path: list[str], colour: str, dashed: bool, label: str) -> None:
    if len(path) < 2:
        return
    folium.PolyLine(
        [_coords(G, n) for n in path], color=colour, weight=7 if not dashed else 5,
        opacity=0.9, dash_array="10 10" if dashed else None, tooltip=label,
    ).add_to(m)


LEGEND_MD = (
    "🟩 verified accessible &nbsp; 🟥 blocked &nbsp; ⬜ grey dashed = unverified &nbsp; "
    "thin red = impassable for selected persona &nbsp; 🟠 pending report"
)
