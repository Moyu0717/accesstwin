import streamlit as st

from accesstwin import config
from accesstwin.core import store
from accesstwin.core.graph import find_edge, iter_edges, load_graph, node_name
from accesstwin.core.routing import route
from accesstwin.ui import components as ui
from accesstwin.ui.i18n import t

ui.setup_page(t("queue_title"), "✅")
persona = ui.sidebar()
G = ui.graph()
P = ui.personas()

st.title(f"✅ {t('queue_title')}")
st.caption("Human-in-the-loop: AI suggestions never change the map by themselves. Approving a report marks the "
           "segment **blocked** (stored as an overlay — the base map data is never modified).")

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


# ---- Section 1: pending obstacle reports -----------------------------------
pending = store.list_reports("pending")
st.subheader(f"📥 Pending obstacle reports ({len(pending)})")
if not pending:
    st.info("No pending reports. New reports from the Report Obstacle page appear here.")
for r in pending:
    ai = r.get("ai", {})
    edge = find_edge(G, r["edge_id"]) or {}
    with st.container(border=True):
        c1, c2, c3 = st.columns([1, 2, 1])
        photo = config.ROOT / r["photo_path"] if r.get("photo_path") else None
        if photo and photo.exists():
            c1.image(str(photo), width="stretch")
        else:
            c1.caption("No photo")
        c2.markdown(
            f"**#{r['id']} · {r['edge_id']}** — {node_name(G, edge.get('from', ''))} ↔ {node_name(G, edge.get('to', ''))}  \n"
            f"Reporter: **{r['reporter_role']}** · {r['created_at'][:16].replace('T', ' ')}  \n"
            f"AI ({ai.get('source', 'n/a')}): **{ai.get('obstacle_type', '?').replace('_', ' ')}**, severity {ai.get('severity', '?')}, "
            f"confidence {float(ai.get('confidence', 0)):.0%}  \n"
            f"Evidence: {ai.get('visible_evidence') or '—'}"
        )
        if ai.get("needs_onsite_measurement"):
            c2.caption("📏 Measure on site: " + ", ".join(ai["needs_onsite_measurement"]))
        if c3.button("✅ Approve", help="Marks this segment blocked", key=f"vq_ok_{r['id']}", type="primary"):
            store.set_report_status(r["id"], "approved")
            st.session_state["vq_flash"] = (f"Report #{r['id']} approved — {r['edge_id']} is now blocked. "
                                            + impact_text(r["edge_id"], G, load_graph()))
            st.rerun()
        if c3.button("✖ Reject", key=f"vq_no_{r['id']}"):
            store.set_report_status(r["id"], "rejected")
            st.session_state["vq_flash"] = f"Report #{r['id']} rejected — no change to the map."
            st.rerun()

# ---- Section 2: verify unverified segments ---------------------------------
st.divider()
st.subheader("🔎 Verify unverified segments")
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
                      format_func=lambda x: "Passable → verified accessible" if x == "passable" else "Not passable → blocked",
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
    st.markdown("**Current overlay** (edge → status)")
    st.json(store.get_overlay())

ui.disclaimer()
