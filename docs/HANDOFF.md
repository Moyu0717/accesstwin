# AccessTwin — Handoff (updated 2026-10-20 00:16)

## 1. One-paragraph status
All planned milestones M0–M9 and deploy addendum D0–D6 are done. The code is on GitHub (`main` = `71ec100`, public repo `Moyu0717/accesstwin`), CI workflow `tests` passed (run 39280158937, as reported), and the app is live on Streamlit Community Cloud at https://accesstwin-demo.streamlit.app/ (checked this session: HTTP 200, health `ok`). `pytest -q` → 140 passed, 0 failed, 0 skipped. The app runs with no keys in demo/Mock mode: photo AI uses the demo classifier, footfall uses bundled synthetic sample results. With a Groq key (local `.env` or cloud secrets) the photo AI uses Groq vision; a live call on `curb_high_step.png` passed locally (`qwen/qwen3.8-27b`, high_curb, confidence 0.95). Not done: real CV counting (never run; footfall numbers are synthetic), screenshots for the proposal (user to capture), OpenRouter (not implemented). Working tree has uncommitted local-only cleanup (see section 6).

## 2. Milestone checklist
- [x] M0 — skeleton, requirements, config, docs templates, git init (`a9b3059`)
- [x] M1 — township (16 nodes / 24 edges), personas, 7 upgrades, 5 sample reports, 5 placeholder photos, `validate.py` → OK (`87e2cec`)
- [x] M2 — graph, personas, routing (direct vs detour), Route Planner, tests (`985bf07`)
- [x] M3 — `scoring.py`, `simulation.py`, Upgrade Simulator, home overview; U1 ranks #1 by ROI (≈101), U2 #2 (≈77) (`125a528`)
- [x] M4 — SQLite overlay (`store.py`), Mock AI, Report Obstacle and Verification Queue; report → approve → E7 blocked → route recomputes (`807fd0e`)
- [x] M5 — photo AI via **Groq** (Gemini removed, see addendum B): live test passed locally on `curb_high_step.png` (D1–D4 commits `d30001c`, `71ec100`)
- [x] M6 — footfall, cloud-safe: live / precomputed / mock modes, Footfall page, no frames written (tested). Real CV NOT run; bundled results are synthetic (`5d42e7a`)
- [x] M7 — suppressed demand (`demand.py`), Planner Dashboard (`pages/6_*`), Planning Brief HTML/CSV (`report.py`) (`0dc3a94`)
- [x] M8 — polish: map framing, shorter labels, graph-load error handling, demo script, README, end-to-end demo test (`a08afc4`)
- [x] M9 — deployed to Streamlit Community Cloud + README (live URL, CI badge) (`71ec100`; live app checked)
- [x] D0–D6 — addendum: questions, Groq provider, cloud-safe footfall, dashboard, cloud readiness (D4 `71ec100`), GitHub push + CI (D5, no new commit), Streamlit Cloud live (D6)

## 3. How to run
- Setup: `py -3.12 -m venv .venv`, then `.venv\Scripts\python.exe -m pip install -r requirements.txt`
- Run, demo mode (offline, no keys): PowerShell `$env:ACCESSTWIN_MOCK="1"; .venv\Scripts\python.exe -m streamlit run app.py`. Click **Reset demo data** in the sidebar before a demo.
- Run, real Groq locally: copy `.env.example` to `.env`, set `GROQ_API_KEY` (and optionally `GROQ_VISION_MODEL`, default `qwen/qwen3.8-27b`), keep `ACCESSTWIN_MOCK` unset or `0`, restart Streamlit. Never commit `.env`.
- Test: `.venv\Scripts\python.exe -m pytest -q` (last run: 140 passed, 0 failed, 0 skipped). Live Groq test: `pytest -m live` (needs the local key).
- Validate data: `.venv\Scripts\python.exe -m accesstwin.core.validate` (last run: `OK: ...`)
- Real CV (local only): `.venv\Scripts\python.exe -m pip install -r requirements-cv.txt` (large, pulls torch), then `.venv\Scripts\python.exe scripts\precompute_footfall.py path\to\clip.mp4` to refresh `data/footfall_precomputed.json`. Not run yet.
- Secret scan before pushing: `bash scripts/secret_scan.sh` (clean at D4 and before the D5 push, as reported).
- Note: `python` is not on PATH on this machine; always use `.venv\Scripts\python.exe`.

## 4. Architecture map
- `app.py` — home: Gap Index (0–100) and per-persona scores, overview map, top 3 critical gaps, links to the 5 demo steps (`scores()` → `compute_scores`, `critical_gaps`).
- `accesstwin/config.py` — `get_secret()` (env / `.env` / Streamlit secrets), `state_dir()` (`ACCESSTWIN_STATE_DIR`, else `data/` when writable, else temp), `resolve_path()`, `STATE_DIR`, `UPLOADS_DIR`, `DB_PATH` (`ACCESSTWIN_DB`), `groq_api_key()`, `groq_vision_model()`, `force_mock()` (`ACCESSTWIN_MOCK`), `vision_provider()`, `mock_mode()`, routing penalties (`PENALTY_UNCOVERED` 0.30, `PENALTY_NO_TACTILE` 0.50, `PENALTY_CRACKED` 0.20), benefit coefficients, `COST_TIER_WEIGHTS` (low 1.0, medium 2.5, high 5.0).
- `accesstwin/core/graph.py` — `load_township()`, `build_graph(data, overlay)` (NetworkX MultiGraph), `load_graph()`, `find_edge()`, `set_edge_attrs()`, `iter_edges()`, `residential_nodes()`, `destination_nodes()`, `categories()`, `node_name()`.
- `accesstwin/core/personas.py` — `Persona` dataclass, `load_personas()`, `get_persona()`.
- `accesstwin/core/routing.py` — `edge_passable()` (pass/fail with the blocking reason), `edge_cost()`, `persona_subgraph()`, `baseline_route()`, `route()` → `RouteResult` (`direct_reachable`, `reason`, `reachable`, `path`, `edges`, `length_m`, `detour_ratio`, `within_max_trip`, `unverified_edges`, `covered_ratio`).
- `accesstwin/core/scoring.py` — Gap Index: `compute_scores()` → `ScoreResult` (`index`, `persona_index`, `pairs`, `gap_matrix()`, `unreachable_pairs`), `pair_score()`, `detour_penalty()`, `vulnerable_population()`, `critical_gaps()`.
- `accesstwin/core/simulation.py` — `load_upgrades()`, `available_upgrades()` (Operate hides design-only), `apply_upgrade(s)` (graph copy), `compare()` → `Delta`, `benefit()`, `explain()`, `rank_upgrades()` (ROI = benefit ÷ cost weight).
- `accesstwin/core/store.py` — SQLite (`DB_PATH`), tables `reports`, `verifications`, `footfall_runs`, `work_orders`. `init_db()`, `seed_sample_reports()`, `reset_demo()`, `add_report()`, `set_report_status()`, `list_reports()`, `add_verification()`, `list_verifications()`, `get_overlay()` (latest event per edge wins), `add_work_order()`, `set_work_order_status()`, `list_work_orders()`, `add_footfall_run()`, `list_footfall_runs()`.
- `accesstwin/core/obstacles.py` — `analyze_photo()` (Groq when a key is set and not mock, else Mock; falls back with a notice), `_groq_call()`, `_groq_client()`, `preprocess_image()` (resize/JPEG before upload), `mock_analyze()` (filename keyword), `parse_ai_json()`, `_is_transient()`. AI output is a suggestion pending review.
- `accesstwin/core/footfall.py` — `count_video()` (chooses live / precomputed / mock), `camera_counts()`, `error_pct()`, `cv_available()`, `detect_mode()`, `load_precomputed()`, `sample_result()`, `FootfallResult`. Frames and crops never written to disk; aggregate counts only.
- `accesstwin/core/demand.py` — suppressed demand: `expected_flows()` (gravity model on baseline shortest paths), `suppressed_demand()` (observed/expected < 0.4 with a barrier or unverified segment, CCTV-covered edges only), `demand_frame()`, `edge_barriers()`, `EdgeDemand`.
- `accesstwin/core/report.py` — `brief_html()` (single-file Planning Brief), `ranking_csv()`, `demand_csv()`, `report_stats()`. Returned as strings; no server-side files.
- `accesstwin/core/validate.py` — `validate_all()` and `main()`: township, personas, upgrades, sample reports, storyline.
- `accesstwin/ui/components.py` — `setup_page()`, `sidebar()`, `graph()`, `personas()`, `card()`, `disclaimer()`, `fmt_m()`, `page_link()`, `persona_label()`, `persona_short()`.
- `accesstwin/ui/map_view.py` — `base_map()` (folium, OpenStreetMap tiles), `add_route()`, `edge_line()`, `LEGEND_MD`; status colours (verified green, blocked red, unverified grey).
- `accesstwin/ui/i18n.py` — `t(key)` and `LABELS` (English only).
- `pages/1_🧭_Route_Planner.py` — same trip, different personas; reason card naming the blocking segment.
- `pages/2_📸_Report_Obstacle.py` — photo → AI suggestion (Groq badge `AI: Groq · <model>` or `AI: Demo classifier (Mock)`) → segment → pending report.
- `pages/3_✅_Verification_Queue.py` — approve/reject reports; on-site verification; route impact (`impact_text()`).
- `pages/4_🎥_Footfall_Analytics.py` — anonymous counts (sample clip / upload), accuracy panel, camera counts vs expected demand.
- `pages/5_🏗️_Upgrade_Simulator.py` — Operate/Design modes, before/after map, Δindex, newly reachable trips, ROI chart, work orders.
- `pages/6_📊_Planner_Dashboard.py` — gap heatmap, footfall layer, suppressed demand, Planning Brief (HTML) and CSV downloads.
- `scripts/precompute_footfall.py` — local-only: runs CV on a clip and refreshes `data/footfall_precomputed.json`. `scripts/secret_scan.sh` — pre-push secret scan.
- `.github/workflows/tests.yml` — CI: Ubuntu, Python 3.11, `ACCESSTWIN_MOCK=1`, validate + pytest.
- Tests: `test_graph`, `test_routing`, `test_scoring`, `test_simulation`, `test_store`, `test_obstacles`, `test_vision_groq` (live test marked `live`), `test_footfall`, `test_demand`, `test_report`, `test_dashboard`, `test_pages` (AppTest smoke per page), `test_ui_flow` (report → approve → reroute), `test_demo_script` (all 5 demo steps, Mock mode), `test_smoke`.

## 5. Data & assumptions
- Demo storyline: synthetic "Demo Township" (fictional, Elmina-style). Route A R1 → J1 → J3 → Clinic = 450 m via E7 (15 cm step). Wheelchair Route B R1 → J2 → J5 → J6 → Clinic = 1,100 m (2.4×, uncovered). E16 has a 12 cm curb, so Block C wheelchair trips to the clinic are 1.56 km, above the 1.5 km max trip.
- Seed reports (`data/sample_reports.json`) are approved on first init and block E20 and E21. "Reset demo data" wipes the tables and re-seeds.
- After Reset demo data: township index 54.6; wheelchair 46.7, elderly 56.0, stroller 46.7, visually impaired 68.1. Base JSON without overlay: 56.1.
- U1 (low cost): Δindex +8.74, 4 newly reachable pairs, ~152 beneficiaries, ROI 100.91, rank #1. U2 (medium): ROI 77.28, rank #2. U4 (design mode only): rank #3 there. U3 scores 0.
- Suppressed demand (demo): E7 / CAM_02 observed 40 vs expected ≈ 551 (ratio 0.07).
- **Synthetic:** footfall sample results (`data/footfall_precomputed.json`), camera counts, `data/videos/sample_preview.png`, sample reports and their 5 photos. No real CCTV was used.
- Persona rules (`data/personas.json`) are demo assumptions, not a design standard. MS 1184 is not implemented.
- Cost tiers are relative (low/medium/high), never RM estimates.
- Unverified edges are excluded by default; the `include_unverified` toggle includes them. Base JSON is never mutated; state changes go to the SQLite overlay.
- Mock AI maps filename keywords: `blocked` → blocked_ramp, `curb`/`kerb`/`step` → high_curb, `ramp` → missing_ramp, `crack`/`broken` → broken_surface, else other at 0.3 confidence.
- Privacy: CCTV analytics are aggregate-only (no frames stored, no face recognition, PDPA). With Groq enabled, only the resized photo and the prompt are sent to Groq.

## 6. Known issues & tech debt
- **Uncommitted local-only cleanup:** `.claude/` (subagent files, `launch.json`) and `CLAUDE.md` are staged for deletion from the index but still on disk; `.gitignore` (adds `.claude/`, `CLAUDE.md`) and `README.md` (one line) are unstaged. Nothing committed. `origin/main` still tracks `.claude/*` and `CLAUDE.md` until this is committed. `AGENTS.md` stays tracked.
- Cloud app sleeps when idle; first load ~30 s ("Yes, get this app back up").
- Cloud runtime data (reports, approvals, work orders) is in a temp SQLite file and resets on restart. Use **Reset demo data**.
- Groq free tier rate-limits back-to-back photo analyses; the app falls back to the demo classifier with a notice.
- Groq secrets on the cloud: not confirmed. Without them the cloud app is in demo/Mock mode.
- Real CV never run (ultralytics/torch not installed). Footfall numbers are synthetic.
- `pytest` count changed from 139 passed + 1 skipped (D4) to 140 passed + 0 skipped (this session). Not investigated.
- `store.py` repeats `executescript(SCHEMA)` in 9 places; consolidate later.
- `.claude/agents/*` (now local-only) load only in a new Claude Code session.
- Map tiles need internet (OpenStreetMap); routing and scoring work offline.
- Streamlit ≥ 1.50 required; pages use `width="stretch"`.
- Planning aid only, not proof of compliance with MS 1184 or any accessibility standard. Verify on site.
- `docs/DECISIONS.md` has no entry for the D5/D6 steps yet.

## 7. Next 3 tasks (priority order)
Before task 1: decide whether to commit the local-only cleanup in section 6 (commits and pushes need the user's go-ahead).
1. **Screenshots for the proposal** — capture the list in `docs/screenshots/README.md` (4–6 PNGs) from the live app or local demo mode, then add them to `README.md` and spec §10. Acceptance: files exist in `docs/screenshots/`; README and spec §10 reference them.
2. **Real CV on your own clip (local)** — `pip install -r requirements-cv.txt`, then `scripts/precompute_footfall.py` on your own short clip. Acceptance: counts are written to `data/footfall_precomputed.json`; no frames written to disk; `pytest -q` still green with and without CV. Keep the clip out of git (`data/videos/*.mp4` is ignored).
3. **Groq on the cloud** — user adds `GROQ_API_KEY`, `GROQ_VISION_MODEL=qwen/qwen3.8-27b`, `ACCESSTWIN_MOCK=0` in Streamlit *App settings → Secrets* (values are never written to docs or chat). Then upload `data/photos/curb_high_step.png` in Report Obstacle. Acceptance: the badge reads `AI: Groq · qwen/qwen3.8-27b` and the result is `high_curb`.

## 8. Notes for Codex
- Read AGENTS.md → spec Section 7 → last RUN_LOG entry first
- Do not change storyline data in `data/` unless the task requires it
- Follow Section 0 constraints (free, mock always works, privacy)
- Never write API keys or tokens into logs, docs or chat; `.env` and `.secrets_local/` are local-only
- `.claude/` and `CLAUDE.md` are local-only; do not re-add them to git

## 9. Deployment
- **Repo:** https://github.com/Moyu0717/accesstwin (public), branch `main`, main file `app.py`
- **Live app:** https://accesstwin-demo.streamlit.app/ (Streamlit Community Cloud, free). Checked 2026-10-20: `/` HTTP 200, health `ok`.
- **CI:** `.github/workflows/tests.yml` (run 39280158937 passing, as reported; the README badge tracks it)
- **Secrets** (names only; set in *App settings → Secrets*, never in the repo): `GROQ_API_KEY`, `GROQ_VISION_MODEL` (`qwen/qwen3.8-27b`), `ACCESSTWIN_MOCK`. Status on the cloud not confirmed. Without `GROQ_API_KEY` the app runs in demo mode.
- **Redeploy:** push to `main` on GitHub; Streamlit Cloud rebuilds automatically. Secrets changes need a reboot of the app.
- **Known cloud limits:** app sleeps when idle (~30 s to wake); runtime SQLite data resets on restart; Groq free-tier rate limits (falls back with a notice); OSM tiles need internet; footfall is bundled synthetic sample results only (no CV in the cloud).
