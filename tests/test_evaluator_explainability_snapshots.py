from test_target_alignment_evaluator import CORPUS, DELIVERY, FACTS, GAPS, RULES, BLOCKS

from backend.target_alignment_evaluator import evaluate_target_alignment


def test_explainability_snapshot_for_missing_rule_trace():
    delivery = {**DELIVERY, "chapters": [{**DELIVERY["chapters"][0], "paragraphs": []}]}
    result = evaluate_target_alignment(delivery, BLOCKS, [], RULES, FACTS, GAPS, [], CORPUS)
    assert result["paradigmAlignment"] == {
        "total": 78.0,
        "dimensions": {
            "chapterOrganization": 20,
            "bodyGranularity": 12.0,
            "planningLanguage": 20,
            "informationDensity": 7.0,
            "mechanismBlockOrganization": 9.0,
            "deliveryLayering": 10,
        },
    }
    finding = next(item for item in result["attributedFindings"] if item["metric"] == "hard_gate.rule_to_final_output_traceability")
    assert {key: finding[key] for key in ("ownerLayer", "impact", "minimalFix")} == {
        "ownerLayer": "Renderer",
        "impact": -8.0,
        "minimalFix": "Restore every eligible Rule to a final paragraph with its Rule ID provenance.",
    }


def test_explainability_snapshot_for_clean_organized_delivery():
    result = evaluate_target_alignment(DELIVERY, BLOCKS, [], RULES, FACTS, [{**GAPS[0], "status": "closed"}], [], CORPUS)
    assert result["paradigmAlignment"]["total"] == 98.1
    assert result["executionCompleteness"]["total"] == 100
    assert result["qualificationStatus"] == "pending"


def test_explainability_snapshot_for_open_gap_and_missing_parameter_contract():
    numeric_rule = {"ruleId": "R3", "ownerChapterId": "C1", "ruleType": "numeric", "reviewStatus": "approved", "semanticValidity": "valid", "schemaSlot": "movement_speed_source", "behavior": "移动速度读取配置", "sourceFactIds": []}
    result = evaluate_target_alignment(DELIVERY, BLOCKS, [], RULES + [numeric_rule], FACTS, GAPS, [], CORPUS)
    parameter = next(item for item in result["attributedFindings"] if item["ownerLayer"] == "Parameter")
    gap = next(item for item in result["attributedFindings"] if item["ownerLayer"] == "Gap")
    assert parameter["minimalFix"] == "Define ParameterContracts only for the existing numeric/config Rules; do not infer values."
    assert gap["minimalFix"] == "Resolve or explicitly retain the reviewed open Gaps; do not render them as confirmed Rules."
