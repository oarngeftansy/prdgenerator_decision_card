# Planning Hierarchy Normalization 设计规格

## 1. 目标

将 Mechanic Review Unit 与最终策划层级解耦。七个 Review Unit 继续作为主策整体审核单元；Planning Hierarchy 则依据当前项目已确认 Owner 动态生成自然的“系统 → 子系统 → 机制职责”结构。

本轮不新增 Pipeline Phase，不重新设计 Proposal，不修改 Evidence、Fact、Rule、Requirement、`job.json` 或 Final Publication。

## 2. 权威 Owner 边界

Planning Owner 继续以已确认的 Current System Hierarchy Audit 为权威：

- 战斗统计归 `关卡结束 → 战斗统计`。
- 结算归 `关卡结束 → 结算`。
- 胜负判定归 `关卡推进 → 胜负判定`。

用户提供的新目录仅用于确认自然层级表达和禁止复合标题，不覆盖既有 Owner Audit。

## 3. 双结构模型

### 3.1 Review Hierarchy

Review Hierarchy 保留七个 Benchmark Review Unit。Review Unit 可以聚合多个 Dimension，其标题可以概括审核范围，例如“武器获取、栏位与攻击”。该标题只用于 Review Layer，不进入 Planning Hierarchy 或 Final Publication。

### 3.2 Planning Hierarchy

Planning Hierarchy 根据 design item 的显式 Owner 投影生成。一个 Review Unit 可以投影到多个 Planning Nodes；每个 design item 只能拥有一个 Primary Planning Node。

Review Unit 数量不约束 Planning 一级节点、章节或职责节点数量。七个 Review Unit 不是 Final Planning Schema。

## 4. 数据流

```text
Mechanic Review Unit
→ stable design items
→ structured owner assignment
→ Planning Hierarchy Node
→ natural planning title
```

Owner assignment 只能来自现有结构化来源：System/Entity Owner、Subsystem/Mechanic Owner、Rule Primary Owner、Chapter Owner 或已确认的 hierarchy audit。禁止通过文本相似度、标题相似度、embedding 或 LLM 猜测 Owner。

## 5. PlanningNode 契约

```json
{
  "planningNodeId": "PNODE-*",
  "title": "攻击",
  "ownerPath": ["核心战斗", "武器", "攻击"],
  "nodeRole": "mechanic_responsibility",
  "sourceDesignItemIds": [],
  "sourceRuleIds": [],
  "sourceReviewUnitIds": [],
  "ownerEvidenceRefs": []
}
```

`nodeRole` 只描述层级职责，使用 `system / subsystem / mechanic_responsibility`。它不是新 Rule、Requirement、Closure Status 或 Pipeline Taxonomy。

Planning Node ID 由规范化 owner path 确定性生成。相同 owner path 必须复用同一个 Planning Node。

## 6. Owner 归一化优先级

1. 已确认 System / Entity Owner。
2. 已确认 Subsystem / Mechanic Owner。
3. 已存在的自然职责名称。
4. 前三项均不存在时才考虑新建自然标题。

标题必须回答“这一节在定义哪个对象或系统的哪类规则”，不得回答“这一节包含哪些 Dimension”。

无结构化 Owner 的 design item 保持内部未映射，记录原因并阻止 Planning Preview 完整通过，不得从文本猜测标题。

## 7. Composite Title Gate

Planning Title 若由多个平级 Mechanic 名通过以下连接符拼接，默认判定为 Review 聚合标题并拒绝：

- `、`
- `/`
- `与`
- `和`
- `+`
- `&`

典型拒绝项：

- 武器获取、栏位与攻击
- 获取、栏位与攻击
- 胜负与结算
- Boss 与关卡阶段
- A/B/C
- A + B + C

Gate 不机械封禁所有包含连接符的真实业务名称。只有存在结构化 `businessConceptEvidenceRefs[]`，证明该复合名称是当前项目中的独立业务概念时才允许豁免。豁免来源必须保留在 audit metadata 中。

Composite Title Gate 只约束 Planning Hierarchy；Review Hierarchy 可以保留复合标题。

## 8. 当前 Benchmark Planning Hierarchy Preview

当前项目依据既有 Owner Audit 生成：

```text
核心战斗
└─ 武器
   ├─ 获取
   ├─ 武器栏
   └─ 攻击

局内成长
├─ 战斗等级
├─ 三选一
└─ 独立抽取

关卡推进
├─ 怪物行为
│  └─ 普通怪物
│     ├─ 移动
│     ├─ 攻击
│     └─ 死亡处理
├─ 关卡流程
│  ├─ 普通阶段
│  └─ 首领阶段
└─ 胜负判定

关卡结束
├─ 战斗统计
└─ 结算
```

该树是当前 Evidence/Owner 下的 Preview 数据，不进入通用固定 Schema。新项目必须从其自身 Owner 数据生成。

## 9. Design Item 投影

每个 design item 新增：

- `planningNodeId`
- `planningOwnerPath`
- `planningOwnerEvidenceRefs`

Atomic Proposal、Requirement、Dimension 与 Evidence lineage 保持不变。

示例：`MDES-WEAPON` 仍作为一个 Review Unit，但其 design items 分别投影到：

- `核心战斗 → 武器 → 获取`
- `核心战斗 → 武器 → 武器栏`
- `核心战斗 → 武器 → 攻击`

抽取下游的武器结果处理继续通过 Rule Reference 指向武器 Primary Owner，不在独立抽取节点复制规则。

## 10. 产物

本轮扩展现有 Mechanic Design Synthesis 产物：

- `mechanic-design-syntheses.json`
- `review-hierarchy.json`
- `planning-hierarchy.json`
- `review-hierarchy-preview.md`
- `planning-hierarchy-preview.md`
- `planning-hierarchy-normalization-audit.md`

Review preview 展示七个审核聚合单元。Planning preview 只展示自然策划层级，不显示 Review Unit 聚合标题、Proposal/Requirement/Dimension ID 或审核状态。

## 11. Gate 与指标

- Review Unit 数量：7。
- Planning 一级标题数量：动态，不要求为 7。
- Atomic Proposal lineage 保留率：100%。
- Design item Primary Planning Node 唯一率：100%。
- 无 Owner design item：0；否则 Planning Preview gate 失败。
- Composite Planning Title：0。
- Engineering Dimension Title：0。
- Review 聚合标题进入 Planning Hierarchy：0。
- Evidence/Fact/Rule/Requirement/Proposal content mutation：0。
- `job.json` mutation：0。
- Final Publication mutation：0。

## 12. 公共接口与测试 seam

### 12.1 `evaluate_composite_title(...)`

```python
evaluate_composite_title(
    title: str,
    *,
    business_concept_evidence_refs: Iterable[str] = (),
) -> dict
```

返回是否允许作为 Planning Title、命中的连接符、是否使用业务概念豁免及原因。

### 12.2 `normalize_planning_hierarchy(...)`

```python
normalize_planning_hierarchy(
    review_units: Iterable[dict],
    owner_assignments: Iterable[dict],
) -> dict
```

只消费显式 design item ID 与 Owner assignment。输出 Review Hierarchy、Planning Hierarchy、Planning Node assignments、Composite Title findings、unmapped items 和 gate metrics。

### 12.3 Benchmark 生成器

测试当前七个 Review Unit 可投影为动态自然树；`MDES-WEAPON` 投影到多个武器职责节点；复合 Review Title 不进入 Planning Hierarchy；统计、结算和胜负使用既有 Owner Audit。

## 13. 非目标

- 不改变七套 Mechanic Proposal 内容。
- 不改变 design item 的 knowledgeClass、approvalState 或 Requirement lineage。
- 不执行 Accept/Edit。
- 不生成 Approved/Confirmed Rule。
- 不关闭 Requirement。
- 不重建 RuleChain。
- 不修改正式策划案。
- 不把当前 Preview 树固化为跨项目章节 Schema。
