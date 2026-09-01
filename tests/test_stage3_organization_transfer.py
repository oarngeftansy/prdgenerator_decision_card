import json
from pathlib import Path

from backend.feishu_language_quality import language_quality_report


ROOT = Path(__file__).resolve().parents[1]
CHAPTER_CASES = json.loads((ROOT / "data/calibration/gve16/chapter-organization-cases.json").read_text(encoding="utf-8"))["cases"]
TRANSFER = json.loads((ROOT / "data/calibration/gve16/transfer-blind-test.json").read_text(encoding="utf-8"))["cases"]
GRAMMAR = json.loads((ROOT / "data/calibration/gve16/document-grammar.json").read_text(encoding="utf-8"))


def test_tc9_three_sample_chapters_explain_parts_order_carrier_and_omission():
    assert [item["id"] for item in CHAPTER_CASES] == ["S3-TC09-A", "S3-TC09-B", "S3-TC09-C"]
    assert len({item["chapter"] for item in CHAPTER_CASES}) == 3
    for item in CHAPTER_CASES:
        assert len(item["parts"]) >= 4
        assert item["orderReason"] and item["omitted"]
        assert all(part["question"] and part["source"] and part["carrier"] and part["reason"] for part in item["parts"])


def test_tc20_repeated_business_paragraph_across_chapters_is_rejected():
    repeated = "玩家确认进入挑战时扣除挑战券，挑战失败时返还本次消耗。"
    model = {"chapters": [
        {"id":"C20-A","scope":"挑战入口","plannerSections":{"summary":repeated}},
        {"id":"C20-B","scope":"挑战结算","plannerSections":{"summary":repeated}},
    ]}

    report = language_quality_report(model)

    assert not report["passed"]
    finding = next(item for item in report["findings"] if item["code"] == "LANGUAGE_CROSS_CHAPTER_DUPLICATION")
    assert "挑战入口" in finding["message"] and "挑战结算" in finding["message"]


def test_tc21_to_tc24_grammar_encodes_dynamic_structure_sentence_order_and_subjects():
    assert GRAMMAR["headingRules"]["mergeSparseSiblings"] is True
    assert GRAMMAR["headingRules"]["numberOnlyOrderedAlgorithms"] is True
    assert GRAMMAR["chapterGrammar"]["fixedTemplateForbidden"] is True
    assert GRAMMAR["sentenceGrammar"]["defaultOrder"] == ["condition", "actor_action", "system_result", "scope_or_boundary"]
    assert set(GRAMMAR["subjectRules"]) == {"player", "system", "runtime_owner", "game_object"}


def test_tc25_and_tc26_are_enforced_by_real_language_audit():
    model = {"chapters": [{
        "id":"C25","scope":"奖励规则",
        "plannerSections":{"summary":"本节主要介绍奖励机制，并通过状态隔离形成闭环。"},
        "tables":[{"rows":[["失败处理","挑战失败返还挑战券"]]}],
        "bodyText":"挑战失败返还挑战券。",
    }]}

    codes = {item["code"] for item in language_quality_report(model)["findings"]}
    assert {"LANGUAGE_FILLER", "LANGUAGE_ABSTRACT_TERM", "LANGUAGE_CARRIER_DUPLICATION"} <= codes


def test_tc27_three_blind_outputs_use_distinct_facts_carriers_structures_and_copy():
    assert [item["shape"] for item in TRANSFER] == ["sparse", "interaction", "algorithm"]
    assert len({item["languagePass"]["carrier"] for item in TRANSFER}) == 3
    assert len({item["languagePass"]["sectionCount"] for item in TRANSFER}) == 3
    assert len({item["languagePass"]["output"] for item in TRANSFER}) == 3
    for item in TRANSFER:
        assert item["factPass"]["claims"]
        assert item["factPass"]["excludedInferences"]
        assert item["languagePass"]["organizationReason"]
