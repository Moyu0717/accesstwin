import streamlit as st

from accesstwin import config
from accesstwin.core import store
from accesstwin.core.graph import find_edge, iter_edges, load_graph, node_name
from accesstwin.core.routing import route
from accesstwin.ui import components as ui
from accesstwin.ui import guide
from accesstwin.ui.i18n import t


def review_detail(r: dict, G, impact_text) -> None:
    """Selected report: evidence, original AI suggestion vs the reporter's choice, similar reports, decisions."""
    ai, orig = r.get("ai", {}), r.get("ai_original")
    edge = find_edge(G, r["edge_id"]) or {}
    chip = ("<span class='at-chip pending'>Waiting for information</span>" if r.get("triage") == "needs_information"
            else "<span class='at-chip pending'>Pending review</span>")
    syn = " <span class='at-chip syn'>Synthetic</span>" if ai.get("source") == "seed" else ""
    st.markdown(f"<div>{chip}{syn}</div><div class='at-title' style='font-size:22px'>Report #{r['id']} · "
                f"{ui.esc(r['edge_id'])}</div><div class='at-sub'>{ui.esc(node_name(G, edge.get('from', '')))} → "
                f"{ui.esc(node_name(G, edge.get('to', '')))} · {ui.esc(r['reporter_role'])} · "
                f"{ui.esc(r['created_at'][:16].replace('T', ' '))}</div>", unsafe_allow_html=True)
    photo = config.resolve_path(r["photo_path"]) if r.get("photo_path") else None
    c1, c2 = st.columns([1, 1.4])
    if photo and photo.exists():
        c1.image(str(photo), width="stretch")
        c1.caption(ui.photo_credit_line(photo.name))
    else:
        c1.markdown("<div class='at-hero-empty'>No photo</div>", unsafe_allow_html=True)
    with c2:
        st.markdown(f"<div class='at-eyebrow'>Description</div><div style='white-space:pre-wrap'>"
                    f"{ui.esc(r.get('description') or '—')}</div>", unsafe_allow_html=True)
        src = ai.get("source", "n/a")
        cur = f"{ai.get('obstacle_type', '?').replace('_', ' ')}, severity {ai.get('severity', '?')}"
        if orig:
            st.markdown(f"<div class='at-eyebrow' style='margin-top:8px'>AI suggestion (original, kept)</div>"
                        f"<div>{ui.esc(orig.get('obstacle_type', '?').replace('_', ' '))}, severity "
                        f"{ui.esc(orig.get('severity', '?'))}, confidence {float(orig.get('confidence', 0)):.0%} · "
                        f"{ui.esc(orig.get('source', ''))}</div>", unsafe_allow_html=True)
        head = ("Reporter choice" + (" (edited)" if ai.get("edited") else "")) if orig else "Category"
        st.markdown(f"<div class='at-eyebrow' style='margin-top:8px'>{ui.esc(head)}</div>"
                    f"<div>{ui.esc(cur)} · {ui.esc(src)}</div>", unsafe_allow_html=True)
        if ai.get("needs_onsite_measurement"):
            st.caption("Measure on site: " + ", ".join(ai["needs_onsite_measurement"]))
        if r.get("triage") == "needs_information" and r.get("reason"):
            st.caption(f"Asked the reporter: {r['reason']}")
    others = [x for x in store.list_reports() if x["edge_id"] == r["edge_id"] and x["id"] != r["id"]]
    if others:
        st.caption("Other reports on this segment: " + ", ".join(
            f"#{x['id']} ({x['status']}{', duplicate' if x.get('triage') == 'duplicate' else ''})" for x in others))
    st.markdown("<div class='at-eyebrow' style='margin-top:10px'>Decision</div>", unsafe_allow_html=True)
    rid = r["id"]
    if st.button("Accept for investigation", key=f"vq_ok_{rid}", type="primary",
                 help="Confirms this obstacle on the segment; only the profiles it affects are re-routed. "
                      "It does not close the path for everyone."):
        store.triage_report(rid, "accept")
        st.session_state["vq_flash"] = (f"Report #{rid} accepted for investigation — obstacle confirmed on "
                                        f"{r['edge_id']}. " + impact_text(r["edge_id"], G, load_graph()))
        st.rerun()
    a1, a2 = st.columns(2)
    with a1:
        need = st.text_input("Information needed", key=f"vq_need_{rid}", placeholder="e.g. a photo of the kerb")
        if st.button("Request information", key=f"vq_info_{rid}"):
            try:
                store.triage_report(rid, "request_info", reason=need)
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.session_state["vq_flash"] = f"Report #{rid}: information requested from the reporter."
                st.rerun()
    with a2:
        mains = [x for x in store.list_reports() if x["id"] != rid and x.get("triage") != "duplicate"]
        labels = {x["id"]: f"#{x['id']} · {x['edge_id']} · {x['status']}" for x in mains}
        main_id = (st.selectbox("Main report", list(labels), key=f"vq_dup_main_{rid}", format_func=labels.get)
                   if mains else None)
        if st.button("Mark duplicate", key=f"vq_dup_{rid}", disabled=main_id is None):
            try:
                store.triage_report(rid, "duplicate", duplicate_of=main_id)
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.session_state["vq_flash"] = f"Report #{rid} linked to report #{main_id} as a duplicate — no map change."
                st.rerun()
    why = st.text_input("Reason for rejecting", key=f"vq_reason_{rid}", placeholder="e.g. not on a walkway")
    if st.button("Reject", key=f"vq_no_{rid}"):
        try:
            store.triage_report(rid, "reject", reason=why)
        except ValueError as exc:
            st.error(str(exc))
        else:
            st.session_state["vq_flash"] = f"Report #{rid} rejected — no change to the map."
            st.rerun()


def main() -> None:
    ui.setup_page(t("queue_title"), "✅")
    persona = ui.sidebar()
    G = ui.graph()
    P = ui.personas()

    ui.page_head(t('queue_title'), eyebrow="Review · Reports and site checks")

    guide.panel("pages/3_✅_Verification_Queue.py")
    st.caption("Human-in-the-loop: AI suggestions never change the map by themselves. Approving a report **confirms a "
               "specific obstacle**; only the profiles it affects are re-routed. A full closure is recorded only by an "
               "explicit site check. Stored as an overlay — the base map data is never modified.")

    flash = st.session_state.pop("vq_flash", None)
    if flash:
        st.success(flash)


    def impact_text(edge_id: str, before_G, after_G) -> str:
        """Which demo trips change because of this decision."""
        changes = []
        for r in [n for n, d in after_G.nodes(data=True) if d.get("type") == "residential"]:
            for dest in [n for n, d in after_G.nodes(data=True) if d.get("type") == "destination"]:
                for key, p in P.items():
                    a, b = route(before_G, r, dest, p), route(after_G, r, dest, p)
                    if (a.reachable, round(a.length_m)) != (b.reachable, round(b.length_m)):
                        changes.append((key, r, dest, a, b))
        if not changes:
            return "No persona route changes."
        key, r, dest, a, b = changes[0]
        before = ui.fmt_m(a.length_m) if a.reachable else "unreachable"
        after = ui.fmt_m(b.length_m) if b.reachable else "unreachable"
        return (f"{len(changes)} persona routes recomputed — e.g. {P[key].label.lower()} {node_name(after_G, r)} → "
                f"{node_name(after_G, dest)}: {before} → {after}.")


    # ---- Section 1: triage — list on the left, the selected report on the right (plan §5.3) ------------------
    pending = store.list_reports("pending")
    waiting = [r for r in pending if r.get("triage") != "needs_information"]
    asked = [r for r in pending if r.get("triage") == "needs_information"]
    st.subheader(f"Reports to review ({len(waiting)})" + (f" · {len(asked)} waiting for information" if asked else ""))
    if not pending:
        st.info("No reports to review. New reports from Report an obstacle appear here.")
    else:
        ids = [r["id"] for r in waiting + asked]
        if st.session_state.get("vq_sel") not in ids:
            st.session_state["vq_sel"] = ids[0]
        left, right = st.columns([1, 2.2], gap="medium")
        with left, st.container(key="vq_rows"):
            for r in waiting + asked:
                ai = r.get("ai", {})
                tag = "waiting for information" if r.get("triage") == "needs_information" else "pending review"
                st.button(f"**#{r['id']} · {r['edge_id']}**\n\n{ai.get('obstacle_type', '?').replace('_', ' ')} · "
                          f"{r['reporter_role']} · {tag}", key=f"vq_row_{r['id']}", use_container_width=True,
                          type="primary" if r["id"] == st.session_state["vq_sel"] else "secondary",
                          on_click=lambda i=r["id"]: st.session_state.__setitem__("vq_sel", i))
        with right:
            r = next(x for x in pending if x["id"] == st.session_state["vq_sel"])
            review_detail(r, G, impact_text)

    # ---- Section 2: verify unverified segments ---------------------------------
    st.divider()
    st.subheader("Verify unverified segments")
    st.caption("Simulates an on-site check, e.g. by a wheelchair-user representative walking the segment with a guard.")
    unverified = [e for e in iter_edges(G) if e.get("status") == "unverified"]
    if not unverified:
        st.info("All segments are verified or blocked.")
    else:
        labels = {e["id"]: f"{e['id']} · {node_name(G, e['from'])} ↔ {node_name(G, e['to'])} · {e['length_m']} m" for e in unverified}
        v1, v2 = st.columns(2)
        edge_id = v1.selectbox("Segment", list(labels), format_func=lambda i: labels[i], key="vq_edge")
        role = v2.selectbox("Verifier role", ["guard", "admin", "wheelchair-user representative", "senior-citizen representative"],
                            key="vq_role")
        result = v1.radio("Result", ["passable", "not_passable"], horizontal=True,
                          format_func=lambda x: "Passable → recorded condition confirmed" if x == "passable" else "Not passable → closed for everyone",
                          key="vq_result")
        note = v2.text_input("Note", placeholder="e.g. ramp gradient fine, surface even", key="vq_note")
        if st.button("Record verification", type="primary", key="vq_verify"):
            store.add_verification(edge_id, role, result, note)
            new_status = "verified accessible" if result == "passable" else "blocked"
            st.session_state["vq_flash"] = (f"{edge_id} marked {new_status} by {role}. "
                                            + impact_text(edge_id, G, load_graph()))
            st.rerun()

    # ---- History ---------------------------------------------------------------
    with st.expander("Decision history"):
        decided = [r for r in store.list_reports() if r["status"] != "pending"]
        st.markdown("**Reports**")
        st.dataframe([{k: r[k] for k in ("id", "edge_id", "reporter_role", "status", "created_at", "decided_at")} for r in decided],
                     hide_index=True, width="stretch")
        st.markdown("**Verifications**")
        st.dataframe(store.list_verifications(), hide_index=True, width="stretch")
        st.markdown("**Current overlay** (segment → status)")
        st.json(store.get_overlay())

    ui.disclaimer()


ui.run_page(main)
