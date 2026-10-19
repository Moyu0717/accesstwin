# AccessTwin — Agent Instructions
- Source of truth: ACCESSTWIN_BUILD_SPEC.md. Read sections 0, 7, 9 first, then docs/HANDOFF.md and the last entry of docs/RUN_LOG.md.
- Run: `pip install -r requirements.txt && streamlit run app.py` (set ACCESSTWIN_MOCK=1 for offline demo).
- Optional real CV: `pip install -r requirements-cv.txt`.
- Test: `pytest -q`. Never mark a milestone done without passing tests.
- Constraints: free tools only; mock fallback must always work; aggregate-only CCTV; AI output is never a safety certification.
- At the end of every session: commit, append to docs/RUN_LOG.md, rewrite docs/HANDOFF.md (templates in spec section 9).
