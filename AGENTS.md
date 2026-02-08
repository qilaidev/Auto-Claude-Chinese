# AGENTS.md

本项目的编码代理指引（面向代码修改与任务执行）。

## 权威入口
- 先读 `CLAUDE.md`：包含完整流程、命令、发布规范。

## 仓库结构（重要）
- 生产后端：`auto-claude/`
- 生产桌面端：`auto-claude-ui/`
- `apps/` 为历史/实验目录，除非明确要求，否则不要修改。

## 中文分叉说明（Auto-Claude-Chinese）
- 默认中文提示词：`PROMPT_LANGUAGE=zh-CN`（缺失时自动回退英文）。
- 复用本地 `claude` CLI 认证（见 `auto-claude/core/auth.py`）。

## 常用流程（核心）
创建规格：
- `python auto-claude/spec_runner.py --interactive`
- 或 `python auto-claude/spec_runner.py --task "任务描述"`

执行构建：
- `python auto-claude/run.py --spec <spec-id>`

审查与合并：
- `python auto-claude/run.py --spec <spec-id> --review`
- `python auto-claude/run.py --spec <spec-id> --merge`
- `python auto-claude/run.py --spec <spec-id> --discard`

QA：
- `python auto-claude/run.py --spec <spec-id> --qa`
- `python auto-claude/run.py --spec <spec-id> --qa-status`

## 常用命令
后端环境：
- `cd auto-claude`
- `uv venv && uv pip install -r requirements.txt`
- 或 `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`

后端测试：
- `cd auto-claude`
- `uv pip install -r ../tests/requirements-test.txt`
- `auto-claude/.venv/bin/pytest tests/ -v`

前端环境：
- `cd auto-claude-ui`
- `pnpm install`
- `pnpm dev`（开发）、`pnpm build`（构建）、`pnpm start`（运行）、`pnpm package`（打包）

## 工作流与产物
- 任务规范在 `auto-claude/specs/<spec-id>/`。
- 阶段日志写入 `task_logs.json` 并在 UI 中展示。
- 工作区隔离在 `.worktrees/<spec-id>/`。

## 代码风格
- Python：类型标注、公共函数/类写 docstring、4 空格缩进。
- TypeScript/React：函数式组件、具名导出、复用既有 UI 组件。
- 尽量控制行宽 < 100，无多余空白。

## 建议与禁区
- 生产修复优先改 `auto-claude/` 或 `auto-claude-ui/`。
- 未经明确要求，不改 `apps/`。
- 不做破坏性 git 操作，除非用户明确要求。
## 其他参考
- 发布流程见 `RELEASE.md`。
