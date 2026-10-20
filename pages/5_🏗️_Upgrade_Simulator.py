import json

import plotly.express as px
import streamlit as st

from accesstwin.core import store
from accesstwin.core.graph import node_name
from accesstwin.core.simulation import available_upgrades, load_upgrades
from accesstwin.ui import cached
from accesstwin.ui import components as ui
from accesstwin.ui import guide
from accesstwin.ui.i18n import t
from accesstwin.ui.map_view import legend, show_map


@st.fragment
def scenario_panel(persona, mode: str) -> None:
    """Upgrade picker, metrics and the before/after map rerun on their own."""
    G = ui.graph()
    P = ui.personas()
    okey = ui.overlay_key()
    by_id = {u["id"]: u for u in available_upgrades(load_upgrades(), mode)}
    default = [u for u in st.session_state.get("sim_selected", ["U1"]) if u in by_id]

    left, right = st.columns([2, 5])
    with left:
        st.subheader("Candidate upgrades")
        selected = st.multiselect(
            "Select one or more (combined scenario)", list(by_id), default=default,
            format_func=lambda i: f"{i} · {by_id[i]['title']} [{by_id[i]['cost_tier']}]", key="sim_multiselect",
        )
        st.session_state["sim_selected"] = selected
        for uid in selected:
            st.caption(f"**{uid}** — {by_id[uid].get('rationale', '')}")

    with right:
        if not selected:
            st.info("Select at least one upgrade on the left to see the before/after comparison.")
            return
        chosen = [by_id[i] for i in selected]
        d, text = cached.scenario(okey, tuple(selected))

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Access Score", f"{d.index_after:.1f}", f"{d.index_delta:+.1f}")
        pdelta = d.persona_delta()
        m2.metric(f"{ui.persona_short(persona.key)} index", f"{d.persona_after[persona.key]:.0f}", f"{pdelta[persona.key]:+.1f}")
        m3.metric("Newly reachable (modelled)", len(d.newly_reachable))
        m4.metric("Estimated residents (model)", f"{d.beneficiaries:.0f}", help="population × vulnerable share, spread over the 4 personas")
        ui.card("💡 What changes", ui.esc(text) + f"<br><span class='at-muted'>⚠️ {t('onsite')}</span>", "good" if d.index_delta > 0 else "")

        changed = [u.get("edge_id") or u["new_edge"]["id"] for u in chosen]
        view = st.radio("Map", ["After", "Before"], horizontal=True, key="sim_view",
                        format_func=lambda v: "After (upgraded segments highlighted)" if v == "After" else "Before")
        if view == "After":
            show_map(height=400, overlay_key=okey, persona_key=persona.key, upgrades_key=json.dumps(selected),
                     highlight_key=json.dumps(changed), show_ids=st.session_state.get("show_ids", False), zoom=15)
        else:
            show_map(height=400, overlay_key=okey, persona_key=persona.key,
                     show_ids=st.session_state.get("show_ids", False), zoom=15)
        st.caption(legend())

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


def main() -> None:
    ui.setup_page(t("sim_title"), "🏗️")
    persona = ui.sidebar()
    upgrades = load_upgrades()

    st.title(f"🏗️ {t('sim_title')}")

    guide.panel("pages/5_🏗️_Upgrade_Simulator.py")
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

    by_id = {u["id"]: u for u in available_upgrades(upgrades, mode)}
    ui.bundle_card(cached.bundle(ui.overlay_key(), mode), "sim_bundle", allow_apply=True)
    scenario_panel(persona, mode)

    st.divider()
    st.subheader("Upgrade priority score ranking")
    st.caption("benefit = Δindex × 10 + newly reachable trips × 3 + beneficiaries ÷ 100;  upgrade priority score = benefit ÷ cost weight (low 1, medium 2.5, high 5).")
    df = cached.ranking(ui.overlay_key(), mode)
    if df.empty:
        st.info("No candidate upgrades for this mode.")
    else:
        fig = px.bar(df, x="roi", y="id", orientation="h", color="cost_tier", text="roi",
                     color_discrete_map={"low": "#16A34A", "medium": "#F59E0B", "high": "#DC2626"},
                     hover_data=["title", "delta_index", "new_reachable_pairs", "beneficiaries"])
        fig.update_layout(yaxis={"categoryorder": "total ascending"}, height=320, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, width="stretch")
        _top = df.iloc[0]
        st.caption(f"Chart summary: {_top['id']} ({_top['cost_tier']} cost) ranks first with priority score {_top['roi']:.1f}; "
                   f"{int((df['roi'] == 0).sum())} of {len(df)} candidates show no measurable access gain.")
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


ui.run_page(main)
