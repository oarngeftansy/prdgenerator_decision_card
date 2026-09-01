# Memory：用户确认的产品约定

## 2026-08-26 当前项目不再迭代《一路狂飙》

- 当前项目主线是 Planner Intelligence 网页工具的通用产品稳定化、跨项目工作流与新项目高质量生成，不再继续迭代《一路狂飙》Final Delivery。
- 《一路狂飙》只保留为历史数据和只读回归样本；不得把它写进当前项目名称、当前目标、下一步主线或待复审交付，也不得继续修改其 Approved Rule / Flow / State / Final Execution Plan。
- 正式验收重点是通用能力与隔离新任务；“苏丹的游戏”是下一轮真实新项目验收素材，不得把验收重新转回《一路狂飙》内容迭代。

## 2026-08-26 跨会话交接与正式验收硬边界

- 当前可部署应用候选固定为 `3c3d954a677eacdd7f720bb1e990d8af14d131c4`；GitHub 使用等价历史提交 `429ce69fd353f21ca2d6fef0e7fef1ba56090c47`，两者树内容相同。交接文档提交可以晚于应用候选，但不能误写成新的应用部署版本。
- `3c3d954` 已把交互审核的业务校验错误与服务故障分开：缺少已观察操作、其他 400 校验、409 revision 冲突和真正网络/服务失败必须展示不同、可执行的提示。任何 400 业务错误不得再统一显示“请检查服务状态”。
- `b80870d` 及其后续应用候选已统一执行证据归位：无依据的机制、参数、公式、配置和验收套话不得冒充 Gameplay Rule；静态展示和当前数值不能进入 Gameplay Flow；证据不足必须转策划决策卡。
- 正式发布必须同时回读后端 capability 与已服务的前端字符串/资源。Brand Update 被运行、服务重启、revision 变化或接口 200，都不能单独证明代码已经落地。
- 正式 8010 尚未验证部署 `3c3d954`。在 capability `evidence-grounded-gameplay-review-v1` 和前端保存提示均回读成功前，不运行“苏丹的游戏”最终验收，也不能宣称正式可发布。
- “苏丹的游戏”验收素材位于桌面文件夹，当前为 18 张 JPG 与 1 个 MP4。部署确认后必须在正式地址跑 P1–P7、所有按钮、刷新/返回、编辑保存、失败重试、图片、决策卡、最终导出与内容质量；结论必须推广为通用标准，不能写项目特例。
- 《一路狂飙》不再是当前迭代对象，只保留为只读历史回归样本；Planning Sketch 仍暂停在只读 pipeline/旧产物审计之前；Phase 3 不启动。

## 2026-08-25 全项目高标准与最终提交门禁

- 所有已有项目、新建项目、失败后重试项目和迁移项目必须消费同一套 Gameplay Model、Interaction Review、Rule Review、Final Export 标准；任何为单个任务、job ID 或《一路狂飙》写出的局部修复都不算完成。
- 用户指出的问题必须闭合“生成 → 持久化 → 迁移 → 读取 → 渲染 → 编辑 → 导出 → 重试”全链，并增加跨项目负例、隔离新任务、旧数据迁移和正式地址浏览器回归。不能只改当前页面或只补一个前端判断。
- 所有反馈项全部修复、自检、截图验证之前，不得把中间安全提交描述成“最终完成”。测试数量高不等于架构干净，也不等于正式环境已经更新。
- 最终提交与发布声明必须分别核对本地 Git、GitHub、SVN 和正式 8010。应用候选代码、交接文档提交和正式部署版本必须明确区分；正式地址未回读新资源并通过桌面端跨项目 QA 时，状态只能是“待部署/待验收”。
- 当前下一步不是 Phase 3，也不是继续修改《一路狂飙》已批准执行案；先完成 `9af07bc` 的 Brand Update 与正式地址验收，再进行共享状态机、模型投影和 P1–P7 门禁的稳定化/路径收敛。

## 2026-08-24 网页工具通用修复与发布硬门禁

- 所有网页修复必须作用于共享模型、通用路由、公共组件或统一持久化层，并同时覆盖已有任务、失败任务、复制/迁移任务和新建任务；禁止只为《一路狂飙》、某个 job ID、某类截图或当前页面写特例。
- 修复完成的最低证据固定为：先定义可复现测试用例，增加自动回归，再在真实浏览器逐项点击，检查目标面板、URL、持久化、刷新/返回恢复、控制台、失败请求和截图。按钮存在、接口 200、单元测试通过或本地页面正常，任何单项都不能单独证明可发布。
- 发布必须核对四个出口：本地 Git、GitHub 同名分支、SVN `AI/trunk/ai_gamedesigntool`、正式部署地址。四端版本标识与发布清单一致且正式地址完成浏览器验收后，才能声称“已同步/已上线/可发布”；部署包已生成或服务已启动不等于正式地址已更新。
- 正式发布前同时回归两个现有项目和至少一个隔离的新建 QA 项目；QA 项目不得修改《一路狂飙》或其他正式任务。修复若只在已有完整数据上通过、却没有覆盖缺模型、失败重试、旧数据迁移和空状态，判定未完成。
- 当前产品验收范围是电脑端。桌面端需覆盖 1366、1440、1920 等常见宽度；参考截图保持原始宽高比，竖图按竖版展示并使用完整包含策略，不裁成正方形、不拉伸。移动端不作为本轮发布门禁。
- 任何保存失败、图片加载失败、按钮无响应或跳转失败都必须查到具体接口、数据状态或异步竞态根因；内容先保留、错误可恢复，禁止用笼统提示掩盖失败，也禁止在无法复现或尚未验证正式地址时向用户保证已修好。

## 2026-08-24 Planning Sketch 确定性生成迭代恢复

- 恢复此前暂停的 Planning Sketch / 策划草图迭代。本阶段只验证如何从当前 Approved Rule、Flow、State 与 Final Execution Plan 确定性生成策划草图，不修改已批准玩法规则，也不继续改写《一路狂飙》Final 执行案。
- 第一动作固定为审计现有 Planning Sketch pipeline、兼容路径、发布路径、测试与旧产物，先给出当前能力、缺口和分阶段迭代方案；未经审计结论与用户确认，不直接进行大规模重构。
- 策划草图必须是权威结构化输入的只读 Projection：不得反向写回 Approved Rule，不得从截图、旧 board spec 或表现文本推导新的玩法答案；无法由权威输入确定的内容必须显式缺失、降级或进入审核路由。
- 迭代目标是同一 Approved Rule / Flow / State / Final Execution Plan 输入得到稳定、可追溯、可复现的 Page/State/Edge/Annotation/Layout 产物，并能证明网页预览与飞书原生画板消费同一 canonical sketch model。

## 2026-08-24 当前交付与跨会话约定

- 当前唯一工作分支是 `codex/planner-decision-card`。新会话必须先读取 `AGENTS.md`、三份 memory、`docs/handoff/CURRENT_SESSION_HANDOFF.md`、`CONTEXT.md` 与 `handoff_state.json`，再依据真实 `git status` 和 HEAD 工作；不得继续使用 2026-07-22 或 2026-08-03 的旧任务状态。
- 《一路狂飙》当前飞书交付文档为 `https://hjjxo8h8vu.feishu.cn/docx/IjKndZqszoj9kgxma0icsDOjnfe`。正文必须保持“玩法概述 → 单局流程 → 核心战斗 → 局内成长 → 关卡推进”的阅读入口顺序。
- 飞书图表必须按正文语义插入对应机制章节，不建立独立图表区或文末附录。当前只保留玩法执行所需的原生表格与玩法流程图；UE、竞品、Presentation-only 画板不得进入 Final。
- “恢复完整度”不等于恢复旧问题：允许从具有确认权威的历史执行内容恢复缺失机制，但必须继续通过 Evidence Guard、Canonical Owner、Entity Scope、Dependency Closure 与 Final Pollution Gate；不得恢复公式、等概率、无放回、权重、保底、隐藏优先级、单局奖励泛化或模板/技术问题。
- Final 不应是稀疏 Rule 列表，也不能是 Schema 问卷。它应重建完整 Mechanic Flow，优先表达已知机制，只保留确实影响玩家体验且所有 Approved 信息与安全推定均无法回答的 Planning Decision。
- 通过 Planner Feedback 验证的经验必须进入持久化 System Lesson，并被声明式 Policy/Guard/Schema/Classification、运行时和跨项目测试实际消费；仅保存 feedbackId、Markdown 或 lineage 不算系统已经学习。
- 后续代码变更按本地 Git commit、GitHub 同名分支、SVN `AI/trunk/ai_gamedesigntool` 三重同步。同步不得包含凭证、缓存、临时测试目录或用户未提交文件。
- 工作区长期存在大量历史修改和生成物。禁止 `git add -A`、`git reset --hard`、`git checkout --` 或无差别清理；尤其不得覆盖或顺带提交用户修改的 `scripts/publish_current_alignment_to_feishu.py`。

## 2026-08-21 Final Mechanic Reconstruction Closure

- Final 在渲染前必须按同一实体、相关 Rule Intent、生命周期、跨章节规则、Planner Feedback 与安全 Planner Inference 重建 Mechanic Flow；不得把 Approved Rule 平铺成碎片列表。
- Schema Question 只用于内部分析。Final 只允许已确认规则、安全推断、明确 Planner Proposal 和具体 Planning Gap；Technical Gap、模板问句和无执行信息的宽泛表达不得进入正文。
- Schema Applicability 必须由当前 Evidence/Mechanic Variant 决定。接触伤害链可以是 Spawn → Movement → Collision/Damage，不强制生成 TargetSelection、AttackState 或 AttackExit 问卷。
- Final 生成 Gap 前先执行 Cross-section Rule Recovery 与 Canonical Owner 恢复；同一完整定义只保留一个 Owner，原来源章节仅作 reference。
- CandidateGeneration 必须显式列出当前已观察到的 CandidateType，再判断类型间是否共享 Eligibility/Sampling；不得用“候选项/内容池”替代类型解析。
- Entity Scope 不匹配的 Rule 必须 reassign、reference 或 block；Presentation Rule 与 blocked Rule 不得通过旧 Assembler fallback 回流 Final。
- Required Slot 缺失时必须先执行 Global Approved Information Recovery：Approved Rule/Fact、confirmed overview/basic flow/chapter narrative、planner-confirmed feedback 都是候选来源；未审核 narrative 永远不能关闭 Closure。
- Final Delivery Candidate 发布前必须完成 Recovered Rule Dependency Closure；被恢复规则引用的 Entity/Mechanic 必须得到定义或登记为具体 Planning Gap，且 undefined referenced entities、unresolved mechanic references、orphan rules 均为 0。

## 2026-08-21 Phase 2 Temporal Probe 生产编排

- 新建生产任务默认启用 `contentModelVersion=2`；历史任务不因打开或重建而升级，历史 `plannerSections` 不得因 Temporal Probe 变为 confirmed 内容。
- Temporal Probe 自动编排位于 `_generate_gameplay_review` 的 v2 projection 初次构建后、最终保存前；规则投影内不执行视频 I/O。
- Gap 可以用 `probeEligible / probeType / targetProperty / anchor / searchWindow / evidenceQuestion / sourceEvidenceRevision` 显式声明可探测合同；服务不根据玩法关键词新增分支。
- 一次自动编排最多形成 `Projection V1 → Probe → Projection V2`；多个 Probe 结果也只许触发一次额外 projection rebuild。

## 2026-08-21 Phase 2 Temporal Gameplay Evidence

- 辅助视频只通过 Gap 驱动的 `TargetedTemporalProbe` 产生 Temporal Observation / Temporal AtomicFact；不得自由扫描并总结玩法，也不得建立第二套 Rule 主链。
- Temporal AtomicFact 默认 `unreviewed`，可以产生 RuleCandidate、审核 Evidence、Temporal Coverage 和 Gap，但不得创建 Approved Rule、关闭 required Closure、标记 Gap resolved、进入 Publication 或改变 Final。
- Entity identity 权限分级：confirmed 才能绑定 `entityId`；probable 只能保留 `candidateEntityId` 且固定 review_required；ambiguous/lost 只产生 `identity_unresolved` Gap。
- First Appearance 与 Spawn 严格分离；Repeated Event 只记录 ObservedIntervals，不得升级为配置间隔、公式或周期规则。
- reference frame 状态只作为 Movement Candidate Guard；背景滚动不得反推对象存在 gameplay movement。
- Probe 按 Evidence revision 记录生命周期、搜索窗口和 exhaustion；同一 Evidence 下 exhausted Probe 不得重复触发，not_observed 只表示当前视频未观察到。
- Temporal Evidence 的策划确认复用现有 `review_rule`、revision 和 undo/redo；只有 Planner approval 后才进入既有 Publication/Final 权威链。

## 2026-08-21 Planning-only 画板输出

- 当前暂时停用 UE 流转图的独立审核与输出逻辑；最后一个交互页面确认后直接进入策划草图预览，不再经过 UE Flow Gate。
- 当前所有画板载体只输出“策划草图”。UE 流转图、竞品参考和旧 UX 画板不进入网页预览、完成度门禁、Final 或飞书发布，也不得因历史状态阻塞导出。
- 底层历史 UE/竞品数据与兼容 API 暂不破坏性删除，等待用户后续提供新的策划草图画板逻辑后再继续调整唯一 planning 载体。

## 2026-08-20 Cross-Project Mechanic Intelligence 架构边界

- 当前主任务采用“声明式 JSON 知识图谱 + 通用图引擎”；Mechanic Library 是可组合的策划知识图谱，不得退化为“大词典 + if/else 分类器”。
- L1 Game Domain、L2 System Family、L3 Mechanic Pattern、L4 Execution Responsibility 是统一分层；Pattern 只声明可能存在的执行职责，`contentAuthority=none`，不得保存任何项目答案。
- Mechanic 必须由当前项目 Evidence / Existence Signal 激活，品类标签不能证明机制存在；同一 Scene / Flow / Feature 可以同时激活多个 Pattern，不允许排他式“一个项目只匹配一个系统”。
- Responsibility 必须按 Evidence、Pattern、Existence Signal、Current Rule 和 Cross-system Relation 动态激活；没有自身存在信号的可选职责保持 dormant，不能膨胀成 Missing Requirement。
- 当前项目结构由多个 Pattern 通过共享 Entity / Resource / State / Event / Flow 组合；Evidence、Fact、Approved Rule 继续是项目事实和答案的权威来源。
- 扩展新类型时只新增声明式图数据和迁移 Benchmark；禁止在 Python 引擎中增加玩法/品类特定分支，禁止把《一路狂飙》答案硬编码给其他项目。
- 下一阶段必须同时覆盖系统型、玩法型和混合型案例，迁移测试不少于 25 个；重点验证 Mechanic/Responsibility Recall 与 Precision、Gap 价值、噪声抑制、自然层级、生命周期、分支、算法、参数和跨系统关系。

## 2026-08-20 GVE16 正文逐行验收与发布防错

- 正文验收必须先抽取 GVE16 第一手真实目录，再逐标题、逐段、逐表行和逐图落位对照最终成品；项目内部断言、关键词命中、Closure 状态或测试通过不能替代对照。
- 目录标题应围绕单一编辑职责；不得用大量“X与X / X、Y与Z”复合标题压缩不同 Owner、机制、状态或载体。自然术语可以保留连接词，但不能借连接词掩盖职责混合。
- 当前《一路狂飙》详细正文 Owner 顺序为载具、武器、怪物、战斗规则、关卡规则；怪物包含普通怪物和首领，伤害公式归战斗计算，战斗统计归关卡内部逻辑。玩法概述和单局流程是阅读入口，不抢详细规则 Primary Owner。
- 网页和飞书必须消费同一 canonical body；飞书原生自动编号直接承载实际章节。UE流转图、策划草图、竞品参考保持三个独立画板，并在远端 preview + raw 双验收后才可交付。

## 2026-08-20 Final 正文开头、编号与配图同源

- 《一路狂飙》最终正文必须先给出简洁“玩法概述”，明确玩家目标、核心循环、局内成长和胜负结算，再进入载具、武器、怪物、战斗规则、关卡规则等详细章节。
- 飞书自动编号必须作用于实际正文大章，禁止在开头额外生成“自动编号目录”或用手写数字冒充原生编号。
- 网页与飞书必须消费同一份 canonical body 及相同的 BOARD/P5/P6 嵌入锚点；图示放在对应说明或规则之后，独立审核页签不能替代正文配图。
- 正文目录先以“单局体验流程”给出进入挑战、普通战斗、关卡内成长、首领来袭、首领战斗、残敌清理和结算的线性主线，再按载具、武器、怪物、成长、统计、胜负结算展开细节。
- “怪物”必须同时承载普通怪物与首领；首领的进入、页面信息、终止和残敌清理不能只散落在关卡转场句中。

## 2026-08-19 Planner Review Density Reduction

- `/mechanic-review` 是独立 Mechanic Review Layer，不是 P7；P7 与 Final Publication 只消费 Approved Data，本审核台的 AI 状态与设计分叉不得进入 P7。
- Mechanic Review 默认层只显示核心规则、分支/特殊规则、参数与真实设计分叉；Depth、Remediation、QA、原始依据、lineage、Requirement/Proposal/Dimension、技术依赖和补齐说明统一进入 Expand Detail。
- 默认规则必须通过 Rule Importance Gate：改变玩家选择/结果、状态机、数值/资源/随机、核心分支、跨系统业务关系，或不定义会产生两种合理且不同的玩法实现。否则降为 supporting detail。
- 每个 Mechanic 默认控制在 3～6 条核心、0～4 条分支、0～3 参数、0～2 决策点；正确废话、被具体分支覆盖的概述和同义后果不进入默认层，但完整数据与来源映射保留。
- 已确认与 AI 补全只用颜色圆点区分，不逐条显示文字标签；密度压缩只作用于只读 Review Projection，不改变 Mechanic Model、Depth 或 lineage。
- Rule Importance Gate 必须拒绝循环定义与“正确但无决策”的表达，例如“伤害属于产生伤害的对象”“流程完成后退出”“死亡后停止普通行为”；若底层意图是统计或归因，应改写成真实业务口径（如按武器分别累计），否则降入 Expand Detail。

## 2026-08-19 Planning Language Compression

- Full Mechanic Review 使用只读 `plannerReadableSections` 投影压缩主策默认阅读层；Mechanic Model、原始 design item、Depth 与 Evidence/Fact/Rule/Requirement/Proposal lineage 均保持权威且不得被展示文本回写。
- 默认信息顺序为核心规则、分支与特殊处理、参数、跨系统关系；原始规则、Evidence、Inference、QA 与 lineage 默认折叠。AI 补全状态只用统一侧标/颜色，不逐条重复标签。
- 每条可读 bullet 只表达一个策划结论，目标不超过 35～45 个中文字符，并保留 `sourceDesignItemIds[]`。程序术语转译为玩法语言；实现细节只留在折叠层。
- 动效、镜头、特效、界面布局和纯视觉反馈继续进入策划草图 / Visual & Interaction Board；Logic 仅保留影响玩法状态的交互结果，并通过结构化引用关联表现内容。

## 2026-08-19 Planner Value Gate

- Full Mechanic Reconstruction 的 High-value Design Question 必须至少改变玩家策略/结果/构筑、核心状态或生命周期、资源/数值/随机/奖励/统计、跨系统数据流/归属，或存在两个以上合理且行为不同的实现结果。
- 临时变量清理、内部 ID/引用、confirmation lock、listener/event、可寻址实例模型、内部计时器清理、QA 步骤及唯一合理的流程保持行为，归入 Supporting Execution Detail 或 Implementation-only，不计 Core Design Depth。
- Core Design Depth 以独立 Design Lever 为计分单位；同一玩法决策下的同义/原子 Dimension 合并保留 lineage，不得拆分分母刷深度。Review 层可保留技术与 QA 细节，但 Final GVE16 Alignment 不由这些细节抬分。

## 2026-08-19 Full Mechanic Reconstruction

- Depth Remediation 的修复单位是完整 Mechanic Model，不是单个 Depth Dimension；优先重建成组状态、算法、数据流、分支、生命周期和跨系统关系，禁止按易补 Gap 做百分点微调。
- Remediation 阶段以完整 Mechanic Model、Projected Design Coverage 与独立 Core Design Depth Coverage 验收；主策 Accept/Edit 后才以 Current Coverage、Requirement Closure、RuleChain、Final Publication 和 GVE16 A–J 验收。
- Core Design Depth 只评价适用的状态、触发/条件、分支/Repeat、算法、数据流、生命周期/中断/重置及跨机制依赖；QA、Presentation、Placeholder、文档长度、Proposal/Rule 数量和无独立消费者的辅助参数不得抬分。
- Projected Design Coverage=100% 不能证明达到 GVE16 深度，也不能阻止发现二阶/三阶执行问题；Conditional 子问题仍必须由当前项目 existence signal 激活。
- Full Mechanic Reconstruction 的 Review 产物不产生 Approved Rule、不关闭 Requirement、不修改 Planning Hierarchy、Final Publication 或 job.json；每项设计继续保留 knowledge class 与权威 lineage，待主策按 design item Accept/Edit。

## 2026-08-19 Mechanic Execution Depth Expansion

- Structural Completeness 只评价适用 Entry/Core Processing/Branch or Repeat/Exit/Next State 是否闭环，不代表 GVE16 级执行深度；Execution Depth Coverage 独立按 Active Depth Dimension 的 Satisfaction Contract 计分。
- Depth Dimension 必须是可独立判断 covered/missing 的执行问题；同义子项、参数 facets 和实现事件细节不得拆分扩大分母。Conditional/Optional 子维度继续受 parent existence signal Gate 控制。
- Current Coverage 只接受语义职责匹配的 Existing/Approved Logic Rule；UI/Presentation Rule 不得因文本相关覆盖逻辑维度。
- Projected Conservative Coverage 只增加通过 Gate 的 Conservative Proposal；Projected Design Coverage 再增加 Design Inference、Recommended Alternative 与参数职责 Proposal。Proposal 不改变 Current Coverage。
- Projected Coverage=100% 不代表深度完成。只要仍有当前未解决 Core、Human Decision、Compatibility/Coherence 失败或无有效路由的 Active Dimension，`depthReady=false`。
- 当前七类只属于 benchmark depth profile；本轮只产生 Review/Audit 产物，不修改 Planning Hierarchy、Final Publication、job.json、Evidence、Fact、Rule 或 Requirement Status。

## 2026-08-18 Review Hierarchy 与 Planning Hierarchy 解耦

- 七个 Mechanic Review Unit 只是当前 Benchmark 的审核聚合粒度，不是 Final Planning Schema；一个 Review Unit 可以投影到多个自然 Planning Nodes。
- Planning Hierarchy 由当前项目显式 System/Entity、Subsystem/Mechanic、Rule Primary 与 Chapter Owner 动态生成。Current System Hierarchy Audit 是本轮权威输入，但不是永久结构真理；Normalization 不迁移 Owner，只以 `ownerStructureFindings` 记录 Entity/Flow/Lifecycle Owner 混用风险。
- Planning Title Quality Gate = Composite Title Check + Single Responsibility Check。复合 Review 标题可留在审核层，但不得进入 Planning 层；自然节点必须围绕单一对象、资源、状态、生命周期或机制职责，父子职责成立且不能用万能容器掩盖聚合。
- Planning Hierarchy Preview 必须在每个承载节点下展示实际自然语言 design item/confirmed rule 摘要，默认不显示 Proposal、Requirement、Dimension ID；完整 lineage 只进入 normalization audit metadata。

## 2026-08-18 Mechanic-level Design Review

- 主策默认按 Mechanic 审核完整 AI 方案，Atomic Proposal/Requirement/Dimension 只作为可展开 lineage；当前 Benchmark 固定验证七个 Mechanic，但不把七类固化为跨项目 Schema。
- `reviewEligibility=ready` 只表示结构完整、内部一致、适合审核，不代表 Confirmed、Resolved 或 Publication Eligible；Mechanic Execution Completeness 与 Coherence 分开计算。
- `recommendedDesign` 由稳定 `designItemId` 组成，每项保存 sequence、text、knowledgeClass、sourceProposalIds、requirementIds、parameterRefs 和 approvalState。
- Accept Mechanic 是按 design item 批量产生审核决定，不把整个 Mechanic 合成一条 Rule；Accept/Edit 后仍按 design item/Requirement 分别生成 Approved Rule，并保留 `satisfiesRequirementIds[]`。
- 每个 Atomic Proposal 只有一个 Primary Mechanic Owner；其他 Mechanic 只能用结构化 Rule Reference 消费。当前武器结果处理归武器机制，独立抽取只引用，不重复定义。
- Placeholder 是最后兜底，仅用于精确数值、商业决策、核心意图不明或真实设计分叉；常识性执行收口优先生成明确 Design Inference。

## 2026-08-18 Proposal 与正式 Publication 的标题边界

- `executionDimensionId` 仅用于 Requirement/Proposal 审核与 lineage，禁止直接成为正式策划案标题；正式发布必须通过 Planning Title / Chapter Assembly 转译为自然策划语言。
- 同一 Mechanic lifecycle 下的多个 Dimension 优先合并为一个自然机制章节并用步骤、分支或生命周期载体表达，禁止一 Dimension 一标题的 schema dump。
- `proposalType / assumptionLevel / proposalId` 等审核字段只保留在 Review UI 与 metadata，禁止进入正式执行案正文。
- Chapter Assembly 必须拒绝 `weapon.slot_activation / attack.post_exit_state / statistics.end` 这类工程化 ID 作为 owner 或规则组标题；内部 ID 仍保留在结构化 provenance 中。

## 2026-08-18 Mechanic Requirement Discovery 与 Temporal Evidence Probe

- `Execution Requirement / Missing Rule Requirement` 不是 Rule，不具备 Publication 资格；它必须有稳定 `REQ-*`，并由 Evidence Candidate、P4/P6、Fact/Rule 通过显式 lineage 反查。
- Closure Status 只使用 `resolved / evidence_probe / evidence_resolvable / evidence_unknown / review_required / dormant_optional / not_applicable`；P4/P6 是 `review_required` 的 routing 属性，不新增 `parameter_required` 或 `partially_resolved`。
- Expected Dimension 分为 Core / Conditional / Optional。Conditional/Optional 没有 current-project existence signal 时保持 dormant，不进入 Probe、P4/P6、Missing 或 Recall 分母；parent resolved 后 child 仍独立过 Applicability Gate。
- Existing Coverage 必须满足 exact Dimension Satisfaction Contract；语义相关 Rule 不等于满足。部分覆盖以 parent/child Dimension 表达。
- Entry/Exit/Repeat/Pause/Resume/Interrupt/State Transition 等时序维度以视频或连续帧为一等 Evidence Source；Evidence Source 按 observableModes 选择，不能固定截图优先。
- `evidence_unknown` 必须在完整选定来源、所有锚点、候选扩展、反例检查与候选收敛均有审计记录后才能进入，并可在新素材到达时重开。
- Observation、时间顺序、状态相关性、因果支持必须分开保存；A 后出现 B 不得自动晋升为 A 导致 B。`evidence_resolvable` 仍须经过 Evidence → Fact → Rule。
- 运行时 `benchmark_execution_prior_v1` 与测试 Gold `benchmark_expected_dimensions_gold_v1` 分离；正式代码不得读取 Gold。首轮门槛为 Core Recall≥90%、Overall Active Recall≥80%、Unsupported≤5%、Routing≥90%、Probe Integrity=100%。

## 2026-08-18 RULE→SYN 权威 provenance bridge

- Phase 5.6 `RULE-*` 与 Phase 6.x `SYN-*` 之间允许建立多对多 provenance bridge，但只能消费显式结构化 lineage，例如 synthesis plan 的稳定 input line ID 及该 line 的 `supportingRuleIds[]`。
- 禁止使用文本、标题、embedding、LLM 判断或 Evidence 文本近似建立 identity 映射；没有显式 lineage 的 SYN 节点保持 unmapped。
- Bridge 只投射 chainId、position、node role、predecessor/successor、relation、terminal/reset 等既有 chain metadata，不重新生成 Rule 内容或补造 Closure。
- 同一 SYN 拆成多个发布句但无法由 lineage 区分具体 chain node 时，不得仅因共享 SYN ID 强制这些句子形成 ordered steps。

## 2026-08-18 动态最终目录与网页迁移边界

- Human Preview 中的“武器/词条/三选一/怪物/关卡/结算”仅是当前案例的 presentation grouping，不是正式 Chapter Schema，更不是所有项目或《一路狂飙》的固定六章。
- 最终目录固定遵循 `Evidence/Fact → MechanicScope → System → Subsystem → Mechanism/ChapterType → Chapter`；章节数量、层级和标题由当前游戏实际证据动态决定。
- Entity owner、Rule primary owner、Chapter owner 必须分别解析。武器栏可由载具持有，但规则定义可归武器系统；展示在结算页的数据也不自动归结算规则所有。
- 一个机制只有具备独立职责、足够规则内容、自有参数/生命周期/状态/限制之一，且合并会降低理解时，才值得独立成章。RuleGroup 和 SchemaSlot 都不等于 Chapter。
- 在用户确认 Current System Hierarchy Audit 前，不修改网页目录、不写 `job.json`、不迁移 P4/P6、不删除旧章节。

## 2026-08-17 统一 Alignment / Granularity 质量基础设施

- 每个后续阶段完成后必须分别运行 GVE16 Paradigm Alignment 与 Execution Completeness；前者只评价已有可信内容的组织表达，后者才评价机制、参数与 Gap 完整度，两个分数不得互相替代。
- 全局 Hard Gates 为：unsupported semantic addition=0、Presentation mixed into Logic body=0、Gap rendered as confirmed rule=0、Rule→Final Output traceability=100%、inferred Fact rendered as confirmed=0；任一失败则 qualificationStatus=fail。
- GranularityEvaluator 必须结合 Rule provenance、mechanismSemantic、semantic domain、block boundary 和 carrier，禁止用字数或一 Rule 一句比例单独刷分。
- 若 Paradigm Alignment <80，下一阶段自动选择 Paradigm attributedFindings 中最大扣分责任层；达到 80 后仍需两次不同生成指纹的完整运行均≥80，以及非当前项目盲测≥75且项目特有结构污染为0，才能 qualified。
- Legacy evaluator 仅可标记为 false-negative 历史对照，绝不进入新评分、阈值、finding 或 qualification。

## 2026-08-17 Phase 5.1 交付载体分离

- Execution Document 只读取 `logic / flow / numeric / config / interaction`；Presentation Rule 独立进入 Visual / Interaction Board，不再作为普通执行正文输出。
- 每条 Presentation Rule 必须生成一个稳定 VisualBlock；`relatedEntityIds` 直接消费 Phase 5 审计，`relatedLogicRuleIds` 仅允许显式 Rule ID，或同时满足共享 Entity、机制语义兼容、证据链交集后建立。
- Execution Document 默认不显示任何 VisualBlock 引用句；Logic ↔ VisualBlock 只在 JSON/provenance 中通过 `relatedVisualBlockIds[]` 和 `relatedLogicRuleIds[]` 追溯。人工正文不得出现 `VIS-RULE-* / RULE-* / MB-* / GAP-*` 内部 ID。
- Phase 5.1 不修改八步流程、P3/P5 定义、UI、P7、Entity Graph、Rule、Gap 或参数。

## 2026-08-17 Phase 5.3 Mechanic Reasoning

- `MechanicModel` 是 Rule/Gap 之后的只读机制节点地图；`confirmed` 仅由 Approved Rule 支持，`inferred_structure` 只证明节点位置，`unresolved` 挂载 Reviewed Gap，二者都不得产生 Rule 内容或关闭 Gap。
- `MechanicStructureCorpus` 只保存 GVE16 的匿名、provisional 机制阶段结构，`contentAuthority=none`，禁止运行时保存原句、项目字段、数值、规则、章节树或 Gap 答案。
- Mechanic Depth Score 评价结构节点识别与 Gap 定位，不因 Gap 未关闭直接扣分；`mechanical_information_gain` 将有信息但只表达单一输入/现象的 Rule 标为 `low_abstraction`，不误报为 filler。
- 主策推理契约升级为 `PlanningMechanismModel`：固定检查 Object、State、Trigger、Condition、Processing、StateTransition、Result、Boundary、Parameter、Dependency 和 Lifecycle；四态只允许 `confirmed / derived_structure / hypothesis / unresolved`。
- `derived_structure` 只能证明节点必须存在；`hypothesis` 只是审核建议。两者均不得生成 Approved Rule、关闭 Gap、提高 Execution Completeness 或进入正文。
- 开放 Gap 必须输出 `gapId + mechanicId + mechanismNode`，不再仅作为章节平铺问题列表。
- Phase 5.3.1 起，旧 Planning Reasoning Depth 95 只标记为 `Template / Reasoning Coverage Score`，不能作为 GVE16 推理深度验收结果；验收使用独立 `Mechanic Reconstruction Depth`。
- PlanningMechanismModel 必须关系化为 MechanicNode + MechanicEdge；模板节点、无依据 derived_structure、无证据 lifecycle 均不得提高 Reconstruction Depth。
- `derived_structure` 仅允许不可跳过的 confirmed 因果缺口、Rule 语义必然要求、Reviewed Gap 定位或已证明 applicable 的 Schema slot；initialize/persist/reset/config/dependency/boundary 不得模板式自动派生。
- Phase 5.3.2 起，Rule 必须先做 subject/object/condition/action/state_change/result/boundary/numeric 语义拆解，再 grounding 到节点；一条 Rule 可确认多个节点，禁止整句只落一个粗粒度 slot。
- `derived_structure` 必须携带 derivationType、sourceNodeIds、sourceRuleIds 和 derivationReason；缺任一项降为 hypothesis。
- `persists_until` 只代表 transientStateDuration，不能自动激活 lifecyclePersistence。最终机制深度使用 `Reconstruction Coverage × Graph Grounding Quality`。
- Phase 5.4 的 ReasoningGap 只能来自 grounded graph breakpoint；模板 slot 数量、无 grounded node 的机制和 hypothesis-only 节点不得触发 blocking Gap。
- ReasoningGap 必须绑定 sourceNodeIds、missing semantic/relation、Program impact 与 QA impact；只读标记既有 Gap 的 reuse/rewrite/delete/defer，不写回 P4、不创建 Approved Rule。
- ReasoningGap 在进入策划语言前必须通过 DecisionWorthinessFilter；common-sense deterministic、无有效分支、实现细节、过度防御边界和 already-implied 问题必须 suppress，条件未成立的问题 defer。
- 只有 keep 项可以进入后续 PlannerQuestion；Decision-aware Gap Quality 必须对低决策相关性、triviality 和无玩法后果扣分。

## 2026-08-17 Phase 5.9 规则展开深度

- `RuleExpansionPlan` 只校准已确认 Scope 内规则应展开到的执行颗粒度；不得借 GVE16 布局、类型模板或 External Corpus 新建子机制、Rule、Gap 或参数答案。
- 展开前固定通过 Expansion Stop Gate：子机制须为 `confirmed / strongly_implied`，答案须改变玩法、结果、数值或状态，且成熟执行策划确有必要明确；否则记录 `stopReason` 后停止。
- 玩法参数仍附着于自然规则位置；possible 的随机前置、满级、重复、权重、波次、胜利、奖励，以及内部排序、轮询、同帧竞争、伤害事件均不得因追求“深度”被实例化。
- `under-expanded` 只表示已确认存在的机制仍缺执行策划必须明确的玩法规则，不授权系统推理答案；参数未知由 Parameter Completeness 单独记录。刷新存在消耗不等于扣除时点必须确认，只有扣除时点会改变玩家可感知结果或资源规则时才允许提升。
- Phase 6.0 起，Rule Expansion Depth 与 Parameter Completeness 完全分开；仅参数值、单位、公式或配置来源未知时，规则深度可以是 appropriate、参数完整度单独为 incomplete。
- `recorded_data` 必须有历史记录、战绩、排行榜、跨局保存或持久化逻辑证据；结算界面展示通关时间或新纪录样式只能支持 displayed data，不能自动建立保存规则。
- 参数默认跟随所属玩法 Rule 使用 inline 或 nested bullet；只有多个同类对象共享字段且当前证据支持结构时才允许属性表。无证据公式、配置表名和字段名一律禁止。
- 跨系统正文只在缺少衔接会影响当前章节理解时使用自然短引用；一个 Rule 仅在 Primary Owner 完整定义，其他章节不得复制具体数值、分支或效果清单，也不使用“详见某章”式机械提示。
- 胜负到结算的引用必须由当前 Scope 明确支持；失败已确认但结算入口未确认时同样保持 `no_reference_needed`，不得按常见流程自动写“失败/胜利后进入结算”。
- 跨系统去重门槛是 `duplicated_full_rule_block=0`，不是禁止任何复述。为保证当前章节独立可读，可以用一条短 contextual restatement 直接陈述条件与结果，例如“载具生命值归零时关卡失败”；机器层 owner/reference 术语不得影响正文措辞。
- Human Planning Preview 禁止显示 Full definitions、Short references、Suppressed definitions 等审计结构；这些信息只进入 provenance JSON 或独立审计文件。

## 2026-08-17 Phase 5 Entity Graph 边界

- Entity Graph 只建模 Logic/Data，统一使用广义 Entity，并以 `runtime_object / container / content_item / candidate_set / runtime_context / process / report` 严格区分 EntityType；目录标题不得直接等价为 Entity。
- Presentation Rule 只能通过 `relatedEntityIds[]` 单向引用已存在 Entity，不得创建 Entity、推导 owner / parent-child / source-target，或反向定义业务逻辑。
- Phase 5 只完成 Entity Graph 与 Presentation 污染审计，不修改六章 reference document 和 P7 正式导出；逻辑正文与表现交付分离留到独立 Phase 5.1。

## 总体目标

- 工具面向游戏策划，输入有序截图并可用视频补充上下文，先审核交互，再审核玩法，最终输出一份同时包含交互与玩法的完整飞书策划文档。
- 最终结果必须持续对齐用户提供的两份飞书样例；工作台、网页预览和最终飞书不能各自使用不同的内容结构。
- 每轮重要修改完成后，要以主策视角自检，按优先级列出仍需修复的事项；不能只报告测试通过。

## 分阶段验收证据链

- 所有阶段任务必须使用项目 Skill `executing-staged-acceptance`。固定顺序是：实现但保持进行中 → 先提交验收用例 → 用户确认用例 → 按确认用例在真实环境自检 → 截图举证 → 恢复测试数据 → 自动回归 → 展示证据 → 用户人工验收。
- 用户确认验收用例之前不得开始正式自检；用户明确验收通过之前不得标记阶段完成或进入下一阶段。
- 截图必须绑定具体用例、页面、前置条件和观察结果；DOM 断言与自动化测试只能补充，不能冒充浏览器截图。未触发的条件分支必须诚实标为不适用。
- 决策卡阶段固定覆盖 TC1–TC9：明确证据不出卡、多解出完整卡、单选、多选、自己填写、暂时跳过、跨页面一致、下游失效传播、P7 正文隔离与导出门禁。
- 参数审核必须区分逐行参数表与业务配置整表；整表不得显示伪造的 `0/N 已确认`。顶部汇总、每表状态和进入 P7 的门禁必须来自全部活动表的同一份真实审核状态。
- 任何列表式审核在保存、重绘和刷新后都要保持当前对象，不能复位到第一项；以对象 ID 持久化，不能只保存数组索引。

## 主策工作台交互约定

- 同一页面同一业务动作只保留一个主入口：页底已有保存/通过时，页头不再重复；P1 新增章节不出现第二个同义按钮。
- P6 以章节组织、逐表审核：左侧切章节，同章多表同时可见，每表只显示“重新生成此表/通过此表”，全页只有一个“进入文档预览”。保存或刷新后保持当前 table ID 所属章节和目标表可见。
- P7 当前页面始终明确为“文档导出”；未完成步骤只显示 pending，不得抢占当前页高亮。顶部、右侧、百分比和导出门禁共用同一份完成度快照。
- 全链路固定顺序与名称为：玩法目录 → 交互审核 → 交付物预览 → 规则审核 → 图解审核 → 参数审核 → 文档导出。不得混用“图鉴审核”，也不得在 P7 颠倒图解与参数顺序。
- 主策视角验收同时检查：动作是否唯一、操作对象是否明确、保存后是否原位、下一步是否唯一、失败是否可恢复、页面身份/URL/可见根节点是否一致；只证明按钮可点击不算通过。

## 动态玩法结构

- 玩法目录默认先识别多个“大机制/玩法系统”，再把具体机制归入对应系统；禁止因为素材中某个功能名称显眼，就把战斗、成长、收购、阵容、结算等所有内容都塞进该功能名下。
- 是否拆成不同大机制，以玩家目标、操作对象、资源流、状态机、生命周期/重置规则、实现职责和独立验收边界是否不同为依据。多个维度明显不同就应拆分；同一闭环的连续步骤、共享对象和生命周期时才合并。
- 不规定固定的大机制数量。素材确实只有一个不可分割闭环时可以只有一个系统；禁止为了看起来丰富而凭空硬拆或套用其他项目的系统标题。
- P1 内部的“大机制确认 → 具体机制确认”属于同一页面的两个步骤。第一步确认后必须依据服务端返回的 `structurePhase=mechanisms` 留在 `gameplay_directory`，同步 URL 并滚动回新步骤顶部；只有第二步最终确认后才能进入交互审核。

- 玩法系统、模块和最终章节必须根据每份素材实际展示的机制动态生成，绝不能使用固定万能目录。
- “战斗与关卡 → 核心战斗、首领战；局内成长 → 局内成长”只属于任务 `183261b4137e40a59596b3afcaad4f18` 的当前拆分，不是其他素材的模板。
- 不同素材可能没有武器、敌人、首领、关卡、成长或结算系统；没有证据的系统不得强行生成。
- “确认玩法目录”必须处于较早环节。策划可以改名、调整顺序、合并、拆分、新增和删除章节；后续玩法审核、策划草图和飞书正文必须复用确认后的目录。
- AI 初步分类只是一份建议；最终系统边界和章节标题以素材证据及策划确认结果为准。
- 最终飞书玩法正文按实际玩法结构组织，例如玩法概述、核心循环及素材确实存在的具体系统；六层审核法是工作台内部检查方法，不是最终文档固定目录。
- “正常怎么玩、关键规则、特殊情况、怎么验证、需要配置的数值、计算公式、计算示例、配置来源”等是后台完整性检查维度，不得作为所有章节共用的固定正文标题。正文根据机制自然组织；有序列表只在真实顺序需要时出现，公式直接使用业务名称，配置优先用一张已审核表格承载。
- 表格已经表达的字段、默认值、范围、单位和来源不得在正文重复；正文只补充表格无法承载的设计目的、因果关系、执行约束和生命周期。验收用例留在审核门禁，不进入最终策划正文。
- 新任务先生成“玩法系统 → 子系统 → 具体机制”的证据结构，策划分两步确认：先确认玩法系统，再确认具体机制；详细规则只能在两次确认后生成。
- 第二阶段详细生成必须保留策划确认后的系统、子系统、机制名称和章节编号，不得重新分类或覆盖策划修改。

## 策划语言与信息分层

- 所有策划可见界面使用策划熟悉的简体中文；不要暴露程序字段名、状态码、内部编号、英文枚举或不必要的专业术语。
- 禁止在策划界面直接显示“跨页面规则、规则来源、规则参数、关联章节、必须处理、补充规则与验收”等内部化表述；必须改写为用户能立即理解的问题或操作。
- 玩法概述、目录摘要、章节说明和最终正文描述目标、循环、机制、条件、状态变化和结果，不逐帧复述按钮、弹窗、屏幕位置、颜色、边框、特效或鼠标位置。
- 原始页面、操作和视觉描述保留在交互证据层；不得删除证据，也不得把证据语言冒充玩法规则。
- 白色规则卡只放已确认内容，并使用标题加分条规则；“可能、推测、无法确认、待确认”等内容放入黄色注记。
- 视觉模型的谨慎措辞不等于整条内容未知：混合句要先保留画面明确事实，只把真正影响流程或规则、且需要策划决策的问题做成黄色注记；不得用成排“未知待确认”掩盖解析或汇总缺陷。
- 内容可信度必须区分：素材明确展示、参考文档明确说明、根据上下文合理推断、策划人工补充、待确认。
- 不使用“场景 1、场景 2”“确认第 3 步操作”等机械命名；根据玩家行为、页面目的或玩法阶段自动生成策划可读标题。

## 交互审核与策划草图

- 单步审核一次只呈现一个玩家操作，固定阅读顺序为“操作前 → 玩家操作 → 系统反馈 → 操作结果”；复杂规则放在对应步骤下。
- 需要人工确认的内容必须提供明确可选项，不能只展示“待确认”文字让用户无从操作。
- 确认当前页面或环节后，应自动前往下一项；按钮必须有即时状态、进度、成功或失败反馈，不能点击无反应。
- 策划草图使用原始截图并保持原始宽高比，不能拉伸、裁切或用替代截图冒充。
- 网页策划草图与飞书原生白板使用同一份“页面规格图集”结构：页面或页面状态、原始截图、右侧分层说明卡、已确认的页面去向和黄色确认项。玩法系统与模块只用于玩法目录和正文，不作为交互画板顶层结构。
- 当前版本按用户最新飞书策划白板实现；红色 1、2、3、4 编号属于后续 UE 流转图能力，本版本保留扩展但默认不显示。
- 实线表示前进或打开，虚线表示返回或关闭；黄色注记用于异常、跨状态约束、特殊优先级和待确认内容。
- 顶部 HUD、状态栏、倒计时、血量等常驻信息只作为截图内证据，不单独提升为交互环节或主流程规则；只有玩家可操作或会改变页面状态的内容才进入策划草图。
- 未知、可能、推测或无法确认的转场不得画成正式箭头；多条箭头必须使用独立空白通道，不能穿过截图、标题或规则卡，也不能互相重叠。
- 项目默认按移动端交互表达；鼠标、光标、悬停等桌面端观察不得进入交互规则或箭头标签，已确认操作统一使用点击、长按、滑动、拖动等移动端策划用语。
- 页面说明文字必须完整自然换行，卡片和飞书文字节点高度随内容增长，不得用省略号隐藏正文；不存在真实转场或缺少可见端点时不得自动补箭头。
- 策划草图页面单元对齐 GVE16 样例：移动端原始截图在左，浅黄色标题栏的完整页面说明卡在右；说明分组由页面实际内容动态生成，主流程优先纵向排列，分支可横向展开。

## 玩法审核

### 图解生成与审核

- 玩法图解必须表达真实的策划语义：玩家操作、系统处理、判断条件、分支、循环、汇合和结果。属性或参数逐项串联即使有箭头也不能通过。
- 策划人工编排或已通过主策判断的语义图不得被通用生成器覆盖。正文变化时保留上一版合格图并标记需更新；重建后保持图解 ID 和章节绑定、提升版本并重新审核，不得自动通过。
- 已有跨章节图覆盖某章节时，不得再为该章节补一张重复单章图；生成后必须检查有效图数量、ID 唯一性和章节覆盖关系。
- P5 左侧章节、中间图解和右侧审核控件必须绑定同一图解 ID；切换章节时三处同步。状态汇总、颜色、完成度与下一步门禁统一读取后端真实状态。
- 待审核使用橙色并明确写“待审核”，正文变化导致失效时写“需更新”，只有真实 reviewed 状态使用绿色“已通过”。
- 用户判退图解时立即停止后续审核，不得继续批量点绿；先撤销误写状态、分析语义缺口、修复并重新展示完整大图。

### 策划配置表的正式交付规则

- 正式策划案中的表格必须围绕实际查配动作设计，不能把后台字段审计数据直接排成万能表。载具等级表直接列等级、升级道具、消耗和各级属性；武器表直接列伤害、冷却、目标和范围；词条表直接列前置、等级、权重和效果；怪物与波次表直接列怪物、点位、间隔、倍率和切换条件。只有当前素材存在对应对象时才启用这些知识储备。
- 禁止在 P7 或飞书正式正文输出以下通用审计表：`属性／说明／类型与单位／配置或计算／限制条件`、`字段／策划含义／当前值与范围／类型与单位／配置来源`、`名称／填写格式／单位／默认值`。`parameters` 与 `parameterSchema` 属于工作台审核和质量门禁数据，不是默认交付表格。
- 表名和列名使用业务名，单位直接写进对应列名；正文负责含义、因果、执行时机、约束和生命周期，表格只负责填写与查配，不重复机械解释正文。
- 同一对象按真实配置职责拆表，不把载具等级、栏位、特权，或武器基础属性、解锁养成、词条塞进一张大而泛的表。已有权威表名或字段名时就近映射；没有依据时不伪造正式值、表名或字段名，也不使用大量“待配置”填充单元格。
- 整张表没有已确认值时，只有“配置结构本身”确为交付要求才保留可填写空位；存在多种合理取值且会改变规则时必须进入决策卡并阻断导出，不能用空格冒充确认。
- P7 与飞书必须消费同一组已审核业务表。浏览器验收按对象分别提供原尺寸完整截图，并检查 `scrollWidth <= clientWidth`、右边界未出框、表头没有被压成逐字换行；不得用一张缩小长图代替多张可读证据。

- 图解只用于文字难以清楚表达的结构关系，例如空间关系、包含多个真实状态的流转、概率池关系或多段效果链。纯文字摘要、单个公式、普通参数列表和只有“标题＋说明”的伪流程图不得生成图解；这些内容直接使用正文、公式块或表格表达，并在图解环节标记为“无图解”。

- 每个玩法章节内部按六层检查：章节范围、核心规则、参数与公式、依赖与冲突、验收用例、审核结论。
- “进入条件、开始前状态、处理过程、选择分支、结果、保留或清空、特殊情况”只作为 AI 后台完整度检查，不得原样变成策划端标题。
- 策划端按“一句话玩法 → 正常怎么玩 → 关键规则 → 数值配置 → 特殊情况 → 检查示例 → 还需要确认”阅读；空部分不强制展示。
- 分析草稿不能平铺成同级目录；最终目录先按当前素材识别玩法系统，再把具体规则放到所属系统下。系统名称与拆分必须随素材变化，不能把当前任务的“战斗与关卡、局内成长”固化为全局模板。
- 参数需要字段类型、单位、默认值、上下限、配置来源、计算顺序、取整方式和算例；不能只藏在大段文字中。
- 验收至少覆盖正常、边界、失败、退出重进和跨章节组合情况。
- 审核结论为通过、有条件通过或退回修改，但工作台要用策划自然语言呈现。
- AI 自检可压缩为不超过四句话，但不能省略自检逻辑。
- 工作台采用“证据工作室”三栏结构：左侧动态三级玩法目录，中间原始素材，右侧策划规则；原图和规则长期并排，避免策划来回切换。
- 所有玩法共享“可制作、可配置、可验证”的完整度底线，但不共享固定字段。公式、概率、资源流、空间关系、状态转换等模块只在当前机制确实需要且有证据时出现。
- 参数表、公式、算例和配置来源属于按需模块；空模块不展示。公式本身及每个变量必须标注可信程度，并关联素材截图或参考文档来源。
- 配置类规则需要支持“规则正文 + 配置表 + 字段”的同章输出。例如载具等级可同时写明初始等级、升级消耗、属性变化、不可逆和活动结束重置，并列出 `GveMagicBookVehicle` 的 `_id`、`cost`、`atk`、`hp`、`dr` 字段；准确表名和字段名只能来自参考文档或策划补充，不能由截图臆造。

## 交付与运行

- 交互和玩法最终写入同一份飞书文档，不得拆成两份最终文档。
- 交互画板交付保持“策划草图 → 竞品参考”顺序；竞品参考只能使用用户提供的竞品素材。没有素材时显示“本次未提供（可选，不影响导出）”，不能长期显示模糊的“待补充”。
- 两份飞书样例的共同颗粒度合同是：有证据时必须补齐内容清单、配置字段、执行顺序、公式与算例、异常边界和生命周期；只复用该推导方法，不固定复用样例里的武器、怪物、组队、地图等目录。
- 视觉模型已经配置时不得误报“未配置”；配置状态必须来自真实后端状态。
- 长任务必须展示真实进度。失败时保留任务、素材和可重试入口，不能运行完自动消失、卡在 0% 或用笼统错误循环失败。
- 单帧模型响应解析失败必须被识别为技术失败并进入修复链路；环节摘要要汇总全部代表图，不能因为第一张失败就忽略其他已经识别成功的截图。
- 局域网工作台应能刷新后恢复当前任务，并可通过任务链接直接返回工作台。
- 深链初始化期间，用户新点击的 P1–P7 阶段优先级高于最初 URL 的迟到恢复；所有异步恢复必须比较导航意图版本，不能在请求结束后把用户拉回旧页面。
- P7“处理未完成项”必须跳到规范模型计算出的首个真实阻塞阶段；“返回修改”可保留固定编辑入口，两者不得共用固定路由。

## 每次生成前后的强制主策门禁

- 已由策划确认的新版本页面审核数据，不得再被旧版 `smallLoop` 等兼容字段判为分析失败。质量检查必须优先认可“已确认＋页面目标明确＋存在参考画面”的当前审核结构；旧字段只可作为未确认草稿的补充判断，不能覆盖已确认事实。

- 每次生成玩法结构、玩法细节、交互交付物或最终文档前，必须先以第一次接触项目的主策视角检查：当前目标是否明确、目录是否符合素材、证据是否足够、是否会产生固定模板误套、是否存在策划无法理解的词。
- 每次生成完成后、进入人工审核或发布前，必须再次检查：玩法规则与交互证据是否分层、图文是否对应、章节是否达到可制作/可配置/可验证的颗粒度、参数与公式是否有依据、待确认项是否真需要策划决策。
- 以下任一情况必须阻止生成结果进入正常审核或发布：看图描述冒充玩法规则；按钮/弹窗/屏幕位置等交互术语进入玩法摘要；英文枚举、内部编号、`undefined` 等程序字段外露；固定目录套用不同玩法；图文不一致；重复或空章节；公式和配置字段无证据；点击无反馈或跳转错误。
- 自动检查是硬门禁，不得只依赖对话记忆或人工自觉。每次新增踩坑都要同时补充持久记忆、自动测试和生成/发布校验代码。
- 同一有序素材、模型版本、提示词版本和已确认目录必须使用内容指纹复用已经通过质量门禁的识别结果；缓存只能在完整校验通过后写入，失败结果不得缓存。
- 重新生成不得覆盖已确认目录、已确认章节或策划人工修改。低于质量下限的候选结果必须保留上一次合格版本并明确失败，不得用空泛兜底文案降级交付。
- 历史优秀章节只能提供已通过主策审核的“信息密度与模块选择”参考；禁止把历史章节的玩法名称、数值、规则或结论复制到新素材。
- 新章节的流程、关键规则、特殊情况和验收示例不得明显低于相近已通过章节的信息密度；低于参考密度的 75% 必须阻止进入审核。
- 首次候选未通过主策门禁时允许自动纠偏一次；第二次仍不合格则明确失败。失败候选不得写入缓存，纠偏提示不得改变已确认目录和章节结构。
## 截图覆盖与页面关系硬规则（2026-08-06）

- 每张输入截图必须显式归类为“独立页面、补充画面、重复画面”之一，并且恰好归属一个页面；代表截图只负责展示，不得代替素材完整性清单。
- 每张截图必须拥有自己的页面信息框，再由页面关系串联；禁止将多张截图的识别文字合并后套给同一张图，也禁止静默遗漏非代表截图。
- 同一来源页面的互斥去向必须形成单选组；选择一个去向时，同组其他去向要在同一次保存中取消。完全重复的页面关系只保留一条有效关系。
- 页面信息框除主要用途和操作反馈外，还要保留等级、武器槽、资源、生命、时间、进度等次级区域；这些信息作为页面证据，不得擅自提升为独立流程环节。
- 已存在的历史任务打开时也必须执行上述迁移并持久化，不能只让新任务使用新规则。
## 自动执行与自检

- 用户确认执行后，只要不存在权限、安全或外部凭据阻断，就必须连续完成生成、修复、回归和主策自检，不在可自动处理的中间状态停下来等待“继续”。
- 进入最终文档阶段时，若浏览器已有模型配置且玩法章节仍需补全，工作台应自动补全、自动重建预览并再次执行主策门禁；失败时保留已确认内容并自动重试质量问题。
- 玩法章节数量永远来自当前素材拆解和策划确认后的目录，不固定为 18 章或任何预设数量；进度、日志、预览和导出必须读取同一份动态目录。

## 新窗口交接：颗粒度对齐仍未完成（2026-08-11）

## AI 不确定内容必须转为可决策卡（2026-08-11）

- 禁止在策划界面单独显示“待确认”或“未知待确认”。只有素材不足、确实存在至少两种合理解释时，才生成结构化决策卡；明确素材能够判断的内容由 AI 直接填写。
- 决策卡必须包含：明确问题、至少两个可执行选项、单选或多选限制、自己填写、暂时跳过、AI 推荐及理由、截图或参考文档依据、保存后的影响范围。
- 未选择的卡片不得进入正式规则或冒充已确认结论；应用选择后必须原子更新正文、策划草图、表格和最终文档所消费的规范数据。
- 决策卡需要覆盖玩法目录、页面名称与用途、玩家操作与跳转、触发方式、互斥分支、玩法规则、参数与公式、图解必要性、表格结构和最终文档决策项。
- 2026-08-11 第一阶段已建立玩法章节决策卡模型、P4 卡片界面和后端原子应用操作；其他 P1–P7 位置仍需接入，未完成前不得声称全局覆盖。

### 当前结论

- 禁止把当前分支描述为“已完全对齐两份飞书样例”或“P1–P7 全部验收通过”。页面与主流程已做大量修复，但正文内容仍存在关键未完成项。
- 用户最新明确指出：最终正文仍机械复用相同章节结构，层级很多但每层内容很少，语言像表单和机器模板；必须改成随机制复杂度、证据类型和玩法类别动态组织。
- 已定位并删除一类错误生成源：仅凭章节名关键词自动制造生命值、伤害、抽取、刷新、结算等参数和公式。典型错误包括“变化前生命值／本次承受伤害／恢复量”“参与‘某机制’计算的数值”“数值·按实际配置”。这些内容并非来自用户给出的飞书样例或当前素材，必须在现有任务与未来生成中归零。
- 已删除最终正文兜底句“本节规则已完成审核。”；章节没有摘要时应优先使用已确认规则事实，完全没有事实则视为内容缺失，不能显示审核状态冒充正文。

### 下一窗口必须继续处理的问题（按优先级）

1. **P0：正文结构雷同。** 每章不能固定输出“概述／正常怎么玩／关键规则／参数／验证／特殊情况”。简单机制应写成一段或少量自然小节；复杂机制才按证据展开配置表、公式、算例、边界、生命周期。不同章节的标题、段落数量和信息密度必须明显不同。
2. **P0：逐句来源校验。** 扫描完整预览和飞书输出，删除所有无证据的通用参数、通用公式、通用配置来源和审核状态句；参数或公式只有在素材明确展示、参考文档明确说明或策划人工补充时出现。
3. **P0：清理当前任务遗留数据。** 当前任务 `8312a91c89e144e6a59f81b982f14c06` 由旧任务证据复用恢复，JSON 中仍可能保留旧模板内容。必须先备份，再运行 `migrate_gameplay_presentation` 清理，并重新生成玩法表格与最终预览；不能只修未来生成逻辑。
4. **P0：对齐两份飞书样例的组织与语言。** 对齐的是“如何从证据推导内容、如何按玩法实际结构组织”，不是复制固定目录。正文需呈现内容清单、配置字段、执行顺序、公式依据、异常边界和生命周期，但仅在该机制确实需要且有证据时出现。
5. **P1：P7 同时包含交互与玩法。** 交互部分固定标题为“策划草图”，以画板输出；玩法正文随后按实际系统组织。竞品素材为空时写“本次未提供（可选，不影响导出）”。
6. **P1：完成度一致性。** P7 的顶部步骤、右侧完成清单、百分比和导出门禁必须使用同一真实状态，不能一处完成、一处未完成。
7. **P1：全流程最终验收。** 完成内容修复后，按 P1→P7 逐页实测按钮、跳转、互斥、保存、刷新恢复、滚动、缩放、导出；再逐条复核飞书反馈表，最后才能宣称完成。

### 本轮已经修改但尚需全量回归的代码

- `backend/gameplay_review_model.py`：移除按章节关键词制造参数／公式的框架；伤害数字只保留为画面核对证据，不反推伤害公式。
- `backend/gameplay_copy.py`：展示版本升级到 11；迁移时删除历史 `evidenceLevel=根据素材推断` 且属于通用模板的参数与公式。
- `js/final-document-preview.js`：移除“本节规则已完成审核。”兜底；摘要缺失时使用第一条有效规则，并参与正文去重。
- 对应红—绿测试已更新：`tests/test_review_model.py`、`tests/test_gameplay_review_model.py`、`tests/js/final-document-preview-ui.test.js`。

### 测试与验证状态

- 最新 P7 定向测试：23/23 通过。
- Python 两个定向文件在旧断言更新前为 71 通过、2 失败；这两个失败正是旧测试仍要求自动制造伤害公式和随机池参数，现已按新证据规则修改断言，**提交前必须重跑，下一窗口也必须跑全量后端测试**。
- 任何“测试通过”只代表对应契约，不代表内容已逐字对齐。最终必须额外扫描可见预览，确保以下文本为 0：`本节规则已完成审核`、`参与“`、`按实际配置`（无明确来源时）、无证据的“计算框架”。

## 2026-08-12 阶段5用户确认的内容与界面边界

- 属性不能只通过表格表现。正式策划案按“机制正文逐项解释属性含义、计算/判断作用、时机与边界 → 权威字段就近映射 → 紧凑配置表集中查值”的顺序输出；表格完整但正文属性缺失必须判为未通过。
- 属性正文按实际对象与信息簇命名；禁止统一套用“基础属性／规则与边界”，也禁止把表格逐行机械改写成同构句子。
- 正式正文和图解说明只写业务规则。“流程图只确定”“素材只证明”“仍由决策卡确认”“不从流程图推断”“留待阶段验证”等内容必须留在审核元数据或决策卡。
- 决策卡选项以文字为主：radio/checkbox 固定在每项左侧，文字紧随其后；短选项保持单行，不得因全局输入宽度制造空白或挤压换行。
- P7 未完成入口显示真实剩余数量；存在未处理决策时，点击进入首张未处理卡所属章节并滚动、聚焦，不能笼统跳回参数表，也不能代替用户选择。
- 每次发现废话或元话语，必须同时修复当前数据、生成规则、语言门禁和回归测试。
- 飞书反馈表是最终硬门禁：除“验收无误”外，每条必须具备修复位置、改善路径、自检结果和匹配截图；自动化通过不能代替逐条复核。
# 2026-08-12 飞书样例规则必须进入底层运行链

- 任何从飞书样例确认的规则，只有同时落实到生成提示、规范数据、审核门禁、P7/飞书同源渲染和自动测试，才算进入项目逻辑；只写 Memory、Skill 或说明文档不算完成。
- 所有存在属性的核心对象都必须分别以对象名作为属性大标题，再通过 `plannerSections.attributeSections` 按业务责任生成二级标题并逐项解释含义、所属对象、计算/判断、读写或生效时机和边界；不得只为载具等单个对象建立属性章节。紧凑表格随后承载值、单位、范围和来源，参数表不得替代属性正文，也不得机械文本化。
- P7 与飞书必须消费同一份已确认属性分组；规范化、迁移或重建 `plannerSections` 时不得丢失 `attributeSections`。
- 策划草图中已经识别并有截图支撑的武器、强化、载具、怪物或关卡业务属性，必须进入对应对象正文的 `attributeSections`；画板不是这些业务事实的唯一交付载体。泛化 UI 识别、布局和操作位置不得搬入属性正文。
- 跨载体验收固定覆盖四项：①画板具名业务事实进入对应对象正文；②“画面包含等级信息”、槽位存在、按钮位置等泛化 UI 文本不得进入正文；③同步遗漏数必须为 0，P7 与飞书正文逐条一致；④同一规则覆盖载具、武器、怪物和关卡，但没有具名证据时不得扩写。
- 流程图不得插入同一编号规则组中间。先完整写完当前业务步骤，再紧邻放置对应图解；`afterFlowIndex` 等编辑锚点只能用于内部管理，不能破坏策划正文的连续阅读。
- “图中的内容由后续章节展开”“本节继续说明”“流程图只确定……”属于 AI/审核导航旁白，禁止进入正式策划案。图解后只在确有新增业务规则时写规则本身，否则不补过渡句。
- 长列表与碎标题之间按内容量取中间值：同一章节出现 8 条以上且包含多个明确业务主题时，合并为 2～4 个业务小标题；每个小标题下保留若干分点。不得整段无分组罗列，也不得为每条规则单独起标题。
- 小标题必须由当前内容决定。例如首领章节可按“触发与战斗状态／属性与承伤判定／胜负结算”组织，但奖励、武器、载具等章节不得借用这套标题。相近重复规则合并一次，禁止生成“其他规则”等兜底模板标题。
- 完整运行映射见 `docs/research/feishu-sample-runtime-contract-2026-08-12.md`。
- 返回与保存稳定性：用户主动切换 P1–P7 要进入浏览器历史；深链初始恢复和迟到异步补载只替换当前项。所有返回方式都验证页面、任务 ID、当前对象和已保存数据。P5/P6/P7 单项保存不得自动退回更早步骤；独立 gameplay model 为权威版本，禁止旧内嵌快照覆盖。保存型验收固定证明“一次请求、即时更新、不复位、刷新仍一致”。
- 历史目录迁移：canonical claim 必须有稳定 ID，目录 entry 的 `claimIds` 必须从同章 claims 回填；否则合并/拆分虽然有按钮却没有真实可操作内容。验收必须展开选择面板看到选项。
- 失败任务重试：失败工作台先固定 `job=<失败ID>&ui=analysis_failed`；模型配置暂存并恢复完整 URL；重试只能向该失败 ID 发一次请求。打开工作台与发起重试必须使用不同截图证明，禁止重复截图代替不同状态。
- 2026-08-17 起，内容模型 v2 的 P4 审核单位固定为可追溯的 AtomicFact → SchemaSlot → Rule；一条 Rule 只允许一个规则类型，逻辑、表现、数值、流程、交互、配置必须独立审核。v2 不得把 `plannerSections` 或 `sourceType=planner/pending` 的 claim 作为正文事实源；v1 仅通过显式 legacy adapter 保持兼容。Phase 2 产生的候选 Rule 默认 `unreviewed`，不得自动批准。
- Phase 5.4.2 起，Graph breakpoint 只说明实现信息有缺口，不等于主策必须回答。Candidate Gap 必须先分流为设计决策、参数、实体属性、实现默认、表现细节、证据已回答、上游冲突或延后；只有会显著改变玩法、策略、系统规则、经济、重要状态或跨系统关系的 `real_design_decision` 才进入 Planner Review。
- 默认行为只能抑制低价值问题，不能生成或批准 Rule；参数和实体属性必须降维路由，不得包装成复杂策划问题。发现证据与玩法理解冲突时，必须回到 Evidence → Fact → Rule Review，禁止沿错误前提继续扩写。
- Planner Review 的最终审核单位是 PlannerDecision，不是 ReasoningGap。属于同一 mechanic、共同控制同一 design lever、且可由同一策划结论回答的 Gap 必须聚合；QA 可从一个 Decision 派生多个 Case，但不能反向决定策划问题颗粒度。
- 压缩时仍要继续过滤常识：正常配置完整性、自然交互收尾和无证据的极端容错不得仅因存在 Graph breakpoint 而保留为 PlannerDecision。
- 当前 Planning Reasoning 主目标固定为 Game Design Reasoning：玩家行为、获取/使用/解锁/成长、随机、战斗、资源、关卡、胜负、奖励、限制、生命周期和跨系统关系。排序、轮询、同帧冲突、向量合成、原子提交与内部清理属于 Implementation Reasoning，单独记录且不进入主策正文或 Planner Review。
- Game Rule Template 只能证明“主策通常会定义哪些玩法规则”，不能补答案或自动生成 Planner Review。Implementation Detail 数量不得提高 Game Mechanic Depth。
- Game Rule Template 展开前必须先完成 MechanicScope Inference。只有 Evidence／Fact／Rule／UI structure／Entity relationship 支持为 `confirmed` 或 `strongly_implied` 的子机制，才允许实例化 missingGameRules；`possible / unsupported / contradicted` 只能进入探索或上游复核。
- `unresolved` 只表示“机制存在但规则未知”，不得表示“不知道机制是否存在”。攻击间隔、射程、伤害、刷新次数/消耗、移动速度等直接改变玩家结果的项目保留为 gameplayParameters；ParameterResolver 只负责后续结构化值、单位和来源。
- 外部游戏设计 Skill 只可蒸馏为 `possible scope / possible rule dimension`，`contentAuthority=none`。任何 genre、GDD、经济、平衡或系统设计模板都必须继续经过 Phase 5.4.4 MechanicScope Gate；外部 pattern 不得直接生成 missingGameRules、Approved Rule、Gap 答案或 Renderer 文本。
- Missing Execution Detail 与 unresolved gameplay parameter 必须进入现有审核闭环：规则形式、布尔、多选、复杂规则和证据冲突由 P4 处理；数值与枚举参数由 P6 处理。P6 不得重新决定机制是否存在，P4 不得把具体数值伪装成规则选项。
- 审核控件只能实例化当前 MechanicScope 已确认或强暗示的维度。GVE16／External Corpus 可帮助组织候选，但 possible-only 方案不得直接成为项目选项；Scope 只证明大类机制存在而未证明具体分支时，使用拆分后的结构化规则输入。
- 条件参数必须依赖用户已确认的规则分支：例如持续接触伤害确认后才显示结算间隔，刷新选择资源消耗后才显示资源类型和数量。AI 推荐始终是 recommendation-only，只有用户确认后才能 Promote 为 Approved Rule／Approved Parameter。
- 可观察答案优先路由 Evidence Recheck；无真实设计分支的自然闭环路由 Suppress。两者都不能自动生成 Rule。P4/P6 人工界面禁止内部 semantic、Rule/Gap/Entity ID 与工程术语。
- Phase 6.2 的 GVE16 对齐先做 Content Richness，再做 Density Pruning。“短”不能以遗漏规则为代价；正文丰富度只允许来自 Approved Rule、confirmed／strongly implied Scope 对应 Missing Rule、P4/P6 ReviewDecision 和已观察 Gameplay Parameter。
- Content Richness 必须逐章报告 Present、Supported-but-not-rendered、Pending Review 与 Correctly Rejected Dimensions。possible／unsupported、外部 Skill 候选、GVE16 项目规则、实现细节和常识解释固定贡献 0；Supported-but-not-rendered 属于 Too Thin，但不能由 AI补答案。
- Review-State Rendering 固定为：Approved 写具体规则；P4 Pending 只写简短规则缺口；P6 Pending 写自然参数项；Evidence Recheck 保持 pending_evidence 且不进入正文；Suppress 不进入正文。候选选项、AI 推荐和内部审核问题永不进入策划正文。
- Effective Rule Density 按有效玩法规则、具体数值、有效限制、跨系统关系和可操作未决规则统计，同时要求 filler=0、implementation noise=0。禁止用最少字数、最少句数或抽象总结替代具体规则值。

## 2026-08-19：完整 Alignment Audit 是唯一 Closure Backlog

- 《一路狂飙-GVE16-最完整差异审计.md》是当前 Benchmark 唯一权威 Backlog。禁止代理自行选择“优先修复项”后停止；必须遍历 H/UE/W/C/D/M/L/S/P5/P6/PR 和跨交付一致性全部原子项。
- `material_insufficient`、`review_not_completed`、`scope_unresolved`、`no_existence_signal`、`delivery_pending` 是修复路由，不是跳过理由。
- 非 `=` 项最终必须进入 fixed、approved_design、evidence_resolved、parameter_resolved、scope_confirmed_not_applicable 或 blocked_by_missing_source；长期 U/△/scope_unresolved 不算完成。
- 没有截图信号不能自动判 N/A。先完成完整素材、UI入口、系统关系和产品范围核验；只有主策明确不存在才能 not applicable。
- 每个关闭项必须改变真实交付面；只修改 Audit/Matrix 不算修复。
- GVE16 项目答案不可迁移，但其暴露的当前项目必答问题必须形成《一路狂飙》自己的 AI 方案、审核决策与 Approved Data。

## 2026-08-19：UE 画板编号与正文 Owner 纠错

- UE 流转图每张图的 1/2/3/4 必须指向同一截图内四个不同真实功能，说明控件是什么及作用；禁止把编号用于整张画面的时序解说。
- Screenshot title 必须绑定自己的 authoritative frameId；禁止借用 representativeFrames[0]。
- 当前自然 Owner 至少包含载具、武器、怪物、战斗规则、关卡规则。“核心战斗/局内成长”只是当前聚合结构，不能遮蔽稳定实体 Owner。
- 武器栏是载具持有结构；武器获取/攻击/词条归武器；战斗等级、三选一、独立抽取默认属于关卡内部逻辑，除非项目证据证明另有稳定 System。

## 2026-08-19：Alignment Closure 必须通过端到端发布追踪

- Matrix 的 `closureState`、Review Layer、sidecar、raw node 或测试命中只能证明中间状态，不能证明用户交付。最终关闭必须单独记录 `deliveryClosed`，并完整证明 Source → Approved Data → Rule/Parameter/Presentation/Transition → Assembly → Final Artifact → Feishu Render → Semantic/Visual Verification。
- 当前用户链接的飞书文档仍消费旧 `gameplayReviewModel`，未消费 canonical `human-planning-preview.md`；因此此前“完整 Closure 已完成”的结论无效。
- 当前飞书只有两块 UE 白板和一张旧通用参数表；P5 必要图解未发布，canonical P6 六张业务表未完整发布。策划草图预览为七个超宽横排 Section，默认总览不可读，raw 节点存在不能抵消视觉失败。
- P0 只读审计产物位于 `artifacts/p0-end-to-end-publication-trace-audit-2026-08-19/`。修复恢复前先以该目录的 195 项 trace 定位首个断链位置，不得继续用关键词命中或相关句代替 Satisfaction Contract。

## 2026-08-25 Gameplay Model 全项目生命周期不变式

- Gameplay Model 不是《一路狂飙》或成功生成任务的特例产物；每个正常项目从交互模型建立后，必须有可序列化的 Gameplay Model。AI 未生成内容时，模型仍必须包含由 Approved Flow / State 确定性投影的 rule-free skeleton。
- AI 生成失败只能将 `contentState` 改为 `failed`，等待或重生成时为 `pending`，不能删除聚合根。从未成功过时保留确定性骨架；已有有效版本时保留完整内容并记录 `lastValidRevision`。
- `failed` 必须同时给出 `failureKind`（configuration/network/quality/system）、策划可读原因、素材门槛判断和下一步。刷新只恢复现场，不承诺外部 AI 成功；重试重新发起生成且不得覆盖骨架或最后有效版本。截图数量达到上传门槛不等于有效信息充分，两者必须分别说明。
- 进入 P1、刷新或恢复深链不得隐式触发 AI 重试；失败原因卡必须先稳定显示，只有用户点击明确的“生成玩法目录”按钮才允许重新排队。
- GET 必须只读、可重复、返回 200；惰性规范化或补建失败时返回确定性恢复骨架，不得写入 job，也不得编造 Gameplay Rule。
- “GET 只读且可恢复”必须覆盖页面启动依赖的聚合 `/api/jobs/{id}` 和专用 Gameplay Model GET，不能只修后者；正式验收必须从浏览器网络面确认两个入口都无 500。
- 前端只根据显式 lifecycle/review state 判定是否需要生成；不得以 `chapters.length === 0` 猜测，因为合法的历史或最小模型可能暂无章节。
- P4–P7 直达链遇到未就绪容器时，必须同时把视图和 URL canonicalize 到 P1；只改画面不改 URL 会在刷新/后退时重现错路由。
- Gameplay 生成失败只封锁依赖 Gameplay 内容的后续交付，不能封锁已经存在的 Approved Flow / State / Interaction Model；P2 及已满足前置条件的环节必须仍可检查。
- 缺少 API Key 属于提交前 configuration failure：后端必须在排队前返回明确 400，前端必须引导填写并保存 Key；不得生成一个永远无法执行的 pending 任务，也不得只显示笼统 system failure。
- 页面进入、刷新和深链恢复不得触发任何有成本的生成。P7 完整预览也必须由用户点击明确按钮后才可 POST；请求 URL 最终必须同步实际 active view，而不是用户请求但被拦截的 view。
- 取消隐式生成后必须补齐有意图的 idle UI；显式按钮不能作为左上角裸内容漂在空白页中，应使用桌面端居中状态卡，让用户清楚这是等待操作而非加载失败。
- 恢复卡、空态和错误态的 CSS 必须显式尊重 `[hidden]`。状态单测通过不等于视觉正确，发布前必须用桌面截图检查隐藏层、重叠和选择器优先级。
- 恢复态是正式产品态，必须有明确状态、保护说明和单一主操作。验收固定覆盖 ready 已有项目、failed 已有项目、required 新项目、最后有效版本保留、截图序列和视频两类输入，并留存桌面端截图、URL、控制台与失败请求证据。
- 异步 Gameplay 生成不得只有 `running` 和一个静态百分比。每次生成必须有唯一 attempt/generation ID、`startedAt`、`deadlineAt`、真实阶段和总时限 watchdog；超过时限自动转为可重试的 network failure，并保留确定性骨架或最后有效版本。
- 超时与正常完成必须按 generation ID 做 compare-and-set。旧请求迟到返回时不得覆盖已经超时、重试或完成的新一轮结果；服务重启同样把遗留 queued/running 转为可重试失败。
- 生成进度只显示服务真实上报阶段与百分比，并用客户端时间显示已等待时长和自动停止预期；不得用动画或递增假进度掩盖模型卡死。桌面验收必须看到阶段、百分比、已等待时间、超时后可重试说明，且无重叠或横向溢出。
- 截图导入是可中断事务：开始处理前持久化 expected-count manifest，完成后原子标记 complete。服务重启遇到 image-sequence job 的 `frames=[]` 时，必须用 source/frame/structure 三联文件和 manifest 恢复；无法证明完整则明确失败并要求重新选择原文件夹，禁止永久 `queued/0%`。
- 浏览器 API Key 不落盘，因此服务重启后不可假装能自动继续付费分析。素材恢复成功但无可信服务端 Key 时，保留恢复后的 frames/scenes/tracks，显示“素材已恢复，等待重新分析”，由用户重新确认 Key 后显式重试。

# 2026-08-26 Gameplay 详细生成不能把证据缺口变成失败循环

- “可进入策划审核”和“可最终发布”是不同门槛。Grounded 玩法正文已经生成、但截图不能证明具体数值或公式时，必须删除无依据答案并生成 Planner Decision；不能先删字段，再用最终发布门槛判整批失败。
- 未解决决策卡只允许草稿进入 P4，不得绕过 P7/导出门禁。决策卡必须列出缺失参数或公式、至少两个可执行选项、推荐理由、证据缺口和下游影响。
- 长批量 AI 生成必须按章建立安全检查点。每章只有通过响应结构、证据引用和无依据模块清理后才可暂存；后续模型服务中断时从未完成章续跑，不能丢弃已经完成的章。
- 批次级语义或质量失败必须删除该批检查点，避免低质量内容在手动重试中固化；网络/API异常则保留已验证检查点。
- 分章缓存必须携带 job identity、Approved Gameplay revision、证据指纹、模型与 prompt contract。相同截图或相同章节名不能使不同项目共享 AI 响应。
- APIStatus、InternalServer、RateLimit、Connection、Timeout 等模型服务错误必须归类为 network/request failure，展示可重试原因；不得误报“服务内部异常”。
- 正式验收必须模拟“第 N 章成功、第 N+1 章断线、重试续跑”，并验证模型调用次数没有重做前 N 章、项目间缓存不污染、语义失败会清除坏缓存。
