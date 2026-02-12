# Auto-Claude-Chinese（简体中文）

> Language / 语言：**[English](README.en.md)** | **[Mixed](README.md)**

Auto-Claude-Chinese 是上游 [Auto-Claude](https://github.com/AndyMik90/Auto-Claude)
的中文增强分叉，目标是：**保留上游工程能力，同时提供开箱即用的中文体验**。

## 这个分叉解决了什么问题？

### 1) 默认中文提示词（可回退英文）

- 默认：`PROMPT_LANGUAGE=zh-CN`
- 机制：中文提示词缺失时自动回退英文
- 范围：核心流程提示词 + MCP 工具提示词

### 2) 复用本地 Claude CLI 认证

无需额外 API Key，直接复用本地 `claude` 已登录态。  
认证优先级（从高到低）：

1. `CLAUDE_CODE_OAUTH_TOKEN`
2. `ANTHROPIC_AUTH_TOKEN` / `ANTHROPIC_API_KEY`
3. `~/.claude/settings.json`
4. macOS Keychain（官方 OAuth）

## 核心能力

- **自主任务流**：需求 → 规格 → 计划 → 编码 → QA
- **并行 Agent 会话**：多任务并行执行，提升吞吐
- **隔离工作区**：基于 Git worktree，不污染主分支
- **QA 闭环**：自动审查 + 自动修复 + 人工复核
- **桌面端可视化**：看板、日志、上下文注入、状态追踪

## 快速开始（推荐 UI）

### 前置要求

1. Node.js 20+
2. Python 3.10+
3. Docker Desktop
4. Claude Code CLI：`npm install -g @anthropic-ai/claude-code`

### 1) 初始化后端

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

## CLI 常用命令

```bash
python auto-claude/spec_runner.py --interactive
python auto-claude/spec_runner.py --task "任务描述"
python auto-claude/run.py --spec <spec-id>
python auto-claude/run.py --spec <spec-id> --review
python auto-claude/run.py --spec <spec-id> --merge
python auto-claude/run.py --spec <spec-id> --discard
python auto-claude/run.py --spec <spec-id> --qa
python auto-claude/run.py --spec <spec-id> --qa-status
```

## 仓库结构（重要）

- `auto-claude/`：生产后端（Agent 编排与执行核心）
- `auto-claude-ui/`：生产桌面端（Electron + React）
- `apps/`：历史/实验目录（默认不参与生产修改）

## 与上游同步（关键）

本仓库上游固定为：
`https://github.com/AndyMik90/Auto-Claude`

建议每周至少同步一次：

```bash
./scripts/i18n/update-upstream.sh
```

如果脚本提示“无共同祖先”，使用：

```bash
git checkout -b sync/unrelated-upstream-$(date +%Y%m%d)
git merge upstream/main --allow-unrelated-histories
```

同步后务必执行：

```bash
./scripts/i18n/apply-translations.sh
python scripts/i18n/check-prompt-loader.py
```

详细说明见：`scripts/i18n/README.md`

## 测试

```bash
cd auto-claude
uv pip install -r ../tests/requirements-test.txt
.venv/bin/pytest ../tests/ -v
```

## 开源协作

- 贡献指南：`CONTRIBUTING.md`
- CLA：`CLA.md`
- 发布流程：`RELEASE.md`
- 许可证：`LICENSE`（AGPL-3.0）
