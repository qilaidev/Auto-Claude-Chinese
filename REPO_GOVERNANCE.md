# REPO_GOVERNANCE

更新时间：2026-04-12
仓库：`Auto-Claude-Chinese`

## 仓库定位
Auto Claude 的中文增强版 / 本地化 fork，包含中文提示词、认证复用与桌面应用流程，属于正式项目，不是垃圾目录。

## 当前判断
- 本地状态：目录保留
- 云端状态：`tytsxai/Auto-Claude-Chinese`，public，未归档
- 当前分类：继续维护候选 / 可继续公开
- 风险级别：中（涉及本地 Claude 认证复用与中文化维护）

## 已确认事实
- `README.md:8` 明确其为 Auto-Claude 中文增强版
- `README.md:18` 起说明其核心特色是中文提示词与复用本地 `claude` CLI 认证状态
- `README.md:29` 起列出认证优先级，涉及 OAuth、`~/.claude/settings.json` 与 macOS Keychain
- `README.md:51` 指出生产/发布基准目录为 `auto-claude/` 与 `auto-claude-ui/`
- `.git/config:8` 远端为 `git@github.com:tytsxai/Auto-Claude-Chinese.git`
- GitHub 已核实：`tytsxai/Auto-Claude-Chinese` 为 public、未归档

## 建议动作
### 本地
- 保留目录
- 继续维护

### 云端
- 当前 public 状态可以继续保留
- 但应持续复核认证说明，避免让外部用户误解本地凭证复用边界
- 如果后续维护停滞，可再判断是否转为归档型 fork

## 待办
- [ ] 判断是否仍在活跃维护中文提示词与发布流程
- [ ] 复核认证与安全说明，避免将本地凭证复用描述成“零风险”能力
- 2026-04-12：完成第三批仓库首轮治理盘点，确认其为公开中文 fork 项目
