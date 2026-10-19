# AccessTwin — Agent Instructions
- Source of truth: ACCESSTWIN_BUILD_SPEC.md plus ACCESSTWIN_DEPLOY_ADDENDUM.md (the addendum wins on conflicts: Groq vision, cloud deploy). Read spec sections 0, 7, 9 and the addendum first, then docs/HANDOFF.md and the last entry of docs/RUN_LOG.md.
- Run: `pip install -r requirements.txt && streamlit run app.py` (set ACCESSTWIN_MOCK=1 for offline demo). On Windows use `.venv\Scripts\python.exe -m ...` (python is not on PATH).
- Optional real CV: `pip install -r requirements-cv.txt`.
- Test: `pytest -q`. Never mark a milestone done without passing tests.
- Constraints: free tools only; mock fallback must always work; aggregate-only CCTV; AI output is never a safety certification.
- At the end of every session: commit, append to docs/RUN_LOG.md, rewrite docs/HANDOFF.md (templates in spec section 9).
- Secrets (GROQ_API_KEY) live only in `.env` or Streamlit Cloud secrets — never in code, docs or logs.
