import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_blind_transfer_separates_fact_reasoning_from_language_organization():
    cases = json.loads((ROOT / "data/calibration/gve16/transfer-blind-test.json").read_text(encoding="utf-8"))["cases"]

    assert {case["shape"] for case in cases} == {"sparse", "interaction", "algorithm"}
    for case in cases:
        assert case["factPass"]["claims"]
        assert case["factPass"]["excludedInferences"]
        assert case["languagePass"]["output"]
        assert case["languagePass"]["organizationReason"]


def test_blind_transfer_varies_structure_without_copying_sample_content_or_fixed_headings():
    cases = json.loads((ROOT / "data/calibration/gve16/transfer-blind-test.json").read_text(encoding="utf-8"))["cases"]
    outputs = [case["languagePass"]["output"] for case in cases]
    forbidden = ["魔物", "勇者", "词条", "重Roll", "局内资金", "GveMagicBook", "正常怎么玩", "关键规则", "特殊情况", "怎么验证"]

    assert len({case["languagePass"]["carrier"] for case in cases}) == 3
    assert len({case["languagePass"]["sectionCount"] for case in cases}) >= 2
    for output in outputs:
        assert not any(term in output for term in forbidden)
