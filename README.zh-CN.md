# Auto-Claude-Chinese（简体中文）

> Language / 语言：**[English](README.en.md)** | **[Mixed](README.md)**

Auto-Claude-Chinese 是 Auto Claude 的中文增强分叉版：

- 默认中文提示词（`PROMPT_LANGUAGE=zh-CN`）
- 中文提示词缺失时自动回退英文
- 复用本地 `claude` CLI 认证状态，无需额外 API Key

如果你在找这些关键词，本项目都覆盖：
`AI 编程代理`、`多 Agent 开发`、`Claude Code`、`自动化编码`、`Git Worktree`。

## 核心能力

- **自主任务流**：输入需求后，Agent 自动完成规划、编码、QA 校验。
- **并行 Agent 终端**：支持多会话并行开发，提升复杂任务吞吐。
- **隔离工作区**：基于 Git worktree，默认不污染主分支。
- **自校验循环**：内置 QA 审查与修复闭环。
- **桌面端体验**：可视化任务看板、上下文注入、进度追踪。

## 中文分叉特色

### 1) 全面中文提示词

- 默认 `PROMPT_LANGUAGE=zh-CN`
- 核心流程 + PR 审查链路均提供中文提示词
- 可在 `auto-claude/.env` 中切换为英文：`PROMPT_LANGUAGE=en`

### 2) 本地认证复用

无需手动管理 API Key，按以下顺序自动获取认证：

1. `CLAUDE_CODE_OAUTH_TOKEN`
2. `~/.claude/settings.json`
3. macOS Keychain

关键实现：`auto-claude/core/auth.py`

## 快速开始

### 前置条件

1. Node.js 20+
2. Python 3.10+
3. Docker Desktop
4. Claude Code CLI（`npm install -g @anthropic-ai/claude-code`）

### 1) 后端环境

```bash
cd auto-claude
uv venv && uv pip install -r requirements.txt
# 或
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
```

### 2) 启动记忆层

```bash
docker-compose up -d falkordb
```

### 3) 启动桌面端

```bash
cd auto-claude-ui
pnpm install
pnpm run build && pnpm run start
```

### 4) 创建并执行任务

```bash
python auto-claude/spec_runner.py --task "实现一个登录功能"
python auto-claude/run.py --spec <spec-id>
```

## 仓库结构

- `auto-claude/`：生产后端（核心执行引擎）
- `auto-claude-ui/`：生产桌面端（Electron + React）
- `apps/`：历史/实验目录（默认不参与生产修改）

## 开源协作

- 贡献指南：`CONTRIBUTING.md`
- CLA 说明：`CLA.md`
- 发布流程：`RELEASE.md`
- 许可证：`LICENSE`（AGPL-3.0）

欢迎提交 Issue、PR 和改进建议。
