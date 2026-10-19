# AccessTwin — Addendum: Groq Vision + Full Demo + GitHub & Streamlit Cloud Deployment

> **To the AI agent:** This addendum extends `ACCESSTWIN_BUILD_SPEC.md`. Where they conflict, **this file wins**. Read `AGENTS.md`, `docs/HANDOFF.md` and the last entry of `docs/RUN_LOG.md` first. Current state: M0–M4 and M8 are done and verified (89 tests passing, Mock demo runs locally on Windows via `.venv`).
>
> **Goal of this addendum:** a judge or teammate opens **one public URL** and the whole 3-minute demo works in the browser — no code, no install, no API key required. Real AI photo analysis uses **Groq** (free tier) when a key is configured; otherwise Mock.
>
> All tools must stay **free**. The user works on **Windows / PowerShell**; `python` is not on PATH, always use `.venv\Scripts\python.exe`.

---

## A. Questions to ask the user ONCE, at the start (then continue without stopping)

Ask these together in a single message, then wait for the answers:

1. **GitHub:** Is the GitHub CLI installed and logged in? (Check yourself first with `gh --version` and `gh auth status`.) If not, tell the user to run `winget install GitHub.cli` and then `gh auth login` **themselves** in a terminal (browser login, HTTPS). Never ask the user to paste a GitHub token into the chat.
2. **Repo:** repository name (suggest `accesstwin`) and visibility — **public** (simplest for Streamlit Cloud and judges) or private. Default owner is the account `gh auth status` reports.
3. **Groq key:** Ask the user to create a free key at https://console.groq.com/keys and put it **themselves** into the local `.env` file as `GROQ_API_KEY=...` (tell them the exact file path). Do not ask them to paste it in chat. If they don't have one yet, proceed in Mock mode and test Groq later.

Everything else: make reasonable decisions, record them in `docs/DECISIONS.md`, and keep going.

---

## B. Vision provider: replace Gemini with Groq

### B.1 Design
- Remove the Gemini dependency (`google-genai`) from `requirements.txt` and code.
- Add a provider abstraction in `accesstwin/core/obstacles.py`:
  - `VISION_PROVIDER` = `groq` | `openrouter` | `mock` (default: `groq` if `GROQ_API_KEY` is set, else `mock`).
  - `analyze_photo(image_bytes, filename) -> ObstacleResult` with the **same JSON schema** as spec §5.6 (so the UI and tests don't change).
- **Groq** (primary, free tier): use the official `groq` Python SDK (OpenAI-compatible chat completions with an `image_url` content part carrying a base64 data URL).
  - Model from env `GROQ_VISION_MODEL`. **Do not hard-code from memory.** At implementation time, list available models (`client.models.list()` or `GET https://api.groq.com/openai/v1/models`) and pick a current model that accepts image input (as of 2025 this was the Llama 4 Scout/Maverick family, e.g. `meta-llama/llama-4-scout-17b-16e-instruct`; verify it still exists). Put the chosen value in `.env.example` and `DECISIONS.md`.
  - Pre-process images: convert to RGB JPEG, resize so the longest side ≤ 1024 px, quality 85 — keeps requests small and within Groq's base64 size limits.
  - Request JSON: try `response_format={"type": "json_object"}`; if the model rejects it with images, fall back to a strict "return only JSON" prompt and extract the first `{...}` block.
  - `temperature=0.2`, timeout 30 s.
- **OpenRouter** (optional secondary, only if `OPENROUTER_API_KEY` is set): same code path via OpenAI-compatible endpoint `https://openrouter.ai/api/v1` using a currently available `:free` vision model (verify at implementation time). Implement only if cheap to add; otherwise document as future work.
- Failure handling (unchanged in spirit): invalid JSON → retry once → fall back to Mock result **plus** the manual category dropdown; rate-limit (HTTP 429) or network error → Mock result with a visible notice "AI temporarily unavailable — using demo classifier". The app must never crash because of the AI call.
- UI: the AI result card shows a small badge `AI: Groq · <model>` or `AI: Demo classifier (Mock)`.
- Never send anything except the resized image and the prompt. Show the existing notice "avoid capturing faces or licence plates".

### B.2 Secrets loading (works locally AND on Streamlit Cloud)
In `accesstwin/config.py`, implement `get_secret(name, default=None)`:
1. `st.secrets[name]` if available (wrap in try/except — `st.secrets` raises when no secrets file exists),
2. else `os.environ` (after `load_dotenv()`),
3. else default.

Use it for `GROQ_API_KEY`, `GROQ_VISION_MODEL`, `VISION_PROVIDER`, `OPENROUTER_API_KEY`, `ACCESSTWIN_MOCK`.
`ACCESSTWIN_MOCK` semantics: `1` forces Mock for everything; unset/`0` = use real providers where keys exist, Mock otherwise. **Default on the cloud must work with zero secrets.**

### B.3 Tests
- Unit tests for: image pre-processing, JSON extraction from messy model output, provider selection logic, 429/timeout → Mock fallback (mock the HTTP client; tests must not call the real API).
- One opt-in live test marked `@pytest.mark.live`, skipped unless `GROQ_API_KEY` is set, that sends one sample photo and validates the schema. Run it once locally if the key exists and record the result in RUN_LOG.

---

## C. Finish the remaining demo features (cloud-safe)

The demo script steps 3 and 5 currently depend on M6/M7. Finish them so the full script works on the cloud.

### C.1 M6 Footfall — cloud-safe version
- Streamlit Cloud has limited CPU/RAM; **do not** put `ultralytics`/`torch` in `requirements.txt`. Keep them in `requirements-cv.txt` (local only).
- Implement `footfall.py` per spec §5.4 with three modes, chosen automatically:
  1. **Live CV** (local, if `ultralytics` + `supervision` import): real counting.
  2. **Precomputed** (default on cloud): ship `data/footfall_precomputed.json` with results for the bundled sample clip(s) — counts, 10-second buckets, manual count, error %. If live CV is available locally, generate this file with real counts via a script `scripts/precompute_footfall.py`; otherwise generate a clearly labelled synthetic version and say so in DECISIONS.md.
  3. **Mock** for any user-uploaded video on the cloud: deterministic counts + notice "Live video analysis runs on the on-premise edge device; cloud demo shows sample results."
- Bundle a **short, small** sample clip (≤ 10 MB) in `data/videos/` only if its licence allows redistribution (the `supervision` sample assets are fine to download locally; check the licence before committing — if unsure, don't commit the video and use the precomputed JSON + a still preview image instead).
- Page shows: mode badge, counts, bucket chart, accuracy panel (manual vs automated count), link to edge via `cctv_id`, privacy notice. No frames are ever written to disk.

### C.2 M7 Dashboard + Planning Brief
Implement spec §5.5 (`demand.py`), §5.8 (`report.py`) and §6 page 7 as written. Make sure at least one edge on Route A is flagged **Suppressed demand** in the default demo data. The Planning Brief downloads via `st.download_button` (HTML + CSV) — no server-side file writes needed.

### C.3 Update the demo script
Remove the "(after M6/M7)" markers from `docs/DEMO_SCRIPT.md` once those steps work. Add a "Before you present" checklist: open the URL 5 minutes early (the free app sleeps when idle — click "Yes, get this app back up" if shown), press **Reset demo data**, select the Wheelchair persona.

---

## D. Make the app cloud-ready

1. **Entry point:** `app.py` at repo root; multipage via `pages/`.
2. **Paths:** every file path built from `Path(__file__).resolve()` — no reliance on the current working directory, no Windows-only separators.
3. **Writable state:** Streamlit Cloud's filesystem is ephemeral and may be shared between viewers.
   - Create the SQLite DB on startup if missing, seeded from `data/sample_reports.json`.
   - Put the DB and uploads under a writable temp dir on the cloud (e.g. `tempfile.gettempdir()/accesstwin/`), local `data/` when running locally. Detect with a config flag, not by guessing OS.
   - The **Reset demo data** button restores the seeded state. Document in README that data resets when the app restarts (fine for a demo).
4. **Caching:** `@st.cache_data` / `@st.cache_resource` for loading the base graph and personas; invalidate overlay-dependent results when the DB changes (e.g. pass a DB version counter into cached functions).
5. **Dependencies:** `requirements.txt` must contain only what the cloud needs (streamlit, streamlit-folium, folium, networkx, pandas, plotly, numpy, pillow, python-dotenv, groq, opencv-python-headless only if actually imported on the cloud path — otherwise move it to requirements-cv.txt). Use lower bounds (`>=`), and make sure a **fresh install works on Python 3.11 and 3.12**.
6. **Theme & config:** `.streamlit/config.toml` with theme only. **Never** commit `.streamlit/secrets.toml`; add `.streamlit/secrets.toml.example` showing the keys.
7. **.gitignore:** `.venv/`, `.env`, `.streamlit/secrets.toml`, `data/accesstwin.db`, `data/uploads/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`, model weights (`*.pt`), large videos not meant for the repo.
8. **Secret scan before every push:** search the repo (including git history of staged files) for `gsk_`, `sk-`, `GROQ_API_KEY=`, `api_key=` with a value. Abort the push if anything real is found.
9. **Repo size:** keep the repo < 50 MB; no file > 25 MB.
10. **Map tiles:** OpenStreetMap tiles need internet — fine on the cloud. Add attribution (Folium does this by default).

---

## E. Verify like the cloud will (before pushing)

Run all of these and record results in RUN_LOG:
1. `.venv\Scripts\python.exe -m pytest -q` → all green (live tests skipped unless key present).
2. **Clean-environment install test:** create a throwaway venv (e.g. `.venv-cloudtest`), `pip install -r requirements.txt` **only**, then run the Streamlit AppTest demo-script test inside it. This catches missing dependencies that the dev venv hides. Delete the throwaway venv afterwards.
3. Run with **no secrets at all** (temporarily rename `.env`): the full demo script passes in Mock/Precomputed mode. Restore `.env`.
4. If a Groq key exists: run with it and confirm one real photo analysis appears with the `AI: Groq` badge.
5. Headless run: `.venv\Scripts\python.exe -m streamlit run app.py --server.headless true --server.port 8599`, then check `http://localhost:8599/_stcore/health` returns `ok`; stop the server.

---

## F. Push to GitHub

1. `gh auth status` must succeed (otherwise stop and ask the user per §A).
2. Create the repo with the user's chosen name/visibility: `gh repo create <name> --<public|private> --source . --remote origin --push` (if a remote already exists, just push).
3. Add a lightweight free CI workflow `.github/workflows/tests.yml`: on push/PR, Ubuntu, Python 3.11, `pip install -r requirements.txt pytest`, `pytest -q` with `ACCESSTWIN_MOCK=1`. Push and confirm the run passes with `gh run watch` (or `gh run list`). Fix and re-push if it fails.
4. README additions: live demo URL placeholder, badges (CI), 1-paragraph pitch, screenshots folder `docs/screenshots/` (take 4–6 screenshots via Streamlit AppTest is not possible — instead leave a TODO list of which screens the user should capture), "Run locally", "Enable real AI (Groq)", "Enable real CV (local)", privacy & disclaimer section.

---

## G. Deploy to Streamlit Community Cloud (free)

Deployment requires the user to click through a web page once; you cannot do it from the CLI. After pushing, give the user **these exact steps** (in Chinese, short):

1. Open https://share.streamlit.io and sign in with GitHub (authorise access to the repo; for a private repo, grant private-repo access when asked).
2. Click **Create app** → **Deploy a public app from GitHub** (wording may differ slightly).
3. Repository: `<owner>/<repo>`, Branch: `main`, Main file path: `app.py`. Optionally choose a custom subdomain, e.g. `accesstwin-demo`.
4. **Advanced settings** → Python version **3.11** (or 3.12) → **Secrets**, paste:
   ```toml
   GROQ_API_KEY = "paste-your-key-here"
   GROQ_VISION_MODEL = "<the model you chose>"
   ACCESSTWIN_MOCK = "0"
   ```
   (Skip the secrets entirely to run in demo/Mock mode.)
5. Click **Deploy**, wait for the build to finish, and send the app URL back.

When the user returns the URL:
- Check it responds (`curl -I <url>`; a sleeping-app page still counts as reachable — note it).
- Put the URL in README (top, as "Live demo") and in `docs/HANDOFF.md`; commit and push.
- If the build failed, ask the user to copy the **build log** from the app's "Manage app" panel, fix the cause locally, re-run §E, push (Streamlit Cloud redeploys automatically on push).

Also tell the user: every future `git push` to `main` updates the live app automatically.

---

## H. Milestones for this addendum

| # | Milestone | Acceptance |
|---|---|---|
| D0 | Questions in §A answered; plan noted in RUN_LOG | answers recorded (no secrets in logs) |
| D1 | Groq provider + secrets loader + tests | `pytest -q` green; Gemini fully removed (`grep -ri gemini` finds only DECISIONS/RUN_LOG history) |
| D2 | M6 cloud-safe footfall | Footfall page works in Precomputed + Mock modes; no frames written (tested) |
| D3 | M7 dashboard, suppressed demand, Planning Brief download | ≥1 suppressed-demand edge on Route A; brief downloads |
| D4 | Cloud readiness (§D) + verification (§E) | all five checks in §E pass |
| D5 | GitHub push + CI green | `gh run list` shows success |
| D6 | Streamlit Cloud live | user-provided URL reachable; README + HANDOFF updated |

Use subagents as before (Haiku for tests/docs/data, `cv-engineer` for footfall). Run independent work in parallel.

---

## I. Logging (unchanged, mandatory)

After every milestone: commit → append `docs/RUN_LOG.md` (template in main spec §9.1) → fully rewrite `docs/HANDOFF.md` (§9.2, add a "Deployment" section: repo URL, app URL, secrets needed, how redeploy works, known cloud limits) → append trade-offs to `docs/DECISIONS.md`. **Never** write API keys or tokens into any log or doc. Never claim something works unless a command proved it.

Also update the main spec: replace Gemini references in §0, §2 and §5.6 with "Groq (see addendum)", and update `AGENTS.md`/`CLAUDE.md` to mention this addendum.
