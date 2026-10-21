import json

import streamlit as st

from accesstwin.core import store
from accesstwin.core.graph import destination_nodes, node_name, residential_nodes
from accesstwin.core.routing import route
from accesstwin.ui import components as ui
from accesstwin.ui import guide
from accesstwin.ui.i18n import t
from accesstwin.ui.map_view import DETOUR_COLOUR, REFERENCE_COLOUR, legend, pending_key, show_map


def _set_persona() -> None:
    v = st.session_state["rp_persona"]
    st.session_state["persona"] = v
    st.session_state["persona_select"] = v


def _report_on(edge_id: str) -> None:
    guide.queue_presets({"ro_edge": edge_id})


def _blocking_edge(r) -> str | None:
    """Segment id of the first blocking reason on the shortest reference path (reasons start with the id)."""
    for why in (r.baseline_blockers or []) + ([r.reason] if r.reason else []):
        eid = str(why).split(":", 1)[0].strip()
        if eid:
            return eid
    return None


@ui.fragment
def planner(persona) -> None:
    """Profile + trip pickers inline, conclusion first, then map, then the report action (2A-3)."""
    G = ui.graph()
    res_nodes = residential_nodes(G)
    dest_nodes = destination_nodes(G)
    keys = list(ui.personas())
    conclusion = st.container()  # conclusion first (2A-3); filled once the pickers below are read
    st.session_state["rp_persona"] = persona.key
    st.segmented_control(t("persona"), keys, key="rp_persona", format_func=ui.persona_short, on_change=_set_persona,
                         help=t("persona_assumption"))
    c1, c2, c3 = st.columns([1, 1, 1], vertical_alignment="bottom")
    origin = c1.selectbox(t("origin"), [n["id"] for n in res_nodes], format_func=lambda i: node_name(G, i), key="rp_origin")
    dest_ids = [n["id"] for n in dest_nodes]
    dest = c2.selectbox(
        t("destination"), dest_ids, index=dest_ids.index("D_CLINIC") if "D_CLINIC" in dest_ids else 0,
        format_func=lambda i: f"{node_name(G, i)} ({G.nodes[i].get('category', '').replace('_', ' ')})", key="rp_dest",
    )
    include_unverified = c3.toggle(t("include_unverified"), value=False, key="rp_unverified")

    r = route(G, origin, dest, persona, include_unverified=include_unverified)
    who = ui.persona_short(persona.key)

    # ---- conclusion first
    if not r.reachable:
        status, cls, body = (f"No passable route for {who}", "blocked",
                             f"Blocking: {r.reason}. No alternative path satisfies this profile's rules.")
    elif not r.direct_reachable:
        status, cls, body = (f"Detour needed · {ui.fmt_m(r.length_m)}", "blocked",
                             f"The shortest reference path ({ui.fmt_m(r.baseline_length_m)}) is interrupted: "
                             f"{'; '.join(r.baseline_blockers) or r.reason}. The usable route is "
                             f"{r.detour_ratio:.1f}× the reference.")
    elif r.edges == r.baseline_edges:
        status, cls, body = (f"Direct route usable · {ui.fmt_m(r.length_m)}", "verified",
                             f"{who} can use the shortest reference path.")
    else:
        status, cls, body = (f"Route usable · {ui.fmt_m(r.length_m)}", "verified",
                             "A slightly different path is preferred (comfort penalties such as no shade or no tactile paving).")
    conclusion.markdown(f"<div class='at-route-head'><div class='at-eyebrow'>{ui.esc(who)} · {ui.esc(node_name(G, origin))} → "
                        f"{ui.esc(node_name(G, dest))}</div><div class='at-status {cls}' style='font-size:20px;font-weight:600'>"
                        f"{ui.esc(status)}</div><div style='margin-top:4px;font-size:15px'>{ui.esc(body)}</div></div>",
                        unsafe_allow_html=True)
    eid = _blocking_edge(r) or (r.edges[0] if r.edges else None)
    if eid:
        conclusion.button(f"Report an obstacle on this route ({eid})", key="rp_report", type="primary",
                          on_click=_report_on, args=(eid,))
        if st.session_state.get("guide_pending", {}).get("ro_edge") == eid:
            conclusion.page_link("pages/2_📸_Report_Obstacle.py", label="Open the report form →")
    if r.reachable:
        facts = [("Distance", ui.fmt_m(r.length_m)), ("Reference path", ui.fmt_m(r.baseline_length_m)),
                 ("Covered (shade/rain)", f"{r.covered_ratio:.0%}"), ("Unverified segments", str(len(r.unverified_edges)))]
        st.markdown("<div class='at-grid4'>" + "".join(
            f"<div><div class='at-muted'>{ui.esc(k)}</div><div class='at-big' style='font-size:20px'>{ui.esc(v)}</div></div>"
            for k, v in facts) + "</div>", unsafe_allow_html=True)
        if not r.within_max_trip:
            st.warning(f"Longer than this profile's comfortable trip ({ui.fmt_m(persona.max_trip_m)}).")
        if r.unverified_edges:
            st.warning("Uses unverified segments: " + ", ".join(r.unverified_edges) + " — check on site before relying on it.")

    # ---- map
    routes = [[r.baseline_path, REFERENCE_COLOUR, False, f"Shortest reference path: {ui.fmt_m(r.baseline_length_m)}"]]
    if r.reachable and r.path != r.baseline_path:
        routes.append([r.path, DETOUR_COLOUR, True, f"{who} route: {ui.fmt_m(r.length_m)}"])
    show_map(height=520, key_nodes_key=json.dumps([origin, dest]), overlay_key=ui.overlay_key(), persona_key=persona.key,
             include_unverified=include_unverified,
             routes_key=json.dumps(routes), pending_key=pending_key(store.list_reports("pending")),
             show_ids=st.session_state.get("show_ids", False))
    st.caption(legend())
    st.caption(t("unverified_notice"))
    if r.reachable:
        st.caption("Path: " + " → ".join(node_name(G, n) for n in r.path))


    with st.expander("Compare all profiles for this trip"):
        rows = []
        for key, p in ui.personas().items():
            rr = route(G, origin, dest, p, include_unverified=include_unverified)
            rows.append({
                "profile": ui.persona_short(key),
                "direct route": "usable" if rr.direct_reachable else "interrupted",
                "reachable": "yes" if rr.reachable else "no",
                "distance": ui.fmt_m(rr.length_m) if rr.reachable else "—",
                "detour": f"{rr.detour_ratio:.2f}×" if rr.reachable else "—",
                "reason": rr.reason or "",
            })
        st.dataframe(rows, hide_index=True, width="stretch")


def main() -> None:
    ui.setup_page(t("route_title"), "🧭")
    persona = ui.sidebar()
    ui.page_head(t('route_title'), eyebrow="Resident · Plan a trip")
    guide.panel("pages/1_🧭_Route_Planner.py")
    st.caption("Same origin and destination, different reachability per profile.")
    r1, r2, _ = st.columns([1, 1, 3])
    with r1:
        ui.page_link("pages/2_📸_Report_Obstacle.py", label=f"{t('res_report')} →")
    with r2:
        ui.page_link("pages/10_Track_Report.py", label=f"{t('res_track')} →")
    planner(persona)
    ui.disclaimer()


ui.run_page(main)
