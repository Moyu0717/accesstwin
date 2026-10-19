#!/usr/bin/env bash
# Scan every tracked or about-to-be-tracked file (and all committed history) for API keys. Exit 1 on a hit.
set -u
cd "$(dirname "$0")/.."
PATTERN='gsk_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9_-]{20,}|GROQ_API_KEY *= *"?[A-Za-z0-9_-]{8,}|api_key *= *"[A-Za-z0-9_-]{8,}'
files=$(git ls-files --cached --others --exclude-standard)
hits=$(echo "$files" | tr '\n' '\0' | xargs -0 grep -nIE "$PATTERN" 2>/dev/null | grep -v '^scripts/secret_scan.sh' | grep -v 'paste-your-key-here' || true)
hist=$(git log -p --all 2>/dev/null | grep -nE "^\+.*($PATTERN)" | grep -v 'PATTERN=' | grep -v 'paste-your-key-here' || true)
for f in .env .streamlit/secrets.toml; do
  if git ls-files --error-unmatch "$f" >/dev/null 2>&1 || echo "$files" | grep -qx "$f"; then echo "FAIL: $f would be committed"; exit 1; fi
done
if [ -n "$hits$hist" ]; then echo "FAIL: possible secret found:"; echo "$hits$hist" | cut -c1-80; exit 1; fi
echo "secret scan: clean ($(echo "$files" | wc -l) files + history)"
