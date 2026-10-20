# Temporary start marker for the Streamlit Cloud log (ISSUE-1); remove once the live app is confirmed working.
print("AccessTwin app.py started", flush=True)

import streamlit as st

# Paint something immediately, before any heavy import, so the page is never blank (fix pack F2.3).
st.set_page_config(page_title="AccessTwin", page_icon="♿", layout="wide")
_loading = st.empty()
_loading.info("Loading AccessTwin demo…")

from accesstwin.ui.i18n import t  # noqa: E402

# Explicit navigation so the first item reads "Overview" (not the file name "app"); titles follow the language.
NAV = [
    ("pages/0_🏠_Overview.py", "nav_overview", "🏠"),
    ("pages/1_🧭_Route_Planner.py", "nav_route", "🧭"),
    ("pages/2_📸_Report_Obstacle.py", "nav_report", "📸"),
    ("pages/3_✅_Verification_Queue.py", "nav_queue", "✅"),
    ("pages/4_🎥_Footfall_Analytics.py", "nav_footfall", "🎥"),
    ("pages/5_🏗️_Upgrade_Simulator.py", "nav_sim", "🏗️"),
    ("pages/6_📊_Planner_Dashboard.py", "nav_dash", "📊"),
    ("pages/7_ℹ️_About.py", "nav_about", "ℹ️"),
]
_page = st.navigation([st.Page(path, title=t(key), icon=icon, default=(i == 0))
                       for i, (path, key, icon) in enumerate(NAV)])
_loading.empty()
_page.run()
