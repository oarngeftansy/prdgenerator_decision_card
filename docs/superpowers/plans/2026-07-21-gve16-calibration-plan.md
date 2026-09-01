# GVE16 Deep Calibration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a versioned, evidence-backed GVE16 standard by mapping the complete document, three whiteboards, and two same-gameplay level videos into one validated intermediate model.

**Architecture:** Read-only source adapters normalize Feishu/PDF, whiteboard, and video evidence into focused JSON artifacts. A calibration layer then builds four-way mappings among video evidence, planning prose, UE nodes, and visible behavior, and renders comparison reports without changing the website runtime.

**Tech Stack:** Python 3.11, ffmpeg/ffprobe, OpenCV, existing Qwen-compatible analysis service, JSON Schema-style validation, pytest.

## Global Constraints

- Treat `1.mp4` and `2.mp4` as two levels of the same gameplay.
- Preserve source provenance and timestamps for every material conclusion.
- Use only `observed`, `inferred`, and `unknown` evidence levels.
- Do not modify the source Feishu document or any source whiteboard.
- Do not write calibration-specific assumptions into the website runtime.
- GVE16 becomes the default standard only after calibration validation passes.

---

### Task 1: Calibration artifact contracts

**Files:**
- Create: `backend/calibration/__init__.py`
- Create: `backend/calibration/models.py`
- Create: `tests/calibration/test_models.py`

**Interfaces:**
- Produces: `validate_artifact(data: dict, kind: str) -> list[str]`
- Produces: `make_source_ref(source_type: str, source_id: str, locator: str) -> dict`

- [ ] **Step 1: Write the failing contract tests**

```python
from backend.calibration.models import make_source_ref, validate_artifact


def test_source_ref_and_evidence_levels():
    ref = make_source_ref("video", "level-1", "00:01:12.500")
    assert ref == {"sourceType": "video", "sourceId": "level-1", "locator": "00:01:12.500"}
    assert validate_artifact({"evidenceLevel": "certain"}, "evidence") == [
        "evidenceLevel must be one of observed, inferred, unknown"
    ]
```

- [ ] **Step 2: Run the focused test and verify failure**

Run: `python -m pytest tests/calibration/test_models.py -v`

Expected: FAIL because `backend.calibration.models` does not exist.

- [ ] **Step 3: Implement the minimal contracts**

```python
EVIDENCE_LEVELS = {"observed", "inferred", "unknown"}


def make_source_ref(source_type: str, source_id: str, locator: str) -> dict:
    return {"sourceType": source_type, "sourceId": source_id, "locator": locator}


def validate_artifact(data: dict, kind: str) -> list[str]:
    errors = []
    if kind == "evidence" and data.get("evidenceLevel") not in EVIDENCE_LEVELS:
        errors.append("evidenceLevel must be one of observed, inferred, unknown")
    return errors
```

- [ ] **Step 4: Run tests and commit**

Run: `python -m pytest tests/calibration/test_models.py -v`

Expected: PASS.

Commit: `git commit -m "test: define GVE16 calibration contracts"`

### Task 2: Document and table normalizer

**Files:**
- Create: `backend/calibration/document_parser.py`
- Create: `tests/calibration/test_document_parser.py`
- Create: `data/calibration/gve16/document.json`

**Interfaces:**
- Consumes: fetched Feishu XML/Markdown or extracted PDF text.
- Produces: `parse_document(content: str) -> dict` with `chapters`, `tables`, `rules`, `media`, and `sourceRefs`.

- [ ] **Step 1: Write a failing hierarchy/table test**

```python
from backend.calibration.document_parser import parse_document


def test_parse_document_keeps_heading_and_table_provenance():
    source = "# 玩法说明\n规则正文\n|字段|内容|\n|触发|升级后|"
    result = parse_document(source)
    assert result["chapters"][0]["title"] == "玩法说明"
    assert result["tables"][0]["rows"][0] == {"字段": "触发", "内容": "升级后"}
    assert result["rules"][0]["sourceRef"]["sourceType"] == "document"
```

- [ ] **Step 2: Run the focused test and verify failure**

Run: `python -m pytest tests/calibration/test_document_parser.py -v`

Expected: FAIL because the parser is absent.

- [ ] **Step 3: Implement heading, paragraph, table, and media parsing**

The parser must preserve chapter order, normalize table headers, retain original text, and create a stable locator using the heading path plus row index. It must extract `<whiteboard token="...">`, image tokens, and PDF page locators without inventing missing cells.

- [ ] **Step 4: Fetch/read the complete source and write the normalized artifact**

Run the Feishu document adapter in read-only mode; if a section is unavailable, use `【Gve16】执行文档261008.pdf` and record `sourceType: pdf` with page locators. Write UTF-8 JSON to `data/calibration/gve16/document.json`.

Expected: all top-level chapters are present, every table row retains its source locator, and no rule lacks `sourceRef`.

- [ ] **Step 5: Run tests and commit**

Run: `python -m pytest tests/calibration/test_document_parser.py -v`

Commit: `git commit -m "feat: normalize GVE16 document evidence"`

### Task 3: Whiteboard graph normalizer

**Files:**
- Create: `backend/calibration/whiteboard_parser.py`
- Create: `tests/calibration/test_whiteboard_parser.py`
- Create: `data/calibration/gve16/whiteboards.json`

**Interfaces:**
- Consumes: `tmp/lark-whiteboards/raw/01-ux.json`, `02-plan.json`, and `03-reference.json`.
- Produces: `parse_whiteboard(nodes: list[dict], board_id: str) -> dict` with normalized `nodes`, `edges`, `groups`, and `assets`.

- [ ] **Step 1: Write a failing connector/group test**

```python
from backend.calibration.whiteboard_parser import parse_whiteboard


def test_connector_preserves_direction_and_group():
    raw = [
        {"id": "a", "type": "text_shape", "text": "玩法主界面"},
        {"id": "b", "type": "text_shape", "text": "挑战失败"},
        {"id": "e", "type": "connector", "start": {"id": "a"}, "end": {"id": "b"}},
    ]
    graph = parse_whiteboard(raw, "ux")
    assert graph["edges"][0]["from"] == "a"
    assert graph["edges"][0]["to"] == "b"
```

- [ ] **Step 2: Run the focused test and verify failure**

Run: `python -m pytest tests/calibration/test_whiteboard_parser.py -v`

Expected: FAIL because the parser is absent.

- [ ] **Step 3: Implement type adapters and geometry normalization**

Support `text_shape`, `composite_shape`, `rect`, `round_rect`, `sticky_note`, `image`, `group`, `section`, and `connector`. Preserve original IDs, text, bounds, parent/group membership, connector endpoints, styles, and asset tokens. Nodes with unresolved endpoints must be listed in `diagnostics.unresolvedEdges`.

- [ ] **Step 4: Normalize all three boards and run graph diagnostics**

Write `data/calibration/gve16/whiteboards.json`. Confirm expected source totals are represented: UX includes 159 text shapes, 121 images, 48 groups, 26 connectors, and 25 sections; planning includes 54 composite shapes, 43 rectangles, 30 connectors, and 58 images; reference includes 26 images.

- [ ] **Step 5: Run tests and commit**

Run: `python -m pytest tests/calibration/test_whiteboard_parser.py -v`

Commit: `git commit -m "feat: normalize GVE16 whiteboard graphs"`

### Task 4: Full-video evidence extraction

**Files:**
- Create: `backend/calibration/video_calibrator.py`
- Create: `tests/calibration/test_video_calibrator.py`
- Create: `data/calibration/gve16/videos/level-1.json`
- Create: `data/calibration/gve16/videos/level-2.json`

**Interfaces:**
- Consumes: `1.mp4`, `2.mp4`, existing scene detection, frame extraction, Qwen vision, and optional transcription.
- Produces: `calibrate_video(path: Path, level_id: str) -> dict` with `coverage`, `chapters`, `scenes`, `events`, `frames`, `audio`, and `diagnostics`.

- [ ] **Step 1: Write a failing coverage/event-chain test**

```python
from backend.calibration.video_calibrator import validate_video_calibration


def test_rejects_core_event_without_complete_chain():
    result = validate_video_calibration({
        "duration": 600,
        "sampledUntil": 600,
        "events": [{"importance": "core", "beforeState": "主页", "action": "点击开始"}],
    })
    assert "core event missing systemResponse and afterState" in result
```

- [ ] **Step 2: Run the focused test and verify failure**

Run: `python -m pytest tests/calibration/test_video_calibrator.py -v`

Expected: FAIL because validation is absent.

- [ ] **Step 3: Implement resumable full-duration analysis**

Reuse the existing video pipeline for low-frequency full scan, boundary densification, OCR/UI structure extraction, visual interpretation, and audio alignment. Persist each stage. Every core event must include `beforeState`, `action`, `systemResponse`, `afterState`, `evidenceRefs`, and `evidenceLevel`; missing fields remain explicit `unknown` values.

- [ ] **Step 4: Analyze both complete videos**

Run calibration separately for `1.mp4` as `level-1` and `2.mp4` as `level-2`. Confirm `sampledUntil` reaches each ffprobe duration and that no unprocessed time gap exceeds the configured low-frequency scan interval.

- [ ] **Step 5: Run tests and commit**

Run: `python -m pytest tests/calibration/test_video_calibrator.py -v`

Commit: `git commit -m "feat: calibrate two complete GVE16 level videos"`

### Task 5: Four-way mapping and same-gameplay comparison

**Files:**
- Create: `backend/calibration/mapper.py`
- Create: `tests/calibration/test_mapper.py`
- Create: `data/calibration/gve16/mapping.json`

**Interfaces:**
- Consumes: normalized document, whiteboards, level-1, and level-2 artifacts.
- Produces: `build_mapping(...) -> dict` with `concepts`, `relations`, `sharedRules`, `levelDifferences`, `unmatched`, and `conflicts`.

- [ ] **Step 1: Write a failing common-rule/difference test**

```python
from backend.calibration.mapper import classify_level_rule


def test_rule_requires_evidence_in_both_levels_to_be_shared():
    assert classify_level_rule({"level-1": ["E1"], "level-2": ["E9"]}) == "shared"
    assert classify_level_rule({"level-1": ["E1"], "level-2": []}) == "level-1-only"
```

- [ ] **Step 2: Run the focused test and verify failure**

Run: `python -m pytest tests/calibration/test_mapper.py -v`

Expected: FAIL because mapping logic is absent.

- [ ] **Step 3: Implement concept matching and provenance rules**

Map each concept across `videoEvidence`, `documentRules`, `ueNodes`, and `visibleBehavior`. A concept is shared across levels only when both levels have evidence. Conflicting values are retained side by side and never silently merged. Unmatched source items remain in explicit queues.

- [ ] **Step 4: Build and validate the mapping artifact**

Expected: every mapped statement contains at least one source reference; every `observed` statement has a video timestamp or direct document/board locator; unmatched and conflict counts are reported.

- [ ] **Step 5: Run tests and commit**

Run: `python -m pytest tests/calibration/test_mapper.py -v`

Commit: `git commit -m "feat: map GVE16 logic across four evidence layers"`

### Task 6: Standard package and reverse-generation benchmark

**Files:**
- Create: `backend/calibration/standard_builder.py`
- Create: `tests/calibration/test_standard_builder.py`
- Create: `data/standards/gve16-1.0.json`
- Create: `docs/calibration/gve16-learning-report.md`
- Create: `docs/calibration/gve16-reconstruction-gameplay.md`
- Create: `docs/calibration/gve16-reconstruction-interaction.md`

**Interfaces:**
- Consumes: mapping artifact and existing planner renderers.
- Produces: `build_standard(mapping: dict) -> dict` and reconstruction reports.

- [ ] **Step 1: Write a failing default-standard validation test**

```python
from backend.calibration.standard_builder import validate_standard


def test_gve16_standard_has_both_modes_and_quality_gates():
    errors = validate_standard({"id": "gve16", "modes": ["gameplay"]})
    assert "interaction mode is required" in errors
    assert "quality gates are required" in errors
```

- [ ] **Step 2: Run the focused test and verify failure**

Run: `python -m pytest tests/calibration/test_standard_builder.py -v`

Expected: FAIL because the builder is absent.

- [ ] **Step 3: Build the versioned standard package**

The package must contain mode-specific chapter order, required fields, terminology, UE node/edge semantics, evidence rules, audit thresholds, and source version metadata. It must not contain Feishu credentials, local absolute paths, or raw API keys.

- [ ] **Step 4: Reverse-generate and compare outputs**

Render gameplay and interaction documents from the calibrated intermediate model. The learning report must list matched source sections, structural deviations, unsupported assumptions removed, unmatched items, conflicts, and recommended standard refinements.

- [ ] **Step 5: Run tests and commit**

Run: `python -m pytest tests/calibration/test_standard_builder.py -v`

Commit: `git commit -m "feat: package calibrated GVE16 planning standard"`

### Task 7: Calibration acceptance gate

**Files:**
- Create: `backend/calibration/audit.py`
- Create: `tests/calibration/test_audit.py`
- Create: `docs/calibration/gve16-acceptance.md`

**Interfaces:**
- Consumes: every calibration artifact.
- Produces: `audit_calibration(root: Path) -> dict` with a deterministic pass/fail result and actionable findings.

- [ ] **Step 1: Write a failing audit test**

```python
from backend.calibration.audit import audit_calibration


def test_audit_fails_when_video_is_not_fully_covered(tmp_path):
    report = audit_calibration(tmp_path)
    assert report["passed"] is False
    assert any(item["code"] == "VIDEO_COVERAGE_MISSING" for item in report["findings"])
```

- [ ] **Step 2: Run the focused test and verify failure**

Run: `python -m pytest tests/calibration/test_audit.py -v`

Expected: FAIL because the audit is absent.

- [ ] **Step 3: Implement deterministic acceptance checks**

Check complete duration coverage, source provenance, valid evidence levels, complete core event chains, unresolved graph edges, orphan nodes, document chapter/table completeness, shared-rule evidence in both levels, conflicts, unmatched items, and secret/path leakage.

- [ ] **Step 4: Run the full calibration suite and write acceptance results**

Run: `python -m pytest tests/calibration -v`

Run: `python -m backend.calibration.audit --root data/calibration/gve16 --output docs/calibration/gve16-acceptance.md`

Expected: tests PASS. The acceptance report may remain `not accepted` only when it lists concrete evidence gaps for user review; the website integration plan must not begin until those gaps are resolved or explicitly accepted.

- [ ] **Step 5: Commit**

Commit: `git commit -m "test: add GVE16 calibration acceptance gate"`
