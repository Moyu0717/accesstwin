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

## Session 2 — 2026-10-19 23:34 (agent: Claude Code, model: Claude Opus 5.5 main + Haiku/Sonnet subagents)
**Goal:** Deploy addendum D0 (questions) + D1 (Groq vision provider, secrets loader, tests)
**Done:**
- D0: repo `Moyu0717/accesstwin` (public, empty) provided by the user. `gh` not installed → plain git push + public GitHub API for CI. No `.env` / Groq key yet → Mock.
- D1: `accesstwin/config.py` (get_secret, vision_provider, force_mock, state_dir, resolve_path), `accesstwin/core/obstacles.py` (Groq via `groq` SDK, image pre-processing, fallbacks), Report Obstacle badge `AI: Groq · <model>` / `AI: Demo classifier (Mock)`, `.env.example`, `.streamlit/secrets.toml.example`, `.gitignore`, `.gitattributes`, requirements (google-genai removed, groq added, opencv moved to requirements-cv.txt). Spec §0/§2/§5.6 and AGENTS.md/CLAUDE.md now point to the addendum.
**Verified by:**
- `pytest -q --ignore=tests/test_footfall.py` → 115 passed, 1 skipped (live Groq test skipped: no key)
- `grep -ri gemini` over code/requirements → no matches
**Not done / Blocked:**
- Live Groq call not tested (needs the user's key in `.env`).
**Bugs / Known issues:**
- None new.
**Subagents used:** test-writer → tests/test_vision_groq.py; cv-engineer → D2 footfall (in progress)
**Next step (exact):** finish D2 (footfall) and D3 (dashboard), then run addendum §E checks.

## Session 2 (cont.) — 2026-10-19 23:43 (agent: Claude Code, model: Claude Opus 5.5 main + Haiku/Sonnet subagents)
**Goal:** Deploy addendum D2 (cloud-safe footfall), D3 (dashboard, suppressed demand, Planning Brief), D4 (cloud readiness + §E checks)
**Done:**
- D2 (commit "D2: ..."): `accesstwin/core/footfall.py` (live / precomputed / mock), `pages/4_🎥_Footfall_Analytics.py`, `scripts/precompute_footfall.py`, synthetic `data/footfall_precomputed.json`, `data/videos/sample_preview.png`, store helpers, tests — by cv-engineer.
- D3 (commit "D3: ..."): `accesstwin/core/demand.py`, `accesstwin/core/report.py`, `pages/6_📊_Planner_Dashboard.py`, camera-vs-expected section on the Footfall page, home links for all 5 demo steps, cached township JSON, `docs/DEMO_SCRIPT.md` without "(after M6/M7)" markers + "Before you present" checklist; demo-script test now covers all 5 steps.
- D4: `.github/workflows/tests.yml`, README rewrite (live URL placeholder, CI badge, Groq/CV/privacy sections), `docs/screenshots/README.md` (capture list), `scripts/secret_scan.sh`, `.gitignore` (+ `.secrets_local/`).
**Verified by:**
- `pytest -q` (dev venv, Python 3.12) → 139 passed, 1 skipped (live test skipped by default)
- Clean env: fresh Python 3.11.9 venv with `requirements.txt` only (streamlit 1.66.0, groq 1.7.0, no cv2) → full suite 139 passed, 1 skipped, with `.env` renamed away and ACCESSTWIN_MOCK unset (no secrets)
- `pytest -m live` with the user's key in `.env` → 1 passed; `curb_high_step.png` → source groq, `qwen/qwen3.8-27b`, high_curb, confidence 0.95. An immediate second call fell back to the demo classifier with the "AI temporarily unavailable" notice (rate limit likely).
- Headless: streamlit on port 8599 → `/_stcore/health` ok, `/` HTTP 200
- `bash scripts/secret_scan.sh` → clean
**Not done / Blocked:**
- Real CV never run (ultralytics/torch not installed); precomputed footfall numbers are synthetic.
**Bugs / Known issues:**
- Groq free tier rate-limits back-to-back photo analyses; the app falls back to the demo classifier with a notice.
**Subagents used:** cv-engineer → D2; test-writer → test_demand/test_report/test_dashboard
**Next step (exact):** push to `origin main`, confirm the GitHub Actions run is green, then give the user the Streamlit Cloud steps.

## Session 2 (cont. 2) — 2026-10-20 00:16 (agent: main agent + subagents)
**Goal:** Deploy addendum D5 (GitHub push + CI green) and D6 (Streamlit Community Cloud live)
**Done:**
- D5: pushed `main` to https://github.com/Moyu0717/accesstwin (public) with plain git + Git Credential Manager (`gh` CLI not installed). The push added no new commit: `origin/main` = `71ec100` = local HEAD. GitHub Actions workflow `tests` (`.github/workflows/tests.yml`: Python 3.11, `ACCESSTWIN_MOCK=1`, validate + pytest) sat queued ~30 min on GitHub's side, then finished **passing** (run 39280158937, as reported by the user). Secret scan `bash scripts/secret_scan.sh` → clean before push (as reported).
- D6: app live on Streamlit Community Cloud at https://accesstwin-demo.streamlit.app/ . Checked in this session with a cookie jar: `/` → HTTP 200, `/~/+/_stcore/health` → `ok`.
- Whether Groq secrets were added on the cloud is unknown (user did not say). Without them the app runs in demo/Mock mode.
- Local-only cleanup (not committed): `.claude/` (4 subagent files, `launch.json`) and `CLAUDE.md` are staged for deletion from the index (files kept on disk); `.gitignore` gained `.claude/` and `CLAUDE.md` (unstaged); `README.md` has one unstaged line change. `AGENTS.md` kept.
- Doc-logging: this entry and a full rewrite of `docs/HANDOFF.md` (with the Deployment section per addendum §I). No commit made.
**Verified by:**
- `git log --oneline -15` → `71ec100` D4, `0dc3a94` D3, `5d42e7a` D2, `d30001c` D1, `c55a8cd` docs, `a08afc4` M8, `807fd0e` M4, `125a528` M3, `828c5ab` docs, `985bf07` M2, `87e2cec` M1, `a9b3059` M0
- `git status` → branch `main`, up to date with `origin/main`; staged deletions of `.claude/*` and `CLAUDE.md`; unstaged `.gitignore` and `README.md`
- `git ls-remote origin main` → `71ec100d9d0cbecc29e8ae19a9aab5d28f8e23d1`
- `.venv/Scripts/python.exe -m pytest -q` → 140 passed, 0 failed, 0 skipped (21.6 s). Previous entry: 139 passed, 1 skipped; the difference was not investigated.
- `curl` to the cloud app → `/` HTTP 200; `/~/+/_stcore/health` → `ok`
- GitHub API lookup of run 39280158937 → HTTP 403 (unauthenticated rate limit); CI result taken from the user's report, not re-verified here
**Not done / Blocked:**
- Screenshots for `docs/screenshots/` not captured (user to do, checklist in `docs/screenshots/README.md`)
- Real CV never run (ultralytics/torch not installed); precomputed footfall numbers and camera counts are synthetic
- Groq secrets on the cloud: unknown, see above
- OpenRouter not implemented
- Pending local-only cleanup not committed (doc-logger is read-only with git); `.claude/*` and `CLAUDE.md` remain tracked on `origin/main` until committed
- `docs/DECISIONS.md` not updated in this step (this entry was limited to two files)
**Bugs / Known issues:**
- Streamlit Community Cloud: the free app sleeps when idle; first load ~30 s ("Yes, get this app back up")
- Cloud runtime data (reports, approvals, work orders) lives in a temp SQLite file and resets on app restart
- Groq free tier rate-limits back-to-back photo analyses; the app falls back to the demo classifier with a notice (reproduced in D2)
- OpenStreetMap tiles need internet
**Subagents used:** doc-logger → this RUN_LOG entry and HANDOFF rewrite. No other subagent work is recorded for the D5/D6 steps.
**Next step (exact):** Decide whether to commit the pending local-only cleanup (`.claude/` and `CLAUDE.md` deletions, `.gitignore`, `README.md`) and push; then follow the three tasks in `docs/HANDOFF.md` section 7, starting with the screenshots for the proposal.
