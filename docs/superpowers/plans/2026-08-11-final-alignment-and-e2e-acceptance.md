# 最终颗粒度对齐与 P1–P7 验收实施计划

> **For agentic workers:** REQUIRED SUB-SKILLS: Use superpowers:executing-plans and project skill `executing-staged-acceptance` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. 每个阶段必须先提交验收用例供用户确认，再按确认用例自检并展示截图证据；只有用户明确回复“验收通过”才标记完成并进入下一阶段。

**Goal:** 完成决策卡全局化、玩法正文动态组织、飞书样例颗粒度门禁、当前任务迁移、P7 与完成度统一、P1–P7 端到端验收，并修复飞书反馈表中所有状态不是“验收无误”的问题。

**Architecture:** 使用规范化的玩法审核模型作为目录、正文、参数表、图解、预览和飞书输出的唯一内容源；使用统一的 `decisionCards` 契约承载真正多解的问题；使用一份完成度快照同时驱动顶部步骤、右侧状态、百分比和发布门禁。真实任务迁移采用“备份 → 干跑扫描 → 原子写回 → 重建衍生物 → 内容扫描”的顺序。

**Tech Stack:** Python 3.12、FastAPI、原生 JavaScript、Node test runner、pytest、SVG/飞书原生白板、JSON 任务存储。

## Global Constraints

- 不得把自动化测试通过等同于最终正文或真实页面验收完成。
- 不得覆盖策划已经确认或人工修改的目录、章节和规则。
- 参数、公式、配置字段和生命周期只能来自素材、参考文档或策划人工补充。
- 简单机制使用自然短文；复杂机制才展开配置表、公式、算例、边界和生命周期。
- 未选择的决策卡不得进入正式正文、画板、表格或最终文档。
- 当前任务修改前必须创建可恢复备份；迁移与重建失败时保留原任务。
- 每阶段完成后必须暂停等待用户验收，不自动进入下一阶段。
- 每阶段固定执行“实现但保持进行中 → 提交验收用例 → 用户确认 → 真实环境自检 → 截图举证 → 恢复测试数据 → 自动回归 → 展示证据 → 用户人工验收”；顺序和证据要求以 `skills/executing-staged-acceptance/SKILL.md` 为准。
- 飞书多维表格 `tbl4h5LG299VWgHg / vewRNAggZL` 是反馈范围的权威来源；所有状态不等于“验收无误”的记录均为必须修复项，不得按旧审计文档直接判定已满足。
- 反馈记录必须绑定对应截图或视频附件、复现步骤、代码修复、自动测试和用户验收结果；缺少任一项不得关闭。

---

### 阶段 0：反馈表权威清单与附件证据建档

**Sources:**
- Feishu: `https://hjjxo8h8vu.feishu.cn/wiki/MQOWwHokkimZakkoa2ycUGwZnib?table=tbl4h5LG299VWgHg&view=vewRNAggZL`
- Spreadsheet snapshot: `C:/Users/momoca/Downloads/ai策划 (1).xlsx`
- Attachment archive: `C:/Users/momoca/Downloads/ai策划_附件(1).zip`
- Create: `docs/qa/feedback-source-manifest-2026-08-11.md`
- Create: `docs/qa/feedback-open-items-2026-08-11.md`

**Known source state:**
- 当前 Excel 只包含 `数据表!A1 = 类型`，没有反馈记录，不能作为完整问题清单。
- 附件 ZIP 包含 13 张 PNG 和 1 段 MP4；文件位于归档内 `数据表/`，尚未与反馈行建立可靠映射。

**Interfaces:**
- Consumes: complete Feishu table rows with record identity, description, status and attachments.
- Produces: `feedback-open-items-2026-08-11.md`, containing every row whose normalized status is not exactly `验收无误`.

- [ ] 读取飞书多维表格或重新导出的完整 Excel，记录表格 ID、视图 ID、导出时间、总行数和字段名。
- [ ] 对状态字段做精确归一化；只排除状态严格为“验收无误”的记录，空状态、处理中、待验收、已修复等全部保留。
- [ ] 为每条保留记录分配稳定编号，记录原始描述、页面位置、状态、附件文件和复现条件。
- [ ] 解包 13 张 PNG 与 1 段 MP4 到只用于 QA 的证据目录，生成文件哈希并绑定对应记录；禁止按文件顺序猜测映射。
- [ ] 将每条问题路由到阶段 1–6 的具体修复项；无法分类的记录单独列出且不得遗漏。
- [ ] 比较仓库两个旧反馈审计文档，解释 9 条/10 条数量冲突；旧“已满足”结论不能作为关闭证据。

**用户验收方法：**

1. 打开生成的开放问题清单，核对总行数与飞书视图一致。
2. 随机抽查至少三条，确认描述、原状态和截图/视频附件对应正确。
3. 确认状态为“验收无误”的记录未进入修复队列；其他所有状态均进入。
4. 若 Excel 仍只有一个单元格，需要从飞书重新导出包含全部记录与字段的 `.xlsx`，再重复本阶段。

**通过标准：** 飞书所有非“验收无误”记录一条不少地进入开放问题清单，并与附件可靠绑定。

---

### 阶段 1：决策卡全局契约与审核入口

**状态：已由用户于 2026-08-11 明确验收通过。**

**Files:**
- Modify: `backend/gameplay_review_model.py`
- Modify: `backend/gameplay_review_service.py`
- Modify: `backend/gameplay_analysis.py`
- Modify: `js/gameplay-review.js`
- Modify: `js/gameplay-directory.js`
- Modify: `js/gameplay-diagrams.js`
- Modify: `js/gameplay-tables.js`
- Modify: `js/final-document-preview.js`
- Modify: `css/gameplay-review.css`
- Test: `tests/test_gameplay_review_service.py`
- Test: `tests/js/gameplay-review.test.js`
- Test: `tests/js/gameplay-directory.test.js`
- Test: `tests/js/gameplay-diagrams.test.js`
- Test: `tests/js/gameplay-tables.test.js`
- Test: `tests/js/final-document-preview-ui.test.js`

**Interfaces:**
- Consumes: `chapter.decisionCards[]` and canonical gameplay operation queue.
- Produces: `resolve_decision_card` and `skip_decision_card`; resolved planner claims consumed by every downstream renderer.

- [ ] 写失败测试：单选、多选、自填、推荐理由、依据、影响范围、跳过和未选择不进入正式内容。
- [ ] 运行定向测试，确认因各页面尚未接入决策卡而失败。
- [ ] 抽取共享决策卡呈现与操作载荷，接入目录、玩法规则、图解、表格和最终预览决策区。
- [ ] 后端原子应用选择并使相关章节、表格、图解和预览失效重建；跳过只保留未决状态。
- [ ] 运行决策卡相关前后端测试与全量前端测试。

**用户验收方法：**

1. 打开一个包含触发方式分歧的任务，依次进入 P1、P4、P5、P6、P7。
2. 确认卡片至少有两个具体选项、AI 推荐与理由、依据、单/多选说明、“自己填写”和“暂时跳过”。
3. 不选择时查看正文和 P7，问题不得显示成已确认规则。
4. 选择后刷新页面，选择仍存在；正文、相关表格和 P7 使用选择结果。
5. 选择“暂时跳过”，正式正文不得出现该结论。

**通过标准：** 所有入口使用同一张规范卡片；没有裸“待确认/未知待确认”；选择与刷新恢复一致。

---

### 阶段 2：玩法正文随机制动态组织

**状态：已由用户于 2026-08-11 明确验收通过。**

**最终验收口径：** 正文不得使用固定审核模板标题；短机制合并在业务大章节中，以精简段首组织且不重复列表；只有真实顺序使用编号；配置表不与正文重复；公式仅在有依据时出现；P7 与飞书使用同一份确认正文。

**验收证据：** `artifacts/stage2-recheck-browser-acceptance/`；最终前端回归 375/375，正文与飞书相关后端回归 45/45，正式任务 revision 134 未被测试数据污染。

**Files:**
- Modify: `backend/gameplay_rule_copy.py`
- Modify: `backend/gameplay_copy.py`
- Modify: `backend/gameplay_render.py`
- Modify: `backend/feishu_render.py`
- Modify: `js/final-document-preview.js`
- Test: `tests/test_gameplay_rule_copy.py`
- Test: `tests/test_gameplay_copy.py`
- Test: `tests/test_gameplay_render.py`
- Test: `tests/test_feishu_render.py`
- Test: `tests/js/final-document-preview-ui.test.js`

**Interfaces:**
- Consumes: confirmed `plannerSections`, evidence-backed optional modules, mechanism complexity.
- Produces: `compose_dynamic_chapter_sections(chapter)` shared by browser preview and Feishu rendering.

- [ ] 写失败测试：简单机制最多一至三个自然段；流程机制按执行顺序；配置机制按内容清单/规则/配置；计算机制仅在有依据时显示公式与算例。
- [ ] 运行测试并确认旧固定“概述/流程/规则/参数/验证/特殊情况”结构导致失败。
- [ ] 实现章节复杂度与证据模块分类，生成动态标题和段落序列。
- [ ] 浏览器 P7 与飞书渲染共同消费同一章节组合结果，删除审核状态兜底和机械空模块。
- [ ] 扫描输出，确保无重复标题、空模块、通用模板句和无证据公式。

**用户验收方法：**

1. 在 P7 连续打开至少三个不同类型章节：简单规则、顺序流程、含配置或公式的复杂机制。
2. 对比三个章节的标题数量、段落顺序和表格/公式模块。
3. 简单章节应短而完整；复杂章节才出现配置表、公式、算例、边界或生命周期。
4. 搜索正文，不得出现“本节规则已完成审核”“参与某机制计算的数值”“按实际配置”等无来源句。

**通过标准：** 三类章节结构明显不同，且每个出现的模块都有真实内容和来源。

---

### 阶段 3：飞书样例颗粒度与逐句来源门禁

**状态：进行中。须完成样例逆向研究、Skill 与门禁实现后，先提交阶段 3 验收用例，待用户确认后再执行正式自检。**

**Files:**
- Create: `docs/research/feishu-sample-sentence-provenance-2026-08-11.md`
- Create: `docs/research/feishu-sample-language-and-content-grammar-2026-08-11.md`
- Create: `data/calibration/gve16/sentence-provenance.json`
- Create: `data/calibration/gve16/document-grammar.json`
- Create: `skills/feishu-granularity-reasoning/SKILL.md`
- Create: `skills/feishu-granularity-reasoning/references/provenance-rules.md`
- Modify: `backend/feishu_prd_depth_contract.py`
- Modify: `backend/lead_planner_gate.py`
- Modify: `backend/gameplay_generation_quality.py`
- Modify: `backend/gameplay_analysis.py`
- Modify: `scripts/lead_planner_audit.py`
- Test: `tests/test_feishu_prd_depth_contract.py`
- Test: `tests/test_lead_planner_gate.py`
- Test: `tests/test_gameplay_generation_quality.py`
- Test: `tests/test_gameplay_quality_reference.py`

**Interfaces:**
- Consumes: 两份飞书样例原文与画板、截图/视频、参考文档、配置表、会议结论，以及项目 claims、parameter/formula evidence metadata 和 confirmed planner input。
- Produces: 逐句来源矩阵、作者推理规则、章节内容语法、语言组织语法、可复用 `feishu-granularity-reasoning` Skill，以及每章内容清单、配置字段、顺序、公式依据、边界和生命周期审计报告。

- [ ] 回读两份飞书样例的完整正文、表格和画板节点，保留章节层级、句子顺序和相邻视觉证据。
- [ ] 对每个有业务含义的句子标注来源类型：截图直接事实、视频时序、参考文档、配置表、会议/策划决定、上下文推断或无法溯源。
- [ ] 对所有“上下文推断”记录推断前提、推断步骤、排除的替代解释、可靠程度，以及作者为什么允许将其写成规则。
- [ ] 记录作者刻意省略的内容，区分“没有证据所以不写”“对制作无价值所以不写”“已由表格或画板承载所以正文不重复”。
- [ ] 逆向每个章节的内容选择逻辑：该部分必须回答什么问题、包含哪些事实类型、哪些信息进入正文/清单/表格/公式/算例/边界/生命周期、哪些内容由其他载体承担。
- [ ] 逆向作者的篇章组织逻辑：先目标还是先条件、先正常流程还是先配置、何时从概述下钻到执行顺序、何时把例外放在段末或独立小节、跨章节引用如何避免重复。
- [ ] 逆向作者的句子组织逻辑：主语选择、条件前置、动作与系统响应的排列、数值和单位的嵌入方式、确定事实与推断的措辞差异、标题粒度、列表并列规则和段落收束方式。
- [ ] 统计不同机制类别的章节长度、标题数量、段落密度、列表/表格使用条件和信息重复率；提取范围和选择条件，不把平均值变成固定模板。
- [ ] 从逐句矩阵归纳可迁移的推理算子，例如状态差分、前后帧因果、UI 文案到规则意图、配置字段到生命周期、异常画面到边界条件；禁止保留样例专属玩法名和数值。
- [ ] 使用一份非样例素材做双盲测：先只用推理算子生成事实模型，再只用内容与语言语法组织章节；分别检查越证据推断、内容缺漏、结构模板化和机器化措辞。
- [ ] 将通过盲测的规则写入 `skills/feishu-granularity-reasoning/SKILL.md`，并提供来源推理、内容选择、语言组织的正例、反例、停止条件和证据优先级。
- [ ] 写失败测试：有证据却遗漏所需颗粒度时阻断；没有证据时不得强行要求或生成模块。
- [ ] 实现逐句来源分类与六项颗粒度审计报告。
- [ ] 将审计接入生成后、P7 预览前和飞书发布前门禁。
- [ ] 输出策划可读的具体缺口，不暴露内部字段名。
- [ ] 使用两份样例研究结论复核门禁项目，不复制样例固定目录。

**用户验收方法：**

1. 先打开逐句来源矩阵，随机选择样例中的五句话，核对每句的直接依据、推断步骤和替代解释是否讲得通。
2. 再打开语言与内容语法，随机选择三个章节，核对为什么包含这些部分、为什么按这个顺序、为什么使用当前标题和句式。
3. 检查 Skill 的反例：截图只能证明页面存在时，不得推断隐藏公式、刷新规则或生命周期；短机制不得被强行扩成固定多节模板。
4. 检查双盲测章节，确认它同时迁移了样例的推理方法、内容选择方法和语言组织方法，但没有复制样例玩法名、字段、数值或固定标题。
5. 打开 P7 完整度检查，选择一个证据充足的复杂章节，确认实际适用的内容清单、配置字段、执行顺序、公式依据、异常边界和生命周期均可追溯。
6. 删除或清空一个有证据的关键字段，预览或导出应被明确阻止并指出缺哪一项；简单章节不适用的公式或配置不得被强制生成。

**通过标准：** 随机抽查的样例句均能解释“作者看到了什么、基于什么推断、为什么能这样写”；随机抽查的章节均能解释内容组成、标题、顺序、载体和措辞；Skill 双盲测可迁移推理与表达方法且不复制样例内容；门禁既拦截真实缺口，又不向无证据章节填模板。

---

### 阶段 4：当前任务安全迁移与衍生物重建

**Files:**
- Modify: `backend/gameplay_copy.py`
- Modify: `backend/gameplay_tables.py`
- Modify: `backend/review_preview.py`
- Create: `scripts/migrate_current_gameplay_task.py`
- Test: `tests/test_gameplay_copy.py`
- Test: `tests/test_gameplay_tables.py`
- Test: `tests/test_review_preview.py`
- Runtime data: `data/jobs/8312a91c89e144e6a59f81b982f14c06/job.json` when present; otherwise use the task ID verified from the current URL/job store.

**Interfaces:**
- Consumes: `migrate_gameplay_presentation(job, dry_run=True|False)`.
- Produces: timestamped backup, migration report, rebuilt tables and current-revision final preview.

- [ ] 只读扫描当前任务，确认真实任务 ID、版本、章节数、人工修改标记和历史模板命中项。
- [ ] 创建时间戳备份并校验备份 JSON 可读、任务 ID 一致。
- [ ] 干跑迁移，输出将删除、保留和重建的项目清单。
- [ ] 执行原子迁移，不覆盖策划人工修改；失败时恢复备份。
- [ ] 重建玩法表格、图解状态和完整预览，更新到当前 revision。
- [ ] 扫描任务 JSON 与可见预览，确认历史模板文本为零。

**用户验收方法：**

1. 使用原任务链接刷新，确认任务、截图、目录、已确认内容仍在。
2. 抽查三章，确认人工修改未丢失，旧通用参数和公式已消失。
3. 打开 P6，确认表格来自当前章节真实字段；打开 P7，确认预览是当前 revision。
4. 若有异常，可使用我提供的备份路径恢复。

**通过标准：** 数据不丢失、模板污染清零、P6/P7 衍生物与当前版本一致。

---

### 阶段 5：P7 内容结构与完成度单一数据源

**Files:**
- Modify: `backend/review_preview.py`
- Modify: `backend/gameplay_render.py`
- Modify: `backend/feishu_render.py`
- Modify: `js/final-document-preview.js`
- Modify: `js/feishu-publish.js`
- Modify: `js/backend.js`
- Test: `tests/test_review_preview.py`
- Test: `tests/test_gameplay_render.py`
- Test: `tests/js/final-document-preview-ui.test.js`
- Test: `tests/js/feishu-publish.test.js`
- Test: `tests/js/screenshot-backend.test.js`

**Interfaces:**
- Consumes: canonical interaction gate, gameplay gate, table/diagram decisions and preview revisions.
- Produces: `completionSnapshot` used by step badges, checklist, percentage and publish guard.

- [ ] 写失败测试：任一未完成项必须同时反映在顶部、右侧、百分比和导出按钮。
- [ ] 实现统一完成度快照，删除前端各处重复推导。
- [ ] 固定 P7 交互为“策划草图”画板；没有画板时阻止导出，不用普通正文代替。
- [ ] 玩法正文按确认后的真实系统与动态章节结构排列。
- [ ] 验证竞品为空时统一显示“本次未提供（可选，不影响导出）”。

**用户验收方法：**

1. 在一个章节未确认时进入 P7：顶部、右侧、百分比和导出按钮必须一致显示未完成。
2. 完成该章节并刷新：四处同时更新，不出现一处完成一处未完成。
3. 检查第一部分标题为“策划草图”且展示画板；玩法正文随后按当前系统排列。
4. 未上传竞品素材时，确认显示固定可选提示且不阻止导出。

**通过标准：** 所有完成度展示同源；P7 内容顺序与导出门禁一致。

---

### 阶段 6：P1–P7 真实端到端功能验收

**Files:**
- Modify as defects are found: `js/backend.js`, P1–P7 component files and corresponding backend endpoints.
- Modify: `scripts/qa-p1-p7-live.js`
- Modify: `scripts/audit-p1-p7-ui.js`
- Test: corresponding `tests/js/*.test.js` and `tests/test_*api.py` files for each reproduced defect.

**Interfaces:**
- Consumes: migrated current task and live local server.
- Produces: timestamped QA artifact directory with screenshots, action log and pass/fail matrix.

- [ ] 启动本地服务并用当前任务链接进入工作台。
- [ ] P1 检查目录编辑、保存、确认、刷新恢复和进入 P2。
- [ ] P2 检查截图归属、节点、跳转、互斥、保存和切换环节。
- [ ] P3 检查策划草图、滚动、缩放、全屏、重建和竞品空状态。
- [ ] P4 检查规则编辑、决策卡、保存、切章、焦点和滚动恢复。
- [ ] P5 检查图解必要性、审核推进、无图解状态和刷新恢复。
- [ ] P6 检查表格字段、行确认、分页、折叠和刷新恢复。
- [ ] P7 检查目录、正文、完成度、导出门禁和飞书操作状态。
- [ ] 为 P1–P7 每个可操作按钮建立“初始页面/前置状态/点击动作/唯一目标页面/预期状态变化/刷新后状态/返回后状态”记录；不得只验证按钮存在或 click 事件被触发。
- [ ] 逐一验证前进、返回、步骤栏、目录、章节切换和跨页入口，杜绝无响应、错误页面、重复跳转、循环跳转、携带错误任务 ID 或错误 UI 参数。
- [ ] 对拖动、节点移动、画板平移、缩放、目录滚动和表格折叠执行“操作后截图 → 保存 → 切页返回 → 刷新恢复”；杜绝移动后立即复位、切页复位、刷新丢失或不同页面互相覆盖状态。
- [ ] 对互斥选择、决策卡选择、审核推进和保存按钮验证重复点击、快速连点、失败重试与禁用状态，确保不会重复提交、回滚已确认内容或显示假成功。
- [ ] 对所有异步按钮验证加载中、成功和失败反馈；请求失败时必须停留在正确页面并保留用户输入，禁止静默失败或错误跳转。
- [ ] 使用当前真实任务完成一次受控飞书导出：先验证未完成时确实阻断，再完成门禁并导出，核对返回的飞书文档标识、文档顺序、策划草图白板、玩法正文、表格和最终状态；仅验证按钮可点击不算通过。
- [ ] 飞书导出后重新打开目标文档并与 P7 当前 revision 对照；导出失败、内容缺失、写入旧 revision、重复创建错误文档或状态未回写均判定阶段 6 失败。
- [ ] 每发现一个缺陷先写失败测试，再修复并重跑该页和全量回归。

**用户验收方法：**

1. 使用我提供的当前任务链接按 P1→P7 顺序操作。
2. 每页按验收矩阵逐项点击；重点检查按钮反馈、跳转、互斥、保存后刷新、滚动/缩放和返回。
3. 对照我提供的七张最终截图和操作日志确认页面与实际结果一致。
4. 在 P2/P3/P6 分别执行一次拖动或折叠，保存后切到其他页面再返回并刷新，确认位置和状态不会复位。
5. 从 P1 到 P7 分别使用页面主按钮、顶部步骤和返回入口各走一次，确认每条路径进入唯一正确页面且保留同一任务。
6. 在 P7 先制造一个未完成项确认飞书导出被阻止；修复后执行一次真实导出，并打开飞书目标文档核对最新正文与画板。

**通过标准：** P1–P7 矩阵无未处理失败项；每个按钮的目标、状态变化、失败反馈和刷新恢复均正确；移动、缩放、滚动、折叠不会意外复位；真实飞书导出成功且目标文档与当前 P7 revision、正文、表格和白板一致。

---

### 阶段 7：飞书反馈表逐条复核与最终交付验收

**Files:**
- Modify: `docs/feedback-audit-2026-08-11-final.md`
- Modify: `docs/qa/feishu-feedback-audit-2026-08-11-final.md`
- Modify tests and implementation only for feedback rows that fail live verification.
- Modify: `.claude/memory/memory.md`
- Modify: `.claude/memory/wiki.md`
- Modify: `.claude/memory/learnings.md`

**Interfaces:**
- Consumes: original 13-row feedback list, live QA artifacts, backend/frontend test evidence and content scan.
- Produces: one authoritative row-by-row acceptance table with evidence links and remaining risks.

- [ ] 重新读取阶段 0 建立的权威开放问题清单，统一两个旧审计文档中 9/10 条数量冲突。
- [ ] 每条反馈使用真实页面重新操作，不沿用旧“已满足”结论。
- [ ] 未满足项写失败测试、修复并重复该条验收。
- [ ] 只有原始状态为“验收无误”的记录可以免修；任何其他状态即使标记“已修复”或“待验收”，仍需本轮真实页面复验和用户确认。
- [ ] 运行全量前后端测试、编译、内容扫描和真实 P7 预览检查。
- [ ] 更新持久记忆，明确真实完成项和任何外部发布限制。
- [ ] 向用户提供最终人工验收清单；用户确认后才允许标记整体完成。

**用户验收方法：**

1. 按最终反馈表从第 1 条逐条点击证据链接和复现步骤。
2. 对每条记录“通过/不通过”；任何一条不通过都返回对应阶段修复。
3. 最后检查 P7 完整预览和一次受控导出流程。

**通过标准：** 反馈表每一行均有真实操作证据且用户确认通过；不存在以自动化测试替代人工验收的条目。

---

## 阶段 7 之后的最终工作台任务重构与飞书交付硬门禁

七个阶段全部由用户明确验收通过后，仍不得直接宣布整体完成，必须按以下顺序处理当前工作台正式任务 `8312a91c89e144e6a59f81b982f14c06`：

1. 从当前任务的最新规范化模型重新生成玩法目录、策划草图、玩法正文、图解状态、参数表和 P7 完整预览；不得沿用阶段执行前的缓存产物。
2. 扫描重构后的可见输出，确认没有历史模板、重复段落、无来源参数/公式、错误图解或旧 revision。
3. 先向用户提交重构后 P1、P3、P4、P6、P7 的完整截图、任务 revision、内容扫描和载体一致性证据，等待用户确认该任务输出可用于交付。
4. 用户确认重构输出后，执行一次真实飞书导出；不得以模拟调用、按钮可点击或本地 XML 生成代替。
5. 导出后重新打开飞书文档，回读并核对文档标识、最新 revision、章节顺序、策划草图白板、玩法正文、真实表格和发布状态。
6. 将飞书文档链接、回读结果和最终截图提交给用户验收；只有用户明确确认后才允许宣布整个任务完成。

**失败处理：** 重构或导出任一步失败，保留当前正式任务和迁移备份，修复后从重构步骤重新执行；不得导出旧版本或用已有飞书文档冒充本轮结果。

---

## 最终验证命令

```powershell
$env:PYTHONPATH='.runtime312;runtime_packages_pytest;.'
python -m pytest tests -q
node --test tests/js/*.test.js
python -m compileall -q backend tests scripts
git diff --check
```

最终还必须执行：当前任务内容污染扫描、P1–P7 live QA、P7 可见正文检查、飞书反馈表逐条人工复核，以及“阶段 7 后重新生成当前任务全部输出 → 用户确认 → 真实飞书导出 → 飞书回读核对”。任何一项没有新鲜证据都不能声称整体完成。
