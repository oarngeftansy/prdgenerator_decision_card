# Planner Review Density Reduction

## 目标与产品边界

降低 `/mechanic-review` 的默认信息密度，使主策能在 10 秒内识别每个 Mechanic 的核心玩法规则。

`/mechanic-review` 是独立 Mechanic Review Layer，不是 P7。P7、Final Publication、Mechanic Model、原始 design item、Depth、Evidence / Fact / Rule / Requirement / Proposal lineage 与 `job.json` 均不修改。

## 方案

在现有只读 `plannerReadableSections` 上增加 Rule Importance Gate，并生成默认层与 Expand Detail 双层投影。默认层只消费通过 Importance Gate 的高价值规则；其他内容仍保留于后台模型或详情层。

不采用直接删除数据，也不采用前端按数量截断。

## 默认主策视图

每个 Mechanic 仅按以下顺序展示：

1. 核心规则：3～6 条
2. 分支 / 特殊规则：0～4 条
3. 参数：0～3 个
4. 需要主策决策的设计分叉：0～2 个

已确认规则与 AI 补全规则继续用不同颜色圆点区分，但不显示逐条文字标签。

默认隐藏并统一进入 Expand Detail：

- Core Design Depth 与 Remediation
- QA 可验证结果
- 原始规则与依据
- lineage、Requirement、Proposal、Dimension
- 跨系统技术依赖
- internal lifecycle label
- “主策审核后仍需补齐”说明
- supporting execution detail 与被去重的表达

## Rule Importance Gate

默认规则至少满足一项：

- 改变玩家选择或玩法结果；
- 改变状态机；
- 改变数值、资源或随机结果；
- 改变核心分支；
- 改变跨系统业务关系；
- 未定义时会产生两种不同且合理的玩法实现。

否则降为 supporting detail，不进入默认视图。

Rule Importance 只控制展示，不修改原始规则价值、状态或 Depth 计分。

## 去重与正确废话 Gate

- 删除被后续具体分支完全覆盖的概述句。
- 合并可由更强规则直接推出的同义后果。
- 保留会改变玩法结果的例外，不因缩短页面删除真实分支。
- 每个默认 bullet 继续保留 `sourceDesignItemIds[]`；被降级或去重的来源 ID 写入详情 metadata。

当前重点：

- 三选一删除“未选择候选不生效”等正确废话，合并生成、选择、生效与恢复表达。
- 武器删除“先判断新旧武器”的概述句，由新武器和重复武器分支直接表达。
- 怪物删除“单怪脱离不影响其他怪物”等已由独立结算规则覆盖的重复后果。

## 展示数据契约

每个 Mechanic 的密度投影至少包含：

- `defaultSections[]`
- `expandDetail`
- `beforeDefaultRuleCount`
- `afterDefaultRuleCount`
- `downgradedSupportingCount`
- `removedRedundantCount`
- `reductionRate`
- `sourceDesignItemIds[]`
- `integrity.depthUnchanged`
- `integrity.lineageUnchanged`

## 验收

- 三个 Mechanic 都输出 Before / After 默认视图。
- 默认规则符合 3～6 条核心、0～4 条分支、0～3 参数、0～2 决策点。
- 默认信息量整体至少减少 40%。
- 默认视图不显示 Depth、QA、原始依据、内部 ID、技术依赖或补齐说明。
- Expand Detail 能查看全部被隐藏信息。
- 重复“AI 推荐”标签为 0，颜色状态仍存在。
- 每条默认规则均有来源映射。
- Mechanic Model、Deep Model、Depth 与 lineage 哈希不变。
- P7 与 Final Publication 文件哈希不变。

## 非目标

- 不重新设计 Mechanic 或 Proposal 内容。
- 不新增 Depth Question、Rule、Requirement、状态或 Pipeline Phase。
- 不修改 P7、Final Publication、Planning Hierarchy 或 `job.json`。
- 不以规则数量减少作为独立质量分；减少必须来自 Importance、去重或展示分层。
