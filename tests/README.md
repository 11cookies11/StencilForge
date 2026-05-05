# StencilForge Test Infrastructure

## Test Layers

```text
┌──────────────────────────────────────────────────────────┐
│ LAYER 1: Backend Unit (pytest, fast, CI on every push)   │
│   tests/python/test_*.py  (93 tests, ~3 sec)              │
│   Covers: config, pipeline, engine, geometry, i18n, CLI   │
├──────────────────────────────────────────────────────────┤
│ LAYER 2: Backend Integration (pytest -m integration)      │
│   tests/python/test_integration_generate.py  (24 tests)   │
│   Covers: real Gerber ZIP → STL with config variations    │
│   Manual/nightly only. Time: ~40 sec on Windows, ~3 min   │
│   on CI.                                                  │
├──────────────────────────────────────────────────────────┤
│ LAYER 3: Frontend Unit (Vitest + jsdom, fast)             │
│   ui-vue/tests/unit/*.spec.js  (72 tests, ~8 sec)         │
│   Covers: Vue component logic, events, i18n, state        │
├──────────────────────────────────────────────────────────┤
│ LAYER 4: Frontend E2E (Playwright, Chromium, slow)        │
│   ui-vue/tests/e2e/*.spec.js  (1 test, ~30 sec)           │
│   Covers: real browser interaction (language switching)   │
│   Nightly only.                                           │
└──────────────────────────────────────────────────────────┘
```

## Quick Reference — How to Run

### All tests (recommended for AI agents before/after changes)

| Platform | Command |
|----------|---------|
| Unix (CI, macOS, Linux) | `bash scripts/test-all.sh` |
| Windows | `powershell -File scripts/test_all.ps1` |

### Quick feedback (skip integration + e2e)

| Platform | Command |
|----------|---------|
| Unix | `bash scripts/test-quick.sh` |
| Windows | `pytest tests/python/ -m "not integration" -q; cd ui-vue; npm run test:unit` |

### Individual layers

```bash
# Backend unit only
pytest tests/python/ -m "not integration" -q

# Backend integration only
pytest tests/python/ -m integration -v

# Frontend unit only
cd ui-vue && npm run test:unit

# Frontend E2E only (needs Playwright browsers installed)
cd ui-vue && npm run test:e2e

# CLI manual test
python -m stencilforge generate <input_dir> <output.stl> --model-backend trimesh --verbose
```

## Test File Map

### Backend (tests/python/)

| File | Scope | Uses Gerber fixtures? |
|------|-------|-----------------------|
| `test_config.py` | Config validation, round-trip, defaults | No |
| `test_aperture_workspace.py` | Aperture rule normalization, matching | No |
| `test_pipeline_engine.py` | Engine selection (trimesh/cadquery/sfmesh) | No |
| `test_pipeline_core_fallbacks.py` | Outline fallback, aperture rule effect | Stub files |
| `test_sfmesh_engine.py` | SfMesh/Trimesh STL export | Synthetic polygons |
| `test_geometry_projection.py` | Polygon extrusion with holes | No |
| `test_gerber_compat.py` | Legacy Gerber file loading | Monkeypatched |
| `test_outline_extraction.py` | Outline from real GKO layers | **Yes** (case_001, case_003) |
| `test_backend_i18n.py` | Backend locale normalization, keys | No |
| `test_frontend_i18n_files.py` | Frontend locale JSON consistency | Reads ui-vue/src/i18n/ |
| `test_packaging_branding.py` | MSIX manifest, branding config | No |
| `test_ui_support.py` | Qt screen helpers, project root | No |
| `test_cli.py` | CLI parsing, config merge, backward compat | No |
| `test_integration_generate.py` | **Full Gerber→STL pipeline** | **Yes** (all 5 cases) |

### Gerber Fixtures (tests/fixtures/gerber/)

| Case | Contents | Purpose |
|------|----------|---------|
| `case_001_basic/` | `Test_deepseek.zip` (185KB), `ST-LINK-V2-1.zip` (53KB) | Standard PCBs |
| `case_002_no_outline/` | `Test_deepseek_no_outline.zip` (177KB) | Missing GKO/outline layer |
| `case_003_qfn/` | `Test_MCU_PCB.zip` (144KB), `Test_Camera.zip` (216KB) | QFN package boards |
| `case_004_zip_input/` | `Test_mini_电吉他.zip` (166KB) | ZIP-as-input format |
| `case_005_large_board/` | `Test_BIG_PCB.zip` (398KB), `Test_all_in_one.zip` (1.6MB) | Stress/large boards |

`expect.json` contains loose tolerance metrics used by integration tests.

### Frontend (ui-vue/tests/)

| File | Framework | Scope |
|------|-----------|-------|
| `unit/i18n.spec.js` | Vitest (node) | i18n functions: normalize, translate, fallback |
| `unit/AppIcon.spec.js` | Vitest (jsdom) | SVG icon rendering, size, fallback |
| `unit/AppHeader.spec.js` | Vitest (jsdom) | Title bar: render, events, language menu |
| `unit/AppSelect.spec.js` | Vitest (jsdom) | Dropdown: toggle, select, keyboard, click-outside |
| `unit/HelpTooltip.spec.js` | Vitest (jsdom) | Tooltip: hover show/hide, variants |
| `unit/BasicConfigForm.spec.js` | Vitest (jsdom) | Config form: inputs, emits, advanced section |
| `unit/App.spec.js` | Vitest (jsdom) | Main app: tabs, i18n, config state, patterns |
| `e2e/i18n-switch.spec.js` | Playwright | Real browser language switching |

## CI Workflows

| Workflow | Trigger | Runs |
|----------|---------|------|
| `tests.yml` | Every push/PR to main/feat/** | Layer 1 + Layer 3 (fast) |
| `test-integration.yml` | Nightly (2:23 UTC) + manual | Layer 2 (Gerber fixtures) |
| `nightly-e2e.yml` | Nightly (2:00 UTC) + manual | Layer 4 (Playwright) |
| `lint.yml` | Every push/PR | actionlint + markdownlint |

## AI Agent Guidelines

### When to run what

- **After any Python change** → `pytest tests/python/ -m "not integration" -q`
- **After CLI change** → Above + `pytest tests/python/test_cli.py -v`
- **After Vue component change** → `cd ui-vue && npx vitest run`
- **After pipeline/core change** → All of above + `pytest tests/python/ -m integration -v`
- **Before merging PR** → `bash scripts/test-all.sh`

### Adding new tests

- **New config field** → Add case to `test_config.py::test_validation_errors`
- **New CLI flag** → Add `_FIELD_MAP` entry + test in `test_cli.py`
- **New Vue component** → Add `tests/unit/<Component>.spec.js` with Vitest
- **New Gerber fixture** → Add ZIP to `tests/fixtures/gerber/case_NNN_name/input/`, add test in `test_integration_generate.py`
- **New pipeline feature** → Add integration test using `gerber_fixture` from `conftest.py`

### Test markers

- `@pytest.mark.integration` — slow tests using real Gerber fixtures. Skipped by `-m "not integration"`.
- Use `pytest.skip()` for missing fixtures/dependencies, not `xfail`.

### Encoding note

On Windows, some test fixture filenames contain non-ASCII characters. Use `encoding="utf-8"` when reading files. The CLI handles this via `UnicodeEncodeError` fallback.
