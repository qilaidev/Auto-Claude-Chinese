# Auto-Claude-Chinese (English)

> Language / 语言：**[简体中文](README.zh-CN.md)** | **[Mixed](README.md)**

Auto-Claude-Chinese is a Chinese-enhanced fork of Auto Claude for autonomous
software development with multi-agent workflows.

- Default Chinese prompts via `PROMPT_LANGUAGE=zh-CN`
- Automatic fallback to English prompts when Chinese prompts are missing
- Reuses local authenticated `claude` CLI credentials (no extra API key required)

Search terms this project targets:
`AI coding agent`, `multi-agent coding`, `Claude Code`,
`autonomous development`, `Git worktree workflow`.

## Key Capabilities

- **Autonomous task pipeline**: agents plan, implement, and validate tasks end-to-end.
- **Parallel agent terminals**: run multiple coding sessions concurrently.
- **Isolated workspaces**: every task runs in a Git worktree to protect `main`.
- **Self-validation loop**: integrated QA review + fix cycle before merge.
- **Desktop UX**: visual Kanban task flow, context injection, real-time progress.

## Chinese Fork Highlights

### 1) Full Chinese prompt experience

- Default `PROMPT_LANGUAGE=zh-CN`
- Chinese prompts for core workflow and PR review paths
- Switch back to English with `PROMPT_LANGUAGE=en` in `auto-claude/.env`

### 2) Local auth reuse

No manual API key management. Auth resolution priority:

1. `CLAUDE_CODE_OAUTH_TOKEN`
2. `~/.claude/settings.json`
3. macOS Keychain

Implementation reference: `auto-claude/core/auth.py`

## Quick Start

### Prerequisites

1. Node.js 20+
2. Python 3.10+
3. Docker Desktop
4. Claude Code CLI (`npm install -g @anthropic-ai/claude-code`)

### 1) Backend setup

```bash
cd auto-claude
uv venv && uv pip install -r requirements.txt
# or
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
```

### 2) Start memory layer

```bash
docker-compose up -d falkordb
```

### 3) Launch desktop app

```bash
cd auto-claude-ui
pnpm install
pnpm run build && pnpm run start
```

### 4) Create and run a task

```bash
python auto-claude/spec_runner.py --task "Implement authentication"
python auto-claude/run.py --spec <spec-id>
```

## Repository Layout

- `auto-claude/`: production backend (orchestration engine)
- `auto-claude-ui/`: production desktop app (Electron + React)
- `apps/`: legacy/experimental area (avoid for production changes)

## Open Source Collaboration

- Contribution guide: `CONTRIBUTING.md`
- CLA process: `CLA.md`
- Release process: `RELEASE.md`
- License: `LICENSE` (AGPL-3.0)

Issues and pull requests are welcome.
