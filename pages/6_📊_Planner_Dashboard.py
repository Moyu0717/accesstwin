import json

import pandas as pd
import plotly.express as px
import streamlit as st

from accesstwin import config
from accesstwin.core import report, store
from accesstwin.core.demand import demand_frame
from accesstwin.core.graph import find_edge, node_name
from accesstwin.ui import cached
from accesstwin.ui import components as ui
from accesstwin.ui import guide
from accesstwin.ui.map_view import show_map


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


    st.title("📊 Planner Dashboard")


    guide.panel("pages/6_📊_Planner_Dashboard.py")
    mode = st.radio("Mode", ["operate", "design"], horizontal=True,
                    index=["operate", "design"].index(st.session_state.get("mode", "operate")),
                    format_func=lambda m: "Operate (existing township)" if m == "operate" else "Design (pre-construction review)",
                    key="dash_mode")
    st.session_state["mode"] = mode
    if mode == "design":
        st.info("🏗️ **Pre-construction review** — gaps found here can be fixed on the drawing, before anything is built. "
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
    k1.metric("Gap Index", f"{scores.index:.0f} / 100")
    k2.metric("Suppressed-demand segments", len(sup))
    k3.metric("Open reports", sum(1 for r in reports if r["status"] == "pending"))
    k4.metric("Work orders", len(store.list_work_orders()))

    left, right = st.columns([3, 2])
    with left:
        st.subheader("🗺️ Footfall heat layer")
        peak = max([d.observed for d in demand if d.observed] or [1])
        circles = [[d.edge_id, 6 + 22 * d.observed / peak, "#DC2626" if d.suppressed else "#2563EB",
                    f"{d.cctv_id} on {d.edge_id}: observed {d.observed:.0f} vs expected {d.expected or 0:.0f} — {d.status}"]
                   for d in demand if d.observed is not None]
        show_map(height=430, overlay_key=okey, persona_key=persona.key, circles_key=json.dumps(circles),
                 show_ids=st.session_state.get("show_ids", False), zoom=15)
        st.caption("Circle size = observed footfall (aggregate counts only). 🔴 suppressed demand · 🔵 as expected. "
                   f"Counts source: {counts_src}.")
    with right:
        st.subheader("🚷 Suppressed demand")
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

    st.subheader("🔥 Gap heatmap (residential × persona)")
    gm = scores.gap_matrix(G)
    gm.columns = [ui.persona_short(c) for c in gm.columns]
    fig = px.imshow(gm, text_auto=".0f", zmin=0, zmax=100, color_continuous_scale="RdYlGn", aspect="auto")
    fig.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, width="stretch")
    _low = gm.stack().idxmin()
    st.caption(f"Heatmap summary: lowest score {gm.stack().min():.0f}/100 for {_low[1]} at {_low[0]}; "
               f"highest {gm.stack().max():.0f}/100. Higher is better.")

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("📥 Report statistics")
        stats = report.report_stats(reports)
        if stats["total"]:
            df = pd.DataFrame([{"obstacle type": k.replace("_", " "), "reports": v} for k, v in stats["by_type"].items()])
            st.plotly_chart(px.bar(df, x="obstacle type", y="reports", height=260), width="stretch")
            _most = df.sort_values("reports", ascending=False).iloc[0]
            st.caption(f"Chart summary: {stats['total']} reports; most common type: {_most['obstacle type']} ({_most['reports']}).")
            st.caption("By status: " + ", ".join(f"{k} {v}" for k, v in stats["by_status"].items())
                       + " · by reporter: " + ", ".join(f"{k} {v}" for k, v in stats["by_role"].items()))
        else:
            st.info("No reports yet.")
    with c2:
        st.subheader("🏆 Top 5 upgrades")
        if ranking.empty:
            st.info("No candidate upgrades for this mode.")
        else:
            st.dataframe(ranking.head(5)[["rank", "id", "title", "cost_tier", "delta_index", "roi"]], hide_index=True, width="stretch")

    st.subheader("📄 Export Planning Brief")
    html_doc = cached.brief_html(okey, counts_key, mode, json.dumps([[r['id'], r['status']] for r in reports]))
    d1, d2, d3 = st.columns(3)
    d1.download_button("⬇️ Planning Brief (HTML)", html_doc, file_name="accesstwin_planning_brief.html",
                       mime="text/html", type="primary", key="dash_dl_html")
    d2.download_button("⬇️ Upgrade ranking (CSV)", report.ranking_csv(ranking) if not ranking.empty else "",
                       file_name="accesstwin_upgrades.csv", mime="text/csv", key="dash_dl_csv")
    d3.download_button("⬇️ Suppressed demand (CSV)", report.demand_csv(demand), file_name="accesstwin_demand.csv",
                       mime="text/csv", key="dash_dl_demand")
    st.caption("Open the HTML in a browser and print to PDF (Ctrl+P) to share — zero cost.")

    ui.disclaimer()


ui.run_page(main)
