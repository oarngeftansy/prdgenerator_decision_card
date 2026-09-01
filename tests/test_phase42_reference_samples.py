from pathlib import Path

from scripts.generate_phase42_mechanism_samples import generate


def test_reference_samples_cover_six_chapters_and_preserve_semantic_provenance(tmp_path: Path):
    result = generate(tmp_path)
    assert list(result["chapters"]) == ["载具移动", "武器攻击", "三选一", "怪物攻击", "关卡流程", "结算"]
    assert result["metrics"]["ruleToMechanismBlockToFinalParagraphTraceabilityRate"] == 1.0
    assert result["metrics"]["unsupportedSemanticAdditionCount"] == 0
    assert result["chapters"]["关卡流程"]["classification"] == "evidence_insufficient"
    assert result["chapters"]["载具移动"]["classification"] == "partial_mechanism_chain"
    assert (tmp_path / "mechanism-samples.md").exists()
    assert (tmp_path / "mechanism-samples.json").exists()
