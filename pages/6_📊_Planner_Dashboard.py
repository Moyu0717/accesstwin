import json

import pandas as pd
import plotly.express as px
import streamlit as st

from accesstwin import config
from accesstwin.core import network_import, report, store, validation
from accesstwin.core.demand import demand_frame
from accesstwin.core.graph import build_graph, find_edge, node_name
from accesstwin.core.scoring import compute_scores, critical_gaps
from accesstwin.core.simulation import load_upgrades
from accesstwin.ui import cached
from accesstwin.ui import components as ui
from accesstwin.ui import guide
from accesstwin.ui.i18n import t
from accesstwin.ui.map_view import show_map


@ui.fragment
def draft_network_review() -> None:
    """Design mode (P1-4): upload a draft walkway network, validate it, and review its gaps before building."""
    st.subheader("Pre-construction review: import a draft walkway network")
    st.caption("Upload a draft masterplan's walkway network as two CSV files. It is analysed in this session only "
               "(nothing is stored). Draft segments are not built yet, so they are all counted as planned (unverified).")
    tn, ts = network_import.template_csvs()
    sn, ss = network_import.sample_csvs()
    c1, c2, c3, c4 = st.columns(4)
    c1.download_button("Template nodes.csv", tn, "nodes.csv", "text/csv", key="dn_tpl_nodes")
    c2.download_button("Template segments.csv", ts, "segments.csv", "text/csv", key="dn_tpl_segs")
    c3.download_button("Sample nodes.csv", sn, "sample_nodes.csv", "text/csv", key="dn_smp_nodes")
    c4.download_button("Sample segments.csv", ss, "sample_segments.csv", "text/csv", key="dn_smp_segs")
    use_sample = st.toggle("Use the sample draft network", value=True, key="dn_use_sample")
    if use_sample:
        nodes_txt, segs_txt, name = sn, ss, "Sample draft network (fictional)"
    else:
        u1, u2 = st.columns(2)
        fn = u1.file_uploader("nodes.csv", type=["csv"], key="dn_nodes")
        fs = u2.file_uploader("segments.csv", type=["csv"], key="dn_segs")
        if fn is None or fs is None:
            st.info("Upload both files (or switch on the sample) to run the review.")
            return
        nodes_txt, segs_txt, name = fn.getvalue().decode("utf-8-sig"), fs.getvalue().decode("utf-8-sig"), "Uploaded draft network"
    data, errors = network_import.parse_network(nodes_txt, segs_txt, name)
    if errors:
        st.error(f"{len(errors)} problem(s) found — fix the CSV files and upload again:")
        st.dataframe([{"problem": e} for e in errors[:50]], hide_index=True, width="stretch")
        return
    G = build_graph(data)
    P = ui.personas()
    s = compute_scores(G, P, include_unverified=True)
    st.success(f"{name}: {len(data['nodes'])} nodes, {len(data['edges'])} segments — valid.")
    cols = st.columns(len(P) + 1)
    cols[0].metric("Draft Access Score", f"{s.index:.0f} / 100")
    for col, (k, v) in zip(cols[1:], s.persona_index.items()):
        col.metric(ui.persona_short(k), f"{v:.0f}")
    st.markdown("**Critical gaps to fix on the drawing:**")
    rows = []
    for g in critical_gaps(s, G, P, top=5):
        pr = g["pair"]
        rows.append({"from": node_name(G, pr.residential), "persona": ui.persona_label(pr.persona),
                     "destination type": pr.category.replace("_", " "),
                     "result": "unreachable" if pr.reach == 0 else ("over comfortable distance" if pr.reach < 1
                                                                     else f"{pr.detour_ratio:.1f}× detour"),
                     "why": pr.reason or "—"})
    st.dataframe(rows, hide_index=True, width="stretch",
                 column_config={"why": st.column_config.TextColumn("why", width="large")})


@ui.fragment
def work_order_board() -> None:
    """Operate-mode loop (P1-3): open → in progress → done → verify on site → segment verified with the repair."""
    st.subheader("Work orders")
    orders = store.list_work_orders()
    if not orders:
        st.info("No work orders yet. Create one from the Upgrade Simulator (\"Create work order\").")
        return
    titles = {u["id"]: u["title"] for u in load_upgrades()}
    repairable = {u["id"] for u in load_upgrades() if u.get("edge_id")}
    verified = {v["note"].split()[0] for v in store.list_verifications() if (v.get("note") or "").startswith(store.WO_NOTE_PREFIX)}
    cols = st.columns(3)
    for col, status, label in zip(cols, store.WORK_ORDER_STATUSES, ["Open", "In progress", "Done"]):
        with col:
            group = [o for o in orders if o["status"] == status]
            st.markdown(f"**{label}** ({len(group)})")
            for o in group:
                with st.container(border=True):
                    st.markdown(f"**#{o['id']} · {o['upgrade_id']}** — {titles.get(o['upgrade_id'], '')}")
                    st.caption(f"Created {o['created_at'][:16].replace('T', ' ')} · time to fix: — (tracked in pilot)")
                    if status == "open" and st.button("Start work", key=f"wo_start_{o['id']}"):
                        store.set_work_order_status(o["id"], "in_progress")
                        st.rerun()
                    if status == "in_progress" and st.button("Mark done", key=f"wo_done_{o['id']}"):
                        store.set_work_order_status(o["id"], "done")
                        st.rerun()
                    if status == "done":
                        if f"{store.WO_NOTE_PREFIX}{o['id']}" in verified:
                            st.success("Verified on site — the segment is updated.")
                        else:
                            st.warning("Verify on site before the segment counts as accessible.")
                            if o["upgrade_id"] not in repairable:
                                st.caption("New link path (design option): it is added to the network once built and "
                                           "surveyed — not modelled as an on-site repair here.")
                            elif st.button("Verify on site (passable)", key=f"wo_verify_{o['id']}", type="primary"):
                                store.verify_work_order(o["id"], "guard", "repair checked on site")
                                st.rerun(scope="app")


def main() -> None:
    ui.setup_page("Planner Dashboard", "📊")
    persona = ui.sidebar()
    G = ui.graph()
    P = ui.personas()


    def observed_counts() -> tuple[dict[str, float], str]:
        try:
            from accesstwin.core.footfall import camera_counts

            return camera_counts(), "footfall module"
        except Exception:
            with open(config.FOOTFALL_PRECOMPUTED_PATH, encoding="utf-8") as f:
                return json.load(f).get("camera_daily_counts", {}), "precomputed file"


    ui.page_head(t('dash_title'), eyebrow="Planning · Dashboard")


    guide.panel("pages/6_📊_Planner_Dashboard.py")
    mode = st.radio("Mode", ["operate", "design"], horizontal=True,
                    index=["operate", "design"].index(st.session_state.get("mode", "operate")),
                    format_func=lambda m: "Operate (existing township)" if m == "operate" else "Design (pre-construction review)",
                    key="dash_mode")
    st.session_state["mode"] = mode
    if mode == "design":
        st.info("**Pre-construction review** — gaps found here can be fixed on the drawing, before anything is built. "
                "Design-only upgrades (e.g. new link paths) are included in the ranking below.")

    okey = ui.overlay_key()
    scores = cached.scores(okey)
    ranking = cached.ranking(okey, mode)
    counts, counts_src = observed_counts()
    counts_key = json.dumps(counts, sort_keys=True)
    demand = cached.demand(okey, counts_key)
    reports = store.list_reports()
    sup = [d for d in demand if d.suppressed]

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Access Score", f"{scores.index:.0f} / 100")
    k2.metric("Suppressed-demand segments", len(sup))
    k3.metric("Open reports", sum(1 for r in reports if r["status"] == "pending"))
    k4.metric("Work orders", len(store.list_work_orders()))

    left, right = st.columns([3, 2])
    with left:
        st.subheader("Footfall heat layer")
        peak = max([d.observed for d in demand if d.observed] or [1])
        circles = [[d.edge_id, 6 + 22 * d.observed / peak, "#A63429" if d.suppressed else "#526E70",
                    f"{d.cctv_id} on {d.edge_id}: observed {d.observed:.0f} vs expected {d.expected or 0:.0f} — {d.status}"]
                   for d in demand if d.observed is not None]
        show_map(height=430, overlay_key=okey, persona_key=persona.key, circles_key=json.dumps(circles),
                 show_ids=st.session_state.get("show_ids", False), zoom=15)
        st.caption("Circle size = observed footfall (aggregate counts only). Dark red = suppressed demand · teal = as expected (also listed on the right). "
                   f"Counts source: {counts_src}.")
    with right:
        st.subheader("Suppressed demand")
        if not sup:
            st.info("No suppressed-demand segments with the current counts.")
        for d in sup:
            e = find_edge(G, d.edge_id)
            ui.card(f"{d.edge_id} · {node_name(G, e['from'])} ↔ {node_name(G, e['to'])} ({d.cctv_id})",
                    f"Observed <b>{d.observed:.0f}</b> vs expected <b>{d.expected:.0f}</b> (ratio {d.ratio:.2f} &lt; 0.4).<br>"
                    f"Barriers on routes through it: {', '.join(d.barrier_edges)}.<br>"
                    "<span class='at-muted'>Low traffic ≠ unimportant — people may not walk here because they can't.</span>", "bad")

    st.dataframe(demand_frame(demand), width="stretch", hide_index=True, column_config=ui.DEMAND_COLUMNS)
    st.caption("Gravity model: expected ∝ population × importance ÷ distance^1.5, scaled to total observed. "
               "Segments without a camera show 'No CCTV coverage' and are never inferred.")

    ui.bundle_card(cached.bundle(okey, mode), "dash_bundle")

    st.subheader("Gap heatmap (home × profile)")
    gm = scores.gap_matrix(G)
    gm.columns = [ui.persona_short(c) for c in gm.columns]
    fig = px.imshow(gm, text_auto=".0f", zmin=0, zmax=100, color_continuous_scale=["#F3F5F0", "#9DBAB6", "#2F5F5C"], aspect="auto",
                    labels={"color": "Access Score"})
    fig.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10), font=dict(size=13, color="#242824"))
    fig.update_traces(textfont=dict(size=14, color="#111611"))
    st.plotly_chart(fig, width="stretch")
    _low = gm.stack().idxmin()
    st.caption(f"Heatmap summary: lowest score {gm.stack().min():.0f}/100 for {_low[1]} at {_low[0]}; "
               f"highest {gm.stack().max():.0f}/100. Higher is better.")

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Report statistics")
        stats = report.report_stats(reports)
        if stats["total"]:
            df = pd.DataFrame([{"obstacle type": k.replace("_", " "), "reports": v} for k, v in stats["by_type"].items()])
            st.plotly_chart(px.bar(df, x="obstacle type", y="reports", height=260, color_discrete_sequence=["#526E70"]),
                            width="stretch")
            _most = df.sort_values("reports", ascending=False).iloc[0]
            st.caption(f"Chart summary: {stats['total']} reports; most common type: {_most['obstacle type']} ({_most['reports']}).")
            st.caption("By status: " + ", ".join(f"{k} {v}" for k, v in stats["by_status"].items())
                       + " · by reporter: " + ", ".join(f"{k} {v}" for k, v in stats["by_role"].items()))
        else:
            st.info("No reports yet.")
    with c2:
        st.subheader("Top 5 upgrades")
        if ranking.empty:
            st.info("No candidate upgrades for this mode.")
        else:
            st.dataframe(ranking.head(5)[["rank", "id", "title", "cost_tier", "delta_index", "roi"]], hide_index=True, width="stretch",
                         column_config={"delta_index": st.column_config.NumberColumn("Δ Access Score"),
                                        "roi": st.column_config.NumberColumn("upgrade priority score")})

    if mode == "design":
        draft_network_review()
    work_order_board()

    with st.expander("Evidence & validation (what is measured, synthetic or planned)"):
        fc, cc = validation.footfall_check(), validation.classifier_check()
        st.dataframe(validation.kpi_rows(fc, cc, cached.bundle(okey, mode)), hide_index=True, width="stretch",
                     column_config={"status": st.column_config.TextColumn("status", width="large")})
        st.markdown("**Bundled photos: expected vs demo classifier**")
        st.dataframe(cc["rows"], hide_index=True, width="stretch")
        st.caption("No field validation has been done yet. Synthetic and planned items are labelled; nothing here is "
                   "a measured result from a real township.")

    st.subheader("Export Planning Brief")
    html_doc = cached.brief_html(okey, counts_key, mode, json.dumps([[r['id'], r['status']] for r in reports]))
    d1, d2, d3 = st.columns(3)
    d1.download_button("Planning Brief (HTML)", html_doc, file_name="accesstwin_planning_brief.html",
                       mime="text/html", type="primary", key="dash_dl_html")
    d2.download_button("Upgrade ranking (CSV)", report.ranking_csv(ranking) if not ranking.empty else "",
                       file_name="accesstwin_upgrades.csv", mime="text/csv", key="dash_dl_csv")
    d3.download_button("Suppressed demand (CSV)", report.demand_csv(demand), file_name="accesstwin_demand.csv",
                       mime="text/csv", key="dash_dl_demand")
    st.caption("Open the HTML in a browser and print to PDF (Ctrl+P) to share — zero cost.")

    ui.disclaimer()


ui.run_page(main)
