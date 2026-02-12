#!/usr/bin/env bash
# 从上游拉取并分析更新（兼容“无共同历史”的分叉仓库）

set -euo pipefail

UPSTREAM_URL="https://github.com/AndyMik90/Auto-Claude"

echo "=== Auto-Claude 中文化 - 上游同步检查 ==="
echo ""

# 检查是否在正确目录
if [[ ! -d "auto-claude" ]]; then
  echo "错误: 请在项目根目录运行此脚本"
  exit 1
fi

# 添加上游仓库（如果不存在）
if ! git remote | grep -qx "upstream"; then
  echo "添加上游仓库: $UPSTREAM_URL"
  git remote add upstream "$UPSTREAM_URL"
fi

echo "获取上游更新..."
git fetch upstream --prune

LOCAL_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
LOCAL_HEAD="$(git rev-parse HEAD)"
UPSTREAM_HEAD="$(git rev-parse upstream/main)"

echo ""
echo "当前分支: $LOCAL_BRANCH"
echo "本地 HEAD: ${LOCAL_HEAD:0:12}"
echo "上游 HEAD: ${UPSTREAM_HEAD:0:12}"

echo ""
echo "=== 提交差距统计 ==="
git rev-list --left-right --count "$LOCAL_HEAD...$UPSTREAM_HEAD" \
  | awk '{printf("本地独有提交: %s\n上游独有提交: %s\n", $1, $2)}'

MERGE_BASE=""
if MERGE_BASE="$(git merge-base "$LOCAL_HEAD" "$UPSTREAM_HEAD" 2>/dev/null)"; then
  echo ""
  echo "检测到共同祖先: ${MERGE_BASE:0:12}"
  echo ""
  echo "=== 上游新增提交（最近 30 条）==="
  git log --oneline --no-merges "$LOCAL_HEAD..$UPSTREAM_HEAD" | head -30 || true
else
  echo ""
  echo "⚠️  未检测到共同祖先（无共享历史）。"
  echo "这通常意味着当前仓库不是通过标准 fork 关系创建，而是重新初始化过历史。"
  echo ""
  echo "=== 树快照差异（按目录前缀统计）==="
  git diff --name-only "$LOCAL_HEAD" "$UPSTREAM_HEAD" \
    | awk -F/ 'NF>0 {print $1}' \
    | sort | uniq -c | sort -nr | head -20
fi

echo ""
echo "=== 提示词目录差异（快照对比）==="
git diff --name-status "$LOCAL_HEAD" "$UPSTREAM_HEAD" -- auto-claude/prompts | head -80 || true

echo ""
echo "下一步建议："
if [[ -n "${MERGE_BASE:-}" ]]; then
  echo "  1) 新建同步分支: git checkout -b sync/upstream-main-$(date +%Y%m%d)"
  echo "  2) 合并上游主干: git merge upstream/main"
else
  echo "  1) 新建同步分支: git checkout -b sync/unrelated-upstream-$(date +%Y%m%d)"
  echo "  2) 允许无共同历史合并: git merge upstream/main --allow-unrelated-histories"
  echo "  3) 冲突处理后，优先保留本仓库中文化与认证特性："
  echo "     - auto-claude/prompts/zh-CN/"
  echo "     - auto-claude/prompts_pkg/prompt_loader.py"
  echo "     - auto-claude/core/auth.py"
fi
echo "  4) 合并后运行: ./scripts/i18n/apply-translations.sh"
