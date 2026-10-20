# Temporary start marker for the Streamlit Cloud log (ISSUE-1); remove once the live app is confirmed working.
print("AccessTwin app.py started", flush=True)

import streamlit as st

# Paint something immediately, before any heavy import, so the page is never blank (fix pack F2.3).
st.set_page_config(page_title="AccessTwin", page_icon="♿", layout="wide")
_loading = st.empty()
_loading.info("Loading AccessTwin demo…")

# Explicit navigation so the first item reads "Overview" (not the file name "app").
NAV = [
    ("pages/0_🏠_Overview.py", "Overview", "🏠"),
    ("pages/1_🧭_Route_Planner.py", "Route Planner", "🧭"),
    ("pages/2_📸_Report_Obstacle.py", "Report Obstacle", "📸"),
    ("pages/3_✅_Verification_Queue.py", "Verification Queue", "✅"),
    ("pages/4_🎥_Footfall_Analytics.py", "Footfall Analytics", "🎥"),
    ("pages/5_🏗️_Upgrade_Simulator.py", "Upgrade Simulator", "🏗️"),
    ("pages/6_📊_Planner_Dashboard.py", "Planner Dashboard", "📊"),
    ("pages/7_ℹ️_About.py", "About", "ℹ️"),
]
_page = st.navigation([st.Page(path, title=title, icon=icon, default=(i == 0))
                       for i, (path, title, icon) in enumerate(NAV)])
_loading.empty()
_page.run()
