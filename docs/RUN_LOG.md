# AccessTwin — Run Log

Append-only. One entry per session / milestone (template: spec section 9.1).

## Session 1 — 2026-10-19 22:40 (agent: Claude Code, model: Claude Opus 5.5)
**Goal:** M0 — project skeleton
**Done:**
- Created `.claude/agents/` (data-builder, test-writer, cv-engineer, doc-logger), `requirements*.txt`, `.env.example`, `.gitignore`, `.streamlit/config.toml`, `CLAUDE.md`, `AGENTS.md`, `accesstwin/config.py`, blank `app.py`, `docs/` templates, `tests/` smoke test, `git init`.
- Python 3.12 venv in `.venv/` with all main requirements installed.
**Verified by:**
- `pytest -q` → 1 passed
- `streamlit run app.py --server.headless true --server.port 8599` → HTTP 200 on `/`, `/_stcore/health` = ok
**Not done / Blocked:**
- M1 data is being built in parallel by data-builder (not part of this commit).
**Bugs / Known issues:**
- `python` is not on PATH on this machine; use `.venv/Scripts/python.exe`.
**Subagents used:** data-builder → M1 data (running in background)
**Next step (exact):** Run `.venv/Scripts/python.exe -m accesstwin.core.validate` once M1 data lands.

## Session 1 (cont.) — 2026-10-19 22:42 (agent: Claude Code, model: Claude Opus 5.5 main + Haiku subagents)
**Goal:** M1 + M2
**Done:**
- M1 (commit `87e2cec`): `data/township.json` (16 nodes / 24 edges), `data/personas.json`, `data/upgrades.json` (7 upgrades), `data/sample_reports.json` (5 reports), `data/photos/` (5 placeholder images), `accesstwin/core/validate.py`.
- M2 (commit `985bf07`): `accesstwin/core/graph.py`, `accesstwin/core/personas.py`, `accesstwin/core/routing.py` (`route()` returns `direct_reachable` + `reason` for the blocked shortest route, and `reachable` for the persona detour), `accesstwin/core/store.py` (SQLite overlay; full M4 UI not yet built), `accesstwin/ui/components.py`, `accesstwin/ui/map_view.py`, `accesstwin/ui/i18n.py`, `pages/1_🧭_Route_Planner.py`, `tests/test_graph.py`, `tests/test_routing.py`, `tests/test_pages.py` (AppTest smoke test for every page).
- Map tiles switched from CartoDB to OpenStreetMap (CartoDB needs an API key).
**Verified by:**
- `.venv/Scripts/python.exe -m pytest -q` → 25 passed, 0 failed
- `.venv/Scripts/python.exe -m accesstwin.core.validate` → `OK: township, personas, upgrades and sample reports are valid and the storyline holds`
- `.venv/Scripts/python.exe -m streamlit run app.py --server.headless true --server.port 8599` (ACCESSTWIN_MOCK=1) → `/` HTTP 200, `/_stcore/health` = ok (checked 22:42; server stopped afterwards)
- `git log --oneline -15` → `985bf07` M2, `87e2cec` M1, `a9b3059` M0; `git status` → working tree clean at that point
**Not done / Blocked:**
- M3 (`scoring.py`, `simulation.py`, Upgrade Simulator page) in progress; no files written yet.
- M4 UI (Report Obstacle, Verification Queue) not built; the acceptance test for report → approve → blocked → reroute does not exist yet.
- M5, M6, M7, M9 deferred by the user until after the proposal; M8 polish pending.
- Map rendering in a browser was not verified (tiles need internet). Graph/routing logic runs offline.
**Bugs / Known issues:**
- `python` is not on PATH; use `.venv/Scripts/python.exe`.
- `.claude/agents/*` subagent files only load in a new Claude Code session; this session used generic subagents with the same instructions.
- folium CartoDB tiles need a key; switched to OpenStreetMap tiles (internet needed for map tiles).
- `app.py` is still the M0 skeleton home page.
- `store.py` runs `executescript(SCHEMA)` inside most helper functions; works, but is redundant and should be consolidated later.
**Subagents used:** data-builder → M1 data; test-writer → M2 tests
**Next step (exact):** Implement `accesstwin/core/scoring.py` and `accesstwin/core/simulation.py`, then `pages/5_🏗️_Upgrade_Simulator.py` (M3). Acceptance per spec section 7: applying U1 raises the wheelchair index and creates new reachable pairs > 0; U1 ranks top 2 in ROI. Prove both with pytest before claiming M3 done.

## Session 1 (cont. 2) — 2026-10-19 22:55 (agent: Claude Code, model: Claude Opus 5.5 main + Haiku subagents)
**Goal:** M3, M4, M8
**Done:**
- M3 (commit `125a528`): `accesstwin/core/scoring.py` (`compute_scores`, `pair_score`, `detour_penalty`, `critical_gaps`, `ScoreResult.gap_matrix`), `accesstwin/core/simulation.py` (`apply_upgrade(s)`, `compare` → `Delta`, `benefit`, `explain`, `rank_upgrades`), `pages/5_🏗️_Upgrade_Simulator.py`, home `app.py`. Data change: E16 (Block C → Junction 7) given `has_step: true, curb_height_cm: 12` (see DECISIONS).
- M4 (commit `807fd0e`): `accesstwin/core/store.py` overlay (derived from approved reports and verifications), `accesstwin/core/obstacles.py` (Mock AI by filename keyword; Gemini path coded but not verified), `pages/2_📸_Report_Obstacle.py`, `pages/3_✅_Verification_Queue.py`. Tests: `tests/test_store.py`, `tests/test_obstacles.py` (test-writer), `tests/test_ui_flow.py` (main agent: report → approve → E7 blocked → route recomputes through the real pages).
- M8 (commit `a08afc4`): map framing (`fit_bounds`, no scroll-zoom), shorter map labels, graph-load error handling, `docs/DEMO_SCRIPT.md`, `README.md`, `tests/test_demo_script.py` (demo script via Streamlit AppTest in Mock mode).
- Browser walk-through of Home, Route Planner, Report Obstacle, Verification Queue and Upgrade Simulator (operate + design) showed no errors after a server restart. Reported by the main agent; not re-run in this entry.
**Verified by:**
- `.venv/Scripts/python.exe -m pytest -q` → 89 passed, 0 failed (13.8 s)
- `.venv/Scripts/python.exe -m accesstwin.core.validate` → `OK: township, personas, upgrades and sample reports are valid and the storyline holds`
- `streamlit run app.py --server.headless true --server.port 8599` → `/` HTTP 200, `/_stcore/health` = `ok` (checked 22:5x; server stopped afterwards, port 8599 confirmed free)
- Numbers checked on a scratch DB (`ACCESSTWIN_DB` pointed to the session scratchpad, project `data/accesstwin.db` not touched): base index 56.1 (wheelchair 46.7, elderly 61.0, stroller 46.7, visually impaired 69.0); after seed overlay 54.6 (wheelchair 46.7, elderly 56.0, visually impaired 68.1); U1 rank 1 ROI 100.91 (Δindex +8.74, 4 new reachable pairs, 152 beneficiaries); U2 rank 2 ROI 77.28; U4 appears only in design mode (rank 3 there, ROI 60.74).
- `git log --oneline -15` → `a08afc4` M8, `807fd0e` M4, `125a528` M3, `828c5ab` docs, `985bf07` M2, `87e2cec` M1, `a9b3059` M0
- `git status` → on branch `master`, working tree clean (before this log entry)
**Not done / Blocked:**
- M5 (Gemini verification with a real key): not started. Needs a free AI Studio key from the user; no key is in `.env`.
- M6 (footfall / CV, `footfall.py` + Footfall page): not started. Owner: cv-engineer.
- M7 (`demand.py`, Planner Dashboard, `report.py` export): not started. Deferred by the user until after the proposal.
- M9 (deploy to Streamlit Community Cloud): not started. Deferred by the user.
- Demo script steps that need Footfall or Dashboard are marked "(after M6/M7)" in `docs/DEMO_SCRIPT.md`.
**Bugs / Known issues:**
- One test-writer run saw `tests/test_ui_flow.py` fail once while the main agent was editing pages mid-run. Four later full runs passed, and the full run in this entry passed (89/89). Not reproduced.
- A running Streamlit server does not always reload edited helper modules. Restart it after edits.
- Map tiles need internet (OpenStreetMap); routing and scoring work offline.
- Gemini path in `obstacles.py` is unverified (M5). Mock mode is the only verified AI path.
- `store.py` still calls `executescript(SCHEMA)` in 9 places (redundant; consolidate later).
- `python` is not on PATH; use `.venv/Scripts/python.exe`.
- `.claude/agents/*` load only in a new Claude Code session.
- No pages 4 (Footfall) and 6 (Dashboard) yet.
**Subagents used:** test-writer → M3 tests, M4 tests; doc-logger → this log and `docs/HANDOFF.md`
**Next step (exact):** Put a free AI Studio key in `.env` (`GEMINI_API_KEY`, `GEMINI_MODEL`, `ACCESSTWIN_MOCK=0`), restart Streamlit, and run Report Obstacle on `data/photos/curb_high_step.png`. Confirm the returned JSON is valid (M5). Then start M6 with cv-engineer.
