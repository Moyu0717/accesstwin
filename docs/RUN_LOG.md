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
