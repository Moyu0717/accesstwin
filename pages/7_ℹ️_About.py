"""About — the problem, how it works, who benefits, pilot, business model, privacy, limitations (P1-1)."""
import streamlit as st

from accesstwin.ui import components as ui
from accesstwin.ui import guide
from accesstwin.ui.i18n import t

FLOW_DOT = """
digraph G {
  rankdir=LR; bgcolor="transparent";
  node [shape=box, style="rounded,filled", fillcolor="#F0F7F6", color="#0F766E", fontname="sans-serif", fontsize=11];
  edge [color="#4B5563"];
  cctv [label="Anonymous CCTV\\nfootfall counts"];
  rep  [label="Resident & guard\\nobstacle reports\\n(AI suggests, people verify)"];
  net  [label="Walkway network\\n(segments + attributes)"];
  route [label="Persona routing\\nwheelchair · elderly ·\\nstroller · visually impaired"];
  gap  [label="Access Score\\n(0–100, higher is better)"];
  sup  [label="Suppressed demand\\n(people may not walk\\nhere because they can't)"];
  roi  [label="Upgrade priority score\\nbenefit ÷ cost tier"];
  wo   [label="Work orders →\\nfix → verify on site"];
  cctv -> sup; rep -> net; net -> route -> gap -> roi -> wo; sup -> roi; wo -> net [style=dashed, label=" updates"];
}
"""


def main() -> None:
    ui.setup_page("About", "ℹ️")
    ui.sidebar()
    st.title(f"ℹ️ {t('about_title')}")
    guide.panel("pages/7_ℹ️_About.py")

    st.markdown("""
**AccessTwin is a township's accessibility digital twin.** It combines anonymous CCTV footfall, resident and guard
obstacle reports and the walkway network to tell a developer **which segment to fix first, at what cost tier, and how
many people gain access to which places.**

### The problem
- A path on the map does not mean everyone can use it: one 15 cm step can cut a wheelchair user off from a clinic.
- Low footfall on a path is not proof it is unimportant — people may avoid it *because* they cannot use it.
- Fixes are usually chosen by complaint volume, not by who gains access and at what cost.
""")
    st.caption("We do not quote population statistics here until we have a sourced figure; the township and all numbers "
               "in this demo are fictional.")

    st.subheader("How it works")
    try:
        st.graphviz_chart(FLOW_DOT, width="stretch")
    except Exception:  # graphviz rendering unavailable — show the text version only
        pass
    st.caption("Text version: CCTV counts + obstacle reports + walkway network → persona routing → Access Score and "
               "suppressed demand → upgrade ranking by benefit per cost tier → work orders → on-site verification, "
               "which updates the network.")

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Who benefits")
        st.markdown("""
- Wheelchair users, elderly residents, parents with strollers, visually impaired people
- Temporarily injured residents and delivery workers
- *Design for those who find it hardest, and everyone benefits.*
""")
        st.subheader("Pilot plan")
        st.markdown("""
- 1 township, 2–3 main pedestrian corridors
- 1–2 existing CCTV cameras (with the property's authorisation)
- 4 weeks of guard-patrol and resident reporting
- Joint on-site validation with local disability and senior-citizen groups
""")
    with c2:
        st.subheader("Business model")
        st.markdown("""
- **Operate:** annual per-township subscription for property management (reports → work orders → verification)
- **Design:** per-project pre-construction review of draft masterplans — changing a drawing is cheaper than rebuilding a path
- Accessibility metrics that feed ESG / sustainability reporting; the same persona and scoring logic reused across townships
""")
        st.subheader("Privacy & PDPA")
        st.markdown(f"""
- {t('pdpa')}
- Photos: please avoid faces and licence plates. In this demo, photos are analysed by a demo classifier; with a
  configured Groq key, the resized photo and the prompt are sent to Groq for a suggestion.
- AI output is a suggestion pending human review — never a certification.
""")

    st.subheader("Limitations (honest list)")
    st.markdown("""
- The township, populations, camera counts and cost tiers are **fictional demo data**; persona rules are demo assumptions, not a design standard.
- Footfall sample results are **synthetic** until real CCTV runs are recorded.
- Validation with real users is **planned**, not done.
- Not proof of compliance with accessibility design standards (e.g. MS 1184); every route and upgrade needs on-site verification.
""")

    st.subheader("Accessibility of this app")
    st.markdown("""
- Map status uses a colour-blind-safe palette **and** a non-colour cue for every state (solid / dashed / dotted lines, ✖ on blocked segments).
- Every chart has a one-line text summary; photos have captions; all controls are standard keyboard-reachable widgets.
- Theme text colours are chosen for at least 4.5:1 contrast on white.
""")

    credits = ui.photo_credits()
    if credits:
        st.subheader("Photo credits")
        st.caption("Third-party editorial images used with credit for a non-commercial hackathon demo; faces and "
                   "licence plates blurred. Not licensed by AccessTwin — removed on request.")
        for name, c in credits.items():
            st.markdown(f"- {c['label']} — {c['source']} ({c['url']})")

    st.subheader("Team")
    st.caption("Team details to be added.")

    ui.disclaimer()


ui.run_page(main)
