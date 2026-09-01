from backend.mechanic_scope_inference import apply_mechanic_scope, evaluate_scope_precision, infer_mechanic_scopes
from scripts.generate_phase544_mechanic_scope import generate_phase544


CORPUS = {"templates": {"attack": {"ruleChecks": ["acquisition", "unlock", "loadout_capacity", "replacement", "attack_method", "progression", "modifier_application"]}}}


def _chapter():
    return {"mechanicId": "M-WEAPON", "chapterId": "C-WEAPON", "chapterType": "attack", "object": "武器"}


def _rule(rule_id, slot, behavior, owner="C-WEAPON", rule_type="logic"):
    return {"ruleId": rule_id, "ownerChapterId": owner, "schemaSlot": slot, "behavior": behavior,
            "ruleType": rule_type, "semanticValidity": "valid", "reviewStatus": "approved", "evidenceIds": ["E1"]}


def test_template_only_weapon_submechanics_are_not_instantiated_as_unresolved():
    scopes = infer_mechanic_scopes([_chapter()], [_rule("R1", "attack_method", "武器发射投射物")], [], {}, CORPUS)
    by_item = {item["scopeItem"]: item for item in scopes}
    assert by_item["attack_method"]["existenceStatus"] == "confirmed"
    assert by_item["unlock"]["existenceStatus"] == "unsupported"
    assert by_item["replacement"]["existenceStatus"] == "unsupported"
    assert by_item["acquisition"]["existenceStatus"] in {"possible", "unsupported"}


def test_entity_container_can_strongly_imply_loadout_without_inventing_replacement():
    entity_graph = {"entities": [{"entityId": "E-SLOT", "name": "武器栏", "entityType": "container",
                                  "primaryDefinitionChapter": "C-SLOT"}]}
    scopes = infer_mechanic_scopes([_chapter()], [_rule("R1", "attack_method", "武器发射投射物")], [], entity_graph, CORPUS)
    by_item = {item["scopeItem"]: item for item in scopes}
    assert by_item["loadout_capacity"]["existenceStatus"] == "strongly_implied"
    assert by_item["loadout_capacity"]["relationshipBasis"] == ["E-SLOT"]
    assert by_item["replacement"]["existenceStatus"] == "unsupported"


def test_scope_gate_only_instantiates_confirmed_or_strongly_implied_rules():
    model = {"mechanicId": "M-WEAPON", "missingGameRules": [
        {"semantic": "unlock", "gameRuleType": "unlock_rule"},
        {"semantic": "attack_method", "gameRuleType": "combat_rule"}],
        "parameterNeeds": [], "implementationDetails": []}
    scopes = infer_mechanic_scopes([_chapter()], [_rule("R1", "attack_method", "武器发射投射物")], [], {}, CORPUS)
    gated = apply_mechanic_scope([model], scopes)[0]
    assert [item["semantic"] for item in gated["missingGameRules"]] == ["attack_method"]
    assert "unlock" in [item["scopeItem"] for item in gated["explorationCandidates"]]


def test_player_facing_parameters_remain_gameplay_parameters_not_implementation_details():
    model = {"mechanicId": "M-WEAPON", "missingGameRules": [], "parameterNeeds": [
        {"semantic": "next_attack_trigger", "contract": "Weapon.attackInterval"},
        {"semantic": "attack_entry", "contract": "Weapon.attackRange"},
        {"semantic": "damage_output", "contract": "Weapon.damage"}], "implementationDetails": []}
    scopes = infer_mechanic_scopes([_chapter()], [_rule("R1", "attack_method", "武器发射投射物")], [], {}, CORPUS)
    gated = apply_mechanic_scope([model], scopes)[0]
    assert {item["semantic"] for item in gated["gameplayParameters"]} == {"next_attack_trigger", "attack_entry", "damage_output"}
    assert gated["implementationDetails"] == []


def test_scope_precision_fails_if_unsupported_template_item_is_instantiated():
    scopes = [{"mechanicId": "M", "scopeItem": "unlock", "existenceStatus": "unsupported"}]
    models = [{"mechanicId": "M", "missingGameRules": [{"semantic": "unlock"}]}]
    report = evaluate_scope_precision(scopes, models)
    assert report["unsupportedInstantiatedCount"] == 1
    assert report["qualityGate"] == "fail"


def test_contact_interval_is_conditional_until_sustained_damage_exists():
    model = {"mechanicId": "M-MONSTER", "missingGameRules": [], "parameterNeeds": [],
             "implementationDetails": [{"sourceId": "G1", "semantic": "contact_damage_interval", "reason": "old"}]}
    scopes = [{"mechanicId": "M-MONSTER", "scopeItem": "sustained_contact_damage", "existenceStatus": "possible"}]
    gated = apply_mechanic_scope([model], scopes)[0]
    assert gated["gameplayParameters"] == []
    assert gated["conditionalGameplayParameters"][0]["semantic"] == "contact_damage_interval"
    assert "contact_damage_interval" not in [item["semantic"] for item in gated["implementationDetails"]]


def test_phase544_real_scope_gate_blocks_template_only_weapon_rules(tmp_path):
    summary = generate_phase544(tmp_path)
    assert summary["scopePrecision"]["unsupportedInstantiatedCount"] == 0
    assert summary["scopePrecision"]["templateOnlyInstantiatedCount"] == 0
    assert summary["gameplayParameterCount"] == 6
    assert summary["conditionalGameplayParameterCount"] == 1
    import json
    models = json.loads((tmp_path / "scoped-game-rule-models.json").read_text(encoding="utf-8"))
    weapon = next(model for model in models if model["mechanicType"] == "attack")
    assert "unlock_rule" not in {item["gameRuleType"] for item in weapon["missingGameRules"]}
    assert "replacement" not in {item["semantic"] for item in weapon["missingGameRules"]}
    provenance = json.loads((tmp_path / "provenance.json").read_text(encoding="utf-8"))
    assert provenance["sourceFilesUnchanged"] is True
