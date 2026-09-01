import json

from scripts.generate_phase53_mechanic_reconstruction import generate_phase53_artifacts


def test_phase53_builds_six_models_and_preserves_all_content_authorities(tmp_path):
    result = generate_phase53_artifacts(tmp_path)
    models = json.loads((tmp_path / "mechanic-models.json").read_text(encoding="utf-8"))
    provenance = json.loads((tmp_path / "provenance.json").read_text(encoding="utf-8"))

    assert result["mechanicModelCount"] == 6
    assert {model["mechanicType"] for model in models} == {"movement", "attack", "randomization", "level_flow", "settlement"}
    assert all(model["contentAuthority"] == "approved_rule_only" for model in models)
    assert all(node["content"] is None for model in models for node in model["inferredNodes"] + model["unresolvedNodes"])
    assert provenance["sourceFilesUnchanged"] is True
    assert provenance["modifiedRuleCount"] == 0
    assert provenance["modifiedGapCount"] == 0
    assert provenance["modifiedExecutionDocumentCount"] == 0
    assert provenance["parameterResolverInvoked"] is False


def test_phase53_localizes_reviewed_gaps_and_exposes_shallow_observation_only_mechanics(tmp_path):
    result = generate_phase53_artifacts(tmp_path)
    models = json.loads((tmp_path / "mechanic-models.json").read_text(encoding="utf-8"))
    all_gap_ids = {gap_id for model in models for node in model["nodes"] for gap_id in node["supportingGapIds"]}

    assert result["unmappedGapCount"] == 0
    assert "GAP-8ADD419B526A" in all_gap_ids
    assert "GAP-0A1B9EC595AE" in all_gap_ids
    assert set(result["observationOnlyMechanics"]) == {"关卡 / 关卡流程", "结算"}
    assert (tmp_path / "six-mechanic-reconstruction-audit.md").exists()
