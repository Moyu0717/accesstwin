"""Folium maps rendered once to static HTML and cached (fix pack F3).

Every map is display-only, so instead of the bidirectional `st_folium` component we render the Folium map to an
HTML string, cache it keyed by everything that changes the picture, and show it with `components.html`.
"""
from __future__ import annotations

import json
from typing import Iterable

import folium
import networkx as nx
import streamlit as st
import streamlit.components.v1 as components

from accesstwin.core.graph import build_graph, find_edge, iter_edges, load_township
from accesstwin.core.personas import Persona, load_personas
from accesstwin.core.routing import edge_passable

# Colour-blind-safe (Okabe–Ito) palette, and every status also has a non-colour cue:
# verified = solid blue, blocked = solid vermillion + ✖ marker, unverified = grey dashed,
# impassable for the selected persona = thin dotted vermillion.
STATUS_COLOURS = {"verified_accessible": "#0072B2", "blocked": "#D55E00", "unverified": "#8C8C8C"}
STATUS_DASH = {"verified_accessible": None, "blocked": None, "unverified": "6 8"}
IMPASSABLE_COLOUR, IMPASSABLE_DASH = "#D55E00", "2 6"
CATEGORY_COLOURS = {"clinic": "#DC2626", "bus_stop": "#1D4ED8", "school": "#7C3AED", "grocery": "#EA580C", "park": "#15803D"}


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
    show_ids: bool = False,
    zoom: int = 16,
) -> folium.Map:
    lats = [float(d["lat"]) for _, d in G.nodes(data=True)]
    lons = [float(d["lon"]) for _, d in G.nodes(data=True)]
    m = folium.Map(location=[sum(lats) / len(lats), sum(lons) / len(lons)], zoom_start=zoom,
                   tiles="OpenStreetMap", control_scale=True, scrollWheelZoom=False, prefer_canvas=True)
    m.fit_bounds([[min(lats), min(lons)], [max(lats), max(lons)]], padding=(20, 20))
    highlight = set(highlight_edges)

    for edge in iter_edges(G):
        status = edge.get("status", "unverified")
        colour = STATUS_COLOURS.get(status, "#9CA3AF")
        why = None
        weight, opacity = 5, 0.9
        dash = STATUS_DASH.get(status)
        if persona is not None and status != "blocked":
            ok, why = edge_passable(edge, persona, include_unverified)
            if not ok and status != "unverified":
                colour, weight, dash = IMPASSABLE_COLOUR, 3, IMPASSABLE_DASH  # impassable for this persona
        if edge["id"] in highlight:
            weight, opacity, colour = 9, 1.0, "#F59E0B"
        folium.PolyLine(edge_line(G, edge), color=colour, weight=weight, opacity=opacity, dash_array=dash,
                        tooltip=_edge_tooltip(edge, why)).add_to(m)
        if status == "blocked":  # non-colour cue for blocked segments
            folium.map.Marker(edge_midpoint(G, edge), tooltip=f"{edge['id']}: blocked", icon=folium.DivIcon(
                html="<div style='font-size:15px;line-height:15px;color:#D55E00;font-weight:900;"
                     "text-shadow:0 0 2px #fff,0 0 2px #fff'>✖</div>")).add_to(m)
        if show_ids:
            folium.map.Marker(edge_midpoint(G, edge), icon=folium.DivIcon(
                html=f"<div style='font-size:9px;color:#374151;font-weight:600'>{edge['id']}</div>")).add_to(m)

    for nid, d in G.nodes(data=True):
        loc = [float(d["lat"]), float(d["lon"])]
        if d.get("type") == "residential":
            folium.CircleMarker(loc, radius=8, color="#0E7490", weight=2, fill=True, fill_color="#67E8F9", fill_opacity=0.9,
                                tooltip=f"🏠 {d['name']} · pop {d.get('population')} · vulnerable {d.get('vulnerable_share', 0):.0%}").add_to(m)
        elif d.get("type") == "destination":
            c = CATEGORY_COLOURS.get(d.get("category"), "#6B7280")
            folium.CircleMarker(loc, radius=9, color="#111827", weight=2, fill=True, fill_color=c, fill_opacity=0.95,
                                tooltip=f"📍 {d['name']} ({d.get('category', '').replace('_', ' ')})").add_to(m)
        else:
            folium.CircleMarker(loc, radius=3, color="#374151", fill=True, tooltip=d.get("name", nid)).add_to(m)

    for r in pending_reports:
        edge = find_edge(G, r["edge_id"])
        if edge is None:
            continue
        folium.CircleMarker(edge_midpoint(G, edge), radius=9, color="#EA580C", fill=True, fill_color="#FB923C",
                            fill_opacity=0.9, tooltip=f"Pending report #{r['id']} on {r['edge_id']}: {r.get('type', '?')}").add_to(m)
    return m


def add_route(m: folium.Map, G: nx.MultiGraph, path: list[str], colour: str, dashed: bool, label: str) -> None:
    if len(path) < 2:
        return
    folium.PolyLine([_coords(G, n) for n in path], color=colour, weight=7 if not dashed else 5, opacity=0.9,
                    dash_array="10 10" if dashed else None, tooltip=label).add_to(m)


@st.cache_data(max_entries=64, show_spinner=False)
def map_html(
    overlay_key: str,
    persona_key: str | None = None,
    include_unverified: bool = False,
    routes_key: str = "[]",
    highlight_key: str = "[]",
    pending_key: str = "[]",
    upgrades_key: str = "[]",
    circles_key: str = "[]",
    show_ids: bool = False,
    zoom: int = 16,
) -> str:
    """Render a map to a standalone HTML string. All arguments are hashable keys (JSON strings), never objects.

    routes_key:   [[path(list of node ids), colour, dashed(bool), label], ...]
    pending_key:  [{"id", "edge_id", "type"}, ...]
    upgrades_key: [upgrade ids] applied (simulated) before drawing
    circles_key:  [[edge_id, radius, colour, tooltip], ...]
    """
    G = build_graph(load_township(), json.loads(overlay_key) or None)
    upgrade_ids = json.loads(upgrades_key)
    if upgrade_ids:
        from accesstwin.core.simulation import apply_upgrades, load_upgrades

        by_id = {u["id"]: u for u in load_upgrades()}
        G = apply_upgrades(G, [by_id[i] for i in upgrade_ids if i in by_id])
    persona = load_personas()[persona_key] if persona_key else None
    m = base_map(G, persona, include_unverified, json.loads(highlight_key), json.loads(pending_key), show_ids, zoom)
    for path, colour, dashed, label in json.loads(routes_key):
        add_route(m, G, path, colour, dashed, label)
    for edge_id, radius, colour, tooltip in json.loads(circles_key):
        e = find_edge(G, edge_id)
        if e:
            folium.CircleMarker(edge_midpoint(G, e), radius=radius, color=colour, fill=True, fill_opacity=0.35,
                                tooltip=tooltip).add_to(m)
    return m.get_root().render()


def pending_key(reports: list[dict]) -> str:
    return json.dumps([{"id": r["id"], "edge_id": r["edge_id"],
                        "type": (r.get("ai") or {}).get("obstacle_type", "?")} for r in reports])


def show_map(height: int = 480, **keys) -> None:
    """Display a cached static map. `keys` are passed straight to `map_html`."""
    components.html(map_html(**keys), height=height)


LEGEND_MD = (
    "**Segments:** solid blue = verified accessible · solid orange-red with ✖ = blocked · grey dashed = unverified · "
    "thin dotted orange-red = impassable for the selected persona · amber thick = upgraded (simulator). "
    "**Points:** light-blue circles = homes · coloured circles = destinations (hover for the name) · "
    "orange dot = pending report."
)
