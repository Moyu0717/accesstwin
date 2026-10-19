# AccessTwin — Design Decisions

Format: date / decision / reason / alternatives considered.

## 2026-10-19 — Python 3.12 virtualenv in `.venv/`
- **Decision:** All commands run through `.venv/Scripts/python.exe` (Python 3.12). `python` is not on PATH on the dev machine; 3.14 is the default `py` but many wheels lag behind.
- **Alternatives:** system Python 3.14 (risk of missing wheels), conda (not installed).

## 2026-10-19 — Spec copied to project root
- **Decision:** `reference/ACCESSTWIN_BUILD_SPEC.md` was copied to `ACCESSTWIN_BUILD_SPEC.md` at the root, matching the layout in spec section 3. `reference/` is kept untouched.

## 2026-10-19 — Subagent files vs. runtime availability
- **Decision:** The 4 subagent definitions live in `.claude/agents/`. Subagent files are only picked up when a Claude Code session starts, so in the session that created them the work was dispatched to generic subagents running the same model (haiku) with the same instructions pasted in.
- **Alternatives:** restart the session (would lose the parallel data build during M0).

## 2026-10-19 — Township topology designed by the main agent
- **Decision:** The main agent fixed the exact node/edge table (16 nodes, 24 edges) before handing data generation to `data-builder`, because the Route A / Route B storyline, the "U1 ranks top 2" acceptance test and the "~50 wheelchair index" pitch number all depend on precise lengths and barriers.
- **Key numbers:** Route A R1→J1→J3→Clinic = 450 m via E7 (15 cm step). Wheelchair Route B R1→J2→J5→J6→Clinic = 1,100 m (2.4×, uncovered).

## 2026-10-19 — "Wheelchair R1 → clinic unreachable" vs. "Route B reachable"
- **Decision:** The spec asks both that wheelchair R1 → clinic is "unreachable with reason mentioning E7" (M2) and that a fallback Route B exists at ≥2× distance (4.1, demo script). `route()` therefore reports two levels: `direct_reachable=False` with `reason="E7: step 15 cm > wheelchair user limit 2 cm"` (the shortest/Route A is not usable) and `reachable=True` for the persona detour (Route B, 1,100 m). `reason` is filled whenever the direct route is blocked, even if a detour exists. Route Planner shows the reason card plus the fallback.
- **Alternatives:** make Route B exceed max_trip (would break the "2× longer fallback" story).
