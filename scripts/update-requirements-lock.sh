#!/usr/bin/env bash
set -euo pipefail

# ==================== 后端依赖锁文件刷新 ====================
# 基于 auto-claude/requirements.txt 生成 auto-claude/requirements.lock
# 用法：
#   ./scripts/update-requirements-lock.sh

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/auto-claude"
OUT_FILE="$BACKEND_DIR/requirements.lock"
TMP_DIR="$(mktemp -d)"

cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

python3 -m venv "$TMP_DIR/venv"
source "$TMP_DIR/venv/bin/activate"
pip install -r "$BACKEND_DIR/requirements.txt"

pip freeze \
  | sed '/^pip==/d;/^setuptools==/d;/^wheel==/d' \
  > "$OUT_FILE"

echo "✅ Updated: $OUT_FILE"
