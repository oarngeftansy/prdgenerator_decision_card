from backend.document_assembler import assemble_chapter, build_final_document
from backend.document_quality_evaluator import evaluate_document
from backend.planning_language_renderer import render_rule
from backend.planning_style_linter import lint_document


PROFILE = {"forbidden_expressions": ["为了", "从而", "该设计旨在"]}


def rule(rule_id="R1", rule_type="logic", behavior="敌人接触载具后触发伤害", **extra):
    value = {
        "ruleId": rule_id,
        "ownerChapterId": "C1",
        "semanticKey": f"C1:s:{rule_type}:{rule_id}",
        "ruleType": rule_type,
        "schemaSlot": "s",
        "subject": "敌人",
        "trigger": None,
        "conditions": [],
        "behavior": behavior,
        "result": None,
        "stateChange": None,
        "exitCondition": None,
        "exception": None,
        "sourceFactIds": [f"F-{rule_id}"],
        "evidenceIds": [f"E-{rule_id}"],
        "reviewStatus": "approved",
        "semanticValidity": "valid",
    }
    value.update(extra)
    return value


def test_renderer_rejects_unapproved_rules_and_keeps_traceability():
    rejected = render_rule(rule(reviewStatus="unreviewed"), PROFILE)
    assert rejected["status"] == "rejected"
    rendered = render_rule(rule(), PROFILE)
    assert rendered["text"] == "敌人接触载具后触发伤害。"
    assert rendered["sourceRuleIds"] == ["R1"]
    assert rendered["sourceFactIds"] == ["F-R1"]


def test_renderer_uses_controlled_variants_without_adding_semantics():
    rendered = render_rule(rule(behavior="终极词条改变攻击方向将武器喷射方向由单方向改为四向喷射"), PROFILE)
    assert rendered["text"] == "终极词条将武器喷射方向由单方向改为四向喷射。"


def test_assembler_separates_presentation_and_never_confirms_gaps():
    chapter = {"chapterId": "C1", "system": "核心战斗", "object": "怪物", "title": "攻击"}
    result = assemble_chapter(
        chapter,
        [rule(), rule("R2", "presentation", "首领来袭时显示提示文字")],
        [{"gapId": "G1", "chapterId": "C1", "question": "怪物在什么条件下停止攻击？", "status": "reviewed_open"}],
        PROFILE,
    )
    assert [group["title"] for group in result["groups"]] == ["逻辑规则", "表现规则"]
    assert result["reviewedGaps"] == []
    assert "待确认" not in "".join(sentence["text"] for group in result["groups"] for sentence in group["sentences"])


def test_final_document_metrics_are_semantic_and_traceable():
    data = {
        "chapters": [{"chapterId": "C1", "system": "核心战斗", "object": "怪物", "title": "攻击"}],
        "rules": [rule(), rule("R2", "presentation", "敌人受击时显示伤害数字")],
        "gaps": [],
    }
    document = build_final_document(data, PROFILE, title="测试 B 版")
    metrics = evaluate_document(document, data["rules"], data["gaps"], PROFILE)
    assert metrics["unsupportedBodySentenceCount"] == 0
    assert metrics["mixedLogicPresentationCount"] == 0
    assert metrics["gapPromotedToConfirmedCount"] == 0
    assert metrics["ruleToFinalSentenceTraceabilityRate"] == 1.0
    assert lint_document(document, PROFILE)["pass"] is True
    chapter = document["systems"][0]["objects"][0]["chapters"][0]
    assert chapter["foldIntoObject"] is False
