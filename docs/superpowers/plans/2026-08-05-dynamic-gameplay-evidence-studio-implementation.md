# Dynamic Gameplay Evidence Studio Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a dynamically structured gameplay review model and evidence-led planner workspace whose depth matches GVE16 without copying a fixed game-specific directory.

**Architecture:** Extend the gameplay review model with editable systems, subsystems, and mechanisms while retaining stable chapter IDs as the review and publication seam. Generate structure in two confirmed stages, then enrich only confirmed mechanisms with evidence-backed rules, parameters, formulas, examples, and configuration sources. Render the same normalized model in the web workspace, diagrams, preview, and Feishu output.

**Tech Stack:** Python 3, FastAPI, plain JavaScript modules, CSS Grid, Node test runner, pytest.

## Global Constraints

- GVE16 defines document depth and completeness, not a fixed directory.
- Every detected gameplay system must reach the same production-ready completeness contract while using gameplay-specific fields and rules.
- Gameplay structure is generated from current material, reference documents, and planner-confirmed edits.
- Parameters, formulas, examples, configuration sources, and diagrams render only when supported by evidence.
- Desktop uses the three-column evidence studio; narrow screens switch between directory, evidence, and document without page-level horizontal overflow.
- Long Chinese content wraps naturally; no ellipsis truncation, fixed content height, overlap, or content clipping.
- Blue is reserved for current selection, focus, and primary actions; yellow is reserved for exceptions or planner decisions.
- Existing confirmed content is invalidated only when it depends on the changed structure or rule.
- Interaction and gameplay remain parts of the same final Feishu document.

---

### Task 1: Normalize a dynamic gameplay hierarchy

**Files:**
- Modify: `backend/gameplay_review_model.py`
- Modify: `backend/gameplay_review_service.py`
- Test: `tests/test_gameplay_review_model.py`
- Test: `tests/test_gameplay_review_service.py`

**Interfaces:**
- Consumes: existing `gameplayReviewModel.chapters` and stable `GCH-*` identifiers.
- Produces: `normalize_gameplay_structure(model: dict) -> dict`, `systems[]`, `subsystemId`, `systemId`, and structure operations accepted by `apply_gameplay_operations`.

- [ ] **Step 1: Write the failing hierarchy normalization test**

```python
def test_normalize_structure_groups_only_observed_chapters_and_preserves_ids():
    model = sample_model(chapters=[
        {"id": "GCH-001", "scope": "持续战斗", "systemName": "战斗与关卡", "subsystemName": "核心战斗"},
        {"id": "GCH-002", "scope": "升级选择", "systemName": "局内成长", "subsystemName": "升级选择"},
    ])
    normalized = normalize_gameplay_structure(model)
    assert [item["name"] for item in normalized["systems"]] == ["战斗与关卡", "局内成长"]
    assert normalized["chapters"][0]["id"] == "GCH-001"
    assert normalized["chapters"][0]["systemId"] == normalized["systems"][0]["id"]
```

- [ ] **Step 2: Run the focused test and verify RED**

Run: `python -m pytest tests/test_gameplay_review_model.py::test_normalize_structure_groups_only_observed_chapters_and_preserves_ids -q`

Expected: FAIL because `normalize_gameplay_structure` and hierarchy fields do not exist.

- [ ] **Step 3: Implement deterministic hierarchy normalization**

```python
def normalize_gameplay_structure(model: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(model)
    systems: list[dict[str, Any]] = []
    system_by_name: dict[str, dict[str, Any]] = {}
    for chapter in result.get("chapters", []):
        system_name = clean_name(chapter.get("systemName") or chapter.get("group") or "其他玩法")
        subsystem_name = clean_name(chapter.get("subsystemName") or system_name)
        system = system_by_name.get(system_name)
        if system is None:
            system = {"id": f"GSY-{len(systems) + 1:03d}", "name": system_name, "subsystems": []}
            system_by_name[system_name] = system
            systems.append(system)
        subsystem = next((item for item in system["subsystems"] if item["name"] == subsystem_name), None)
        if subsystem is None:
            subsystem = {"id": f"GSS-{sum(len(x['subsystems']) for x in systems):03d}", "name": subsystem_name, "chapterIds": []}
            system["subsystems"].append(subsystem)
        subsystem["chapterIds"].append(chapter["id"])
        chapter["systemId"] = system["id"]
        chapter["subsystemId"] = subsystem["id"]
    result["systems"] = systems
    return result
```

- [ ] **Step 4: Add structure edit and selective invalidation tests**

```python
def test_moving_one_mechanism_invalidates_only_its_dependent_output():
    model = model_with_two_confirmed_chapters_and_diagrams()
    changed = apply_gameplay_operations(model, [{
        "type": "move_chapter",
        "chapterId": "GCH-001",
        "systemId": "GSY-002",
        "subsystemId": "GSS-003",
    }], model["revision"])
    assert chapter(changed, "GCH-001")["confirmation"]["confirmed"] is False
    assert chapter(changed, "GCH-002")["confirmation"]["confirmed"] is True
```

- [ ] **Step 5: Run model and service tests**

Run: `python -m pytest tests/test_gameplay_review_model.py tests/test_gameplay_review_service.py -q`

Expected: PASS.

- [ ] **Step 6: Commit the hierarchy slice**

```powershell
git add backend/gameplay_review_model.py backend/gameplay_review_service.py tests/test_gameplay_review_model.py tests/test_gameplay_review_service.py
git commit -m "feat: add dynamic gameplay hierarchy"
```

### Task 2: Generate structure before detailed rules

**Files:**
- Modify: `backend/gameplay_analysis.py`
- Modify: `backend/server.py`
- Test: `tests/test_gameplay_analysis.py`
- Test: `tests/test_gameplay_directory.py`

**Interfaces:**
- Consumes: timestamped frames, visual analyses, reference documents, and `normalize_gameplay_structure`.
- Produces: `generate_gameplay_structure(...)`, directory checkpoint `system-directory-pending`, and confirmed structure input for detail generation.

- [ ] **Step 1: Write a failing dynamic-structure generation test**

```python
def test_structure_generation_does_not_inject_absent_weapon_or_enemy_systems(monkeypatch, tmp_path):
    configure_visual_response(monkeypatch, {
        "systems": [{"name": "拼图", "subsystems": [{"name": "拖放规则", "mechanisms": [{"name": "宝石归位", "sourceFrameIds": ["F0001"]}]}]}]
    })
    model = generate_gameplay_structure(job_with_frame("F0001"), tmp_path, vision_config())
    names = json.dumps(model["systems"], ensure_ascii=False)
    assert "拼图" in names
    assert "武器" not in names
    assert "敌人" not in names
```

- [ ] **Step 2: Run the test and verify RED**

Run: `python -m pytest tests/test_gameplay_analysis.py::test_structure_generation_does_not_inject_absent_weapon_or_enemy_systems -q`

Expected: FAIL because generation still returns a flat detailed chapter list.

- [ ] **Step 3: Add the structure-only prompt and parser**

```python
STRUCTURE_KEYS = {"systems", "name", "subsystems", "mechanisms", "sourceFrameIds", "reason"}

def generate_gameplay_structure(job, directory, config, progress=lambda *_: None):
    prompt = build_structure_prompt(job)
    raw = call_visual_model(prompt, job, directory, config)
    structure = validate_structure_response(raw, valid_frame_ids(job))
    return build_structure_model(structure)
```

The prompt must explicitly state: identify only systems evidenced by this material; game-design knowledge may suggest inspection targets but may not add facts; do not reuse sample directories.

- [ ] **Step 4: Add the two directory confirmation checkpoints**

```python
current.update(
    status="review",
    stage="请先确认玩法系统",
    checkpoint="system-directory-pending",
    gameplayReviewModel=structure_model,
)
```

After system confirmation, generate subsystem and mechanism candidates and set `checkpoint="mechanism-directory-pending"`. Detailed rule generation starts only after both checkpoints are confirmed.

- [ ] **Step 5: Verify recovery preserves approved structure**

Run: `python -m pytest tests/test_gameplay_analysis.py tests/test_gameplay_directory.py tests/test_resume_jobs.py -q`

Expected: PASS, including retry from either directory checkpoint without erasing prior confirmation.

- [ ] **Step 6: Commit the generation slice**

```powershell
git add backend/gameplay_analysis.py backend/server.py tests/test_gameplay_analysis.py tests/test_gameplay_directory.py tests/test_resume_jobs.py
git commit -m "feat: confirm gameplay structure before rule generation"
```

### Task 3: Enrich confirmed mechanisms with optional planner modules

**Files:**
- Modify: `backend/gameplay_analysis.py`
- Modify: `backend/gameplay_review_model.py`
- Modify: `backend/gameplay_rule_copy.py`
- Test: `tests/test_gameplay_analysis.py`
- Test: `tests/test_gameplay_rule_copy.py`

**Interfaces:**
- Consumes: confirmed `systems`, `subsystems`, chapters, evidence, and reference documents.
- Produces: `plannerSections`, `parameterSchema`, `formulae`, `workedExamples`, `configurationSources`, and evidence-level metadata.

- [ ] **Step 1: Write the failing optional-module test**

```python
def test_detail_generation_keeps_supported_formula_and_omits_empty_modules():
    chapter = normalize_generated_chapter({
        "name": "伤害计算",
        "formulae": [{"expression": "最终伤害 = 攻击属性 × 武器比例", "variables": ["攻击属性", "武器比例"]}],
        "workedExamples": [],
        "configurationSources": [{"title": "武器基础属性表", "field": "damageRatio"}],
    })
    assert chapter["formulae"][0]["expression"] == "最终伤害 = 攻击属性 × 武器比例"
    assert "workedExamples" not in chapter
    assert chapter["configurationSources"][0]["field"] == "damageRatio"
```

- [ ] **Step 2: Run the test and verify RED**

Run: `python -m pytest tests/test_gameplay_analysis.py::test_detail_generation_keeps_supported_formula_and_omits_empty_modules -q`

Expected: FAIL because those modules are not normalized.

- [ ] **Step 3: Implement evidence-backed optional module normalization**

```python
def keep_non_empty_modules(chapter: dict[str, Any]) -> dict[str, Any]:
    for key in ("parameterSchema", "formulae", "workedExamples", "configurationSources"):
        value = chapter.get(key)
        if not value:
            chapter.pop(key, None)
    return chapter
```

Every formula variable and parameter row must include `evidenceLevel` and either `sourceFrameIds` or `referenceSource`. Reject unsupported formulas instead of downgrading them to facts.

- [ ] **Step 4: Add copy tests separating gameplay rules from interaction evidence**

```python
def test_rule_copy_does_not_promote_interface_description_to_gameplay_rule():
    chapter = chapter_from_visual_claim("屏幕中央弹出三个卡片")
    result = build_planner_sections(chapter)
    assert "弹出三个卡片" not in result["summary"]
    assert result["evidenceNotes"][0]["text"] == "屏幕中央弹出三个卡片"
```

Add a cross-gameplay completeness matrix that covers representative, structurally different mechanics:

```python
@pytest.mark.parametrize(("mechanism_type", "required_concepts", "forbidden_concepts"), [
    ("combat", {"目标", "伤害", "受击结果"}, {"配方", "建造占地"}),
    ("crafting", {"材料", "合成条件", "产物"}, {"伤害乘区", "敌人仇恨"}),
    ("building", {"放置条件", "空间占用", "拆除"}, {"抽取保底", "伤害跳字"}),
    ("management", {"资源流入", "资源消耗", "结算周期"}, {"碰撞范围", "配方格"}),
    ("puzzle", {"操作对象", "合法步骤", "撤销或重置"}, {"武器比例", "生产队列"}),
    ("collection_pool", {"候选范围", "权重或概率", "重复获取"}, {"建造朝向", "攻击距离"}),
])
def test_each_gameplay_family_reaches_specific_planner_depth(mechanism_type, required_concepts, forbidden_concepts):
    chapter = generate_family_fixture(mechanism_type)
    rendered = json.dumps(build_planner_sections(chapter), ensure_ascii=False)
    assert all(concept in rendered for concept in required_concepts)
    assert all(concept not in rendered for concept in forbidden_concepts)
```

- [ ] **Step 5: Run enrichment tests**

Run: `python -m pytest tests/test_gameplay_analysis.py tests/test_gameplay_rule_copy.py tests/test_gameplay_review_model.py -q`

Expected: PASS.

- [ ] **Step 6: Commit the enrichment slice**

```powershell
git add backend/gameplay_analysis.py backend/gameplay_review_model.py backend/gameplay_rule_copy.py tests/test_gameplay_analysis.py tests/test_gameplay_rule_copy.py
git commit -m "feat: enrich confirmed gameplay mechanisms"
```

### Task 4: Build the evidence studio directory and evidence column

**Files:**
- Modify: `js/gameplay-directory.js`
- Modify: `js/gameplay-review.js`
- Modify: `css/gameplay-review.css`
- Test: `tests/js/gameplay-directory.test.js`
- Test: `tests/js/gameplay-review.test.js`

**Interfaces:**
- Consumes: normalized `systems`, subsystems, chapters, evidence frames, and existing workspace callbacks.
- Produces: semantic tree navigation, two-stage directory editor, persistent evidence column, and narrow-screen panel selection.

- [ ] **Step 1: Write the failing three-level directory rendering test**

```javascript
test("renders system, subsystem and mechanism labels without flattening", () => {
  const root = document.createElement("div");
  render(root, workspaceWithDynamicStructure());
  assert.equal(root.querySelectorAll('[data-gameplay-system]').length, 2);
  assert.equal(root.querySelectorAll('[data-gameplay-subsystem]').length, 3);
  assert.match(root.textContent, /战斗与关卡/);
  assert.match(root.textContent, /伤害计算/);
});
```

- [ ] **Step 2: Run frontend tests and verify RED**

Run: `node --test tests/js/gameplay-directory.test.js tests/js/gameplay-review.test.js`

Expected: FAIL because the rail renders only flat chapters.

- [ ] **Step 3: Render an accessible hierarchy and evidence column**

```javascript
function renderGameplayTree(root, model, selectedChapterId, onSelect) {
  const tree = el("nav", "", { "aria-label": "玩法目录" });
  (model.systems || []).forEach((system) => {
    const group = el("section", "", { "data-gameplay-system": system.id });
    group.append(el("h3", system.name));
    (system.subsystems || []).forEach((subsystem) => {
      const block = el("div", "", { "data-gameplay-subsystem": subsystem.id });
      block.append(el("h4", subsystem.name));
      subsystem.chapterIds.forEach((id) => block.append(chapterButton(model, id, selectedChapterId, onSelect)));
      group.append(block);
    });
    tree.append(group);
  });
  root.append(tree);
}
```

Evidence thumbnails use original aspect ratios and `object-fit: contain`. The selected screenshot remains visible while the planner reads or edits the mechanism.

- [ ] **Step 4: Add long Chinese and narrow-screen contract tests**

```javascript
test("long mechanism names remain readable and mobile exposes directory evidence and document tabs", () => {
  const root = renderLongChineseWorkspace();
  assert.equal(root.querySelector('[data-mobile-panel="directory"]').textContent, "玩法目录");
  assert.equal(root.querySelector('[data-mobile-panel="evidence"]').textContent, "参考画面");
  assert.equal(root.querySelector('[data-mobile-panel="document"]').textContent, "规则正文");
  assert.equal(root.querySelector(".gameplay-chapter-item").style.textOverflow, "");
});
```

- [ ] **Step 5: Run the frontend slice**

Run: `node --test tests/js/gameplay-directory.test.js tests/js/gameplay-review.test.js tests/js/review-workspace.test.js`

Expected: PASS.

- [ ] **Step 6: Commit the evidence-studio shell**

```powershell
git add js/gameplay-directory.js js/gameplay-review.js css/gameplay-review.css tests/js/gameplay-directory.test.js tests/js/gameplay-review.test.js
git commit -m "feat: build gameplay evidence studio"
```

### Task 5: Render document-style rules, parameters, formulas, and sources

**Files:**
- Create: `js/gameplay-document.js`
- Modify: `js/gameplay-review.js`
- Modify: `css/gameplay-review.css`
- Test: `tests/js/gameplay-document.test.js`
- Test: `tests/js/gameplay-review.test.js`

**Interfaces:**
- Consumes: a selected normalized chapter and existing edit callbacks.
- Produces: `renderGameplayDocument(root, chapter, workspace)` and content tabs that hide absent modules.

- [ ] **Step 1: Write failing module-visibility and formula tests**

```javascript
test("shows supported formula and hides absent parameter and example tabs", () => {
  const root = document.createElement("div");
  renderGameplayDocument(root, formulaOnlyChapter(), workspace());
  assert.match(root.textContent, /公式与算例/);
  assert.match(root.textContent, /最终伤害 = 攻击属性 × 武器比例/);
  assert.doesNotMatch(root.textContent, /字段与参数/);
  assert.doesNotMatch(root.textContent, /暂无参数/);
});
```

- [ ] **Step 2: Run the test and verify RED**

Run: `node --test tests/js/gameplay-document.test.js`

Expected: FAIL because `gameplay-document.js` does not exist.

- [ ] **Step 3: Implement document module rendering**

```javascript
function availableModules(chapter) {
  return [
    ["rules", "规则正文", chapter.plannerSections],
    ["parameters", "字段与参数", chapter.parameterSchema?.length],
    ["formulae", "公式与算例", chapter.formulae?.length || chapter.workedExamples?.length],
    ["sources", "配置来源", chapter.configurationSources?.length],
    ["decisions", "需要策划决定", chapter.unknowns?.length],
  ].filter(([, , present]) => present);
}
```

Parameter tables use semantic `<table>` markup and a local overflow wrapper. Formula blocks render expressions, variable definitions, calculation order, rounding, and only evidence-backed examples.

- [ ] **Step 4: Add interaction-state and accessibility tests**

```javascript
test("document tabs expose selected state and disabled save during mutation", () => {
  const root = renderDocumentWorkspace({ pending: true });
  assert.equal(root.querySelector('[role="tab"][aria-selected="true"]').textContent, "规则正文");
  assert.equal(root.querySelector('[data-action="save"]').disabled, true);
});
```

- [ ] **Step 5: Run document and workspace tests**

Run: `node --test tests/js/gameplay-document.test.js tests/js/gameplay-review.test.js tests/js/review-workspace.test.js`

Expected: PASS.

- [ ] **Step 6: Commit the document slice**

```powershell
git add js/gameplay-document.js js/gameplay-review.js css/gameplay-review.css tests/js/gameplay-document.test.js tests/js/gameplay-review.test.js
git commit -m "feat: render gameplay rules as planner document"
```

### Task 6: Keep web preview, diagrams, and Feishu output structurally aligned

**Files:**
- Modify: `backend/gameplay_render.py`
- Modify: `backend/feishu_render.py`
- Modify: `backend/feishu_publish.py`
- Modify: `backend/gameplay_diagrams.py`
- Test: `tests/test_gameplay_render.py`
- Test: `tests/test_feishu_publish.py`
- Test: `tests/test_review_preview.py`

**Interfaces:**
- Consumes: normalized dynamic systems and approved optional diagrams.
- Produces: identical heading order and rule conclusions across preview and Feishu, with diagrams attached only to their mechanism IDs.

- [ ] **Step 1: Write a failing cross-renderer alignment test**

```python
def test_preview_and_feishu_follow_confirmed_dynamic_heading_order():
    model = dynamic_model_with_formula_and_no_weapon_system()
    preview = render_gameplay_review(model)
    feishu = render_feishu_gameplay(model)
    expected = ["战斗与关卡", "战斗规则", "伤害计算", "局内成长"]
    assert headings(preview) == expected
    assert headings(feishu) == expected
    assert "武器系统" not in preview
    assert "武器系统" not in feishu
```

- [ ] **Step 2: Run renderer tests and verify RED**

Run: `python -m pytest tests/test_gameplay_render.py::test_preview_and_feishu_follow_confirmed_dynamic_heading_order -q`

Expected: FAIL because renderers iterate flat chapters independently.

- [ ] **Step 3: Share one ordered traversal helper**

```python
def iter_confirmed_gameplay_sections(model: dict[str, Any]):
    chapters = {item["id"]: item for item in model.get("chapters", [])}
    for system in model.get("systems", []):
        yield "system", system
        for subsystem in system.get("subsystems", []):
            yield "subsystem", subsystem
            for chapter_id in subsystem.get("chapterIds", []):
                chapter = chapters.get(chapter_id)
                if chapter and chapter.get("confirmation", {}).get("confirmed"):
                    yield "mechanism", chapter
```

Both renderers consume this helper and the same optional-module rendering policy. Interaction and gameplay remain in the same Feishu document.

- [ ] **Step 4: Verify diagram scoping and stale behavior**

```python
def test_structure_change_stales_only_diagrams_bound_to_changed_mechanism():
    changed = move_mechanism(model_with_two_diagrams(), "GCH-001", "GSS-003")
    assert diagram(changed, "GDI-001")["status"] == "stale"
    assert diagram(changed, "GDI-002")["status"] == "reviewed"
```

- [ ] **Step 5: Run publication regression tests**

Run: `python -m pytest tests/test_gameplay_render.py tests/test_feishu_publish.py tests/test_review_preview.py tests/test_gve16_native_whiteboard.py -q`

Expected: PASS.

- [ ] **Step 6: Commit the delivery slice**

```powershell
git add backend/gameplay_render.py backend/feishu_render.py backend/feishu_publish.py backend/gameplay_diagrams.py tests/test_gameplay_render.py tests/test_feishu_publish.py tests/test_review_preview.py
git commit -m "feat: align dynamic gameplay delivery"
```

### Task 7: Run full QA and deploy the updated LAN workspace

**Files:**
- Modify: `index.html`
- Modify: `.claude/memory/memory.md`
- Modify: `.claude/memory/learnings.md`
- Test: `tests/test_review_workspace_ui_contract.py`
- Test: `tests/js/review-workspace.test.js`

**Interfaces:**
- Consumes: all previous slices.
- Produces: cache-busted browser assets, durable project memory, passing full suites, and a verified LAN URL.

- [ ] **Step 1: Add the final UI contract test**

```python
def test_gameplay_workspace_contract_names_planner_concepts_and_omits_program_terms():
    html = Path("index.html").read_text(encoding="utf-8")
    js = Path("js/gameplay-review.js").read_text(encoding="utf-8") + Path("js/gameplay-document.js").read_text(encoding="utf-8")
    assert "玩法目录" in js
    assert "参考画面" in js
    assert "公式与算例" in js
    for forbidden in ("component", "undefined", "mechanismType", "schema-ready"):
        assert forbidden not in visible_copy(js)
```

Add a release gate that rejects a detected system when all of its mechanisms contain only a title or visual description and none contains production rules, data, dependencies, or acceptance content.

- [ ] **Step 2: Run focused backend and frontend suites**

Run: `python -m pytest tests/test_gameplay_analysis.py tests/test_gameplay_directory.py tests/test_gameplay_review_model.py tests/test_gameplay_review_service.py tests/test_gameplay_render.py tests/test_feishu_publish.py -q`

Run: `node --test tests/js/gameplay-directory.test.js tests/js/gameplay-review.test.js tests/js/gameplay-document.test.js tests/js/gameplay-diagrams.test.js tests/js/review-workspace.test.js`

Expected: PASS with zero failures.

- [ ] **Step 3: Run complete test suites**

Run: `python -m pytest -q`

Run: `$tests = Get-ChildItem tests\js\*.test.js | ForEach-Object FullName; node --test $tests`

Expected: both exit with code 0.

- [ ] **Step 4: Browser-check desktop and narrow layouts**

Verify at 1440px, 1280px, 900px, and 390px:

```text
No page-level horizontal overflow.
No ellipsis on gameplay titles or rule copy.
Original screenshots preserve aspect ratio.
Desktop shows directory, evidence, and document.
Narrow layout exposes all three through keyboard-accessible panel controls.
Loading, empty, generation failure, and save failure do not contradict each other.
```

- [ ] **Step 5: Record durable product rules and bump asset versions**

Update memory with the confirmed dynamic-directory rule, GVE16 depth rule, evidence-studio layout, and optional-module policy. Increment query versions for every changed JavaScript and CSS asset in `index.html`.

- [ ] **Step 6: Restart and verify LAN service**

Stop only the confirmed PID bound to port 8000, start the application with hidden window mode, then verify:

```powershell
Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:8000/' | Select-Object StatusCode
Invoke-WebRequest -UseBasicParsing 'http://192.168.50.67:8000/' | Select-Object StatusCode
```

Expected: both return `200`.

- [ ] **Step 7: Commit the verified release slice**

```powershell
git add index.html .claude/memory/memory.md .claude/memory/learnings.md tests/test_review_workspace_ui_contract.py tests/js/review-workspace.test.js
git commit -m "test: verify dynamic gameplay evidence studio"
```
