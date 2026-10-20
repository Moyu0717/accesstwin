"""Network — the V2 planning workspace (priority locations · plan-view map · Inspector).

Everything shown is computed by the core through ui.cached / ui.workspace. "Preview ramp" only changes a
session-only scenario; nothing is written to the database and actual routes are unchanged.
"""
import json
from types import SimpleNamespace

import streamlit as st

from accesstwin.core.graph import node_name
from accesstwin.ui import cached
from accesstwin.ui import components as ui
from accesstwin.ui import guide
from accesstwin.ui import workspace as ws
from accesstwin.ui.i18n import t
from accesstwin.ui.map_view import DETOUR_COLOUR, REFERENCE_COLOUR, show_map

PAGE = "pages/0_🏠_Overview.py"


def _set_scenario(ids: tuple) -> None:
    ws.ctx()["scenario"] = ids


def _fmt_len(m: float) -> tuple[str, str]:
    return (f"{m / 1000:.1f}", "km") if m >= 1000 else (f"{m:.0f}", "m")


def journey_section(loc, okey: str, scenario: tuple, persona) -> tuple:
    """Shortest reference vs available route for the selected profile (baseline or scenario)."""
    base = cached.journey(okey, (), loc.origin, loc.dest, persona.key)
    cur = cached.journey(okey, scenario, loc.origin, loc.dest, persona.key) if scenario else base
    ref_v, ref_u = _fmt_len(cur.baseline_length_m)
    if cur.reachable:
        av_v, av_u = _fmt_len(cur.length_m)
    else:
        av_v, av_u = "—", ""
    ref_note = (t("interrupted") if not cur.direct_reachable else
                ("Available in simulation" if scenario else "Usable for this profile"))
    av_note = ("proposed direct route" if scenario and cur.direct_reachable else
               (f"{cur.detour_ratio:.1f}× the reference" if cur.reachable and cur.detour_ratio else "No passable route"))
    st.markdown(
        f"<div class='at-section'><div class='at-eyebrow'>{ws.esc(ui.persona_short(persona.key))} "
        f"{ws.esc(t('journey_head'))}</div><div class='at-grid2'>"
        f"<div><div class='at-muted'>{ws.esc(t('shortest_reference'))}</div>"
        f"<div class='at-big'>{ref_v} <small>{ref_u}</small></div>"
        f"<div class='at-status {'blocked' if not cur.direct_reachable else 'verified'}' style='font-weight:500'>"
        f"{'✖ ' if not cur.direct_reachable else '✓ '}{ws.esc(ref_note)}</div></div>"
        f"<div><div class='at-muted'>{ws.esc(t('available_route'))}</div>"
        f"<div class='at-big'>{av_v} <small>{av_u}</small></div><div class='at-muted'>{ws.esc(av_note)}</div></div>"
        f"</div></div>", unsafe_allow_html=True)
    return base, cur


def inspector(loc, okey: str, scenario: tuple, persona, G) -> None:
    st.markdown("<span class='at-ws-inspector'></span>", unsafe_allow_html=True)
    st.markdown(f"<div class='at-eyebrow' style='display:flex;justify-content:space-between'>"
                f"<span>{ws.esc(t('location_details'))}</span><span>{ws.esc(loc.edge_id)}</span></div>",
                unsafe_allow_html=True)
    with st.container(key="ws_top_action"):
        action_box(loc, scenario, "top")
    kind_cls = {"barrier": "blocked", "inspection": "pending", "blocked": "blocked"}[loc.kind]
    status = "Proposed scenario" if scenario else loc.status_text
    mark = "◆" if scenario else {"barrier": "●", "inspection": "○", "blocked": "✖"}[loc.kind]
    route_line = (f"{node_name(G, loc.origin)} → {node_name(G, loc.dest)}" if loc.origin and loc.dest else
                  f"{node_name(G, ws.find_edge(G, loc.edge_id)['from'])} → {node_name(G, ws.find_edge(G, loc.edge_id)['to'])}")
    st.markdown(f"<div class='at-status {'sim' if scenario else kind_cls}'>{mark} {ws.esc(status)}</div>"
                f"<div class='at-title'>{ws.esc(loc.label)}</div><div class='at-sub'>{ws.esc(route_line)}</div>",
                unsafe_allow_html=True)
    e = ws.find_edge(G, loc.edge_id)
    if loc.kind == "barrier" and e.get("has_step"):
        st.markdown(ws.step_section_svg(float(e.get("curb_height_cm", 0)), ramp=bool(scenario)), unsafe_allow_html=True)
    st.markdown(f"<div class='at-section'><div class='at-eyebrow'>{ws.esc(t('existing_condition'))}</div>"
                f"<div class='at-big'>{ws.esc(loc.condition_value)} <small>{ws.esc(loc.condition_unit)}</small></div>"
                f"<div class='at-muted'>{ws.esc(loc.condition_text)}</div></div>", unsafe_allow_html=True)
    if loc.kind == "inspection" or not (loc.origin and loc.dest):
        st.markdown(
            f"<div class='at-section'><div class='at-eyebrow'>{ws.esc(ui.persona_short(persona.key))} "
            f"{ws.esc(t('journey_head'))}</div><div class='at-big'>— <small>{ws.esc(t('not_assessed'))}</small></div>"
            f"<div class='at-muted'>No journey impact is estimated until the site record is confirmed.</div></div>"
            f"<div class='at-section'><div class='at-eyebrow'>Profile impact</div>"
            f"<div class='at-muted'>{ws.esc(t('not_assessed'))} — which profiles are affected depends on the site "
            f"inspection.</div></div>", unsafe_allow_html=True)
    else:
        journey_section(loc, okey, scenario, persona)
        tags = "".join(f"<span>{ws.esc(ui.persona_short(k))}</span>" for k in loc.affected) or "<span>None</span>"
        st.markdown(f"<div class='at-section'><div class='at-eyebrow'>{ws.esc(t('affected_profiles'))}</div>"
                    f"<div class='at-tags'>{tags}</div></div>", unsafe_allow_html=True)
    st.markdown(f"<div class='at-section'><div class='at-eyebrow'>{ws.esc(t('evidence_origin'))}</div>"
                f"<div class='at-kv'><span>{ws.esc(t('condition_record'))}</span><b><span class='at-chip syn'>Synthetic</span></b></div>"
                f"<div class='at-kv'><span>Record status</span><span>{ws.esc(e.get('status', '').replace('_', ' '))}</span></div>"
                f"<div class='at-muted' style='font-size:12px'>A recorded status is not a guarantee that every profile can pass.</div>"
                f"</div>", unsafe_allow_html=True)
    action_box(loc, scenario, "bottom")


def action_box(loc, scenario: tuple, where: str) -> None:
    """Main action at the top of the Inspector and repeated at the end (plan §4.2)."""
    st.markdown(f"<div class='at-section' style='border-top:none;padding-top:4px'><div class='at-eyebrow'>"
                f"{ws.esc(t('next_action'))}</div></div>", unsafe_allow_html=True)
    if loc.upgrade:
        up = loc.upgrade
        st.markdown(f"<div style='font-weight:600;font-size:15px'>{ws.esc(up['title'])}</div>"
                    f"<div class='at-muted' style='margin:4px 0 10px'><span class='at-chip'>{ws.esc(up['cost_tier'].capitalize())} cost tier</span></div>",
                    unsafe_allow_html=True)
        if scenario:
            st.button(f"↩ {t('return_baseline')}", key=f"ws_return_{where}", type="primary", use_container_width=True,
                      on_click=_set_scenario, args=((),))
        else:
            st.button(f"{t('preview_ramp') if 'ramp' in up['title'].lower() else 'Preview upgrade'} ↗",
                      key=f"ws_preview_{where}", type="primary", use_container_width=True,
                      on_click=_set_scenario, args=((up["id"],),))
        st.caption(t("sim_only"))
    else:
        st.markdown(f"<div style='font-weight:600;font-size:15px'>{ws.esc(t('confirm_site'))}</div>"
                    f"<div class='at-muted' style='margin:4px 0 10px'><span class='at-chip'>{ws.esc(t('not_estimated'))}</span></div>",
                    unsafe_allow_html=True)
        ws._page_link("pages/3_✅_Verification_Queue.py", f"{t('open_queue')} ↗")
        st.caption("Verify the record before proposing a change.")


def main() -> None:
    ui.setup_page(t("home_title"), "♿")
    persona = ui.sidebar()
    ws.project_bar("network")
    guide.panel(PAGE)
    G = ui.graph()
    okey = ui.overlay_key()
    c = ws.ctx()
    locs = ws.priority_locations(okey)
    if not locs:
        st.info("No priority locations: every profile reaches every destination type with the current data.")
        ui.disclaimer()
        return
    ids = [x.edge_id for x in locs]
    if c["segment"] not in ids:
        c["segment"] = ids[0]
    loc = ws.find_location(okey, c["segment"])
    scenario = tuple(c["scenario"]) if loc.upgrade and tuple(c["scenario"]) == (loc.upgrade["id"],) else ()
    if c["scenario"] and not scenario:
        c["scenario"] = ()

    left, centre, right = st.columns([1, 3.2, 1.3], gap="small")
    with left:
        st.markdown(f"<div class='at-eyebrow'>{ws.esc(t('network_study'))}</div>"
                    f"<div style='font-size:22px;font-weight:500;letter-spacing:-.6px'>{ws.esc(t('assessment_title'))}</div>"
                    f"<div class='at-muted' style='margin:4px 0 10px'>{ws.esc(t('assessment_sub'))}</div>",
                    unsafe_allow_html=True)
        by_id = {x.edge_id: x for x in locs}
        st.radio(t("priority_locations"), ids, key="ws_segment", index=ids.index(c["segment"]),
                 format_func=lambda i: f"{ids.index(i) + 1:02d} · {by_id[i].label} — {i} · {by_id[i].status_text}",
                 on_change=lambda: c.update(segment=st.session_state["ws_segment"], scenario=()))
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        st.markdown("<span class='at-ws-list'></span>", unsafe_allow_html=True)
        base = cached.scores(okey)
        if scenario:
            d, _ = cached.scenario(okey, scenario)
            ws.score_block(SimpleNamespace(index=d.index_after, persona_index=d.persona_after), "Simulated",
                           delta=d.index_delta)
        else:
            ws.score_block(base, "Baseline")
        if not guide.active():
            if st.button(t("guide_start"), key="guide_start", help="A 5-step tour of the whole demo. Exit any time."):
                guide.start()
                st.rerun()

    with centre:
        st.markdown("<span class='at-ws-map'></span>", unsafe_allow_html=True)
        st.markdown(
            f"<div class='at-mobile-only at-muted'>AccessTwin · Demo Township · Study 01</div>"
            f"<div class='at-eyebrow' style='display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap'>"
            f"<span>Demo Township / Access network</span><span><span class='at-chip {'sim' if scenario else ''}'>"
            f"{'Simulated · scenario' if scenario else 'Baseline'}</span> <span class='at-chip syn'>Synthetic</span>"
            f"</span></div><div class='at-h2'>{ws.esc(loc.label)} · "
            f"{'ramp scenario' if scenario else 'existing conditions'}</div>", unsafe_allow_html=True)
        # phones: conclusion + primary action before the map
        st.markdown(f"<div class='at-mobile-only'><div class='at-status {'sim' if scenario else 'blocked'}'>"
                    f"{ws.esc('Proposed scenario' if scenario else loc.status_text)} · {ws.esc(loc.edge_id)} · "
                    f"{ws.esc(loc.condition_value)} {ws.esc(loc.condition_unit)}</div></div>", unsafe_allow_html=True)
        with st.container(key="ws_mobile_action"):
            action_box(loc, scenario, "mobile")
        street = st.toggle(t("street_map"), key="ws_street", value=False,
                           help="Optional OpenStreetMap background. The default plan view needs no tiles.")
        routes, legend = [], []
        if loc.origin and loc.dest:
            cur = cached.journey(okey, scenario, loc.origin, loc.dest, persona.key)
            ref_label = ("Shortest reference path — interrupted" if not cur.direct_reachable
                         else "Shortest reference path")
            routes.append([cur.baseline_path, REFERENCE_COLOUR, False, ref_label])
            legend.append([f"3px solid {REFERENCE_COLOUR}", ref_label])
            if cur.reachable and cur.path != cur.baseline_path:
                routes.append([cur.path, DETOUR_COLOUR, True, f"Accessible detour ({ui.persona_short(persona.key)})"])
                legend.append([f"3px dashed {DETOUR_COLOUR}", "Accessible detour"])
        legend.append(["2px solid #A63429", "! Barrier / ✖ blocked"])
        legend.append(["2px dashed #687064", "Unverified"])
        show_map(height=600, overlay_key=okey, persona_key=persona.key, routes_key=json.dumps(routes),
                 upgrades_key=json.dumps(list(scenario)), selected=loc.edge_id,
                 selected_label=f"{loc.label} · {loc.edge_id}", street=street, legend_key=json.dumps(legend),
                 show_ids=st.session_state.get("show_ids", False))
        st.caption("Fictional layout · not to scale. The list on the left is the equivalent of the map — "
                   "no hover needed. Hover a line for its recorded attributes.")

    with right:
        inspector(loc, okey, scenario, persona, G)

    ws.status_bar(bool(scenario), cached.data_version(okey))
    ui.disclaimer()


ui.run_page(main)
