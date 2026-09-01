# Planning Language Compression & Planner Readability

## 目标

在不修改 Mechanic Model、Depth Dimension、业务规则含义或任何 Evidence / Fact / Rule / Requirement / Proposal lineage 的前提下，为 Full Mechanic Reconstruction 建立主策可快速扫读的 Review 表达。

本层是 Review Layer 的只读投影，不产生 Approved Rule，也不修改 Final Publication 或 `job.json`。

## 权威数据与投影边界

- 原始 `designItems` 继续作为业务语义与 lineage 的权威来源。
- 新增 `plannerReadableSections`，仅负责分组、拆句、策划语言转译与默认信息层级。
- 每条压缩后的规则保留稳定显示项 ID，并引用一个或多个原始 `designItemId`；不得新增原始规则没有的条件、状态、分支、数值或结果。
- Depth Coverage、Core Design Depth、Evidence/Fact/Rule/Requirement/Proposal lineage 均从原始结构计算，不读取压缩文本。

## 默认信息层级

每个 Mechanic 按以下顺序展示：

1. 核心规则
2. 分支与特殊处理
3. 参数
4. 与其他系统的关系

Evidence、Inference 依据、lineage、QA 与内部状态放入折叠详情。知识类型通过统一侧标或颜色表达，不在每条正文中重复“AI 推荐”。

## 策划语言压缩

- 每条 bullet 只表达一个可独立执行或验收的策划结论。
- 默认目标长度为 35～45 个中文字符；超过阈值时优先按独立条件、状态变化或结果拆分。
- 一条规则含两个以上连接动作，或两个以上独立状态变化时必须检查并拆分。
- 不因保持 lineage 而把多个 Dimension 拼成一句；拆分后的多条 bullet 可以共同引用同一原始 `designItemId`。
- 禁止用抽象正确句替代真实信息，拆分后必须完整保留原始规则的条件、对象、动作、分支与结果。

## 技术语言转译

主策默认层不显示 `Primary Owner`、instance、commit、submit、回写成功、listener/event、target reference、confirmation lock、temporary result object、consumer rule id 等实现术语。

默认转译为玩家与玩法对象可理解的规则，例如：

- “效果作用于对应武器”
- “选择完成后立即生效”
- “怪物死亡后停止攻击”
- “替换武器后原武器停止生效”

技术原文及完整 lineage 仅在折叠详情中保留。

## Logic / Presentation 分流

- 默认 Review 正文只保留玩法逻辑、状态、条件、结果和必要的交互闭环。
- 动效、镜头、特效、界面布局、演出与纯视觉反馈继续进入策划草图 / Visual & Interaction Board。
- Logic 通过结构化 `relatedVisualBlockIds` 引用表现内容，不在玩法规则中复制表现描述。
- “关闭选择界面并恢复战斗”等影响玩法状态的交互结果仍属于 Logic；界面如何关闭、动画如何播放属于策划草图。

## Planner Readability Gate

对默认主策视图检查：

- 技术术语命中数为 0；
- 超长 bullet 显著减少，并报告剩余例外；
- 单条 bullet 不混合多个独立状态变化；
- 不重复显示知识类型标签；
- 内容按核心、分支、参数、跨系统关系组织；
- Presentation 不进入 Logic 正文。

## TDD 验收

公开验证边界为生成后的 Review JSON、Review Markdown 与 `/mechanic-review` 页面。

1. 三个 Mechanic 均生成压缩前/后对照。
2. 压缩稿中禁用技术语言命中数为 0。
3. 默认 bullet 的长度与复合职责统计显著下降。
4. 每条显示项均能追溯到原始 design item。
5. 压缩前后 Depth Coverage 完全一致。
6. Evidence/Fact/Rule/Requirement/Proposal lineage 的结构化值完全一致。
7. 业务语义守恒检查覆盖原始 design item 的条件、动作、状态变化和结果。
8. 网页默认显示压缩稿；原文、证据、推演、QA 与 lineage 可折叠查看。
9. 表现内容仍由策划草图承载，Logic 默认层不重新混入 Presentation。

## 非目标

- 不修改 Mechanic Model 或已有 Proposal 内容。
- 不新增 Depth Question、Rule、Requirement 或审核状态。
- 不改变 Planning Hierarchy、Final Publication 或 `job.json`。
- 不通过删除业务信息换取短句，也不以 bullet 数量作为质量分数。
