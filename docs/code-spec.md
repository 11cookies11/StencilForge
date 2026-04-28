# Code Spec

## Core Principles

- Prefer clarity over cleverness.
- Keep functions small and single-purpose.
- Keep modules focused on one responsibility.
- Use existing project patterns before introducing new abstractions.

## Naming

- Use descriptive names instead of abbreviations.
- Use boolean prefixes like `is_`, `has_`, `can_`, and `should_`.
- Keep shared concept names consistent across Python, Vue, config, and packaging.
- Keep config suffixes consistent, such as `*_mm`, `*_enabled`, `*_mode`, `*_ratio`, and `*_tol`.

## Python Rules

- Use `src` layout imports consistently.
- Add type hints to new or changed Python code when practical.
- Keep business logic out of UI layers.
- Keep serialization and validation inside the config layer.
- Avoid hidden side effects in helper functions.

## Config Rules

- `StencilConfig` is the canonical config model.
- `from_dict()` must tolerate missing and legacy fields.
- `to_dict()` or equivalent serialization must be complete and stable.
- UI partial updates must merge against the full current config.

## UI Rules

- Keep Vue components small enough to scan quickly.
- Split large views into reusable components when the template starts to sprawl.
- Keep text, controls, and state aligned with the layout.
- Put user-facing strings in i18n, not in business logic.

## Error Handling

- Surface errors clearly and consistently.
- Do not silently swallow errors unless there is a documented fallback.
- Log technical details separately from user-facing messages.

## Testing Rules

- Add regression tests for config, parsing, packaging, and main workflow changes.
- Keep frontend i18n and build checks passing.
- Verify packaging changes with local build checks.

## Change Hygiene

- Keep diffs focused.
- Remove dead code when it becomes unreachable.
- Do not leave placeholder entry points, temporary assets, or opaque comments behind.
