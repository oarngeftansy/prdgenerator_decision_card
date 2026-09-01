# Findings

## Account-switch handoff
- Authoritative continuation file: `HANDOFF_NEXT_AGENT.md`.
- The current interaction run must use only frames from job `e6964af547fc4e28b3573f80d84a9b34`; the prior prototype's four frames belong to old job `328ba8dabecd4f8d98240589f25f50b3` and must not enter the final deliverable.
- Review hierarchy is semantic, not frame-count based: complete flow, stages, then a linear small flow or repeatable small loop inside each stage.

## Product objective
- Input: a 10–20 minute gameplay or interaction demonstration video.
- Output: a planning document matching the user-provided GVE16 gameplay/interaction examples.
- The two example videos are two levels of the same gameplay.

## Source capabilities
- ScreenCoder provides executable UI-region and component evidence extraction already connected through the backend adapter/pipeline.
- ai-website-cloner-template contains a detailed website decomposition, topology, component-specification, behavior replication, and visual-QA workflow; its original `clone-website` skill is not yet deployed under the project skill directories.
- `ultra-high-standard-prd` contributes deterministic identifiers, component trees, states, tokens, acceptance criteria, inference/default/TBD labeling, and machine-readable JSON structure.
- `prd-to-figma` contributes mapping rules for layouts, variants, prototype links, variables, and user-flow representation, but the supplied folder contains instructions only—not a runnable Figma plugin.

## Integration direction
- Use the PRD skills as a structured intermediate representation and optional downstream design handoff, not as a replacement for the human-readable GVE16 document.
- Keep evidence and inference separate so every planning conclusion can point back to timestamps/frames.
- Deploy canonical project skills to `skills/` and project-level callable copies to `.codex/skills/`.
- The current `backend/planner.py` emits a fixed 12-section Markdown document directly from scenes/frames. It lacks a stable intermediate planning model, deterministic entity IDs, explicit state/flow objects, and schema validation.
- The existing calibration parser already extracts headings, tables, rules, and whiteboard references from GVE16, so it is the correct upstream source for a learned output profile rather than duplicating sample parsing.
- Existing project skills already cover evidence extraction, temporal reconciliation, gameplay planning, interaction planning, calibration, and quality audit; the new deployment should compose them and fill schema/handoff gaps instead of cloning their responsibilities.

## 2026-07-24 GVE16 alignment correction
- User clarified that the final form must align to the GVE16 interaction-planning sample, and that "evidence chain/evidence frame" wording likely does not belong in the visible GVE16 document.
- Treat frame/time evidence as internal traceability and validation data. The final Markdown/Feishu surface should use GVE16-native planning language such as scenes, task flow, page/component hierarchy, interaction events, state transitions, component rules, feedback, exceptions, pending confirmations, acceptance, and quality audit.
- PRD-to-Figma concepts are allowed only when they help enforce structure behind the scenes; do not introduce Figma-style visible sections such as pageList, designTokens, prototype links, or design-token pages.

## Quality concern
- Both incoming `SKILL.md` files appear to contain mojibake in Chinese text. Their schemas remain legible, but the instructions need encoding normalization before deployment.
- A repository-wide `rg` inspection returned exit code 1 despite useful matches, likely because some requested root globs did not exist; no project state was changed.
- The official `quick_validate.py` uses the Windows locale when `PYTHONUTF8` is unset. It validated 8 packages, then raised `UnicodeDecodeError` on 4 UTF-8 Skill files; project tests read all packages explicitly as UTF-8. Re-run the validator with `PYTHONUTF8=1`.

## Deep user audit
- Real job: upload a long gameplay/interaction video and receive a trustworthy GVE16 planning document that can be corrected and handed to design/implementation.
- Immediate issue fixed: the UI previously implied no standard was active when no sample was selected. GVE16 is now always injected; selected samples are additive calibration only.
- Remaining pain: a user can enter only an API key for the built-in Qwen profile, but an arbitrary provider cannot be inferred reliably from a key alone. A provider catalog or explicit base/model remains necessary for non-Qwen services.
- Remaining pain: automated tests validate both modes offline, but final fidelity to the two real videos still depends on a successful paid vision-model run and side-by-side sample scoring.
- Larger bet: once Feishu/Figma connectors are callable, consume `designHandoff` and persist external artifact IDs rather than regenerating flow semantics downstream.

## Minimality review
- No new runtime dependency was added.
- The intermediate model is one focused module and reuses existing evidence, calibration, audit, and rendering code.
- Dual Skill copies are intentional because the website runtime and project-level Codex require separate discovery roots.

## Low-confidence repair loop discovery
- The browser already captures frames locally through `captureVideoFrame(url, second)`.
- The backend already supports full-job and scene-level reanalysis, but has no frame-window endpoint.
- Review edits persist through `/api/jobs/{job_id}/review`; local reanalysis must preserve planner-edited fields instead of replacing them silently.
- The current 22-frame attention set is driven by low confidence, conflict, or missing critical fields; ordinary unknown notes do not contribute.
- The reason UI is already a pure frontend projection, so specific reason classification can remain deterministic while a backend-provided `attentionSignals` list supplies observed evidence problems.
- `analyze_video()` always performs scene analysis plus a globally sampled detail pass; calling it for a tiny frame window would unnecessarily rewrite the scene and may overwrite reviewed fields.
- Backend extraction already has reusable primitives (`_read_at`, ScreenCoder adapter, perceptual hash), but the public extractor only supports a full sample list and rebuilds scenes/tracks.
- Existing scene reanalysis replaces entire analyzed frame objects and therefore does not protect planner edits; the new local flow needs an explicit merge policy.
- Frames not chosen for the 60-frame detail pass are marked with `unknowns: ["该帧继承场景摘要，未进行独立视觉模型分析。"]`; this is a strong specific reason for many low-confidence frames.
- On the real task, F0002 now correctly explains `关键操作可能发生在两帧之间` and `操作结果没有画面证明`, replacing the generic warning.
- The local extraction succeeded and persisted five ordered supplemental images without changing the 138 main frames. The configured browser session did not supply a usable visual-model credential to the new request, so the model phase exercised the designed failure/retry state.
# 2026-07-22 UE 画板偏差根因

- 当前实现把 UE 画板固定渲染为 Mermaid 文本流程图；样例则以真实截图为主节点，以 section 分区，并用连接器表达推进、分支和回环。
- 旧测试只检查画板存在、非空以及包含文本边，无法发现视觉结构完全不一致。
- 旧发布规格明确把 SVG/白板 DSL 延后，导致“测试通过”与“样例复刻”目标冲突。
- 修复必须先改变验收契约：截图节点、阶段分区、操作/反馈/条件文案、主路径和回环缺一不可；先以一个小切片达到 90 分，再推广到完整视频。
# 2026-07-23 Feishu whiteboard image render fix

- Successful reference doc `ZNWkd0Ke3oZCtAxDQA5ckxonnJS` uses whiteboard `TbCdwRIiphN9nhbOtSWcWkLMnEz`; its rendered screenshot nodes are normal OpenAPI `image` nodes with 27-character Feishu media tokens and non-zero dimensions.
- Failed target writes used SVG/data-uri payloads or non-whiteboard media tokens as `image.token`. SVG import created invisible image nodes with `width: 0`, `height: 0`, and `image.token` containing embedded SVG/data-image text.
- Correct upload path is `docs +media-upload --parent-type whiteboard --parent-node <whiteboard_token> --doc-id <doc_token> --file <local_image> --as user`; this returns a whiteboard-scoped `file_token` usable in raw `image.token`.
- Target whiteboard `XTlEwvcxohLp9QbnpR3c9SpOnhf` now renders all seven annotated screenshots after uploading media to the whiteboard parent and adding token-backed image nodes.

# 2026-07-24 Feishu representative-frame boundary

- Feishu document output must contain no evidence/reference-frame section. Evidence frames remain local analysis material only.
- UE flow whiteboards use one representative frame per confirmed event/step. When `loopHierarchy` is absent, fall back to `planningModel.events[].evidence[0].sourceId`, deduplicated in event order.
- Real 137-frame job `faaf4c2d8cb24e9b940067577d3b46ef` resolves to exactly seven board frames: F0007, F0021, F0043, F0064, F0081, F0111, F0136.
- Repaired document `Zk2Xdzlapo1DM6xFsd0cmCBvnqe` by overwriting the body, then uploading whiteboard-scoped media and adding raw token-backed image nodes. Read-only verification found zero reference headings/old frame anchors and exactly seven raw image nodes.

## 2026-07-24 built-in API visibility
- The public config correctly reported `hasBuiltInApi: true`, but the frontend only collapsed the editable API panel; users could reopen it and still see API Key/Base URL/model fields.
- Product rule: when the backend supplies the built-in API, the entire editable API panel stays hidden. Maintainers change provider/model in project configuration rather than through the shared experience page.
# 2026-07-24 成功飞书文档与画板反向分析

- 成功文档 `TVnddRv6FoGFE0xTSMkcKNSunpc` 的正文顺序为：定位 callout → 需求概述 → UE 流转图说明与真实 `<whiteboard token>` → 完整交互循环 → 分环节规则表 → 待确认 callout → 状态与异常 → 验收项 → 证据索引。
- 137 帧只作为底层证据；正文明确声明使用 7 张关键状态图。画板承担代表画面与编号规则的主要呈现，不把所有帧逐张铺进文档。
- 成功画板 `XTlEwvcxohLp9QbnpR3c9SpOnhf` 预览呈现：完整大循环、三个环节、7 张代表截图、10 个红色编号、实线正向箭头、虚线回环、黄色待确认说明。
- 真正让截图显示成功的条件：`docs +media-upload --parent-type whiteboard --parent-node <board> --doc-id <doc> --file <relative>` 返回白板作用域 27 位 token；随后写入 `type=image` 且宽高非零的 raw 节点。
- 不能只按预览判成功：raw 中共有 15 个 image 节点，只有 8 个非零尺寸，且有重叠坐标，说明历史失败写入留下了零尺寸/重复节点。新 Skill 必须在交付前检查零尺寸图片、重复坐标、代表帧数量和 token 唯一性，并在不合格时重建干净画板。

## 2026-07-24 三层参考标准与 FlowDoc 取舍

- GVE16 是总体策划颗粒度与表达标准：大流程、环节、组件/区域、操作条件、系统反馈、结果状态和异常。
- `TVnddRv6FoGFE0xTSMkcKNSunpc` 是正文格式基准，不被原型文档的简版正文替代。
- `ZNWkd0Ke3oZCtAxDQA5ckxonnJS` 是 UE 流转图逻辑基准。其画板包含 2 个真实 Section、8 个非零尺寸 token-backed 图片节点、1 条实线进入箭头和 1 条虚线返回箭头。
- FlowDoc 可复用“先审整体流程，再审局部页面/区域/元素”的审核层级、截图框选编辑、跳转去重、主交互默认筛选、条件分支和撤销/重做；其 Figma 工程文档与视觉风格不替代 GVE16。
- FlowDoc 审核层还必须明确四类视图及可编辑边界：全流程视图修改环节和跨页跳转；环节视图修改区域与规则；组件视图修改热点边界和组件字段；导出预览视图只读验收并返回对应层级修正。
- 用户修改优先于后续 AI 重分析；视图切换只改变信息密度，所有编辑回写同一份 GVE16 中间模型。

## 2026-07-27 截图优先输入决策

- 产品方向改为截图主导：用户选择文件夹并上传 2–30 张有序截图；视频只补充动效、过渡和缺失信息。
- 目录只读取第一层；文件名不强制数字前缀，使用自然排序并允许用户拖拽或键盘调整。
- 现有前端已经能读取多张图片并在浏览器生成帧，但入口文案仍只写视频、无视频时分析按钮被禁用，正式后端任务也只接受一个视频。
- 为保留任务历史、重新分析和飞书导出，图片组必须进入正式后端任务，而不是只走浏览器降级分析。

## 2026-07-27 GVE16 审核工作台决策

- FlowDoc 只决定如何筛选、框选、定位和确认；最终内容仍由 GVE16、`TVnd...` 和 `ZNWk...` 三层标准约束。
- 一期采用上传页与全宽审核工作台分离、横向环节泳道、截图与规则并排，以及只读导出预览；独立组件视图留到二期。
- 流程关系统一建模为转换，而不是全部称为点击跳转。点击型拥有可拖动锚点；动画结束、媒体结束、系统事件和条件满足等自动转换没有点击位置。
- 生成流程图前必须按来源环节筛选 AI 候选转换；未保留的候选不进入流程图。
- 环节视图一期即支持组件框创建、移动、缩放、红色编号和规则同步绑定；内部稳定 ID 与显示编号分离。
- 完整 GVE16 还需要每个环节的小循环、一至三张代表状态图、组件状态矩阵、跨状态约束/黄色说明、可测试验收项和合格 AI 草稿门槛。
# 2026-07-28 最新版 GVE16 文档发现

- 最新基准文档：`THLgdhhtIomhh4x2osacalc8nAf`，读取时 revision 为 `9528`。
- `UE流转图` 章节包含三个原生画板：`UX设计`、`策划草图`、`竞品参考`。三者是不同信息源，不应合并成同一职责：UX 是完整界面信息架构/跳转参考，策划草图是策划状态与操作链，竞品参考只用于机制和表现参照。
- 正文独立规则域包括 `叙事`、`引导`、`红点提示`。叙事需要触发场景、触发节点、播放后续流转；引导需要触发范围/次数、前置条件、步骤、指向组件、提示文案与完成去向；红点需要显示条件、消去条件和逐层穿透路径。
- `叙事` 当前样例包含关卡内 SD 小人、关卡内拍脸、BOSS 气泡，以及进入关卡/通关后两个触发节点类型。
- 画板预览与 raw 节点已只读保存到 `artifacts/latest-gve16-reference/`，该目录保持未跟踪状态。
- 第一次读取失败是 PowerShell 执行策略阻止 `lark-cli.ps1`；改用既有的 `lark-cli.cmd` 后成功，不需要重新授权。

# 2026-07-28 规则域扩展决策

- 规则域审核独立位于环节全部确认和导出预览之间，避免把跨环节规则塞进单个环节长表单。
- 叙事、引导、红点三个域始终出现在审核和正文；无素材依据时显示“本次素材未展示，待确认”。
- 非结构性待确认允许导出，但用户必须确认已经审核规则域；引用损坏和红点路径断裂仍是阻断错误。
- 策划草图自动生成；UX设计和竞品参考使用可选独立素材，不参与主视觉分析，不冒充策划证据。
- 最新 GVE16 的三块画板是三个独立原生 whiteboard，发布层需要从单画板检查点扩展为三画板检查点。

# 2026-07-28 实施计划边界

- 保持审核模型 `schemaVersion=2.0`，用 additive backfill 兼容已有本地历史，避免一次无收益的版本迁移。
- 规则文本通过现有 revisioned operations/undo 栈保存；UX/竞品二进制素材走独立 multipart API，不进入文本撤销栈。
- 素材 API 挂在现有 `/review-model` 路由下，确保 `ReviewClient.request` 的路径和错误处理保持一致。
- 渲染层返回按 `ux/planning/competitor` 排序的 named boards；发布层使用按 board key 分隔的结构、媒体和验收检查点。

# 2026-07-28 Task 6 双画板交互合同

- 已核验交互参考飞书 Wiki `ZsTVw7lTEi9rErknL9bcRfFunei`，revision 40；采用兼容策略 A（compatibility strategy A）。
- 活跃交互画板顺序为 `planning → competitor`：planning 146 (58 image/54 composite/30 connector/4 sticky)，competitor 26 image。
- 本记录不包含白板 token、凭证或其他密钥。

# 2026-07-28 Gameplay research boundary

- Interaction delivery is complete and remains exactly `planning -> competitor`; gameplay research must not reopen that export contract.
- Product journey is sequential: interaction review first, then gameplay review.
- Gameplay input uses ordered key screenshots as anchors and video as supporting evidence. Only adjacent intervals around a key screenshot are inspected when the screenshot alone cannot reveal trigger, transition, duration, or result.
- Gameplay review is text/structure-first and does not present source screenshots. Diagrams are generated only for chapters that materially need a visual explanation.
- Each generated diagram has its own feedback box and independent revision loop.
- Gameplay checkpoints are chapter-level and mechanism-specific. Parameter fields must be selected from the observed mechanic, not copied from a universal template.
- Primary samples: Maze Development Story execution document and latest GVE16 excluding UE flow. Optional method sources: `donchitos/claude-code-game-studios` and `bkingfilm/lapian-notes`.
- Supporting video `主线1.mp4` opens successfully through the existing OpenCV runtime: 540x1166 portrait, ~30 fps, 7,457 frames, ~248.57 seconds. This length reinforces targeted adjacent-window sampling rather than full-video analysis.
- Repository research conclusion: reuse Game Studios' typed mechanism parameters, dependency mapping, independent review verdicts, and phase gates; reuse Lapian's timestamped evidence IDs, schema-validated imports, and coarse-to-fine deep dives.
- Do not copy the simulated 49-agent hierarchy, global gate modes, narrative-first film ontology, or one-frame-per-second bulk sampling.
- Neither repository supplies the required pre/post-roll adjacency contract, claim-level evidence coverage, interaction-first chapter gate, or per-diagram feedback/regeneration state. These are first-party product requirements.
- Minimum durable gameplay entities identified: `EvidenceAnchor`, `GameplayChapter`, `MechanismSpec`, `CheckpointReview`, `GeneratedDiagram`, and `DiagramFeedback`.
- Maze document taxonomy is mechanism-centric: gameplay overview; backpack/refresh/edit mode; monsters/heroes/projectiles/player; currencies/materials; common level rules; drops; special levels; special wallet monster.
- Maze chapters mix four information layers that the tool must separate during review: observable player loop, deterministic rules/state transitions, typed configuration/formulas, and implementation/resource fields.
- Diagram demand is not universal. Backpack/refresh uses spatial fit and drag-state diagrams; general level flow uses phase/state diagrams; special combat scaling uses formula/range tables. Ordinary actor attributes and currency rules are better reviewed as structured text/tables.
- The Maze reference itself embeds several native whiteboards in spatial/flow-heavy chapters, supporting optional generated diagrams at chapter level rather than routine screenshot display.
- 2026-07-29 GVE16 representative gameplay reads: `武器栏` is a finite-capacity/irreversible-selection state model (1 fixed + 4 optional slots, empty/filled click branches, affix count and cooldown display); `武器词条` is a typed progression/random-pool contract (weapon type, affix group, prerequisites, max level, weight bonus, effect targets/parameter mutation); `怪物行为` is a wave-spawn and combat state machine (ordered groups, ms interval, relative XY spawn points by class, move/attack range transition, hit/death). These three chapters use tables/text plus only supporting screenshots; generated diagrams should be reserved for slot state, spawn topology, or behavior state transitions when review ambiguity exists.
- GVE16 `战斗计算/关卡波次/获取武器词条` confirm three distinct gameplay checkpoint schemas: formulas must name inputs/coefficient source and worked validation; waves require ordered phase/distance/spawn/vehicle/reward parameters plus timing calculation; random-choice systems require eligibility, ordered without-replacement draw, multi-step weights, temporary result, confirm/reroll branches, cost tiers, reset lifetime, and pause/resume state. The affix section uses 5 screenshots but no whiteboard; a deterministic probability/decision diagram would materially help review, while screenshots remain optional evidence rather than the gameplay review surface.
- GVE16 settlement/external-level rules require separate checkpoints for failure/win predicates, reward accumulation boundaries, statistics carry-over, context-specific messaging, linear challenge eligibility, entry-time stamina spending/non-refund, and sweep unlock/highest-cleared-only/reward aggregation. These are state/rule tables; they do not inherently require generated imagery.
- Maze document outline confirms a broader mechanism-centric taxonomy than GVE16: core loop; spatial backpack/refresh/edit mode; actors/projectiles/player; currencies/materials/items; common level flow/drop refresh; special levels/modes; special wallet monster. It mixes observable play, formulas, config tables, resource fields, and implementation details inside large sections, so the tool must normalize those into distinct review checkpoint layers instead of reproducing the source headings verbatim.
- Final export boundary confirmed: create one complete Feishu execution document, with approved UE planning/competitor content first and reviewed gameplay chapters afterward; do not create separate interaction and gameplay documents.
