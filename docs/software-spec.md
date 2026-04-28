# Software Spec

## Product Goal

StencilForge is a desktop tool for generating PCB stencil STL models from Gerber inputs.

## UX Principles

- Prioritize the main workflow: input, configure, generate, preview, export.
- Keep the default path short and clear.
- Hide advanced options behind progressive disclosure.
- Treat preview as validation, not marketing.

## Visual Rules

- Use a restrained, tool-oriented visual style.
- Keep neutral surfaces as the default and reserve accent colors for primary actions.
- Use one consistent icon and control style across the app.
- Keep branding visible but not dominant.

## Data Rules

- Configuration must have a single source of truth.
- UI, CLI, packaging, and runtime must share the same config fields.
- Saving and reloading must preserve all fields.
- Partial updates must never reset hidden fields.

## Packaging Rules

- Source branding, README branding, MSIX assets, and store assets must stay aligned.
- Generated artifacts should not be edited by hand.
- Entry points and packaging scripts must reference real modules and files.

## Release Rules

- Any change that affects packaging, assets, or entry points must be validated locally.
- Keep store assets, installer assets, and runtime assets in sync.
