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
         "Clinic approach (E7) is selected: the shortest reference path is interrupted by a raised step, and the "
         "wheelchair profile needs a much longer detour. The Access Score is lowest for wheelchair and stroller.",
         "Read the Inspector on the right, then press Next.",
         {"persona": "wheelchair", "persona_select": "wheelchair", "rp_origin": "R1", "rp_dest": "D_CLINIC"}),
    Stop("pages/1_🧭_Route_Planner.py", 2, "Same trip, different people",
         "Block A → Clinic: the direct route is blocked for a wheelchair at E7; the detour is about 2.4× longer.",
         "Optional: switch the sidebar profile to Older adult to see the direct route work. Then press Next.",
         {"persona": "wheelchair", "persona_select": "wheelchair", "ro_src": "Use an example photo",
          "ro_sample": "kerb_high_granite_step.jpg", "ro_edge": "E7"}),
    Stop("pages/2_📸_Report_Obstacle.py", 3, "Evidence: a resident reports it",
         "The location (E7) and the sample kerb photo are pre-filled. The photo is analysed only when you ask.",
         "Press **Analyse photo**, check the suggested category, press **Submit report** and note the receipt "
         "code, then Next."),
    Stop("pages/3_✅_Verification_Queue.py", 3, "Evidence: a guard approves",
         "AI only suggests — a person decides. Accepting confirms the step for the profiles it affects; it does "
         "not close the path for everyone.",
         "Open the E7 report and press **Accept for investigation**, then Next."),
    Stop("pages/4_🎥_Footfall_Analytics.py", 3, "Evidence: suppressed demand",
         "Anonymous CCTV counts on E7 are far below what the model expects.",
         "Press **Run count**, scroll to 'Camera counts vs expected demand', then Next (this resets the demo data).",
         {"cmp_view": "Scenario"}, reset_next=True),
    Stop("pages/8_Compare.py", 4, "Decide what to fix first",
         "Baseline vs a low-cost kerb ramp at E7 (simulated): Access Score, every profile, the journey distance and "
         "the cost tier in one aligned table.",
         "Switch the map between Baseline and Scenario, then Next."),
    Stop("pages/9_Deliver.py", 5, "Deliver the study",
         "The brief records the barrier, the proposed response and the next decisions for the same snapshot.",
         "Download the study brief, then Finish."),
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
                store.reset_demo()  # this session's sandbox only
            queue_presets(stop.preset_next)
            st.session_state["guide_step"] = i + 1
            _go(STOPS[i + 1].page)
        if c2.button("Exit guided demo", key="guide_exit"):
            st.session_state["guide_step"] = None
            st.rerun()
