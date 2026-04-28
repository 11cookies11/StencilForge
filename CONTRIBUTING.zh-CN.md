# 贡献指南

语言：简体中文 | [English](CONTRIBUTING.md)

感谢你愿意参与这个项目。

## 开始之前

- 先搜索已有的 Issue 和 Pull Request。
- 保持讨论友善和尊重，见 `CODE_OF_CONDUCT.md`。

## 流程

1. 先开 Issue 描述变更。
2. 如果变更被接受，再提交关联该 Issue 的 Pull Request。

## 提交信息和 PR 标题

本项目使用 Conventional Commits：

`<type>(可选 scope): <description>`

常见 type：

- `feat`：新功能
- `fix`：修复 bug
- `chore`：维护、依赖更新、工具、无行为变化的重构
- `docs`：仅文档修改
- `refactor`：不改变行为的代码重组
- `test`：测试相关
- `ci`：CI 修改

推荐使用中英双语提交信息：

- 标题保留英文，方便工具处理。
- 正文补一段简短中文摘要。

示例：

- `feat: add export endpoint`
- `chore: bump dependencies`

可选：启用提交信息模板：

```bash
git config commit.template .gitmessage
```

## PR 自检清单

- 清楚说明改了什么、为什么改
- 如有必要，补充或更新测试
- 如有必要，更新文档
- 尽量保持变更小而聚焦
