# Long-Video Frame Review Filters Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add scene jumping and four plain-language review filters to the single-frame reviewer without changing saved job data.

**Architecture:** Extend the existing dependency-free `FrameReviewer` module with pure filtering and scene-selection helpers. Keep `state.frames` as the source of truth; the renderer derives a visible ordered subset and every navigation source resolves through `showFrameAt`.

**Tech Stack:** Vanilla HTML/CSS/JavaScript, Node built-in test runner, Python unittest static contract, existing FastAPI task data.

## Global Constraints

- Filter labels are exactly: “全部”, “需要重点检查”, “视频没有明确展示”, “尚未人工确认”.
- External timeline or evidence jumps automatically restore “全部” when the target is filtered out.
- No new runtime dependency and no backend schema change.
- Mobile controls may wrap but must not create horizontal scrolling.

---

### Task 1: Pure Filter Model

**Files:**
- Modify: `js/frame-reviewer.js`
- Modify: `tests/js/frame-reviewer.test.js`

**Interfaces:**
- Produces: `FrameReviewer.filterFrames(frames, filter)`
- Produces: `FrameReviewer.firstFrameIndexForScene(frames, sceneId, filter)`
- Produces: `FrameReviewer.filterOptions()`

- [ ] **Step 1: Add failing tests**

Test that `attention` includes low confidence, unknown evidence, or conflict flags; `unknown` includes unknown evidence or non-empty unknowns; `unconfirmed` excludes confirmed frames; scene lookup returns the first matching ordered index or `-1`.

- [ ] **Step 2: Verify RED**

Run: `node --test tests/js/frame-reviewer.test.js`
Expected: FAIL because the three interfaces do not exist.

- [ ] **Step 3: Implement the smallest pure helpers**

Use array filtering and the existing stable timestamp sort. Accept legacy confidence values `低` and `low`, legacy unknown evidence values, and optional `hasConflict` / `conflicts` fields.

- [ ] **Step 4: Verify GREEN**

Run: `node --test tests/js/frame-reviewer.test.js`
Expected: all model tests pass.

### Task 2: Reviewer Toolbar and Filtered Navigation

**Files:**
- Modify: `js/state.js`
- Modify: `js/frames-models.js`
- Modify: `tests/js/frame-renderer-contract.test.js`

**Interfaces:**
- Adds: `state.frameFilter = "all"`
- `reviewableFrames()` returns the ordered visible subset.
- `showFrameAt(index, options)` treats index as a visible-subset index.

- [ ] **Step 1: Extend the renderer contract test**

Assert source contains `frame-scene-select`, `frame-filter-select`, `reviewableFrames`, and the empty-filter message.

- [ ] **Step 2: Verify RED**

Run: `node --test tests/js/frame-renderer-contract.test.js`
Expected: FAIL on missing toolbar contracts.

- [ ] **Step 3: Render toolbar and filtered counts**

Derive options from `state.sceneGroups`, preserve the current frame when possible, render “筛选后第 X / Y 帧 · 全部 Z 帧”, and render a filter-specific empty state when `Y` is zero.

- [ ] **Step 4: Wire toolbar changes**

Filter change preserves the active frame when it remains visible and otherwise opens the first result. Scene change keeps the filter when possible; when no filtered frame exists in the scene, restore `all` and open the scene's first frame.

- [ ] **Step 5: Verify GREEN**

Run: `node --test tests/js/*.test.js`
Expected: all JavaScript tests pass.

### Task 3: External Jump Compatibility and Responsive UI

**Files:**
- Modify: `js/backend.js`
- Modify: `css/style.css`
- Modify: `index.html`
- Modify: `tests/js/frame-navigation-contract.test.js`
- Modify: `tests/test_single_frame_ui_contract.py`

**Interfaces:**
- `jumpToEvidence(timestamp, frameId)` clears an incompatible filter before selecting the target.

- [ ] **Step 1: Add failing navigation and UI contracts**

Assert external jumps set `state.frameFilter = "all"` when needed; CSS contains wrapping toolbar layout and labeled controls; cache versions are bumped.

- [ ] **Step 2: Verify RED**

Run: `node --test tests/js/frame-navigation-contract.test.js` and `python tests/test_single_frame_ui_contract.py`
Expected: both fail on missing filter integration.

- [ ] **Step 3: Implement external jump reset and toolbar styling**

Use `FrameReviewer.findFrameIndex` against the visible subset first, restore `all` only when absent, then resolve against all frames. Use native `select` controls, flex wrapping, visible focus, and full-width mobile controls.

- [ ] **Step 4: Run automated verification**

Run:

```powershell
node --test tests/js/*.test.js
python tests/test_single_frame_ui_contract.py
python -m compileall -q backend
node --check js/frame-reviewer.js
node --check js/frames-models.js
node --check js/backend.js
node --check js/app.js
```

Expected: zero failures.

- [ ] **Step 5: Run real-task browser QA**

Open the completed 138-frame task. Verify all four filters, empty results, filtered arrows, scene jump, external timeline reset, gameplay/interaction switching, textarea arrow protection, and mobile wrapping.

- [ ] **Step 6: Final review**

Run ponytail-review, deep-user-pain-audit, and verification-before-completion; apply safe simplifications and repeat the full verification command.
