# Wiki：当前有效项目事实

## 2026-08-26 项目范围纠正（覆盖下方《一路狂飙》当前交付状态）

- Planner Intelligence 网页工具是当前唯一迭代主线；《一路狂飙》Final Delivery 已退出当前项目范围。
- 下方《一路狂飙》文档、revision、审计和候选状态仅是历史事实，不再表示待办、当前交付或待策划复审事项。
- 如需回归，只能把《一路狂飙》当作不可修改的 legacy fixture；当前新项目验收使用“苏丹的游戏”等隔离任务验证通用产品能力。


## 2026-08-26 当前交接事实（覆盖下方同类旧状态）

- 本地分支 `codex/planner-decision-card` 的可部署应用候选为 `3c3d954a677eacdd7f720bb1e990d8af14d131c4`，父提交 `b80870d`。本地 tracked worktree 干净；大量历史未跟踪产物继续保留；`scripts/publish_current_alignment_to_feishu.py` 无本轮 diff。
- GitHub 的应用候选等价提交为 `429ce69fd353f21ca2d6fef0e7fef1ba56090c47`；本次交接 HEAD 又通过受控 GitHub API 推送并完成 tree 校验。新会话应回读精确远端 SHA，不能把应用候选 SHA 与交接 SHA 混为一个版本。
- SVN `ai_gamedesigntool` 的应用候选同步为 r126；本次交接最终同步为 r128，release manifest 指向最终本地交接 HEAD。应用 Brand Update 仍固定使用 `3c3d954`。
- 应用候选测试基线：Python `1652 passed`，JavaScript `492 passed`；另有证据归位聚焦回归 `137 passed`。这些是本地回归证据，不等于正式部署或浏览器 QA。
- 最新 Brand Update：`artifacts/deploy-brand-update-20260825-15bfa38/3c3d954/brand-update-3c3d954.exe`，SHA-256 `E05D52515B8D49C8B21788F44C35B464585F34D40BC54EE0853724E737F81CD3`；canonical 输出为 `artifacts/deploy-brand-update-20260826-3c3d954`。
- 正式 `http://192.168.50.210:8010/` 最后回读仍缺少 `evidence-grounded-gameplay-review-v1`，served JS 也缺少 `当前环节缺少已确认的玩家操作` 与 `当前环节尚未满足确认条件`，所以 `3c3d954` 尚未证明落地。
- 杂货铺任务 `9e982100a25843f78c44793df15d3237` 最后观察为 Interaction Review revision 38、7/7 stage 已确认、Gameplay revision 32、generation completed；该数据会继续变化，新会话必须重新回读。
- RDP 3389 可达，SMB 445 与 WinRM 5985 不可达；现有 mstsc 窗口的自动截图因 Windows 接口不支持失败，Chrome 自动化因无法确认当前 URL 被安全门禁停止。不得据此声称已完成正式浏览器 QA。
- 桌面 `苏丹的游戏` 素材为 18 张 JPG 与 1 个 MP4；正式全流程尚未开始，必须先完成最新部署验证。


## 2026-08-26 11:30 生成循环修复候选（覆盖下方同类旧状态）

- 本地分支 `codex/planner-decision-card` 的应用候选为 `7c7bb07112d31a584e78b5b3e46a9a6b64f5f017`，父提交 `4823222`。GitHub 与 SVN 尚待本轮同步；正式 8010 仍是上一版，不能宣称上线。
- `4823222` 保存完整 last-valid Gameplay Model、全链 job ownership fail-closed，并提供停服/备份/revision/scopes/SHA 锁定的离线恢复工具。《一路狂飙》accepted revision 370、8 章快照 SHA-256 为 `8597D662BE2857C501F45456FA460278C9201C4080836019B6A86EF641E7BBC1`，dry-run 已过，正式恢复未执行。
- `7c7bb07` 把无证据参数/公式转 Planner Decision，分离 review-entry 与 delivery quality；同时为分章生成增加项目隔离的安全检查点，API/网络中断后从未完成章续跑，语义失败清理坏检查点。
- 杂货铺正式任务 `9e982100a25843f78c44793df15d3237` 的旧版循环已实证：所有已生成章都删除无依据数值/公式；最近一次在 11/13 后被上游模型/API异常打断并丢弃进度。部署前禁止继续盲目重试。
- 当前完整基线：Python `1640 passed / 0 failed / 3 warnings`，JavaScript `490 passed / 0 failed`。正式 QA 仍待新版 Brand Update。

## 2026-08-25 19:16 交接权威基线（覆盖下方同类旧状态）

- 仓库为 `C:\Users\momoca\Documents\ai策划案\prdgenerator_decision_card`，分支 `codex/planner-decision-card`。应用候选提交与 GitHub 同名分支均为 `9af07bc6fc9cb24b728c75566cc51cbd2bceefde`。
- SVN `AI/trunk/ai_gamedesigntool` 已同步到 revision `113`，其 release manifest 的 `sourceCommit` 为 `9af07bc6fc9cb24b728c75566cc51cbd2bceefde`。
- 正式地址 `http://192.168.50.210:8010/` 尚未部署该候选。最后一次只读回读仍为 `style ux30 / review-workspace review24 / gameplay-review.css gameplay19 / gameplay-review.js gameplay24 / flow-review review16 / backend ux98`。不得把 Git/SVN 已同步描述成正式上线。
- 待运行部署包：`artifacts/deploy-brand-update-20260825-9af07bc/brand-update-9af07bc.exe`；RDP 重定向路径为 `\\tsclient\X\brand-update-9af07bc.exe`；SHA-256 为 `2AFCC179DBCC127FC11A797750E6AE8D118B0974F28E5B9572235D40340969DA`。包内 manifest 仍以应用候选 `9af07bc` 为来源。
- 当前完整自动化基线：Python `1622 passed / 0 failed / 4 warnings`，JavaScript `490 passed / 0 failed`，缓存合同 `1 passed`。浏览器 QA 证据位于 `artifacts/qa-interaction-decision-and-rule-clarity-20260825/`。
- 通用修复包括：未知交互改为策划决策卡；静态/数值证据不再冒充 Gameplay Flow；连续自然语言 AI 玩法理解；字符串不再逐字渲染；“编辑规则”打开真实可见编辑器；空配置模板不再伪造正文；P7 右栏可滚动；“处理未完成项”会触发服务端语言/颗粒度修复与确认后的详细内容重生成。
- 这些修复已覆盖公共实现与自动回归，但正式 8010 的跨项目桌面验收尚未执行。验收矩阵固定包括《一路狂飙》、杂货铺、角色创建和隔离全新项目，并检查 P1–P7、保存、重试、刷新/返回、图片、编辑、导出、URL、控制台与失败请求。
- 当前架构仍有中高 AI-grown 技术债：legacy/new/migrated/preview 多表示并存，P4–P7 状态门禁分散，CSS cascade 与部署资产可能部分更新。下一阶段是稳定化和路径收敛；测试通过不能被写成“架构已干净”。Phase 3 保持暂停。

## 2026-08-25 正式部署增量

- 正式站点已部署 Git `85422536`：截图序列导入使用原子 manifest 与 frames/structures/source_images 三件套恢复；该规则覆盖所有项目与任务 ID。正式环境 3 个不同任务各恢复 14 张截图并进入可操作的 API Key 重试状态，当前 0 个 queued/processing 卡死任务。
- `data/planner_knowledge/system-lessons-v1.json` 已纳入部署包，`/api/health` 同时校验 `interrupted-screenshot-import-recovery-v1` 和 `systemLessons=true`；更新器改为按 netstat 找到真实 8010 listener 并结束该 PID，不再误碰无关的 ReleasePlatform:8000 服务。
- 本轮完整基线为 Python `1591 passed / 0 failed / 3 warnings`、JavaScript `477 passed / 0 failed`；正式恢复任务 14/14 图片与版本化静态资源均 HTTP 200。
- 正式站点已部署 Git `18e0eba`，资源标记为 `ux98 / review24 / gameplay19`；GitHub 同名分支已核对同 SHA，SVN 应用同步为 revision `102`。
- Gameplay 异步生成新增 5 分钟总时限、generation ID compare-and-set、迟到结果丢弃、阶段/百分比/已等待时间/自动停止说明。角色创建的历史 stuck running 在服务重启后已转为可重试失败，确定性 skeleton 保留；《一路狂飙》8 章 ready 内容未受影响。
- 本轮完整回归为 Python `1586 passed / 0 failed / 3 warnings`、JavaScript `477 passed / 0 failed`。正式浏览器验证角色恢复页和《一路狂飙》P1→P2→P1，page error 0、失败请求 0；桌面截图无文字重叠或横向溢出。

## 2026-08-24 当前权威基线

- 仓库：`C:\Users\momoca\Documents\ai策划案\prdgenerator_decision_card`
- 分支：`codex/planner-decision-card`
- 会话收口前 Git/GitHub HEAD：`a6d2f9072bb8bc50b2b9bc613b0aa15ddce39bfe`；本次 handoff commit 完成后以 `git rev-parse HEAD` 与远端同名分支实际 SHA 为准。
- GitHub：`https://github.com/oarngeftansy/yanling-jingtong.git`，同名分支在会话收口前与本地 `0/0`。
- 最近完整 Python 基线：`1561 passed / 0 failed / 3 warnings`。本次仅更新记忆、交接和审计文件，不改变 Rule/Projection/Renderer 运行逻辑。
- Phase 1、Phase 2 与 Feedback Closure 已完成；核心权威链为 `Evidence → AtomicFact → AtomicRule/RuleCandidate → Intent → Canonical Owner → Schema/Dependency Closure → Guard → Review → PublicationProjection → Final`。
- 12 条历史 Planner Feedback 已固化为 11 条项目无关 System Lessons：`data/planner_knowledge/system-lessons-v1.json`；运行时入口为 `backend/system_lesson_registry.py`；映射审计为 `artifacts/system-lessons-2026-08-24/FEEDBACK-SYSTEM-LESSON-MATRIX.md`。当前 `lessonCount=11`、`feedbackCount=12`、`verifiedLessonCount=11`、`danglingPolicyCount=0`、`missingTestCount=0`。

## 2026-08-24 《一路狂飙》Final Delivery Candidate v3

- 当前飞书文档：`https://hjjxo8h8vu.feishu.cn/docx/IjKndZqszoj9kgxma0icsDOjnfe`，远端 revision `59`。
- 当前顶层顺序：玩法概述 → 单局流程 → 核心战斗 → 局内成长 → 关卡推进。
- 远端回读指标：47 个标题、71 个列表项、9 张原生表格、5 张玩法图；6 个具体策划决策项；Victory full definition 仅 1 个；内部 ID 为 0。
- Final 污染核验：unsupported formula/probability/weight、guarantee、hidden priority、technical gap、template question、duplicate full definition、entity scope leakage、UE/竞品/Presentation-only board 均为 0。
- 已恢复载具栏位与局内重置、武器获取与攻击模式、三选一暂停/恢复/结果、独立抽取、普通怪/首领流程、离散经验值、计时、胜败结算、统计及退出/重试。
- 恢复文本载荷位于 `artifacts/yilu-kuangbiao-feishu-v3-2026-08-24/restore-*.md` 与 `safe-table-*.md`；它们记录远端修订，不改变结构化 Rule Authority。

## 2026-08-24 GitHub / SVN 发布状态

- GitHub 会话收口前已推送到 `a6d2f90`，本地与远端同名分支一致。
- SVN 项目地址：`https://192.168.50.30/svn/AI/trunk/ai_gamedesigntool`。
- SVN 初始可复现发布为 revision `80`，来源 commit `a6d2f90`；发布包包含 Git HEAD 与白名单依赖根 `runtime_packages_server`、`runtime_packages_pytest`，`secretFindingCount=0`。
- Windows 环境若无 `svn.exe`，后续增量同步必须使用受控 working copy/Tortoise 流程；不得用 Import 覆盖已有目录，也不得持久化 SVN 密码。

## 2026-08-21 Phase 2 Temporal Probe 生产集成纵切片

- 生产编排入口为 `backend/temporal_probe_orchestration.py::orchestrate_targeted_temporal_probes`，由 `backend/server.py::_generate_gameplay_review` 在 v2 model build 后、保存前调用。
- 编排服务复用 `build_targeted_probe_requests`、`build_requirement_temporal_index`、`extract_and_structure`、`build_temporal_entity_track_candidate`、`run_targeted_temporal_probe` 和 `add_targeted_temporal_probe_result`。
- 显式 Gap 声明合同支持现有 schema `status=open` 以及旧领域 `status=unresolved`；completed/exhausted 在同 `sourceEvidenceRevision` 下不重跑，新 revision 继承 attempt count 并允许再执行。
- 生产集成测试位于 `tests/test_temporal_probe_production_integration.py`，覆盖 T1–T6；聚焦回归基线为 70 passed。

## 2026-08-21 Phase 2 Temporal Evidence 实现基线

- `backend/requirement_temporal_probe.py` 是 TargetedTemporalProbe 深模块，包含 Gap eligibility、candidate window、identity 分级、reference frame、Persistent State、Lifecycle Boundary、Repeated Event、Probe exhaustion 与 coverage。
- `AtomicFact` 已加入 temporal pattern、reference frame、persistence、probe/video/window/track lineage、identity status 与 candidate entity。
- `rule_normalizer.py` 将 `temporalEvidence` 适配到现有 Rule Intelligence Projection；Temporal RuleCandidate 不形成第二套 Rule 链。
- `add_targeted_temporal_probe_result` 以 revisioned、undoable 方式保存 Probe 结果；现有 `review_rule` 批准 Temporal Candidate。
- Phase 2 完整回归基线为 `1468 passed / 0 failed / 3 warnings`。

## 2026-08-21 Planning-only Board Policy

- `compile_gve16_whiteboards`、`compile_gve16_delivery_whiteboards`、`compile_accepted_delivery_whiteboards` 当前统一只返回 `planning / 策划草图`。
- P2 工作流已移除 `ue_flow` 路由；历史 `ui=ue_flow` 深链兼容重定向至 `interaction_preview`。最后 Stage 确认状态为 `preview_pending`，不再写 UE fingerprint/confirmation gate。
- Review Preview、Completion Snapshot、P7、accepted preview API 与 Feishu Render 不再要求或输出 competitor/ue/ux 画板；legacy UE/competitor embed anchor 会被忽略，planning anchor 仍必须唯一存在。
- 历史 UE 编译器、确认 API 和竞品素材解析暂时保留为兼容代码，但当前主链不调用、不展示、也不作为门禁。

## 2026-08-21 Cross-Project Mechanic Benchmark 与只读适配层

- 跨项目迁移夹具现包含 29 个 system/gameplay/mixed 稀疏证据案例；质量评估入口为 `evaluate_migration_benchmark`，汇总 Pattern/Responsibility Recall、Precision、High-value Gap、Noise、Implementation Leakage 和 genre-only activation，并保留逐案例明细。
- 只读主链适配入口为 `build_mechanic_intelligence_projection`。它只消费 Evidence、Fact 及 Approved Rule 的显式 existence signal 和满足关系；Review Proposal、genre、Planning 与 Final 内容不参与激活。
- 适配层只输出 Detected Mechanic、Active Responsibility、Project Mechanic Graph、candidate-only Review Candidate、`contentAuthority=none` Planning Hint 和完整性审计；不创建 Approved Rule，不修改 Planning，不产生 Final Publication 内容。
- 聚焦回归入口为 `tests/test_mechanic_knowledge_graph.py`、`tests/test_cross_project_mechanic_benchmark.py`、`tests/test_mechanic_pipeline_adapter.py`。
- Responsibility activation contract 已支持通用 `anyApprovedRuleTags` 与 `anyRelationTypes`；多类 clause 同时出现时必须全部满足，且输出 `activationRuleIds` / `activationRelationTypes`。Unreviewed Rule 永不激活职责。
- Responsibility 的执行覆盖维度保存在 JSON `planningDimensions`，引擎只做通用汇总。29 案例当前夹具内指标为 Pattern/Responsibility Recall 与 Precision 1.0、High-value Gap 1.0、Noise/Implementation Leakage 0；该结果只证明当前迁移夹具契约，不代表真实未知项目已达到同等质量。
- 图校验现强制 contract Signal 引用存在、每个 L3 Pattern 有 L2 `contains` 父边、每个 L4 Responsibility 有 `may_activate` 入边，并要求每个 Pattern 至少连接一个 Entity/Resource/State/Event/Flow shared concept；新增 Pattern 已补齐完整层级与组合边。

## 2026-08-20 Cross-Project Mechanic Intelligence 当前实现

- 当前分支为 `codex/planner-decision-card`；本次交接前代码 HEAD 为 `c159e25`，远端 `origin/codex/planner-decision-card` 仍停在 `91cb47a`，本地领先 45 个提交。
- 已确认并开始落地“声明式 JSON 知识图谱 + 通用图引擎”。设计规格：`docs/superpowers/specs/2026-08-20-cross-project-mechanic-intelligence-design.md`；实施计划：`docs/superpowers/plans/2026-08-20-cross-project-mechanic-intelligence.md`；ADR：`docs/adr/0001-declarative-mechanic-knowledge-graph.md`。
- 图数据入口：`data/planner_knowledge/mechanic-knowledge-graph-v1.json`。当前首批 Pattern 为 `dash`、`lock_on`、`melee_combo`、`parry`、`boss_encounter`、`boss_phase`、`shop`、`shop_refresh`、`random_draw`、`candidate_selection`，并声明共享 Entity / Resource / State / Event / Flow 概念。
- 通用引擎入口：`backend/mechanic_knowledge_graph.py`。已提供 `validate_mechanic_graph`、`load_mechanic_graph`、`MechanicKnowledgeGraph.pattern`、`responsibilities_for`、`detect_mechanics`、`activate_responsibilities`、`compose_project_graph`、`discover_missing_requirements`。
- 已实现：拒绝悬空边和项目答案；品类标签不激活 Pattern；一个证据流可同时检出多个 Pattern；职责按自身信号动态激活；Pattern 通过共享概念组成项目图；仅对 active 且未被 Approved Rule 满足的职责产生 Missing Requirement。
- 聚焦测试：`tests/test_mechanic_knowledge_graph.py`，交接前为 7 个用例通过。运行入口：设置 `PYTHONPATH=<repo>;<repo>\runtime_packages_pytest` 后执行 `C:\Users\momoca\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest tests/test_mechanic_knowledge_graph.py -q -p no:cacheprovider --basetemp .test-tmp/mechanic-handoff`。
- 尚未完成：完整 Pattern/Responsibility 声明式扩充；不少于 25 个系统型、玩法型、混合型迁移案例；迁移指标与负例；接入现有 Evidence/Fact/Rule/Review/Planning Hierarchy/Publication 流水线；相关回归与分批提交。
- 《一路狂飙》飞书 UE 画板最近一次层级修复提交为 `5e8dc6a`；远端 UE token 为 `AdZtw3Qx3hIiPPbKFGCcmVXgn5c`，文档为 `https://hjjxo8h8vu.feishu.cn/docx/PYf7dBtgdodX9txDCpTctE7inGd`，9 个页面说明在远端导出中可见。此事实不代表正文 Alignment 已完成。
- `http://192.168.50.210:8010/` 已于 2026-08-24 完成桌面端发布：P1–P7 正式交互链、按钮与跳转、竖版参考图、机制审核页和已接受策划预览页均通过；3 个正式页面 HTTP 200、控制台 0 错误、失败请求 0。移动端不在本轮范围。
- 工作区保留用户/历史修改：`scripts/publish_current_alignment_to_feishu.py` 有未提交修改，另有大量未跟踪测试目录、runtime packages、截图与部署产物；任何提交都必须精确暂存，禁止 `git add -A`。

## 2026-08-19 Alignment Closure 终态

- `alignment-closure-matrix.json` 完整覆盖 186 个原子 ID 与 9 个跨交付 ID，195/195 均已获得允许终态：141 fixed、24 approved_design、20 parameter_resolved、5 scope_confirmed_not_applicable、2 evidence_resolved、3 blocked_by_missing_source；开放项为 0。
- Final 判定为 `=` 186、`×` 0、`△` 3、`U` 0；原始非 `=` 为 109。三个 `△` 只对应两个真实外部入口：W-18/P6-06 缺正式武器词条配置导出（稳定表/字段/版本），L-13 缺双倍奖励商业策略决策。
- Final、UE、策划草图、P5、P6、Closure Matrix、Final Crosswalk、A–J 与简版差异总览均已重生成。A–J 为 A94、B94、C94、D96、E94、F92、G94、H95、I99、J99；A–H 平均 94.1。
- UE sidecar 已为 reviewed，包含 14 条具名、带真实触发控件或 system trigger 的 transition，以及循环 entry/exit。UE-15 已远端发布并通过 preview + raw-node 双验收：策划画板 65 节点、7 Section、14 截图、19 straight 连线；文档为 `https://hjjxo8h8vu.feishu.cn/docx/PYf7dBtgdodX9txDCpTctE7inGd`。
- L-06/P5-09 经 185–202 秒连续视频 Probe 关闭：Boss 死亡后继续清场，剩余怪物清空后进入成功结算；未外推底层事件名或检测频率。
- 战斗等级、三选一、独立抽取、武器/怪物/伤害、关卡/奖励/失败均已形成项目自有执行契约，并投影到需要消费它们的真实交付面。
- 完成前回归必须使用 workspace `--basetemp`；默认 Windows Temp 可能权限失败，不得误报为业务失败。
- Closure 全量回归基线：Python 186 passed、JavaScript 452 passed。

## 2026-08-18 当前交接状态

- 新会话统一入口为 `docs/handoff/CURRENT_SESSION_HANDOFF.md`。
- 最新动态层级只读审计位于 `artifacts/current-system-hierarchy-audit-2026-08-18/`；状态为待用户确认，尚未写入网页任务。
- 固定六章网页迁移已停止且未执行；`job.json` 未被本轮修改。
- 当前安全回退提交为 `b5589ed feat: reconstruct GVE16 planning delivery depth`。
- 旧工作区仍有三项未提交历史修改：`scripts/migrate_current_job_prd_depth.py`、`tests/test_current_job_prd_depth_migration.py`、`tests/js/gameplay-workspace.test.js`；它们不属于当前安全交接提交。
- 当前下一步只有一个：用户确认 System Hierarchy Audit 后，再设计动态网页目录迁移；不得直接硬编码《一路狂飙》章节。

## 2026-08-12 P6 参数审核状态修复

- 正式任务共有7张活动业务表。诊断前3张 reviewed、4张 stale；真实接口和浏览器目标 ID 验证后，“武器解锁与养成”“武器词条”已按用户通过意图写为 reviewed，当前为5/7。
- P6 业务表进度改为“整表待审核/整表已通过”，不再把任意第5列误读成逐行审核状态。
- 顶部汇总和进入 P7 的门禁统一检查全部活动表；剩余“怪物战斗属性”“关卡波次与刷怪配置结构”保留待用户人工审核。
- P6 现以 `selectedTableId` 保存当前表；通过本节后的模型重绘和整页刷新均保持原表，不再复位第一张。
- 当前正式任务已由用户操作达到7/7张表 reviewed；进入 P7 按钮现已开放，仍需用户确认阶段6验收后才能推进阶段7。

## 2026-08-12 P5 图解审核修复

- 正式任务 `8312a91c89e144e6a59f81b982f14c06` 当前保留6张策划语义图，ID 为 `GDI-101` 至 `GDI-106`，均为 reviewed；最新审核模型 revision 为219。
- 图解已标记为 curated，正文变化时通用生成器不得覆盖。过期更新需原位保留 ID 与章节绑定，并重新进入人工审核。
- P5 左侧章节导航现区分待审核、需更新、已通过；章节切换会同步更新中间图解和右侧审核对象。
- 当前真实页面显示“已生成6张图解，6已通过，0待审核”，P6 参数审核可进入并可刷新恢复。

## 2026-08-12 正式策划表交付链路

- 当前任务 `8312a91c89e144e6a59f81b982f14c06` 的玩法审核模型 revision 为 `174`。
- 当前正式业务表为：载具等级、载具栏位与特权、武器基础属性、武器解锁与养成、武器词条、怪物战斗属性、关卡波次与刷怪配置结构。
- `js/final-document-preview.js` 已停止把章节 `parameters/parameterSchema` 自动渲染成通用参数表；`backend/gameplay_render.py` 已停止在飞书正文输出通用参数表和集中参数目录。两端仍保留这些数据供审核、编辑和门禁使用。
- `backend/granularity_audit.py` 在审计版本 4 下会以 `GRANULARITY_GENERIC_CONFIGURATION_TABLE` 阻断万能五列表；正式浏览器验收还同时检查三套历史通用表头。
- 表格自检证据位于 `artifacts/stage5-planner-table-acceptance/`；真实浏览器结果为颗粒度、语言、同源三项通过，无浏览器错误，无表格横向溢出。当前仍有 5 项真实决策卡，因此完成度保持 91%，导出继续阻断。

## 绑定样例

- 玩法执行文档样例：`https://hjjxo8h8vu.feishu.cn/wiki/DzFuwF9PYip7X0kEjdVcY6OGnif`
- 交互、策划草图与玩法表达样例：`https://hjjxo8h8vu.feishu.cn/wiki/ZsTVw7lTEi9rErknL9bcRfFunei`
- 用户明确要求：后续实现持续对齐以上两份文档；如果无法读取或记忆丢失，必须明确告知用户并请其重新提供内容，不能凭印象声称已经对齐。

## 2026-08-12 当前阶段5事实

- 正式任务 `8312a91c89e144e6a59f81b982f14c06`：玩法 revision 170，交互 revision 31。
- 仍有 5 项真实策划决策，P7 为 91%，导出阻断；不得擅自选择或把推荐写成结论。
- 已增加载具、武器/词条、怪物/刷怪的正文属性分组，并保留后续集中查配表。
- 颗粒度门禁包含 `attributeNarrative`；语言门禁包含 `LANGUAGE_REVIEW_META` 并检查图解说明。
- P7 未完成入口显示真实数量并精准跳转首张未处理卡；决策选项为左侧紧凑圆圈和单行文字。
- 阶段5尚未获得用户最终验收；结束前仍需逐条核对飞书反馈表中除“验收无误”外的全部问题。

## 当前交付合同

- 分支 `codex/planner-decision-card` 在提交 `816f8d5` 之后开始实现全局决策卡。第一阶段新增 `decisionCards` 玩法章节契约及 `resolve_decision_card` / `skip_decision_card` 操作；P4 已不再把裸 `unknowns` 渲染成策划决策。
- 项目已新增 `skills/executing-staged-acceptance`，作为阶段 1–7 的统一验收门禁；阶段 1 的决策卡 TC1–TC9 保存在该 Skill 的参考文件中。用户已于 2026-08-11 明确确认阶段 1 和阶段 2 验收通过；当前进入阶段 3“飞书样例颗粒度与逐句来源门禁”的实现阶段。

- 工作流程：上传并确认素材顺序 → 识别并确认玩法目录 → 确认交互流程 → 单步检查页面反馈 → 预览交互交付物 → 审核玩法规则 → 审核必要图解 → 预览并发布完整文档。
- 最终文档包含交互策划草图、竞品参考和玩法正文；玩法和交互在同一份文档内。
- 网页预览与飞书原生白板共同消费 `backend/planning_board_model.py` 的共享结构；2026-08-04 用户确认将其从系统树整体替换为 GVE16 样例的页面规格图集。
- 当前交互画板只交付两个原生白板：`策划草图`、`竞品参考`。
- 玩法目录和章节摘要使用玩法抽象；截图级交互描述保留为证据。

## 当前本地任务

- 当前正在回归的任务 ID：`4180cd72eeaa4819be41db50bb4c5011`；局域网地址：`http://192.168.50.67:8000/?job=4180cd72eeaa4819be41db50bb4c5011`。
- 旧任务 `183261b4137e40a59596b3afcaad4f18` 的结构与数量仍只作为历史实例，不是当前任务或其他素材的固定模板。

- 当前任务 ID：`183261b4137e40a59596b3afcaad4f18`。
- 当前任务的已识别系统仅作为本任务实例：`战斗与关卡`、`局内成长`。
- 当前任务局域网地址：`http://192.168.50.67:8000/?job=183261b4137e40a59596b3afcaad4f18`。
- 本地服务从项目根目录启动，源码路径必须优先于运行依赖路径，防止网页继续加载旧代码。

## 技术验证基线

- 2026-08-04：完整 Python 回归为 530 项通过，前端 Node 回归为 200 项通过。
- 2026-08-04：当前任务的最新策划草图实测为 2 个系统、3 个模块、6 张有效规则卡、15 张原图、0 条黄色注记、0 处“未知待确认”；无有效规则的重复环节并入相邻有效环节，原图不丢失。
- 以上数量只用于当前任务回归，不是其他素材的固定验收数量。
- 2026-08-04：GVE16 页面规格式策划草图改造完成最终回归，Python 605 项通过、前端 JavaScript 206 项通过；最终整分支审查无 Critical、Important 或 Minor 问题，结论为可合并。
- 当前任务实时页面规格模型为 7 个页面、15 张原始截图、3 条已确认页面关系；数量仅用于当前任务实测，不是其他素材模板。
- 当前任务的玩法目录已经由策划确认，共 9 个章节，按“战斗与关卡 / 局内成长”两组组织；不得再恢复旧的“营救 NPC”草稿，也不得替用户确认仍处于草稿状态的具体章节。
- 当前任务 F0007、F0008 首次逐帧识别失败的直接原因是视觉模型返回 JSON 缺少逗号，不是没有配置视觉模型。系统现已对无效 JSON 自动重试一次，并提供“重新识别这张图”，截图任务不再要求必须存在源视频。
- 策划草图的页面说明必须把“页面用途”写成页面级目标；战斗受击、血量变化、伤害数字等属于功能反馈或原始证据，不能冒充页面用途。页面元素说明不得出现鼠标、时间戳、残缺括号、省略号或截图照抄式数值。

## 2026-08-06 当前任务修复状态

- 任务 `4180cd72eeaa4819be41db50bb4c5011` 当前包含 18 个玩法章节；目录错误摘要已修正并重新确认。
- 当前自动图解共 17 张，覆盖空间关系、公式、状态流程和效果链；玩法表格已重新生成，缺少明确依据的字段不再标为“当前素材”。
- 完整回归基线：Python 677 项、前端 249 项全部通过。

## 2026-08-06 主策自动修复与模型配置续跑

- 当前任务 `4180cd72eeaa4819be41db50bb4c5011` 的玩法细节状态为 `detail_generation_pending`；这不是完成态，生成和最终预览必须继续补全。
- 目录确认已传递当前视觉模型配置；最终预览可从待生成状态自动续跑；已确认目录不得返回假的 100% 完成。
- 浏览器未保存密钥时，前端不提交空请求，而是展开可见的模型 API 设置，保存后返回原工作台。
- 回归基线：Python `682 passed`；前端 `250 passed`；本地服务 HTTP 200。

## 2026-08-06 表格与图例规则

- 2026-08-06：任务 `4180cd72eeaa4819be41db50bb4c5011` 的旧图解经结构检查后，16 张仅包含标题与一段说明、1 张为纯公式，均已转为“无图解”；玩法正文中的公式信息与玩法表格继续保留。
- 玩法参数可能由模型返回为列表或字典，两种结构都必须读取，禁止因结构差异漏掉生命、攻击、暴击、元素属性、成本、概率等字段。
- 除单章参数表外，只要素材包含成组属性或计算关系，就必须自动生成“属性分类与投放来源”汇总表和“属性与计算关系图例”；分类必须依据当前素材动态建立，不能套用固定游戏模板。
- 属性行优先记录属性分类、属性名、策划说明、投放来源，并保留类型、单位、默认值、范围、配置来源与取整方式供单章审核；没有素材或参考文档支持时不得编造数值。
- 当前任务已生成 22 行属性汇总及 3 行计算图例；回归基线更新为 Python `684 passed`、前端 `250 passed`。
## 2026-08-06 截图完整性与互斥分支验收

- 当前任务 `4180cd72eeaa4819be41db50bb4c5011` 已完成旧数据迁移：15/15 张截图全部归属页面，其中 7 张独立页面、8 张补充画面、0 张静默遗漏。
- 当前素材没有完全重复截图，也没有真实多分支，因此重复画面数与互斥分支组数均为 0；系统能力仍由自动测试覆盖。
- 7 张截图识别出共 12 项等级、武器槽、资源或状态次级信息。
- 本批最终回归基线：Python 689 项、前端 JavaScript 256 项；局域网服务端口 8000，任务链接保持不变。

## 2026-08-06 当前任务路由恢复

- 任务 `4180cd72eeaa4819be41db50bb4c5011` 的数据未丢失；当前仍为 7/7 个已确认交互环节、18 个玩法章节。旧质量字段导致的 `NO_QUALIFIED_STAGE` 误判已修复，任务重新进入正式工作台。
- 回归基线更新为 Python `692 passed`、前端 JavaScript `256 passed`；局域网服务进程 PID 8252，端口 8000。
## 阶段 6 飞书交付当前事实（2026-08-12）

- 阶段 6 尚未完成；S6-TC03 真实飞书导出未通过。
- 当前正式飞书文档是中途写入形成的污染版本，排布不等同 P7 预览，不可交付。
- 正确策划图解为恢复后的 GDI-101～GDI-106；其中 GDI-105 必须是含首领触发、战斗与胜负分支的语义流程，不能是属性列表。
- 下一次发布的前置条件：P7 与飞书使用同一有序交付清单；用户先确认本地章节、图文和表格排布；随后完成远端全文与画板回读核验。
# 2026-08-17 Phase 5 EntityBuilder

- 公共构建入口为 `build_entity_graph(chapters, approved_rules, reviewed_gaps, entity_declarations)`，确定性输出 Entity、核心关系、Presentation 单向引用和污染审计。
- 《一路狂飙》Phase 5 审计产物位于 `artifacts/planning-content-phase5-2026-08-17/`；源 job 保持 failed 原状态且 SHA256 为 `e0e57e4436552597ab64c2bc3f61463839ac738a72b314072d3ecec06e3d8da6`。

# 2026-08-17 Phase 5.1 Delivery Separation

- 公共接口为 `build_visual_blocks(...)` 与 `build_logic_only_delivery(...)`。
- Phase 5.1 独立产物位于 `artifacts/planning-content-phase5.1-2026-08-17/`，包含 Logic-only 正文、16 个 VisualBlock、六章对比、质量报告和 provenance；未写回 P7 或 UI。

# 2026-08-17 Phase 5.1 Alignment Baseline

- 新接口为 `load_gve16_alignment_corpus(...)`、`evaluate_granularity(...)`、`evaluate_target_alignment(...)`；实现完全独立于 legacy `document_quality_evaluator.py`。
- 当前真实 baseline 位于 `artifacts/planning-content-phase5.1-evaluation-2026-08-17/`：Paradigm Alignment 90.42，Execution Completeness 39.57，Hard Gates 全部通过，qualificationStatus=pending。
- 当前 minimum next-fix module 为 Gap；原因是 Paradigm 已超过80，而 Execution Completeness 的最大缺口来自开放 SchemaSlot Gap。尚未执行第二次独立完整生成和异项目盲测，因此不能 qualified。

# 2026-08-17 Phase 5.3 Mechanic Reconstruction

- 公共入口为 `load_mechanic_structure_corpus(...)`、`build_mechanic_models(...)` 和 `evaluate_mechanic_depth(...)`。
- 《一路狂飙》六机制只读产物位于 `artifacts/planning-content-phase5.3-2026-08-17/`；未修改 Rule、Gap、Entity Graph、Execution Document、P7、UI 或参数。
- 升级后的 Planning Reasoning 六章产物位于 `artifacts/planning-content-phase5.3-planning-reasoning-2026-08-17/`；29 个开放 Gap 全部定位到 `mechanicId + mechanismNode`，Planning Reasoning Depth 为 95.0，对 Execution Completeness 贡献固定为 0。
# 2026-08-17 Phase 5.3.1 Mechanic Graph

- GVE16 MechanicStructureCorpus v2 使用用户提供文本的 SHA-256 `89d105f7d4a2a46e66ca3ac1d13c6a9b4d1c6320fed0f0a70a2068b42feb91bf`，运行时只保存匿名节点/边/分支/生命周期/依赖/边界/参数承载 pattern，仍为 provisional 且 `contentAuthority=none`。
- 六章重校准产物位于 `artifacts/planning-content-phase5.3.1-2026-08-17/`；不改 Rule、Gap、Renderer、正文或 ParameterResolver。

# 2026-08-17 Phase 5.3.2 Semantic Grounding

- 六章 Rule Semantic Decomposition、Grounded Graph、GraphSemanticValidator 与 Effective Reconstruction Depth 产物位于 `artifacts/planning-content-phase5.3.2-2026-08-17/`。
- 本轮只读消费 15 条 Logic/Data Approved Rule，拆出 28 个语义分量；Presentation Rule 不进入机制图。关卡流程与结算没有可进入逻辑图的 Approved Rule，因此 Graph Grounding Quality 为 not_assessable、Effective Depth 为 0。

# 2026-08-17 Phase 5.4 Reasoning-aware Gap Expansion

- 六章只读 ReasoningGap、既有 Gap disposition 和 Gap Quality 产物位于 `artifacts/planning-content-phase5.4-2026-08-17/`。
- 关卡流程与结算因无 grounded node 不生成新 ReasoningGap；既有 Gap 仅标记 defer-until-grounded。Phase 5.4 不修改 Approved Gap/Rule、P4 或正文。

# 2026-08-17 Phase 5.4.1 Decision Worthiness

- 32 条 Phase 5.4 Candidate Gap 的 keep/suppress/defer 审计位于 `artifacts/planning-content-phase5.4.1-decision-worthiness-2026-08-17/`；本轮未生成 PlannerQuestion。
- DecisionWorthiness 只读消费 ReasoningGap、grounded graph、Approved Rule 与 Evidence，不修改任何上游权威数据或 P4。

# 2026-08-17 Phase 5.4.2 Planner Significance & Gap Routing

- 公共入口为 `route_gap_for_planner_significance(...)`、`route_candidate_gaps(...)` 与 `evaluate_planner_signal_to_noise(...)`。
- 32 条 Candidate Gap 的只读分流产物位于 `artifacts/planning-content-phase5.4.2-gap-routing-2026-08-17/`：10 条 Planner Review、7 条 ParameterNeed、2 条 EntityAttribute、8 条 Implementation Default、1 条 Evidence Answered、2 条 Upstream Conflict、2 条 Deferred。
- `RULE-246A8B1E9DF1` 的“沿预设路线自动行进”仅追溯到静态帧及生成式画面描述，不能排除玩家直接控制路线，已标记 upstream conflict 并路由 Rule Review；本阶段未修改该 Rule。

# 2026-08-17 Phase 5.4.3 Planner Decision Compression

- 公共入口为 `compress_planner_decisions(...)` 与 `evaluate_planner_decision_granularity(...)`。
- Phase 5.4.2 的 10 条 Planner Review Gap 被压缩为 3 个 PlannerDecision：词条入池规则、三选一随机规则、接触伤害方式；压缩率 70%。
- 候选为空/不足转 Configuration Validation，选择后恢复战斗转 Implementation Default；产物位于 `artifacts/planning-content-phase5.4.3-decision-compression-2026-08-17/`。

# 2026-08-17 Phase 5.4.3 Game Rule & Mechanic Reconstruction

- 公共入口为 `load_game_rule_corpus(...)`、`build_game_rule_models(...)` 与 `evaluate_game_mechanic_depth(...)`。
- 六章只读重建产物位于 `artifacts/planning-content-phase5.4.3-game-rule-reconstruction-2026-08-17/`；Game Mechanic Depth 为 13.43，Implementation Detail 14 条且对评分贡献为 0。
- “载具沿预设路线自动行进”因上游静态证据冲突从 confirmedRules 移至 rulesUnderReview；本阶段没有修改原 Rule。

# 2026-08-17 Phase 5.4.4 Mechanic Scope Inference

- 公共入口为 `infer_mechanic_scopes(...)`、`apply_mechanic_scope(...)` 与 `evaluate_scope_precision(...)`。
- 六章共审计 56 个 scope item：19 confirmed、6 strongly_implied、23 possible、7 unsupported、1 contradicted；只有前两类进入规则层。
- Scope Gate 将 35 个模板展开的 missingGameRules 收紧为 9 个；unsupported/template-only 实例化均为 0。6 个 Gameplay Parameter 保留在玩法层，接触伤害间隔作为 conditional Gameplay Parameter 延后。
- 产物位于 `artifacts/planning-content-phase5.4.4-mechanic-scope-2026-08-17/`；未修改 Rule/Approved Gap/P4/正文，未调用 ParameterResolver。

# 2026-08-17 Phase 5.4.5 External Game Design Skill Distillation

- 本地可搜索位置未发现用户所述安装副本的目标源文件；只读研究改用作者 GitHub 主仓库 10 份指定原始文件/角色视角，没有安装或执行外部 Skill。
- `data/calibration/external-game-design-corpus.json` 收录 34 个去重后的 exploration-only pattern：mechanic scope 4、game rule 7、system dependency 5、progression 3、randomization 3、economy 3、balance 5、parameter 4。
- 5 个 forward_design_only、7 个 implementation_only 与 8 个 reject pattern 只进入适配审计，不进入 Corpus。直接生成 missingGameRules、状态提升、数值默认或 genre 自动实例化均为 0。

# 2026-08-17 Phase 5.5 Game Rule Decision Reconstruction

- `GameRuleGroup` 是系统策划规则组织单位，不由 Graph Node、ReasoningGap 或单个参数直接决定章节颗粒度。
- 固定先经 MechanicScope Gate，再按稳定玩法主题聚合 Known Rule、Missing Game Rule、Gameplay Parameter、相关 Entity/System 与 lifecycle；possible／unsupported／contradicted 只进入 rejected dimensions。
- ExternalGameDesignCorpus 继续为 `contentAuthority=none`，只辅助分类，不创建规则组或事实。

# 2026-08-17 Phase 5.6 Gameplay Loop & Rule Chain Reconstruction

- `GameplayRuleChain` 以 Entry → Player Action → System Response → State Change → Progression Result → Exit/Next 串联 GameRuleGroup；主链只承载已确认或 strongly implied 玩法。
- possible／unsupported 不填主链；链路必要但无答案的位置用人类可理解的 Missing Link 表达，内部 semantic 仅保留追溯。
- Gameplay Parameter 必须挂到对应链节点；Implementation Detail 固定不进入链。

# 2026-08-17 Phase 5.7 Core Loop → System Rule Projection

- Core Gameplay Loop 固定为 overview-only；完整执行规则必须投影到唯一 Primary Owner，其他系统只保留 short reference。
- Missing Link 必须投影到已有系统或 Entity 的主定义章节；Parameter Carrier 保留 owner，但值、单位、来源与公式仍留待 ParameterResolver。
- Projected System Chapter 同时携带 RuleGroup 与来源 GameplayRuleChain，避免退回静态分类或复制整条 Loop。

# 2026-08-17 Phase 5.8 GVE16-native Rule Layout Reconstruction

- RuleLayoutPlan 不使用统一 ExecutionRuleSpec；栏目顺序由当前 Rule／Missing Link／Parameter 关系优先决定，再引用 GVE16 匿名同类机制布局。
- 少量内容直接 bullet，中等内容才生成语义子栏目；Missing 与 Parameter 嵌入自然规则位置，不建立统一待确认区或参数区。
- ExternalGameDesignCorpus 仍无布局覆盖权和内容权，只允许作为低优先级分类辅助。

# 2026-08-19 P0 End-to-End Publication Trace Audit

- 入口脚本：`scripts/generate_p0_publication_trace_audit.py`。
- 完整逐项追踪：`artifacts/p0-end-to-end-publication-trace-audit-2026-08-19/end-to-end-trace.json`。
- 审计汇总与定位数组：`artifacts/p0-end-to-end-publication-trace-audit-2026-08-19/p0-publication-trace-audit.json`。
- 人读版：`artifacts/p0-end-to-end-publication-trace-audit-2026-08-19/P0-END-TO-END-PUBLICATION-TRACE-AUDIT.md`。
- 远端语义快照：`artifacts/p0-end-to-end-publication-trace-audit-2026-08-19/remote-feishu-semantic-snapshot.json`。
- 审计脚本只读抓取飞书，不修改 Rule、Job、Renderer 或远端文档；工作区中尚未提交的 P5 renderer 修改明确排除在当前已发布状态之外。
