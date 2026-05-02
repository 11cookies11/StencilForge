#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────
# Quick test suite (fast feedback, no Gerber fixtures, no browser)
# Runs: backend unit + CLI tests + frontend unit tests
# Suitable for: pre-commit, push CI, quick local verification
# Time: ~10 seconds
# ──────────────────────────────────────────────────────────────────────────
set -euo pipefail
cd "$(dirname "$0")/.."

echo "=== Backend unit tests (fast) ==="
python -m pytest tests/python/ -m "not integration" -q

echo ""
echo "=== Frontend unit tests ==="
cd ui-vue
npm run test:unit
cd ..

echo ""
echo "=== Quick tests passed ==="
