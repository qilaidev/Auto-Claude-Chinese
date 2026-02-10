# Auto-Claude 上线验收清单（Go-Live Checklist）

本文档用于“准备立即上线生产并长期稳定运行”的最终验收。

原则：

- 小步上线：所有项可验证、可回滚。
- 先门禁再放量：通过门禁后再开放给真实项目。
- 任何未确认项都按阻断处理（No-Go）。

---

## 0. 基本信息（发布前填写）

- 发布日期（UTC+8）：`____-__-__ __:__`
- 发布负责人：`________`
- 值班人（On-call）：`________`
- 回滚负责人：`________`
- 目标环境路径：`________________________`
- 目标版本/提交：`________________________`

---

## 1. 必过门禁（Go / No-Go）

### 1.1 后端测试

在仓库根目录执行：

```bash
./.venv-codex/bin/pytest tests/ -q
```

- [ ] 通过（无失败）

### 1.2 前端测试（如使用 UI）

```bash
cd auto-claude-ui
pnpm test
```

- [ ] 通过（无失败）

### 1.3 预检门禁（strict）

```bash
python auto-claude/run.py --doctor --doctor-strict
```

- [ ] 通过（0 warnings / 0 failures）

### 1.4 敏感信息扫描

```bash
./auto-claude/scan-for-secrets --all-files
```

- [ ] 通过（无泄露）

---

## 2. 生产配置确认

至少确认以下变量（建议写入部署环境，不写入仓库明文）：

- [ ] 认证可用（以下之一）
  - `CLAUDE_CODE_OAUTH_TOKEN`
  - `ANTHROPIC_AUTH_TOKEN`
  - `ANTHROPIC_API_KEY`
- [ ] 日志已启用
  - `AUTO_CLAUDE_LOG_FILE` 或 `AUTO_CLAUDE_LOG_DIR`
- [ ] 脏工作区合并保护开启（默认）
  - `AUTO_CLAUDE_ALLOW_DIRTY_MERGE=false`
- [ ] 自动备份开启（默认）
  - `AUTO_CLAUDE_DISABLE_AUTO_BACKUP=false`
- [ ] 备份保留策略合理
  - `AUTO_CLAUDE_MAX_BACKUPS_PER_SPEC=20`（或按磁盘策略调整）
- [ ] 状态陈旧阈值明确
  - `AUTO_CLAUDE_STATUS_STALE_HOURS=6`（按班次调整）
- [ ] 磁盘阈值符合主机容量
  - `AUTO_CLAUDE_DOCTOR_MIN_FREE_MB=1024`
  - `AUTO_CLAUDE_DOCTOR_FAIL_FREE_MB=256`
- [ ] 事故告警（可选但推荐）
  - `AUTO_CLAUDE_ALERT_WEBHOOK_URL` 使用 `https://`
  - `AUTO_CLAUDE_ALERT_TIMEOUT_SECONDS=3`

---

## 3. 运行前演练（建议）

### 3.1 备份与恢复演练

```bash
# 先创建一个 spec 的备份（通过 discard/cleanup 自动触发，或准备已有备份）
python auto-claude/run.py --spec <spec-id> --list-backups

# 恢复最新备份（演练环境）
python auto-claude/run.py --spec <spec-id> --restore-backup
```

- [ ] 备份可列出
- [ ] 恢复可执行

### 3.2 僵死状态处理演练

如果 `--doctor` 报 stale status / stale lock：

```bash
ps aux | grep "auto-claude/run.py"
rm -f .auto-claude-status
rm -f .auto-claude/.locks/merge-*.lock
```

- [ ] 值班同学已掌握处理步骤

---

## 4. 上线后 24 小时观察点

- [ ] `--doctor --doctor-strict` 每日巡检至少 1 次
- [ ] `.auto-claude/incidents/` 无新增 fatal 报告
- [ ] `.auto-claude/backups/` 正常增长并未异常膨胀
- [ ] 日志轮转正常（大小和数量符合预期）
- [ ] 无“status stale / lock stale”反复出现

---

## 5. 快速回滚预案

### 5.1 代码回滚

- 使用 git 回滚至上一稳定提交（tag/commit）。

### 5.2 数据回滚

```bash
python auto-claude/run.py --spec <spec-id> --restore-backup --overwrite-existing --yes
```

### 5.3 UI 后端回滚（打包版）

- 删除 `userData/auto-claude-source/`，重启后回到内置后端。
- 若存在 `.auto-claude-source.backup`，可重命名恢复。

---

## 6. 最终发布判定

- [ ] 所有 1.x 门禁项全部通过
- [ ] 至少 1 名非发布人完成交叉复核
- [ ] 回滚负责人确认可在 10 分钟内执行回滚

**判定**：`GO / NO-GO`（圈选）

**备注**：

```
____________________________________________________________
____________________________________________________________
```

