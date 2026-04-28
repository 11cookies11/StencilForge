# Contributing

Language: English | [简体中文](CONTRIBUTING.zh-CN.md)

Thanks for taking the time to contribute.

## Before you start

- Search existing issues and pull requests first.
- Keep discussions respectful. See `CODE_OF_CONDUCT.md`.

## Workflow

1. Open an issue describing the change.
2. If the change is accepted, open a pull request that references the issue.

## Commit messages and PR titles

This project follows Conventional Commits:

`<type>(optional scope): <description>`

Common types:

- `feat`: a new feature
- `fix`: a bug fix
- `chore`: maintenance, dependency updates, tooling, and refactors without behavior changes
- `docs`: documentation only
- `refactor`: code restructuring without behavior changes
- `test`: tests
- `ci`: CI changes

Bilingual commit messages are recommended:

- Keep the subject in English for tool compatibility.
- Add a short Chinese summary in the body.

Examples:

- `feat: add export endpoint`
- `chore: bump dependencies`

Optional: enable the commit message template with:

```bash
git config commit.template .gitmessage
```

## Pull request checklist

- Clear description of what changed and why
- Tests updated or added, if applicable
- Docs updated, if applicable
- Small, focused diffs whenever possible
