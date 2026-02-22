# Testing Strategy

This project uses layered automated tests to reduce manual QA:

1. Frontend fast checks:
- `npm run check:i18n`
- `npm run test:unit`
- `npm run build`

2. Python fast checks:
- `pytest --cov=src/stencilforge`

3. Nightly E2E:
- `npm run test:e2e` (Playwright)

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
