# AccessTwin AI 2.0 — Prototype Build Spec (for Claude Code / Codex)

> **To the AI agent executing this file:** This is the single source of truth. Execute in order starting from Section 0. After every milestone you MUST update `docs/RUN_LOG.md` and `docs/HANDOFF.md` (see Section 9). All tools, libraries and hosting must be **free**. With no API key, the system must run the **entire demo in Mock mode**.

---

## 0. Context & Hard Constraints

- Competition: Sime Darby Property University Hackathon "Township of Tomorrow" — **People Track** (sub-themes: Accessibility & Inclusion, Getting around / Mobility, with a touch of Safety).
- Key dates: Proposal submission **2026-10-23**; Top 10 announced 10-28; Final Submission 11-11; Top 10 Pitch 11-14.
- Judging weights (design directly against these):

| Criterion | Weight | How this prototype scores |
|---|---|---|
| Strategic Fit | 15% | Directly addresses People Track Accessibility + Mobility; serves the developer's planning and property-management functions |
| Impact & Sustainability | 25% | Quantifies new reachable destinations, beneficiaries and detour reduction, weighted toward vulnerable groups |
| Innovation | 20% | Multi-persona routing + Upgrade ROI ranking + suppressed-demand detection + pre-construction design review |
| Feasibility | 20% | Reuses existing CCTV and guard patrols; fully free open-source stack; runs offline in Mock mode |
| Commercial | 10% | Cross-township SaaS + design-stage review + ESG / accessibility reporting output |
| Evidence & Pitch | 10% | Built-in KPI panel (count error, detection accuracy, before/after) + 3-minute demo script |

- Must be free: Python, Streamlit, OpenCV, Ultralytics YOLO (`yolov8n.pt` / `yolo11n.pt`), `supervision`, NetworkX, Folium + `streamlit-folium`, SQLite, Pandas, Plotly, pytest. Vision AI uses the **Gemini Flash free tier from Google AI Studio** (model name read from `.env`, never hard-coded). Deployment: **Streamlit Community Cloud** or **Hugging Face Spaces** (free).
- Forbidden: any paid API as a required dependency; face recognition; cross-camera tracking of individuals; labelling AI output as "certified accessible".

---

## 1. Refined Positioning (for the pitch, and the product requirements)

### 1.1 One-liner
**AccessTwin is a township's "accessibility digital twin": it combines anonymous CCTV footfall, resident/guard obstacle reports and the walkway network to tell the developer which segment to fix first, at what cost tier, and how many people gain access to which places.**

### 1.2 Six key upgrades over the original concept
1. **Persona Routing:** The same map yields different reachability for 4 groups — wheelchair users, elderly, parents with strollers, visually impaired people. Each persona has configurable rules (steps, curb height, slope, shade/rain cover, tactile paving, max walking distance).
2. **Accessibility Gap Index:** For every residential node and every key destination (clinic, bus stop, school, grocery, park), compute per-persona reachability and detour, aggregated into a 0–100 township score. This is the headline number of the pitch.
3. **Upgrade ROI Ranking:** For each candidate improvement (add ramp, resurface path, clear obstruction, add covered walkway), automatically simulate before/after and rank by `benefit ÷ cost tier`, producing a Top 5 recommendation list. Cost uses **relative tiers only (low/medium/high)** — never output real RM construction costs.
4. **Suppressed Demand Detection:** A simple gravity model estimates expected footfall and compares it with CCTV counts. Observed far below expected AND the segment has a barrier → flagged as "people may not walk here because they can't". Directly answers "low traffic ≠ unimportant".
5. **Malaysian localisation:** Segment attributes include **shade / covered walkway** and **night lighting** (tropical heat and afternoon storms are real barriers for elderly and stroller users; lighting also touches the Safety sub-theme).
6. **Dual-mode commercial value:**
   - **Operate mode** (existing townships): property management raises work orders and tracks fixes.
   - **Design mode** (planning stage): import the walkway network of a draft masterplan and find accessibility gaps before construction — changing a drawing is far cheaper than rebuilding a path. This is the strongest selling point for a developer.

### 1.3 Human-centred & compliance principles (must be visible in the UI)
- Three segment states: `verified_accessible` / `blocked` / `unverified` (grey; excluded from routing by default with a "pending verification" notice).
- Photo AI only creates a "suggestion pending review"; graph state changes only after guard/admin approval.
- CCTV outputs **aggregate counts only** — no frames stored, no face recognition. UI shows a PDPA notice and "requires property authorisation before connecting real cameras".
- Footer disclaimer: this is a planning aid, not proof of compliance with accessibility design standards (e.g. MS 1184); all routes require on-site verification.

---

## 2. Recommended Models & Subagent Setup (for the person running Claude Code)

| Role | Model | Why |
|---|---|---|
| Main agent (orchestration, core logic) | **Claude Sonnet 5.5** (`/model sonnet`) | Strong coding at moderate cost; drives the whole project |
| Subagents for simple / repetitive work | **Claude Haiku 5.5** | Cheap and fast for synthetic data, tests, docs, format checks |
| Optional one-off architecture review | Claude Opus 5.5 | Only when stuck or for a final review |
| Vision AI inside the prototype | Gemini Flash (AI Studio free tier) | Free; automatically falls back to Mock without a key |

### 2.1 Create these subagent files in the project (`.claude/agents/`)

`.claude/agents/data-builder.md`
```markdown
---
name: data-builder
description: Generates and validates demo data files (township graph JSON, destinations, sample reports, persona configs). Use for any synthetic data or seed-file task.
model: haiku
tools: Read, Write, Edit, Bash, Glob
---
You create small, internally consistent demo datasets for AccessTwin. Follow the schemas in ACCESSTWIN_BUILD_SPEC.md section 4 exactly. After writing, run `python -m accesstwin.core.validate` and fix any errors. Report what files you changed in 5 lines or fewer.
```

`.claude/agents/test-writer.md`
```markdown
---
name: test-writer
description: Writes and runs pytest tests for accesstwin core modules. Use after a core module is implemented or changed.
model: haiku
tools: Read, Write, Edit, Bash, Glob, Grep
---
Write focused pytest tests under tests/ for the module named in the task. Cover the acceptance criteria listed in ACCESSTWIN_BUILD_SPEC.md section 7. Run `pytest -q` and report pass/fail counts and any failing test names. Do not modify non-test code; report bugs instead.
```

`.claude/agents/cv-engineer.md`
```markdown
---
name: cv-engineer
description: Implements the CCTV footfall counting pipeline (OpenCV + YOLO + supervision line-zone counting). Use only for footfall.py and its page.
model: sonnet
tools: Read, Write, Edit, Bash, Glob, Grep
---
Implement accesstwin/core/footfall.py per spec section 5.4. CPU-only, must process a 30-second 720p clip in under ~2 minutes by sampling frames. Never save frames or crops; output aggregate counts only. Provide a mock fallback when ultralytics is unavailable.
```

`.claude/agents/doc-logger.md`
```markdown
---
name: doc-logger
description: Updates docs/RUN_LOG.md and docs/HANDOFF.md at the end of a work session using the templates in spec section 9.
model: haiku
tools: Read, Write, Edit, Bash, Glob
---
Run `git log --oneline -15`, `git status`, and `pytest -q`, then append a session entry to docs/RUN_LOG.md and fully rewrite docs/HANDOFF.md using the templates in ACCESSTWIN_BUILD_SPEC.md section 9. Be factual; never claim something works unless a command proved it.
```

**Usage rules:** The main agent owns `routing.py`, `simulation.py`, `scoring.py` and UI integration (these need global understanding). Data, tests and logs go to Haiku subagents; CV goes to `cv-engineer`. Run parallelisable work in the background (e.g. let `data-builder` build data while the main agent does M0/M2 scaffolding).

---

## 3. Tech Stack & Directory Layout

```
accesstwin/
├── CLAUDE.md                 # points to this spec; project memory for Claude Code
├── AGENTS.md                 # same content as CLAUDE.md; read by Codex
├── ACCESSTWIN_BUILD_SPEC.md  # this file
├── README.md                 # install, run, deploy, demo script
├── requirements.txt
├── requirements-cv.txt       # ultralytics + supervision (optional, local only)
├── .env.example              # GEMINI_API_KEY= ; GEMINI_MODEL= ; ACCESSTWIN_MOCK=1
├── .streamlit/config.toml    # theme
├── app.py                    # Streamlit entry (home = index overview)
├── pages/
│   ├── 1_🧭_Route_Planner.py      # resident: choose persona, origin, destination
│   ├── 2_📸_Report_Obstacle.py    # resident/guard: upload photo → AI suggestion
│   ├── 3_✅_Verification_Queue.py # guard/admin: review, verify segments
│   ├── 4_🎥_Footfall_Analytics.py # upload MP4 → anonymous counts
│   ├── 5_🏗️_Upgrade_Simulator.py  # what-if + ROI ranking
│   └── 6_📊_Planner_Dashboard.py  # index, hotspots, suppressed demand, export
├── accesstwin/
│   ├── __init__.py
│   ├── config.py             # .env, mock switch, paths, scoring coefficients
│   ├── core/
│   │   ├── graph.py          # load township.json → NetworkX MultiGraph
│   │   ├── personas.py       # 4 persona rule sets
│   │   ├── routing.py        # persona filtering + shortest path
│   │   ├── scoring.py        # Gap Index, beneficiary calculation
│   │   ├── simulation.py     # what-if and ROI ranking
│   │   ├── demand.py         # gravity model, suppressed demand
│   │   ├── footfall.py       # CV counting
│   │   ├── obstacles.py      # Gemini Vision + Mock
│   │   ├── store.py          # SQLite (reports, verifications, footfall_runs, work_orders)
│   │   ├── report.py         # export HTML/CSV planning brief
│   │   └── validate.py       # data schema checks (runnable via python -m)
│   └── ui/
│       ├── map_view.py       # Folium layers: segment colours, report markers, heat
│       └── components.py     # shared cards, disclaimer, persona selector
├── data/
│   ├── township.json
│   ├── personas.json
│   ├── upgrades.json
│   ├── sample_reports.json
│   ├── photos/               # sample obstacle photos (user-taken; generated placeholders if missing)
│   ├── videos/               # sample video (user-taken or supervision sample asset)
│   └── uploads/              # gitignored
├── tests/
└── docs/
    ├── RUN_LOG.md
    ├── HANDOFF.md
    ├── DECISIONS.md
    └── DEMO_SCRIPT.md
```

`requirements.txt` (use `>=`, don't over-pin):
```
streamlit>=1.38
streamlit-folium>=0.22
folium>=0.17
networkx>=3.2
pandas>=2.1
plotly>=5.20
numpy
pillow
python-dotenv
opencv-python-headless>=4.9
google-genai>=1.0
pytest
```
`requirements-cv.txt`:
```
ultralytics>=8.2
supervision>=0.22
```
> `ultralytics` pulls in torch, which may be too large/slow for Streamlit Cloud. Keep it out of the main requirements; `footfall.py` switches to Mock automatically on import failure and the page notes "run locally with requirements-cv.txt to enable real counting".

---

## 4. Data Schemas

### 4.1 `data/township.json`
A fictional "Elmina-style Demo Township". Coordinates roughly near Shah Alam are fine (UI labels it *Fictional demo layout*). Size: **14–18 nodes, 20–26 edges**.

```json
{
  "meta": {"name": "Demo Township", "crs": "WGS84", "fictional": true},
  "nodes": [
    {"id": "R1", "name": "Residential Block A", "type": "residential", "lat": 3.1801, "lon": 101.5012, "population": 420, "vulnerable_share": 0.22},
    {"id": "D_CLINIC", "name": "Community Clinic", "type": "destination", "category": "clinic", "importance": 1.0, "lat": 3.1823, "lon": 101.5051},
    {"id": "J1", "name": "Junction 1", "type": "junction", "lat": 3.1810, "lon": 101.5030}
  ],
  "edges": [
    {
      "id": "E1", "from": "R1", "to": "J1", "length_m": 180,
      "surface": "good",
      "has_step": false,
      "curb_height_cm": 2,
      "max_slope_pct": 3,
      "width_cm": 150,
      "tactile_paving": false,
      "covered": false,
      "lit_at_night": true,
      "status": "verified_accessible",
      "cctv_id": "CAM_01"
    }
  ]
}
```
Allowed values: `surface` ∈ {good, cracked, broken, gravel}; `status` ∈ {verified_accessible, blocked, unverified}; `cctv_id` may be null.

Required storyline (makes the demo convincing):
- Destination categories: `clinic`, `bus_stop`, `school`, `grocery`, `park` (at least one each; importance 1.0 / 0.9 / 0.8 / 0.7 / 0.5).
- **"Route A":** shortest path residential → clinic contains a segment with `has_step: true, curb_height_cm: 15` (edge `E7`) — not reachable by wheelchair.
- **"Route B":** reachable but ≥ 2× the distance, mostly `covered: false`.
- At least 3 `unverified` edges; at least 1 `blocked` edge (e.g. a ramp blocked by parked vehicles).
- At least one residential node with a clearly higher `vulnerable_share` (e.g. near senior housing) to demonstrate equity weighting.
- At least 3 edges with `cctv_id`, one of which lies on Route A (for suppressed demand).

### 4.2 `data/personas.json`
```json
{
  "wheelchair": {"label": "Wheelchair user", "allow_step": false, "max_curb_cm": 2, "max_slope_pct": 8, "min_width_cm": 90, "bad_surfaces": ["broken", "gravel"], "max_trip_m": 1500, "prefers_covered": false, "needs_tactile": false, "equity_weight": 1.6},
  "elderly": {"label": "Elderly", "allow_step": true, "max_curb_cm": 15, "max_slope_pct": 10, "min_width_cm": 60, "bad_surfaces": ["broken"], "max_trip_m": 800, "prefers_covered": true, "needs_tactile": false, "equity_weight": 1.4},
  "stroller": {"label": "Parent with stroller", "allow_step": false, "max_curb_cm": 5, "max_slope_pct": 10, "min_width_cm": 80, "bad_surfaces": ["broken", "gravel"], "max_trip_m": 1500, "prefers_covered": true, "needs_tactile": false, "equity_weight": 1.2},
  "visually_impaired": {"label": "Visually impaired", "allow_step": true, "max_curb_cm": 15, "max_slope_pct": 12, "min_width_cm": 60, "bad_surfaces": ["broken"], "max_trip_m": 1200, "prefers_covered": false, "needs_tactile": true, "equity_weight": 1.5}
}
```
> These values are **configurable demo assumptions**; the UI must say "Demo assumptions — not a design standard". When `needs_tactile: true`, edges without tactile paving are allowed but get a +50% cost penalty. When `prefers_covered: true`, uncovered edges get a +30% cost penalty (heat/rain).

### 4.3 `data/upgrades.json`
```json
[
  {"id": "U1", "title": "Add kerb ramp at Junction 3 (Route A)", "edge_id": "E7", "changes": {"has_step": false, "curb_height_cm": 0, "status": "unverified"}, "cost_tier": "low"},
  {"id": "U2", "title": "Resurface broken path near Grocery", "edge_id": "E12", "changes": {"surface": "good"}, "cost_tier": "medium"},
  {"id": "U3", "title": "Covered walkway Block C → Bus Stop", "edge_id": "E15", "changes": {"covered": true}, "cost_tier": "high"},
  {"id": "U4", "title": "New link path through park (design mode)", "new_edge": {"id": "E_NEW1", "from": "J4", "to": "D_PARK", "length_m": 120, "surface": "good", "has_step": false, "curb_height_cm": 0, "max_slope_pct": 4, "width_cm": 180, "tactile_paving": true, "covered": false, "lit_at_night": true, "status": "unverified"}, "cost_tier": "medium", "design_mode_only": true}
]
```
`cost_tier` weights: low = 1, medium = 2.5, high = 5 (ranking only). Provide 6–8 candidates.
> During simulation, upgraded edges are **assumed passable** (`simulate_assume_verified=True`), but every result card states "Requires on-site verification after completion".

### 4.4 `data/sample_reports.json`
4–6 seed reports (mix of pending/approved, resident/guard), each referencing an existing edge and a photo filename in `data/photos/`.

---

## 5. Core Logic Specification

### 5.1 `routing.py`
- `edge_passable(edge, persona, include_unverified=False) -> tuple[bool, str | None]` (reason when not passable)
- `edge_cost(edge, persona) -> float`: base = `length_m`, plus persona penalties (covered, tactile, `cracked` surface +20%).
- `persona_subgraph(G, persona, include_unverified=False)`
- `route(G, origin, dest, persona, include_unverified=False) -> RouteResult(path, length_m, cost, edges, unverified_edges, covered_ratio, reachable, reason)`
- When unreachable, `reason` must name the **specific blocking edge and cause** (e.g. "E7: step 15 cm > wheelchair limit 2 cm"). Find it by taking the unconstrained shortest path and reporting the first impassable edge.
- Also compute the unconstrained baseline route to show `detour_ratio = persona_length / baseline_length`.

### 5.2 `scoring.py` — Accessibility Gap Index
For each residential node r, persona p, destination category c (nearest reachable destination in that category):
- `reach(r,p,c) = 1` if reachable and `length ≤ max_trip_m`; 0.5 if reachable but over distance; else 0.
- `detour_penalty = min(1, (detour_ratio − 1) / 2)`
- `score(r,p,c) = reach × (1 − 0.5 × detour_penalty)`
- Node-persona score = Σ_c importance_c × score ÷ Σ_c importance_c
- **Township index** = weighted mean using `population × vulnerable_share × equity_weight_p`, × 100.
- Also output `gap_matrix` (residential × persona heatmap data) and an `unreachable_pairs` list.

### 5.3 `simulation.py` — What-if & ROI
- `apply_upgrade(G, upgrade) -> G'` (copy; never mutate the original)
- `compare(G, G', personas) -> Delta`: index change (overall and per persona), newly reachable (residential, persona, destination) pairs, estimated beneficiaries (`population × vulnerable_share`), average detour reduction in metres.
- `rank_upgrades(G, upgrades, mode="operate") -> DataFrame`: `benefit = Δindex_points × 10 + new_reachable_pairs × 3 + Σ beneficiaries / 100` (coefficients in `config.py`), `roi = benefit / cost_weight`, sorted descending. In operate mode, exclude `design_mode_only` upgrades.
- Support **combined scenarios** (multiple upgrades simulated together).
- Each result generates **plain-language explanation text**, e.g. "Adding a ramp at E7 lets wheelchair users from Block A and Block C reach the clinic directly; detour drops from 1.2 km to 450 m; an estimated 130 residents who need extra mobility support benefit."

### 5.4 `footfall.py` — Anonymous CCTV Counting
- Input: MP4; user sets a counting line (a slider for horizontal line y-position is enough — no freehand drawing).
- Pipeline: OpenCV reads frames → sample every N frames (default 3) → YOLO (`person` class) → `supervision.ByteTrack` → `supervision.LineZone` counts in/out.
- Output: `{in, out, total, frames_processed, fps_effective, occlusion_note}` plus counts per 10-second bucket (for charting).
- **Accuracy panel:** user may enter a manual count → show error %. UI explains that occlusion and dense crowds cause under-counting.
- Privacy: never write frames or crops to disk; optional preview frame with **Gaussian-blurred person boxes**, kept in memory only.
- Mock: if import fails or `ACCESSTWIN_MOCK=1`, return deterministic fake counts (seeded from a hash of the file bytes) and label the UI *Mock*.
- Sample video: prefer user footage in `data/videos/`; otherwise download the pedestrian sample from `supervision.assets` (`VideoAssets.PEOPLE_WALKING`) into `data/videos/`.
- Store results in SQLite `footfall_runs`; link to an edge via `cctv_id` for the heat layer and suppressed demand.

### 5.5 `demand.py` — Suppressed Demand
- Gravity model: for OD pairs whose baseline shortest path uses edge e, `expected_flow_e = Σ population_r × importance_d / (dist_rd)^1.5`, then scale so total expected matches total observed across covered edges.
- `suppression_ratio = observed / expected`; if `< 0.4` AND the edge (or its baseline route) contains a barrier/unverified edge → flag **Suppressed demand**.
- Edges without counts show "No CCTV coverage" — never infer.
- In Mock mode, seed counts so that the Route A camera shows suppression.

### 5.6 `obstacles.py` — Photo Obstacle Detection
- With `GEMINI_API_KEY`: call `GEMINI_MODEL` via `google-genai` (read from env; example value `gemini-2.5-flash` — if renamed, use the current free Flash model in AI Studio).
- Prompt must request **JSON only**:
```json
{"obstacle_type": "high_curb|missing_ramp|blocked_ramp|broken_surface|narrow_path|no_tactile|flooding|other|none",
 "severity": "low|medium|high",
 "affected_personas": ["wheelchair", "stroller"],
 "confidence": 0.0,
 "visible_evidence": "short description",
 "needs_onsite_measurement": ["curb height", "slope"]}
```
- Parse failure → retry once → still failing → fall back to a manual category dropdown.
- Mock: return preset results based on filename keywords (`curb`, `ramp`, `crack`, `blocked`); otherwise `other`, confidence 0.3.
- Report flow: photo + nearest edge (dropdown, or map click if easy) + reporter role (resident/guard) → status `pending`.
- Photos stored only locally in `data/uploads/`; pre-upload notice: "Please avoid capturing faces or licence plates."

### 5.7 `store.py` (SQLite, `data/accesstwin.db`)
Tables: `reports(id, edge_id, reporter_role, photo_path, ai_json, status[pending|approved|rejected], created_at)`, `verifications(id, edge_id, verifier_role, result, note, created_at)`, `footfall_runs(id, video_name, cctv_id, total_in, total_out, buckets_json, manual_count, mock, created_at)`, `work_orders(id, upgrade_id, report_id, status[open|in_progress|done], created_at)`.
- Approving an obstacle report → that edge becomes `blocked` (stored as an overlay; base JSON never modified).
- Verifying an edge as passable → `verified_accessible`.
- Graph at load time = base JSON + SQLite overlay. Provide a "Reset demo data" button.

### 5.8 `report.py`
Export a single-file HTML "Planning Brief": township index, Top 5 upgrades (with explanation text), suppressed-demand segments, report statistics, disclaimer. Also export CSV. (Users can print the HTML to PDF from the browser at zero cost.)

---

## 6. UI Specification (Streamlit)

Global: sidebar with persona selector and a "Mock mode" badge; disclaimer component at the bottom of every page. Map colours: green = verified accessible, red = blocked, grey dashed = unverified, orange marker = pending report; edges impassable for the selected persona drawn as thin red lines.

1. **Home `app.py` — Township Overview:** large Gap Index (one metric card per persona), overview map, "Top 3 critical gaps", button to start the demo.
2. **Route Planner:** choose persona, origin (residential), destination → map shows both the baseline shortest route (dashed) and the persona route (solid); show distance, detour ratio, unverified edges encountered, covered ratio. If unreachable, show a reason card.
3. **Report Obstacle:** upload photo → AI result card (type, severity, affected personas, confidence, items needing on-site measurement) → choose edge → submit.
4. **Verification Queue:** table of pending reports; view photo and AI result; Approve / Reject buttons. Second section: mark `unverified` edges as verified (simulates "wheelchair-user representative verified on site"; record verifier role and note).
5. **Footfall Analytics:** upload or choose sample video, set counting line, run (progress bar), metric cards + time-bucket bar chart + accuracy input + link to edge.
6. **Upgrade Simulator:** multiselect upgrades on the left; right side shows before/after maps (`st.columns`) + Δ index + newly reachable list + explanation text; below, ROI ranking table and Plotly bar chart; "Create work order" button.
7. **Planner Dashboard:** gap heatmap (residential × persona), footfall heat layer, suppressed-demand list, report statistics, Operate/Design mode toggle (Design mode enables `design_mode_only` upgrades and shows a "Pre-construction review" header), export Planning Brief.

UI language: English primary. Keep labels in one `i18n` dict so Bahasa Malaysia / Chinese can be added later.

---

## 7. Milestones & Acceptance Criteria (execute in order)

| # | Milestone | Owner | Acceptance (must be proven by a command) |
|---|---|---|---|
| M0 | Skeleton, requirements, `.env.example`, `CLAUDE.md`, `AGENTS.md`, `docs/` templates, `.gitignore`, git init | main agent | `streamlit run app.py` opens a blank home page |
| M1 | Data (township / personas / upgrades / sample_reports) + `validate.py` | data-builder (parallel) | `python -m accesstwin.core.validate` passes; Route A storyline holds |
| M2 | `graph.py`, `personas.py`, `routing.py` + Route Planner page | main + test-writer | Tests: wheelchair R1 → clinic is unreachable with reason mentioning E7; elderly reachable; `include_unverified` toggle changes results |
| M3 | `scoring.py`, `simulation.py` + Upgrade Simulator page | main + test-writer | Tests: applying U1 raises wheelchair index and new reachable pairs > 0; U1 (low cost, high benefit) ranks top 2 in ROI |
| M4 | `store.py`, Report Obstacle, Verification Queue (Mock AI) | main | Report → approve → edge turns blocked → route recomputes (overlay logic verified in tests) |
| M5 | `obstacles.py` with Gemini (optional key) | main | Mock works without key; with key, one sample photo returns valid JSON |
| M6 | `footfall.py` + Footfall page | cv-engineer | Counts produced on sample video; Mock runs without ultralytics; no frames written to disk (tested) |
| M7 | `demand.py` + Planner Dashboard + `report.py` | main | Dashboard shows at least 1 suppressed-demand edge; exported HTML opens |
| M8 | Polish: theme, copy, empty states, error handling | main | Full 3-minute demo script runs end-to-end without errors in Mock mode |
| M9 | Deploy to Streamlit Community Cloud (without CV deps) + README | main | README covers local run, deploy, demo script; `pytest -q` all green |

**Priority:** The proposal is due 10-23. If time is short, **M0–M4 + M8 (Mock demo)** is enough for screenshots / screen recording in the proposal. M5–M7 and M9 can be finished during the Mentoring Sprint (11-02 to 11-11) if selected for Top 10.

---

## 8. 3-Minute Demo Script (write to `docs/DEMO_SCRIPT.md`)

1. **(0:00–0:30) Problem** — Home: wheelchair index is only ~50; "A path on the map doesn't mean you can get there."
2. **(0:30–1:00) Route Planner** — Same origin/destination: elderly can reach it, wheelchair cannot; reason card points to E7 (15 cm step); fallback Route B is 2× longer and uncovered.
3. **(1:00–1:30) Evidence** — Upload a curb photo → AI flags `high_curb`, needs on-site measurement → guard approves in the queue; Footfall page shows that segment far below expected → Suppressed demand.
4. **(1:30–2:30) Decide** — Upgrade Simulator: select U1 → map recomputes instantly, index +X, new reachable destinations, ~N residents benefit; ROI ranking explains why U1 beats the expensive covered walkway.
5. **(2:30–3:00) Scale** — Dashboard switches to Design mode for pre-construction review; export Planning Brief; close: "Build a township that works for everyone."

---

## 9. Run Log & Handoff After Every Session (mandatory)

**Rules:** Before ending any work session (or after each milestone), the `doc-logger` subagent (or the main agent) must:
1. `git add -A && git commit -m "<milestone>: <summary>"`
2. **Append** an entry to the end of `docs/RUN_LOG.md` (never delete old entries).
3. **Fully rewrite** `docs/HANDOFF.md` to reflect the true current state.
4. Append significant design trade-offs to `docs/DECISIONS.md` (format: date / decision / reason / alternatives considered).
5. Never claim a feature is "done" unless a command verified it.

### 9.1 `docs/RUN_LOG.md` entry template
```markdown
## Session <N> — <YYYY-MM-DD HH:MM> (<agent: Claude Code / Codex>, model: <model>)
**Goal:** <goal / milestone>
**Done:**
- <item + files touched>
**Verified by:**
- `pytest -q` → <x passed, y failed>
- `<other command>` → <result>
**Not done / Blocked:**
- <item and reason>
**Bugs / Known issues:**
- <issue, how to reproduce>
**Subagents used:** <name → task>
**Next step (exact):** <the first thing the next person should do on opening the project>
```

### 9.2 `docs/HANDOFF.md` template (overwrite fully each time)
```markdown
# AccessTwin — Handoff (updated <YYYY-MM-DD HH:MM>)
## 1. One-paragraph status
## 2. Milestone checklist
- [x]/[ ] M0 … M9 (one-line status each)
## 3. How to run
- setup / run / test / mock mode / real Gemini / real CV commands
## 4. Architecture map
- one-line responsibility per module + key function names
## 5. Data & assumptions
- demo storyline, persona assumptions, cost tiers, what is synthetic
## 6. Known issues & tech debt
## 7. Next 3 tasks (priority order, with acceptance criteria)
## 8. Notes for Codex
- Read AGENTS.md → spec Section 7 → last RUN_LOG entry first
- Do not change storyline data in data/ unless the task requires it
- Follow Section 0 constraints (free, mock always works, privacy)
```

### 9.3 `AGENTS.md` / `CLAUDE.md` content (identical)
```markdown
# AccessTwin — Agent Instructions
- Source of truth: ACCESSTWIN_BUILD_SPEC.md. Read sections 0, 7, 9 first, then docs/HANDOFF.md and the last entry of docs/RUN_LOG.md.
- Run: `pip install -r requirements.txt && streamlit run app.py` (set ACCESSTWIN_MOCK=1 for offline demo).
- Optional real CV: `pip install -r requirements-cv.txt`.
- Test: `pytest -q`. Never mark a milestone done without passing tests.
- Constraints: free tools only; mock fallback must always work; aggregate-only CCTV; AI output is never a safety certification.
- At the end of every session: commit, append to docs/RUN_LOG.md, rewrite docs/HANDOFF.md (templates in spec section 9).
```

---

## 10. Proposal / Pitch Material (fill in with prototype screenshots once built)

- **Beneficiaries:** wheelchair users, elderly, parents with strollers, visually impaired people, temporarily injured residents, delivery workers — "design for those who find it hardest, and everyone benefits."
- **KPI table:** count error % (vs manual count); obstacle classification accuracy (20–30 labelled photos); Gap Index before/after; number of newly reachable destinations; number of route suggestions judged unsafe by real users during validation (target: 0).
- **Business model:** annual per-township subscription (Operate) + per-project pre-construction review fee (Design); accessibility metrics that feed directly into ESG / sustainability reporting; the same persona and scoring logic reused across townships.
- **Pilot path:** 1 township, 2–3 main pedestrian corridors, 1–2 existing CCTV cameras (with authorisation), 4 weeks of guard-patrol reporting, joint validation with local disability / senior-citizen groups.
- **Risks & mitigations:** keep the four risk boundaries from the original concept (surveillance permissions, data representativeness, route safety, no fabricated costs) and show the matching UI safeguards in the demo (grey unverified edges, AI pending review, privacy notices, cost tiers).
