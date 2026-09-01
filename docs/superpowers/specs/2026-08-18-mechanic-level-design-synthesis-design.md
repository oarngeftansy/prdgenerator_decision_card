# Mechanic-level Design Synthesis 设计规格

## 1. 目标

把 Requirement/Dimension 级 Atomic Proposal 确定性聚合成七套可整体审核的 Mechanic Design，让主策审核“完整机制方案”，而不是逐条审批工程化 Dimension。

本轮只产生 Review Layer 产物，不生成 Confirmed Rule，不关闭 Requirement，不修改 `job.json`，不写入 Final Publication。

## 2. 固定边界

- GVE16 与 Planner Knowledge 只提供 Execution Prior，不提供《一路狂飙》项目规则答案。
- 不新增 Pipeline Phase、Taxonomy、Closure Status 或固定章节 Schema。
- Atomic Proposal、Requirement 与 Dimension 保留稳定 ID 和 lineage，但默认审核界面不显示工程化 ID。
- Information Gain 不等于 Design Quality；推荐方案必须通过 Coherence、Reuse 与 Compatibility Gate。
- AI Design 只有经主策 Accept/Edit 后才能生成 Approved Rule。

## 3. 聚合范围

当前仅生成七个 Benchmark Mechanic：

1. 武器获取、栏位与攻击
2. 独立武器抽取
3. 三选一
4. 普通怪物移动与攻击
5. Boss 与关卡阶段
6. 伤害统计
7. 胜负与结算

Atomic Proposal 通过显式 `mechanicId`、`originRequirementId`、`executionDimensionId`、Rule/Relation lineage 和配置映射进入 Mechanic，不使用文本、标题、embedding 或 LLM 相似度推断归属。

## 4. MechanicDesignSynthesis 契约

每个 Mechanic 生成一个 `MechanicDesignSynthesis`：

```json
{
  "mechanicDesignId": "MDES-*",
  "mechanicId": "PMECH-*",
  "planningTitle": "普通怪物行为",
  "ownerPath": ["怪物", "普通怪物", "行为逻辑"],
  "confirmedRules": [],
  "recommendedDesign": [],
  "designInferences": [],
  "parameterPlaceholders": [],
  "designDecisions": [],
  "ruleReferences": [],
  "atomicProposalIds": [],
  "requirementIds": [],
  "evidenceRefs": [],
  "coherenceFindings": [],
  "compatibilityFindings": [],
  "unclosedLifecycleSlots": [],
  "reviewEligibility": "ready"
}
```

`reviewEligibility` 只允许 `ready / needs_evidence / needs_design_decision`。它是 Review readiness，不是新的 Requirement Closure Status，也不授予 Publication 资格。

## 5. Primary Owner 与规则复用

一个项目规则只能有一个 Primary Owner。其他 Mechanic 只能通过结构化 `ruleReference` 消费该规则，不得复制完整定义。

当前确定：武器结果处理归“武器获取、栏位与攻击”所有。独立抽取只定义：

`生成并确认抽取结果 → 调用武器结果处理 → 处理完成后返回战斗`

`draw.downstream_effect` 因此不得重复定义“新武器入空栏、重复武器转为强化”。

Rule Reuse Gate 输出：Primary owner、引用方、被复用 Rule/Proposal lineage 和自然语言衔接文本。引用不会创建新 Rule。

## 6. Mechanic-level Design Synthesis

每套审核方案按以下内容组织：

1. 已确认规则
2. AI 推荐完整机制
3. AI 推演部分
4. 待配置参数
5. 真正仍需主策决定的设计点
6. 可展开的 Requirement、Proposal、Evidence 与 Rule lineage

默认视图使用自然策划标题和连续机制语言。Atomic `executionDimensionId` 只在展开 lineage 后显示。

普通怪物的 `movement.state / attack.entry / attack.exit / attack.post_exit_state / attack.death_interrupt` 合并为“怪物 → 普通怪物 → 行为逻辑”，用有序步骤表达完整生命周期，不生成一 Dimension 一标题。

## 7. Cross-Proposal Design Coherence Gate

每个 Mechanic 在进入默认审核队列前检查：

- Entry、Running、Exit、Next State 是否闭合；Reset 仅在当前机制需要时激活。
- Pause/Resume、Start/End、Commit/Return 是否成对。
- 上游输出是否能作为下游输入。
- 同一条件下是否存在互斥状态冲突。
- 激活分支是否具有结果或后续状态。
- 同一项目规则是否被多个 Proposal 重复定义。
- 生命周期是否缺少必要 Entry、Exit 或 Reset。
- 参数是否绑定 Mechanic、Dimension，并在 Consumer Rule 已存在时绑定该 Rule。

Finding 必须指向具体 Atomic Proposal/Requirement lineage。没有 Finding 时不代表项目规则已确认，只代表方案内部可审核。

## 8. Design Compatibility Gate

推荐设计逐项核对：

- Existing Evidence
- Confirmed Fact
- Confirmed Rule
- 当前 UI 与已观察流程
- 上下游 Mechanic
- 当前项目已确认对象

与任何 Confirmed 内容冲突的候选不得成为 Recommended Design。没有直接冲突但超出素材证明范围的内容保留为 Design Inference。冲突项进入 `compatibilityFindings`，不自动修改 Evidence、Fact、Rule 或 Requirement。

## 9. Alternative Design Gate

只有存在真实、会改变玩法或系统行为的设计分叉时才生成 Alternative，例如满栏处理、重复武器处理、结算返回页面、刷新消耗。

普通执行收口不强制生成 Alternative，例如死亡后停止行为、临时流程结束后退出、结算结束后离开结算状态。没有真实分叉时输出单一推荐机制。

## 10. Review Layer

主策默认审核粒度为 Mechanic。每张 Review Card 提供：

- 自然机制标题
- 已确认规则
- AI 推荐完整机制
- 明确标识的 AI 推演部分
- 待配置参数
- 仍需决定的设计点
- 可展开 lineage
- `Accept Mechanic / Edit / Reject / Expand Evidence`

Review Layer 可以显示 Confirmed Rule、Design Inference、Alternative、Placeholder、Requirement、assumptionLevel、Proposal/Requirement ID 和审核操作。

## 11. Review 与 Final Publication 硬隔离

处理链固定为：

```text
Mechanic Design Synthesis
→ Review Preview
→ Accept / Edit
→ Approved Rule
→ Requirement Closure
→ RuleChain Reconstruction
→ Mechanic Assembly
→ Final Publication
```

Final Publication 只消费：

- Confirmed Rule
- 主策 Accept/Edit 后生成的 Approved Rule
- 已批准参数与配置

Final Publication 禁止消费或显示：

- 待确认、待审核
- AI 建议、AI 推演、Design Inference 标签
- Alternative Design
- Placeholder、Requirement
- assumptionLevel、proposalId、requirementId、executionDimensionId
- “可能、建议、推荐方案”等审核语言

如果 Approved Rule 足以形成可执行机制，只发布已批准部分。如果未审核 Core Requirement 导致 Mechanic 无法成立，内部标记 `Publication Blocked` 并阻止该 Mechanic 发布；该标记与原因不得写入正式正文。

Accept/Edit 生成的 Approved Rule 使用去审核化策划语言，同时通过 metadata 保留 Proposal、Requirement、Evidence lineage。

## 12. Planning Title 与 Chapter Assembly

- `executionDimensionId` 永远不作为正式标题。
- 正文标题只使用显式自然语言 `planningTitle`。
- 同一 Mechanic lifecycle 的多个 Dimension 优先合并为一个机制章节。
- Proposal 类型、assumptionLevel、proposalId 等字段不参与 Final Markdown 渲染。
- `attack.entry / attack.exit / statistics.end` 等工程化 ID 作为标题时 Publication Gate 必须失败。

## 13. 本轮产物

- `mechanic-design-syntheses.json`
- `mechanic-design-review-queue.json`
- `mechanic-level-ai-design-review-preview.md`
- `mechanic-design-synthesis-audit.md`

审核稿必须给出：

- 七套完整 Mechanic AI 方案
- 每套使用的 Atomic Proposal lineage
- 重复 Proposal 合并数量
- Cross-Proposal Conflict 数量
- Rule Reuse 数量
- 未闭合 Lifecycle 数量
- 每套 Confirmed / Inference / Placeholder 占比

## 14. TDD 公共 Seam

### 14.1 `synthesize_mechanic_design(...)`

验证确定性聚合、Primary Owner、Rule Reference、生命周期闭合、冲突、兼容性与参数 Consumer。

### 14.2 `build_mechanic_review_view(...)`

验证默认视图使用自然标题且不泄漏工程化 ID；展开视图具有完整 lineage；审核字段只存在于 Review Layer。

### 14.3 当前 Benchmark 生成器

验证：

- 恰好生成七个 Mechanic。
- 18 条 Atomic Proposal 全部且仅归属一次，跨 Mechanic 复用通过 Reference 表达。
- `draw.downstream_effect` 引用武器结果处理，不复制其规则。
- 普通怪物五个 Dimension 合并为一套生命周期方案。
- Alternative 只出现在真实设计分叉。
- 冲突、无后续分支、参数无 Consumer 会阻止 `ready`。
- Requirement、Confirmed Rule、`job.json` 和 Final Publication 均零修改。

### 14.4 Final Publication 隔离

验证：

- 未批准 Proposal 即使语言完整，也不能进入 Assembly。
- Final Markdown 出现审核状态、审核语言、内部 ID 或 Proposal metadata 时失败。
- Publication Blocked 只存在于内部结果，不出现在正式正文。

## 15. 非目标

- 本轮不执行七个 Mechanic 的 Accept/Edit。
- 不生成 Approved/Confirmed Rule。
- 不关闭 Requirement。
- 不重建 RuleChain。
- 不重新发布正式策划案。
- 不计算新的 GVE16 Alignment Score。
