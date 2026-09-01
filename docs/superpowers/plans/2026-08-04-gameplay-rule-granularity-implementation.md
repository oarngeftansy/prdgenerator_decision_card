# 玩法规则颗粒度对齐 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让玩法章节和策划白板从截图复述升级为与用户飞书样例同颗粒度的策划规则，同时保持动态目录和同一份最终文档。

**Architecture:** 在视觉模型草稿与审核模型之间增加确定性的规则完整度整理层。底层保留完整机制字段和证据来源；工作台与飞书渲染器分别输出策划自然语言与必要的规则细节，不把后台字段名暴露给策划。

**Tech Stack:** Python 3.12、FastAPI、原生 JavaScript、pytest、Node test runner、飞书文档 XML 与原生白板。

## Global Constraints

- 两份既有飞书样例是章节组织、规则颗粒度和图文职责的验收基线。
- 目录必须按当前素材动态识别，不固化“武器系统”“敌人及首领”等章节。
- “触发、前置状态、分支、重置、边界”仅为后台完整性检查，不作为策划端标题。
- 策划端使用“一句话玩法、正常怎么玩、关键规则、数值配置、特殊情况、检查示例、还需要确认”。
- 截图只作为证据；方位、颜色、按钮、弹窗和单帧数字不能冒充玩法结论。
- 网页预览与最终飞书必须使用同一个结构化玩法模型。
- 不删除当前任务的九个章节、十五张证据图和已确认内容。

---

### Task 1: 规则完整度整理层

**Files:**
- Create: `backend/gameplay_rule_copy.py`
- Modify: `backend/gameplay_analysis.py`
- Modify: `backend/gameplay_review_model.py`
- Test: `tests/test_gameplay_rule_copy.py`
- Test: `tests/test_gameplay_analysis.py`

**Interfaces:**
- Consumes: `_validate_draft` 返回的章节草稿。
- Produces: `enrich_gameplay_draft(draft: dict) -> dict` 与 `planner_sections(chapter: dict) -> dict[str, object]`。

- [ ] **Step 1: 写失败测试，证明截图复述不能直接成为玩法正文**

```python
def test_enrichment_separates_visual_evidence_from_gameplay_rules():
    draft = fixture_draft(
        title="局内成长",
        mechanismType="random_pool",
        claims=[{"text": "屏幕中央弹出三个选项，底部显示刷新按钮", "sourceType": "material", "sourceFrameIds": ["F0002"]}],
        mechanism={"type": "random_pool", "description": "玩家升级后从三项强化中选择一项"},
    )
    chapter = enrich_gameplay_draft(draft)
    assert chapter["plannerSections"]["summary"] == "玩家在局内成长时选择一项强化，使本局能力发生变化。"
    assert "屏幕中央" not in chapter["plannerSections"]["normalFlow"]
    assert chapter["evidenceClaims"][0]["text"].startswith("屏幕中央")
```

- [ ] **Step 2: 运行测试并确认 RED**

Run: `python -m pytest tests/test_gameplay_rule_copy.py -q`

Expected: FAIL because `backend.gameplay_rule_copy` does not exist.

- [ ] **Step 3: 实现机制类型到策划表达的确定性映射**

`gameplay_rule_copy.py` 为 `core_loop`、`entity_behavior`、`formula`、`progression`、`random_pool`、`economy_reward`、`level_wave`、`buff_chain`、`settlement`、`external_entry` 与 `statistics_feedback` 生成：

```python
{
    "summary": str,
    "normalFlow": list[str],
    "keyRules": list[str],
    "specialCases": list[str],
    "acceptanceExamples": list[dict],
}
```

生成时优先使用 `mechanism` 的已知字段；只把包含界面、位置、颜色、按钮、弹窗或特效的声明放入 `evidenceClaims`。缺失字段不自动写“待确认”，只有会改变实现方案的未知项才保留。

- [ ] **Step 4: 加强视觉模型提示词**

要求模型在 `mechanism` 中返回机制类型对应的完整字段；每个验收示例包含 `scene`、`action`、`expected`；视觉表现仍写入 `claims`。继续允许批次重试和形状归一化，不因一个非关键字段缺失而丢弃整章。

- [ ] **Step 5: 将整理层接入草稿合并后和审核模型创建前**

在 `generate_gameplay_chapters` 中对 `_merge_drafts` 结果调用 `enrich_gameplay_draft`。在 `_chapter` 中保存 `plannerSections` 与 `evidenceClaims`，同时保留原始 `claims` 以兼容现有任务。

- [ ] **Step 6: 运行聚焦测试并确认 GREEN**

Run: `python -m pytest tests/test_gameplay_rule_copy.py tests/test_gameplay_analysis.py tests/test_gameplay_review_model.py -q`

Expected: PASS; 视觉证据仍保留，策划正文不包含截图方位描述。

### Task 2: 策划端章节与飞书正文

**Files:**
- Modify: `backend/gameplay_render.py`
- Modify: `js/gameplay-review.js`
- Modify: `js/gameplay-directory.js`
- Test: `tests/test_gameplay_render.py`
- Test: `tests/js/gameplay-review.test.js`
- Test: `tests/js/gameplay-directory.test.js`

**Interfaces:**
- Consumes: `chapter.plannerSections`。
- Produces: 相同章节顺序和规则内容的工作台与飞书正文。

- [ ] **Step 1: 写失败测试，锁定策划阅读顺序**

```python
def test_chapter_uses_planner_reading_order_without_internal_headings():
    xml = render_gameplay_document_sections(confirmed_job).xml
    assert xml.index("一句话玩法") < xml.index("正常怎么玩") < xml.index("关键规则")
    assert "前置状态" not in xml
    assert "重置方式" not in xml
    assert "素材依据" in xml
```

- [ ] **Step 2: 运行 Python 与 JavaScript 测试并确认 RED**

Run: `python -m pytest tests/test_gameplay_render.py -q`

Run: `node --test tests/js/gameplay-review.test.js tests/js/gameplay-directory.test.js`

Expected: FAIL because renderers still expose the old flat summary and parameter labels.

- [ ] **Step 3: 修改飞书章节渲染**

`_chapter_xml` 按以下顺序输出非空部分：一句话玩法、正常怎么玩、关键规则、特殊情况、检查示例、素材依据。配置参数仍汇总到文档末尾的“配置与参数”；未知项仍汇总到“待确认事项”。

- [ ] **Step 4: 修改工作台章节渲染**

默认只展示一句话玩法与正常玩法过程；关键规则、数值配置、特殊情况和检查示例采用按需展开。所有按钮和提示使用中文策划表达，不显示 `mechanismType`、字段键名或英文状态。

- [ ] **Step 5: 运行聚焦测试并确认 GREEN**

Run: `python -m pytest tests/test_gameplay_render.py tests/test_gameplay_directory.py -q`

Run: `node --test tests/js/gameplay-review.test.js tests/js/gameplay-directory.test.js`

Expected: PASS; 工作台与飞书的章节标题、摘要和规则顺序一致。

### Task 3: 策划白板自然语言投影

**Files:**
- Modify: `backend/planning_board_model.py`
- Modify: `backend/feishu_render.py`
- Modify: `backend/feishu_native_board.py`
- Test: `tests/test_planning_board_model.py`
- Test: `tests/test_feishu_sample_aligned_board.py`

**Interfaces:**
- Consumes: 已确认交互阶段与 `gameplayReviewModel.chapters`。
- Produces: 只显示页面与操作逻辑的自然语言规则卡，并通过章节标识关联玩法正文。

- [ ] **Step 1: 写失败测试，禁止后台术语出现在白板**

```python
def test_board_cards_use_natural_planner_sentences():
    board = build_planning_board_model(job)
    text = " ".join(item["text"] for stage in board["stages"] for item in stage["ruleCard"]["items"])
    assert "玩家升级后暂停战斗，并从三项强化中选择一项" in text
    assert all(word not in text for word in ("前置状态", "处理规则", "状态分支", "重置", "边界"))
```

- [ ] **Step 2: 运行测试并确认 RED**

Run: `python -m pytest tests/test_planning_board_model.py tests/test_feishu_sample_aligned_board.py -q`

Expected: FAIL because the board still renders four fixed internal labels.

- [ ] **Step 3: 将规则卡改为自然语言段落**

规则卡最多显示四条：什么时候来到这里、玩家可以做什么、不同选择会发生什么、离开后保留什么。字段缺失时合并成一句可读描述，不显示空标题；概率、公式和配置字段不进入白板。

- [ ] **Step 4: 保持网页 SVG 与飞书原生白板同源**

两个渲染器继续只消费 `build_planning_board_model`，不得自行拼接另一套规则。截图保持原比例，实线前进、虚线返回、黄色只表示真正影响决策的未知事项。

- [ ] **Step 5: 运行聚焦测试并确认 GREEN**

Run: `python -m pytest tests/test_planning_board_model.py tests/test_feishu_sample_aligned_board.py tests/test_gve16_native_whiteboard.py -q`

Expected: PASS; 两种白板输出的规则文字和阶段顺序一致。

### Task 4: 当前任务迁移、主策自检与服务恢复

**Files:**
- Modify through storage API only: `data/jobs/183261b4137e40a59596b3afcaad4f18/job.json`
- Test: `tests/test_history_access.py`
- Test: `tests/test_resume_jobs.py`

**Interfaces:**
- Consumes: 现有九章、十五张证据图和已确认目录。
- Produces: 使用新 `plannerSections` 的当前任务、可打开工作台和可生成飞书预览。

- [ ] **Step 1: 写迁移回归测试**

```python
def test_rule_copy_migration_preserves_confirmed_task_content():
    before = deepcopy(job["gameplayReviewModel"])
    migrate_gameplay_rule_copy(job)
    assert len(job["gameplayReviewModel"]["chapters"]) == len(before["chapters"])
    assert job["gameplayReviewModel"]["evidenceAnchors"] == before["evidenceAnchors"]
    assert [c["confirmation"] for c in job["gameplayReviewModel"]["chapters"]] == [c["confirmation"] for c in before["chapters"]]
```

- [ ] **Step 2: 运行迁移测试并确认 RED**

Run: `python -m pytest tests/test_history_access.py tests/test_resume_jobs.py -q`

Expected: FAIL before migration is wired into task loading.

- [ ] **Step 3: 通过存储接口原子迁移当前任务**

对已有章节补充 `plannerSections`，不重新调用视觉模型，不覆盖策划编辑内容，不改变目录顺序、确认状态和证据锚点。

- [ ] **Step 4: 运行完整测试**

Run: `python -m pytest -q`

Run: `node --test tests/js/*.test.js`

Expected: both commands exit 0 with zero failures.

- [ ] **Step 5: 进行主策视角自检**

逐章检查：标题是否属于实际玩法、是否能讲清正常玩法过程、关键选择和结果是否明确、参数是否可配置、特殊情况是否可执行、检查示例是否可复现、未知项是否真的需要策划决定。记录剩余问题并按阻塞交付、高风险误导、阅读体验三个优先级处理。

- [ ] **Step 6: 重启并验证局域网服务**

启动 Uvicorn 到 `0.0.0.0:8000`，验证当前任务 API、工作台 URL 和最终预览均返回 HTTP 200；进入页面后自动落到当前审核位置。

### Task 5: 玩法章节内联参考画面

**Files:**
- Modify: `backend/gameplay_review_model.py`
- Modify: `js/gameplay-review.js`
- Modify: `css/gameplay-review.css`
- Test: `tests/test_gameplay_review_model.py`
- Test: `tests/js/gameplay-review.test.js`

**Interfaces:**
- Consumes: `chapter.sourceFrameIds`、`chapter.evidenceClaims` 与 `gameplayReviewModel.evidenceAnchors`。
- Produces: `chapter.inlineEvidence`，每项包含 `anchorId`、`frameId`、`imageUrl`、`caption` 和原始尺寸；工作台默认展示前三项，其余按需展开。

- [ ] **Step 1: 写失败测试，锁定证据排序、去重和上限**

```python
def test_chapter_inline_evidence_selects_three_distinct_rule_supporting_frames():
    chapter = model["chapters"][0]
    assert len(chapter["inlineEvidence"]) == 3
    assert len({item["frameId"] for item in chapter["inlineEvidence"]}) == 3
    assert all(item["caption"] for item in chapter["inlineEvidence"])
```

- [ ] **Step 2: 运行 Python 测试并确认 RED**

Run: `python -m pytest tests/test_gameplay_review_model.py -q`

Expected: FAIL because chapters do not expose `inlineEvidence`.

- [ ] **Step 3: 构建章节证据视图**

按照章节 `sourceFrameIds` 的顺序关联证据锚点；优先选择被不同声明引用的截图，相邻重复帧去重。说明文字优先使用引用该图的第一条玩法声明，经过策划语言清理后输出；没有声明时使用“一句话玩法”。保存原图 `width`、`height`，不生成裁切尺寸。

- [ ] **Step 4: 写失败的工作台渲染测试**

```javascript
test("chapter shows three inline original-ratio images and folds the rest", () => {
  assert.equal(root.querySelectorAll(".gameplay-inline-evidence-image").length, 3);
  assert.match(root.textContent, /证明/);
  assert.match(root.textContent, /查看更多参考画面/);
});
```

- [ ] **Step 5: 实现内联图片、放大和更多证据**

在章节“一句话玩法、正常怎么玩”之后渲染前三张图片。图片使用 `width: 100%; height: auto; object-fit: contain`；按钮点击复用现有参考画面抽屉。第四张起放在默认关闭的 `details` 中，标题为“查看更多参考画面（N）”。图片错误只在当前卡片显示“画面加载失败，点击重试”。

- [ ] **Step 6: 运行聚焦与完整测试并重启服务**

Run: `python -m pytest tests/test_gameplay_review_model.py -q`

Run: `node --test tests/js/gameplay-review.test.js`

Run: `python -m pytest -q`

Run: `node --test tests/js/*.test.js`

Expected: all commands exit 0；当前任务仍为九章、十五张证据图，工作台页面返回 HTTP 200。
