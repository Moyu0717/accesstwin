# AccessTwin — township accessibility digital twin (prototype)

AccessTwin combines resident/guard obstacle reports and the walkway network to tell a developer **which segment
to fix first, at what cost tier, and how many people gain access to which places** — for wheelchair users,
elderly residents, parents with strollers and visually impaired people.

Built for the Sime Darby Property University Hackathon "Township of Tomorrow" (People Track). Free, open-source
stack; the whole demo runs offline in **Mock mode** with no API keys. The township is a *fictional demo layout*.

## Run locally (Windows / PowerShell)
```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env            # optional; leave GEMINI_API_KEY empty for Mock mode
$env:ACCESSTWIN_MOCK="1"
.venv\Scripts\python.exe -m streamlit run app.py
```
macOS/Linux: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && ACCESSTWIN_MOCK=1 .venv/bin/streamlit run app.py`.

Map tiles come from OpenStreetMap (needs internet); everything else works offline.

## Test & validate
```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m accesstwin.core.validate
```

## What works today (M0–M4 + M8)
| Page | What it does |
|---|---|
| Home | Accessibility Gap Index (0–100) per persona, overview map, top 3 critical gaps |
| 🧭 Route Planner | Same trip, different personas: baseline (dashed) vs persona route (solid), detour ratio, covered share, unverified segments, reason card naming the blocking segment |
| 📸 Report Obstacle | Photo → AI suggestion (Mock by filename keyword; Gemini path coded but not yet verified) → choose segment → pending report |
| ✅ Verification Queue | Approve/Reject reports (approve = segment blocked via SQLite overlay); verify unverified segments on site |
| 🏗️ Upgrade Simulator | Combined what-if scenarios, before/after maps, Δindex, newly reachable trips, beneficiaries, plain-language explanation, ROI ranking (benefit ÷ cost tier), work orders, Operate/Design mode |

Not built yet: CCTV footfall counting (M6), suppressed-demand dashboard + Planning Brief export (M7), verified
Gemini integration (M5), cloud deployment (M9). See `docs/HANDOFF.md`.

## Demo
See [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md). Click **Reset demo data** in the sidebar before presenting.

## Principles
- Segment states: verified accessible / blocked / unverified (grey; excluded from routing by default).
- AI output is a suggestion pending human review — never a certification.
- CCTV (when built) produces aggregate counts only: no frames stored, no face recognition (PDPA).
- Costs are relative tiers (low/medium/high), never RM estimates.
- Planning aid only, not proof of compliance with accessibility standards (e.g. MS 1184). Verify on site.
