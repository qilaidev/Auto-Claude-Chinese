# Auto-Claude-Chinese 汉化与上游同步指南

本目录用于维护 **Auto-Claude-Chinese** 的两条核心能力：

1. 中文提示词与中文文档质量  
2. 与上游仓库 `https://github.com/AndyMik90/Auto-Claude` 的持续同步

---

## 目录结构

```text
scripts/i18n/
├── README.md                 # 本文档
├── update-upstream.sh        # 拉取并分析上游更新（支持无共同历史检测）
├── apply-translations.sh     # 检查提示词翻译覆盖率
└── check-prompt-loader.py    # 校验多语言加载与回退逻辑
```

对应提示词目录：

```text
auto-claude/prompts/
├── *.md                      # 英文提示词
├── mcp_tools/*.md            # 英文 MCP 提示词
└── zh-CN/
    ├── *.md                  # 中文提示词
    └── mcp_tools/*.md        # 中文 MCP 提示词
```

---

## 维护原则（必须遵守）

- **中文优先**：`PROMPT_LANGUAGE=zh-CN` 作为默认行为。  
- **功能先同步，翻译后补齐**：先合并上游功能，再补新增提示词与文档翻译。  
- **不破坏机器语义**：命令、变量名、路径、占位符保持英文原样。  
- **翻译要可执行**：任何中文文档中的命令都必须可复制运行。

---

## 标准流程

### 1) 检查上游更新

```bash
cd <repo-root>
./scripts/i18n/update-upstream.sh
```

脚本会输出：
- 本地与上游提交差距
- 是否存在共同祖先（merge-base）
- 提示词目录变更摘要
- 下一步推荐命令

> 注意：如果提示“无共同祖先”，说明当前分叉历史与上游不是标准 fork 链路。  
> 这种情况下必须使用 `--allow-unrelated-histories` 进行首次历史对接。

### 2) 同步上游代码

有共同祖先时：

```bash
git checkout -b sync/upstream-main-$(date +%Y%m%d)
git merge upstream/main
```

无共同祖先时：

```bash
git checkout -b sync/unrelated-upstream-$(date +%Y%m%d)
git merge upstream/main --allow-unrelated-histories
```

### 3) 检查翻译覆盖

```bash
./scripts/i18n/apply-translations.sh
```

### 4) 检查提示词加载/回退

```bash
python scripts/i18n/check-prompt-loader.py
PROMPT_LANGUAGE=zh-CN python scripts/i18n/check-prompt-loader.py
PROMPT_LANGUAGE=en python scripts/i18n/check-prompt-loader.py
```

---

## 重点冲突文件（上游同步时）

合并冲突时，以下文件需重点人工复核：

- `auto-claude/core/auth.py`（本地 CLI 认证复用能力）
- `auto-claude/prompts_pkg/prompt_loader.py`（中文回退机制）
- `auto-claude/prompts/zh-CN/**`（中文提示词资产）
- `README.zh-CN.md`、`README.md`（中文文档入口与说明）

建议原则：
- **功能代码尽量跟上游**，避免长期分叉腐化。
- **中文化能力作为本仓库补丁层**，保持可重放、可维护。

---

## 翻译质量标准（建议 PR 自检）

- 术语统一：Prompt/Agent/Spec/Worktree/QA 保持一致译法。  
- 结构一致：标题层级、列表语义、代码块位置与英文保持对齐。  
- 可读性优先：短句、少歧义，避免中英混杂导致误解。  
- 可验证：命令示例在 macOS/Linux 至少可执行一次。

---

## 故障排查

### 中文提示词未生效

1. 检查 `auto-claude/.env` 是否配置 `PROMPT_LANGUAGE=zh-CN`  
2. 检查 `auto-claude/prompts/zh-CN/` 是否存在目标文件  
3. 运行 `python scripts/i18n/check-prompt-loader.py` 验证回退链路

### 上游合并冲突过多

1. 不要直接在 `main` 合并，先建 `sync/*` 分支  
2. 先解决核心执行链路（`auto-claude/`），再处理文档与 UI  
3. 每解决一批冲突就运行测试，避免一次性大爆炸

---

## 一句话策略

**上游做“功能主干”，本仓做“中文补丁层”；保持同步节奏，比一次性大合并更重要。**
