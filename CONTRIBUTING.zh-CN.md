# 贡献指南

语言：简体中文 | [English](CONTRIBUTING.md)

感谢你愿意贡献这个项目！

## 开始之前

- 先搜索是否已有相关的 Issue / PR。
- 保持尊重与友善（见 `CODE_OF_CONDUCT.md`）。

## 流程

1. 先开 Issue 描述变更（缺陷 / 功能 / 文档等）。
2. 讨论确认后，提交 PR，并在 PR 中关联对应的 Issue。

## 提交信息与 PR 标题

本模板推荐使用 Conventional Commits（语义化提交）风格：

`<type>(可选 scope): <description>`

常用 type：

- `feat`：新增功能
- `fix`：修复缺陷
- `chore`：维护类工作（依赖、工具、无行为变化的重构等）
- `docs`：仅文档改动

示例：

推荐中英共存的提交信息：

- 标题使用英文（对工具/校验更友好）
- 在正文中补充一段简短中文摘要

示例（标题 + 正文）：

- `feat: add export endpoint` + 正文：`增加导出接口`
- `chore: bump dependencies` + 正文：`升级依赖`

可选：启用提交信息模板：

- `git config commit.template .gitmessage`

## PR 自检清单

- 清晰描述改了什么、为什么改
- 更新/新增测试（如适用）
- 更新文档（如适用）
- 尽量保持改动小而聚焦
