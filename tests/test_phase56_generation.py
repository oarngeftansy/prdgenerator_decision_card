import json

from scripts.generate_phase56_gameplay_rule_chains import generate_phase56


def test_phase56_supported_chains_are_coherent_traceable_and_read_only(tmp_path):
    summary = generate_phase56(tmp_path)
    assert summary["coherenceGate"] == "pass"
    assert summary["knownRulePlacementRate"] == 1.0
    assert summary["sourceFilesUnchanged"] is True
    assert summary["modifiedApprovedRuleCount"] == summary["modifiedApprovedGapCount"] == 0
    assert summary["finalDocumentGenerated"] is False
    assert summary["parameterResolverInvoked"] is False
    chains = json.loads((tmp_path / "gameplay-rule-chains.json").read_text(encoding="utf-8"))
    assert {chain["chainType"] for chain in chains} == {
        "three_choice_core", "weapon_acquire_attack_upgrade", "level_combat_growth_settlement",
        "monster_movement_contact",
    }
    assert all(chain["supportingRuleIds"] for chain in chains)
