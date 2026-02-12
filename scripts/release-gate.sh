#!/usr/bin/env bash
set -euo pipefail

# ==================== 发布门禁（生产就绪最小闭环） ====================
# 用途：
# 1) 统一上线前检查入口，避免人工漏跑关键步骤
# 2) 失败即退出，阻断高风险发布
#
# 可选环境变量：
# - RELEASE_GATE_SKIP_FRONTEND=true   跳过前端检查
# - RELEASE_GATE_FAST=true            后端仅跑快速测试集（not slow）

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/auto-claude"
UI_DIR="$ROOT_DIR/auto-claude-ui"

echo "==> Release gate started"
echo "    Root: $ROOT_DIR"

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 not found"
  exit 1
fi

if ! command -v git >/dev/null 2>&1; then
  echo "ERROR: git not found"
  exit 1
fi

if ! command -v claude >/dev/null 2>&1; then
  echo "ERROR: claude CLI not found"
  exit 1
fi

echo "==> Backend environment setup"
cd "$BACKEND_DIR"
python3 -m venv .venv
source .venv/bin/activate

if [[ -f requirements.lock ]]; then
  echo "    Installing locked runtime dependencies"
  pip install -r requirements.lock
else
  echo "    Installing runtime dependencies from requirements.txt"
  pip install -r requirements.txt
fi

pip install -r ../tests/requirements-test.txt

echo "==> Production preflight doctor (strict)"
cd "$ROOT_DIR"
python3 auto-claude/run.py --doctor --doctor-strict

echo "==> Backend tests"
cd "$BACKEND_DIR"
if [[ "${RELEASE_GATE_FAST:-}" == "true" ]]; then
  .venv/bin/pytest ../tests/ -v -m "not slow" --tb=short
else
  .venv/bin/pytest ../tests/ -v --tb=short
fi

if [[ "${RELEASE_GATE_SKIP_FRONTEND:-}" == "true" ]]; then
  echo "==> Frontend checks skipped by RELEASE_GATE_SKIP_FRONTEND=true"
  echo "✅ Release gate passed (backend-only)"
  exit 0
fi

if ! command -v pnpm >/dev/null 2>&1; then
  echo "ERROR: pnpm not found"
  exit 1
fi

echo "==> Frontend checks"
cd "$UI_DIR"
pnpm install --frozen-lockfile --ignore-scripts
pnpm lint
pnpm typecheck
pnpm test

echo "✅ Release gate passed"
