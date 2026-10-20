import json

import streamlit as st

from accesstwin.core import store
from accesstwin.core.graph import destination_nodes, node_name, residential_nodes
from accesstwin.core.routing import route
from accesstwin.ui import components as ui
from accesstwin.ui import guide
from accesstwin.ui.i18n import t
from accesstwin.ui.map_view import LEGEND_MD, pending_key, show_map


@st.fragment
def planner(persona) -> None:
    """Pickers + map + result card rerun on their own, without re-running the whole page."""
    G = ui.graph()
    res_nodes = residential_nodes(G)
    dest_nodes = destination_nodes(G)
    c1, c2, c3 = st.columns([1, 1, 1])
    origin = c1.selectbox(t("origin"), [n["id"] for n in res_nodes], format_func=lambda i: node_name(G, i), key="rp_origin")
    dest_ids = [n["id"] for n in dest_nodes]
    dest = c2.selectbox(
        t("destination"), dest_ids, index=dest_ids.index("D_CLINIC") if "D_CLINIC" in dest_ids else 0,
        format_func=lambda i: f"{node_name(G, i)} ({G.nodes[i].get('category')})", key="rp_dest",
    )
    with c3:
        st.write("")
        include_unverified = st.toggle(t("include_unverified"), value=False, key="rp_unverified")

    r = route(G, origin, dest, persona, include_unverified=include_unverified)

    left, right = st.columns([3, 2])
    with left:
        routes = [[r.baseline_path, "#2563EB", True, f"Shortest route (any persona): {ui.fmt_m(r.baseline_length_m)}"]]
        if r.reachable:
            routes.append([r.path, "#7C3AED", False, f"{persona.label} route: {ui.fmt_m(r.length_m)}"])
        show_map(height=520, overlay_key=ui.overlay_key(), persona_key=persona.key, include_unverified=include_unverified,
                 routes_key=json.dumps(routes), pending_key=pending_key(store.list_reports("pending")),
                 show_ids=st.session_state.get("show_ids", False))
        st.caption(LEGEND_MD)
        st.caption(t("unverified_notice"))

    with right:
        st.subheader(ui.persona_label(persona.key))
        if not r.reachable:
            ui.card("🚫 Not reachable for this persona", f"<b>Blocking segment:</b> {r.reason}<br>"
                    "No alternative path satisfies this persona's rules.", "bad")
        else:
            if not r.direct_reachable:
                ui.card("⚠️ Direct route not usable", f"<b>Blocking segment:</b> {r.reason}<br>"
                        f"A detour exists, {r.detour_ratio:.1f}× the shortest distance.", "warn")
            elif r.edges == r.baseline_edges:
                ui.card("✅ Direct route usable", "This persona can use the shortest route.", "good")
            else:
                ui.card("✅ Reachable", "A slightly different path is preferred (comfort penalties such as no shade or no tactile paving).", "good")
            a, b = st.columns(2)
            a.metric("Distance", ui.fmt_m(r.length_m), delta=f"+{ui.fmt_m(r.length_m - r.baseline_length_m)}" if r.length_m > r.baseline_length_m else None, delta_color="inverse")
            b.metric("Detour ratio", f"{r.detour_ratio:.2f}×")
            a.metric("Covered (shade/rain)", f"{r.covered_ratio:.0%}")
            b.metric("Unverified segments", len(r.unverified_edges))
            if not r.within_max_trip:
                st.warning(f"Route is longer than this persona's comfortable max trip ({ui.fmt_m(persona.max_trip_m)}).")
            if r.unverified_edges:
                st.warning("Route uses unverified segments: " + ", ".join(r.unverified_edges) + " — check on site before relying on it.")
            st.caption("Path: " + " → ".join(node_name(G, n) for n in r.path))
        st.caption(f"Shortest route (any persona): {ui.fmt_m(r.baseline_length_m)} via {', '.join(r.baseline_edges)}")

        with st.expander("Compare all personas for this trip"):
            rows = []
            for key, p in ui.personas().items():
                rr = route(G, origin, dest, p, include_unverified=include_unverified)
                rows.append({
                    "persona": ui.persona_label(key),
                    "direct route": "✅" if rr.direct_reachable else "❌",
                    "reachable": "✅" if rr.reachable else "❌",
                    "distance": ui.fmt_m(rr.length_m) if rr.reachable else "—",
                    "detour": f"{rr.detour_ratio:.2f}×" if rr.reachable else "—",
                    "reason": rr.reason or "",
                })
            st.dataframe(rows, hide_index=True, width="stretch")


def main() -> None:
    ui.setup_page(t("route_title"), "🧭")
    persona = ui.sidebar()
    st.title(f"🧭 {t('route_title')}")
    guide.panel("pages/1_🧭_Route_Planner.py")
    st.caption("Same origin and destination, different reachability per persona. Dashed = unconstrained shortest route; "
               "solid = route this persona can actually use.")
    planner(persona)
    ui.disclaimer()


ui.run_page(main)
