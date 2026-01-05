# Auto-Claude 中文化维护指南

本目录包含用于维护 Auto-Claude 中文版本的脚本和文档。

**上游仓库**: https://github.com/AndyMik90/Auto-Claude

## 目录结构

```
scripts/i18n/
├── update-upstream.sh      # 从上游拉取更新
├── apply-translations.sh   # 检查和应用中文翻译
├── check-prompt-loader.py  # 检查提示词加载与回退
└── README.md              # 本文档

auto-claude/prompts/
├── *.md                   # 英文原版提示词
└── zh-CN/
    └── *.md              # 中文翻译提示词
```

## 仓库定位与汉化原则

- 本仓库定位为 Auto-Claude-Chinese，中文优先（提示词与 UI 均以中文为主）
- 不引入 i18n 框架，直接在 UI 文本与提示词文件中做翻译与校对
- 合并上游更新时先拉取代码，再补齐中文提示词与 UI 文本，确保新增功能的中文覆盖
- 命令、文件路径、代码片段、变量名与占位符保持英文原样，避免破坏原有含义

## 使用方法

### 1. 检查上游更新

定期运行此脚本检查上游是否有新的更新：

```bash
cd /Users/jiesen/Desktop/Auto-Claude-2.6.5
./scripts/i18n/update-upstream.sh
```

这个脚本会：
- 添加上游仓库（如果还没有）
- 获取最新的上游更新
- 显示提示词文件的变更

### 2. 合并上游更新

如果有更新，使用以下命令合并：

```bash
git merge upstream/main
```

解决可能的冲突后，继续下一步。

### 3. 应用中文翻译

合并后运行此脚本检查翻译状态：

```bash
./scripts/i18n/apply-translations.sh
```

这个脚本会：
- 统计英文和中文提示词文件数量
- 检查是否有新文件需要翻译
- 提供维护建议

### 4. 检查提示词加载

确认提示词加载和回退逻辑正常：

```bash
python scripts/i18n/check-prompt-loader.py
PROMPT_LANGUAGE=zh-CN python scripts/i18n/check-prompt-loader.py
PROMPT_LANGUAGE=en python scripts/i18n/check-prompt-loader.py
```

### 5. 翻译新文件

如果发现有新的英文提示词文件，需要手动翻译：

1. 复制英文文件到 `auto-claude/prompts/zh-CN/`
2. 翻译文件内容，遵循以下原则：
   - 保持 Markdown 格式和结构
   - 技术术语保留英文（JSON, API, Git, Python 等）
   - 角色定义、指令、输出格式全部翻译成中文
   - 确保翻译准确、专业

## 翻译原则

### 保留英文的内容
- 技术术语：JSON, API, REST, Git, Python, JavaScript 等
- 代码示例和命令
- 文件路径和变量名
- URL 和链接

### 需要翻译的内容
- 角色定义和职责描述
- 工作流程和步骤说明
- 输出格式要求
- 示例说明文字
- 注意事项和提示

### 翻译风格
- 使用专业、准确的技术中文
- 保持简洁明了
- 避免过度口语化
- 保持与原文相同的语气和风格

## 配置说明

在 `auto-claude/.env` 文件中设置语言：

```bash
# 使用中文提示词
PROMPT_LANGUAGE=zh-CN

# 使用英文提示词
# PROMPT_LANGUAGE=en
```

## 维护流程

1. **定期检查更新**（建议每周一次）
   ```bash
   ./scripts/i18n/update-upstream.sh
   ```

2. **合并更新**
   ```bash
   git merge upstream/main
   ```

3. **检查翻译状态**
   ```bash
   ./scripts/i18n/apply-translations.sh
   ```

4. **检查提示词加载**
   ```bash
   python scripts/i18n/check-prompt-loader.py
   ```

5. **翻译新文件**
   - 手动翻译或使用 AI 辅助
   - 保存到 `auto-claude/prompts/zh-CN/`

6. **测试验证**
   - 设置 `PROMPT_LANGUAGE=zh-CN`
   - 运行 Auto-Claude 测试功能

7. **提交更改**
   ```bash
   git add .
   git commit -m "更新中文翻译"
   git push
   ```

## 故障排除

### 问题：中文提示词未生效

**解决方案：**
1. 检查 `.env` 文件中 `PROMPT_LANGUAGE=zh-CN` 是否正确设置
2. 确认中文提示词文件存在于 `auto-claude/prompts/zh-CN/`
3. 重启 Auto-Claude 应用

### 问题：合并冲突

**解决方案：**
1. 查看冲突文件：`git status`
2. 手动解决冲突
3. 标记为已解决：`git add <file>`
4. 完成合并：`git commit`

### 问题：翻译文件缺失

**解决方案：**
运行 `./scripts/i18n/apply-translations.sh` 查看缺失的文件列表，然后手动翻译。

## 贡献指南

如果你想改进中文翻译：

1. Fork 本仓库
2. 创建特性分支：`git checkout -b improve-translation`
3. 修改翻译文件
4. 提交更改：`git commit -m "改进 XXX 的中文翻译"`
5. 推送分支：`git push origin improve-translation`
6. 创建 Pull Request

## 联系方式

如有问题或建议，请在 GitHub 上创建 Issue。
