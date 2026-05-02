#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────
# Full test suite (backend + frontend + integration)
# Runs: all Python tests (unit + CLI + integration with Gerber fixtures)
#       all frontend tests (unit + i18n check + build)
# Suitable for: pre-release, manual full verification
# Time: ~2-5 minutes (integration tests run the full pipeline)
# ──────────────────────────────────────────────────────────────────────────
set -euo pipefail
cd "$(dirname "$0")/.."

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

pass_count=0
fail_count=0

run_step() {
  local name="$1"
  shift
  echo ""
  echo "==> $name"
  if "$@"; then
    echo -e "${GREEN}[PASS]${NC} $name"
    pass_count=$((pass_count + 1))
  else
    echo -e "${RED}[FAIL]${NC} $name"
    fail_count=$((fail_count + 1))
  fi
}

# ── Backend ────────────────────────────────────────────────────────────

run_step "Python: unit + CLI tests" \
  python -m pytest tests/python/ -m "not integration" -q

run_step "Python: integration tests (Gerber fixtures)" \
  python -m pytest tests/python/ -m integration -q

# ── Frontend ───────────────────────────────────────────────────────────

pushd ui-vue > /dev/null

run_step "Frontend: i18n consistency check" \
  npm run check:i18n

run_step "Frontend: Vitest component tests" \
  npx vitest run

run_step "Frontend: Vite production build" \
  npm run build

popd > /dev/null

# ── Summary ────────────────────────────────────────────────────────────

echo ""
echo "=========================================="
total=$((pass_count + fail_count))
echo "Results: $pass_count / $total steps passed"
if [ $fail_count -gt 0 ]; then
  echo -e "${RED}$fail_count step(s) failed${NC}"
  exit 1
else
  echo -e "${GREEN}All steps passed${NC}"
fi
