"""Folium maps rendered once to static HTML and cached (fix pack F3).

Every map is display-only, so instead of the bidirectional `st_folium` component we render the Folium map to an
HTML string, cache it keyed by everything that changes the picture, and show it with `components.html`.
"""
from __future__ import annotations

import html
import json
from typing import Iterable

import folium
import networkx as nx
import streamlit as st
import streamlit.components.v1 as components

from accesstwin.core.graph import build_graph, find_edge, iter_edges, load_township
from accesstwin.core.personas import Persona, load_personas
from accesstwin.core.routing import edge_passable

# V2 plan-view palette (accesstwin/ui/theme.py tokens). Every status also has a non-colour cue:
# recorded = solid warm grey, blocked = solid red + ✖, unverified = grey dashed,
# impassable for the selected profile = thin dotted red, selected segment = copper with dark outline.
STATUS_COLOURS = {"verified_accessible": "#A9A595", "blocked": "#A63429", "unverified": "#687064"}
STATUS_DASH = {"verified_accessible": None, "blocked": None, "unverified": "6 8"}
IMPASSABLE_COLOUR, IMPASSABLE_DASH = "#A63429", "2 6"
SELECTED_COLOUR, SELECTED_OUTLINE = "#B75D37", "#5C2A16"
UPGRADED_COLOUR = "#B75D37"
REFERENCE_COLOUR, DETOUR_COLOUR = "#B75D37", "#526E70"
MAP_BACKGROUND = "#E9ECE1"
CATEGORY_COLOURS = {"clinic": "#8E4326", "bus_stop": "#526E70", "school": "#5D5A8C", "grocery": "#765818", "park": "#345F4C"}


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
    selected: str = "",
    street: bool = False,
) -> folium.Map:
    """Plan view: no tiles by default, the walkway graph drawn like a drawing on paper (plan §4.3)."""
    lats = [float(d["lat"]) for _, d in G.nodes(data=True)]
    lons = [float(d["lon"]) for _, d in G.nodes(data=True)]
    m = folium.Map(location=[sum(lats) / len(lats), sum(lons) / len(lons)], zoom_start=zoom,
                   tiles="OpenStreetMap" if street else None, control_scale=street, scrollWheelZoom=False,
                   prefer_canvas=True)
    # Same bounds for every view of the scene: all nodes of the base network (Baseline and Scenario share them).
    m.fit_bounds([[min(lats), min(lons)], [max(lats), max(lons)]], padding=(28, 28))
    if not street:
        m.get_root().header.add_child(folium.Element(
            "<style>.leaflet-container{background:" + MAP_BACKGROUND + " !important;font-family:'Segoe UI',Arial,sans-serif}</style>"))
    highlight = set(highlight_edges)

    for edge in iter_edges(G):
        status = edge.get("status", "unverified")
        colour = STATUS_COLOURS.get(status, "#687064")
        why = None
        weight, opacity = 6, 0.95
        dash = STATUS_DASH.get(status)
        if persona is not None and status != "blocked":
            ok, why = edge_passable(edge, persona, include_unverified)
            if not ok and status != "unverified":
                colour, weight, dash = IMPASSABLE_COLOUR, 3, IMPASSABLE_DASH  # impassable for this profile
        line = edge_line(G, edge)
        if edge["id"] == selected:
            folium.PolyLine(line, color=SELECTED_OUTLINE, weight=13, opacity=0.9).add_to(m)
            colour, weight, opacity, dash = SELECTED_COLOUR, 8, 1.0, None
        elif edge["id"] in highlight:
            folium.PolyLine(line, color=SELECTED_OUTLINE, weight=12, opacity=0.6).add_to(m)
            colour, weight, opacity, dash = UPGRADED_COLOUR, 8, 1.0, None
        folium.PolyLine(line, color=colour, weight=weight, opacity=opacity, dash_array=dash,
                        tooltip=_edge_tooltip(edge, why)).add_to(m)
        if status == "blocked":  # non-colour cue for blocked segments
            folium.map.Marker(edge_midpoint(G, edge), tooltip=f"{edge['id']}: blocked", icon=folium.DivIcon(
                html="<div style='font-size:15px;line-height:15px;color:#A63429;font-weight:900;"
                     "text-shadow:0 0 2px #fff,0 0 2px #fff'>✖</div>")).add_to(m)
        if show_ids:
            folium.map.Marker(edge_midpoint(G, edge), icon=folium.DivIcon(
                html=f"<div style='font-size:9px;color:#374151;font-weight:600'>{edge['id']}</div>")).add_to(m)

    for nid, d in G.nodes(data=True):
        loc = [float(d["lat"]), float(d["lon"])]
        if d.get("type") == "residential":
            folium.CircleMarker(loc, radius=7, color="#394338", weight=2, fill=True, fill_color="#FBFBF8", fill_opacity=1,
                                tooltip=f"{d['name']} · pop {d.get('population')} · vulnerable {d.get('vulnerable_share', 0):.0%}").add_to(m)
            _label(m, loc, d["name"], nid)
        elif d.get("type") == "destination":
            c = CATEGORY_COLOURS.get(d.get("category"), "#586151")
            folium.CircleMarker(loc, radius=6, color="#242824", weight=1.5, fill=True, fill_color=c, fill_opacity=0.95,
                                tooltip=f"{d['name']} ({d.get('category', '').replace('_', ' ')})").add_to(m)
            _label(m, loc, d["name"], nid)
        else:
            folium.CircleMarker(loc, radius=3, color="#586151", fill=True, tooltip=d.get("name", nid)).add_to(m)

    for r in pending_reports:
        edge = find_edge(G, r["edge_id"])
        if edge is None:
            continue
        folium.CircleMarker(edge_midpoint(G, edge), radius=8, color="#765818", weight=2, fill=True, fill_color="#FBFBF8",
                            fill_opacity=1, tooltip=f"Pending report #{r['id']} on {r['edge_id']}: {r.get('type', '?')}").add_to(m)
    return m


def _label_offsets() -> dict:
    try:
        from accesstwin import config

        with open(config.DATA_DIR / "display_names.json", encoding="utf-8") as f:
            return json.load(f).get("node_label_offsets", {})
    except (OSError, ValueError):
        return {}


def _label(m: folium.Map, loc, text: str, node_id: str = "") -> None:
    dx, dy = _label_offsets().get(node_id, [0, 0])
    folium.map.Marker(loc, icon=folium.DivIcon(icon_size=(160, 16), icon_anchor=(-9 - dx, 7 - dy), html=(
        "<div style='font-size:12px;letter-spacing:.3px;color:#2F382A;white-space:nowrap;"
        "text-shadow:0 0 3px #E9ECE1,0 0 3px #E9ECE1,0 0 3px #E9ECE1'>" + html.escape(str(text)) + "</div>"))).add_to(m)


def add_barrier_marker(m: folium.Map, G: nx.MultiGraph, edge_id: str, label: str) -> None:
    """Outlined "!" barrier marker with a readable label (selected segment)."""
    e = find_edge(G, edge_id)
    if not e:
        return
    folium.map.Marker(edge_midpoint(G, e), tooltip=label, icon=folium.DivIcon(icon_size=(220, 26), icon_anchor=(11, 34),
        html=("<div style='display:flex;align-items:center;gap:6px'>"
              "<span style='display:inline-grid;place-items:center;width:20px;height:20px;border:2px solid #A63429;"
              "border-radius:50%;background:#FBFBF8;color:#A63429;font-weight:800;font-size:13px'>!</span>"
              "<span style='background:#FAF9F4;border:1px solid #D8D2C6;padding:2px 6px;font-size:12px;color:#242824;"
              "white-space:nowrap'>" + html.escape(label) + "</span></div>"))).add_to(m)


def add_legend(m: folium.Map, items: list, caption: str = "Fictional layout · not to scale") -> None:
    """Legend inside the map frame. items = [(css border-top style, label)]."""
    rows = "".join("<span style='display:inline-flex;align-items:center;gap:6px;margin-right:12px'>"
                   "<i style='display:inline-block;width:20px;border-top:" + style + "'></i>" + html.escape(lb) + "</span>"
                   for style, lb in items)
    m.get_root().html.add_child(folium.Element(
        "<div style='position:absolute;left:12px;bottom:12px;z-index:9999;background:rgba(249,249,244,.95);"
        "border:1px solid #D8DDD0;padding:8px 10px;font:13px Segoe UI,Arial,sans-serif;color:#2F382A;max-width:90%'>"
        + rows + "<div style='margin-top:4px;color:#586151'>" + html.escape(caption) + "</div></div>"))


def _tag(m: folium.Map, loc, text: str, border: str, colour: str = "#242824") -> None:
    folium.map.Marker(loc, icon=folium.DivIcon(icon_size=(240, 24), icon_anchor=(-8, 30), html=(
        "<span style='background:#FAF9F4;border:1px solid " + border + ";padding:2px 6px;font:12.5px Segoe UI,Arial,"
        "sans-serif;color:" + colour + ";white-space:nowrap'>" + html.escape(text) + "</span>"))).add_to(m)


def add_route(m: folium.Map, G: nx.MultiGraph, path: list[str], colour: str, dashed: bool, label: str,
              faded: bool = False) -> None:
    if len(path) < 2:
        return
    coords = [_coords(G, n) for n in path]
    if faded:  # previous route in a scenario view: thin, light, labelled on the map itself
        folium.PolyLine(coords, color=colour, weight=4, opacity=0.85, dash_array="4 8", tooltip=label).add_to(m)
        _tag(m, coords[len(coords) // 2], label, "#C9C5B9", "#5E5A50")
        return
    folium.PolyLine(coords, color=colour, weight=7 if not dashed else 5, opacity=0.9,
                    dash_array="10 10" if dashed else None, tooltip=label).add_to(m)


def add_proposed(m: folium.Map, G: nx.MultiGraph, edge_id: str, label: str) -> None:
    """Amber halo under the simulated upgrade plus an on-map callout."""
    e = find_edge(G, edge_id)
    if not e:
        return
    folium.PolyLine([_coords(G, e["from"]), _coords(G, e["to"])], color="#E8A33D", weight=20, opacity=0.55,
                    tooltip=label).add_to(m)
    _tag(m, edge_midpoint(G, e), label, "#E8A33D", "#7A3E1F")


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
    selected: str = "",
    selected_label: str = "",
    street: bool = False,
    legend_key: str = "",
    proposed_label: str = "",
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
    m = base_map(G, persona, include_unverified, json.loads(highlight_key), json.loads(pending_key), show_ids, zoom,
                 selected=selected, street=street)
    highlights = json.loads(highlight_key)
    if proposed_label and highlights:
        add_proposed(m, G, highlights[0], proposed_label)
    for path, colour, dashed, label, *rest in json.loads(routes_key):
        add_route(m, G, path, colour, dashed, label, faded=bool(rest and rest[0]))
    for edge_id, radius, colour, tooltip in json.loads(circles_key):
        e = find_edge(G, edge_id)
        if e:
            folium.CircleMarker(edge_midpoint(G, e), radius=radius, color=colour, fill=True, fill_opacity=0.35,
                                tooltip=tooltip).add_to(m)
    if selected and selected_label:
        add_barrier_marker(m, G, selected, selected_label)
    if legend_key:
        add_legend(m, [tuple(x) for x in json.loads(legend_key)])
    return m.get_root().render()


def pending_key(reports: list[dict]) -> str:
    return json.dumps([{"id": r["id"], "edge_id": r["edge_id"],
                        "type": (r.get("ai") or {}).get("obstacle_type", "?")} for r in reports])


def show_map(height: int = 480, **keys) -> None:
    """Display a cached static map. `keys` are passed straight to `map_html`."""
    components.html(map_html(**keys), height=height)


def legend() -> str:
    from accesstwin.ui.i18n import t

    return t("legend")


LEGEND_MD = legend()  # English default for non-UI callers; pages call legend()
