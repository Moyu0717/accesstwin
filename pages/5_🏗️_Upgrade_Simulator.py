import json

import plotly.express as px
import streamlit as st
from streamlit_folium import st_folium

from accesstwin.core import store
from accesstwin.core.graph import node_name
from accesstwin.core.scoring import compute_scores
from accesstwin.core.simulation import (
    apply_upgrades, available_upgrades, compare, explain, load_upgrades, rank_upgrades,
)
from accesstwin.ui import components as ui
from accesstwin.ui.i18n import t
from accesstwin.ui.map_view import LEGEND_MD, base_map

ui.setup_page(t("sim_title"), "🏗️")
persona = ui.sidebar()
G = ui.graph()
P = ui.personas()
upgrades = load_upgrades()

st.title(f"🏗️ {t('sim_title')}")
mode = st.radio("Mode", ["operate", "design"], horizontal=True,
                index=["operate", "design"].index(st.session_state.get("mode", "operate")),
                format_func=lambda m: "Operate (existing township)" if m == "operate" else "Design (pre-construction review)",
                key="sim_mode")
st.session_state["mode"] = mode
if mode == "design":
    st.info("🏗️ **Pre-construction review** — design-only options (e.g. new link paths in a draft masterplan) are enabled. "
            "Changing a drawing is far cheaper than rebuilding a path.")
st.caption("Cost uses relative tiers only (low / medium / high) — never real RM construction costs. "
           "Simulated upgrades are assumed passable once built. " + t("onsite"))

overlay_key = json.dumps(store.get_overlay(), sort_keys=True)


@st.cache_data(show_spinner="Ranking every candidate upgrade…")
def ranking(overlay_key: str, mode: str):
    return rank_upgrades(ui.graph(), load_upgrades(), ui.personas(), mode=mode)


@st.cache_data(show_spinner=False)
def baseline_scores(overlay_key: str):
    return compute_scores(ui.graph(), ui.personas())


avail = available_upgrades(upgrades, mode)
by_id = {u["id"]: u for u in avail}
default = [u for u in st.session_state.get("sim_selected", ["U1"]) if u in by_id]

left, right = st.columns([1, 3])
with left:
    st.subheader("Candidate upgrades")
    selected = st.multiselect(
        "Select one or more (combined scenario)", list(by_id), default=default,
        format_func=lambda i: f"{i} · {by_id[i]['title']} [{by_id[i]['cost_tier']}]", key="sim_multiselect",
    )
    st.session_state["sim_selected"] = selected
    for uid in selected:
        u = by_id[uid]
        st.caption(f"**{uid}** — {u.get('rationale', '')}")

with right:
    if not selected:
        st.info("Select at least one upgrade on the left to see the before/after comparison.")
    else:
        chosen = [by_id[i] for i in selected]
        G2 = apply_upgrades(G, chosen)
        before = baseline_scores(overlay_key)
        d = compare(G, G2, P, before=before)
        title = chosen[0]["title"] if len(chosen) == 1 else f"Combined scenario ({', '.join(selected)})"
        text = explain(G2, d, P, d.reductions, title)

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Township index", f"{d.index_after:.1f}", f"{d.index_delta:+.1f}")
        pdelta = d.persona_delta()
        m2.metric(f"{ui.persona_label(persona.key)} index", f"{d.persona_after[persona.key]:.0f}", f"{pdelta[persona.key]:+.1f}")
        m3.metric("Newly reachable trips", len(d.newly_reachable))
        m4.metric("Est. beneficiaries", f"{d.beneficiaries:.0f}", help="population × vulnerable share, spread over the 4 personas")
        ui.card("💡 What changes", text + f"<br><span class='at-muted'>⚠️ {t('onsite')}</span>", "good" if d.index_delta > 0 else "")

        changed = [u.get("edge_id") or u["new_edge"]["id"] for u in chosen]
        b1, b2 = st.columns(2)
        with b1:
            st.markdown("**Before**")
            st_folium(base_map(G, persona, zoom=15), height=360, use_container_width=True, returned_objects=[], key="sim_before")
        with b2:
            st.markdown("**After** (upgraded segments highlighted)")
            st_folium(base_map(G2, persona, highlight_edges=changed, zoom=15), height=360, use_container_width=True,
                      returned_objects=[], key="sim_after")
        st.caption(LEGEND_MD)

        if d.newly_reachable:
            with st.expander(f"Newly reachable trips ({len(d.newly_reachable)})", expanded=True):
                st.dataframe([
                    {"from": node_name(G, x["residential"]), "persona": ui.persona_label(x["persona"]),
                     "destination": node_name(G, x["dest"]), "distance": ui.fmt_m(x["length_m"]), "before": x["before"]}
                    for x in d.newly_reachable
                ], hide_index=True, width="stretch")
        st.dataframe([{"persona": ui.persona_label(k), "before": round(d.persona_before[k], 1),
                       "after": round(d.persona_after[k], 1), "change": round(pdelta[k], 1)} for k in P],
                     hide_index=True, width="stretch")

st.divider()
st.subheader("📈 Upgrade ROI ranking")
st.caption("benefit = Δindex × 10 + newly reachable trips × 3 + beneficiaries ÷ 100;  ROI = benefit ÷ cost weight (low 1, medium 2.5, high 5).")
df = ranking(overlay_key, mode)
if df.empty:
    st.info("No candidate upgrades for this mode.")
else:
    fig = px.bar(df, x="roi", y="id", orientation="h", color="cost_tier", text="roi",
                 color_discrete_map={"low": "#16A34A", "medium": "#F59E0B", "high": "#DC2626"},
                 hover_data=["title", "delta_index", "new_reachable_pairs", "beneficiaries"])
    fig.update_layout(yaxis={"categoryorder": "total ascending"}, height=320, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, width="stretch")
    st.dataframe(df[["rank", "id", "title", "cost_tier", "delta_index", "new_reachable_pairs", "beneficiaries",
                     "avg_detour_reduction_m", "benefit", "roi"]], hide_index=True, width="stretch")
    with st.expander("Top 5 — plain-language explanations", expanded=False):
        for _, row in df.head(5).iterrows():
            st.markdown(f"**#{row['rank']} {row['id']}** — {row['explanation']}  \n_{t('onsite')}_")

    st.markdown("#### 🛠️ Create work order")
    c1, c2 = st.columns([3, 1])
    wo_target = c1.selectbox("Upgrade", df["id"].tolist(), format_func=lambda i: f"{i} · {by_id.get(i, {}).get('title', i)}",
                             key="sim_wo_target")
    if c2.button("Create work order", type="primary", key="sim_wo_btn"):
        oid = store.add_work_order(upgrade_id=wo_target)
        st.success(f"Work order #{oid} created for {wo_target} (status: open).")
    orders = store.list_work_orders()
    if orders:
        st.dataframe(orders, hide_index=True, width="stretch")

ui.disclaimer()
