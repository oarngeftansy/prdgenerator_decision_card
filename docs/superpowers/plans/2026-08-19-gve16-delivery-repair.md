# GVE16 End-to-End Delivery Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repair every publication break identified by the P0 trace, then make the web preview and the existing Feishu document deterministic projections of the same approved planning artifact.

**Architecture:** Keep the 195-item trace as the acceptance ledger. Promote accepted design/parameter decisions into stable approved records, assemble the canonical Final from those records, and render both web and Feishu from that canonical artifact. Publish P5 diagrams and the detailed UE board as native Feishu whiteboards, then verify remote text, native numbering, raw nodes, preview readability, and per-item semantic satisfaction.

**Tech Stack:** Python 3, JavaScript, SVG, Feishu Docx/whiteboard CLI, JSON sidecars, Markdown canonical planning document.

## Global Constraints

- Do not copy GVE16 project values, table/field names, weights, or project-specific answers.
- Compare every chapter and sentence against the GVE16 execution questions, then answer only with current screenshots, video, approved inference, or explicit project design.
- Final publication contains approved data only; review state, internal IDs, lineage, implementation notes, and unapproved alternatives stay outside Final.
- Feishu gameplay steps use native ordered-list blocks; typed numeric prefixes are not acceptable.
- UE delivery contains detailed screenshot-first flow sections, numbered component rules, forward/return connectors, and readable default overview.
- P5 diagrams must preserve branches, loops, labels, and directed edges; a vertical explanation stack is a failure.
- Commit each independently verified repair; publish only after local, web, and Feishu artifacts agree.

---

### Task 1: Preserve the P0 Audit Baseline

**Files:**
- Add: `scripts/generate_p0_publication_trace_audit.py`
- Add: `artifacts/p0-end-to-end-publication-trace-audit-2026-08-19/*`
- Modify: `.claude/memory/{memory,wiki,learnings}.md`
- Modify: `docs/handoff/CURRENT_SESSION_HANDOFF.md`

**Interfaces:**
- Consumes: remote Feishu revision and the 195-item Alignment Matrix.
- Produces: `end-to-end-trace.json` with `deliveryClosureDecision` and first-failure localization.

- [ ] Commit the audit baseline without including the unverified P5 renderer change.
- [ ] Confirm the committed trace contains every audit ID and actual Final/Feishu text fields.

### Task 2: Establish Stable Approved Publication Inputs

**Files:**
- Modify: `scripts/generate_full_mechanic_accepted_publication.py`
- Modify: `artifacts/full-mechanic-accepted-publication-2026-08-19/alignment-closure-review.json`
- Modify: `artifacts/full-mechanic-acceptance-2026-08-19/approved-review-rules.json`
- Modify: `artifacts/full-mechanic-accepted-publication-2026-08-19/gameplay-rule-chains.json`
- Test: `tests/test_approved_mechanic_publication.py`

**Interfaces:**
- Consumes: accepted review decisions, evidence-resolved facts, parameter contracts, and business blockers.
- Produces: stable decision IDs, approved-data IDs, rule/parameter/presentation/transition IDs, owner and chain references.

- [ ] Add deterministic identity and provenance for every accepted design or parameter decision.
- [ ] Make the canonical chapter assembly consume those structured records rather than unrelated legacy prose.
- [ ] Regenerate canonical artifacts and commit the provenance repair.

### Task 3: Unify Web and Feishu Source of Truth with Native Numbering

**Files:**
- Modify: `backend/feishu_render.py`
- Modify: `backend/gameplay_render.py`
- Modify: `scripts/publish_current_alignment_to_feishu.py`
- Modify: `js/final-document-preview.js`
- Test: `tests/test_feishu_render.py`
- Test: `tests/js/final-document-preview-ui.test.js`

**Interfaces:**
- Consumes: canonical structured chapters and publication sidecars.
- Produces: semantically identical web/Feishu chapter order, paragraphs, native ordered lists, tables, and diagram slots.

- [ ] Remove the old raw `job.gameplayReviewModel` publication path for the current accepted artifact.
- [ ] Render sequences as `<ol><li>…</li></ol>` and keep heading text unnumbered.
- [ ] Verify no fallback or legacy planner section can overwrite canonical approved content.
- [ ] Commit the common-source renderer repair.

### Task 4: Repair and Verify P5 Structural Diagrams

**Files:**
- Modify: `scripts/generate_full_mechanic_accepted_publication.py`
- Modify: `data/jobs/4180cd72eeaa4819be41db50bb4c5011/structures/p5-review-diagrams.json`
- Modify: `artifacts/full-mechanic-accepted-publication-2026-08-19/necessary-diagrams.json`
- Test: `tests/test_approved_mechanic_publication.py`

**Interfaces:**
- Consumes: semantic nodes and directed edges for weapon, choice, monster, level/outcome, and damage data flows.
- Produces: branching SVGs with arrowheads, edge labels, return loops, and multiple X/Y lanes.

- [ ] Fix self-loop and return-edge geometry.
- [ ] Assert rendered edge and arrow counts match semantic edges and node positions span multiple axes.
- [ ] Render and visually inspect every diagram before committing.

### Task 5: Rebuild the Detailed UE Planning Board

**Files:**
- Modify: `backend/feishu_native_board.py`
- Modify: `scripts/build_current_native_whiteboard_delivery.py`
- Modify: `data/jobs/4180cd72eeaa4819be41db50bb4c5011/structures/ue-flow-annotations.json`
- Test: `tests/test_current_native_whiteboard_delivery.py`

**Interfaces:**
- Consumes: confirmed representative frames, numbered components, transitions, entry/exit states, and exceptions.
- Produces: complete loop overview, stage rows, readable per-stage small loops, real Sections, and straight forward/return connectors.

- [ ] Replace the seven-section ultra-wide strip with a bounded multi-row flow layout.
- [ ] Keep each screenshot, red marker, numbered rule, and yellow constraint readable at default overview.
- [ ] Export preview and query raw nodes; commit only after both checks agree.

### Task 6: Publish Canonical Final, P5, P6, and UE to Existing Feishu Document

**Files:**
- Modify: `scripts/publish_current_alignment_to_feishu.py`
- Update: `artifacts/full-mechanic-accepted-publication-2026-08-19/feishu-publication-checkpoint.json` locally only.

**Interfaces:**
- Consumes: verified canonical Final, five P5 diagrams, six P6 tables, planning UE board, and competitor board.
- Produces: the existing Feishu document updated in place with native lists and native whiteboards.

- [ ] Update document body without creating a duplicate document.
- [ ] Fetch the resulting document and bind all whiteboard tokens by semantic title.
- [ ] Write board structures before media, upload representative frames, then add token-backed image nodes.
- [ ] Export previews and query raw nodes for every board.
- [ ] Commit the publication code/checkpoint-safe metadata, then push the branch.

### Task 7: Full Reverse Re-audit and Delivery Closure

**Files:**
- Modify: `scripts/generate_p0_publication_trace_audit.py`
- Update: `artifacts/p0-end-to-end-publication-trace-audit-2026-08-19/*`
- Update: `docs/handoff/CURRENT_SESSION_HANDOFF.md`

**Interfaces:**
- Consumes: freshly fetched web and Feishu artifacts.
- Produces: 195 reverse traces, chapter-by-chapter GVE16 crosswalk, and compact final difference locator.

- [ ] Re-fetch Feishu and start every check from the user-visible artifact.
- [ ] Verify unsupported claims, wrong owners, generic fallbacks, duplicate primary rules, satisfaction false positives, P5/P6 loss, and visual unreadability are absent.
- [ ] Compare every Final chapter and sentence with the audit contract and GVE16 execution questions.
- [ ] Commit and push the final audit only after all delivery links are evidenced.
