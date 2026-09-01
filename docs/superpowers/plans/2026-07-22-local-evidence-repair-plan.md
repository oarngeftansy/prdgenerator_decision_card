# Local Evidence Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a planner capture five nearby evidence images for one low-confidence frame, locally reanalyze that evidence, protect manual edits, and recalculate actionable review reasons.

**Architecture:** Add a focused backend module for supplemental timestamps, image extraction, model prompting, signal normalization, and edit-safe merging. Expose three frame-scoped endpoints through the existing FastAPI app. Extend the current single-frame reviewer and backend synchronization without adding auxiliary images to the main `frames` collection.

**Tech Stack:** Python 3.11, FastAPI, OpenCV, OpenAI-compatible client, browser JavaScript, CSS, Node built-in test runner, pytest.

## Global Constraints

- Supplemental images never enter `job.frames`, scene `frameIds`, GVE16 Evidence IDs, or review totals.
- Default sample offsets are exactly `[-1, -0.5, 0, 0.5, 1]` seconds, clipped to the video duration and deduplicated.
- The current provider configuration is passed at request time; no Qwen-only behavior.
- Human-edited fields are never silently overwritten.
- Only the target frame changes; the scene analysis and unrelated frames stay byte-equivalent.
- Model signals are restricted to `text_unreadable`, `visual_occlusion`, `action_between_frames`, `result_not_shown`, and `state_chain_broken`.
- No new runtime dependency.

---

### Task 1: Supplemental evidence domain module

**Files:**
- Create: `backend/local_evidence.py`
- Create: `tests/test_local_evidence.py`

**Interfaces:**
- Produces: `sample_times(center: float, duration: float) -> list[float]`.
- Produces: `extract_supplemental(video_path, output_dir, frame_id, center, duration) -> list[dict]`.
- Produces: `normalize_attention_signals(value) -> list[str]`.
- Produces: `merge_local_analysis(frame, candidate) -> dict` returning updated analysis and suggestions.

- [x] **Step 1: Write failing unit tests** for normal, start-edge, end-edge, and too-short timestamp sets; signal whitelist/deduplication; image reuse; and edit-safe merge behavior.
- [x] **Step 2: Run `python -m pytest tests/test_local_evidence.py -q`** and verify collection fails because `backend.local_evidence` does not exist.
- [x] **Step 3: Implement timestamp calculation and signal normalization** with standard-library operations only.
- [x] **Step 4: Implement OpenCV extraction** using stable filenames `<frame_id>_<milliseconds>.jpg`, reusing existing files and returning sorted public artifact paths.
- [x] **Step 5: Implement edit-safe merging**: update untouched fields, preserve `humanEditedFields`, and store differing values in `analysisSuggestion`.
- [x] **Step 6: Run `python -m pytest tests/test_local_evidence.py -q`** and expect all Task 1 tests to pass.

### Task 2: Local vision analysis and frame APIs

**Files:**
- Modify: `backend/analysis_service.py`
- Modify: `backend/server.py`
- Modify: `backend/storage.py`
- Create: `tests/test_local_evidence_api.py`

**Interfaces:**
- Produces: `analyze_local_evidence(job_dir, frame, scene, samples, config, mode) -> dict`.
- Produces: `POST /api/jobs/{job_id}/frames/{frame_id}/supplement-and-reanalyze`.
- Produces: `POST /api/jobs/{job_id}/frames/{frame_id}/suggestions/{field}/accept`.
- Produces: `DELETE /api/jobs/{job_id}/frames/{frame_id}/suggestions/{field}`.

- [x] **Step 1: Write failing API and service tests** using a temporary job root and a fake analysis function; assert 404/409 boundaries, archived rejection, in-progress rejection, and target-only mutation.
- [x] **Step 2: Run `python -m pytest tests/test_local_evidence_api.py -q`** and verify the endpoints/functions are absent.
- [x] **Step 3: Add the local-analysis prompt and parser** requiring target-frame fields, allowed signals, and timestamp references; raise a user-safe configuration error when no client is available.
- [x] **Step 4: Add the asynchronous supplement worker and start endpoint**. Persist `extracting`, `analyzing`, `ready`, or `failed` on the target frame; retain technical errors in `technicalError` and a plain-language `message` for the UI.
- [x] **Step 5: Mark manual edits in `/review`** by comparing submitted values with `lastModelAnalysis`; preserve `humanEditedFields` across saves.
- [x] **Step 6: Add accept/reject suggestion endpoints** with an editable-field whitelist. Accept writes the suggested value, marks it human-edited, clears that suggestion, and regenerates audit/plan; reject only clears the suggestion.
- [x] **Step 7: Run Task 1–2 tests** and verify main-frame count, IDs, scene data, and unrelated frames remain unchanged.

### Task 3: Actionable reason model

**Files:**
- Modify: `tests/js/frame-reviewer.test.js`
- Modify: `js/frame-reviewer.js`

**Interfaces:**
- Consumes: `frame.attentionSignals`, analysis values, unknown notes, and mode.
- Produces: the existing `attentionReasons(frame, mode)` array with specific labels and suggestions.

- [x] **Step 1: Add failing tests** for inherited-scene analysis, missing result proof, unreadable text, occlusion, between-frame action, broken state chain, fallback wording, priority, deduplication, and the three-reason limit.
- [x] **Step 2: Run `node --test tests/js/frame-reviewer.test.js`** and verify the new expectations fail.
- [x] **Step 3: Extend `attentionReasons` minimally** using a fixed signal-to-copy map and deterministic field checks; ensure ordinary `unknowns` still do not expand the attention filter.
- [x] **Step 4: Run the reviewer tests** and expect all tests to pass.

### Task 4: Supplemental evidence and suggestion UI

**Files:**
- Modify: `tests/js/frame-renderer-contract.test.js`
- Modify: `tests/js/frame-navigation-contract.test.js`
- Modify: `js/backend.js`
- Modify: `js/frames-models.js`
- Modify: `css/style.css`
- Modify: `index.html`

**Interfaces:**
- Produces: `supplementAndReanalyzeFrame(frameId)` and `resolveFrameSuggestion(frameId, field, accept)`.
- Consumes: `supplementalEvidence`, `analysisSuggestion`, `humanEditedFields`, and `attentionSignals` from backend job frames.

- [x] **Step 1: Add failing contract tests** for the supplement button, processing/failed/ready states, chronological thumbnails, suggestion actions, and cache-version updates.
- [x] **Step 2: Run the renderer/navigation contract tests** and verify the new assertions fail.
- [x] **Step 3: Map backend supplemental state into frontend frames** without adding items to `state.frames`.
- [x] **Step 4: Render the supplement action inside the existing attention block**. Disable it while running; render plain-language status and a retry action after failure.
- [x] **Step 5: Render up to five chronological thumbnails** with timestamp labels, keyboard-accessible buttons, video seeking, and active-image preview in the existing visual column.
- [x] **Step 6: Render field-level suggestion cards** below affected controls with `采用建议` and `保留当前内容`; call the frame-scoped endpoints and refresh the same frame.
- [x] **Step 7: Poll a local frame repair without switching the whole job to the global processing state**; update only the active frame when ready.
- [x] **Step 8: Add responsive styles** preserving 44×44 targets, visible focus, no horizontal overflow, and existing layout hierarchy; bump the affected asset versions.
- [x] **Step 9: Run JavaScript tests and syntax checks** and expect zero failures.

### Task 5: End-to-end verification and simplification

**Files:**
- Modify if needed: the files above only.
- Update: `task_plan.md`
- Update: `findings.md`
- Update: `progress.md`

**Interfaces:** None; this task verifies the complete workflow.

- [ ] **Step 1: Run focused backend tests**: `python -m pytest tests/test_local_evidence.py tests/test_local_evidence_api.py tests/test_planner.py tests/test_video_to_gve16_contract.py -q`.
- [ ] **Step 2: Run focused frontend tests**: `node --test tests/js/frame-reviewer.test.js tests/js/frame-renderer-contract.test.js tests/js/frame-navigation-contract.test.js`.
- [ ] **Step 3: Run syntax/import checks**: `python -m compileall -q backend`, `python -c "import backend.server"`, and `node --check` on changed JavaScript files.
- [ ] **Step 4: Restart the local backend**, load job `96c1a295b7684a5ba1e2b4bddef82d4a`, verify 138/22 counts, and run one F0002 supplemental flow with the configured provider.
- [ ] **Step 5: Verify preservation**: the original frame count, IDs, scene list, and restored human content are unchanged; auxiliary images persist outside the main list.
- [ ] **Step 6: Perform desktop and narrow-screen browser QA**, check console errors, keyboard operation, loading/error states, and no horizontal scroll.
- [ ] **Step 7: Run `ponytail-review` on the scoped diff**, remove dead/duplicated code, then rerun all focused checks.
- [ ] **Step 8: Run `verification-before-completion` and the deep-user pain audit**; report any provider-cost or source-video limitation honestly.
