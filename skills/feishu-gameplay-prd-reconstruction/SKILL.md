---
name: feishu-gameplay-prd-reconstruction
description: Use when gameplay output from screenshots, videos, reference documents, or spreadsheets is too shallow, reads like image narration, misses rules or configuration depth, or must match the execution-ready granularity of approved Feishu game-design samples. Excludes UE flowchart production.
---

# Feishu Gameplay PRD Reconstruction

## Goal

Turn evidence into an implementation-ready game-design specification. Match the reasoning depth of the approved Feishu samples without copying their fixed game systems. Do not produce UE flowcharts.

## Required workflow

1. Read `references/evidence-to-output.md` and classify every source.
2. Read `references/granularity-contract.md` and build an adaptive four-level-at-most directory.
3. Write the gameplay overview from the player's viewpoint: goal, basic controls, core loop, progression/resource driver, and win/fail conditions. Object descriptions are supporting system detail, not the overview.
4. Separate visible evidence from gameplay rules. Screenshots prove visible states; reference documents and tables may prove hidden rules, fields, formulas, reset behavior, and ownership.
5. Select only the modules that the mechanism needs: prose rules, content catalog, parameter table, formula, state/branch matrix, local screenshot, or structural diagram.
6. For random systems, explicitly reconstruct pool eligibility, weights, draw order, replacement, duplicate/empty behavior, caps, reroll cost, temporary results, and reset.
7. For lifecycle rules, distinguish normal exit, re-entry, force quit/relogin, round end, stage settlement, and activity end whenever evidence covers them.
8. Read `references/quality-gates.md` and run the main-planner review before returning or publishing.
9. When a JSON gameplay model is available, run `scripts/validate_prd_granularity.py <model.json>`.
10. Before publishing, compare the draft with approved samples by information role rather than wording: 内容清单、配置字段、执行顺序、公式、异常边界、生命周期。Any role supported by evidence but absent from the draft is a blocking gap.
11. Choose document depth adaptively. Put a short mechanism directly under its subsystem as natural rule prose. Add another heading, table, formula block, state matrix, or diagram only when that mechanism has enough independent content to justify it. Never export every chapter with an identical form-like skeleton.
12. For parameterized mechanisms, preserve the sample's carrier order: 行为正文 → 就近命名映射 → 配置表（when values need lookup）→ 生命周期。Write each mapping as `业务名 → 配置表/字段名` beside the mechanism. If no authoritative configuration source exists, use `建议程序字段名（待程序/配置表确认）`; never invent an official table name. Configuration tables must be mechanism-specific and directly fillable: 载具等级表列等级、消耗与属性；武器表列伤害、冷却、索敌与范围；词条表列前置、权重、等级与效果；怪物/波次表列怪物、刷怪点、倍率和切换条件。Never use a universal audit schema such as `属性 / 说明 / 类型与单位 / 配置或计算 / 限制条件`; put units in the business column title and do not repeat prose explanations inside the table.
13. Build an applicability matrix before judging depth. For every system actually present in the evidence, check: content inventory, base properties, entry/unlock, progression, execution order, configuration mapping, player operation, system feedback, branches/failures, settlement, persistence/reset, and acceptance. A short paragraph cannot pass merely because it mentions the mechanism.
14. Treat approved samples as a question library, not a fact library. Compare the current project with the samples dimension by dimension; write only supported facts, create a decision card for genuinely ambiguous choices, and record unsupported sample-only dimensions as non-applicable with evidence.
15. Require a structural gameplay diagram when the mechanism contains at least three ordered stages, a branch/merge, a loop, pause/resume, multiple cooperating entities, spatial spawn/layout logic, or multi-stage random selection. This diagram is separate from the screenshot-first interaction planning board.
16. Keep domain templates and long-form heading sets as reserve knowledge. Activate weapon, Buff, inventory, sweep, random, wave, state, or other question libraries only when current evidence identifies that domain. Treat headings as selectable content responsibilities; merge, reorder, or omit them according to actual content volume.
17. Validate overview-to-detail traceability. Every major core-loop, progression, resource, win/fail, or mode claim in the overview must land in a detailed chapter, table, diagram, or explicit scope exclusion.
18. When one object has local and external progression or temporary and persistent states, document them separately and state conversion, inheritance, settlement, and reset relationships.
19. Preserve cancelled, deferred, and historical rules as status-tagged knowledge only. Exclude them from active flow, configuration, completion, and export gates.
20. Use a worked example when a confirmed formula or proportional state change remains ambiguous after symbolic explanation. The example must use confirmed or clearly illustrative values and may not create a new rule.
21. Run content discovery before granularity review. Inventory every evidenced gameplay mode, phase, entity, resource, rule, data/configuration item, interaction, presentation requirement, scope status, and production dependency. Map each item to prose, table, image, diagram, decision card, or explicit non-applicability.
22. Keep content coverage and depth coverage as separate gates. Missing evidenced content fails even if existing chapters are detailed; shallow treatment fails even if the directory names every system.
23. Build an attribute ledger for every evidenced core entity. Vehicle/carrier, weapon/skill/projectile, monster/NPC, player/avatar, resource and reward objects each receive their own applicable attributes; never collapse different owners into one generic parameter list. For every supported attribute record business meaning, type/unit, owner, read/write timing, calculation or judgment role, source, nearby field mapping when authoritative, range/boundary, and lifecycle. Missing values become decision cards, not invented defaults.
24. Attribute completeness must be visible in the gameplay prose, not only in a parameter table. Follow the sample documents' three-layer order: explain each applicable attribute beside its owning behavior (meaning, calculation/judgment role, timing and boundary); place authoritative business-name-to-field mappings nearby; then use a compact table only for centralized lookup of values, units and ranges. A table row alone does not satisfy the prose-granularity gate, and prose must not be a mechanical sentence-by-sentence transcription of that table.
25. Keep review-process language out of the formal PRD. Phrases such as “the diagram only proves…”, “the material only shows…”, “still to be confirmed by a decision card”, or “cannot be inferred from the diagram” belong in audit evidence or decision-card state, never in gameplay prose, diagram captions, or Feishu output. Rewrite the published carrier as direct business rules (condition, player action, system action, result, boundary), while unresolved alternatives remain represented only by the decision card and export gate.
26. When evidence contains waves, monster groups, spawn points, coordinates/offsets, intervals, enemy IDs, per-wave multipliers or rewards, automatically produce a focused wave/spawn configuration table beside the corresponding rule. Typical columns are selected from: level, wave, ordered monster group, group interval, spawn-point type, xy offset, monster/BOSS IDs and counts, health/attack multipliers, stop point, reward, and next-wave condition. Do not emit empty sample-only columns.
27. Treat length as a risk signal, never a quota. As a planning heuristic, a small feature often needs 3,000–8,000 Chinese characters, a medium core system 8,000–20,000, a complete core gameplay 20,000–50,000, and a multi-system game design 50,000–150,000 or more. Do not pad or repeat. If complete rules exceed one output, continue by chapter instead of compressing granularity.
28. Place every structural diagram inside the mechanism it explains. Introduce the trigger and current state before the diagram; continue with routing consequences, parameters, exceptions, and lifecycle after it. A detached diagram gallery cannot satisfy gameplay depth.
29. Place a source screenshot immediately beside the rule it materially clarifies: after the relevant state/operation is introduced and before details that depend on the image. Give it a planner-facing caption that states what visible fact it supports. Do not collect all screenshots into a generic evidence appendix when the sample uses inline illustration.
30. Derive headings from the actual information clusters and their volume. Never emit universal slots such as “规则与边界”, “执行内容”, “参数命名”, or “异常与边界” for every chapter. Merge short adjacent clusters; use a specific heading such as “武器栏状态”, “刷新与确认”, or “活动结束后的重置” only when it helps navigation.
31. Keep audit and provenance language out of the delivery body. Statements such as “本截图只能证明”, “不能冒充正式结论”, “当前素材不足以”, coverage status, source confidence, and improvement paths belong to review metadata or decision cards. Rewrite the user-facing body as confirmed design behavior; omit unsupported claims and route genuine choices to decision cards.
32. Separate review data from delivery tables. `parameters`, `parameterSchema`, evidence level, source status, range audit and completion metadata may drive the workbench and gates, but they do not automatically become a published table. The formal P7 and Feishu output may render only reviewed, mechanism-specific tables whose columns match a real planner lookup/fill task. Reject all universal schemas shaped like `属性/说明/类型与单位/配置或计算/限制条件`, `字段/策划含义/当前值与范围/类型与单位/配置来源`, or `名称/填写格式/单位/默认值`.
33. Verify business tables in the real browser by owning object, not as one compressed montage. Capture vehicle, weapon/affix, and monster/wave sections separately at readable scale. Require every table to stay inside its evidence canvas (`scrollWidth <= clientWidth` and right edge inside the container), and visually inspect that headers do not collapse into character-by-character wrapping. P7 and Feishu must render the same reviewed table set.
34. Treat every structural gameplay artifact as a 策划语义图, not a parameter visualization. Build nodes from actual player actions, system processing, decisions, branches, loops, merges and terminal states. Parameter rows, visible sample values and attribute lists may annotate a node but may not become the primary sequence. “出现箭头” only proves drawing capability; it never proves the diagram's gameplay meaning is correct.
35. Protect curated diagrams. A diagram with planner-authored nodes, decision diamonds, branch labels or loop routing must carry a curated/manual provenance marker and不得被通用生成器覆盖、降级或 silently replaced after prose changes. Mark it as an 过期图解, preserve the last good visual, and require semantic regeneration or renewed review. Reject a candidate that loses branches, loops, distinct node IDs or relationship density.
36. Keep reusable knowledge domain-neutral. Store evidence questions, semantic carriers, completeness gates and organization decisions as the rule; keep vehicle, weapon, Buff, inventory, sweep, monster and similar systems only as optional examples activated by matching evidence. A new gameplay type must not inherit sample entities, fields, headings or values.
37. In Feishu delivery, chapter numbering uses native ordered-list blocks rather than numeric prefixes embedded in title strings. Numbering must remain editable and renumber automatically when chapters are inserted, removed or reordered.
36. Keep diagram lifecycle deterministic. Refresh every existing stale diagram in place, preserve its ID and chapter bindings, increment its diagram revision, and return it to open review; do not auto-approve it. Existing multi-chapter coverage blocks new single-chapter duplicates. Detect and remove any 重复图解 before review or export.
37. Bind the complete review surface by identity. The 左侧章节、中间图解、右侧审核对象 must always resolve to the 同一图解 ID. Changing a chapter must update the visible card and action target together; for a chapter with several diagrams, focus the first unresolved diagram. Test the submitted ID, not only the visible title.
38. Derive every count, badge, progress value and next-route gate from 后端真实状态. Distinguish open, stale and reviewed visually; never show a green status for an unresolved artifact. A reviewed summary must equal the canonical per-diagram states after refresh. If all are reviewed, allow P6; otherwise keep P5 with an explicit actionable reason.
39. Enforce a 单一事实主载体. Confirmed business prose lives once in `plannerSections`; duplicate copies in object state, runtime responsibility, or presentation metadata become `carrierRefs`. Preserve a secondary carrier only when it adds a genuinely different implementation responsibility.
40. Classify every reserve domain as `applicable / decision_required / not_applicable`. Current evidence activates the domain; unresolved responsibilities create decision cards; absent domains remain omitted. Tag reusable examples as `sample_reserve` and never publish them as current-project facts.
41. Use 对象归属的属性正文: explain an attribute beside its owner and behavior before any lookup table. Do not merge vehicle, weapon, monster, building, inventory, reward, or other unrelated owners into one universal field catalog.
42. 禁止固定标题 and 禁止审核报告口吻. Titles name a real business object or independently useful mechanism; delivery prose states conditions, actions, results, and boundaries rather than generation instructions, comparison verdicts, or repair notes.
43. Keep 局部截图与流程图就近放置 at the rule they explain. A screenshot follows its anchored rule; a diagram stays inside its mechanism without cutting one numbered rule group into unrelated fragments.
44. Run 跨项目盲测 with at least three materially different domains before calling a reusable rule complete. Then use 分阶段验收: send the acceptance cases and inspection method first, wait for confirmation, self-check in the real browser, and provide 每个用例使用唯一匹配截图. Never reuse one image as evidence for several cases.
45. Separate gameplay logic, semantic feedback, and presentation. Logic owns triggers, state changes, calculations, permissions, results, and lifecycle. Semantic feedback may state what changed or what the player can verify. Position, color, attachment, animation, and visual styling belong to the planning board and must not be repeated in gameplay prose.
46. Write for three readers at once. A planner must recover design intent and player consequence; a programmer must recover trigger, data, state transition, and ownership; a tester must recover observable result, failure path, and boundary. Natural prose may combine related facts, but may not hide these responsibilities behind audit vocabulary or mechanical table transcription.
47. Compare against planner-written references by information role, not wording. Produce a delta matrix for supported roles: present in handwritten reference, present in generated draft, missing, excess, and remediation. A supported missing rule blocks delivery; excess visual narration or generic filler is removed rather than justified by length.
48. Apply a common-knowledge necessity gate sentence by sentence. Keep a statement only when it changes player action, system state, configuration/calculation, constraint/branch, test condition, or resolves a real ambiguity. Delete generic statements such as “players can control the vehicle” or “the interface displays related content.” A familiar rule remains necessary when it specifies a project-specific threshold, transition, persistence, or exception.
49. 手写策划文档对照必须逐章、逐项阅读，禁止只比较标题、字数或关键词。固定核对九个维度：机制拆分、规则深度、属性解释、配置映射、执行顺序、异常边界、生命周期、图文关系、语言与排布。每行必须同时记录“手写文档有／当前输出有／缺失／多余或错误／改善方式”，并引用手写文档章节或行号以及当前模型字段或预览段落。样例中的项目专属事实只能作为知识库储备；没有当前素材或策划决策依据时，必须判为越权内容并删除或转入决策卡。任一适用维度仍有无改善路径的缺失、越权事实或过期图解时，不得通过颗粒度门禁。

## Non-negotiable rules

- Organize by the actual gameplay: system → subsystem → mechanism → rule cluster/variant when needed. Never force weapons, enemies, combat, or growth into unrelated material.
- 不得固定套用 GVE16 的武器、怪物、战斗章节，也不得固定套用 GVE5 的组队、地图、探索章节；只复用二者的证据推导方法和执行级深度。
- Write planner-facing content in concise Simplified Chinese. Internal JSON keys and controlled enum values may remain English.
- A screenshot caption is evidence, not the gameplay rule.
- Do not turn screen coordinates, colors, buttons, popups, or visible numbers into a gameplay chapter unless they prove a mechanism.
- Do not invent hidden formulas, probabilities, configuration tables, default values, or persistence rules.
- Put unsupported decisions in a specific “需要策划决定” list; do not flood the normal rule body with “待确认”.
- Keep pure text and formulas as text. Generate a diagram only when spatial, state, branch, ownership, or sequence relationships materially benefit from a visual.
- Use local screenshots only when they clarify layout, component grouping, state comparison, or a rule step.
- When a screenshot is useful, embed the correct original or approved planning-board crop at the corresponding paragraph. Preserve aspect ratio and readability; never substitute an audit montage, thumbnail strip, or unrelated frame.
- Preserve evidence provenance: 素材明确展示 / 参考文档明确说明 / 根据上下文合理推断 / 策划人工补充 / 待确认.
- 多个可区分的武器、敌人、奖励、事件、状态或等级必须输出逐项内容清单；不得压缩成“存在多种”。
- 属性验收必须覆盖对象的完整研发配置面，而不是只列战斗基础值。若项目实际涉及，应分别核对：载具的基础属性、等级消耗、栏位状态和特权效果；武器的类型、解锁、局外养成、战斗属性；词条的归属、前置、等级上限、权重、显示文案、解锁等级、作用技能和效果参数；怪物的基础值、波次倍率、移动/攻击/承伤、免疫、类型、动作与子弹；刷怪的组间隔、点位类型、相对坐标、怪物组和数量。缺项必须判为未通过。
- 上述载具、武器、词条、怪物和刷怪字段属于知识储备，不得照搬到不相关项目；仅当素材、策划输入或机制关系证明该对象存在时，才生成对应清单。
- 精确配置表名、字段名、概率、默认值和公式只能来自参考文档、配置表或策划确认；截图只能证明可见内容和状态变化。
- 参数命名不得默认汇总成脱离机制语境的字段字典总表。行为正文解释发生方式与结果；就近命名映射说明业务名与实现字段的关系；配置表集中承载值、单位、范围；生命周期紧跟机制结尾。不得用集中字段字典总表替代这四种职责。
- 禁止为了控制篇幅省略规则。若完整描述超过单次输出长度，应自动分章节连续输出，而不是压缩颗粒度。
- When an acceptance or feedback spreadsheet exists, every row not explicitly marked accepted/验收无误 is a blocking obligation. Record its repair location, actionable remediation, real-browser result, and unique matching screenshot; do not infer completion from unrelated automated tests or reuse one screenshot across different cases.
- Decision-card options are text-first controls. Keep the radio/checkbox beside the option text, avoid forced wrapping for short labels, and verify real computed layout so global form styles cannot create empty space or displace the label.
- Internal parameter review schemas never authorize a generic table in the final PRD. A business table names the thing being configured and places units in the relevant column heading; prose owns meaning, causality, timing, constraints and lifecycle. Split one object into separate tables when different teams or operations fill them independently.
- Do not fill unsupported cells with invented numbers, official table names, or repeated “待配置”. Keep a fillable blank only when the configuration structure itself is an explicit deliverable; if alternative values change the design, create a decision card and keep export blocked.
- Short enums and identifiers such as `BOSS`, `BOSS点`, type names or IDs are allowed to appear in both prose and lookup tables. Carrier-duplication gates must target explanatory payload or concrete numeric facts, not these necessary labels.

## Output standard

Every applicable mechanism must state its entry condition, existing state, processing order, player choices, state changes, result, reset/persistence behavior, and evidenced limits or failures. Parameterized mechanisms must expose implementable fields. Calculated mechanisms must expose operands, order, modifiers, rounding, and an example only when values are confirmed.

玩法概述必须独立回答玩家目标、基础操作、核心循环、成长或资源驱动、胜败条件。载具、武器、角色、页面或组件的对象说明只能进入对应系统章节，不能替代玩法概述。

The final document uses the approved hierarchy and chapter semantics. The web workbench, diagrams, tables, and Feishu export must derive from the same confirmed structure.

## Production-depth system checklist

Use only the rows applicable to the current evidence; do not force these systems into unrelated projects.

- Vehicle/carrier: base attributes; level and upgrade cost/result; slots and capacity; default versus selectable slots; selection/removal constraints; displayed state; click behavior; privilege/unlock effects; reset scope.
- Weapon/skill: type inventory; damage/cooldown/target/range/duration properties; unlock and out-of-level growth; affix ownership, prerequisites, max level, weight, text parameters, affected skill/effect, and pool entry/removal.
- Enemy/NPC: spawn timing and groups; spawn-point roles and spatial offsets; movement; attack entry/exit; hit/death; health, attack, speed, range, interval, reduction, elemental modifier, dodge/block/immunity, type, and projectile references.
- Level: map composition and loop reuse; wave order and distance/time derivation; carrier points and speed changes; in-level level/experience; choice and reroll algorithms; buffs; statistics and formulas; time limit; speed toggle; success/failure settlement; external unlock/challenge/sweep.

Passing requires supported applicable dimensions to appear in natural prose, nearby field mappings, focused tables, or diagrams according to their role. It does not require copying sample chapter names, exact values, official table names, or irrelevant dimensions.
