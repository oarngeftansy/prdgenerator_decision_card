# Single-Frame Reviewer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the multi-card frame grid with an accessible single-frame reviewer that browses every frame chronologically and presents gameplay/interaction explanations in GVE16-style plain language.

**Architecture:** Add one dependency-free JavaScript module for ordering, index navigation, mode-specific field definitions, and terminology mapping. Reuse the existing `state.frames`, review persistence, timeline, video seeking, and rendering entry points; `renderFrames()` becomes a single active-frame view rather than creating one card per frame.

**Tech Stack:** Vanilla HTML/CSS/JavaScript, Node built-in test runner/assertions, existing FastAPI job data.

## Global Constraints

- Desktop uses the approved left-image/right-text A layout; mobile uses image-above/text-below.
- All frames are browsed in ascending timestamp order.
- Gameplay and interaction modes use different plain-language field sets.
- User-facing labels must not expose `default`, `loading`, `success`, `error`, `beforeState`, `afterState`, or `component tree`.
- Existing saved jobs and `state.frames` remain compatible.
- No new runtime dependency.

---

### Task 1: Reviewer Navigation and Plain-Language Field Model

**Files:**
- Create: `js/frame-reviewer.js`
- Create: `tests/js/frame-reviewer.test.js`
- Modify: `index.html`

**Interfaces:**
- Produces: `FrameReviewer.sortFrames(frames)`
- Produces: `FrameReviewer.moveIndex(index, delta, length)`
- Produces: `FrameReviewer.findFrameIndex(frames, frameId, timestamp)`
- Produces: `FrameReviewer.fieldsForMode(mode)`
- Produces: `FrameReviewer.isTextEditingTarget(target)`

- [ ] **Step 1: Write failing Node tests for chronological ordering, bounded arrows, target lookup, mode fields, and forbidden terminology**

```javascript
const test = require("node:test");
const assert = require("node:assert/strict");
const reviewer = require("../../js/frame-reviewer.js");

test("sortFrames orders every frame by timestamp without mutation", () => {
  const input = [{ id: "B", timestamp: 9 }, { id: "A", timestamp: 1 }];
  assert.deepEqual(reviewer.sortFrames(input).map((item) => item.id), ["A", "B"]);
  assert.deepEqual(input.map((item) => item.id), ["B", "A"]);
});

test("moveIndex stops at first and last frame", () => {
  assert.equal(reviewer.moveIndex(0, -1, 3), 0);
  assert.equal(reviewer.moveIndex(2, 1, 3), 2);
  assert.equal(reviewer.moveIndex(1, 1, 3), 2);
});

test("mode fields use GVE16 plain language", () => {
  const visible = JSON.stringify([
    ...reviewer.fieldsForMode("gameplay"),
    ...reviewer.fieldsForMode("interaction"),
  ]);
  assert.match(visible, /玩家做了什么/);
  assert.match(visible, /当前是什么界面/);
  for (const term of ["default", "loading", "success", "error", "beforeState", "afterState", "component tree"])
    assert.doesNotMatch(visible, new RegExp(term, "i"));
});
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `node --test tests/js/frame-reviewer.test.js`
Expected: FAIL because `js/frame-reviewer.js` does not exist.

- [ ] **Step 3: Implement the pure model with explicit gameplay and interaction field arrays**

The module must expose the five interfaces above to `window.FrameReviewer` and `module.exports`, preserve stable ordering for equal timestamps, return `-1` only when no frame exists, and treat `INPUT`, `TEXTAREA`, `SELECT`, and content-editable elements as text editing targets.

- [ ] **Step 4: Load the module before `frames-models.js` and verify GREEN**

Run: `node --test tests/js/frame-reviewer.test.js`
Expected: all tests pass.

### Task 2: Single Active-Frame Rendering

**Files:**
- Modify: `js/state.js`
- Modify: `js/frames-models.js`
- Create: `tests/js/frame-renderer-contract.test.js`

**Interfaces:**
- `state.currentFrameIndex: number` is the active ordered-frame position.
- `renderFrames()` renders exactly one `.frame-reviewer` article.
- `showFrameAt(index, options?)` changes the active frame, queues current edits, re-renders, and optionally focuses the reviewer title.
- Existing `data-field` and `data-index` editing hooks continue to update the underlying original frame.

- [ ] **Step 1: Write a failing renderer contract test**

Use Node to read `js/frames-models.js` and assert the source contains `showFrameAt`, `.frame-reviewer`, `frame-prev`, `frame-next`, `aria-live`, and does not map every frame into `.frame-card` markup.

- [ ] **Step 2: Run the contract and verify RED**

Run: `node --test tests/js/frame-renderer-contract.test.js`
Expected: FAIL because the single-frame contracts are absent.

- [ ] **Step 3: Replace the card grid renderer with the approved A layout**

Render:

- a navigation bar with previous/next buttons, scene, frame ID, timestamp, and `current / total`;
- one image with retry-safe alt text and “在视频中定位” action;
- one right-hand form generated by `FrameReviewer.fieldsForMode(state.analysisMode)`;
- evidence level, confidence, unknowns, and “确认此帧” controls;
- empty state without navigation when no frames exist.

Escape all frame-derived text and preserve the original frame index in editing attributes even though display order is timestamp-sorted.

- [ ] **Step 4: Run the renderer and model tests**

Run: `node --test tests/js/frame-reviewer.test.js tests/js/frame-renderer-contract.test.js`
Expected: all tests pass.

### Task 3: Navigation, Timeline Integration, and Save Safety

**Files:**
- Modify: `js/app.js`
- Modify: `js/backend.js`
- Modify: `js/frames-models.js`
- Create: `tests/js/frame-navigation-contract.test.js`

**Interfaces:**
- Arrow buttons call `showFrameAt` with a bounded index.
- Document-level `ArrowLeft`/`ArrowRight` navigation is ignored while editing text.
- `jumpToEvidence(timestamp, frameId)` calls the same frame-selection path before seeking video.
- Pending local edits remain in `state.frames`; failed backend persistence marks the review as unsaved and prevents ready-for-final status.

- [ ] **Step 1: Write failing navigation contract tests**

Assert the browser wiring includes unique handlers for `.frame-prev`, `.frame-next`, evidence/timeline jumps, editable-target protection, and an unsaved review state.

- [ ] **Step 2: Run the contract and verify RED**

Run: `node --test tests/js/frame-navigation-contract.test.js`
Expected: FAIL because the navigation path and unsaved state are absent.

- [ ] **Step 3: Wire every navigation source to the active frame**

Use event delegation in the existing listeners. Before changing index, keep textarea values in `state.frames` and call the existing debounced persistence path. Timeline and review-queue clicks set the active frame and source-video time together. Keyboard navigation must not fire for editable targets.

- [ ] **Step 4: Add explicit save failure feedback**

On review persistence failure, keep local changes, set `state.reviewUnsaved = true`, show “尚未保存到任务”, and force `readyForFinal` display to false. Clear the flag after the next successful save.

- [ ] **Step 5: Run all JavaScript contracts**

Run: `node --test tests/js/*.test.js`
Expected: all tests pass.

### Task 4: Responsive Styling and Browser QA

**Files:**
- Modify: `css/style.css`
- Modify: `index.html`
- Create: `tests/test_single_frame_ui_contract.py`

**Interfaces:**
- `.frame-reviewer-body` is a 58/42 desktop grid and one-column mobile layout.
- Arrow controls have at least 44×44px interactive area and visible focus.
- Low-confidence/unknown status uses icon/text plus color.

- [ ] **Step 1: Write a failing static UI contract**

The pytest contract must assert the stylesheet contains the reviewer grid, 44px controls, mobile collapse, visible `:focus-visible`, and no inline `frameList` max-height grid declaration remains in `index.html`.

- [ ] **Step 2: Run the contract and verify RED**

Run: `python -m pytest tests/test_single_frame_ui_contract.py -v`
Expected: FAIL because reviewer CSS is absent.

- [ ] **Step 3: Implement desktop, mobile, focus, disabled, loading-image, and unsaved styles**

Remove obsolete multi-card grid constraints only when no longer referenced. Keep existing color tokens and panel language; do not redesign unrelated parts of the site.

- [ ] **Step 4: Run automated verification**

Run:

```powershell
node --test tests/js/*.test.js
python -m pytest tests -q
node --check js/frame-reviewer.js
node --check js/frames-models.js
node --check js/backend.js
node --check js/app.js
```

Expected: zero failures and syntax exit code 0.

- [ ] **Step 5: Run browser QA at desktop and mobile widths**

Verify one frame only, chronological arrows, disabled endpoints, keyboard behavior, timeline/review jumps, gameplay/interaction labels, edit persistence, unsaved feedback, and no horizontal overflow. Confirm a real historical job opens in its saved mode.

- [ ] **Step 6: Run final review**

Use `ponytail-review`, `deep-user-pain-audit`, and `verification-before-completion`; apply safe simplifications and re-run the full verification commands.

## Risks and Controls

- Existing JavaScript is global-script based: expose one `FrameReviewer` namespace instead of adding a framework or bundler.
- Sorted display order can differ from array order: carry the original frame index for edits and confirmations.
- Backend jobs may update while open: preserve the active frame by ID when new data arrives.
- Technical source fields remain in job JSON: translate only at the presentation boundary and retain evidence IDs.

## Verification Commands

```powershell
node --test tests/js/*.test.js
python -m pytest tests -q
python -m compileall -q backend
node --check js/frame-reviewer.js
node --check js/frames-models.js
node --check js/backend.js
node --check js/app.js
```
