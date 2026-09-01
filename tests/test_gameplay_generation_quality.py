import json
import os
import time
from copy import deepcopy
from pathlib import Path

from backend.gameplay_generation_quality import (
    GameplayGenerationQualityError,
    evidence_fingerprint,
    preserve_planner_decisions,
    prune_cached_responses,
    require_quality_floor,
    quality_report,
)


def test_generation_cache_pruning_removes_only_expired_json(tmp_path):
    cache = tmp_path / ".gameplay-generation-cache"
    cache.mkdir()
    expired = cache / "expired.json"
    current = cache / "current.json"
    unrelated = cache / "keep.txt"
    expired.write_text("{}", encoding="utf-8")
    current.write_text("{}", encoding="utf-8")
    unrelated.write_text("keep", encoding="utf-8")
    now = time.time()
    os.utime(expired, (now - 8 * 24 * 60 * 60, now - 8 * 24 * 60 * 60))

    assert prune_cached_responses(cache, now=now) == [expired]
    assert not expired.exists()
    assert current.exists()
    assert unrelated.exists()


def test_same_ordered_evidence_and_generation_contract_share_one_fingerprint(tmp_path):
    left = tmp_path / "left"
    right = tmp_path / "right"
    (left / "frames").mkdir(parents=True)
    (right / "frames").mkdir(parents=True)
    (left / "frames" / "F0001.jpg").write_bytes(b"same-image")
    (right / "frames" / "F0001.jpg").write_bytes(b"same-image")
    job = {"frames": [{"id": "F0001", "imageUrl": "/frames/F0001.jpg"}]}

    first = evidence_fingerprint(job, left, model="vision-v1", prompt_version="gameplay-v1")
    second = evidence_fingerprint(job, right, model="vision-v1", prompt_version="gameplay-v1")

    assert first == second
    assert first != evidence_fingerprint(job, right, model="vision-v2", prompt_version="gameplay-v1")


def test_generation_cache_is_isolated_by_project_identity_even_for_identical_frames(tmp_path):
    left = tmp_path / "left"
    right = tmp_path / "right"
    for root in (left, right):
        (root / "frames").mkdir(parents=True)
        (root / "frames" / "F0001.jpg").write_bytes(b"same-image")
    base = {"frames": [{"id": "F0001", "imageUrl": "/frames/F0001.jpg"}]}

    first = evidence_fingerprint({**base, "id": "project-a"}, left, model="vision-v1", prompt_version="gameplay-v1")
    second = evidence_fingerprint({**base, "id": "project-b"}, right, model="vision-v1", prompt_version="gameplay-v1")

    assert first != second


def test_generation_cache_is_isolated_by_interaction_and_approved_model_revisions(tmp_path):
    (tmp_path / "frames").mkdir()
    (tmp_path / "frames" / "F0001.jpg").write_bytes(b"same-image")
    base = {
        "id": "same-project",
        "frames": [{"id": "F0001", "imageUrl": "/frames/F0001.jpg"}],
        "interactionModel": {"revision": 7},
        "gameplayReviewModel": {"revision": 3},
    }

    original = evidence_fingerprint(base, tmp_path, model="vision-v1", prompt_version="gameplay-v1")
    interaction_changed = evidence_fingerprint(
        {**base, "interactionModel": {"revision": 8}}, tmp_path, model="vision-v1", prompt_version="gameplay-v1",
    )
    approval_changed = evidence_fingerprint(
        {**base, "gameplayReviewModel": {"revision": 4}}, tmp_path, model="vision-v1", prompt_version="gameplay-v1",
    )

    assert len({original, interaction_changed, approval_changed}) == 3


def test_regeneration_never_overwrites_confirmed_or_planner_edited_content():
    existing = {
        "directory": {"status": "confirmed", "understanding": {"summary": "主策确认的理解"}},
        "chapters": [{
            "id": "GCH-001", "scope": "人工章节名", "plannerSummary": "人工规则",
            "summarySource": "planner", "confirmation": {"confirmed": True, "revision": 3},
        }],
    }
    candidate = {
        "directory": {"status": "draft", "understanding": {"summary": "模型改写"}},
        "chapters": [{
            "id": "GCH-001", "scope": "模型章节名", "plannerSummary": "模型规则",
            "confirmation": {"confirmed": False},
        }],
    }

    result = preserve_planner_decisions(existing, candidate)

    assert result["directory"] == existing["directory"]
    assert result["chapters"][0] == existing["chapters"][0]


def test_low_quality_generation_is_rejected_instead_of_replacing_last_good_result():
    shallow = {
        "systems": [{"name": "玩法系统"}],
        "directory": {"understanding": {"summary": "玩法规则。"}, "entries": []},
        "chapters": [{
            "id": "GCH-001", "plannerSummary": "随机武器抽取的玩法规则。",
            "plannerSections": {"summary": "随机武器抽取的玩法规则。"},
        }],
    }

    try:
        require_quality_floor(shallow, "details")
    except GameplayGenerationQualityError:
        return
    raise AssertionError("low-quality gameplay generation must be rejected")


def test_detail_autofill_preserves_confirmation_but_replaces_shallow_generated_copy():
    existing = {
        "chapters": [{
            "id": "GCH-001", "status": "approved",
            "confirmation": {"confirmed": True, "revision": 10},
            "plannerSections": {"summary": "旧的浅层说明。", "normalFlow": [], "keyRules": []},
        }],
    }
    candidate = {
        "chapters": [{
            "id": "GCH-001", "status": "pending", "confirmation": {"confirmed": False},
            "plannerSections": {
                "summary": "依据素材重新补全的说明。",
                "normalFlow": ["满足条件后开始。"],
                "keyRules": ["按确认顺序处理。"],
                "specialCases": ["条件不足时不执行。"],
                "acceptanceExamples": [{"scene": "正常情况", "action": "满足条件", "expected": "规则生效"}],
            },
        }],
    }

    result = preserve_planner_decisions(existing, candidate, refresh_confirmed_content=True)

    chapter = result["chapters"][0]
    assert chapter["plannerSections"]["summary"] == "依据素材重新补全的说明。"
    assert chapter["status"] == "approved"
    assert chapter["confirmation"] == {"confirmed": True, "revision": 10}


def test_detail_autofill_refreshes_generated_directory_summaries_without_renaming_confirmed_entries():
    existing = {
        "directory": {
            "status": "confirmed",
            "entries": [{"chapterId": "GCH-001", "title": "随机武器抽取", "summary": "武器自动攻击敌人。"}],
        },
        "chapters": [{
            "id": "GCH-001", "scope": "随机武器抽取", "status": "approved",
            "confirmation": {"confirmed": True}, "summarySource": "generated",
            "plannerSummary": "武器自动攻击敌人。",
        }],
    }
    candidate = {
        "directory": {"status": "draft", "entries": []},
        "chapters": [{
            "id": "GCH-001", "scope": "随机武器抽取", "status": "pending",
            "confirmation": {"confirmed": False}, "summarySource": "generated",
            "plannerSummary": "玩家从候选池随机获得一种武器或技能。",
            "plannerSections": {"summary": "玩家从候选池随机获得一种武器或技能。"},
        }],
    }

    result = preserve_planner_decisions(existing, candidate, refresh_confirmed_content=True)

    assert result["directory"]["entries"][0] == {
        "chapterId": "GCH-001", "title": "随机武器抽取",
        "summary": "玩家从候选池随机获得一种武器或技能。",
    }


def test_implementation_ready_chapter_passes_the_ninety_point_floor():
    model = {
        "systems": [{"name": "战斗系统"}],
        "directory": {"understanding": {"summary": "玩家控制载具推进并击败敌人。"}, "entries": []},
        "chapters": [{
            "id": "GCH-001", "scope": "载具战斗", "sourceFrameIds": ["F0001"],
            "mechanism": {"type": "custom", "rules": "载具持续攻击有效目标。"},
            "plannerSummary": "载具持续攻击有效目标，击败敌人后继续推进。",
            "plannerSections": {
                "summary": "载具持续攻击有效目标，击败敌人后继续推进。",
                "normalFlow": ["进入战斗后锁定有效目标并持续攻击。"],
                "keyRules": ["目标失效后重新选择目标。"],
                "specialCases": ["没有有效目标时保持推进。"],
                "acceptanceExamples": ["目标被击败后能够继续选择下一目标。"],
            },
            "acceptanceCases": [{"scene": "正常战斗", "action": "击败目标", "expected": "继续推进"}],
            "dependencies": [],
        }],
    }

    assert require_quality_floor(model, "details")["generationQuality"]["score"] >= 90


def test_candidate_cannot_fall_below_the_approved_reference_density():
    model = {
        "systems": [{"name": "成长系统"}],
        "directory": {"understanding": {"summary": "玩家选择强化改变能力。"}, "entries": []},
        "chapters": [{
            "id": "GCH-001", "scope": "强化选择", "sourceFrameIds": ["F0001"],
            "mechanism": {"type": "custom", "rules": "选择后立即生效。"},
            "plannerSummary": "玩家从候选项中选择一项强化。",
            "plannerSections": {"normalFlow": ["出现候选项。"], "specialCases": ["无候选时停止。"],
                                "acceptanceExamples": ["选择后能力变化。"]},
            "acceptanceCases": [{"scene": "正常", "action": "选择", "expected": "生效"}],
            "dependencies": [],
        }],
    }

    report = quality_report(model, "details", references=[{"normalFlowItems": 3, "keyRuleItems": 2,
                                                           "specialCaseItems": 1, "acceptanceItems": 2}])

    assert not report["passed"]
    assert any("REFERENCE_DENSITY" in item for item in report["errors"])


def test_quality_reports_persist_structure_and_detail_scores_separately():
    model = {
        "systems": [{"name": "创建系统"}],
        "directory": {"understanding": {"summary": "玩家创建角色。"}, "entries": []},
        "chapters": [{
            "id": "GCH-001", "scope": "角色创建", "chapterType": "custom", "sourceFrameIds": ["F0001"],
            "mechanism": {"type": "custom", "rules": "确认后创建角色。"},
            "plannerSections": {
                "normalFlow": ["玩家输入名称并确认创建。", "系统保存角色并进入初始场景。"],
                "keyRules": ["名称不能为空。"], "specialCases": ["名称重复时保持在当前页面。"],
                "acceptanceExamples": ["输入有效名称后角色创建成功。"],
            },
            "acceptanceCases": [{"scene": "有效输入", "action": "确认", "expected": "创建并进入场景"}],
            "dependencies": [],
        }],
    }

    require_quality_floor(model, "structure")
    structure = deepcopy(model["structureQuality"])
    require_quality_floor(model, "details")

    assert model["structureQuality"] == structure
    assert model["detailQuality"]["passed"] is True
    assert model["generationQuality"] == model["detailQuality"]


def test_detail_quality_rejects_static_evidence_masquerading_as_flow():
    model = {
        "systems": [{"name": "经营系统"}],
        "directory": {"understanding": {"summary": "店铺经营规则。"}, "entries": []},
        "chapters": [{
            "id": "GCH-001", "scope": "店铺等级", "chapterType": "presentation", "sourceFrameIds": ["F0001"],
            "mechanism": {"type": "custom", "rules": "显示店铺数据。"},
            "plannerSections": {
                "normalFlow": ["界面显示当前等级2767级。", "底部显示每秒收益4.9万。"],
                "keyRules": ["等级上限由配置决定。"], "specialCases": ["达到上限后不再升级。"],
                "acceptanceExamples": ["等级和收益显示正确。"],
            },
            "acceptanceCases": [{"scene": "打开页面", "action": "查看", "expected": "显示当前数据"}],
            "dependencies": [],
        }],
    }

    report = quality_report(model, "details")

    assert report["passed"] is False
    assert any("FLOW_CHAIN" in item for item in report["errors"])

    try:
        require_quality_floor(model, "details")
    except GameplayGenerationQualityError:
        pass
    assert model["detailQuality"]["passed"] is False


def test_detail_quality_cannot_ignore_granularity_findings():
    model = {
        "granularityAuditVersion": 5,
        "reviewState": {"structurePhase": "detailed"},
        "systems": [{"name": "经营系统"}],
        "directory": {"understanding": {"summary": "玩家升级店铺。"}, "entries": []},
        "chapters": [{
            "id": "GCH-001", "scope": "店铺升级", "sourceFrameIds": ["F0001"],
            "granularityEvidence": {
                "executionSequence": {"sourceIds": ["DOC-1"], "requiredFacts": ["扣除资源", "提升等级"]},
            },
            "mechanism": {"type": "custom", "rules": "升级后收益提高。"},
            "plannerSections": {
                "summary": "玩家升级店铺。",
                "normalFlow": ["点击升级后收益提高。"],
                "keyRules": ["每次只升一级。"],
                "specialCases": ["资源不足时不执行。"],
                "acceptanceExamples": ["资源足够时升级成功。"],
            },
            "acceptanceCases": [{"scene": "资源足够", "action": "升级", "expected": "收益提高"}],
            "dependencies": [],
        }],
    }

    report = quality_report(model, "details")

    assert report["passed"] is False
    assert any("GRANULARITY_EXECUTIONSEQUENCE_FACTS_MISSING" in item for item in report["errors"])


def test_golden_quality_samples_keep_their_expected_grade():
    samples = json.loads((Path(__file__).parent / "fixtures" / "gameplay_quality_golden.json").read_text(encoding="utf-8"))
    for sample in samples:
        assert quality_report(sample["model"], "details")["passed"] is sample["expectedPassed"], sample["name"]


def test_parameter_driven_mechanism_cannot_pass_without_configuration_depth():
    model = {
        "systems": [{"name": "成长系统"}],
        "directory": {"understanding": {"summary": "玩家升级单位并获得属性提升。"}, "entries": []},
        "chapters": [{
            "id": "GCH-001", "scope": "单位升级", "sourceFrameIds": ["F0001"],
            "mechanism": {"type": "progression", "unlock": "达到条件后开放", "levels": "逐级提升"},
            "plannerSummary": "玩家消耗资源提升单位等级。",
            "plannerSections": {"normalFlow": ["消耗资源后提升一级。"], "keyRules": ["升级不可逆。"],
                                "specialCases": ["达到上限后不可继续升级。"],
                                "acceptanceExamples": ["资源足够时升级成功。"]},
            "acceptanceCases": [{"scene": "资源足够", "action": "升级", "expected": "等级提升"}],
            "dependencies": [],
        }],
    }

    report = quality_report(model, "details")

    assert not report["passed"]
    assert report["chapters"][0]["score"] <= 85

    model["chapters"][0]["parameterSchema"] = [{
        "name": "升级消耗", "plannerMeaning": "每级升级所需资源数量", "type": "整数",
        "unit": "个", "defaultValue": "需要策划决定", "range": "大于等于零",
        "configurationSource": "升级配置表", "rounding": "取整", "evidenceLevel": "参考文档明确说明",
        "referenceSource": "载具升级说明",
    }]
    assert quality_report(model, "details")["passed"]


def test_review_entry_accepts_grounded_rules_with_parameter_decision_card_but_delivery_floor_stays_strict():
    model = {
        "systems": [{"name": "经营系统"}],
        "directory": {"understanding": {"summary": "玩家升级店铺并提高经营收益。"}, "entries": []},
        "chapters": [{
            "id": "GCH-001", "scope": "店铺等级与收益", "sourceFrameIds": ["F0001"],
            "mechanism": {"type": "progression", "unlock": "进入店铺后开放升级", "effect": "升级后提高经营收益"},
            "plannerSummary": "玩家投入资源提升店铺等级，并获得更高的持续收益。",
            "plannerSections": {
                "normalFlow": ["玩家进入店铺并选择升级。", "系统扣除资源、提升等级并刷新收益。"],
                "keyRules": ["每次升级只提升一级。"],
                "specialCases": ["资源不足时不扣除资源，等级保持不变。"],
                "acceptanceExamples": ["资源足够时升级成功并刷新收益。"],
            },
            "acceptanceCases": [{"scene": "资源足够", "action": "升级", "expected": "等级和收益提高"}],
            "dependencies": [],
            "decisionCards": [{
                "id": "GDC-001", "question": "升级消耗和收益增量采用哪套配置？", "status": "pending",
                "selectionMode": "single", "allowCustom": True,
                "options": [{"id": "existing", "label": "沿用现有配置"}, {"id": "new", "label": "补充新配置"}],
                "impacts": ["参数表", "玩法正文", "验收用例", "最终文档"],
            }],
        }],
    }

    assert quality_report(model, "details")["passed"] is False
    review_report = quality_report(model, "details", allow_pending_decisions=True)
    assert review_report["passed"] is True
    assert review_report["mode"] == "review_entry"


def test_review_entry_scores_a_grounded_rule_with_an_explicit_pending_gap_as_reviewable():
    model = {
        "systems": [{"name": "经营系统"}],
        "directory": {"understanding": {"summary": "玩家经营店铺并提升持续收益。"}, "entries": []},
        "chapters": [{
            "id": "GCH-001",
            "scope": "店铺升级",
            "sourceFrameIds": ["F0001"],
            "mechanism": {"type": "custom", "rules": "玩家确认升级后，系统提升店铺等级。"},
            "plannerSummary": "玩家确认升级后，店铺等级随之提高。",
            "plannerSections": {
                "normalFlow": ["玩家确认升级后，系统提升店铺等级。"],
                "keyRules": [],
                "specialCases": [],
                "acceptanceExamples": [],
            },
            "decisionCards": [{
                "id": "GDC-001",
                "question": "截图未证明升级消耗和失败反馈，应采用哪种规则？",
                "status": "pending",
                "selectionMode": "single",
                "allowCustom": True,
                "options": [
                    {"id": "configure", "label": "由策划补齐消耗与失败反馈"},
                    {"id": "omit", "label": "本阶段不配置消耗与失败反馈"},
                ],
                "impacts": ["玩法正文", "验收用例", "最终文档"],
            }],
        }],
    }

    strict = quality_report(model, "details")
    review = quality_report(model, "details", allow_pending_decisions=True)

    assert strict["passed"] is False
    assert review["passed"] is True
    assert review["chapters"][0]["score"] >= review["threshold"]


def test_review_entry_does_not_force_reference_density_that_evidence_left_pending():
    model = {
        "systems": [{"name": "经营系统"}],
        "directory": {"understanding": {"summary": "玩家经营店铺并提升持续收益。"}, "entries": []},
        "chapters": [{
            "id": "GCH-001",
            "scope": "店铺升级",
            "sourceFrameIds": ["F0001"],
            "mechanism": {"type": "custom", "rules": "玩家确认升级后，系统提升店铺等级。"},
            "plannerSummary": "玩家确认升级后，店铺等级随之提高。",
            "plannerSections": {
                "normalFlow": ["玩家确认升级后，系统提升店铺等级。"],
                "keyRules": [],
                "specialCases": [],
                "acceptanceExamples": [],
            },
            "decisionCards": [{
                "id": "GDC-001",
                "question": "截图未证明失败反馈和验收结果，应采用哪种规则？",
                "status": "pending",
                "selectionMode": "single",
                "options": [
                    {"id": "configure", "label": "由策划补齐"},
                    {"id": "omit", "label": "确认不配置"},
                ],
                "impacts": ["玩法正文", "验收用例", "最终文档"],
            }],
        }],
    }
    reference = [{
        "normalFlowItems": 1,
        "keyRuleItems": 2,
        "specialCaseItems": 2,
        "acceptanceItems": 2,
    }]

    strict = quality_report(model, "details", references=reference)
    review = quality_report(model, "details", references=reference, allow_pending_decisions=True)

    assert any("REFERENCE_DENSITY" in item for item in strict["errors"])
    assert not any("REFERENCE_DENSITY" in item for item in review["errors"])
    assert review["passed"] is True


def test_formula_requires_order_rounding_evidence_and_example_when_values_are_known():
    parameter = {
        "name": "攻击力", "plannerMeaning": "参与伤害计算的攻击值", "type": "整数", "unit": "点",
        "defaultValue": 100, "range": "0以上", "configurationSource": "战斗配置表",
        "rounding": "取整", "evidenceLevel": "参考文档明确说明", "referenceSource": "战斗规则",
    }
    model = {
        "systems": [{"name": "战斗系统"}],
        "directory": {"understanding": {"summary": "根据战斗属性计算伤害。"}, "entries": []},
        "chapters": [{
            "id": "GCH-001", "scope": "伤害计算", "sourceFrameIds": ["F0001"],
            "mechanism": {"type": "formula", "formula": "伤害=攻击力"}, "parameterSchema": [parameter],
            "formulae": [{"name": "伤害公式", "expression": "伤害=攻击力"}],
            "plannerSummary": "根据攻击力计算伤害。",
            "plannerSections": {"normalFlow": ["读取攻击力并计算伤害。"], "keyRules": ["按顺序结算。"],
                                "specialCases": ["无效目标不结算。"], "acceptanceExamples": ["攻击后扣减生命。"]},
            "acceptanceCases": [{"scene": "有效目标", "action": "攻击", "expected": "扣减生命"}],
            "dependencies": [],
        }],
    }
    assert not quality_report(model, "details")["passed"]

    model["chapters"][0]["formulae"][0].update({
        "calculationOrder": "读取攻击力→计算→取整→扣减生命", "rounding": "取整",
        "evidenceLevel": "参考文档明确说明", "referenceSource": "战斗规则",
    })
    model["chapters"][0]["workedExamples"] = [{"title": "算例", "steps": "攻击力100，代入后伤害为100。"}]
    assert quality_report(model, "details")["passed"]


def test_evidence_applicable_depth_is_blocked_when_the_required_content_is_missing():
    model = {
        "systems": [{"name": "成长系统"}],
        "directory": {"understanding": {"summary": "玩家获得强化并改变本局能力。"}, "entries": []},
        "chapters": [{
            "id": "GCH-001", "scope": "强化选择", "sourceFrameIds": ["F0001"],
            "mechanism": {"type": "custom", "rules": "玩家选择一项强化。"},
            "plannerSummary": "玩家从候选项中选择一项强化。",
            "plannerSections": {"normalFlow": ["选择后强化生效。"], "keyRules": ["一次选择一项。"],
                                "specialCases": ["没有候选项时不弹出。"], "acceptanceExamples": ["选择后属性变化。"]},
            "acceptanceCases": [{"scene": "正常", "action": "选择", "expected": "生效"}],
            "granularityEvidence": {"lifecycle": {"sourceIds": ["DOC-19"], "applicable": True}},
        }],
    }

    report = quality_report(model, "details")

    assert not report["passed"]
    assert any("GRANULARITY_LIFECYCLE_MISSING" in item for item in report["errors"])


def test_absent_evidence_does_not_force_formula_configuration_or_lifecycle_templates():
    model = {
        "systems": [{"name": "战斗系统"}],
        "directory": {"understanding": {"summary": "载具前进并对抗敌人。"}, "entries": []},
        "chapters": [{
            "id": "GCH-001", "scope": "载具移动", "sourceFrameIds": ["F0001"],
            "mechanism": {"type": "custom", "rules": "载具沿路线前进。"},
            "plannerSummary": "载具沿路线前进，玩家调整横向位置。",
            "plannerSections": {"normalFlow": ["载具持续前进。"], "keyRules": ["玩家只能调整横向位置。"],
                                "specialCases": ["超出范围时停止移动。"], "acceptanceExamples": ["拖动后位置变化。"]},
            "acceptanceCases": [{"scene": "正常", "action": "拖动", "expected": "位置变化"}],
            "granularityEvidence": {},
        }],
    }

    report = quality_report(model, "details")

    assert not any("GRANULARITY_" in item for item in report["errors"])


def test_qualified_structure_response_is_reused_without_calling_the_model_again(tmp_path):
    import sys
    import types

    sys.modules.setdefault("openai", types.SimpleNamespace(OpenAI=object))
    from backend import gameplay_analysis

    (tmp_path / "frames").mkdir()
    (tmp_path / "frames" / "F0001.jpg").write_bytes(b"stable-frame")
    job = {"id": "stable-job", "interactionModel": {"revision": 1}, "frames": [{"id": "F0001", "imageUrl": "/frames/F0001.jpg"}]}
    response = {"systems": [{
        "name": "战斗推进", "reason": "载具持续推进并对抗敌人。",
        "subsystems": [{"name": "载具控制", "mechanisms": [{
            "name": "载具移动", "reason": "玩家调整载具位置并继续推进。", "sourceFrameIds": ["F0001"],
        }]}],
    }]}
    calls = []
    original_client, original_call = gameplay_analysis._client, gameplay_analysis._call
    gameplay_analysis._client = lambda _config: object()
    gameplay_analysis._call = lambda *_args, **_kwargs: calls.append(1) or response
    try:
        model_name = "vision-" + tmp_path.name
        gameplay_analysis.generate_gameplay_structure(job, tmp_path, {"model": model_name})
        gameplay_analysis.generate_gameplay_structure(job, tmp_path, {"model": model_name})
    finally:
        gameplay_analysis._client, gameplay_analysis._call = original_client, original_call

    assert calls == [1]


def test_low_quality_structure_is_repaired_once_and_only_qualified_result_is_cached(tmp_path):
    import sys
    import types

    sys.modules.setdefault("openai", types.SimpleNamespace(OpenAI=object))
    from backend import gameplay_analysis

    (tmp_path / "frames").mkdir()
    (tmp_path / "frames" / "F0001.jpg").write_bytes(b"repair-frame")
    job = {"id": "repair-job", "frames": [{"id": "F0001", "imageUrl": "/frames/F0001.jpg"}]}
    bad = {"systems": []}
    good = {"systems": [{
        "name": "战斗推进", "reason": "载具持续推进并对抗敌人。",
        "subsystems": [{"name": "载具控制", "mechanisms": [{
            "name": "载具移动", "reason": "玩家调整载具位置并继续推进。", "sourceFrameIds": ["F0001"],
        }]}],
    }]}
    calls = []
    cache_root = tmp_path.parent / ".gameplay-generation-cache"
    before_cache = set(cache_root.glob("*.json")) if cache_root.exists() else set()
    original_client, original_call = gameplay_analysis._client, gameplay_analysis._call
    gameplay_analysis._client = lambda _config: object()
    gameplay_analysis._call = lambda *_args, **_kwargs: calls.append(1) or (bad if len(calls) == 1 else good)
    try:
        model = gameplay_analysis.generate_gameplay_structure(job, tmp_path, {"model": "repair-" + tmp_path.name})
    finally:
        gameplay_analysis._client, gameplay_analysis._call = original_client, original_call

    assert calls == [1, 1]
    assert model["chapters"]
    assert len(set(cache_root.glob("*.json")) - before_cache) == 1
