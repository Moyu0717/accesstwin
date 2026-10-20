"""Overview — the default page (Accessibility Gap Index, map, critical gaps)."""
import streamlit as st

from accesstwin.core import store
from accesstwin.core.graph import node_name
from accesstwin.core.scoring import critical_gaps
from accesstwin.ui import cached
from accesstwin.ui import components as ui
from accesstwin.ui import guide
from accesstwin.ui.i18n import t
from accesstwin.ui.map_view import LEGEND_MD, pending_key, show_map


def main() -> None:
    ui.setup_page(t("home_title"), "♿")
    persona = ui.sidebar()
    G = ui.graph()
    P = ui.personas()
    okey = ui.overlay_key()
    s = cached.scores(okey)

    st.title(f"♿ {t('app_title')} — {t('home_title')}")

    guide.panel("pages/0_🏠_Overview.py")
    if not guide.active():
        g1, g2 = st.columns([1, 3])
        if g1.button("▶ Guided demo (3 min)", key="guide_start", type="primary",
                     help="A 5-step tour of the whole demo. Exit any time."):
            guide.start()
            st.rerun()
        g2.caption("New here? The guided demo walks you through the problem, the evidence, the decision and the "
                   "pre-construction review in about 3 minutes.")
    st.markdown(f"**{t('tagline')}**")
    st.caption(t("fictional"))

    top, cards = st.columns([1, 3])
    with top:
        st.metric("Gap Index", f"{s.index:.0f} / 100",
                  help="Weighted by population × vulnerable share × persona equity weight. 100 = every resident can reach "
                       "every key destination directly within a comfortable distance.")
        st.caption("“A path on the map doesn’t mean you can get there.”")
    with cards:
        cols = st.columns(len(P))
        for col, (key, p) in zip(cols, P.items()):
            col.metric(ui.persona_short(key), f"{s.persona_index[key]:.0f}", help=p.label)
        st.caption(t("persona_assumption"))

    left, right = st.columns([3, 2])
    with left:
        show_map(height=480, overlay_key=okey, persona_key=persona.key,
                 pending_key=pending_key(store.list_reports("pending")), show_ids=st.session_state.get("show_ids", False))
        st.caption(LEGEND_MD)
        st.caption(t("unverified_notice"))
    with right:
        st.subheader("🚧 Top 3 critical gaps")
        for i, g in enumerate(critical_gaps(s, G, P, top=3), 1):
            p = g["pair"]
            status = "unreachable" if p.reach == 0 else (
                "over comfortable distance" if p.reach < 1 else f"{p.detour_ratio:.1f}× detour")
            why = p.reason or "No passable path."
            ui.card(f"{i}. {ui.persona_label(p.persona)} · {node_name(G, p.residential)} → {p.category.replace('_', ' ')}",
                    f"<b>{status}</b> (score {p.score * 100:.0f}/100)<br><span class='at-muted'>{why}</span>", "bad")
        st.markdown("#### ▶️ Start the demo")
        ui.page_link("pages/1_🧭_Route_Planner.py", label="1 · Route Planner — same trip, different personas", icon="🧭")
        ui.page_link("pages/2_📸_Report_Obstacle.py", label="2 · Report Obstacle → Verification Queue — evidence", icon="📸")
        ui.page_link("pages/4_🎥_Footfall_Analytics.py", label="3 · Footfall Analytics — anonymous counts", icon="🎥")
        ui.page_link("pages/5_🏗️_Upgrade_Simulator.py", label="4 · Upgrade Simulator — what to fix first", icon="🏗️")
        ui.page_link("pages/6_📊_Planner_Dashboard.py", label="5 · Planner Dashboard — suppressed demand & Planning Brief", icon="📊")

    with st.expander("Gap matrix (residential × persona, 0–100)"):
        st.dataframe(s.gap_matrix(G), width="stretch")

    ui.disclaimer()


ui.run_page(main)
