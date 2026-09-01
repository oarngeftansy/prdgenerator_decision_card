# Attention Reasons Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Explain in plain Chinese why each filtered frame needs review and update that explanation in place after edits.

**Architecture:** Add one pure `attentionReasons(frame, mode)` function beside the existing attention predicate, then reuse it for filtering and rendering. The renderer records whether the visible frame began as an attention item so it can show a resolved message without navigating away.

**Tech Stack:** Browser JavaScript, CSS, Node built-in test runner.

## Global Constraints

- Keep the existing attention-frame population unchanged.
- Use GVE16-aligned plain Chinese and expose no internal field names.
- Add no dependency and no backend schema field.
- Recalculate after an editable field changes; never auto-navigate.

---

### Task 1: Pure reason model

**Files:**
- Modify: `tests/js/frame-reviewer.test.js`
- Modify: `js/frame-reviewer.js`

**Interfaces:**
- Produces: `attentionReasons(frame, mode): Array<{ label: string, suggestion: string }>`
- Changes: `filterFrames(..., "attention", mode)` uses `attentionReasons().length`.

- [x] **Step 1: Write failing tests** for conflict priority, mode-specific missing action/context, low-confidence wording, deduplication, three-item cap, and complete-frame empty output.
- [x] **Step 2: Run `node --test tests/js/frame-reviewer.test.js`** and verify failure because `attentionReasons` is absent.
- [x] **Step 3: Implement the minimal pure mapping** and export it; make the attention filter reuse it.
- [x] **Step 4: Run `node --test tests/js/frame-reviewer.test.js`** and expect all tests to pass.

### Task 2: In-place UI feedback

**Files:**
- Modify: `tests/js/frame-renderer-contract.test.js`
- Modify: `js/frames-models.js`
- Modify: `css/style.css`
- Modify: `index.html`

**Interfaces:**
- Consumes: `FrameReviewer.attentionReasons(frame, state.analysisMode)`.
- Produces: `.frame-attention-reasons` and `.frame-attention-resolved` feedback regions.

- [x] **Step 1: Add failing renderer contract assertions** for the reason and resolved regions plus an in-place feedback refresh hook.
- [x] **Step 2: Run `node --test tests/js/frame-renderer-contract.test.js`** and verify the new assertions fail.
- [x] **Step 3: Render up to three reason rows** below navigation and refresh only the feedback area on text/select input while preserving the active frame.
- [x] **Step 4: Add responsive accessible styles** and increment frontend asset versions in `index.html`.
- [x] **Step 5: Run both JavaScript test files and syntax checks**; expect zero failures.

### Task 3: Product verification

**Files:**
- Test only; no intended production changes.

- [x] **Step 1: Run the complete focused test set**: `node --test tests/js/frame-reviewer.test.js tests/js/frame-renderer-contract.test.js tests/js/frame-navigation-contract.test.js`.
- [x] **Step 2: Run `node --check js/frame-reviewer.js` and `node --check js/frames-models.js`**.
- [x] **Step 3: Open the completed 138-frame task**, filter to the existing 22 attention frames, verify reasons, edit one cause away, and confirm the frame stays visible with the resolved message.
- [x] **Step 4: Perform the deep-user pain audit** and report any residual limitation.
