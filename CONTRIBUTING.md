# Contributing

Language: English | [简体中文](CONTRIBUTING.zh-CN.md)

Thanks for taking the time to contribute!

## Before you start

- Search existing issues and pull requests first.
- Keep discussions respectful (see `CODE_OF_CONDUCT.md`).

## Workflow

1. Open an issue describing the change (bug / feature / docs).
2. If it’s accepted, open a pull request referencing the issue.

## Commit messages & PR titles

This template recommends using the Conventional Commits style:

`<type>(optional scope): <description>`

Common types:

- `feat`: a new feature
- `fix`: a bug fix
- `chore`: maintenance tasks (deps, tooling, refactors without behavior change)
- `docs`: documentation only changes

Bilingual commit messages (recommended):

- Keep the subject in English (best compatibility with tools)
- Add a short Chinese summary in the commit body

Examples:

- `feat: add export endpoint` + body: `增加导出接口`
- `chore: bump dependencies` + body: `升级依赖`

Optional: enable the commit message template:

- `git config commit.template .gitmessage`

## Pull request checklist

- Clear description of what changed and why
- Tests updated/added (if applicable)
- Docs updated (if applicable)
- Small, focused diffs whenever possible
