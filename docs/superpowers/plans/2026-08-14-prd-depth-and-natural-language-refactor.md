# PRD Depth and Natural-Language Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a cross-project gameplay-PRD generation contract that separates content carriers, blocks sample leakage and AI-style copy, enforces mechanism-specific depth, and migrates the current “一路狂飙” task as the first regression sample.

**Architecture:** Add a pure normalization and domain-policy layer before quality auditing and rendering. Existing language, granularity, lead-planner, and rendering modules consume the normalized model; project-specific migration uses the same public functions and cannot bypass the gates. “一路狂飙” remains fixture data, while three unrelated blind-test domains prove portability.

**Tech Stack:** Python 3.12, pytest, existing XML gameplay renderer, Node.js built-in test runner, existing local browser QA scripts.

## Global Constraints

- Rules for depth, language, titles, carriers, and decision cards are global; no project name or current screenshot ID may be hard-coded into reusable backend modules.
- Sample reserves may activate questions only; they may not publish current-project facts, official table names, numeric limits, formulas, or mechanics.
- Published prose contains gameplay rules only. Audit notes, evidence capability, confidence, and remediation stay in review metadata.
- A fact has one primary delivery carrier. Other carriers reference its stable ID instead of copying the sentence.
- Domain modules activate as `applicable`, `decision_required`, or `not_applicable`; `not_applicable` never creates an empty heading.
- Tests are written and observed failing before production changes.
- Existing user artifacts and untracked QA output are never staged.

---

## File Structure

- Create `backend/planning_content_policy.py`: normalize published carrier ownership and stable cross-carrier references.
- Create `backend/gameplay_domain_policy.py`: activate reusable domain question libraries and validate source scope.
- Modify `backend/feishu_language_quality.py`: detect AI-style titles, audit language, repeated cadence, and cross-carrier prose duplication.
- Modify `backend/granularity_audit.py`: require evidence-supported mechanism closure and decision coverage.
- Modify `backend/lead_planner_gate.py`: run provenance, carrier, language, and depth gates together.
- Modify `backend/gameplay_render.py`: render only primary carriers and place local figures/diagrams without editor follow-up text.
- Modify `backend/stage3_quality_gate.py`: expose actionable gate failures to P4/P7/export.
- Create `scripts/migrate_current_job_prd_depth.py`: migrate the current task through generic policies after a snapshot.
- Create `scripts/qa-prd-depth-refactor.js`: browser evidence capture for both acceptance points.
- Modify `skills/feishu-gameplay-prd-reconstruction/SKILL.md` and its references: persist the general rules in the project Skill.
- Add focused tests under `tests/` and `tests/js/`.

---

### Task 1: Single-Owner Content Carrier Normalization

**Files:**
- Create: `backend/planning_content_policy.py`
- Create: `tests/test_planning_content_policy.py`
- Modify: `backend/lead_planner_gate.py`

**Interfaces:**
- Produces: `normalize_delivery_carriers(model: dict[str, Any]) -> dict[str, Any]`
- Produces: `carrier_policy_report(model: dict[str, Any]) -> dict[str, Any]`
- Consumed by: lead-planner audit, renderer, current-task migration.

- [ ] **Step 1: Write failing carrier tests**

```python
from backend.planning_content_policy import carrier_policy_report, normalize_delivery_carriers


def test_same_rule_has_one_primary_published_carrier():
    sentence = "敌人进入攻击距离后停止移动并开始攻击。"
    model = {"chapters": [{
        "id": "C1",
        "plannerSections": {"normalFlow": [sentence], "keyRules": [], "specialCases": []},
        "objectStates": [sentence],
        "runtimeResponsibilities": [sentence],
        "presentationRules": [sentence],
    }]}
    normalized = normalize_delivery_carriers(model)
    chapter = normalized["chapters"][0]
    assert chapter["plannerSections"]["normalFlow"] == [sentence]
    assert chapter["objectStates"] == []
    assert chapter["runtimeResponsibilities"] == []
    assert chapter["presentationRules"] == []
    assert len(chapter["carrierRefs"]) == 3
    assert carrier_policy_report(normalized)["passed"] is True


def test_distinct_runtime_responsibility_is_preserved():
    model = {"chapters": [{
        "id": "C2",
        "plannerSections": {"normalFlow": ["波次开始时生成怪物。"]},
        "runtimeResponsibilities": ["服务端在波次开始时生成本波怪物列表。"],
    }]}
    chapter = normalize_delivery_carriers(model)["chapters"][0]
    assert chapter["runtimeResponsibilities"] == ["服务端在波次开始时生成本波怪物列表。"]
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest tests/test_planning_content_policy.py -q`

Expected: collection fails with `ModuleNotFoundError: backend.planning_content_policy`.

- [ ] **Step 3: Implement normalization**

```python
from __future__ import annotations

from copy import deepcopy
import hashlib
import re
from typing import Any

SECONDARY_FIELDS = ("objectStates", "runtimeResponsibilities", "presentationRules")


def _normalized(value: Any) -> str:
    return re.sub(r"[\s，。；：、,.!?！？（）()\-—]", "", str(value or "")).casefold()


def _fact_id(chapter_id: str, text: str) -> str:
    digest = hashlib.sha1(_normalized(text).encode("utf-8")).hexdigest()[:10]
    return f"FACT-{chapter_id}-{digest}"


def normalize_delivery_carriers(model: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(model)
    for chapter in result.get("chapters") or []:
        chapter_id = str(chapter.get("id") or "chapter")
        planner = chapter.get("plannerSections") if isinstance(chapter.get("plannerSections"), dict) else {}
        primary = []
        for name in ("summary", "normalFlow", "keyRules", "specialCases", "attributeSections"):
            value = planner.get(name)
            values = value if isinstance(value, list) else [value]
            primary.extend(_normalized(item) for item in values if str(item or "").strip())
        refs = []
        for field in SECONDARY_FIELDS:
            kept = []
            for item in chapter.get(field) or []:
                if _normalized(item) in primary:
                    refs.append({"field": field, "factId": _fact_id(chapter_id, str(item))})
                else:
                    kept.append(item)
            chapter[field] = kept
        chapter["carrierRefs"] = refs
    return result


def carrier_policy_report(model: dict[str, Any]) -> dict[str, Any]:
    findings = []
    for chapter in model.get("chapters") or []:
        planner_text = _normalized((chapter.get("plannerSections") or {}))
        for field in SECONDARY_FIELDS:
            for item in chapter.get(field) or []:
                if _normalized(item) and _normalized(item) in planner_text:
                    findings.append({"chapterId": chapter.get("id"), "field": field,
                                     "code": "CARRIER_DUPLICATE_PRIMARY_FACT",
                                     "action": "保留一个正文主载体，其他字段改为 factId 引用。"})
    return {"passed": not findings, "findings": findings}
```

- [ ] **Step 4: Integrate carrier report into lead-planner output audit**

Import `carrier_policy_report` and append `chapterId:code` failures during `phase == "details"`.

- [ ] **Step 5: Run focused and lead-planner tests**

Run: `python -m pytest tests/test_planning_content_policy.py tests/test_lead_planner_gate.py -q`

Expected: all tests pass.

- [ ] **Step 6: Commit**

```powershell
git add backend/planning_content_policy.py backend/lead_planner_gate.py tests/test_planning_content_policy.py
git commit -m "feat: enforce single-owner PRD content carriers"
```

---

### Task 2: Cross-Project Domain Activation and Sample Isolation

**Files:**
- Create: `backend/gameplay_domain_policy.py`
- Create: `tests/test_gameplay_domain_policy.py`
- Modify: `backend/lead_planner_gate.py`
- Modify: `backend/granularity_audit.py`

**Interfaces:**
- Produces: `classify_domain_modules(evidence_tags: set[str], unresolved: set[str]) -> dict[str, str]`
- Produces: `provenance_scope_report(model: dict[str, Any]) -> dict[str, Any]`
- Domain keys: `movement`, `placement`, `random`, `combat`, `growth`, `buff`, `inventory`, `level`, `sweep`.

- [ ] **Step 1: Write failing portability tests**

```python
from backend.gameplay_domain_policy import classify_domain_modules, provenance_scope_report


def test_sparse_movement_does_not_activate_unrelated_domains():
    states = classify_domain_modules({"movement", "health"}, set())
    assert states["movement"] == "applicable"
    assert states["combat"] == "applicable"
    assert states["inventory"] == "not_applicable"
    assert states["sweep"] == "not_applicable"


def test_unresolved_random_algorithm_requires_decision():
    states = classify_domain_modules({"random_choice"}, {"weights", "replacement"})
    assert states["random"] == "decision_required"


def test_sample_reserve_cannot_publish_current_fact():
    model = {"chapters": [{
        "id": "C1", "scope": "载具",
        "plannerSections": {"keyRules": ["进入关卡时包含1个默认武器栏和4个自选栏。"]},
        "provenanceClaims": [{"text": "进入关卡时包含1个默认武器栏和4个自选栏。",
                              "sourceScope": "sample_reserve", "publicationAllowed": True}],
    }]}
    report = provenance_scope_report(model)
    assert report["passed"] is False
    assert report["findings"][0]["code"] == "SAMPLE_RESERVE_PUBLISHED_AS_FACT"
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest tests/test_gameplay_domain_policy.py -q`

Expected: collection fails because `backend.gameplay_domain_policy` does not exist.

- [ ] **Step 3: Implement domain and provenance policy**

Create immutable tag sets for each domain. Return `decision_required` when a domain is evidenced but its required unresolved set is non-empty; otherwise return `applicable`. Detect any published claim whose `sourceScope` is `sample_reserve`, or whose only source is a reserve library.

- [ ] **Step 4: Integrate source-scope findings**

Add `provenance_scope_report` to `lead_planner_output_audit`. In `granularity_audit_report`, accept `sourceScope` values only from `current_material`, `current_reference`, `current_configuration`, `planner_decision`, and `sample_reserve`; the last one can support a question but not a published conclusion.

- [ ] **Step 5: Run portability and provenance tests**

Run: `python -m pytest tests/test_gameplay_domain_policy.py tests/test_granularity_audit.py tests/test_lead_planner_gate.py -q`

Expected: all tests pass.

- [ ] **Step 6: Commit**

```powershell
git add backend/gameplay_domain_policy.py backend/lead_planner_gate.py backend/granularity_audit.py tests/test_gameplay_domain_policy.py tests/test_granularity_audit.py
git commit -m "feat: isolate sample reserves from project facts"
```

---

### Task 3: Human Planning Titles and Non-AI Language Gate

**Files:**
- Modify: `backend/feishu_language_quality.py`
- Modify: `tests/test_feishu_language_quality.py`
- Modify: `tests/test_feishu_language_grammar_calibration.py`

**Interfaces:**
- Extends: `language_quality_report(model) -> {passed, findings, chapters}`
- New codes: `LANGUAGE_TEMPLATE_TITLE`, `LANGUAGE_AUDIT_VOICE`, `LANGUAGE_REPEATED_CADENCE`, `LANGUAGE_EMPTY_ABSTRACTION`.

- [ ] **Step 1: Add failing language tests**

```python
def test_rejects_ai_composite_title():
    model = {"chapters": [{"id": "C1", "scope": "命中、反馈与伤害归集",
                            "plannerSections": {"summary": "武器命中后造成伤害。"}}]}
    codes = {item["code"] for item in language_quality_report(model)["findings"]}
    assert "LANGUAGE_TEMPLATE_TITLE" in codes


def test_rejects_audit_voice_in_delivery_copy():
    model = {"chapters": [{"id": "C2", "scope": "武器",
                            "plannerSections": {"keyRules": ["当前项目应逐项保留奖励，而不能概括处理。"]}}]}
    codes = {item["code"] for item in language_quality_report(model)["findings"]}
    assert "LANGUAGE_AUDIT_VOICE" in codes


def test_accepts_business_object_titles():
    model = {"chapters": [{"id": "C3", "scope": "武器栏",
                            "plannerSections": {"summary": "玩家获得新武器后，将武器写入一个空栏位。"}}]}
    assert language_quality_report(model)["passed"] is True
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest tests/test_feishu_language_quality.py -q`

Expected: the new title and audit-voice assertions fail.

- [ ] **Step 3: Implement language checks and remediation**

Reject three-part abstract title constructions, editorial verbs, empty abstractions, and three or more consecutive sentences with the same “系统/玩家 + 动作 + 并” cadence. Every new code receives a concrete remediation action and affected carrier.

- [ ] **Step 4: Run language calibration**

Run: `python -m pytest tests/test_feishu_language_quality.py tests/test_feishu_language_grammar_calibration.py -q`

Expected: all tests pass, including existing natural short-mechanism cases.

- [ ] **Step 5: Commit**

```powershell
git add backend/feishu_language_quality.py tests/test_feishu_language_quality.py tests/test_feishu_language_grammar_calibration.py
git commit -m "feat: gate AI-style PRD titles and prose"
```

---

### Task 4: Mechanism-Specific Closure and Decision Coverage

**Files:**
- Modify: `backend/granularity_audit.py`
- Modify: `backend/gameplay_generation_quality.py`
- Create: `tests/test_cross_project_prd_depth.py`
- Modify: `tests/test_gameplay_generation_quality.py`

**Interfaces:**
- Produces: `mechanism_closure_report(model: dict[str, Any]) -> dict[str, Any]`
- Each applicable domain reports covered and missing responsibilities plus remediation.

- [ ] **Step 1: Add failing depth tests for three unrelated domains**

```python
from backend.gameplay_generation_quality import mechanism_closure_report


def random_model(*, normal_flow=None, unresolved=None, decision_cards=None):
    return {"chapters": [{
        "id": "R1", "scope": "三选一", "domainStates": {"random": "applicable"},
        "plannerSections": {"normalFlow": normal_flow or []},
        "unresolvedResponsibilities": sorted(unresolved or set()),
        "decisionCards": decision_cards or [],
    }]}


def inventory_model(*, rules):
    return {"chapters": [{
        "id": "I1", "scope": "背包", "domainStates": {"inventory": "applicable"},
        "plannerSections": {"keyRules": rules}, "decisionCards": [],
    }]}


def test_random_choice_requires_pool_filter_commit_and_reset():
    model = random_model(normal_flow=["升级后显示三个候选，选择后继续战斗。"])
    report = mechanism_closure_report(model)
    missing = report["domains"]["random"]["missing"]
    assert {"eligibility", "filter", "duplicate", "empty", "commit", "reset"} <= set(missing)


def test_inventory_does_not_require_combat_formula():
    model = inventory_model(rules=["物品只能放入未占用且形状匹配的格子。",
                                   "放置失败时物品返回原位置。"])
    report = mechanism_closure_report(model)
    assert report["domains"]["combat"]["status"] == "not_applicable"


def test_unknown_weight_rule_requires_decision_card():
    model = random_model(unresolved={"weights"}, decision_cards=[])
    report = mechanism_closure_report(model)
    assert any(item["code"] == "MECHANISM_DECISION_CARD_MISSING" for item in report["findings"])
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest tests/test_cross_project_prd_depth.py -q`

Expected: import or assertion failures because mechanism closure is not implemented.

- [ ] **Step 3: Implement reusable closure responsibilities**

Define responsibility keys per domain, map current planner fields to those keys, and require a decision card when evidence activates a responsibility but the conclusion remains unresolved. A short movement rule must pass without random, configuration, formula, or lifecycle filler.

- [ ] **Step 4: Integrate closure into generation quality and granularity reports**

Return actionable findings such as “补充候选不足时的处理，或建立决策卡” rather than a generic completeness percentage.

- [ ] **Step 5: Run depth suites**

Run: `python -m pytest tests/test_cross_project_prd_depth.py tests/test_gameplay_generation_quality.py tests/test_granularity_audit.py -q`

Expected: all tests pass.

- [ ] **Step 6: Commit**

```powershell
git add backend/granularity_audit.py backend/gameplay_generation_quality.py tests/test_cross_project_prd_depth.py tests/test_gameplay_generation_quality.py
git commit -m "feat: enforce mechanism-specific PRD closure"
```

---

### Task 5: Adaptive Rendering and Local Figure Placement

**Files:**
- Modify: `backend/gameplay_render.py`
- Modify: `tests/test_gameplay_render.py`
- Modify: `tests/js/final-document-preview-ui.test.js`

**Interfaces:**
- Renderer consumes normalized primary carriers.
- Diagram placement consumes `placement.chapterId`, `afterRuleId`, and `sourceRevision`; `followUp` editor text is never published.
- Inline figures consume `afterRuleId`, `frameId`, and a business caption.

- [ ] **Step 1: Add failing renderer tests**

```python
def test_editor_follow_up_is_not_published():
    job = complete_job()
    model = job["gameplayReviewModel"]
    model["diagrams"] = [{"id": "D1", "title": "三选一", "status": "reviewed",
        "chapterIds": ["GCH-001"], "sourceRevision": model["revision"],
        "placement": {"chapterId": "GCH-001", "afterRuleId": "R1",
                      "followUp": "图中的算法由后续章节展开；本节继续说明。"},
        "freshness": "current", "interactionRevision": job["reviewModel"]["revision"],
        "svg": "<svg><text>三选一</text></svg>"}]
    xml = render_gameplay_document_sections(job).xml
    assert "本节继续说明" not in xml


def test_presentation_rules_do_not_repeat_in_body():
    job = complete_job()
    sentence = "弹窗背景变暗并显示三张卡片。"
    chapter = job["gameplayReviewModel"]["chapters"][0]
    chapter["presentationRules"] = [sentence]
    chapter["plannerSections"]["keyRules"] = [sentence]
    xml = render_gameplay_document_sections(job).xml
    assert xml.count(sentence) == 1
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest tests/test_gameplay_render.py -q`

Expected: at least one new test fails against the existing renderer.

- [ ] **Step 3: Normalize before rendering and remove editor metadata**

Call `normalize_delivery_carriers` at the renderer boundary. Render `plannerSections`, reviewed mechanism tables, formula blocks, diagrams, and inline figures only. Never serialize audit findings, carrier refs, confidence, improvement paths, or diagram `followUp`.

- [ ] **Step 4: Add adaptive heading density behavior**

Merge a section with one short item into the nearest semantic parent; retain a heading only for independently useful rule clusters, tables, formulas, or diagrams. Use the chapter’s business title and supplied semantic section names rather than fixed labels.

- [ ] **Step 5: Run Python and preview UI tests**

Run: `python -m pytest tests/test_gameplay_render.py -q`

Run: `node --test tests/js/final-document-preview-ui.test.js`

Expected: both suites pass.

- [ ] **Step 6: Commit**

```powershell
git add backend/gameplay_render.py tests/test_gameplay_render.py tests/js/final-document-preview-ui.test.js
git commit -m "feat: render adaptive PRD carriers and local figures"
```

---

### Task 6: Persist General Rules in Project Skill and Knowledge Base

**Files:**
- Modify: `skills/feishu-gameplay-prd-reconstruction/SKILL.md`
- Modify: `skills/feishu-gameplay-prd-reconstruction/references/granularity-contract.md`
- Modify: `skills/feishu-gameplay-prd-reconstruction/references/evidence-to-output.md`
- Modify: `skills/feishu-gameplay-prd-reconstruction/references/quality-gates.md`
- Modify: `docs/research/gve16-production-depth-addendum-2026-08-11.md`
- Modify: `tests/test_feishu_gameplay_prd_reconstruction_skill.py`

**Interfaces:**
- Skill documents point to the same carrier, provenance, domain activation, language, diagram, attribute, and acceptance contracts enforced in code.

- [ ] **Step 1: Add failing Skill contract tests**

Assert the Skill and references explicitly contain: single-owner carriers, `applicable/decision_required/not_applicable`, sample-reserve isolation, owner-specific attribute prose, no fixed headings, local screenshot/diagram placement, no audit voice, cross-project blind tests, and screenshot-backed staged acceptance.

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest tests/test_feishu_gameplay_prd_reconstruction_skill.py -q`

Expected: new assertions fail because the full general contract is not yet present.

- [ ] **Step 3: Update Skill and references**

Write rules as reusable behavior, not “一路狂飙” instructions. Keep weapons, Buffs, inventory, sweep, waves, placement, and random mechanisms as reserve question libraries activated only by evidence.

- [ ] **Step 4: Run Skill tests**

Run: `python -m pytest tests/test_feishu_gameplay_prd_reconstruction_skill.py tests/test_feishu_skill_traceability.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add skills/feishu-gameplay-prd-reconstruction docs/research/gve16-production-depth-addendum-2026-08-11.md tests/test_feishu_gameplay_prd_reconstruction_skill.py
git commit -m "docs: persist cross-project PRD generation rules"
```

---

### Task 7: Migrate the Current Task Through Generic Policies

**Files:**
- Create: `scripts/migrate_current_job_prd_depth.py`
- Create: `tests/test_current_job_prd_depth_migration.py`
- Modify: `data/jobs/8312a91c89e144e6a59f81b982f14c06/job.json` only through the migration script during the accepted run.

**Interfaces:**
- Produces: `migrate_job(job: dict[str, Any]) -> dict[str, Any]`
- Uses: `normalize_delivery_carriers`, `classify_domain_modules`, `provenance_scope_report`, language/depth gates.
- Must create a timestamped backup before replacing the live job file.

- [ ] **Step 1: Write failing migration tests against a sanitized fixture**

```python
def test_migration_removes_sample_only_current_facts(current_job_fixture):
    migrated = migrate_job(current_job_fixture)
    text = json.dumps(migrated["gameplayReviewModel"], ensure_ascii=False)
    assert "策划提供的系统样例" not in text
    assert "图中的升级、首领和胜负节点由后续章节" not in text


def test_migration_keeps_unknown_algorithms_as_decisions(current_job_fixture):
    migrated = migrate_job(current_job_fixture)
    cards = [card for chapter in migrated["gameplayReviewModel"]["chapters"]
             for card in chapter.get("decisionCards") or []]
    questions = "\n".join(card["question"] for card in cards)
    assert "候选池" in questions
    assert "武器抽取" in questions


def test_migration_passes_all_content_gates(current_job_fixture):
    migrated = migrate_job(current_job_fixture)
    model = migrated["gameplayReviewModel"]
    assert lead_planner_output_audit(model, "details") == []
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest tests/test_current_job_prd_depth_migration.py -q`

Expected: collection fails because the migration module does not exist.

- [ ] **Step 3: Implement pure migration**

Remove duplicated secondary carriers, demote reserve-only claims to decision inputs, rebuild semantic titles, preserve current evidence IDs, place valid figures locally, and clear stale preview revisions. Do not copy exact GVE16 field names or values.

- [ ] **Step 4: Run migration tests**

Run: `python -m pytest tests/test_current_job_prd_depth_migration.py -q`

Expected: all tests pass without modifying the live job.

- [ ] **Step 5: Back up and migrate the live task**

Run: `python scripts/migrate_current_job_prd_depth.py --job 8312a91c89e144e6a59f81b982f14c06 --apply`

Expected: JSON output includes the backup path, previous revision, new revision, chapter count, decision-card count, and `gatePassed: true`.

- [ ] **Step 6: Commit migration code and migrated task separately**

```powershell
git add scripts/migrate_current_job_prd_depth.py tests/test_current_job_prd_depth_migration.py
git commit -m "feat: migrate gameplay PRDs through generic depth policy"
git add data/jobs/8312a91c89e144e6a59f81b982f14c06/job.json
git commit -m "fix: rebuild current gameplay PRD with depth policy"
```

---

### Task 8: Full Regression, Browser Evidence, and Two Acceptance Gates

**Files:**
- Create: `scripts/qa-prd-depth-refactor.js`
- Create during execution only: `artifacts/prd-depth-refactor-2026-08-14/`
- Modify: no production files unless a failing regression receives its own test-first fix.

**Interfaces:**
- Browser QA writes `manifest.json` mapping every acceptance case to one unique screenshot path and inspected assertions.

- [ ] **Step 1: Add the browser QA script**

The script must capture distinct screens for: semantic directory, vehicle prose, weapon prose, random decision card, wave/monster depth, local diagram placement, inline screenshot placement, parameter table, and final preview. It must fail if two test cases reference the same screenshot or if any screenshot omits its expected heading.

- [ ] **Step 2: Run focused backend suites**

Run: `python -m pytest tests/test_planning_content_policy.py tests/test_gameplay_domain_policy.py tests/test_cross_project_prd_depth.py tests/test_feishu_language_quality.py tests/test_granularity_audit.py tests/test_gameplay_render.py tests/test_current_job_prd_depth_migration.py -q`

Expected: all tests pass.

- [ ] **Step 3: Run the complete backend suite**

Run: `python -m pytest -q`

Expected: all tests pass with no warnings introduced by this change.

- [ ] **Step 4: Run all JavaScript tests**

Run: `Get-ChildItem tests\js\*.test.js | ForEach-Object { node --test $_.FullName; if ($LASTEXITCODE -ne 0) { throw "JS test failed: $($_.Name)" } }`

Expected: every file exits with code 0.

- [ ] **Step 5: Run browser evidence capture**

Run: `node scripts/qa-prd-depth-refactor.js --base-url http://127.0.0.1:8000 --job 8312a91c89e144e6a59f81b982f14c06 --output artifacts/prd-depth-refactor-2026-08-14`

Expected: the manifest reports all content cases passed and every case has a different screenshot.

- [ ] **Step 6: Present acceptance point one**

Send the user the generator-root-cause cases, how to inspect them, automated results, and screenshot paths. Stop until the user accepts.

- [ ] **Step 7: Present acceptance point two**

After acceptance point one, send the rebuilt current-task cases, how to inspect each chapter, automated results, and screenshot paths. Stop until the user accepts.

- [ ] **Step 8: Commit QA assets that belong in source control**

```powershell
git add scripts/qa-prd-depth-refactor.js
git commit -m "test: add PRD depth browser acceptance"
```

Do not add generated screenshots or runtime artifacts unless the user explicitly requests them in Git.

---

## Plan Self-Review

- Spec coverage: carrier separation, sample isolation, domain activation, adaptive titles, non-AI language, mechanism closure, owner-specific attributes, local diagrams/screenshots, decision cards, current-task migration, Skill persistence, and cross-project blind tests each have an implementation task.
- Completeness scan: every code task names its function, tests, expected failure, implementation behavior, verification command, and commit boundary; unresolved gameplay facts are deliberately represented by decision-card behavior.
- Type consistency: normalization, domain, provenance, closure, rendering, and migration function names are unique and referenced consistently by later tasks.
- Scope: generic generator changes are completed and independently testable before the current-task migration; the migration cannot bypass the generic gates.
