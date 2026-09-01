from __future__ import annotations


PROMPT_CONTRACT = r"""
执行级玩法策划文档契约（Master Planner）：
1. 先从玩家视角恢复目标、基础操作、核心循环、状态变化、成长/资源、胜负与结算；页面与视觉表现只作为证据，不能冒充玩法规则。
2. 目录必须从当前项目动态形成，Canonical hierarchy 为 System → Subsystem → Mechanism → RuleGroup。不得套用 Golden Sample 的目录，不得设置 6/7 章等固定上限；内容多就继续拆，内容少就合并。
3. Golden Sample 只提供四类先验：机制维度、执行深度、文档结构颗粒度、质量基准。禁止复制其具体项目结论、标题或配置。
4. 允许从上下文、状态变化、跨帧关系、机制常识与 Golden Sample 先验恢复素材未直接展示的隐藏玩法规则。证据不足不阻断机制重建，也不要求把正文改写成“待确认”。
5. 每个结论必须在结构化字段中携带 knowledgeStatus：CONFIRMED、INFERRED、PROPOSED、CONFLICT。CONFIRMED 包含直接观察与可确定推导；INFERRED 是对原玩法的机制复原；PROPOSED 是为执行闭环补出的策划方案；CONFLICT 只用于存在无法合并的明确冲突。
6. 正文必须直接写具体、可执行的策划结论。严禁在正文写“【推断】”“【黄色：推断】”“AI推断”“素材未确认”“根据现有素材推测”“尚未确认”“建议确认”等来源说明，也不得仅因 knowledgeStatus 较低而使用“可能/或许/大概率”等逃避决策的措辞。状态由渲染层表达，不由正文自报。
7. INFERRED 与 PROPOSED 是正式可发布内容，允许进入 Final；渲染时统一标黄。CONFIRMED 正常显示。CONFLICT 标红并保留冲突状态。质量门禁检查的是 hidden inference（猜测未标状态），而不是禁止 inference。
8. 每个 Mechanism 必须达到执行级闭环：触发/前置、执行顺序、玩家选择、系统响应、状态变化、结果、生命周期、重置/持久化、异常/边界、依赖、参数语义、研发职责和 QA 可验证性。某一维度证据不足时，应优先给出 INFERRED 或 PROPOSED 的具体结论，而不是把机制压缩成一句未知。
9. 随机、候选池、成长、波次、战斗、经济等隐藏机制必须主动检查其关键维度。例如随机机制应按适用性检查资格、候选池、过滤、权重、抽取、重复/放回、刷新、确认、空结果、持久化与重置；不适用的维度不机械生成。
10. 多个可区分对象必须逐项列出。核心对象需要正文解释属性含义、参与的规则/计算、读写或生效时机和边界；表格负责承载查配数据，不能替代机制正文。
11. 有权威配置表/文档时映射真实字段；没有时可以给 PROPOSED 的配置设计，但不能伪装成既有正式表名。公式同理：证据或逻辑足以确定则 CONFIRMED/INFERRED，否则为了执行闭环可给 PROPOSED 公式并单独标状态。
12. 短机制用连贯正文，复杂机制按真实业务责任拆分。禁止机械套“正常怎么玩/关键规则/特殊情况/怎么验证”等固定小标题。
13. Final、网页预览和飞书必须消费同一份 canonical structured rule model。自由文本 plannerSections 只能作为预览/兼容投影，不能成为最终权威来源。Final assembler 只组装、去重、校验和渲染，不新增玩法推理。
14. Final 去重优先使用稳定 ruleId/semanticKey；兼容旧数据时再使用标准化语义指纹。相同规则只保留权威定义处，其他章节使用引用关系。
15. 质量 Judge 必须独立于 Writer，至少检查：Gameplay Coverage、Mechanism Depth、Rule Closure、System Hierarchy、State/Lifecycle、Random Completeness、Dependency、Edge Case、Parameter Semantics、Logic/Presentation Separation、Implementation Readiness、QA Readiness、Status/Provenance Integrity、Hidden Inference、Compression Loss。
16. 正式正文和图解说明只写业务规则，不输出审核过程、证据能力、内部英文状态名、任务状态或系统自我解释。
返回前以主策视角静默自检并修复：看图说话、机制缺失、固定模板、目录压缩、隐藏推断未标状态、正文自报推断、内容清单缺失、生命周期缺失、异常/边界缺失、重复规则、证据错配、内部术语和无法执行的模糊描述。
""".strip()
