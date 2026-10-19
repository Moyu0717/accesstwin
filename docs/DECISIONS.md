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

## 2026-10-19 — E16 (Block C → Junction 7) given steps
- **Decision:** E16 now has `has_step: true, curb_height_cm: 12`. Without it, wheelchair users from Block C could detour via J7 and U1 produced 0 "newly reachable" pairs, failing the M3 acceptance test. With it, Block C's wheelchair trip to the clinic is 1.56 km (> 1.5 km max trip) and U1 makes it practical (250 m). Wheelchair index is now ≈47 (spec pitch: "~50").
- **Alternatives:** loosen the definition of "newly reachable" (less honest), lengthen Route B for everyone (breaks the 2× story).

## 2026-10-19 — Definitions used by the simulator
- **Newly reachable pair:** a (residential, persona, category) pair whose `reach` becomes 1 (reachable within the persona's max trip) when it was 0 or 0.5 before.
- **Beneficiaries:** for each residential node, `population × vulnerable_share × (personas with a material gain ÷ 4)`; a material gain is a pair score rise ≥ 0.05 or a newly reachable pair. Assumes a node's vulnerable residents are spread evenly over the 4 personas. Avoids counting a whole block as benefiting from a 20 m shortcut.
- **Simulated edges** get `status = verified_accessible` (`simulate_assume_verified=True`); every result card says "Requires on-site verification after completion".
- **Ranking ties** broken by benefit. U1 ranks #1 in both modes (ROI ≈ 101 vs U2 ≈ 77).
- **Alternatives:** count every node with any improvement (gave 355 beneficiaries for every upgrade — no discrimination).

## 2026-10-19 — M4 implementation choices
- **Overlay derived, not stored:** the overlay is computed from approved reports (→ blocked) and verifications (passable → verified_accessible, not passable → blocked); the latest event per edge wins. No extra table beyond the 4 in spec 5.7.
- **Seed reports:** `init_db()` seeds `data/sample_reports.json` into an empty DB; seeds with status `approved` immediately block their edge (E20, E21). "Reset demo data" wipes all 4 tables and re-seeds.
- **Mock AI before M5:** `obstacles.py` uses filename keywords (`blocked` → blocked_ramp, `curb/kerb/step` → high_curb, `ramp` → missing_ramp, `crack/broken` → broken_surface, else other @0.3). The Gemini path (JSON-only prompt, parse → retry once → manual dropdown) is coded but **not verified** — that is M5.
- **Streamlit ≥ 1.50:** pages use `width="stretch"` (the `use_container_width` argument is deprecated in 1.66); requirements bumped from 1.38 to 1.50.
- **Page smoke tests:** every page runs under `streamlit.testing.v1.AppTest` in `pytest`, plus a report → approve → reroute flow test through the real pages.
