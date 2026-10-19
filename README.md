# AccessTwin — township accessibility digital twin

[![tests](https://github.com/Moyu0717/accesstwin/actions/workflows/tests.yml/badge.svg)](https://github.com/Moyu0717/accesstwin/actions/workflows/tests.yml)

**Live demo:** _coming soon — Streamlit Community Cloud URL_ (no install, no API key needed)

AccessTwin is a township's "accessibility digital twin". It combines anonymous CCTV footfall, resident and guard
obstacle reports, and the walkway network to tell a developer **which segment to fix first, at what cost tier, and
how many people gain access to which places** — for wheelchair users, elderly residents, parents with strollers and
visually impaired people. It also finds *suppressed demand* (paths people avoid because they can't use them) and
reviews draft masterplans before anything is built. Built for the Sime Darby Property University Hackathon
"Township of Tomorrow" (People Track). The township is a **fictional demo layout**.

## Pages
| Page | What it shows |
|---|---|
| Home | Accessibility Gap Index (0–100) per persona, overview map, top 3 critical gaps |
| 🧭 Route Planner | Same trip, different personas; reason card names the blocking segment; detour and shade |
| 📸 Report Obstacle | Photo → AI suggestion (Groq vision, or the demo classifier without a key) → pending report |
| ✅ Verification Queue | Guard/admin approves or rejects; on-site verification of unverified segments |
| 🎥 Footfall Analytics | Anonymous CCTV counts (bundled sample results on the cloud), accuracy panel |
| 🏗️ Upgrade Simulator | What-if scenarios, before/after maps, ROI ranking by cost tier, work orders |
| 📊 Planner Dashboard | Gap heatmap, footfall heat layer, suppressed demand, Planning Brief (HTML/CSV) download |

Demo walkthrough: [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md). Screenshot checklist: [`docs/screenshots/`](docs/screenshots/README.md).

## Run locally
Windows / PowerShell:
```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m streamlit run app.py
```
macOS / Linux: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/streamlit run app.py`

Tests: `.venv\Scripts\python.exe -m pytest -q` · data check: `.venv\Scripts\python.exe -m accesstwin.core.validate`

## Enable real AI (Groq, free tier)
1. Create a key at https://console.groq.com/keys.
2. Locally: copy `.env.example` to `.env` and set `GROQ_API_KEY=...`. On Streamlit Cloud: *App settings → Secrets*
   (see `.streamlit/secrets.toml.example`).
3. Optional: `GROQ_VISION_MODEL` (default `qwen/qwen3.8-27b`, checked against Groq's vision docs on 2026-10-19).

Without a key — or with `ACCESSTWIN_MOCK=1` — the photo AI uses a demo classifier and the app works the same way.
Rate limits, timeouts or bad replies fall back to the demo classifier with a visible notice.

## Enable real CV counting (local only)
```powershell
.venv\Scripts\python.exe -m pip install -r requirements-cv.txt   # ultralytics, supervision, opencv (large: pulls torch)
.venv\Scripts\python.exe scripts\precompute_footfall.py path\to\clip.mp4   # refreshes data/footfall_precomputed.json
```
The cloud app never installs these; it shows the bundled sample results (currently **synthetic**) and Mock counts for uploads.

## Deployment
Hosted free on Streamlit Community Cloud from this repo (`main`, `app.py`). Every push to `main` redeploys.
Runtime data (reports, approvals, work orders) lives in a temporary SQLite file and **resets when the app restarts**
— fine for a demo; use **Reset demo data** to start fresh.

## Privacy & disclaimer
- CCTV analytics produce aggregate counts only: no frames stored, no face recognition, no cross-camera tracking.
  Connecting real cameras requires the property's authorisation (PDPA).
- Photos: avoid faces and licence plates. With Groq enabled, only the resized photo and the prompt are sent.
- AI output is a suggestion pending human review — never a certification. Segments stay *unverified* (grey) until checked on site.
- Costs are relative tiers (low/medium/high), never RM estimates. Persona rules are demo assumptions.
- AccessTwin is a planning aid, not proof of compliance with accessibility design standards (e.g. MS 1184).
