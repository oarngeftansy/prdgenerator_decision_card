# Domain Context

## 2026-08-26 当前工作上下文

- 当前可部署应用候选是 `3c3d954`，主要父提交 `b80870d`。它在通用证据归位基础上补齐交互保存业务校验诊断。GitHub 已推送 tree 等价提交 `429ce69`，SVN 已到 r126；正式 `http://192.168.50.210:8010/` 尚未回读到新 capability 和 served JS 文案。
- 所有已有、新建、失败重试和迁移项目必须使用同一 Gameplay/Interaction/Rule/Final 标准。缺陷必须闭合生成、持久化、迁移、GET、渲染、编辑、导出、重试和批量中断恢复；禁止按项目名或 job ID 写产品逻辑特例。
- Gameplay 详细生成有三个不同门槛：目录结构、可进入策划审核的 grounded draft、最终发布。缺少截图依据的参数或公式转 Planner Decision；草稿可进入 P4，但未解决卡仍封锁 P7/导出。禁止因最终参数不完整把整批草稿反复丢弃。
- 长批量生成按章保存经语法和证据清理的安全检查点；网络/API异常后从未完成章续跑，批次语义失败则清除该批检查点。缓存必须包含 job identity、Approved Model revision 和证据指纹，禁止跨项目数据污染。
- 杂货铺最后观察为 Interaction revision 38、7/7 stage confirmed、Gameplay revision 32、generation completed；这是可变生产状态，新会话必须回读。正式验证覆盖杂货铺、角色创建与多个隔离新任务；历史项目只读。
- 当前全量基线为 Python `1652 passed`、JavaScript `492 passed`，另有证据归位聚焦回归 `137 passed`。测试是防回归证据，不代表正式部署或浏览器 QA 已完成。
- 桌面 `苏丹的游戏` 文件夹有 18 张 JPG 与 1 个 MP4。必须先验证 `3c3d954` 正式落地，再用这些素材跑 P1–P7、所有按钮和最终内容质量，不得在旧版本上验收后宣称通用完成。
- 当前项目不再迭代《一路狂飙》Final Delivery。其旧飞书 revision、候选和审计只作为历史事实或只读回归资料，不是当前待办、交付或待复审事项。
- Planning Sketch 迭代在正式发布稳定后恢复，先只读审计 pipeline、旧产物和兼容/发布路径。Phase 3 暂停。
- 后续提交只精确暂存本轮文件；工作区用户修改与历史生成物不得覆盖或混入，尤其保护 `scripts/publish_current_alignment_to_feishu.py`。四出口状态必须分开核验。

## Phase 5.3 Mechanic Reasoning

- **MechanicModel**：位于 Rule/Gap 与最终组织层之间的只读机制节点地图；描述一个机制需要哪些执行节点，以及各节点当前的证据状态，但不产生 Approved Rule、不关闭 Gap。
- **Mechanic Node**：机制中的单一职责位置，例如触发、目标选择、处理、状态变化、结果或退出边界。节点只允许 `confirmed`、`inferred_structure`、`unresolved`、`not_applicable` 四种状态。
- **Inferred Structure**：仅由 ChapterSchema、MechanicStructureCorpus 或已确认因果邻接证明“该执行位置应存在”；不包含答案，不得进入正文或成为 Rule。
- **Unresolved Node**：实现机制所需、且已有 Reviewed Gap 指向但当前没有 Approved Rule 答案的节点；Gap 必须挂到该节点，不能只作为章末列表存在。
- **MechanicStructureCorpus**：从人工执行策划样本抽取的匿名机制阶段与组织关系；只提供结构节点和顺序，不保存项目答案、数值、字段或原句。
- **Mechanical Information Gain**：一条可信信息对机制模型新增的系统关系、条件、输入、处理、状态变化、结果、边界、参数需求或跨机制依赖数量；纯表现或只有输入动作而无系统后果的信息增益为低。
- **PlanningMechanismModel**：MechanicModel 的主策推理版本，固定沿 `Object → State → Trigger → Condition → Processing → StateTransition → Result → Boundary → Parameter → Dependency → Lifecycle` 建立只读机制骨架，并保留 Fact 与 Evidence 追溯。
- **Derived Structure**：由 ChapterType 模板与已确认机制类型确定性要求的节点；只能说明必须检查该位置，不能说明该位置的业务答案。
- **Hypothesis Node**：模板中仅在特定机制变体下可能适用、但当前证据未证明适用性的候选节点；只能进入审核建议层，不能生成 Rule、关闭 Gap 或进入正文。
- **MechanicNode**：当前项目机制图中的单一语义节点；状态与 Rule、Gap、Evidence 追溯绑定。模板本身不能把节点提升为 `derived_structure`。
- **MechanicEdge**：两个 MechanicNode 之间经当前项目证据或严格结构推导建立的有向关系，只允许 `triggers / requires / transitions_to / branches_to / repeats_to / produces / depends_on / persists_until / resets`。
- **Template / Reasoning Coverage Score**：旧 Planning Reasoning Depth 的降级名称；只说明模板覆盖了问题空间，不代表已重建当前项目的因果网络。
- **Mechanic Reconstruction Depth**：评价当前项目中 confirmed／有理由的 derived 节点、实际有向边、状态转换、分支、边界、生命周期与依赖；无 Approved Rule、无 Edge 的模板模型必须低分。
- **Lifecycle Applicability**：生成 initialize／persist／reset 前必须先证明机制拥有持续状态；不能证明时生命周期为 `not_applicable`，模板槽位不得自动建立生命周期节点。
- **Rule Semantic Decomposition**：把一条 Approved Rule 明确表达的 subject、object、condition、action、state change、result、boundary 与 numeric 拆为可追溯语义分量；一条 Rule 可以同时支持多个节点。
- **Semantic Grounding**：Rule Semantic Decomposition 优先于模板，把每个明确语义分量绑定到 MechanicNode；模板不得把 Rule 已证明的节点降级，也不得凭标题升级节点。
- **Transient State Duration**：某个运行时状态持续到事件发生的局部关系，以 `persists_until` 表示；它不等于跨阶段保存、继承、初始化或重置。
- **Lifecycle Persistence**：跨阶段、跨流程或跨关卡的 initialize／inherit-save／reset 关系；只有 Approved Rule 明确支持时才适用。
- **Graph Grounding Quality**：独立评价 Rule 信息保留、confirmed node 角色、Edge 方向和 relation type、节点升降级依据；没有 Approved Rule 的图为 `not_assessable`，不能获得虚高质量分。
- **Effective Reconstruction Depth**：`Reconstruction Coverage × Graph Grounding Quality`；防止关系数量增加但语义错误的图获得高推理深度。
- **Graph Breakpoint**：由 grounded node／edge 证明机制确实存在，但执行所需的输入、处理、关系、结果、边界或依赖仍未定义的位置；模板槽位和 hypothesis-only 节点不是 breakpoint。
- **ReasoningGap**：绑定一个或多个 Graph Breakpoint、面向策划审核的只读决策问题；必须说明程序影响与 QA 影响，不产生答案、不升级为 Approved Rule，也不自动写回既有 Gap。
- **Gap Disposition**：ReasoningGap 对既有 Gap 的只读审计结论，只允许 reuse、rewrite、new、delete-low-value 或 defer-until-grounded。
- **Gap Quality**：评价 breakpoint grounding、问题具体性、程序价值、QA 价值、语义唯一性与无答案暗示；Gap 数量不增加质量分。
- **Decision Worthiness**：判断一个 grounded Candidate Gap 是否值得成为策划决策问题；结果只允许 keep、suppress 或 defer。
- **Keep**：不同答案会改变玩法结果、程序分支、数值、状态转换、规则边界或 QA 预期，问题可进入后续策划语言层。
- **Suppress**：问题属于常识确定、无有效分支、实现细节、过度防御边界或已被现有规则明确暗示，不进入策划审核。
- **Defer**：问题只有在另一项前置决策成立后才适用；前置项未决前不展示，也不删除。
- **Decision-aware Gap Quality**：在原 Gap Quality 上增加 Decision Relevance、Non-triviality 与 Gameplay Consequence；保留无价值问题必须扣分。
- **Gap Disposition（Planner Routing）**：Candidate Gap 在策划展示前的责任分流，只允许 `real_design_decision / parameter_need / entity_attribute / implementation_default / visual_detail / already_answered_by_evidence / upstream_conflict / defer`；只有第一类进入 Planner Review。
- **Human Planner Salience**：判断资深主策是否会在执行文档中主动明确该事项。程序内部自然实现、无反例的默认行为和纯 QA 防御细节不能仅凭技术影响获得高显著性。
- **Planner Signal-to-Noise Ratio**：Planner Review 中真实设计决策占比；另行报告真实设计决策占全部 Candidate 的比例，避免只靠隐藏所有问题获得表面 100%。
- **PlannerDecision**：主策实际审核单位，由同一 mechanic 下、共同控制一个 design lever、且可由同一策划结论回答的多个 ReasoningGap 聚合而成；一个 Decision 可派生多个 QA Case。
- **Design Lever**：策划结论中会改变玩家策略、随机结果、成长节奏、战斗规则、重要状态、资源消耗或系统生命周期的独立控制点。Graph breakpoint、参数字段和 QA Case 本身不是 design lever。
- **Planner Decision Granularity Gate**：检查 sibling 问题答案覆盖、参数/属性误提升、QA 边界碎分和重复 design lever；同一 lever 不能因多个 breakpoint 拆成多个 PlannerDecision。
- **Game Design Reasoning**：面向玩家玩法与主策执行文档的推理层，覆盖获取、使用、解锁、成长、随机、战斗、奖励、胜负、关卡、资源、状态、限制、生命周期和系统依赖。
- **Implementation Reasoning**：只影响程序内部实现、但不改变玩家实际玩法规则的次级层，例如事件排序、竞态、内部排序、轮询、向量合成、原子提交、缓存/状态清理和技术兜底。
- **GameRuleModel**：按机制聚合已确认游戏规则、缺失游戏规则、参数需求和隐藏 Implementation Detail 的只读模型；只有 `missingGameRules` 有资格进入后续 Planner Review。
- **Game Mechanic Depth**：评价游戏规则覆盖、玩家行为链、成长/资源链、限制、系统关系、胜负/奖励和生命周期；Implementation Detail 数量固定贡献 0。
- **MechanicScope**：Game Rule Template 实例化前的子机制存在性判定，记录 Evidence、Rule、UI 和 relationship 依据；状态只允许 `confirmed / strongly_implied / possible / unsupported / contradicted`。
- **Strongly Implied Scope**：当前项目已证明承载对象或必需玩法关系存在，但具体规则未知的子机制；可产生 missingGameRules，但不能生成答案。
- **Exploration Candidate**：possible、unsupported 或 contradicted 的 scope item；不进入 missingGameRules 或 Planner Review。
- **Gameplay Parameter**：数值、单位或配置虽待 ParameterResolver 结构化，但会直接改变玩家行为或结果的玩法契约，例如攻击间隔、射程、伤害、移动速度、刷新次数和刷新消耗。
- **Scope Precision**：检查 unsupported/template-only 子机制是否被误实例化，以及当前证据支持 scope 的比例；目标是精确展开，不追求模板覆盖率。
- **ExternalGameDesignCorpus**：从外部游戏设计 Skill 蒸馏的只读探索语料，只保存 mechanic scope、game rule、dependency、progression、randomization、economy、balance 和 gameplay parameter 抽象 pattern；`contentAuthority=none`。外部来源仅能产生 possible dimension，不能直接创建 missingGameRules。
- **External Pattern Candidate**：外部 Corpus 产生的 possible scope 或 possible rule dimension。它不能自行升级状态，必须由当前项目 Evidence／Fact／Rule／UI／relationship 通过 MechanicScope Gate 后才能进入 missingGameRules。
- **GameRuleGroup**：系统策划组织玩法规则的最小主题单元；聚合同一玩家可理解玩法决策下的 Known Rule、Missing Game Rule、Gameplay Parameter、关联系统和生命周期信息。底层 Node、Edge、Gap 和单个参数都不能直接决定规则组标题。
- **Rule Group Granularity Gate**：检查一 Gap 一标题、同义 sibling、参数误升章、Implementation Detail 污染、非玩法主题标题和未通过 MechanicScope 的模板规则组；目标是形成稳定规则组，而不是增加标题数量。
- **GameplayRuleChain**：把一个核心玩法或跨系统循环中的进入、玩家行为、系统响应、状态变化、成长结果和退出/下一步按因果顺序连接起来的只读模型；Rule 可以同时支撑入口与响应，但每个链步骤都必须保留 Rule 追溯。
- **Missing Link**：已确认链步骤之间仍缺失的玩家可理解玩法连接；只能定位断点和提出未知事项，不能用 possible/unsupported scope 填入主链或生成答案。
- **Chain Coherence Gate**：检查规则链是否只有分类而无顺序、Known Rule 是否进入链、跨章节玩法是否形成跨系统链、Missing Link 是否可由策划理解，以及 Implementation Detail 是否污染主链。
- **RuleProjection**：把 GameplayRuleChain 中的 Rule 投影到唯一 Primary Owner，并记录其他 Reference Owner、规则角色和定义方式；同一 Rule 只能有一个 `full_definition`，其他系统与 Core Loop 只能短引用。
- **Core Gameplay Loop**：只说明战斗、成长、选择、强化、胜负与结算如何循环的整体玩法概览；不承载完整执行规则定义。
- **Projected System Chapter**：承载其 Primary Owner 下的完整规则、短引用、Missing Link 与 Parameter Carrier，并保留来源 Chain；它按系统职责组织，而不是复制整条跨系统 Loop。
- **RuleLayoutPlan**：在 Projected System Chapter 内，依据当前 Rule 关系与同类机制的匿名 GVE16 顺序，为一个 GameRuleGroup 决定直接 bullet 或动态子栏目；不存在统一 trigger/condition/result 字段模板。
- **Native Subsection**：由当前内容实际支撑的玩法语义栏目，例如自动攻击、攻击方式、候选生成或刷新；没有 Rule、引用、Missing Link 或 Parameter Carrier 时不得实例化。
- **Layout Quality Gate**：检查统一 Schema 痕迹、空标题、内部 semantic 标题、过度分层、一 Rule 一小标题及违反同类机制自然顺序；GVE16 只提供匿名布局证据，不提供项目内容。
- **Rule Expansion Depth**：评价已确认机制的游戏规则是否达到执行策划所需颗粒度；参数值未知不直接降低该状态，`under-expanded` 只表示仍缺必要游戏规则。
- **Parameter Completeness**：独立记录已确认玩法参数的值、单位、公式或配置来源是否完整；不得反向改变 Rule Expansion Depth。
- **Parameter Placement Plan**：把 observed value、unresolved gameplay parameter 或 confirmed config reference 放回所属 RuleLayout 的自然位置；内部 semantic 只用于追溯，不作为策划可读标签。
- **Scope Correction**：在不改写历史 Scope 产物的前提下记录证据复核导致的状态降级；结算展示不能单独证明 recorded data 跨局持久化。
- **CrossSystemReferencePlan**：把 GameplayRuleChain 中已确认的跨系统衔接投影为自然短引用；目标 Rule 仍只在 Primary Owner 完整定义，引用章不得复制其参数、分支或具体效果清单。
- **Reference Depth**：跨系统关系的阅读层承载强度，只允许 `inline_reference / short_rule_reference / no_reference_needed`；无 Scope 支持的关系固定为 no reference，JSON 保留审计但正文不渲染。
- **Contextual Restatement**：在非 Primary Owner 章节用一条短句复述理解当前流程所必需的核心规则；允许与主定义共享 Rule provenance，但不得复制目标章节的完整规则块、参数表或分支展开。
- **Human Planning Preview**：只呈现拟进入策划文档的自然章节与规则句，不显示 Full Definition、Reference、Suppression、Owner 或内部 ID；相关审计信息单独保存在 JSON／audit markdown。
- **ReviewDecision**：把已确认需要人工补充的 Missing Execution Detail 或 Gameplay Parameter 映射为审核控件的中间模型；Rule 形式由 P4 决定，参数值由 P6 填写，AI 候选和推荐均不能自动批准。
- **Dependent Review Decision**：只有前置 P4 选择成立时才激活的后续 P6 参数，例如选择持续接触伤害后才显示伤害间隔；未激活项不进入正文，也不关闭 Gap。
- **Evidence Recheck Route**：素材可能已经展示答案时，优先回到 Evidence → Fact → Rule，不让策划重复选择可观察事实。
- **Natural Default Route**：没有玩家可感知设计分支的自然玩法闭环只用于抑制低价值问题；它不生成 Approved Rule。
- **Review Control Quality Gate**：强制检查常识问题、实现问题、可观察事实重问、规则/参数错路由、无依据选项、内部语义泄漏及 AI 自动批准，任一非零则 Phase 6.1.5 失败。
- **Content Richness Audit**：按章节核对已确认 Rule、已支持 Scope 缺口、P4/P6 ReviewDecision、已观察值与跨系统关系是否都进入阅读层；`possible / unsupported` 只能计入 Correctly Rejected，不能增加正文。
- **Supported-but-not-rendered Dimension**：已经由 confirmed／strongly implied Scope 或 Approved Rule 证明需要、但没有出现在正文或可操作 Pending 项中的玩法维度；它表示 Too Thin，不授权系统推理答案。
- **Effective Rule Density**：以有效玩法规则、具体数值、约束、跨系统关系和可操作未决规则计量信息密度，并独立报告 filler 与 implementation noise；不以字数、句数或篇幅作为丰富度目标。
- **Review-State Rendering**：Approved 写具体规则；P4 Pending 写简短规则项“待确认”；P6 Pending 写自然参数项“待确认”；Evidence Recheck 保持 `pending_evidence` 且不进正文；Suppress 不进正文。依赖型 P6 仅在前置 P4 选项批准后激活。

## Phase 5 Entity Graph

- **Entity**：逻辑或数据层中具有稳定身份、可被规则持续引用的业务节点。目录标题、视觉样式和界面布局不因出现于文档而自动成为 Entity。
- **EntityType**：Entity 的领域类别，只允许 `runtime_object`、`container`、`content_item`、`candidate_set`、`runtime_context`、`process`、`report`。
- **Owner**：对 Entity 的生命周期或主要定义负责的另一 Entity。章节旧 scope 不能自动成为 owner。
- **Parent / Child**：逻辑或数据层中的组成、收纳或稳定从属关系；必须有非表现证据或已确认的领域声明支撑。
- **Source / Target**：已批准规则所证明的有向作用关系。Gap、目录标题和 Presentation Rule 均不能单独建立该关系。
- **Primary Definition Chapter**：集中定义 Entity 业务规则的唯一主要章节。
- **Reference Chapter**：引用同一 Entity、但不重复建立主要定义的章节。
- **Presentation Reference**：Presentation Rule 通过 `relatedEntityIds` 单向引用既有 Entity。该引用不能创建 Entity，也不能反向定义 owner、parent/child 或 source/target。
- **Presentation Pollution**：由纯表现内容创建核心 Entity、推导核心关系，或把 Presentation Rule 作为核心关系证据的情况；Phase 5 要求数量为 0。

## Cross-Project Mechanic Intelligence

- **Mechanic Pattern**：可由当前项目 Evidence 激活的通用机制结构；它声明可能需要检查的执行职责，不保存任何项目答案。
- **Existence Signal**：来自 UI、文案、操作、状态、时间、数值、实体、奖励、转场、重复或空间行为，能支持 Pattern 或 Responsibility 存在的可追溯信号。
- **Responsibility Profile**：Mechanic Pattern 指向的候选执行问题集；其中每个 Responsibility 只在自身激活条件被当前 Evidence、Rule 或跨系统关系满足时生效。
- **Pattern Composition**：多个 Mechanic Pattern 通过共享 Entity、Resource、State、Event 或 Flow 在当前项目中组成真实系统结构；不存在“一个 Feature 只属于一个系统”的排他分类。
- **Project Mechanic Graph**：由已检出 Pattern、当前项目的 Entity/Resource/State/Event/Flow 与有证据的边组成的项目图；Pattern Library 只作为候选图模板。
