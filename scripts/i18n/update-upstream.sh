#!/bin/bash
# 从上游拉取更新的脚本

set -e

echo "=== Auto-Claude 中文化 - 上游更新脚本 ==="
echo ""

# 检查是否在正确的目录
if [ ! -d "auto-claude" ]; then
    echo "错误: 请在项目根目录运行此脚本"
    exit 1
fi

# 添加上游仓库（如果还没有添加）
if ! git remote | grep -q "upstream"; then
    echo "添加上游仓库..."
    git remote add upstream https://github.com/AndyMik90/Auto-Claude
fi

# 获取上游更新
echo "获取上游更新..."
git fetch upstream

# 显示差异
echo ""
echo "=== 上游更新摘要 ==="
git log HEAD..upstream/main --oneline --no-merges

echo ""
echo "=== 提示词文件变更 ==="
git diff HEAD..upstream/main --name-only -- auto-claude/prompts/

echo ""
echo "提示: 使用以下命令合并上游更新:"
echo "  git merge upstream/main"
echo ""
echo "合并后，请运行 apply-translations.sh 重新应用中文翻译"
