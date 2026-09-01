# Planner Intelligence 当前会话交接

更新时间：2026-08-26（Asia/Shanghai）

## 一句话状态

通用证据归位与交互保存诊断已完成在应用候选 `3c3d954`，本地测试基线为 Python 1652、JavaScript 492；本交接已同步 GitHub 等价 tree 与 SVN，但正式 8010 仍未回读到新 capability/前端文案，因此“苏丹的游戏”正式 P1–P7 验收尚未开始，Phase 3 继续暂停。

## 新会话开始前必须做

1. 完整读取 `AGENTS.md`、三份 `.claude/memory`、本文件、`CONTEXT.md`、`CURRENT_STATE.md` 和 `handoff_state.json`。
2. 核对真实 HEAD、分支、tracked status、远端分支、SVN manifest 和正式 health/served JS。
3. 禁止 reset、stash、覆盖、清理或提交用户/历史修改；精确暂存。特别保护 `scripts/publish_current_alignment_to_feishu.py`。
4. 当前项目不再迭代《一路狂飙》；它只可作为不可修改的历史回归样本。不要把它列为当前项目、交付目标或待复审事项；不启动 Phase 3。

## 权威架构边界

`Evidence → AtomicFact → AtomicRule/RuleCandidate → Intent → Canonical Owner → Closure → Guard → Review → PublicationProjection → Final`

- 截图是静态证据媒介，不等于玩家无操作；未知操作进入策划决策卡。
- Interaction Model 建立后，每个项目始终有 Gameplay Model；失败保留 rule-free skeleton 或 last-valid。
- GET 只读，不因惰性补建失败返回 500，不在读取时隐式消耗 AI。
- 静态展示、当前数值、公式、配置和证据摘要不能冒充 Gameplay Flow；证据不足进入 Planner Decision。
- 结构质量、review-entry grounded draft、最终 delivery quality 是三个独立门槛。
- 缓存包含 project/job、Approved revision、evidence fingerprint 和 generation contract；禁止跨项目污染。
- 同一标准覆盖已有、新建、失败、迁移和所有输入类型，不允许项目/job 特判。

## 当前提交与同步

- 分支：`codex/planner-decision-card`
- 应用 commit：`3c3d954a677eacdd7f720bb1e990d8af14d131c4`（交互保存错误分流）
- 父提交：`b80870d248c1ae9470ebdffa218f6f8502db6e56`（证据归位）
- 交接 commit：以新会话 `git rev-parse HEAD` 为准；它只修改记忆与交接文件，不是新的应用部署候选。
- GitHub：通过受控 API 推送与 tree 校验完成；远端 SHA 以新会话 API/`ls-remote` 回读为准，tree 必须等于本地 HEAD tree。常规 Git helper/443 曾不稳定。
- SVN：`ai_gamedesigntool` 交接已同步；新会话以 release manifest 的 last-changed revision 和 sourceCommit 回读为准。应用部署仍使用 `3c3d954` Brand Update，不因文档提交重建应用包。
- 正式：`http://192.168.50.210:8010/` 尚未证明包含本候选。

## 已完成的通用修复

- 无 Evidence carrier 的机制叙述、参数、公式、配置和验收套话不再成为 Gameplay Rule。
- legacy 参数只有值确实出现在本章证据时保留，其他转决策卡。
- presentation/numeric/config 不再无条件进入 normalFlow；质量检查使用真实 carrier。
- Prompt contract 为 `gameplay-detail-v6-evidence-grounded-review`；capability 为 `evidence-grounded-gameplay-review-v1`。
- 保存错误分流：409 同步 canonical revision；缺 observed action 给具体策划提示；其他 400 显示确认条件未满足；网络/5xx 才显示服务故障。

## 测试基线

- Python：`1652 passed`
- JavaScript：`492 passed`
- 证据归位聚焦回归：`137 passed`
- 正式浏览器全按钮 QA：未完成。

## 正式部署与任务事实

- Brand Update：`artifacts/deploy-brand-update-20260825-15bfa38/3c3d954/brand-update-3c3d954.exe`
- SHA-256：`E05D52515B8D49C8B21788F44C35B464585F34D40BC54EE0853724E737F81CD3`
- 正式最后回读缺少 `evidence-grounded-gameplay-review-v1`，served JS 也缺少 `当前环节缺少已确认的玩家操作` 和 `当前环节尚未满足确认条件`，所以部署未闭环。
- 杂货铺 `9e982100a25843f78c44793df15d3237` 最后观察：Interaction revision 38、7/7 confirmed、Gameplay revision 32、generation completed；新会话必须重新回读。
- RDP 3389 可达，SMB 445/WinRM 5985 不可达；mstsc 捕获失败、Chrome 因 URL 不确定被安全门禁停止，不能宣称浏览器 QA 已完成。

## 产品范围与 Planning Sketch

- 当前唯一迭代主线是 Planner Intelligence 网页工具的通用产品能力。《一路狂飙》Final Delivery 已退出当前项目范围，下方或历史文件中的相关 revision/候选状态仅作历史记录。
- Planning Sketch 仍暂停。网页稳定后先只读审计 pipeline、旧产物、兼容和发布路径。
- Phase 3 未开始。

## 下一步严格顺序

1. 回读正式 health、served `js/backend.js` 和 application marker；不匹配则运行正确 Brand Update 后再次回读。
2. 部署确认后，用 `C:\Users\momoca\Desktop\苏丹的游戏` 的 18 张 JPG 与 1 个 MP4 创建隔离新任务。
3. 跑 P1–P7 和每个按钮，验证 URL/历史、刷新、编辑保存、重试、图片、决策卡、数据隔离、控制台、失败请求和最终导出。
4. 审计最终内容的 Owner、因果流程、Evidence、无常识填充、无实现/表现污染、无虚构机制和无重复定义。
5. 冒烟杂货铺、角色创建和至少一个额外隔离新任务；历史 fixture 只读，不开展内容迭代。全部通过后才宣布正式发布。
6. 随后恢复 Planning Sketch 只读审计，不开启 Phase 3。
