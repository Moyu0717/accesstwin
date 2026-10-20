"""Track my report — resident receipt lookup by the unguessable report code (Round 2B).

Only the code holder sees a report here; there is no list of other people's reports. This demo keeps data per
browser session, so a code works only in the session that created it.
"""
import streamlit as st

from accesstwin.core import store
from accesstwin.core.graph import iter_edges, node_name
from accesstwin.ui import components as ui
from accesstwin.ui.i18n import t


def main() -> None:
    ui.setup_page(t("nav_track"), "♿")
    ui.sidebar()
    G = ui.graph()
    ui.page_head(t("nav_track"), eyebrow="Resident · Track my report",
                 sub="Enter the report code from your receipt (for example AT-7KQ2-M9XD).")

    last = st.session_state.get("ro_receipt")
    if last and not st.session_state.get("tr_code"):
        r0 = store.get_report(last)
        if r0:
            st.session_state["tr_code"] = r0["token"]
    code = st.text_input("Report code", key="tr_code", max_chars=12)
    if not code:
        st.caption("No code yet? Report an obstacle first; the receipt shows your code.")
        ui.page_link("pages/2_📸_Report_Obstacle.py", label="Report an obstacle →")
        ui.disclaimer()
        return
    r = store.get_report_by_token(code)
    if r is None:
        st.error("No report with this code in this session. Check the code; codes look like AT-XXXX-XXXX.")
        ui.disclaimer()
        return
    e = next((x for x in iter_edges(G) if x["id"] == r["edge_id"]), {"from": "", "to": ""})
    state, nxt = store.report_state(r)
    ai = r.get("ai") or {}
    st.markdown(
        f"<div class='at-route-head'><div class='at-eyebrow'>Report {ui.esc(r['token'])}</div>"
        f"<div class='at-status pending' style='font-size:20px;font-weight:600'>{ui.esc(state)}</div>"
        f"<div style='margin-top:4px'>Next step: {ui.esc(nxt)}</div></div>"
        f"<div class='at-kv'><span>Location</span><span>{ui.esc(r['edge_id'])} · {ui.esc(node_name(G, e['from']))} → "
        f"{ui.esc(node_name(G, e['to']))}</span></div>"
        f"<div class='at-kv'><span>Category</span><span>{ui.esc(ai.get('obstacle_type', 'other').replace('_', ' '))}</span></div>"
        f"<div class='at-kv'><span>Submitted</span><span>{ui.esc(r['created_at'][:16].replace('T', ' '))}</span></div>",
        unsafe_allow_html=True)
    if r.get("description"):
        st.markdown(f"<div class='at-section'><div class='at-eyebrow'>Your description</div>"
                    f"<div style='white-space:pre-wrap'>{ui.esc(r['description'])}</div></div>", unsafe_allow_html=True)
    if r.get("triage") == "needs_information":
        more = st.text_area("Add the requested information", key="tr_more", max_chars=1000)
        if st.button("Send information", type="primary", key="tr_send"):
            if more.strip():
                store.add_report_info(r["token"], more)
                st.success("Thank you — the report is back with the reviewer.")
                st.rerun()
            else:
                st.error("Write the information first; nothing was sent.")
    st.caption("This demo keeps reports for this browser session only. No processing time is promised.")
    ui.page_link("pages/1_🧭_Route_Planner.py", label="Back to my route →")
    ui.disclaimer()


ui.run_page(main)
