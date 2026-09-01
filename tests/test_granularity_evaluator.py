from pathlib import Path

from backend.granularity_evaluator import evaluate_granularity
from backend.gve16_alignment_corpus import load_gve16_alignment_corpus


ROOT = Path(__file__).resolve().parents[1]
CORPUS = load_gve16_alignment_corpus(ROOT / "data/quality/gve16-alignment-corpus-v1.json")


def _entry(rule_id, slot, rule_type="logic"):
    return {"ruleId": rule_id, "schemaSlot": slot, "ruleType": rule_type, "text": rule_id}


BLOCKS = [
    {"blockId": "B1", "chapterId": "C1", "owner": "对象A", "mechanismSemantic": "移动方式", "status": "partial_mechanism_chain", "ruleIds": ["R1", "R2"], "processing": [_entry("R1", "movement_trigger")], "input_constraint": [_entry("R2", "movement_control")], "presentation": []},
    {"blockId": "B2", "chapterId": "C1", "owner": "对象A", "mechanismSemantic": "受击处理", "status": "partial_mechanism_chain", "ruleIds": ["R3"], "effect": [_entry("R3", "damage_death_definition", "numeric")], "presentation": []},
]


def _delivery(paragraphs):
    return {"chapters": [{"chapterId": "C1", "title": "对象A", "paragraphs": paragraphs}], "metrics": {}}


CLEAN = _delivery([
    {"paragraphId": "P1", "kind": "execution_rule", "heading": "移动方式", "format": "sentence", "text": "对象A按既定路径移动，玩家可调整横向位置。", "ruleIds": ["R1", "R2"]},
    {"paragraphId": "P2", "kind": "execution_rule", "heading": "受击处理", "format": "bullets", "text": "- 对象A受击后更新当前生命值。", "ruleIds": ["R3"]},
])


def test_reports_carriers_and_rule_granularity_from_structured_provenance():
    report = evaluate_granularity(CLEAN, BLOCKS, CORPUS)
    metrics = report["metrics"]
    assert metrics["oneRuleOneSentenceRatio"] == 0.0
    assert metrics["averageRulesPerParagraph"] == 1.5
    assert metrics["carrierDistribution"] == {"prose": 1, "bullet": 1, "numbered": 0, "table": 0}
    assert metrics["crossSemanticDomainParagraphCount"] == 0
    assert metrics["lostEligibleRuleCount"] == 0


def test_forced_cross_domain_merge_cannot_raise_score():
    forced = _delivery([{
        "paragraphId": "P1", "kind": "execution_rule", "heading": "移动方式", "format": "sentence",
        "text": "对象A移动后扣除生命值。", "ruleIds": ["R1", "R3"],
    }, {
        "paragraphId": "P2", "kind": "execution_rule", "heading": "移动方式", "format": "sentence",
        "text": "玩家调整横向位置。", "ruleIds": ["R2"],
    }])
    clean = evaluate_granularity(CLEAN, BLOCKS, CORPUS)
    report = evaluate_granularity(forced, BLOCKS, CORPUS)
    assert report["score"] <= clean["score"]
    assert report["metrics"]["crossSemanticDomainParagraphCount"] == 1
    finding = report["findings"][0]
    assert finding["metric"] == "granularity.cross_semantic_domain_paragraph_count"
    assert finding["ownerLayer"] == "Granularity / Editorial"
    assert finding["minimalFix"] == "Split the paragraph at the semantic-domain boundary; keep only Rules with the same owner and mechanism semantic together."


def test_deleting_required_rule_cannot_raise_score():
    deleted = _delivery([CLEAN["chapters"][0]["paragraphs"][0]])
    assert evaluate_granularity(deleted, BLOCKS, CORPUS)["score"] <= evaluate_granularity(CLEAN, BLOCKS, CORPUS)["score"]
    assert evaluate_granularity(deleted, BLOCKS, CORPUS)["metrics"]["lostEligibleRuleCount"] == 1


def test_meaningless_extra_heading_cannot_raise_score():
    noisy = _delivery(CLEAN["chapters"][0]["paragraphs"] + [{
        "paragraphId": "P3", "kind": "execution_rule", "heading": "进一步说明", "format": "sentence",
        "text": "继续执行。", "ruleIds": ["R1"],
    }])
    report = evaluate_granularity(noisy, BLOCKS, CORPUS)
    assert report["score"] <= evaluate_granularity(CLEAN, BLOCKS, CORPUS)["score"]
    assert report["metrics"]["unsupportedHeadingCount"] == 1


def test_snapshot_clean_metrics_and_score_are_stable():
    report = evaluate_granularity(CLEAN, BLOCKS, CORPUS)
    assert report["scoreComponents"] == {
        "semanticDomainIsolation": 8.0,
        "mechanismCohesion": 8.0,
        "provisionalDistributionFit": 2.43,
    }
    assert report["score"] == 18.43
