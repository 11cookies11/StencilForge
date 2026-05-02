#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────
# Integration test suite (full Gerber → STL pipeline with real fixtures)
# Runs: pytest -m integration
# Suitable for: pre-release verification, manual QA, nightly CI
# Time: ~1-5 minutes (runs the real pipeline on 5 PCB designs)
# ──────────────────────────────────────────────────────────────────────────
set -euo pipefail
cd "$(dirname "$0")/.."

echo "=== Python integration tests (real Gerber fixtures) ==="
python -m pytest tests/python/ -m integration -v
echo ""
echo "=== Integration tests passed ==="
