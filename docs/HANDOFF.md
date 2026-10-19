# AccessTwin — Handoff (updated 2026-10-19 22:55)

## 1. One-paragraph status
M0–M4 and M8 are done and committed (`a9b3059`, `87e2cec`, `985bf07`, `125a528`, `807fd0e`, `a08afc4`). `pytest -q` → 89 passed, 0 failed; `accesstwin.core.validate` → OK; Streamlit headless serves `/` with HTTP 200 and `/_stcore/health` = ok. The app runs fully in Mock mode (no keys): Home (Gap Index), Route Planner, Report Obstacle, Verification Queue and Upgrade Simulator (Operate and Design modes). Approving a report blocks its segment through the SQLite overlay, and routes recompute. The 3-minute demo script (`docs/DEMO_SCRIPT.md`) runs end-to-end in Mock mode, except the steps marked "(after M6/M7)". Not built: real Gemini verification (M5), footfall/CCTV counting (M6), suppressed-demand dashboard and Planning Brief export (M7), and deployment (M9). The Gemini code path exists in `obstacles.py` but has never been run against the real API.

## 2. Milestone checklist
- [x] M0 — skeleton, requirements, config, docs templates, git init (`a9b3059`)
- [x] M1 — township (16 nodes / 24 edges), personas, 7 upgrades, 5 sample reports, 5 placeholder photos, `validate.py` → OK (`87e2cec`)
- [x] M2 — graph, personas, routing (direct vs detour), Route Planner, tests (`985bf07`)
- [x] M3 — `scoring.py`, `simulation.py`, Upgrade Simulator page, home overview; U1 ranks #1 by ROI (≈101), U2 #2 (≈77) (`125a528`)
- [x] M4 — SQLite overlay (`store.py`), Mock AI (`obstacles.py`), Report Obstacle and Verification Queue pages; report → approve → E7 blocked → route recomputes (`807fd0e`)
- [ ] M5 — `obstacles.py` with Gemini (optional key): NOT STARTED. Code path exists but is unverified; needs a free AI Studio key.
- [ ] M6 — `footfall.py` + Footfall page: NOT STARTED (cv-engineer). No pages/4 yet.
- [ ] M7 — `demand.py` + Planner Dashboard + `report.py` export: NOT STARTED. No pages/6 yet. Deferred until after the proposal.
- [x] M8 — polish: map framing, shorter labels, graph-load error handling, `docs/DEMO_SCRIPT.md`, `README.md`, `tests/test_demo_script.py` (`a08afc4`)
- [ ] M9 — deploy to Streamlit Community Cloud + README: NOT STARTED. Deferred until after the proposal.

## 3. How to run
- Setup: `py -3.12 -m venv .venv`, then `.venv/Scripts/python.exe -m pip install -r requirements.txt`
- Run (Mock mode, offline): PowerShell `$env:ACCESSTWIN_MOCK="1"; .venv/Scripts/python.exe -m streamlit run app.py`. Cmd: `set ACCESSTWIN_MOCK=1` first. Click **Reset demo data** in the sidebar before a demo.
- Test: `.venv/Scripts/python.exe -m pytest -q` (last run: 89 passed)
- Validate data: `.venv/Scripts/python.exe -m accesstwin.core.validate` (last run: `OK: ...`)
- Mock mode: on by default (`config.mock_mode()`); no API keys needed. Map tiles need internet.
- Real Gemini (M5): NOT VERIFIED. `.env.example` has `GEMINI_API_KEY`, `GEMINI_MODEL=gemini-2.5-flash`, `ACCESSTWIN_MOCK=1`. The planned check is to set `GEMINI_API_KEY`, `GEMINI_MODEL`, `ACCESSTWIN_MOCK=0` and analyse `data/photos/curb_high_step.png`.
- Real CV (M6): NOT IMPLEMENTED. `requirements-cv.txt` exists but no module imports it.
- Note: `python` is not on PATH on this machine; always use `.venv/Scripts/python.exe`.

## 4. Architecture map
- `app.py` — home page: Gap Index (0–100) and per-persona scores, overview map, top 3 critical gaps (`scores()` → `compute_scores`, `critical_gaps`).
- `accesstwin/config.py` — paths (`TOWNSHIP_PATH`, `DB_PATH` via `ACCESSTWIN_DB`, `PHOTOS_DIR`), `.env` loading, `GEMINI_API_KEY`/`GEMINI_MODEL`, `mock_mode()`, routing penalties (`PENALTY_UNCOVERED` 0.30, `PENALTY_NO_TACTILE` 0.50, `PENALTY_CRACKED` 0.20), benefit coefficients and `COST_TIER_WEIGHTS` (low 1.0, medium 2.5, high 5.0).
- `accesstwin/core/graph.py` — `load_township()`, `build_graph(data, overlay)` (NetworkX MultiGraph), `load_graph(with_overlay)`, `find_edge()`, `set_edge_attrs()`, `iter_edges()`, `residential_nodes()`, `destination_nodes()`, `categories()`, `node_name()`.
- `accesstwin/core/personas.py` — `Persona` dataclass, `load_personas()`, `get_persona()`.
- `accesstwin/core/routing.py` — `edge_passable()` (pass/fail plus the reason naming the edge), `edge_cost()`, `persona_subgraph()`, `baseline_route()` (shortest by length), `route()` → `RouteResult` (`direct_reachable`, `reason`, `reachable`, `path`, `edges`, `length_m`, `detour_ratio`, `within_max_trip`, `unverified_edges`, `covered_ratio`).
- `accesstwin/core/scoring.py` — Accessibility Gap Index: `compute_scores()` → `ScoreResult` (`index`, `persona_index`, `node_persona`, `pairs`, `gap_matrix()`, `unreachable_pairs`), `pair_score()`, `detour_penalty()`, `vulnerable_population()`, `critical_gaps()`.
- `accesstwin/core/simulation.py` — `load_upgrades()`, `available_upgrades()` (Operate hides design-only), `apply_upgrade(s)` (graph copy; simulated edges get `verified_accessible`), `compare()` → `Delta`, `benefit()` (Δindex×10 + new pairs×3 + beneficiaries/100), `explain()`, `rank_upgrades()` (ROI = benefit ÷ cost weight).
- `accesstwin/core/store.py` — SQLite at `data/accesstwin.db`, tables `reports`, `verifications`, `footfall_runs`, `work_orders`. `init_db()`, `seed_sample_reports()`, `reset_demo()`, `add_report()`, `set_report_status()`, `list_reports()`, `add_verification()`, `list_verifications()`, `get_overlay()` (latest event per edge wins; approved report → blocked; passable verification → verified_accessible), `add_work_order()`, `set_work_order_status()`, `list_work_orders()`.
- `accesstwin/core/obstacles.py` — `analyze_photo()` (Gemini or Mock), `mock_analyze()` (filename keyword), `parse_ai_json()`, `_gemini_call()` (coded, unverified), `OBSTACLE_TYPES`, `SEVERITIES`, `PERSONA_KEYS`, `PROMPT`.
- `accesstwin/core/validate.py` — `validate_all()` and `main()`; checks township, personas, upgrades, sample reports and the storyline.
- `accesstwin/ui/components.py` — `setup_page()`, `sidebar()` (persona picker), `graph()`, `personas()`, `card()`, `disclaimer()`, `fmt_m()`, `page_link()`.
- `accesstwin/ui/map_view.py` — `base_map()` (folium, OpenStreetMap tiles, fit_bounds), `add_route()`, `edge_line()`, `LEGEND_MD`, status colours (verified green, blocked red, unverified grey).
- `accesstwin/ui/i18n.py` — `t(key)` and `LABELS` (English only, `LANG = "en"`).
- `pages/1_🧭_Route_Planner.py` — same trip, different personas; baseline vs persona route, reason card naming the blocking segment.
- `pages/2_📸_Report_Obstacle.py` — photo → AI suggestion → choose segment → pending report.
- `pages/3_✅_Verification_Queue.py` — approve/reject reports; verify unverified segments on site; shows impact on routes (`impact_text()`).
- `pages/5_🏗️_Upgrade_Simulator.py` — Operate/Design modes, before/after map, Δindex, newly reachable trips, beneficiaries, ROI chart, work orders (`ranking()`, `baseline_scores()`).
- Missing for now: `pages/4_*` (Footfall, M6) and `pages/6_*` (Dashboard, M7); `footfall.py`, `demand.py`, `report.py` do not exist.
- Tests: `test_graph.py`, `test_routing.py`, `test_scoring.py`, `test_simulation.py`, `test_store.py`, `test_obstacles.py`, `test_pages.py` (AppTest smoke per page), `test_ui_flow.py` (report → approve → reroute), `test_demo_script.py` (demo script in Mock mode), `test_smoke.py`.

## 5. Data & assumptions
- Demo storyline: synthetic "Demo Township" (fictional, Elmina-style). Route A R1 → J1 → J3 → Clinic = 450 m via E7 (15 cm step). Wheelchair Route B R1 → J2 → J5 → J6 → Clinic = 1,100 m (2.4×, uncovered). E16 has a 12 cm curb, so Block C wheelchair trips to the clinic are 1.56 km, above the 1.5 km max trip.
- Seed reports (`data/sample_reports.json`) are approved on first init and block E20 and E21. "Reset demo data" wipes the 4 tables and re-seeds.
- After Reset demo data (seeded overlay): township index 54.6; wheelchair 46.7, elderly 56.0, stroller 46.7, visually impaired 68.1. Base JSON without overlay: 56.1 (elderly 61.0, visually impaired 69.0). Verified this session on a scratch DB.
- U1 (low cost): Δindex +8.74, 4 newly reachable pairs, 152 beneficiaries, ROI 100.91, rank #1. U2 (medium): ROI 77.28, rank #2. U4 (design mode only): rank #3 in design mode. U3 scores 0.
- Persona rules (`data/personas.json`) are demo assumptions, not a design standard. MS 1184 is not implemented.
- Cost tiers are relative (low/medium/high), never RM estimates.
- Newly reachable pair: a (residential, persona, category) pair whose reach becomes 1 when it was 0 or 0.5.
- Beneficiaries: residential population × vulnerable share × (personas with a material gain ÷ 4). Material gain = pair score rise ≥ 0.05 or a newly reachable pair.
- Unverified edges are excluded by default; the `include_unverified` toggle includes them. Blocked E20 is impassable for all personas; broken surface E12 fails all four personas.
- Base JSON is never mutated; state changes go to the SQLite overlay.
- Mock AI maps filename keywords to types: `blocked` → blocked_ramp, `curb`/`kerb`/`step` → high_curb, `ramp` → missing_ramp, `crack`/`broken` → broken_surface, else other at confidence 0.3.
- Sample reports and their 5 photos are synthetic placeholders.
- Footfall / CCTV data (M6) will be synthetic and aggregate-only; no frames stored, no face recognition (PDPA).

## 6. Known issues & tech debt
- One test-writer run saw `tests/test_ui_flow.py` fail once while pages were being edited mid-run. Later full runs passed (latest: 89/89). Not reproduced.
- A running Streamlit server may not reload edited helper modules. Restart after edits.
- Map tiles need internet (OpenStreetMap); routing and scoring work offline.
- Gemini path (M5) unverified; Mock is the only verified AI path.
- `store.py` repeats `executescript(SCHEMA)` in 9 places; consolidate later.
- `.claude/agents/*` load only in a new Claude Code session.
- `python` not on PATH; use `.venv/Scripts/python.exe`.
- Streamlit ≥ 1.50 required; pages use `width="stretch"`.
- Planning aid only, not proof of compliance with MS 1184 or any accessibility standard. Verify on site.
- Browser walk-through (main agent) covered Home, Route Planner, Report Obstacle, Verification Queue, Upgrade Simulator; not re-run in this session.

## 7. Next 3 tasks (priority order)
Priority order is as set by the user. The first physical action for M5 is in `docs/RUN_LOG.md`.
1. **M7 — dashboard + suppressed demand + Planning Brief** — `accesstwin/core/demand.py`, `pages/6_*` Planner Dashboard, `accesstwin/core/report.py` HTML export. Completes demo steps 3 and 5. Acceptance (spec 7): dashboard shows at least 1 suppressed-demand edge; exported HTML opens. Prove both with pytest and a rendered check.
2. **M6 — footfall (CV)** — `accesstwin/core/footfall.py` + Footfall page (`pages/4_*`), built by cv-engineer. Acceptance (spec 7): counts produced on a sample video; Mock runs without ultralytics; no frames written to disk (tested). Keep the CV dependencies out of the default `requirements.txt`.
3. **M5 — Gemini verification** — put a free AI Studio key in `.env` (`GEMINI_API_KEY`, `GEMINI_MODEL`, `ACCESSTWIN_MOCK=0`). Acceptance (spec 7): Mock works without a key; with a key, one sample photo (`data/photos/curb_high_step.png`) returns valid JSON. Never record the key in docs or chat.

## 8. Notes for Codex
- Read AGENTS.md → spec Section 7 → last RUN_LOG entry first
- Do not change storyline data in data/ unless the task requires it
- Follow Section 0 constraints (free, mock always works, privacy)
