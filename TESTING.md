# Testing Strategy

This project uses layered automated tests to reduce manual QA:

1. Frontend fast checks:

- `npm run check:i18n`
- `npm run test:unit`
- `npm run build`

1. Python fast checks:

- `pytest --cov=src/stencilforge`

1. Nightly E2E:

- `npm run test:e2e` (Playwright)

## Quick Start (One Command)

From repository root:

```powershell
.\scripts\test_all.ps1
```

First run (installs Playwright browsers before e2e):

```powershell
.\scripts\test_all.ps1 -InstallBrowsers
```

## Local Commands

### Frontend

```bash
cd ui-vue
npm ci
npm run check:i18n
npm run test:unit
npm run test:e2e
npm run build
```

### Python

```bash
python -m pip install pytest pytest-cov
pytest
```

### Sfmesh Regression

```bash
python scripts/run_sfmesh_regression.py
```

With expect baseline strict checking:

```bash
python scripts/run_sfmesh_regression.py --strict-expect
```

## CI Workflows

- `.github/workflows/tests.yml`
  - Runs on push/PR.
  - Includes frontend i18n/unit/build and Python tests.

- `.github/workflows/nightly-e2e.yml`
  - Runs nightly and on manual dispatch.
  - Executes Playwright tests and uploads reports.

## Current Coverage Focus

- i18n locale normalization, key parity, and placeholder parity.
- Configuration defaulting and validation.
- Frontend language switching flow (E2E).
