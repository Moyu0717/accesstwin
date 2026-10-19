# AccessTwin — 3-Minute Demo Script (Mock mode)

Setup (once): `$env:ACCESSTWIN_MOCK="1"; .venv\Scripts\python.exe -m streamlit run app.py`, then click
**Reset demo data** in the sidebar so the queue starts from the seed reports.

> Scope note: this version covers milestones M0–M4 + M8. Footfall analytics / suppressed demand (M6) and the
> Planner Dashboard + Planning Brief export (M7) are not built yet; the steps that need them are marked
> *(after M6/M7)* and have a fallback line you can say instead.

| Time | Page | Do | Say |
|---|---|---|---|
| 0:00–0:30 | **Home** | Point at the persona cards: wheelchair ≈ 47, stroller ≈ 47 vs elderly ≈ 56. Hover the map: grey dashed = unverified, red = blocked. | "A path on the map doesn't mean you can get there. Our township scores 55 overall, but under 50 for wheelchair users." |
| 0:30–1:00 | **Route Planner** | Persona **Elderly**, Block A → Clinic: direct, 450 m. Switch the sidebar persona to **Wheelchair user**. | "Same trip. The reason card points to E7, a 15 cm step at the clinic entrance. The fallback Route B is 1.1 km — 2.4× longer, and 0% covered from sun and rain." |
| 1:00–1:30 | **Report Obstacle → Verification Queue** | Use sample photo `curb_high_step.png` → AI flags *high curb*, "needs on-site measurement: curb height, slope". Choose segment E7, submit. Open the queue, show the pending card, **Approve**. | "The AI only suggests. A guard approves, and only then does the twin change — every route recomputes instantly." *(after M6: "and the CCTV on E7 shows far fewer people than expected — suppressed demand.")* |
| 1:30–2:30 | **Upgrade Simulator** | Click **Reset demo data** first (so E7 is not blocked). U1 is preselected: township index 55 → 63, wheelchair 47 → 64, 4 newly reachable trips, ≈150 residents benefit. Scroll to the ROI chart: U1 ranks #1, the covered walkway U3 scores 0. | "A low-cost kerb ramp beats an expensive covered walkway. We rank every fix by benefit ÷ cost tier — never fake RM figures — and every result says it needs on-site verification." Click **Create work order**. |
| 2:30–3:00 | **Upgrade Simulator (Design mode)** | Switch Mode to **Design (pre-construction review)**: U4 "new link path through park" appears and ranks #3. *(after M7: Dashboard → export Planning Brief.)* | "For new phases, we review the masterplan before it is built — changing a drawing is far cheaper than rebuilding a path. Build a township that works for everyone." |

## Key numbers (after Reset demo data — seed reports block E20 and E21)
- Township index 54.6; wheelchair 46.7, elderly 56.0, stroller 46.7, visually impaired 68.1 (base JSON without the seed overlay: 56.1).
- Route A (R1 → clinic) 450 m via E7; wheelchair Route B 1,100 m (2.44×), uncovered.
- U1 (low): Δindex +8.7, 4 newly reachable trips, ~152 beneficiaries, ROI ≈ 101 (#1). U2 (medium) ROI ≈ 77 (#2).

Numbers shift slightly after approving reports or verifying segments; **Reset demo data** restores them.
