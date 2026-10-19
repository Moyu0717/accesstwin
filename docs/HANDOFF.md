# AccessTwin — Handoff (updated 2026-10-19 22:42)

## 1. One-paragraph status
M0 (skeleton), M1 (demo data + validator) and M2 (graph, personas, routing, Route Planner page, tests) are done and committed (`a9b3059`, `87e2cec`, `985bf07`). `pytest -q` passes 25/25 and the validator reports OK. `route()` is tested to block the wheelchair direct route R1 → clinic at E7 (15 cm step) and to return the persona detour as fallback; the Route Planner page itself is only smoke-tested (renders without exception). M3 (scoring, simulation, Upgrade Simulator) is in progress and has no files yet. The SQLite overlay in `store.py` exists, but the Report/Verification UI (M4) is not built. The home page `app.py` is still the M0 placeholder. Real Gemini (M5) and real CV (M6) are not implemented; the app runs in mock mode.

## 2. Milestone checklist
- [x] M0 — skeleton, requirements, config, docs templates, git init (`a9b3059`)
- [x] M1 — data (township 16 nodes / 24 edges, personas, 7 upgrades, 5 sample reports, 5 placeholder photos) + `validate.py` → OK (`87e2cec`)
- [x] M2 — `graph.py`, `personas.py`, `routing.py`, Route Planner page, tests: 25 passed (`985bf07`)
- [ ] M3 — `scoring.py`, `simulation.py`, Upgrade Simulator page: IN PROGRESS, no files yet
- [ ] M4 — `store.py` overlay + Report Obstacle + Verification Queue: PARTIAL (overlay and tables exist; UI and report→approve→reroute test not done)
- [ ] M5 — `obstacles.py` with Gemini (optional key): DEFERRED until after proposal, not started
- [ ] M6 — `footfall.py` + Footfall page: DEFERRED until after proposal, not started
- [ ] M7 — `demand.py` + Planner Dashboard + `report.py`: DEFERRED until after proposal, not started
- [ ] M8 — polish (theme, copy, empty states, error handling): PENDING
- [ ] M9 — deploy to Streamlit Community Cloud + README: DEFERRED until after proposal, not started

## 3. How to run
- Setup: `py -3.12 -m venv .venv`, then `.venv/Scripts/python.exe -m pip install -r requirements.txt`
- Run (mock mode, offline): PowerShell `$env:ACCESSTWIN_MOCK="1"`; cmd `set ACCESSTWIN_MOCK=1`; then `.venv/Scripts/python.exe -m streamlit run app.py`
- Test: `.venv/Scripts/python.exe -m pytest -q` (expect 25 passed)
- Validate data: `.venv/Scripts/python.exe -m accesstwin.core.validate` (expect `OK: ...`)
- Mock mode: on by default (`config.mock_mode()`); no API keys needed.
- Real Gemini (M5): NOT IMPLEMENTED. `.env.example` lists `GEMINI_API_KEY`; nothing reads it yet.
- Real CV (M6): NOT IMPLEMENTED. `requirements-cv.txt` exists but is not used by any module yet.
- Note: `python` is not on PATH on this machine; always use `.venv/Scripts/python.exe`.

## 4. Architecture map
- `accesstwin/config.py` — paths (`TOWNSHIP_PATH`, `DB_PATH`, …), `.env` loading, `mock_mode()`, routing penalties (`PENALTY_UNCOVERED` 0.30, `PENALTY_NO_TACTILE` 0.50, `PENALTY_CRACKED` 0.20), ROI coefficients and `COST_TIER_WEIGHTS`.
- `accesstwin/core/graph.py` — `load_township()`, `build_graph(data, overlay)` (NetworkX MultiGraph, `EDGE_DEFAULTS`), `load_graph(with_overlay)`, `find_edge()`, `set_edge_attrs()`, `residential_nodes()`, `destination_nodes()`, `categories()`, `node_name()`.
- `accesstwin/core/personas.py` — `Persona` dataclass, `load_personas()`, `get_persona()`.
- `accesstwin/core/routing.py` — `edge_passable()` (returns pass/fail plus the reason naming the edge), `edge_cost()`, `persona_subgraph()`, `baseline_route()` (unconstrained shortest by length), `route()` → `RouteResult` (`direct_reachable`, `reason`, `reachable`, `path`, `edges`, `length_m`, `detour_ratio`, `within_max_trip`, `unverified_edges`, `covered_ratio`).
- `accesstwin/core/store.py` — SQLite at `data/accesstwin.db` with tables `reports`, `verifications`, `footfall_runs`, `work_orders`; `init_db()`, `seed_sample_reports()`, `reset_demo()`, `add_report()`, `set_report_status()`, `list_reports()`, `add_verification()`, `get_overlay()` (latest event per edge wins; approved report → `blocked`, passable verification → `verified_accessible`), `add_work_order()`.
- `accesstwin/core/validate.py` — checks township / personas / upgrades / sample reports and the storyline; run as a module.
- `accesstwin/ui/components.py` — `setup_page()` (page config, `init_db()`, shared CSS), cached `personas()`.
- `accesstwin/ui/map_view.py` — folium map rendering (OpenStreetMap tiles).
- `accesstwin/ui/i18n.py` — all UI labels in `LABELS` (English only, `LANG = "en"`).
- `pages/1_🧭_Route_Planner.py` — Route Planner (M2).
- `app.py` — M0 placeholder home page.
- Tests: `tests/test_graph.py` (6 tests), `tests/test_routing.py` (storyline and persona rules), `tests/test_pages.py` (AppTest smoke per page), `tests/test_smoke.py`.

## 5. Data & assumptions
- Demo storyline: synthetic "Demo Township" (fictional, Elmina-style). Route A R1 → J1 → J3 → Clinic = 450 m via E7 (15 cm step). Wheelchair fallback Route B R1 → J2 → J5 → J6 → Clinic = 1,100 m (2.4×, uncovered).
- Persona rules (`data/personas.json`) are demo assumptions, not a design standard (MS 1184 is not implemented).
- Unverified edges are excluded by default; the `include_unverified` toggle includes them.
- Blocked edge E20 is not passable for any persona; broken surface E12 fails all four personas.
- Base JSON is never mutated; state changes go to the SQLite overlay.
- Sample reports and their 5 photos are synthetic placeholders.
- Footfall / CCTV data (M6) will be synthetic and aggregate-only.

## 6. Known issues & tech debt
- `app.py` home page is still the M0 skeleton.
- Route Planner map needs internet for OpenStreetMap tiles; routing logic works offline.
- `store.py` repeats `executescript(SCHEMA)` in most helpers; redundant, consolidate later.
- `.claude/agents/*` subagents only load in a new Claude Code session.
- `python` not on PATH; use `.venv/Scripts/python.exe`.
- Real Gemini (M5) and real CV (M6) not implemented.
- No browser-level check of the Route Planner UI; only AppTest smoke and HTTP 200 on `/`.

## 7. Next 3 tasks (priority order)
1. **M3 scoring + simulation** — write `accesstwin/core/scoring.py` (Accessibility Gap Index per persona) and `accesstwin/core/simulation.py` (apply an upgrade to a graph copy; index delta, new reachable pairs, ROI = benefit / cost tier weight). Acceptance: pytest proves applying U1 raises the wheelchair index and creates new reachable pairs > 0, and U1 ranks top 2 in ROI.
2. **M3 Upgrade Simulator page** — `pages/5_🏗️_Upgrade_Simulator.py`: select an upgrade, map recomputes, show index change and ROI ranking. Acceptance: `tests/test_pages.py` passes with the new page included and `pytest -q` stays green.
3. **M4 report → approve → reroute** — Report Obstacle form and Verification Queue (mock AI). Acceptance: a test shows report → approve → edge becomes `blocked` in `get_overlay()` → `route()` changes for the affected persona.

## 8. Notes for Codex
- Read AGENTS.md → spec Section 7 → last RUN_LOG entry first
- Do not change storyline data in data/ unless the task requires it
- Follow Section 0 constraints (free, mock always works, privacy)
