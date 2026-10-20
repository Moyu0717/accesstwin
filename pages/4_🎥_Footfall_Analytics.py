import json

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from accesstwin import config
from accesstwin.core import footfall, store
from accesstwin.core.demand import demand_frame, suppressed_demand
from accesstwin.core.footfall import camera_counts
from accesstwin.core.graph import iter_edges
from accesstwin.ui import components as ui
from accesstwin.ui import guide
from accesstwin.ui.i18n import t


@st.fragment
def accuracy_panel(auto_total: int, default_manual: int) -> None:
    """Typing a manual count only reruns this panel."""
    st.subheader("Accuracy panel")
    manual = st.number_input("Manual count", min_value=0, step=1, key="ff_manual", value=default_manual)
    err = footfall.error_pct(auto_total, manual)
    if err is None:
        st.caption("Enter a manual count to see the error %.")
    else:
        st.metric("Error vs manual count", f"{err:.1f}%")
    st.caption("Occlusion and dense crowds cause under-counting; automated totals are a lower bound.")


def main() -> None:
    ui.setup_page("Footfall Analytics", "🎥")
    persona = ui.sidebar()
    G = ui.graph()

    ui.page_head(t('footfall_title'), eyebrow="Evidence · Footfall")

    guide.panel("pages/4_🎥_Footfall_Analytics.py")
    st.info("Aggregate counts only: no frames or crops are stored, no face recognition is used, and any real "
            "deployment needs property-owner authorisation. " + t("pdpa"))

    pre = footfall.load_precomputed()
    sample = pre["sample_clip"]
    live = footfall.cv_available()
    st.markdown("**Mode: Live CV**" if live else "**Mode: Precomputed sample results**")
    if pre.get("synthetic"):
        st.caption("Sample results are synthetic stand-ins. " + pre.get("note", ""))

    source = st.radio("Source", ["Sample clip", "Upload MP4"], horizontal=True, key="ff_source")
    is_sample = source == "Sample clip"
    upload = None
    if not is_sample:
        upload = st.file_uploader("Video file", type=["mp4", "mov", "avi"], key="ff_upload")
        if not live:
            st.warning("Live video analysis runs on the on-premise edge device; cloud demo shows sample results.")

    cam_edges = {}
    for e in iter_edges(G):
        if e.get("cctv_id"):
            cam_edges[e["cctv_id"]] = e["id"]
    labels = {cid: f"{cid} · {eid}" for cid, eid in sorted(cam_edges.items())}
    labels.setdefault(sample["cctv_id"], sample["cctv_id"])
    cam_ids = list(labels)
    c1, c2 = st.columns(2)
    line_frac = c1.slider("Counting line position (fraction of frame height)", 0.1, 0.9, 0.5, 0.05, key="ff_line")
    cam = c2.selectbox("Camera (linked segment)", cam_ids, index=cam_ids.index(sample["cctv_id"]),
                       format_func=lambda c: labels[c], key="ff_cam")

    if st.button("Run count", key="ff_run", type="primary"):
        res = None
        if is_sample:
            bar = st.progress(1.0, text="Loaded precomputed sample results")
            res = footfall.sample_result()
        elif upload is not None:
            bar = st.progress(0.0, text="Counting…")
            res = footfall.count_video(upload.getvalue(), line_y_frac=line_frac, name=upload.name)
            bar.progress(1.0, text="Done")
        else:
            st.warning("Upload a video first, or switch to the sample clip.")
        if res is not None:
            st.session_state["ff_result"] = res.to_dict()
            st.session_state["ff_is_sample"] = is_sample
            store.add_footfall_run(res.name, cam, res.inbound, res.outbound, json.dumps(res.buckets),
                                   int(sample["manual_count"]) if is_sample else None,
                                   0 if res.mode == "live" else 1)

    r = st.session_state.get("ff_result")
    if r:
        mode_label = {"live": "Live CV", "precomputed": "Precomputed sample results", "mock": "Mock"}[r["mode"]]
        st.markdown(f"**Mode: {mode_label}** · {r['name']}")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("In", r["in"])
        m2.metric("Out", r["out"])
        m3.metric("Total", r["total"])
        m4.metric("Frames processed", r["frames_processed"])
        st.caption(f"Effective rate {r['fps_effective']} fps. {r['occlusion_note']}")
        b = r["buckets"]
        xs = [f"{x['t_start_s']}-{x['t_start_s'] + footfall.BUCKET_S}s" for x in b]
        fig = go.Figure()
        fig.add_bar(x=xs, y=[x["in"] for x in b], name="In", marker_color="#0F766E")
        fig.add_bar(x=xs, y=[x["out"] for x in b], name="Out", marker_color="#B45309")
        fig.update_layout(barmode="group", height=300, margin=dict(l=10, r=10, t=40, b=10),
                          title="Crossings per 10-second bucket")
        st.plotly_chart(fig, width="stretch")
        st.caption(f"Chart summary: {r['in']} crossings in and {r['out']} out across {len(b)} ten-second buckets; "
                   f"busiest bucket {max(b, key=lambda x: x['in'] + x['out'])['t_start_s']} s.")

        accuracy_panel(r["total"], int(sample["manual_count"]) if st.session_state.get("ff_is_sample") else 0)

    st.image(str(config.VIDEOS_DIR / "sample_preview.png"), width="stretch")
    st.caption("Preview still (synthetic) — no frames are stored")

    runs = store.list_footfall_runs()
    if runs:
        st.subheader("Recent runs")
        df = pd.DataFrame(runs[::-1][:10])[["created_at", "video_name", "cctv_id", "total_in", "total_out", "manual_count", "mock"]]
        st.dataframe(df, width="stretch", hide_index=True)

    st.divider()
    st.subheader("Camera counts vs expected demand")

    _demand = suppressed_demand(ui.graph(), ui.personas(), camera_counts())
    for _d in [d for d in _demand if d.suppressed]:
        ui.card(f"Suppressed demand on {_d.edge_id} ({_d.cctv_id})",
                f"Observed {_d.observed:.0f} pedestrians/day vs about {_d.expected:.0f} expected from the gravity model "
                f"(ratio {_d.ratio:.2f}). The route has a barrier ({', '.join(_d.barrier_edges)}): "
                "people may not walk here because they can't.", "bad")
    st.dataframe(demand_frame(_demand), width="stretch", hide_index=True, column_config=ui.DEMAND_COLUMNS)
    st.caption("Daily counts per camera are synthetic demo figures until real CCTV runs are recorded. "
               "See the Planner Dashboard for the full analysis and the Planning Brief.")
    ui.page_link("pages/6_📊_Planner_Dashboard.py", label="Open the Planner Dashboard →")

    ui.disclaimer()


ui.run_page(main)
