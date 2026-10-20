"""Compare — Baseline vs the selected location's proposed upgrade (session-only scenario, never saved)."""
import json

import streamlit as st

from accesstwin.ui import cached
from accesstwin.ui import components as ui
from accesstwin.ui import guide
from accesstwin.ui import workspace as ws
from accesstwin.ui.i18n import t
from accesstwin.ui.map_view import DETOUR_COLOUR, REFERENCE_COLOUR, show_map

PAGE = "pages/8_Compare.py"


def main() -> None:
    ui.setup_page(t("stage_compare"), "♿")
    persona = ui.sidebar()
    ws.project_bar("compare")
    guide.panel(PAGE)
    okey = ui.overlay_key()
    c = ws.ctx()
    loc = ws.find_location(okey, c["segment"])
    if loc is None:
        st.info("No priority location to compare.")
        return
    c["segment"] = loc.edge_id
    st.markdown(f"<div class='at-eyebrow' style='display:flex;justify-content:space-between'>"
                f"<span>{ws.esc(t('compare_title'))} / 01</span><span class='at-chip sim'>Simulated</span></div>",
                unsafe_allow_html=True)
    if not loc.upgrade:
        st.markdown(f"<div class='at-h2'>{ws.esc(loc.label)} · no proposal yet</div>", unsafe_allow_html=True)
        st.info(f"{loc.label} ({loc.edge_id}) needs on-site inspection first — {t('not_assessed')}. "
                "No scenario is modelled, so there is nothing to compare.")
        ws.status_bar(False, cached.data_version(okey))
        return
    up = loc.upgrade
    st.markdown(f"<div class='at-h2'>{ws.esc(loc.label)} · {ws.esc(up['title'])}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='at-sub'>The same journey and the same map extent, with one change at {ws.esc(loc.edge_id)}. "
                "Compare the route and its modelled effect.</div>", unsafe_allow_html=True)

    left, right = st.columns([2.3, 1], gap="medium")
    with left:
        view = st.radio("Map view", ["Baseline", "Scenario"], horizontal=True, key="cmp_view",
                        format_func=lambda v: "01 · Baseline" if v == "Baseline" else "02 · Scenario (Simulated)")
        ids = (up["id"],) if view == "Scenario" else ()
        routes, legend = [], []
        if loc.origin and loc.dest:
            r = cached.journey(okey, ids, loc.origin, loc.dest, persona.key)
            ref_label = "Shortest reference path — interrupted" if not r.direct_reachable else "Shortest reference path"
            routes.append([r.baseline_path, REFERENCE_COLOUR, False, ref_label])
            legend.append([f"3px solid {REFERENCE_COLOUR}", ref_label])
            if r.reachable and r.path != r.baseline_path:
                routes.append([r.path, DETOUR_COLOUR, True, "Accessible detour"])
                legend.append([f"3px dashed {DETOUR_COLOUR}", "Accessible detour"])
            journey_txt = (ws._len_txt(r.length_m) if r.reachable else "no passable route")
        else:
            journey_txt = "—"
        show_map(height=440, overlay_key=okey, persona_key=persona.key, routes_key=json.dumps(routes),
                 upgrades_key=json.dumps(list(ids)), highlight_key=json.dumps([loc.edge_id] if ids else []),
                 selected="" if ids else loc.edge_id, selected_label="" if ids else f"{loc.label} · {loc.edge_id}",
                 legend_key=json.dumps(legend))
        st.caption(f"{'Simulated' if ids else 'Available'} journey ({ui.persona_short(persona.key)}): {journey_txt}. "
                   "Both views use the same map extent.")
    with right:
        st.markdown("<span class='at-ws-score'></span>", unsafe_allow_html=True)
        d, text = cached.scenario(okey, (up["id"],))
        st.markdown(f"<div class='at-eyebrow'>{ws.esc(t('access_score'))} · Simulated</div>"
                    f"<div class='at-score'>{d.index_after:.1f}<small> /100</small></div>"
                    f"<div class='at-sub'>{d.index_delta:+.1f} points vs baseline {d.index_before:.1f}</div>",
                    unsafe_allow_html=True)
        st.markdown(f"<div class='at-section at-muted'>{ws.esc(text)}</div>", unsafe_allow_html=True)
        st.button(f"View {up['id']} on the network ↗", key="cmp_view_on_network", type="primary",
                  use_container_width=True, on_click=lambda: c.update(scenario=(up["id"],)))
        ws._page_link("pages/0_🏠_Overview.py", "Open Network")
        ws._page_link("pages/5_🏗️_Upgrade_Simulator.py", "All upgrades, packages & work orders")

    st.markdown(ws.rows_table_html(ws.compare_rows(okey, loc, persona.key)), unsafe_allow_html=True)
    st.caption("Scenario values are modelled on synthetic demo data. Site measurements and an engineering review are "
               "required before delivery. Nothing here changes the recorded network.")
    ws.status_bar(True, cached.data_version(okey))
    ui.disclaimer()


ui.run_page(main)
