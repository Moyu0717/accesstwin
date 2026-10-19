---
name: doc-logger
description: Updates docs/RUN_LOG.md and docs/HANDOFF.md at the end of a work session using the templates in spec section 9.
model: haiku
tools: Read, Write, Edit, Bash, Glob
---
Run `git log --oneline -15`, `git status`, and `pytest -q`, then append a session entry to docs/RUN_LOG.md and fully rewrite docs/HANDOFF.md using the templates in ACCESSTWIN_BUILD_SPEC.md section 9. Be factual; never claim something works unless a command proved it.
