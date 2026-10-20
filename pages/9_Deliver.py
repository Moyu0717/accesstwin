"""Deliver — the study brief for the same Baseline / Scenario snapshot shown on Compare (HTML + CSV)."""
import csv
import io

import streamlit as st

from accesstwin.ui import cached
from accesstwin.ui import components as ui
from accesstwin.ui import guide
from accesstwin.ui import workspace as ws
from accesstwin.ui.i18n import t

PAGE = "pages/9_Deliver.py"
STEPS = [
    ("Confirm the existing condition", "Measure the step, clear width and slope on site."),
    ("Review the proposed change", "Check route continuity and engineering feasibility (design review)."),
    ("Construction", "Build the change; the recorded network is not updated yet."),
    ("Verify the completed work", "Record measured conditions before updating actual access (repair verification)."),
]


def main() -> None:
    ui.setup_page(t("stage_deliver"), "♿")
    persona = ui.sidebar(bar=False)
    ws.project_bar("deliver")
    guide.panel(PAGE)
    okey = ui.overlay_key()
    c = ws.ctx()
    loc = ws.find_location(okey, c["segment"])
    if loc is None:
        st.info("No priority location selected.")
        return
    version = cached.data_version(okey)
    st.markdown(f"<div class='at-eyebrow' style='display:flex;justify-content:space-between'>"
                f"<span>{ws.esc(t('deliver_title'))} / 01</span><span><span class='at-chip'>Draft</span> "
                f"<span class='at-chip sim'>Simulated</span> <span class='at-chip syn'>Synthetic</span></span></div>",
                unsafe_allow_html=True)
    st.markdown(f"<div class='at-h2'>{ws.esc(loc.label)} · intervention brief</div>", unsafe_allow_html=True)
    st.markdown("<div class='at-sub'>A concise record of the barrier, the proposed response and the next decision.</div>",
                unsafe_allow_html=True)
    rows = ws.compare_rows(okey, loc, persona.key)
    top = st.container()  # primary download sits above the fold; filled once the brief is built
    if rows:
        st.markdown(f"<div class='at-sub'><b>Conclusion (simulated):</b> {ws.esc(rows[0]['assessment'])} "
                    f"{ws.esc(rows[0]['baseline'])} → {ws.esc(rows[0]['scenario'])} ({ws.esc(rows[0]['change'])}).</div>",
                    unsafe_allow_html=True)
    for i, (head, body) in enumerate(STEPS, 1):
        st.markdown(f"<div class='at-section' style='display:flex;gap:18px'><span style='color:#8E4326'>{i:02d}</span>"
                    f"<div><b>{ws.esc(head)}</b><div class='at-muted'>{ws.esc(body)}</div></div></div>",
                    unsafe_allow_html=True)
    if rows:
        st.markdown(ws.rows_table_html(rows), unsafe_allow_html=True)
        st.markdown("<div class='at-mobile-only at-muted'>Swipe the table sideways to see every column.</div>",
                    unsafe_allow_html=True)
    else:
        st.info(f"{loc.label} ({loc.edge_id}): {t('not_assessed')} — confirm site conditions before a proposal.")
    st.markdown("<div class='at-section at-muted'><b>Assumptions.</b> Synthetic demo network; persona rules are demo "
                "assumptions, not design standards; costs are relative tiers only; scenario values are simulated and do "
                "not change the recorded network.</div>", unsafe_allow_html=True)

    scenario_section = {"location": f"{loc.label} ({loc.edge_id})", "upgrade": (loc.upgrade or {}).get("title"),
                        "rows": rows, "steps": STEPS, "version": version, "evidence": ws.evidence_thumbs(loc.edge_id)}
    html_doc = cached.brief_html(okey, ws.counts_key(), st.session_state.get("mode", "operate"),
                                 ws.reports_key(), ws.scenario_json(scenario_section))
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=["assessment", "baseline", "scenario", "change", "source"])
    w.writeheader()
    w.writerows(rows)
    top.download_button("Download study brief (HTML) ↓", html_doc, "accesstwin_study_brief.html", "text/html",
                        type="primary", key="dl_brief_top", use_container_width=True)
    d1, d2 = st.columns(2)
    d1.download_button("Download study brief (HTML) ↓", html_doc, "accesstwin_study_brief.html", "text/html",
                       type="primary", key="dl_brief", use_container_width=True)
    d2.download_button("Download comparison (CSV) ↓", buf.getvalue(), "accesstwin_comparison.csv", "text/csv",
                       key="dl_cmp_csv", use_container_width=True)
    st.caption(f"Local download · synthetic demo data · planning aid only · data version {version}.")
    ws.status_bar(bool(rows), version)
    ui.disclaimer()


ui.run_page(main)
