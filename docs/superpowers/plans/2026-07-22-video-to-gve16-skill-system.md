# Video-to-GVE16 Skill System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert gameplay or interaction videos into evidence-backed GVE16 planning documents through a validated intermediate model and expose the full workflow to both the website and project-level Codex.

**Architecture:** Reuse the existing video, ScreenCoder, semantic-analysis, calibration, and audit pipeline. Add one dependency-free planning-model builder/validator between analysis and rendering, render GVE16 Markdown from that model, and package the source-project methods as focused project Skills. Keep Figma/Feishu as validated handoff data until a callable design connector exists.

**Tech Stack:** Python 3.11, FastAPI, stdlib JSON/data validation, pytest, Markdown/YAML Skill packages.

## Global Constraints

- GVE16 is the default planning standard.
- Support both `gameplay` and `interaction` modes.
- Every conclusion must distinguish observed, inferred, default, and unknown information and retain source references.
- Model configuration remains OpenAI-compatible and provider-neutral.
- Deploy Skills to both `skills/` and `.codex/skills/`.
- Do not claim that Figma or Feishu artifacts were created without a callable connector.

---

### Task 1: Validated GVE16 Intermediate Planning Model

**Files:**
- Create: `backend/planning_model.py`
- Create: `tests/test_planning_model.py`

**Interfaces:**
- Produces: `build_planning_model(job: dict[str, Any]) -> dict[str, Any]`
- Produces: `validate_planning_model(model: dict[str, Any]) -> list[str]`
- Produces: deterministic scene/event/component IDs, evidence references, flow edges, acceptance criteria, and design-handoff data.

- [x] Write tests proving both modes produce stable IDs, mode-specific sections, valid evidence references, and JSON-serializable output.
- [x] Run `python -m pytest tests/test_planning_model.py -v` and confirm failure because the module is absent.
- [x] Implement the smallest dependency-free builder and validator.
- [x] Re-run the focused tests and confirm they pass.

### Task 2: GVE16 Rendering and Pipeline Integration

**Files:**
- Modify: `backend/planner.py`
- Modify: `backend/server.py`
- Create: `tests/test_planner.py`

**Interfaces:**
- Consumes: `job["planningModel"]` from Task 1.
- Produces: human-readable GVE16 Markdown and a persisted `planningModel` in completed/reviewed/reanalyzed jobs.

- [x] Write tests showing the renderer uses the validated model, includes evidence-backed flows, and safely renders nested dict/list values (regression for `unhashable type: 'dict'`).
- [x] Run `python -m pytest tests/test_planner.py -v` and confirm the expected failure.
- [x] Refactor `generate_plan` to build/use the intermediate model and update all server generation paths.
- [x] Run focused tests and the calibration suite.

### Task 3: Complete Project Skill Deployment

**Files:**
- Create: `skills/screencoder-video-ui-analyzer/**`
- Create: `skills/visual-reference-decomposer/**`
- Create: `skills/gve16-planning-schema/**`
- Create: `skills/ultra-high-standard-game-prd/**`
- Create: `skills/planning-to-design-handoff/**`
- Create: `skills/video-to-gve16-planner/**`
- Create matching project-local packages under `.codex/skills/`.
- Create: `tests/test_skill_deployment.py`

**Interfaces:**
- Each Skill contains valid frontmatter, `agents/openai.yaml`, concise instructions, and only necessary progressive-disclosure references.
- The orchestrator routes gameplay/interaction mode and calls existing evidence, reconciliation, calibration, and audit Skills.

- [x] Write a deployment test that checks both trees, metadata, references, UTF-8 readability, and orchestrator dependencies.
- [x] Run it and confirm failure because packages are absent.
- [x] Create canonical Skill packages, absorbing ScreenCoder, clone-website, ultra-high-standard-prd, and prd-to-figma capabilities without unsupported claims.
- [x] Mirror the same packages into `.codex/skills/` and run the deployment test.

### Task 4: End-to-End Contract and Regression Verification

**Files:**
- Create: `tests/test_video_to_gve16_contract.py`
- Modify only proven defects in `backend/analysis_service.py`, `backend/quality.py`, or `backend/server.py` if the contract test exposes them.

**Interfaces:**
- Consumes: representative persisted job data for gameplay and interaction.
- Produces: validated model plus GVE16 document without invoking paid model APIs.

- [x] Write contract tests for gameplay and interaction jobs, including nested model responses and unknown evidence.
- [x] Run tests and capture the failing boundary.
- [x] Apply the minimum root-cause correction if needed.
- [x] Run `python -m pytest tests -v`, syntax compilation, Skill validation, and an offline representative end-to-end generation check.
- [x] Review the diff with `ponytail-review`, run `deep-user-pain-audit`, and re-run final verification.

## Risks and Controls

- Existing files are largely untracked: avoid broad formatting, deletion, or repository cleanup.
- Real 10–20 minute video/API processing is costly: automated verification uses persisted/representative evidence; a real model run is reported separately if credentials or proxy are unavailable.
- Incoming PRD Skills contain mojibake: rebuild readable project-local Skills from their usable schemas rather than copying corrupted text.
- Figma/Feishu execution depends on connectors: emit validated handoff JSON and explicit readiness status only.

## Verification Commands

```powershell
python -m pytest tests -v
python -m compileall backend
python -m pytest tests/test_skill_deployment.py -v
```
