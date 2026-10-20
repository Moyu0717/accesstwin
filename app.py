import streamlit as st

# Paint something immediately, before any heavy import, so the page is never blank (fix pack F2.3).
st.set_page_config(page_title="AccessTwin", page_icon="♿", layout="wide", initial_sidebar_state="collapsed")
_loading = st.empty()
_loading.info("Loading AccessTwin demo…")

from accesstwin.ui.i18n import t  # noqa: E402

# Routing only: the visible navigation is the V2 project bar (Network · Compare · Deliver + More), so the
# default page list is hidden. Titles follow the selected language.
NAV = [
    ("pages/0_🏠_Overview.py", "stage_network"),
    ("pages/8_Compare.py", "stage_compare"),
    ("pages/9_Deliver.py", "stage_deliver"),
    ("pages/1_🧭_Route_Planner.py", "nav_route"),
    ("pages/2_📸_Report_Obstacle.py", "nav_report"),
    ("pages/3_✅_Verification_Queue.py", "nav_queue"),
    ("pages/4_🎥_Footfall_Analytics.py", "nav_footfall"),
    ("pages/5_🏗️_Upgrade_Simulator.py", "nav_sim"),
    ("pages/6_📊_Planner_Dashboard.py", "nav_dash"),
    ("pages/7_ℹ️_About.py", "nav_about"),
]
_page = st.navigation([st.Page(path, title=t(key), default=(i == 0)) for i, (path, key) in enumerate(NAV)],
                      position="hidden")
_loading.empty()
_page.run()
