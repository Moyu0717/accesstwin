# AccessTwin — 3-Minute Demo Script

Works on the live Streamlit Cloud app with **no API key** (photo AI uses the demo classifier, footfall uses the
bundled sample results). Locally: `.venv\Scripts\python.exe -m streamlit run app.py`.

## Before you present
- [ ] Open the app URL **5 minutes early**. The free app sleeps when idle — if you see
      "This app has gone to sleep", click **Yes, get this app back up** and wait for it to load.
- [ ] Press **Reset demo data** in the sidebar (restores the seeded reports; runtime data also resets whenever the app restarts).
- [ ] Select the **Wheelchair user** persona in the sidebar.
- [ ] Use a wide browser window (≥ 1280 px) so the metric cards are not truncated.

## Script

| Time | Page | Do | Say |
|---|---|---|---|
| 0:00–0:30 | **Home** | Point at the persona cards: wheelchair ≈ 47, stroller ≈ 47 vs elderly ≈ 56. Hover the map: grey dashed = unverified, red = blocked. | "A path on the map doesn't mean you can get there. Our township scores 55 overall, but under 50 for wheelchair users." |
| 0:30–1:00 | **Route Planner** | Block A → Clinic. Switch the sidebar persona to **Elderly**: direct, 450 m. Back to **Wheelchair user**. | "Same trip. The reason card points to E7, a 15 cm step at the clinic entrance. The fallback Route B is 1.1 km — 2.4× longer, and 0% covered from sun and rain." |
| 1:00–1:30 | **Report Obstacle → Verification Queue → Footfall Analytics** | Report Obstacle: *Use a sample photo* → `curb_high_step.png` → AI flags *high curb*, "needs on-site measurement: curb height, slope" → segment E7 → Submit. Verification Queue: **Approve**. Footfall Analytics: *Sample clip* → **Run count**, then scroll to "Camera counts vs expected demand". | "The AI only suggests; a guard approves, and only then does the twin change. CCTV gives anonymous counts only — and the camera on E7 sees 40 people a day where our model expects about 550: suppressed demand. Low traffic doesn't mean unimportant — people may not walk here because they can't." |
| 1:30–2:30 | **Upgrade Simulator** | Press **Reset demo data** first (so E7 is not blocked). U1 is preselected: township index 55 → 63, wheelchair 47 → 64, 4 new trips, ≈150 beneficiaries. Scroll to the ROI chart: U1 ranks #1, the covered walkway U3 scores 0. Click **Create work order**. | "A low-cost kerb ramp beats an expensive covered walkway. We rank every fix by benefit ÷ cost tier — never fake RM figures — and every result says it needs on-site verification." |
| 2:30–3:00 | **Planner Dashboard** | Show the gap heatmap and the red suppressed-demand circle on E7. Switch Mode to **Design (pre-construction review)** — U4 "new link path through park" joins the ranking. Click **Planning Brief (HTML)** and open the download. | "For new phases, we review the masterplan before it is built — changing a drawing is far cheaper than rebuilding a path. One click exports a Planning Brief for the board or ESG report. Build a township that works for everyone." |

## Key numbers (after Reset demo data — seed reports block E20 and E21)
- Township index 54.6; wheelchair 46.7, elderly 56.0, stroller 46.7, visually impaired 68.1 (base JSON without the seed overlay: 56.1).
- Route A (R1 → clinic) 450 m via E7; wheelchair Route B 1,100 m (2.44×), uncovered.
- U1 (low): Δindex +8.7, 4 newly reachable trips, ~152 beneficiaries, ROI ≈ 101 (#1). U2 (medium) ROI ≈ 77 (#2).
- Suppressed demand: E7 / CAM_02 observed 40 vs expected ≈ 550 (ratio ≈ 0.07). Camera counts are synthetic demo figures.

Numbers shift slightly after approving reports or verifying segments; **Reset demo data** restores them.
