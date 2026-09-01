from backend.document_assembler import build_final_document
from backend.master_planner_sanitizer import sanitize_semantics_for_master_planner
from backend.planner_quality_judge import evaluate_planner_quality
from backend.planning_language_renderer import render_rule
from backend.rule_status import normalize_rule_status, publication_allowed, strip_status_caveat


def _rule(**overrides):
    value = {
        "ruleId": "R-1",
        "semanticKey": "skill.candidates.draw",
        "ownerChapterId": "C-1",
        "ruleType": "logic",
        "schemaSlot": "normal_flow",
        "subject": "技能候选",
        "behavior": "系统从当前可用技能池中随机抽取3个候选技能",
        "evidenceIds": [],
        "reviewStatus": "approved",
        "semanticValidity": "valid",
        "knowledgeStatus": "INFERRED",
    }
    value.update(overrides)
    return value


def test_inferred_and_proposed_are_publishable():
    assert publication_allowed("INFERRED")
    assert publication_allowed("PROPOSED")
    assert not publication_allowed("CONFLICT")


def test_renderer_keeps_conclusion_and_uses_visual_metadata():
    rendered = render_rule(_rule(behavior="【黄色：推断】 系统从候选池随机抽取3项"))
    assert rendered["text"] == "系统从候选池随机抽取3项。"
    assert rendered["knowledgeStatus"] == "INFERRED"
    assert rendered["visualTone"] == "inference"
    assert "推断" not in rendered["text"]


def test_sanitizer_preserves_inferred_formula_and_parameter():
    chapter = {
        "claims": [{"text": "已满级技能移出候选池", "sourceType": "inference", "sourceFrameIds": []}],
        "parameterSchema": [{"name": "候选数量", "value": 3, "evidenceLevel": "planner"}],
        "formulae": [{"name": "候选抽取", "expression": "sample(pool, 3)", "evidenceLevel": "inference"}],
    }
    result = sanitize_semantics_for_master_planner(chapter)
    assert result["claims"][0]["knowledgeStatus"] == "INFERRED"
    assert result["parameterSchema"][0]["knowledgeStatus"] == "PROPOSED"
    assert result["formulae"][0]["knowledgeStatus"] == "INFERRED"


def test_final_document_deduplicates_by_semantic_key_and_keeps_yellow_tone():
    approved = {
        "chapters": [{"chapterId": "C-1", "title": "技能候选", "system": "局内成长", "object": "技能候选"}],
        "rules": [
            _rule(),
            _rule(ruleId="R-2", behavior="系统从当前可用技能池中随机抽取3个候选技能"),
        ],
        "gaps": [],
    }
    doc = build_final_document(approved)
    sentences = doc["systems"][0]["objects"][0]["chapters"][0]["groups"][0]["sentences"]
    assert len(sentences) == 1
    assert sentences[0]["visualTone"] == "inference"
    assert set(sentences[0]["sourceRuleIds"]) == {"R-1", "R-2"}


def test_quality_judge_rejects_hidden_inference_but_not_explicit_inference():
    hidden = _rule(knowledgeStatus=None, inferenceLevel="inferred")
    explicit = _rule(knowledgeStatus="INFERRED", inferenceLevel="inferred", trigger="玩家升级", result="进入技能选择状态")
    hidden_report = evaluate_planner_quality({"chapters": [{"chapterId": "C-1"}], "rules": [hidden]})
    explicit_report = evaluate_planner_quality({"chapters": [{"chapterId": "C-1"}], "rules": [explicit]})
    assert any(item["dimension"] == "hiddenInference" for item in hidden_report["findings"])
    assert not any(item["dimension"] == "hiddenInference" for item in explicit_report["findings"])


def test_legacy_caveat_is_removed_without_changing_business_copy():
    assert strip_status_caveat("【黄色：推断】 玩家升级后进入三选一") == "玩家升级后进入三选一"
    assert normalize_rule_status(None, source_type="planner") == "PROPOSED"
