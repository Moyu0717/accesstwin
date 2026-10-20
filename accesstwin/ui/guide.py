"""Guided 3-minute demo for judges exploring alone (P1-1).

A small step panel at the top of each page: Step n/5, what to look at, one "Do this" instruction and a
Next → button that pre-sets the right persona/inputs and opens the next page. Exit any time.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import streamlit as st

from accesstwin.core import store


@dataclass(frozen=True)
class Stop:
    page: str  # page file the stop belongs to
    script_step: int  # 1–5, as in the demo script
    title: str
    look: str
    do: str
    preset_next: dict = field(default_factory=dict)  # session-state values set before moving on
    reset_next: bool = False  # reset demo data before moving on


STOPS: list[Stop] = [
    Stop("pages/0_🏠_Overview.py", 1, "The problem",
         "The wheelchair and stroller scores are below 50, while elderly residents score higher.",
         "Read the Top 3 critical gaps on the right, then press Next.",
         {"persona": "wheelchair", "persona_select": "wheelchair", "rp_origin": "R1", "rp_dest": "D_CLINIC"}),
    Stop("pages/1_🧭_Route_Planner.py", 2, "Same trip, different people",
         "Block A → Clinic: the direct route is blocked for a wheelchair at E7 (15 cm step); the detour is 2.4× longer.",
         "Optional: switch the sidebar persona to Elderly to see the direct route work. Then press Next.",
         {"persona": "wheelchair", "persona_select": "wheelchair", "ro_src": "Use a sample photo", "ro_sample": "curb_high_step.png", "ro_edge": "E7"}),
    Stop("pages/2_📸_Report_Obstacle.py", 3, "Evidence: a resident reports it",
         "The sample kerb photo is classified as a high curb that needs on-site measurement.",
         "Press **Submit report**, then Next."),
    Stop("pages/3_✅_Verification_Queue.py", 3, "Evidence: a guard approves",
         "AI only suggests — a person decides. Approval marks the segment blocked for routing.",
         "Press **✅ Approve** on the E7 report, then Next."),
    Stop("pages/4_🎥_Footfall_Analytics.py", 3, "Evidence: suppressed demand",
         "Anonymous CCTV counts on E7 are far below what the model expects.",
         "Press **Run count**, scroll to 'Camera counts vs expected demand', then Next (this resets the demo data).",
         {"sim_selected": ["U1"], "sim_multiselect": ["U1"], "mode": "operate", "sim_mode": "operate"}, reset_next=True),
    Stop("pages/5_🏗️_Upgrade_Simulator.py", 4, "Decide what to fix first",
         "A low-cost kerb ramp (U1) lifts the wheelchair score and ranks first by benefit per cost tier.",
         "Look at the ROI ranking and the recommended package, then Next.",
         {"mode": "design", "dash_mode": "design"}),
    Stop("pages/6_📊_Planner_Dashboard.py", 5, "Scale: review before building",
         "Design mode adds pre-construction options; the Planning Brief summarises everything for a board or ESG report.",
         "Download the Planning Brief, then Finish."),
]


def queue_presets(values: dict) -> None:
    """Widget values can only be set before the widget is created, so presets wait for the next run."""
    st.session_state["guide_pending"] = {**st.session_state.get("guide_pending", {}), **values}


def apply_pending() -> None:
    """Called at the very start of every page (setup_page), before any widget exists."""
    pending = st.session_state.pop("guide_pending", None)
    if pending:
        st.session_state.update(pending)


def start() -> None:
    st.session_state["guide_step"] = 0
    queue_presets({"persona": "wheelchair", "persona_select": "wheelchair"})


def active() -> bool:
    return st.session_state.get("guide_step") is not None


def _go(page: str) -> None:
    try:
        st.switch_page(page)
    except Exception:  # page registry unavailable (a page run on its own, e.g. in tests)
        st.rerun()


def panel(page: str) -> None:
    """Render the guide panel if the guided demo is running and this page is the current stop."""
    i = st.session_state.get("guide_step")
    if i is None or not (0 <= i < len(STOPS)):
        return
    stop = STOPS[i]
    with st.container(border=True):
        if stop.page != page:
            st.markdown(f"**▶ Guided demo** — you are off the tour. Step {stop.script_step}/5 is on another page.")
            c1, c2 = st.columns(2)
            if c1.button("Back to the tour", key="guide_back", type="primary"):
                _go(stop.page)
            if c2.button("Exit guided demo", key="guide_exit_off"):
                st.session_state["guide_step"] = None
                st.rerun()
            return
        st.markdown(f"**▶ Guided demo · Step {stop.script_step}/5 — {stop.title}**")
        st.markdown(f"👀 {stop.look}  \n👉 **Do this:** {stop.do}")
        c1, c2 = st.columns([1, 1])
        last = i == len(STOPS) - 1
        if c1.button("Finish ✓" if last else "Next →", key="guide_next", type="primary"):
            if last:
                st.session_state["guide_step"] = None
                st.rerun()
            if stop.reset_next:
                store.reset_demo()
                st.cache_data.clear()
            queue_presets(stop.preset_next)
            st.session_state["guide_step"] = i + 1
            _go(STOPS[i + 1].page)
        if c2.button("Exit guided demo", key="guide_exit"):
            st.session_state["guide_step"] = None
            st.rerun()
