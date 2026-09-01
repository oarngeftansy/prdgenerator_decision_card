# Refactor Maintenance Banner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an unavoidable, accessible maintenance announcement above the site header across the landing page and P1–P7 workspace.

**Architecture:** Keep the announcement as static semantic HTML in the single public entry point, with presentation in the existing shared stylesheet. Adjust the review-mode header rule and viewport-height calculation so the announcement remains visible without obscuring the workspace.

**Tech Stack:** HTML5, CSS, Python pytest static UI-contract tests.

## Global Constraints

- The announcement is always visible and cannot be dismissed.
- The Feishu link must exactly match the supplied URL and open in a new tab with safe `rel` attributes.
- The announcement must remain visible in landing and `body.has-review` modes.
- Do not modify `scripts/publish_current_alignment_to_feishu.py`, Planning Sketch, Phase 3, or historical project data.

---

### Task 1: Lock the announcement contract and implement the shared banner

**Files:**
- Modify: `tests/test_review_workspace_ui_contract.py`
- Modify: `index.html`
- Modify: `css/style.css`
- Modify: `css/review-workspace.css`

**Interfaces:**
- Consumes: the existing page-level `<header>`, `.topbar`, and `body.has-review` mode.
- Produces: `.maintenance-announcement` as the shared, non-dismissible announcement element.

- [ ] **Step 1: Write the failing contract test**

Add a pytest case that reads `index.html`, `css/style.css`, and `css/review-workspace.css`; assert the exact date, feedback URL, `target="_blank"`, `rel="noopener noreferrer"`, `@岛岛`, absence of a close button inside the announcement, a `.maintenance-announcement` style, and a review-mode rule that hides only `.topbar` rather than the full header.

- [ ] **Step 2: Run the focused test and verify RED**

Run: `python -m pytest tests/test_review_workspace_ui_contract.py -q -p no:cacheprovider --basetemp .test-tmp/maintenance-banner-red`

Expected: FAIL because `.maintenance-announcement` and its required text do not yet exist.

- [ ] **Step 3: Implement the minimal HTML and CSS**

Insert a semantic `role="status"` announcement before `.topbar`, containing the approved copy, exact Feishu link, and emphasized `@岛岛`. Add warm-warning colors, readable spacing, natural wrapping, focus-visible link treatment, and responsive padding. Replace `body.has-review > header { display: none; }` with a rule that hides only `.topbar`; define a banner-height custom property and subtract it from the review workspace viewport height.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `python -m pytest tests/test_review_workspace_ui_contract.py tests/test_screenshot_input_ui_contract.py -q -p no:cacheprovider --basetemp .test-tmp/maintenance-banner-green`

Expected: all tests pass.

- [ ] **Step 5: Run diff and protection checks**

Run: `git diff --check` and `git status --short -- index.html css/style.css css/review-workspace.css tests/test_review_workspace_ui_contract.py scripts/publish_current_alignment_to_feishu.py`

Expected: no whitespace errors; only the four intended implementation files are modified; the protected script has no diff.
