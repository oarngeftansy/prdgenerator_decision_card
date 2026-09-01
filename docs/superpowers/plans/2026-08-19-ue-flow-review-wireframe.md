# UE Flow Review Wireframe Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 生成一个独立的 `线框图.html`，准确模拟“言灵镜瞳”原审核台新增 P3“UE 流转图审核”后的页面结构、只读审核交互和阶段顺序。

**Architecture:** 线框稿是单文件静态原型，不接真实接口、不修改原工作台。HTML 内嵌必要 CSS 与 JavaScript，复用原审核台的三栏布局和视觉语言，通过固定示例数据演示节点选择、连线选择、缩放、阻塞状态、返回 P2 与进入 P4 的交互反馈。

**Tech Stack:** HTML5、原生 CSS、原生 JavaScript、Playwright 浏览器验收。

## Global Constraints

- 线框稿必须表现为原“言灵镜瞳”审核台中的新增阶段，不得创建新的正式产品域或独立发布台视觉。
- 阶段顺序固定展示为 `P2 交互流程审核 → P3 UE 流转图审核 → P4 交互交付物预览`，后续阶段顺延。
- UE 图只读；修改入口只能返回 P2，线框内不得提供拖动节点、修改连线或新增页面功能。
- UE 流转图与策划草图职责分离：UE 图定义页面流转；P4 定义单页交互与表现。
- 线框稿不修改后端、真实路由、`job.json`、P1–P7 状态或飞书文档。
- 最终飞书 UE 流转图必须使用原生飞书画板；线框稿需在说明区明确这一交付合同。

---

### Task 1: Freeze the original review-shell vocabulary

**Files:**
- Read: `index.html`
- Read: `css/review-workspace.css`
- Read: `js/flow-review.js`
- Read: `js/final-document-preview.js`
- Create: `artifacts/ue-flow-review-wireframe-2026-08-19/shell-contract.json`
- Test: `tests/test_ue_flow_wireframe.py`

**Interfaces:**
- Consumes: existing top-step labels, panel class vocabulary, P2 transition fields, P4 delivery-preview title.
- Produces: `shell-contract.json` with `stageLabels`, `leftPanel`, `canvasControls`, `detailFields`, and `footerActions` used by the static wireframe audit.

- [ ] **Step 1: Write the failing shell-contract test**

```python
def test_wireframe_shell_contract_matches_original_workspace():
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert contract["stageLabels"][1:4] == [
        "P2 交互流程审核", "P3 UE 流转图审核", "P4 交互交付物预览"
    ]
    assert contract["footerActions"] == [
        "返回 P2 修改", "重新生成", "确认 UE 流转图并进入 P4"
    ]
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```powershell
$env:PYTHONPATH='.;runtime_packages_pytest'
& 'C:\Users\momoca\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/test_ue_flow_wireframe.py::test_wireframe_shell_contract_matches_original_workspace -q -p no:cacheprovider --basetemp .pytest_tmp_ue_wireframe_red
```

Expected: FAIL because `shell-contract.json` does not exist.

- [ ] **Step 3: Create the exact shell contract**

```json
{
  "stageLabels": [
    "P1 玩法目录",
    "P2 交互流程审核",
    "P3 UE 流转图审核",
    "P4 交互交付物预览",
    "P5 玩法规则审核",
    "P6 图解与参数审核",
    "P7 最终文档"
  ],
  "leftPanel": "流程目录",
  "canvasControls": ["缩小", "放大", "适应画布", "定位当前节点"],
  "detailFields": ["来源页面", "目标页面", "触发方式", "成立条件", "系统反馈", "操作结果", "证据来源"],
  "footerActions": ["返回 P2 修改", "重新生成", "确认 UE 流转图并进入 P4"]
}
```

- [ ] **Step 4: Run the test and verify GREEN**

Run the command from Step 2.

Expected: `1 passed`.

- [ ] **Step 5: Commit**

```powershell
git add tests/test_ue_flow_wireframe.py artifacts/ue-flow-review-wireframe-2026-08-19/shell-contract.json
git commit -m "test: freeze UE flow wireframe shell"
```

### Task 2: Build the single-file interactive wireframe

**Files:**
- Create: `artifacts/ue-flow-review-wireframe-2026-08-19/线框图.html`
- Modify: `tests/test_ue_flow_wireframe.py`

**Interfaces:**
- Consumes: `shell-contract.json` terminology and the confirmed read-only review behavior.
- Produces: one self-contained HTML file with selectors `#ue-flow-canvas`, `.ue-flow-node`, `.ue-flow-edge`, `#ue-detail`, `#back-to-p2`, `#regenerate-flow`, and `#confirm-flow`.

- [ ] **Step 1: Add failing static-structure assertions**

```python
def test_wireframe_contains_original_shell_and_read_only_ue_review():
    html = WIREFRAME.read_text(encoding="utf-8")
    for text in ("言灵镜瞳", "P3 UE 流转图审核", "流程目录", "审核依据",
                 "返回 P2 修改", "重新生成", "确认 UE 流转图并进入 P4"):
        assert text in html
    assert 'id="ue-flow-canvas"' in html
    assert 'draggable="true"' not in html
    assert "新增页面" not in html
    assert "修改连线" not in html
    assert "飞书原生画板" in html
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```powershell
$env:PYTHONPATH='.;runtime_packages_pytest'
& 'C:\Users\momoca\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/test_ue_flow_wireframe.py -q -p no:cacheprovider --basetemp .pytest_tmp_ue_wireframe_html_red
```

Expected: FAIL because `线框图.html` does not exist.

- [ ] **Step 3: Implement the page shell and three-column layout**

Create a self-contained document whose semantic skeleton is:

```html
<header class="workspace-header">
  <strong>言灵镜瞳</strong>
  <nav class="phase-nav" aria-label="审核阶段">…P1–P7…</nav>
</header>
<main class="ue-review-shell">
  <aside class="flow-directory" aria-label="流程目录">…</aside>
  <section class="flow-workspace">
    <header class="flow-toolbar">…缩放与状态…</header>
    <div id="ue-flow-canvas" tabindex="0">…节点与 SVG 连线…</div>
  </section>
  <aside id="ue-detail" aria-label="审核依据">…</aside>
</main>
<footer class="review-actions">
  <button id="back-to-p2">返回 P2 修改</button>
  <button id="regenerate-flow">重新生成</button>
  <button id="confirm-flow">确认 UE 流转图并进入 P4</button>
</footer>
```

The sample flow must include one main path, one branch, one return edge, one loop, and one terminal node. Nodes use representative-frame placeholders and readable page names. The canvas must not expose edit handles.

- [ ] **Step 4: Implement deterministic review-only interactions**

Embed JavaScript that:

```javascript
document.querySelectorAll('.ue-flow-node,.ue-flow-edge').forEach((item) => {
  item.addEventListener('click', () => selectAuditItem(item.dataset.auditId));
});
document.querySelector('#back-to-p2').addEventListener('click', () => {
  showToast('线框示例：正式功能将返回 P2 并定位对应页面或跳转');
});
document.querySelector('#regenerate-flow').addEventListener('click', () => {
  showToast('线框示例：重新读取当前 P2 已确认数据');
});
document.querySelector('#confirm-flow').addEventListener('click', () => {
  showToast('线框示例：确认当前 revision 后进入 P4 交互交付物预览');
});
```

Zoom buttons may change only the canvas transform. Selection may change only highlight and right-panel content.

- [ ] **Step 5: Run static tests and verify GREEN**

Run the command from Step 2.

Expected: all `tests/test_ue_flow_wireframe.py` tests pass.

- [ ] **Step 6: Commit**

```powershell
git add tests/test_ue_flow_wireframe.py artifacts/ue-flow-review-wireframe-2026-08-19/线框图.html
git commit -m "feat: add UE flow review wireframe"
```

### Task 3: Browser-verify the wireframe interaction contract

**Files:**
- Create: `.test-tmp/ue-flow-wireframe-check.js`
- Create: `artifacts/ue-flow-review-wireframe-2026-08-19/线框图.png`
- Modify: `tests/test_ue_flow_wireframe.py`

**Interfaces:**
- Consumes: the static selectors produced by Task 2.
- Produces: browser evidence that selection, details, zoom and all three footer actions behave as review-only wireframe interactions.

- [ ] **Step 1: Add a failing browser-contract marker test**

```python
def test_wireframe_declares_browser_acceptance_contract():
    html = WIREFRAME.read_text(encoding="utf-8")
    assert 'data-browser-contract="ue-flow-review-v1"' in html
```

- [ ] **Step 2: Run the marker test and verify RED**

Run:

```powershell
$env:PYTHONPATH='.;runtime_packages_pytest'
& 'C:\Users\momoca\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/test_ue_flow_wireframe.py::test_wireframe_declares_browser_acceptance_contract -q -p no:cacheprovider --basetemp .pytest_tmp_ue_wireframe_browser_red
```

Expected: FAIL until the marker is added.

- [ ] **Step 3: Add the marker and Playwright browser checks**

The browser script must open the local HTML through a temporary static server, wait for `networkidle`, and assert:

```javascript
await page.locator('.ue-flow-node').nth(1).click();
if (!await page.locator('#ue-detail').getByText('触发方式').isVisible()) throw new Error('detail missing');
const before = await page.locator('#ue-flow-canvas').getAttribute('data-zoom');
await page.getByRole('button', { name: '放大' }).click();
const after = await page.locator('#ue-flow-canvas').getAttribute('data-zoom');
if (before === after) throw new Error('zoom did not change');
for (const name of ['返回 P2 修改', '重新生成', '确认 UE 流转图并进入 P4']) {
  await page.getByRole('button', { name }).click();
  if (!await page.locator('[role="status"]').isVisible()) throw new Error(`${name} feedback missing`);
}
```

Capture a full-page screenshot after selecting a branch edge.

- [ ] **Step 4: Run browser QA**

Run:

```powershell
$env:NODE_PATH='C:\Users\momoca\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules'
& 'C:\Users\momoca\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' .test-tmp/ue-flow-wireframe-check.js
```

Expected JSON:

```json
{"status":200,"nodes":5,"branchEdges":1,"consoleErrors":0,"reviewOnly":true}
```

- [ ] **Step 5: Run all wireframe tests**

Run:

```powershell
$env:PYTHONPATH='.;runtime_packages_pytest'
& 'C:\Users\momoca\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/test_ue_flow_wireframe.py -q -p no:cacheprovider --basetemp .pytest_tmp_ue_wireframe_final
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```powershell
git add tests/test_ue_flow_wireframe.py artifacts/ue-flow-review-wireframe-2026-08-19/线框图.html artifacts/ue-flow-review-wireframe-2026-08-19/线框图.png
git commit -m "test: verify UE flow review wireframe"
```
