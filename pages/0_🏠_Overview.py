"""Network — the V2 planning workspace (priority locations · plan-view map · Inspector).

Everything shown is computed by the core through ui.cached / ui.workspace. "Preview ramp" only changes a
session-only scenario; nothing is written to the database and actual routes are unchanged (fix pack X3).
"""
import json
import os
from types import SimpleNamespace

import streamlit as st

from accesstwin import config
from accesstwin.core import store
from accesstwin.core.graph import node_name
from accesstwin.core.simulation import load_upgrades, unresolved_obstacles
from accesstwin.ui import cached
from accesstwin.ui import components as ui
from accesstwin.ui import guide
from accesstwin.ui import workspace as ws
from accesstwin.ui.i18n import t
from accesstwin.ui.map_view import DETOUR_COLOUR, REFERENCE_COLOUR, show_map

PAGE = "pages/0_🏠_Overview.py"
PREVIOUS_COLOUR = "#B9B6AA"


def _set_scenario(ids: tuple) -> None:
    c = ws.ctx()
    c["scenario"] = ids
    c["toast"] = "Scenario applied — showing the simulated ramp" if ids else "Back to baseline — recorded conditions"


def _fmt(m: float | None) -> str:
    if m is None:
        return "no passable route"
    return f"{m / 1000:.1f} km" if m >= 1000 else f"{m:.0f} m"


def _report_here(edge_id: str) -> None:
    guide.queue_presets({"ro_edge": edge_id, "ro_src": "Use a sample photo"})


# ---------------------------------------------------------------- Inspector sections

def evidence_section(loc, G) -> None:
    """X4: linked reports with photo thumbnails, verifications, and the condition record source."""
    st.markdown(f"<div class='at-section'><div class='at-eyebrow'>{ws.esc(t('evidence_origin'))}</div></div>",
                unsafe_allow_html=True)
    reps = [r for r in store.list_reports() if r["edge_id"] == loc.edge_id][::-1]
    credits = ui.photo_credits()
    if not reps:
        st.caption("No photo evidence yet.")
        b1, b2 = st.columns(2)
        if b1.button("Request site inspection", key=f"ws_inspect_{loc.edge_id}"):
            store.add_inspection_request(loc.edge_id, "requested from the Network inspector")
            st.toast("Site inspection requested (this demo session only).")
        b2.button("Report an obstacle here", key=f"ws_report_{loc.edge_id}", on_click=_report_here, args=(loc.edge_id,))
        if st.session_state.get("guide_pending", {}).get("ro_edge") == loc.edge_id:
            ws._page_link("pages/2_📸_Report_Obstacle.py", "Open Report Obstacle ↗")
    for r in reps:
        ai = r.get("ai") or {}
        src = ai.get("source", "mock")
        badge = f"Groq · {ai.get('model', '')}" if src == "groq" else ("Seed record" if src == "seed" else "Demo classifier")
        cols = st.columns([1, 2], vertical_alignment="top")
        photo = config.resolve_path(r["photo_path"]) if r.get("photo_path") else None
        with cols[0]:
            if photo and photo.exists():
                st.image(str(photo), width="stretch")
                with st.expander("Enlarge"):
                    st.image(str(photo), width="stretch")
                    st.caption(ui.photo_caption(photo.name))
            else:
                st.caption("No photo")
        with cols[1]:
            status = {"pending": "Pending review", "approved": "Confirmed", "rejected": "Rejected"}[r["status"]]
            st.markdown(
                f"<div class='at-kv'><b style='color:var(--text-primary)'>Report #{r['id']}</b><span>{ws.esc(status)}</span></div>"
                f"<div class='at-muted'>{ws.esc(r['reporter_role'].capitalize())} · {ws.esc(r['created_at'][:10])}</div>"
                f"<div class='at-muted'>AI ({ws.esc(badge)}): {ws.esc(ai.get('obstacle_type', '?').replace('_', ' '))}, "
                f"{float(ai.get('confidence', 0)):.0%}</div>"
                f"<div class='at-muted'>{ws.esc(ai.get('visible_evidence') or '')}</div>", unsafe_allow_html=True)
            if photo is not None and photo.name in credits:
                st.caption(ui.photo_caption(photo.name))
    vers = [v for v in store.list_verifications() if v["edge_id"] == loc.edge_id]
    for v in vers[::-1]:
        st.markdown(f"<div class='at-muted'>Verification · {ws.esc(v['verifier_role'])} · {ws.esc(v['created_at'][:10])} · "
                    f"{ws.esc(v['result'].replace('_', ' '))}</div>", unsafe_allow_html=True)
    for q in store.list_inspection_requests(loc.edge_id):
        st.markdown(f"<div class='at-muted'>Site inspection requested · {ws.esc(q['created_at'][:10])} · pending</div>",
                    unsafe_allow_html=True)
    st.markdown("<div class='at-kv'><span>Condition record</span><span class='at-chip syn'>Synthetic survey data</span></div>",
                unsafe_allow_html=True)


def baseline_inspector(loc, okey, persona, G) -> None:
    e = ws.find_edge(G, loc.edge_id)
    if loc.kind == "barrier" and e.get("has_step"):
        st.markdown(ws.step_section_svg(float(e.get("curb_height_cm", 0)), ramp=False), unsafe_allow_html=True)
    st.markdown(f"<div class='at-section'><div class='at-eyebrow'>{ws.esc(t('existing_condition'))}</div>"
                f"<div class='at-big'>{ws.esc(loc.condition_value)} <small>{ws.esc(loc.condition_unit)}</small></div>"
                f"<div class='at-muted'>{ws.esc(loc.condition_text)}</div></div>", unsafe_allow_html=True)
    if loc.kind == "inspection" or not (loc.origin and loc.dest):
        st.markdown(
            f"<div class='at-section'><div class='at-eyebrow'>{ws.esc(ui.persona_short(persona.key))} "
            f"{ws.esc(t('journey_head'))}</div><div class='at-big'>— <small>{ws.esc(t('not_assessed'))}</small></div>"
            f"<div class='at-muted'>No journey impact is estimated until the site record is confirmed.</div></div>",
            unsafe_allow_html=True)
        return
    cur = cached.journey(okey, (), loc.origin, loc.dest, persona.key)
    note = t("interrupted") if not cur.direct_reachable else "Usable for this profile"
    st.markdown(
        f"<div class='at-section'><div class='at-eyebrow'>{ws.esc(ui.persona_short(persona.key))} "
        f"{ws.esc(t('journey_head'))}</div><div class='at-grid2'>"
        f"<div><div class='at-muted'>{ws.esc(t('shortest_reference'))}</div>"
        f"<div class='at-big'>{ws.esc(_fmt(cur.baseline_length_m))}</div>"
        f"<div class='at-status {'blocked' if not cur.direct_reachable else 'verified'}' style='font-weight:500'>"
        f"{'✖ ' if not cur.direct_reachable else '✓ '}{ws.esc(note)}</div></div>"
        f"<div><div class='at-muted'>{ws.esc(t('available_route'))}</div>"
        f"<div class='at-big'>{ws.esc(_fmt(cur.length_m if cur.reachable else None))}</div>"
        f"<div class='at-muted'>{(f'{cur.detour_ratio:.1f}× the reference' if cur.reachable and cur.detour_ratio else '')}</div>"
        f"</div></div></div>", unsafe_allow_html=True)
    tags = "".join(f"<span>{ws.esc(ui.persona_short(k))}</span>" for k in loc.affected) or "<span>None</span>"
    st.markdown(f"<div class='at-section'><div class='at-eyebrow'>{ws.esc(t('affected_profiles'))}</div>"
                f"<div class='at-tags'>{tags}</div></div>", unsafe_allow_html=True)


def scenario_inspector(loc, okey, scenario, G) -> None:
    """X3: change view — condition, journeys, profile chips, score and newly reachable combinations."""
    e = ws.find_edge(G, loc.edge_id)
    up = loc.upgrade
    if e.get("has_step"):
        st.markdown(ws.step_section_svg(float(e.get("curb_height_cm", 0)), ramp=True), unsafe_allow_html=True)
    before_txt = f"{loc.condition_value} {loc.condition_unit} {loc.short.split(' ', 2)[-1] if loc.short else ''}".strip()
    st.markdown(f"<div class='at-section'><div class='at-eyebrow'>Condition</div>"
                f"<div class='at-big' style='font-size:20px'>{ws.esc(before_txt)} → "
                f"{ws.esc('kerb ramp' if 'ramp' in up['title'].lower() else up['title'].split(' at ')[0].lower())} "
                f"<small>(simulated)</small></div></div>", unsafe_allow_html=True)
    changes = ws.journey_changes(okey, loc, scenario)
    rows, chips, same = [], [], []
    for jc in changes:
        if jc.before_m != jc.after_m or jc.before_ok != jc.after_ok:
            diff = (f" ({jc.after_m - jc.before_m:+.0f} m)" if jc.before_m is not None and jc.after_m is not None else "")
            rows.append(f"<div class='at-kv'><span>{ws.esc(ui.persona_short(jc.persona))}</span>"
                        f"<b style='color:var(--accent-strong)'>{ws.esc(_fmt(jc.before_m))} → {ws.esc(_fmt(jc.after_m))}{ws.esc(diff)}</b></div>")
            chips.append(f"<span>{ws.esc(ui.persona_short(jc.persona))} {'✕' if not jc.before_ok else '✓'}→{'✓' if jc.after_ok else '✕'}</span>")
        else:
            same.append(ui.persona_short(jc.persona))
    d, _ = cached.scenario(okey, scenario)
    if not rows and abs(d.index_delta) < 1e-9:
        ui.card("No change", "No change — because this upgrade does not remove a barrier that any profile meets on the "
                "modelled journeys.", "warn")
        return
    st.markdown(f"<div class='at-section'><div class='at-eyebrow'>Journey · {ws.esc(node_name(G, loc.origin))} → "
                f"{ws.esc(node_name(G, loc.dest))}</div>{''.join(rows)}"
                f"<div class='at-tags' style='margin-top:6px'>{''.join(chips)}</div>"
                + (f"<div class='at-muted'>No change for {ws.esc(', '.join(same))} (already able to use this connection).</div>"
                   if same else "") + "</div>", unsafe_allow_html=True)
    per = "".join(f"<div class='at-kv'><span>{ws.esc(ui.persona_short(k))}</span><span>{d.persona_before[k]:.1f} → "
                  f"{d.persona_after[k]:.1f} ({d.persona_after[k] - d.persona_before[k]:+.1f})</span></div>"
                  for k in d.persona_before)
    st.markdown(f"<div class='at-section'><div class='at-eyebrow'>{ws.esc(t('access_score'))} · modelled</div>"
                f"<div class='at-big'>{d.index_before:.1f} → {d.index_after:.1f} <small>({d.index_delta:+.1f})</small></div>"
                f"{per}</div>", unsafe_allow_html=True)
    if d.newly_reachable:
        with st.expander(f"{t('newly_reachable')}: {len(d.newly_reachable)}", expanded=False):
            st.dataframe([{"home": node_name(G, x["residential"]), "profile": ui.persona_short(x["persona"]),
                           "destination": node_name(G, x["dest"]), "before": x["before"]} for x in d.newly_reachable],
                         hide_index=True, width="stretch")
    left = unresolved_obstacles(G, up)
    if left:
        ui.card("Not resolved by this upgrade", "; ".join(ws.esc(o.get("text", o["type"])) for o in left)
                + " — a ramp doesn't remove parked vehicles; this needs enforcement or bollards.", "warn")
    st.markdown(f"<div class='at-muted'><span class='at-chip'>{ws.esc(up['cost_tier'].capitalize())} cost tier</span> "
                f"{ws.esc(t('onsite'))}</div>", unsafe_allow_html=True)


def inspector(loc, okey: str, scenario: tuple, persona, G) -> None:
    st.markdown("<span class='at-ws-inspector'></span><span id='next-action'></span>", unsafe_allow_html=True)
    st.markdown(f"<div class='at-eyebrow' style='display:flex;justify-content:space-between'>"
                f"<span>{ws.esc(t('location_details'))}</span><span>{ws.esc(loc.edge_id)}</span></div>",
                unsafe_allow_html=True)
    with st.container(key="ws_top_action"):
        action_box(loc, scenario, "top")
    review_cls, review_txt = ws.review_state(loc.edge_id)
    kind_cls = {"barrier": "blocked", "inspection": "pending", "blocked": "blocked", "obstruction": "blocked"}[loc.kind]
    status = "Proposed scenario · not built" if scenario else loc.status_text
    mark = "◆" if scenario else {"barrier": "●", "inspection": "○", "blocked": "✖", "obstruction": "●"}[loc.kind]
    route_line = (f"{node_name(G, loc.origin)} → {node_name(G, loc.dest)}" if loc.origin and loc.dest else
                  f"{node_name(G, ws.find_edge(G, loc.edge_id)['from'])} → {node_name(G, ws.find_edge(G, loc.edge_id)['to'])}")
    st.markdown(f"<div class='at-status {'sim' if scenario else kind_cls}'>{mark} {ws.esc(status)}</div>"
                f"<div class='at-title'>{ws.esc(loc.label)}</div><div class='at-sub'>{ws.esc(route_line)}</div>"
                f"<div style='margin-top:6px'><span class='at-status {review_cls}' style='font-weight:500;font-size:13px'>"
                f"{ws.esc(review_txt)}</span></div>", unsafe_allow_html=True)
    if scenario:
        scenario_inspector(loc, okey, scenario, G)
    else:
        baseline_inspector(loc, okey, persona, G)
    evidence_section(loc, G)
    st.markdown("<div style='margin-top:10px'><a href='#next-action'>Back to action ↑</a></div>", unsafe_allow_html=True)


def action_box(loc, scenario: tuple, where: str) -> None:
    """Main action at the top of the Inspector (X9: the bottom repeat became a "Back to action" link)."""
    st.markdown(f"<div class='at-eyebrow' style='margin-top:4px'>{ws.esc(t('next_action'))}</div>", unsafe_allow_html=True)
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
    persona = ui.sidebar(bar=False)
    ws.project_bar("network")
    guide.panel(PAGE)
    G = ui.graph()
    okey = ui.overlay_key()
    c = ws.ctx()
    if c.pop("toast", None):
        st.toast("Scenario applied — showing the simulated ramp" if c["scenario"] else "Back to baseline")
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
    reviews = {x.edge_id: ws.review_state(x.edge_id)[1] for x in locs}

    left, centre, right = st.columns([1.1, 3.1, 1.3], gap="small")
    with left:
        st.markdown(f"<div class='at-eyebrow'>{ws.esc(t('network_study'))}</div>"
                    f"<div style='font-size:22px;font-weight:500;letter-spacing:-.6px'>{ws.esc(t('assessment_title'))}</div>"
                    f"<div class='at-muted' style='margin:4px 0 10px'>{ws.esc(t('assessment_sub'))}</div>",
                    unsafe_allow_html=True)
        by_id = {x.edge_id: x for x in locs}
        st.radio(t("priority_locations"), ids, key="ws_segment", index=ids.index(c["segment"]),
                 format_func=lambda i: f"{ids.index(i) + 1:02d} · {ws.list_label(by_id[i], reviews[i])}",
                 help="Sorted by modelled impact (score loss weighted by vulnerable residents).",
                 on_change=lambda: c.update(segment=st.session_state["ws_segment"], scenario=()))
        st.markdown("<span class='at-ws-list'></span>", unsafe_allow_html=True)
        base = cached.scores(okey)
        if scenario:
            d, _ = cached.scenario(okey, scenario)
            st.markdown(f"<div class='at-muted'>Baseline {d.index_before:.1f} · <b style='color:var(--accent-strong)'>"
                        f"Simulated {d.index_after:.1f}</b></div>", unsafe_allow_html=True)
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
        if scenario:
            with st.container(border=True, key="ws_sim_banner"):
                st.markdown(f"<div class='at-status sim'>SIMULATED · {ws.esc(loc.upgrade['title'])} · not built — "
                            f"existing conditions unchanged</div>", unsafe_allow_html=True)
                b1, b2 = st.columns(2)
                b1.button(f"↩ {t('return_baseline')}", key="ws_return_banner", on_click=_set_scenario, args=((),),
                          use_container_width=True)
                with b2:
                    ws._page_link("pages/8_Compare.py", "Compare in detail →")
        st.markdown(f"<div class='at-mobile-only'><div class='at-status {'sim' if scenario else 'blocked'}'>"
                    f"{ws.esc('Proposed scenario' if scenario else loc.status_text)} · {ws.esc(loc.edge_id)} · "
                    f"{ws.esc(loc.short)}</div></div>", unsafe_allow_html=True)
        with st.container(key="ws_mobile_action"):
            action_box(loc, scenario, "mobile")
        # X6: plan view only on the public demo; street tiles over the real Elmina streets only behind a dev flag.
        street = False
        if os.environ.get("ACCESSTWIN_DEV_STREETMAP", "0") == "1":
            street = st.toggle(t("street_map"), key="ws_street", value=False)
        routes, legend = [], []
        if loc.origin and loc.dest:
            base_r = cached.journey(okey, (), loc.origin, loc.dest, persona.key)
            if scenario:
                cur = cached.journey(okey, scenario, loc.origin, loc.dest, persona.key)
                if base_r.reachable and base_r.path != cur.path:
                    routes.append([base_r.path, PREVIOUS_COLOUR, True, f"previous detour {_fmt(base_r.length_m)}"])
                    legend.append([f"3px dashed {PREVIOUS_COLOUR}", f"Previous detour {_fmt(base_r.length_m)}"])
                if cur.reachable:
                    routes.append([cur.path, REFERENCE_COLOUR, False, f"Simulated route {_fmt(cur.length_m)}"])
                    legend.append([f"4px solid {REFERENCE_COLOUR}", f"Simulated route {_fmt(cur.length_m)}"])
                legend.append([f"4px solid {REFERENCE_COLOUR}", "Proposed ramp (amber outline)"])
            else:
                ref_label = ("Shortest reference path — interrupted" if not base_r.direct_reachable
                             else "Shortest reference path")
                routes.append([base_r.baseline_path, REFERENCE_COLOUR, False, ref_label])
                legend.append([f"3px solid {REFERENCE_COLOUR}", ref_label])
                if base_r.reachable and base_r.path != base_r.baseline_path:
                    routes.append([base_r.path, DETOUR_COLOUR, True,
                                   f"Available route ({ui.persona_short(persona.key)}) {_fmt(base_r.length_m)}"])
                    legend.append([f"3px dashed {DETOUR_COLOUR}", f"Available route {_fmt(base_r.length_m)}"])
        legend += [["2px solid #A63429", "! barrier · ✖ obstruction / closure"], ["2px dashed #687064", "Unverified"],
                   ["2px dotted #A63429", "Impassable for this profile"]]
        show_map(height=600, overlay_key=okey, persona_key=persona.key, routes_key=json.dumps(routes),
                 upgrades_key=json.dumps(list(scenario)),
                 highlight_key=json.dumps([loc.edge_id] if scenario else []),
                 selected="" if scenario else loc.edge_id,
                 selected_label=f"{loc.label} · {loc.edge_id}" if not scenario else "",
                 street=street, legend_key=json.dumps(legend), show_ids=st.session_state.get("show_ids", False))
        if scenario:
            st.caption(f"Proposed ramp at {loc.edge_id} (amber, simulated). Same map extent as the baseline.")
        st.caption("Fictional layout · synthetic data · not to scale. The list on the left is the equivalent of the "
                   "map — no hover needed.")

    with right:
        inspector(loc, okey, scenario, persona, G)

    ws.status_bar(bool(scenario), cached.data_version(okey))
    ui.disclaimer()


ui.run_page(main)
