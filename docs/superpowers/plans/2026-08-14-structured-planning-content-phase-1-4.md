# Structured Planning Content Phase 1–4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将“AI 理解自然语言 → 自由生成策划案”改造成可审计的 `Evidence / Fact → ChapterSchema → Rule → Gap → ApprovedData → PlanningLanguageRenderer → FinalDocument` 主链路，使《一路狂飙》输出在不复制 GVE16 内容的前提下达到成熟执行策划文档的结构与写作范式。

**Architecture:** 保留现有八步产品流程与 P5“图解审核”语义。新任务以版本化结构化 ApprovedData 为唯一正文事实源；`plannerSections` 仅承担旧任务兼容。ChapterSchemaLibrary 决定章节应检查什么，PlanningLanguageRenderer 只把已审核 Rule 确定性地渲染为正文，不在导出阶段补事实、补规则或调用 LLM 自由续写。

**Tech Stack:** Python 3、标准库 `dataclasses` / `typing`、现有 Flask 服务与原生 JavaScript UI、pytest、现有 JSON job 持久化。

## Global Constraints

- 产品流程固定为：视频/截图 → AI理解 → 玩法目录 → 交互审核 → 交付物预览 → 规则审核 → 图解审核 → 参数审核 → 文档导出。
- “交付物预览”继续表示交互交付物预览与审核；P5 继续是图解审核，不改名、不改职责。
- Phase 1～4 仅打通 AI 理解、玩法目录、P4 规则审核与 P7 正文生成所需链路；不重构视频入口、EntityBuilder、ParameterResolver、图解/表格生成或整体 UI。
- `Rule.ruleType` 只允许 `logic | presentation | interaction | flow | numeric | config`；逻辑与表现必须在正文生成前拆分。
- Gap 只记录缺失问题与证据状态，不保存推测答案，不进入最终正文伪装成规则。
- 新任务 `contentModelVersion = 2`；旧任务不强制迁移，继续读取原有 `plannerSections`。允许显式、可回滚的单任务迁移，不做全历史批量迁移。
- GVE16 仅用于抽取组织方式、检查维度和语言模式；Schema、测试夹具和样例禁止出现其项目专属句子、字段、编号、数值或规则。
- 每个 Phase 独立执行 Red → Green → Refactor、自检、固定《一路狂飙》对比产物，然后停止等待验收。未验收不得进入下一 Phase。
- 当前未提交修改在任何实施阶段都必须保留；每次提交只暂存本阶段明确列出的文件。

## Phase 0：冻结 A 版基线（实施前置，不改变产品行为）

### 文件

- 新增 `scripts/freeze_planning_content_baseline.py`
- 新增 `tests/test_planning_content_baseline.py`
- 新增运行时产物目录 `artifacts/planning-content-baseline-2026-08-14/`（不提交素材正文时，仅提交指标 JSON 与脱敏说明）

### 数据输出

`baseline_metrics.json` 固定以下字段：

```json
{
  "jobId": "8312a91c89e144e6a59f81b982f14c06",
  "revision": 369,
  "chapterCount": 0,
  "bodySentenceCount": 0,
  "ruleCandidateCount": 0,
  "duplicateRate": 0.0,
  "fillerRate": 0.0,
  "mixedLogicPresentationRate": 0.0,
  "gapCount": 0,
  "qualityScores": {}
}
```

### TDD 与验收

1. 先写测试，证明对同一 job/revision 连续执行得到相同指标与稳定排序。
2. 实现只读扫描；禁止写回 `job.json`。
3. 运行：`python -m pytest tests/test_planning_content_baseline.py -q`
4. 生成并人工保存 A 版玩法目录、P4 数据、P7 正文和上述指标。
5. 提交建议：`test: freeze planning content baseline`

**验收闸门：** 基线产物可重复生成，且工作树除规划内文件外没有被修改。完成后才开始 Phase 1。

## Phase 1：ChapterSchemaLibrary + ChapterClassifier + ChapterNamingPolicy

### 保留、修改、新增、废弃

**保留：** `backend/analysis_service.py` 的证据提取入口、`backend/gameplay_analysis.py` 的素材分析调用、现有玩法目录 UI 和八步导航。

**新增：**

- `backend/planning_content_models.py`：`ChapterType`、`RuleType`、`SchemaSlotDefinition`、`ChapterSchema` 的版本化契约。
- `backend/chapter_schema_library.py`：Schema 注册、查找、版本检查和完整性校验；内置初始 Schema。
- `backend/chapter_classifier.py`：根据事实信号、现有 mechanism type 和标题候选给出 `chapterType`、置信度及理由。
- `backend/chapter_naming_policy.py`：在 System / ChapterType / MechanicVariant 已确定后生成稳定概念标题，并输出标题质量问题。
- `tests/test_chapter_schema_library.py`
- `tests/test_chapter_classifier.py`
- `tests/test_chapter_naming_policy.py`

**修改：**

- `backend/gameplay_analysis.py`：结构分析结果新增 `chapterType` 和 `classificationEvidence`，不再把自由标题当作章节类型。
- `backend/gameplay_directory.py`：先按分类后的 System / ChapterType / MechanicVariant 与 Schema 分组，再调用 ChapterNamingPolicy；目录节点持有 `schemaVersion`、`namingReason` 和标题质量结果。
- `backend/gameplay_review_model.py`：`MECHANISM_SCHEMAS` 变为兼容映射，内部读取 ChapterSchemaLibrary；移除新任务落入 `custom` 后绕过必填检查的路径。
- `tests/test_gameplay_analysis.py`
- `tests/test_gameplay_directory.py`
- `tests/test_gameplay_review_model.py`

**废弃但暂不删除：** `backend/gameplay_review_model.py` 内硬编码 tuple 型 `MECHANISM_SCHEMAS`。旧任务可经 adapter 使用，所有 `contentModelVersion = 2` 的目录必须走 Library。

### 新数据结构

```python
class ClassifiedChapter(TypedDict):
    chapterId: str
    title: str
    chapterType: ChapterType
    mechanicVariant: str | None
    schemaVersion: str
    confidence: float
    classificationEvidence: list[str]
    sourceFactIds: list[str]

class ChapterNamingInput(TypedDict):
    level: Literal[1, 2, 3]
    systemName: str
    objectName: str | None
    chapterType: ChapterType
    mechanicVariant: str | None
    userVisibleVariantName: str | None
    legacyTitle: str | None

class ChapterNamingResult(TypedDict):
    title: str
    namingReason: str
    source: Literal["system", "object", "stable_rule_category", "user_visible_variant"]
    titleSplit: bool
    qualityIssues: list[Literal[
        "too_long", "parallel_connectors", "multiple_actions", "sentence_like",
        "contains_result", "chapter_type_mismatch"
    ]]
```

### ChapterNamingPolicy

命名发生在分类之后，执行顺序固定为：`System → ChapterType → MechanicVariant → ChapterNamingPolicy → DirectoryEntry`。旧标题只能用于对比和识别对象名，不能继续作为自由摘要标题发布。

- 一级标题优先使用稳定系统名或玩家可识别对象名，例如“核心战斗”“武器”。
- 二、三级标题优先读取 ChapterType 的稳定规则类别映射：`movement=移动`、`attack=攻击`、`damage_death=受击及死亡`、`slot=栏位`、`unlock_progression=解锁与养成`、`randomization=随机`、`combat_calculation=战斗计算`、`presentation=战斗表现`、`settlement=结算`。
- 对象下存在多个独立职责时，以对象名作为父节点，以规则类别作为子节点；不得生成“武器解锁、攻击与词条成长”。
- mechanicVariant 默认不拼入标题。只有 `userVisibleVariantName` 有素材证据、属于玩家或团队稳定使用的玩法名时才可作为标题，例如“三选一”；内部 variant `three_choice`、`ranged`、`straight_line` 不直接翻译后拼接。
- 标题优先使用名词或短名词短语，不包含完整条件、动作链或结果描述。
- 默认禁止 `、`、`与`、`及` 连接多个职责。固定业务概念白名单初始仅包含“解锁与养成”“受击及死亡”；白名单按完整标题匹配，不能泛化为允许任意组合。
- 标题长度建议 2～8 个汉字，超过 12 个汉字产生 `too_long`；命名器不得为规避长度而截断正文摘要。
- 命中两个以上独立动作词，或包含“后/时/则/进入/生效/归集/刷新候选”等条件结果结构时，产生质量问题并拒绝作为正式标题。
- 标题与 ChapterType 稳定映射冲突时产生 `chapter_type_mismatch`，目录保持待审核状态，不回退自由生成。

标题质量检查是确定性规则，不调用 LLM。好标题建立知识树；规则解释全部进入正文。

### 迁移逻辑

- 新任务创建时写入 `contentModelVersion: 2`。
- 旧任务缺少该字段时按 v1 读取，不改写原数据。
- 显式迁移单个任务时，先保留 `legacyGameplayDirectory` 快照，再生成 v2 `classifiedChapters`；迁移失败回退 v1。
- 不能确定类型时使用 `unknown`，但 `unknown` 不是自定义逃生口：必须产生“章节类型待确认”阻塞项。

### TDD 顺序

1. `test_schema_registry_rejects_duplicate_type_and_version`
2. `test_core_and_conditional_slots_have_gap_policy_and_allowed_rule_type`
3. `test_conditional_and_presentation_slots_require_executable_predicate`
4. `test_derived_slot_requires_source_slots_and_derivation_rule`
5. `test_variant_overlay_resolves_without_copying_base_schema`
6. `test_classifier_maps_attack_signals_to_attack_without_title_keyword_dependency`
7. `test_classifier_returns_unknown_variant_instead_of_guessing_when_evidence_is_insufficient`
8. `test_v2_directory_has_no_custom_schema_escape`
9. `test_v1_job_keeps_legacy_directory_unchanged`
10. `test_naming_runs_after_system_type_and_variant_are_known`
11. `test_naming_uses_object_parent_and_stable_rule_category_children`
12. `test_naming_rejects_summary_style_parallel_action_titles`
13. `test_naming_allows_only_fixed_business_concept_whitelist`
14. `test_mechanic_variant_is_omitted_without_user_visible_name_evidence`
15. `test_directory_diff_reports_old_title_new_title_reason_and_split`
16. 实现最小分类、variant、命名与注册逻辑，再接入目录生成。

### 自检与验收

- 运行：`python -m pytest tests/test_chapter_schema_library.py tests/test_chapter_classifier.py tests/test_chapter_naming_policy.py tests/test_gameplay_analysis.py tests/test_gameplay_directory.py tests/test_gameplay_review_model.py -q`
- 对《一路狂飙》重新生成目录，输出 `phase-1-directory-diff.json`：每项必须包含 `oldTitle`、`newTitle`、`chapterType`、`mechanicVariant`、匹配 Schema、`classificationEvidence`、`namingReason`、`titleSplit`，并汇总 unknown 数量。
- 单独输出标题质量报告：标题长度、并列连接词数量、独立动作数量、完整句/结果描述命中项、ChapterType 一致性。
- 人工检查新目录使用“对象父节点 + 稳定规则类别子节点”，不再把正文多个行为压成同一标题。
- 人工检查没有因某个标题无法匹配而退回 custom。
- 盲测一个非载具、非 GVE16 的小游戏素材，分类结果不强行出现无证据模块。
- 提交建议：`feat: classify planning chapters with schema library`

**Phase 1 验收闸门：** 用户确认新旧目录对比与初始 Schema 范围。停止，不进入 Phase 2。

## Phase 2：AtomicFact → SchemaSlot → Rule，P4 改为可审核结构

### 新增文件

- `backend/atomic_fact_normalizer.py`：把分析结果规范为原子事实，保留证据引用，不生成正文。
- `backend/rule_normalizer.py`：将已落槽事实转换为 Rule。
- `backend/rule_separator.py`：把混合规则拆成逻辑、表现、交互、流程、数值、配置原子 Rule。
- `tests/test_atomic_fact_normalizer.py`
- `tests/test_rule_normalizer.py`
- `tests/test_rule_separator.py`

### 修改文件

- `backend/planning_content_models.py`：加入 AtomicFact、SchemaSlotState、Rule、ApprovedData。
- `backend/gameplay_analysis.py`：保留原始分析文本用于追溯，同时输出 `atomicFacts`；停止为 v2 调用 detail 自由正文作为事实源。
- `backend/gameplay_review_model.py`：按 ChapterSchema 建立 slots，并将 Rule 作为 P4 的审核单位。
- `backend/gameplay_review_service.py`：支持 Rule 的确认、驳回、修改和证据回看；确认动作生成不可变 review 记录。
- `backend/gameplay_rule_copy.py`：v2 不再创建作为正文来源的 `plannerSections`；只在 v1 adapter 中保留。
- `js/gameplay-review-client.js`：读取/提交 v2 Rule 审核数据。
- `js/gameplay-review.js`：在现有 P4 页面内展示规则类型、所属槽位、证据和审核状态；不改变导航与页面职责。
- `tests/test_gameplay_review_service.py`
- `tests/test_gameplay_rule_copy.py`

### 新数据结构

```python
class AtomicFact(TypedDict):
    factId: str
    subject: str
    predicate: str
    object: str
    qualifiers: dict[str, str | int | float | bool]
    evidenceIds: list[str]
    confidence: float
    reviewStatus: Literal["unreviewed", "confirmed", "rejected"]

class SchemaSlotState(TypedDict):
    chapterId: str
    slotId: str
    factIds: list[str]
    status: Literal["confirmed", "missing", "conflicted", "not_applicable"]

class Rule(TypedDict):
    ruleId: str
    semanticKey: str
    ownerChapterId: str
    definitionMode: Literal["primary", "reference"]
    ruleType: RuleType
    schemaSlot: str
    subject: str
    trigger: str | None
    conditions: list[str]
    behavior: str
    result: str | None
    stateChange: str | None
    exitCondition: str | None
    exception: str | None
    parameterRefs: list[str]
    evidenceIds: list[str]
    reviewStatus: Literal["unreviewed", "approved", "rejected", "needs_revision"]

class ApprovedData(TypedDict):
    contentModelVersion: Literal[2]
    schemaVersion: str
    chapters: list[ClassifiedChapter]
    facts: list[AtomicFact]
    slots: list[SchemaSlotState]
    rules: list[Rule]
    gaps: list[Gap]
    approvalRevision: int
```

### 强制拆分契约

- 一个 Rule 只能有一个 `ruleType`。
- 同一事实若同时包含扣血与刷新生命条，生成两个 Rule，共享 evidenceIds，但 semanticKey、slot 和 ruleType 独立。
- `logic` 不允许保存视觉、音效、动画或 UI 刷新行为；`presentation` 不允许保存数值结算与状态判定。
- 无法无损拆分时标记 `needs_revision`，不得自动批准。

### 迁移与兼容

- v1 `plannerSections` 只通过 `legacy_planner_sections_adapter()` 进入旧渲染器。
- v2 的 `plannerSections` 即使存在也不能被 P7 读取；测试需锁定该优先级。
- 可选的单任务迁移只从已确认内容生成候选 Rule，默认 `unreviewed`，不得自动批准。

### TDD 顺序

1. 原子事实必须保留至少一个 evidenceId；无证据事实不得进入 confirmed。
2. 混合“扣血 + 刷新生命条 + 伤害跳字”必须得到 1 条 logic 和 2 条 presentation。
3. 相同 evidence 可支持多条不同类型 Rule，但 Rule 均可独立审核。
4. P4 API 拒绝未知 ruleType、空 behavior 和不存在的 schemaSlot。
5. v2 job 不生成正文型 plannerSections；v1 job 行为不变。
6. P4 编辑不能丢失 semanticKey、ownerChapterId、evidenceIds。

### 自检与验收

- 运行：`python -m pytest tests/test_atomic_fact_normalizer.py tests/test_rule_normalizer.py tests/test_rule_separator.py tests/test_gameplay_review_service.py tests/test_gameplay_rule_copy.py -q`
- 对《一路狂飙》输出 `phase-2-p4-audit.json`：每章 facts、slots、rules、ruleType、证据、审核状态，以及所有拆分前后映射。
- 截取 P4 独立截图，证明规则按类型和槽位审核；不要求此阶段语言已达到最终水平。
- 提交建议：`feat: review atomic planning rules in p4`

**Phase 2 验收闸门：** 用户确认自然语言候选已变成可追溯、可拆分、可单条审核的 Rule。停止，不进入 Phase 3。

## Phase 3：确定性 GapAnalyzer

### 新增文件

- `backend/gap_analyzer.py`
- `tests/test_gap_analyzer.py`

### 修改文件

- `backend/planning_content_models.py`：加入 Gap。
- `backend/gameplay_review_model.py`：构建 P4 模型时执行 `required schema slots - confirmed/not_applicable slots`。
- `backend/gameplay_review_service.py`：支持 Gap 的“提供证据后解决”“确认不适用”“保持待确认”，不支持直接把建议答案写成事实。
- `js/gameplay-review.js`：在现有 P4 内显示缺失问题、所属章节/槽位及阻塞级别。
- `tests/test_gameplay_review_model.py`
- `tests/test_gameplay_review_service.py`

### 新数据结构

```python
class Gap(TypedDict):
    gapId: str
    chapterId: str
    chapterType: ChapterType
    slotId: str
    question: str
    severity: Literal["implementation_blocking", "qa_blocking", "documentation_gap"]
    evidenceStatus: Literal["missing", "conflicted", "insufficient"]
    status: Literal["open", "resolved", "not_applicable"]
    resolutionFactIds: list[str]
```

### 核心算法

```text
for each classified chapter:
  schema = library.get(chapterType, schemaVersion)
  applicable_required_slots = evaluate_applicability(schema, confirmed_facts, mechanic_variant)
  covered = confirmed slots + explicitly reviewed not_applicable slots
  gaps = applicable_required_slots - covered
  emit schema-authored question for each gap
```

- GapAnalyzer 不调用 LLM。
- Schema 的问题文本可以提示“需要确认什么”，不能包含默认答案。
- `not_applicable` 必须有人工审核记录；系统不能自行判定关键槽位不适用。
- 证据冲突生成 conflicted Gap，不选取“更常见”的答案。

### TDD 顺序

1. 三选一缺少候选池来源、重复规则、权重等槽位时逐项产生 Gap。
2. 事实未证明“不放回”时不得生成“不放回”Rule。
3. 填充一个 confirmed slot 后只消除对应 Gap。
4. 人工确认 not_applicable 可关闭 Gap，并记录 reviewer/revision。
5. 同一输入多次分析产生稳定 gapId 和排序。
6. 攻击章节的表现槽缺失不能被逻辑 Rule 覆盖。
7. optional 和 predicate 未触发的 conditional slot 不产生 Gap。
8. presentation_only 无表现证据时不产生 Gap，有证据但缺规则时只产生 documentation_gap。
9. severity 只读取 GapPolicy/variant overlay，不能由运行时文本推断。

### 自检与验收

- 运行：`python -m pytest tests/test_gap_analyzer.py tests/test_gameplay_review_model.py tests/test_gameplay_review_service.py -q`
- 对《一路狂飙》输出 `phase-3-gap-report.json`：按章节列出 required、covered、notApplicable、open gaps；每个 Gap 只显示问题和证据状态。
- 抽查随机/三选一章节，确认没有通过常见游戏经验补权重、刷新次数、暂停或空池处理。
- 提交建议：`feat: detect schema gaps without inference`

**Phase 3 验收闸门：** 用户确认 Gap 能发现缺项但绝不补答案。停止，不进入 Phase 4。

## Phase 4：PlanningLanguageRenderer、正文组装与质量闸门

### 新增文件

- `backend/planning_language_spec.py`：语言规范、句式策略、禁用短语及类型约束。
- `backend/planning_language_renderer.py`：Rule → Sentence 的确定性渲染器。
- `backend/common_sense_filter.py`：按信息增量轴过滤解释性内容。
- `backend/semantic_deduplicator.py`：按 semanticKey、ownerChapterId、definitionMode 去重与引用。
- `backend/document_assembler.py`：按 Schema 章节结构组装已批准 Rule 和 Gap 提示。
- `backend/document_quality_evaluator.py`：计算验收指标，不改正文。
- `tests/test_planning_language_renderer.py`
- `tests/test_common_sense_filter.py`
- `tests/test_semantic_deduplicator.py`
- `tests/test_document_assembler.py`
- `tests/test_document_quality_evaluator.py`

### 修改文件

- `backend/gameplay_render.py`：v2 只调用 DocumentAssembler；禁止读取 plannerSections 和调用自由正文生成。
- `backend/feishu_render.py`：v2 使用已组装的确定性章节块；不在发布时重新改写内容。
- `backend/server.py`：P7 自动补正文路径对 v2 关闭；存在 `implementation_blocking` Gap 时返回结构化阻塞结果并引导回 P4，不得补齐。
- `backend/planning_content_policy.py`：质量规则改为检查结构化 Rule 与渲染结果。
- `backend/feishu_language_quality.py`：保留为 v1 兼容/观测，v2 不再依赖正则拆分混合句。
- `backend/granularity_audit.py`：审计输入改为 Rule/SchemaSlot/Gap，而非仅扫描正文。
- `tests/test_gameplay_render.py`
- `tests/test_feishu_render.py`
- `tests/test_server.py`

### 废弃逻辑

- v2 禁用 `gameplay_analysis.py` 的 detail prompt 生成最终章节正文。
- v2 禁用 `gameplay_rule_copy.py` 的通用摘要与 `normal_flow[:4]` 截断作为正文源。
- v2 禁用 `server.py` P7 缺正文时的自动自由补全。
- v2 禁用以 `SequenceMatcher` 句面相似度作为主要去重依据。
- 上述代码先保留在明确命名的 v1 adapter 内；等旧项目迁移策略另案确认后再删除。

### P7 阻塞策略

- 有 `implementation_blocking` Gap：预览显示“待确认项”清单，导出按钮阻塞，并提供返回规则审核入口。
- 只有 `qa_blocking` Gap：允许生成带明确“测试条件待确认”附录的内部预览，但正式交付导出默认阻塞；项目管理员可显式豁免并留下审计记录。
- 只有 `documentation_gap`：不阻塞导出，在质量报告和待确认附录中显示；正文仍不得包含推测答案。
- 无论何种情况，导出阶段只读取 `reviewStatus = approved` 的 Rule 和明确审核通过的参数引用。

### TDD 顺序

1. renderer 拒绝未批准 Rule、无证据 Rule 和未知 ruleType。
2. 每种 ruleType 至少一组 snapshot；logic/presentation 永不合并成一句。
3. 禁用短语被过滤后若无信息增量则整句删除，有规则信息则只删解释性从句。
4. 同 semanticKey 的 primary 只在 ownerChapter 完整定义；其他章节输出引用，不重复定义。
5. v2 正文即使存在 plannerSections 也不读取。
6. implementation_blocking Gap 阻止导出；系统不调用任何正文补全函数。
7. 同一 ApprovedData 重复渲染字节级一致。
8. 五类章节同时输出“旧正文 / 结构化 Rule / 新正文”对比。
9. 同一 Rule 和 languageSpecVersion 重复渲染选择同一 controlled variant。
10. grouping_strategy 不为每个 slot 生成标题，并保持 parent/child 与 inline merge 约束。
11. Alignment evaluator 的 70 分自动项固定可重复，且输出不得回流生成链路。

### 自检与验收

- 运行：`python -m pytest tests/test_planning_language_renderer.py tests/test_common_sense_filter.py tests/test_semantic_deduplicator.py tests/test_document_assembler.py tests/test_document_quality_evaluator.py tests/test_gameplay_render.py tests/test_feishu_render.py tests/test_server.py -q`
- 运行项目完整测试集：`python -m pytest -q`
- 为《一路狂飙》的 movement、attack、slot、randomization、settlement 各输出三栏对比。
- 输出 A/B/C 指标；C 只记录结构/语言范式统计，不把 GVE16 文本放入训练夹具或产物。
- 独立截图 P4 规则审核、P7 Gap 阻塞、P7 新正文预览。
- 对完全不同游戏素材做盲测，确认 Schema 按证据适配。
- 提交建议：`feat: render approved planning rules deterministically`

**Phase 4 验收闸门：** 指标达到约定目标并由用户验收；不自动启动 EntityBuilder、ParameterResolver、图解/参数重构等后续工作。

## ChapterSchemaLibrary 修订设计（Design Revision 2）

### 公共接口

```python
ChapterType = Literal[
    "unknown", "attribute", "movement", "attack", "damage_death",
    "slot", "unlock_progression", "spawn", "randomization",
    "state_machine", "combat_calculation", "interaction", "presentation",
    "settlement", "level_flow", "content_catalog",
]

RuleType = Literal["logic", "presentation", "interaction", "flow", "numeric", "config"]

SlotApplicability = Literal[
    "core", "conditional", "optional", "derived", "presentation_only"
]

PredicateOperator = Literal[
    "all", "any", "not", "evidence_tag", "fact_exists", "rule_exists",
    "variant_is", "slot_confirmed", "parameter_exists"
]

@dataclass(frozen=True)
class ApplicabilityPredicate:
    operator: PredicateOperator
    operands: tuple["ApplicabilityPredicate | str", ...]

@dataclass(frozen=True)
class DerivationSpec:
    source_slots: tuple[str, ...]
    derivation_rule: str
    output_rule_type: RuleType

@dataclass(frozen=True)
class GapPolicy:
    severity: Literal["implementation_blocking", "qa_blocking", "documentation_gap"]
    question: str

@dataclass(frozen=True)
class SchemaSlotDefinition:
    slot_id: str
    label: str
    description: str
    applicability: SlotApplicability
    applicable_when: ApplicabilityPredicate | None
    derivation: DerivationSpec | None
    allowed_rule_types: tuple[RuleType, ...]
    gap_policy: GapPolicy | None
    content_group: str
    ordering_weight: int

@dataclass(frozen=True)
class ParentChildRelationship:
    parent_slot: str
    child_slots: tuple[str, ...]
    render_mode: Literal["nested", "inline", "reference"]

@dataclass(frozen=True)
class InlineMergeRule:
    slot_ids: tuple[str, ...]
    semantic_pattern: str
    max_rules: int
    separator: Literal["sentence", "semicolon"]

@dataclass(frozen=True)
class GroupingStrategy:
    group_order: tuple[str, ...]
    heading_policy: Literal["chapter_only", "semantic_groups", "always"]
    mergeable_slots: tuple[tuple[str, ...], ...]
    parent_child_relationships: tuple[ParentChildRelationship, ...]
    inline_merge_rules: tuple[InlineMergeRule, ...]
    min_rules_for_subheading: int

@dataclass(frozen=True)
class ChapterSchema:
    schema_version: str
    chapter_type: ChapterType
    mechanic_variant: str | None
    display_name: str
    classifier_signals: tuple[str, ...]
    slots: tuple[SchemaSlotDefinition, ...]
    grouping_strategy: GroupingStrategy
    forbidden_mixes: tuple[tuple[RuleType, RuleType], ...]
    rendering_hints: Mapping[str, str]

class ChapterSchemaLibrary:
    def register(self, schema: ChapterSchema) -> None: ...
    def get(self, chapter_type: ChapterType, version: str) -> ChapterSchema: ...
    def list_types(self, version: str) -> tuple[ChapterType, ...]: ...
    def validate(self, schema: ChapterSchema) -> tuple[str, ...]: ...
```

注册键为 `(chapter_type, mechanic_variant, schema_version)`。同键不可重复；`core` 与 `conditional` 必须有 gap_policy；`conditional`、`presentation_only` 必须有可执行 applicable_when；`derived` 必须有 derivation；`optional` 不得因缺失产生 Gap。每个 slot 必须限定 allowed_rule_types；`unknown` 只能产生分类待确认 Gap，不能承载正文 Rule。

Predicate 采用可序列化 AST，不保存自然语言条件。例如远程攻击来源槽：

```yaml
applicability: conditional
applicable_when:
  operator: any
  operands:
    - {operator: evidence_tag, operands: [projectile]}
    - {operator: evidence_tag, operands: [ranged_attack]}
    - {operator: variant_is, operands: [ranged]}
```

求值只读取已确认 fact/rule 标签、mechanicVariant、已确认 slot 和参数引用。证据不足时 predicate 为 false；GapAnalyzer 不调用 LLM。`core` 恒适用；`optional` 仅有证据时建槽；`derived` 仅在全部 source_slots 已确认且 derivation_rule 成功时生成确定性 Rule；`presentation_only` 仅存在对应表现证据时适用，默认不阻塞。

### 五个完整初始 Schema

下表格式为：`槽位｜适用性及 predicate｜允许类型｜Gap 等级/问题｜正文组`。`—` 表示不因缺失产生 Gap。

#### movement

- `movement_trigger｜core｜logic/flow｜implementation_blocking：移动在什么条件下开始？｜movement_core`
- `movement_direction｜conditional；any(evidence_tag:directional, evidence_tag:follow, evidence_tag:targeted)｜logic｜implementation_blocking：移动方向或跟随目标如何确定？｜movement_core`
- `movement_speed_source｜core｜numeric/config｜implementation_blocking：移动速度读取什么数值或配置？｜movement_core`
- `movement_path｜conditional；any(evidence_tag:pathfinding, evidence_tag:waypoint, evidence_tag:bounded_path)｜logic｜implementation_blocking：路径或移动范围如何确定？｜movement_constraints`
- `movement_collision｜conditional；any(evidence_tag:collision, evidence_tag:obstacle, evidence_tag:overlap)｜logic｜qa_blocking：发生碰撞或阻挡时如何处理？｜movement_constraints`
- `movement_stop_condition｜core｜logic/flow｜implementation_blocking：什么条件下停止移动或退出移动状态？｜movement_core`
- `movement_state_constraints｜conditional；any(evidence_tag:disable_movement, evidence_tag:state_restriction)｜logic｜qa_blocking：受限制状态下如何处理移动？｜movement_constraints`
- `movement_duration｜derived；source=movement_trigger,movement_stop_condition；rule=derive_active_interval｜flow｜—｜movement_core`
- `movement_presentation｜presentation_only；any(evidence_tag:movement_animation, evidence_tag:movement_vfx, evidence_tag:movement_ui)｜presentation｜documentation_gap：已观察到的移动表现需要如何定义？｜movement_presentation`

组织：默认只有章标题；`movement_trigger + movement_direction + movement_speed_source + movement_stop_condition` 合并为连续的“移动规则”条目。只有约束类达到 2 条时才出现“移动限制”子标题；表现永远独立成组。

#### attack

- `attack_trigger｜core｜logic｜implementation_blocking：攻击在什么条件下触发？｜attack_core`
- `attack_target｜core｜logic｜implementation_blocking：攻击目标如何选取？｜attack_core`
- `attack_range｜conditional；any(evidence_tag:range_limit, evidence_tag:melee, evidence_tag:ranged_attack)｜numeric/config｜implementation_blocking：攻击距离如何确定？｜attack_parameters`
- `movement_during_attack｜conditional；any(evidence_tag:moving_attacker, evidence_tag:movement_state)｜logic｜qa_blocking：攻击状态下的移动规则是什么？｜attack_constraints`
- `attack_frequency｜conditional；any(evidence_tag:repeat_attack, evidence_tag:cooldown, evidence_tag:attack_interval)｜numeric/config｜implementation_blocking：连续攻击的频率或间隔如何确定？｜attack_parameters`
- `attack_method｜core｜logic｜implementation_blocking：攻击行为按什么方式执行？｜attack_core`
- `melee_ranged_difference｜conditional；all(evidence_tag:multiple_attack_modes, any(evidence_tag:melee, evidence_tag:ranged_attack))｜logic/config｜qa_blocking：不同攻击类型的规则差异是什么？｜attack_variants`
- `projectile_skill_source｜conditional；any(evidence_tag:projectile, evidence_tag:ranged_attack, evidence_tag:skill_attack)｜logic/config｜implementation_blocking：子弹或技能读取什么来源？｜attack_variants`
- `attack_exit_condition｜core｜logic/flow｜implementation_blocking：什么条件下退出攻击状态？｜attack_core`
- `damage_reference｜conditional；evidence_tag:damage_event｜logic/config｜implementation_blocking：命中后的伤害计算引用哪条规则或配置？｜attack_parameters`
- `attack_presentation｜presentation_only；any(evidence_tag:attack_animation, evidence_tag:attack_vfx, evidence_tag:attack_sfx)｜presentation｜documentation_gap：已观察到的攻击表现需要如何定义？｜attack_presentation`

组织：触发、目标、方式、退出按攻击生命周期连续排列；参数紧随其引用的行为，不单独打印字段标题。`attack_variants` 以父规则 `attack_method` 为父节点，按近战/远程 variant 嵌套；表现单列。

#### slot

- `slot_count｜core｜numeric/config｜implementation_blocking：栏位数量如何确定？｜slot_definition`
- `slot_type｜conditional；any(evidence_tag:multiple_slot_types, evidence_tag:typed_slot)｜logic/config｜implementation_blocking：栏位类型及区分规则是什么？｜slot_definition`
- `initial_state｜core｜logic/config｜implementation_blocking：栏位初始状态是什么？｜slot_lifecycle`
- `default_content｜conditional；evidence_tag:default_content｜logic/config｜implementation_blocking：默认内容如何确定？｜slot_lifecycle`
- `fill_condition｜core｜logic/interaction｜implementation_blocking：什么条件下可填充栏位？｜slot_lifecycle`
- `full_slot_rule｜conditional；any(evidence_tag:finite_slots, evidence_tag:slot_full)｜logic｜qa_blocking：栏位填满后如何处理？｜slot_constraints`
- `replace_rule｜conditional；any(evidence_tag:replace, evidence_tag:occupied_slot_action)｜logic/interaction｜qa_blocking：已占用栏位如何替换？｜slot_operations`
- `remove_rule｜conditional；any(evidence_tag:remove, evidence_tag:unequip)｜logic/interaction｜qa_blocking：栏位内容如何卸除？｜slot_operations`
- `display_content｜presentation_only；any(evidence_tag:slot_ui, evidence_tag:slot_state_display)｜presentation｜documentation_gap：栏位界面显示哪些已观察信息？｜slot_presentation`
- `click_behavior｜conditional；evidence_tag:clickable_slot｜interaction｜qa_blocking：点击栏位后执行什么操作？｜slot_operations`

组织示例（`heading_policy=chapter_only`）：

```text
自选武器栏
- 进入关卡时为空。
- 每个栏位仅可选择一种武器。
- 栏位填满后不再获得新武器类型。
```

这里 `initial_state + fill_condition + full_slot_rule` 属于同一 `slot_lifecycle`，按生命周期排序为连续条目；不会生成“初始状态/填充条件/满栏规则”三个数据库式小标题。只有 slot_operations 达到 3 条或存在两个 mechanicVariant 时才建子标题。

#### randomization

- `random_trigger｜core｜logic/flow｜implementation_blocking：随机流程在什么条件下触发？｜random_flow`
- `candidate_pool_source｜core｜config｜implementation_blocking：候选池读取什么来源？｜candidate_pool`
- `pool_entry_condition｜core｜logic/config｜implementation_blocking：候选项满足什么条件后入池？｜candidate_pool`
- `pool_exit_condition｜conditional；any(evidence_tag:pool_removal, evidence_tag:eligibility_change)｜logic/config｜qa_blocking：候选项在什么条件下出池？｜candidate_pool`
- `replacement_rule｜conditional；any(variant_is:three_choice, evidence_tag:draw_without_replacement, evidence_tag:repeat_draw)｜logic/config｜qa_blocking：抽取后是否放回？｜draw_policy`
- `duplicate_rule｜conditional；any(variant_is:three_choice, evidence_tag:multi_result)｜logic/config｜qa_blocking：单次结果是否允许重复？｜draw_policy`
- `random_order｜conditional；any(evidence_tag:filter_stage, evidence_tag:weighted_draw, evidence_tag:multi_stage_random)｜logic｜qa_blocking：筛选与抽取按什么顺序执行？｜draw_policy`
- `weight_rule｜conditional；any(evidence_tag:weight, variant_is:roulette)｜numeric/config｜implementation_blocking：权重如何确定？｜draw_policy`
- `empty_result_rule｜core｜logic/flow｜qa_blocking：没有合法候选项时如何处理？｜random_exceptions`
- `max_level_rule｜conditional；evidence_tag:leveled_candidate｜logic/config｜qa_blocking：达到上限的候选项如何处理？｜candidate_pool`
- `prerequisite_rule｜conditional；evidence_tag:prerequisite｜logic/config｜qa_blocking：候选项的前置条件如何判定？｜candidate_pool`
- `refresh_rule｜conditional；evidence_tag:refresh_action｜logic/interaction｜qa_blocking：刷新后如何重新生成候选项？｜refresh_flow`
- `refresh_count｜conditional；evidence_tag:limited_refresh｜numeric/config｜implementation_blocking：可刷新次数如何确定？｜refresh_flow`
- `refresh_cost｜conditional；evidence_tag:paid_refresh｜numeric/config｜implementation_blocking：刷新消耗如何确定并在何时扣除？｜refresh_flow`
- `pause_rule｜conditional；any(variant_is:three_choice, evidence_tag:selection_overlay)｜flow｜qa_blocking：候选展示和选择期间主流程是否暂停？｜random_flow`
- `confirm_effect_timing｜conditional；any(variant_is:three_choice, evidence_tag:manual_confirmation)｜interaction/flow｜implementation_blocking：选择在何时确认并生效？｜random_flow`

组织：`random_flow` 作为父流程；`candidate_pool` 和 `draw_policy` 是其子组。three_choice 才启用选择/确认/暂停相关槽，roulette 启用权重与停止点相关 variant slot。刷新规则只有证据存在时出现，不打印空组。

#### settlement

- `settlement_trigger｜core｜flow/logic｜implementation_blocking：结算在什么条件下触发？｜settlement_flow`
- `battle_stop_timing｜conditional；evidence_tag:combat_session｜flow｜implementation_blocking：战斗在什么时点停止？｜settlement_flow`
- `result_determination｜core｜logic｜implementation_blocking：结果按什么条件判定？｜settlement_result`
- `statistics｜conditional；evidence_tag:settlement_statistics｜logic/config｜qa_blocking：统计哪些内容及其数据来源？｜settlement_rewards`
- `reward_rule｜conditional；evidence_tag:settlement_reward｜logic/config｜implementation_blocking：奖励如何确定？｜settlement_rewards`
- `record_update｜conditional；evidence_tag:record_update｜logic/flow｜qa_blocking：哪些记录在什么时点更新？｜settlement_persistence`
- `secondary_reward｜conditional；evidence_tag:secondary_reward｜logic/config｜implementation_blocking：二次奖励在什么条件下发放？｜settlement_rewards`
- `settlement_buttons｜conditional；evidence_tag:settlement_ui｜interaction｜qa_blocking：结算界面按钮分别执行什么操作？｜settlement_exit`
- `exit_path｜core｜flow/interaction｜implementation_blocking：结算后通过什么路径离开？｜settlement_exit`
- `failure_branch｜conditional；evidence_tag:failure_result｜flow/logic｜implementation_blocking：失败结果的流程差异是什么？｜settlement_result`
- `persistence_timing｜conditional；any(evidence_tag:persistence, evidence_tag:record_update, evidence_tag:settlement_reward)｜flow/config｜implementation_blocking：结算数据在什么时点写入？｜settlement_persistence`
- `settlement_presentation｜presentation_only；any(evidence_tag:settlement_animation, evidence_tag:settlement_sfx, evidence_tag:settlement_ui)｜presentation｜documentation_gap：已观察到的结算表现需要如何定义？｜settlement_presentation`

组织：按“触发 → 判定 → 奖励/统计 → 落库 → 离开”形成一段执行顺序；奖励的数值来源以内联引用跟随 reward_rule。失败分支嵌套于 result_determination，不独立打印同级字段标题；表现最后独立成组。

### grouping_strategy 的统一行为

- `group_order` 决定语义组顺序，不等于每个 slot 都生成标题。
- `heading_policy=chapter_only` 时默认只保留章标题；单组少于 `min_rules_for_subheading=3` 不生成子标题。
- `mergeable_slots` 只允许在保持原子 Rule 与 RuleType 可追溯的前提下连续呈现；数据层不合并 Rule。
- `parent_child_relationships` 定义流程主规则与分支、变体、参数引用的层级。
- `inline_merge_rules` 只合并同一主语、同一 ruleType、无冲突条件的短规则；logic 与 presentation 永不内联合并。
- 空组不输出；单条参数配置优先内联到所引用规则，多个独立配置才形成“配置”子组。

### mechanicVariant

`chapterType` 表示文档写法大类，`mechanicVariant` 表示该类中的机制变体。它是开放字符串但必须由 Library 注册才能触发 variant 专属 Schema overlay；未注册值保留在数据中并产生 documentation_gap，不擅自套规则。

```python
class ClassifiedChapter(TypedDict):
    chapterType: ChapterType
    mechanicVariant: str | None
    # 其他字段同前

class ChapterSchemaLibrary:
    def resolve(
        self,
        chapter_type: ChapterType,
        mechanic_variant: str | None,
        version: str,
    ) -> ChapterSchema: ...
```

Phase 1 只注册必要变体：`randomization/three_choice`、`randomization/roulette`、`attack/melee`、`attack/ranged`、`movement/follow`、`movement/straight_line`。解析顺序为 base schema → 已注册 variant overlay；variant 只能增加/收窄适用性与组织规则，不能复制整个 base schema。证据不足时 `mechanicVariant=None`，不得猜测。

### Gap severity 的业务语义

- `implementation_blocking`：缺失后程序无法唯一实现或会产生不同业务结果，例如触发、目标、结算判定、配置来源、生效时点。阻止正式导出；必须以确认事实解决或人工确认不适用。
- `qa_blocking`：主体实现路径基本确定，但缺失边界、异常、状态限制或可验证预期，测试无法完整验收。允许内部预览；正式交付默认阻止，只有带 reviewer、reason、revision 的显式豁免才可导出。
- `documentation_gap`：不影响主体实现和核心测试，通常是有证据但未定义完整的表现、命名或辅助说明。不中断导出，进入质量报告和“待确认项”附录。

Severity 由 Schema slot 的 GapPolicy 固定声明，可由 mechanicVariant overlay 收紧，但运行时模型不能根据措辞或 LLM 判断自行升降级。`presentation_only` 默认 documentation_gap；若特定 variant 明确把某表现作为可测试反馈，可在 overlay 中提升为 qa_blocking。

## PlanningLanguageSpec / PlanningLanguageRenderer 初版设计

### Rule → Sentence 输入边界

Renderer 只接受 `reviewStatus = approved` 且 evidenceIds 非空的 Rule。它可以读取 ChapterSchema 的 section/rendering_hints 和已批准参数值，但不能读取原始 AI 总结文本、未确认 Fact、open Gap 或 GVE16 文本。

输出：

```python
class RenderedRule(TypedDict):
    ruleId: str
    ownerChapterId: str
    section: str
    ruleType: RuleType
    text: str
    sourceEvidenceIds: list[str]
```

### RuleSemanticPattern → Controlled Sentence Variants

先由结构字段确定 `semanticPattern`，再在该 pattern 的受控 variants 中确定性选句。variant 选择键为 `stable_hash(ruleId + semanticPattern + languageSpecVersion) % variant_count`；同一版本、同一 Rule 永远输出同一句，升级语言规范才允许变化。任何 variant 都不得增删语义字段。

- `event_action`：`当 {trigger} 时，{behavior}。` / `{trigger} 后，{behavior}。`
- `condition_branch`：`若 {condition}，则 {behavior}；否则 {exception}。` / `{condition} 时执行 {behavior}；不满足时执行 {exception}。`
- `state_enter`：`{condition} 满足后，进入 {state} 状态。` / `达到 {condition} 后进入 {state} 状态。`
- `state_continuous`：`{state} 状态下，持续执行 {behavior}。` / `处于 {state} 状态时，按 {behavior} 执行。`
- `state_exit`：`当 {exitCondition} 时，退出 {state} 状态。` / `{exitCondition} 后结束 {state} 状态。`
- `config_read`：`{subject} 读取 {configRef}。` / `{subject} 按 {configRef} 执行。`
- `level_config`：`每级 {subject} 独立配置。` / `{subject} 按等级分别配置。`
- `numeric_formula`：`{subject} 按 {formulaRef} 计算。` / `{subject} 的计算方式读取 {formulaRef}。`
- `interaction_action`：`点击 {target} 后，{behavior}。` / `对 {target} 执行点击操作时，{behavior}。`
- `presentation_sync`：`{logicEvent} 后同步刷新 {uiElement}。` / `{logicEvent} 时更新 {uiElement}。`
- `reference`：`本规则按《{ownerChapterTitle}》中的“{ruleLabel}”执行。`

语义 pattern 与 RuleType 是正交关系：例如 logic 可为 event_action/state_enter，flow 可为 state_enter/state_exit。Renderer 先校验必需字段，再选 pattern 和 variant；字段不足返回 RenderError 并退回 P4。相邻规则由 grouping_strategy 决定段落与层级，不以随机选句制造“自然感”。

### 禁止或强制降权短语

`为了`、`从而`、`帮助玩家`、`使玩家能够`、`可以看到`、`该设计旨在`、`进一步提升`、`有助于`、`这样可以`、`便于玩家`、`增强体验`、`提升沉浸感`、`让玩法更加`。

- 若短语所在从句没有新增信息轴，删除从句。
- 若整句都没有新增信息轴，删除整句并记录 filter reason。
- 若文本属于明确的“设计目标”章节，允许保留，但该章节不进入执行规则计数。

### CommonSenseFilter 的信息增量判定

每句至少新增一个轴：`condition`、`behavior`、`constraint`、`state`、`result`、`numeric`、`config`、`boundary`、`presentation`。

判定依赖结构化 Rule 字段而不是只做关键词正则：

1. 从 Rule 字段计算 `informationAxes`。
2. 若轴为空，丢弃该候选句。
3. 若句子含目的/价值从句，移除该从句后重新渲染。
4. Rule 有 parameterRefs、exception、exitCondition 或 presentation 行为时，相关信息不可因禁用词误删。
5. Filter 不创造新措辞；它只能接受、裁剪可识别的解释从句或拒绝。

### SemanticDeduplicator

- 主键为 `(semanticKey, ownerChapterId)`，不依赖句面相似度。
- `definitionMode = primary`：只在 ownerChapter 完整定义一次。
- `definitionMode = reference`：其他章节输出“按《{ownerChapterTitle}》中的 {ruleLabel} 执行。”，不复制正文。
- 相同 semanticKey 但 ownerChapter 不同视为建模冲突，进入 P4 待处理，不能静默删除。
- 相似句但 semanticKey 不同不得因 SequenceMatcher 分数高而删除。

### 示例输入与输出

**攻击逻辑**

输入：`logic / trigger=敌人攻击命中载具 / behavior=按伤害计算结果扣除载具当前生命值`

输出：`敌人攻击命中载具后，按伤害计算结果扣除载具当前生命值。`

**受击表现（与上一条独立）**

输入：`presentation / trigger=载具当前生命值变化 / behavior=同步刷新生命条`

输出：`载具当前生命值变化后，同步刷新生命条。`

**状态退出**

输入：`flow / stateChange=攻击状态 / exitCondition=攻击目标不再满足攻击条件 / behavior=退出`

输出：`当攻击目标不再满足攻击条件时，退出攻击状态。`

**随机池配置**

输入：`config / subject=候选池 / configRef=对应玩法候选池配置`

输出：`候选池读取对应玩法候选池配置。`

**满级规则**

输入：`logic / trigger=候选项达到最大等级 / behavior=从候选池移除`

输出：`候选项达到最大等级后，从候选池移除。`

只有素材证据和 P4 审核明确该行为时才允许输出；否则 Schema 产生“达到上限的候选项如何处理？”Gap。

**结算落库**

输入：`flow / trigger=结算结果确认 / behavior=写入本局结算数据 / configRef=结算数据存储规则`

输出：`结算结果确认后，按结算数据存储规则写入本局结算数据。`

**应过滤内容**

输入候选：`该设计旨在帮助玩家快速理解当前状态。`

输出：无。原因：没有条件、行为、限制、状态变化、结果、数值、配置、边界或具体表现要求。

## 目标指标与 A/B/C 评价口径

- Chapter Schema 匹配正确率 ≥ 90%
- 核心规则覆盖率 ≥ 85%
- Logic / Presentation 分类正确率 ≥ 90%
- 核心规则可执行率 ≥ 85%
- 测试可验证率 ≥ 85%
- 无证据推测率 ≤ 5%
- 重复规则率 ≤ 10%
- 常识/解释性废话相对 A 版降低 ≥ 60%
- 与成熟人工执行策划文档的结构与写作范式对齐度（Alignment Score）≥ 80 分

### Alignment Score（0～100）

| 维度 | 权重 | 自动评分 | 人工主策抽检 | 得分方式 |
|---|---:|---:|---:|---|
| 章节组织 | 20 | 12 | 8 | 自动检查 chapterType 顺序、空组、碎片化小标题率、grouping_strategy 违规；人工判断层级是否符合执行文档阅读路径。 |
| Schema 内容完整性 | 20 | 16 | 4 | 自动计算适用 core/conditional slot 的 confirmed、not_applicable、open Gap 覆盖；人工抽检 predicate 是否误触发或漏触发。 |
| 规则颗粒度与可执行性 | 15 | 9 | 6 | 自动检查 Rule 原子性、必需字段、证据引用、跨槽混写；人工判断程序能否据此唯一实现。 |
| 语言表达 | 15 | 8 | 7 | 自动检查受控句式、禁用短语、残缺句、模板连续重复率；人工判断是否接近真实系统策划语气且不机械。 |
| Logic / Presentation 分离 | 10 | 9 | 1 | 自动按 ruleType、字段和禁配词检测混合；人工抽检高风险样本。 |
| 重复控制 | 10 | 9 | 1 | 自动按 semanticKey/ownerChapter/definitionMode 计算重复定义率与引用正确率；人工检查误删。 |
| 常识/解释性内容 | 10 | 7 | 3 | 自动按 informationAxes 与禁用目的从句统计无增量比例；人工识别隐性设计意义和视频解说腔。 |
| **合计** | **100** | **70** | **30** | 自动分与人工分分别归一后按表内分值相加。 |

具体公式：

```text
AlignmentScore =
  ChapterOrganization(20)
  + SchemaCompleteness(20)
  + RuleExecutability(15)
  + PlanningLanguage(15)
  + Separation(10)
  + Deduplication(10)
  + InformationDensity(10)
```

自动子项均使用固定分母：

- Schema 完整性 = `已确认适用槽 + 已审核不适用槽` / `全部适用 core 与 conditional 槽`；optional、未触发 conditional、无证据 presentation_only 不进入分母。
- 碎片化小标题率 = `仅含 1 条 Rule 的非必要子标题 / 全部子标题`，越低得分越高；Schema 明确要求的单条独立表现组不计为碎片。
- 原子规则合格率 = `仅含一个 ruleType 且具备该 semanticPattern 必需字段的 Rule / 全部 approved Rule`。
- 分离率 = `未发现逻辑字段与表现行为混写的 Rule / 全部 logic + presentation Rule`。
- 重复控制得分由重复定义率和 reference 正确率各占一半；目标重复定义率 ≤ 10%。
- 信息密度 = `含至少一个 informationAxis 的句子 / 全部正文句子`；目的/价值从句单独计入解释性比例。
- 语言自动分同时限制同一 controlled variant 三句连续重复；出现时扣语言自动分，但不改生成结果。

人工抽检采用固定样本：每个项目至少抽 5 个章节类型；每类随机抽 5 条规则，另加全部 implementation_blocking Gap 和所有 renderer error。两名主策独立按 0/1/2 评分（不合格/部分合格/合格），分歧项复核；人工子项按可得分比例换算到对应权重。

### A/B/C 对照

- A：Phase 0 冻结的当前旧版《一路狂飙》，按同一 evaluator 和同一人工抽样表评分。
- B：重构后《一路狂飙》，使用与 A 相同素材、章节范围、抽样种子和评分人；主要验收看 `B - A` 及 B 是否 ≥ 80。
- C：GVE16 Golden Reference，仅抽取匿名化组织/颗粒度/语言范式评分，不参与 Schema 命中率与证据推测率比较，不向生成链路提供文本。C 用作上限参照，不要求章节一一对应。
- 跨题材盲测 D：至少一个不同品类游戏，用于防止 B 针对《一路狂飙》或 GVE16 过拟合；D 的 Alignment Score 同样要求 ≥ 80，且无证据推测率 ≤ 5%。

评价器是只读旁路：输入 FinalDocument、ApprovedData 和匿名化人工评分表，输出 score breakdown；任何分数、扣分原因、C 参考数据都不得回流 ChapterClassifier、RuleNormalizer、Renderer 或 DocumentAssembler。

## 明确不在本计划内

- 不调整 P5 图解审核定义、入口或主数据源。
- 不在 Phase 1～4 全量实现 EntityBuilder、ParameterResolver。
- 不重做视频/截图上传与理解能力。
- 不批量迁移历史项目。
- 不大改现有 P4/P7 UI，只增加结构化审核和阻塞所必需的字段展示。
- 不推进后续 P2～P7 扩展任务；每个 Phase 验收后单独等待下一步授权。
