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
