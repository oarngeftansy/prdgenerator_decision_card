# QA Report: ai策划案工具正式发布

| Field | Value |
|-------|-------|
| **Date** | 2026-08-24 |
| **URL** | `http://192.168.50.210:8010/` |
| **Branch** | `codex/planner-decision-card` |
| **Commit** | `72766f81490407ffbfe88e2e8a23ce67346630ce` |
| **Tier** | Exhaustive（桌面端） |
| **Scope** | 两个正式项目、P1–P7、导航、保存、图片、布局、控制台与失败请求 |
| **Status** | 发布前基线已完成；正式部署后验收待执行 |

## 发布前健康分：暂定 75/100

正式站仍运行旧资源 `ux89/gameplay23`，该分数只记录发布前问题，不代表待部署版本。

| Category | Score |
|----------|-------|
| Console | 10 |
| Links | 100 |
| Visual | 85 |
| Functional | 70 |
| UX | 77 |
| Performance | 92 |
| Content | 100 |
| Accessibility | 100 |

## 当前问题

### ISSUE-001：历史项目 P4 参考图全部绑定旧任务目录

| Field | Value |
|-------|-------|
| **Severity** | high |
| **Category** | functional / visual / console |
| **URL** | `/?job=4180cd72eeaa4819be41db50bb4c5011&ui=gameplay` |
| **Fix commit** | `72766f8` |
| **Fix status** | 待正式部署验证 |

**复现：** 打开《一路狂飙》P4。页面请求旧任务 `8312a91c89e144e6a59f81b982f14c06` 的图片；15 个唯一 URL 均返回 404。首屏出现 5 个 `naturalWidth=0` 的可见坏图和 10 次 404 请求。

**证据：** [修复前截图](../../artifacts/qa-formal-release-20260824-issue-image-before.png)

**修复：** 每次确保玩法模型时，按 `frameId` 将证据锚点和章节内联证据重绑定到当前任务 frames，并同步纠正模型 `jobId`。

**回归测试：** `test_ensure_rebinds_copied_evidence_urls_to_the_current_job_frames`；玩法模型与审核 API 合计 54/54 通过。

### ISSUE-002：新项目初次玩法生成失败后 P1/P4 无法恢复

| Field | Value |
|-------|-------|
| **Severity** | high |
| **Category** | functional / ux |
| **URL** | `/?job=d50b2b851a9f4da68275821b39667d80` |
| **Fix commit** | `0e93df6`（已包含在当前 HEAD） |
| **Fix status** | 待正式部署验证 |

**复现：** 角色创建任务为 `gameplayReviewGeneration=failed` 且没有玩法模型；旧正式后端访问 `/gameplay-review-model` 返回 500，顶部 P4 处于不可进入状态。

**证据：** [角色创建旧正式状态](../../artifacts/qa-formal-release-20260824-role-p4-failed-before.png)

**修复：** P1 在失败/无模型状态触发结构重建；服务端允许初次失败在交互尚未确认时恢复，同时保留正常再生成的原门禁。

### ISSUE-003：P4“编辑规则”只展开被隐藏的内层容器

| Field | Value |
|-------|-------|
| **Severity** | high |
| **Category** | functional / ux |
| **URL** | `/?job=4180cd72eeaa4819be41db50bb4c5011&ui=gameplay` |
| **Fix commit** | `6935fb8`（已包含在当前 HEAD） |
| **Fix status** | 待正式部署验证 |

**复现：** 点击后 `.gameplay-rule-details.open=true`，但父级 `.gameplay-supplemental-details.open=false`，编辑器仍不可见且焦点停在 `BODY`。

**证据：** [点击后的旧正式截图](../../artifacts/qa-formal-release-20260824-edit-rules-broken-beforedeploy.png)

**修复：** 单一动作同时展开父级补充区与规则区，滚动到编辑器并聚焦第一个字段。

## 发布后验收

完整用例见 [正式发布回归测试计划](./formal-release-test-plan-2026-08-24.md)。正式部署后必须补齐：两项目 P1–P7 截图、按钮前后截图、三档桌面布局、console/network 摘要、图片 URL 复查、最终健康分和发布结论。
