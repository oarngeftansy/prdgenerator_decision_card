# Priority Review Signal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop ordinary per-frame unknown notes from placing every frame in “需要重点检查”, while retaining low-confidence, conflict, and critical-field-missing frames.

**Architecture:** Keep the existing pure filter module and add mode-aware critical-field validation inside `filterFrames`. Pass the current task mode from the reviewer; leave the separate unknown-evidence filter unchanged.

**Tech Stack:** Dependency-free JavaScript, Node built-in test runner, existing browser QA.

## Global Constraints

- No backend schema change or new dependency.
- `unknowns` alone never triggers the attention filter.
- Low confidence, explicit conflict, or missing mode-critical content always triggers it.

---

### Task 1: Mode-Aware Attention Signal

**Files:**
- Modify: `tests/js/frame-reviewer.test.js`
- Modify: `js/frame-reviewer.js`
- Modify: `js/frames-models.js`
- Modify: `index.html`

**Interfaces:**
- Changes: `FrameReviewer.filterFrames(frames, filter, mode = "gameplay")`
- Changes: `FrameReviewer.firstFrameIndexForScene(frames, sceneId, filter, mode = "gameplay")`

- [ ] **Step 1: Write failing regression tests**

Add cases proving a high-confidence complete frame with non-empty `unknowns` is excluded from attention, low/conflict frames remain included, gameplay requires a gameplay description plus `userAction`, and interaction requires `what` plus `userAction`.

- [ ] **Step 2: Verify RED**

Run: `node --test tests/js/frame-reviewer.test.js`
Expected: FAIL because `unknowns` still triggers attention and mode is ignored.

- [ ] **Step 3: Implement minimal mode-aware validation**

Use trimmed string checks. Gameplay description is present when either `gameState` or `what` is non-empty. Interaction description uses `what`. Both modes require `userAction`. Remove `isUnknown(frame)` from the attention predicate only; keep the unknown filter unchanged.

- [ ] **Step 4: Pass mode from reviewer helpers**

`reviewableFrames()` and scene lookup pass `state.analysisMode`. Bump the reviewer/model script cache version.

- [ ] **Step 5: Run automated verification**

Run:

```powershell
node --test tests/js/*.test.js
python tests/test_single_frame_ui_contract.py
node --check js/frame-reviewer.js
node --check js/frames-models.js
```

Expected: zero failures.

- [ ] **Step 6: Verify the completed 138-frame task**

Open the completed task, select “需要重点检查”, confirm the result is materially below 138 and contains all 22 low-confidence frames. Confirm “视频没有明确展示” still includes frames with unknown notes.

- [ ] **Step 7: Final review**

Run ponytail-review, deep-user-pain-audit, and verification-before-completion, then repeat the automated verification command.
