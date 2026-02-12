#!/usr/bin/env bash
# 生产就绪闸门检查（面向 auto-claude / auto-claude-ui 生产目录）

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

echo "=== Auto-Claude 生产就绪闸门检查 ==="
echo "仓库根目录: $ROOT_DIR"
echo ""

if [[ ! -d "auto-claude" ]]; then
  echo "错误: 未找到 auto-claude 目录，请在仓库根目录执行。"
  exit 1
fi

echo "1) 预检（doctor strict）"
if [[ "${AUTO_CLAUDE_READY_ALLOW_DIRTY:-}" == "true" ]]; then
  echo "提示: AUTO_CLAUDE_READY_ALLOW_DIRTY=true，doctor 使用非 strict 模式。"
  python3 auto-claude/run.py --doctor
else
  python3 auto-claude/run.py --doctor --doctor-strict
fi
echo ""

echo "2) 安全基线（密钥扫描）"
./auto-claude/scan-for-secrets --all-files
echo ""

echo "3) 关键回归测试（生产核心路径）"
./scripts/ops/run-production-tests.sh
echo ""

echo "✅ 生产就绪闸门通过（核心路径）"
echo "提示: 上线前仍建议按需执行全量测试与 UI 打包验证。"
