from copy import deepcopy
from pathlib import Path

from backend.gve16_alignment_corpus import load_gve16_alignment_corpus
from backend.target_alignment_evaluator import evaluate_target_alignment


ROOT = Path(__file__).resolve().parents[1]
CORPUS = load_gve16_alignment_corpus(ROOT / "data/quality/gve16-alignment-corpus-v1.json")


RULES = [
    {"ruleId": "R1", "ruleType": "logic", "reviewStatus": "approved", "semanticValidity": "valid", "schemaSlot": "movement_trigger", "behavior": "对象沿路径移动", "sourceFactIds": ["F1"]},
    {"ruleId": "R2", "ruleType": "interaction", "reviewStatus": "approved", "semanticValidity": "valid", "schemaSlot": "movement_control", "behavior": "玩家调整横向位置", "sourceFactIds": ["F2"]},
]
FACTS = [{"factId": "F1", "evidenceLevel": "observed"}, {"factId": "F2", "evidenceLevel": "observed"}]
BLOCKS = [{
    "blockId": "B1", "chapterId": "C1", "owner": "对象", "mechanismSemantic": "移动方式", "status": "partial_mechanism_chain",
    "processing": [{"ruleId": "R1", "ruleType": "logic", "schemaSlot": "movement_trigger", "resolutionStatus": "executable"}],
    "input_constraint": [{"ruleId": "R2", "ruleType": "interaction", "schemaSlot": "movement_control", "resolutionStatus": "executable"}],
    "presentation": [], "emptyFields": ["result", "exit_boundary"], "unabsorbedGapIds": ["G1"],
}]
DELIVERY = {
    "chapters": [{"chapterId": "C1", "title": "对象 / 移动", "paragraphs": [{
        "paragraphId": "P1", "kind": "execution_rule", "heading": "移动方式", "format": "sentence",
        "text": "对象沿路径移动，玩家可调整横向位置。", "ruleIds": ["R1", "R2"],
    }]}],
    "metrics": {"unsupportedSemanticAdditionCount": 0, "logicPresentationDuplicateDescriptionCount": 0, "visualReferenceResolutionRate": 1.0},
}
GAPS = [{"gapId": "G1", "chapterId": "C1", "schemaSlot": "movement_stop_condition", "severity": "implementation_blocking", "status": "open"}]


def _evaluate(delivery=DELIVERY, rules=RULES, facts=FACTS, gaps=GAPS, params=None):
    return evaluate_target_alignment(delivery, BLOCKS, [], rules, facts, gaps, params or [], CORPUS)


def test_paradigm_alignment_is_independent_from_gap_closure():
    open_result = _evaluate()
    closed = [{**GAPS[0], "status": "closed"}]
    closed_result = _evaluate(gaps=closed)
    assert open_result["paradigmAlignment"] == closed_result["paradigmAlignment"]
    assert open_result["executionCompleteness"]["total"] < closed_result["executionCompleteness"]["total"]


def test_absent_parameter_contract_does_not_reduce_paradigm_alignment():
    numeric = RULES + [{"ruleId": "R3", "ownerChapterId": "C1", "ruleType": "numeric", "reviewStatus": "approved", "semanticValidity": "valid", "schemaSlot": "movement_speed_source", "behavior": "移动速度读取配置", "sourceFactIds": []}]
    absent = _evaluate(rules=numeric, params=[])
    complete = _evaluate(rules=numeric, params=[{"parameterContractId": "PC1", "relatedRuleIds": ["R3"], "status": "resolved"}])
    assert absent["paradigmAlignment"] == complete["paradigmAlignment"]
    assert absent["executionCompleteness"]["dimensions"]["parameterContractCompleteness"] < complete["executionCompleteness"]["dimensions"]["parameterContractCompleteness"]


def test_clean_report_has_two_independent_score_sets_and_pending_status():
    result = _evaluate(gaps=[{**GAPS[0], "status": "closed"}])
    assert set(result["paradigmAlignment"]["dimensions"]) == {
        "chapterOrganization", "bodyGranularity", "planningLanguage", "informationDensity",
        "mechanismBlockOrganization", "deliveryLayering",
    }
    assert set(result["executionCompleteness"]["dimensions"]) == {
        "mechanismChainCompleteness", "programExecutability", "qaTestability",
        "parameterContractCompleteness", "gapClosure",
    }
    assert result["qualificationStatus"] in {"not_qualified", "pending"}


def test_hard_gate_fails_for_inferred_fact_in_confirmed_text():
    inferred = [{"factId": "F1", "evidenceLevel": "inferred"}, FACTS[1]]
    result = _evaluate(facts=inferred)
    assert result["hardGates"]["inferredFactRenderedAsConfirmed"]["passed"] is False
    assert result["qualificationStatus"] == "fail"


def test_hard_gate_fails_for_presentation_in_logic_body():
    rules = RULES + [{"ruleId": "RP", "ruleType": "presentation", "reviewStatus": "approved", "semanticValidity": "valid", "schemaSlot": "movement_presentation", "behavior": "显示路线", "sourceFactIds": []}]
    delivery = deepcopy(DELIVERY)
    delivery["chapters"][0]["paragraphs"][0]["ruleIds"].append("RP")
    result = _evaluate(delivery=delivery, rules=rules)
    assert result["hardGates"]["presentationMixedIntoLogicBody"]["passed"] is False
    assert result["qualificationStatus"] == "fail"


def test_hard_gate_fails_for_gap_confirmed_as_rule():
    delivery = deepcopy(DELIVERY)
    delivery["chapters"][0]["paragraphs"][0]["gapIds"] = ["G1"]
    result = _evaluate(delivery=delivery)
    assert result["hardGates"]["gapRenderedAsConfirmedRule"]["passed"] is False


def test_no_rule_provenance_fails_unsupported_and_traceability_gates():
    delivery = deepcopy(DELIVERY)
    delivery["chapters"][0]["paragraphs"][0]["ruleIds"] = []
    result = _evaluate(delivery=delivery)
    assert result["hardGates"]["unsupportedSemanticAddition"]["passed"] is False
    assert result["hardGates"]["ruleToFinalOutputTraceability"]["passed"] is False
    assert result["qualificationStatus"] == "fail"


def test_deleting_rule_cannot_raise_information_density():
    complete = _evaluate()
    delivery = deepcopy(DELIVERY)
    delivery["chapters"][0]["paragraphs"][0]["ruleIds"] = ["R1"]
    deleted = _evaluate(delivery=delivery)
    assert deleted["paradigmAlignment"]["dimensions"]["informationDensity"] <= complete["paradigmAlignment"]["dimensions"]["informationDensity"]


def test_meaningless_heading_cannot_raise_chapter_organization():
    clean = _evaluate()
    delivery = deepcopy(DELIVERY)
    delivery["chapters"][0]["paragraphs"].append({
        "paragraphId": "P2", "kind": "execution_rule", "heading": "进一步说明",
        "format": "sentence", "text": "对象继续移动。", "ruleIds": ["R1"],
    })
    noisy = _evaluate(delivery=delivery)
    assert noisy["paradigmAlignment"]["dimensions"]["chapterOrganization"] <= clean["paradigmAlignment"]["dimensions"]["chapterOrganization"]


def test_internal_system_id_in_human_body_is_an_editorial_delivery_finding():
    delivery = deepcopy(DELIVERY)
    delivery["chapters"][0]["paragraphs"][0]["text"] += " 相关表现见策划草图 VIS-RULE-RP1。"
    delivery["markdown"] = delivery["chapters"][0]["paragraphs"][0]["text"]

    result = _evaluate(delivery=delivery)

    finding = next(item for item in result["attributedFindings"] if item["metric"] == "delivery.internal_system_id_in_human_body")
    assert finding["ownerLayer"] == "Delivery Separation"
    assert finding["observed"] == 1
    assert result["paradigmAlignment"]["dimensions"]["deliveryLayering"] < 10


def test_delivery_layering_checks_only_visual_relations_in_the_evaluated_rule_scope():
    delivery = deepcopy(DELIVERY)
    delivery["traceability"] = {"logicRuleToVisualBlocks": {"R1": ["VIS-1"]}}
    visuals = [
        {"visualBlockId": "VIS-1", "relatedLogicRuleIds": ["R1"]},
        {"visualBlockId": "VIS-OUTSIDE", "relatedLogicRuleIds": ["R-OUTSIDE"]},
    ]

    result = evaluate_target_alignment(delivery, BLOCKS, visuals, RULES, FACTS, GAPS, [], CORPUS)

    assert result["paradigmAlignment"]["dimensions"]["deliveryLayering"] == 10


def test_qualification_requires_two_distinct_generations_and_clean_blind_run():
    closed = [{**GAPS[0], "status": "closed"}]
    duplicate_runs = {
        "completeRuns": [{"score": 84, "generationFingerprint": "same"}, {"score": 86, "generationFingerprint": "same"}],
        "blindRuns": [{"score": 76, "projectKind": "different_game", "projectSpecificContaminationCount": 0}],
    }
    pending = evaluate_target_alignment(DELIVERY, BLOCKS, [], RULES, FACTS, closed, [], CORPUS, duplicate_runs)
    assert pending["qualificationStatus"] == "pending"

    distinct_runs = {
        "completeRuns": [{"score": 84, "generationFingerprint": "run-a"}, {"score": 86, "generationFingerprint": "run-b"}],
        "blindRuns": [{"score": 76, "projectKind": "different_game", "projectSpecificContaminationCount": 0}],
    }
    qualified = evaluate_target_alignment(DELIVERY, BLOCKS, [], RULES, FACTS, closed, [], CORPUS, distinct_runs)
    assert qualified["qualificationStatus"] == "qualified"

    distinct_runs["blindRuns"][0]["projectSpecificContaminationCount"] = 1
    contaminated = evaluate_target_alignment(DELIVERY, BLOCKS, [], RULES, FACTS, closed, [], CORPUS, distinct_runs)
    assert contaminated["qualificationStatus"] == "pending"
