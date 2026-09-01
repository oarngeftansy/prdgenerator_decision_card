from copy import deepcopy

from backend.entity_builder import build_entity_graph


def _inputs():
    chapters = [
        {"chapterId": "C1", "object": "武器", "title": "攻击", "chapterType": "attack"},
        {"chapterId": "C2", "object": "怪物", "title": "战斗表现", "chapterType": "presentation"},
        {"chapterId": "C3", "object": "关卡", "title": "红色遮罩", "chapterType": "presentation"},
    ]
    rules = [
        {"ruleId": "R1", "ownerChapterId": "C1", "reviewStatus": "approved", "semanticValidity": "valid",
         "ruleType": "logic", "subject": "武器", "behavior": "武器选择怪物作为攻击目标"},
        {"ruleId": "R2", "ownerChapterId": "C2", "reviewStatus": "approved", "semanticValidity": "valid",
         "ruleType": "presentation", "subject": "怪物", "behavior": "怪物受击时显示红色伤害跳字"},
    ]
    gaps = [{"gapId": "G1", "chapterId": "C1", "schemaSlot": "attack_exit", "status": "open"}]
    declarations = [
        {"entityId": "ENT-WEAPON", "name": "武器", "entityType": "runtime_object", "semanticKey": "weapon", "aliases": ["武器"], "primaryChapterId": "C1"},
        {"entityId": "ENT-MONSTER", "name": "怪物", "entityType": "runtime_object", "semanticKey": "monster", "aliases": ["怪物"]},
    ]
    return chapters, rules, gaps, declarations


def test_builds_declared_entities_and_evidence_backed_source_target():
    graph = build_entity_graph(*_inputs())
    assert {e["entityId"] for e in graph["entities"]} == {"ENT-WEAPON", "ENT-MONSTER"}
    assert graph["entityTypeDistribution"] == {"runtime_object": 2}
    edge = next(e for e in graph["relationships"] if e["relationType"] == "source_target")
    assert (edge["sourceEntityId"], edge["targetEntityId"], edge["evidenceRuleIds"]) == ("ENT-WEAPON", "ENT-MONSTER", ["R1"])


def test_directory_heading_and_presentation_concept_do_not_create_entities():
    graph = build_entity_graph(*_inputs())
    assert "红色遮罩" not in {e["name"] for e in graph["entities"]}
    assert "ENT-RED-OVERLAY" not in {e["entityId"] for e in graph["entities"]}
    assert graph["pollutionAudit"]["presentationCreatedEntityCount"] == 0


def test_presentation_rules_only_reference_existing_entities():
    graph = build_entity_graph(*_inputs())
    ref = graph["presentationRuleReferences"][0]
    assert ref == {"ruleId": "R2", "relatedEntityIds": ["ENT-MONSTER"]}
    assert all("R2" not in edge["evidenceRuleIds"] for edge in graph["relationships"])
    assert graph["pollutionAudit"]["presentationBackflowCount"] == 0


def test_owner_parent_and_definition_references_are_explicit_not_inherited_from_scope():
    chapters, rules, gaps, declarations = _inputs()
    declarations.append({"entityId": "ENT-SLOT", "name": "武器栏", "entityType": "container", "semanticKey": "weapon_slot", "aliases": ["武器栏"], "ownerEntityId": "ENT-WEAPON", "parentEntityId": "ENT-WEAPON", "primaryChapterId": "C1", "relationReason": "approved domain declaration"})
    graph = build_entity_graph(chapters, rules, gaps, declarations)
    slot = next(e for e in graph["entities"] if e["entityId"] == "ENT-SLOT")
    assert slot["ownerEntityId"] == "ENT-WEAPON"
    assert slot["parentEntityId"] == "ENT-WEAPON"
    assert slot["primaryDefinitionChapter"] == "C1"
    assert next(e for e in graph["entities"] if e["entityId"] == "ENT-WEAPON")["childEntityIds"] == ["ENT-SLOT"]


def test_inputs_are_not_mutated():
    inputs = _inputs()
    before = deepcopy(inputs)
    build_entity_graph(*inputs)
    assert inputs == before


def test_rejects_unknown_entity_type():
    chapters, rules, gaps, declarations = _inputs()
    declarations[0]["entityType"] = "ui_element"
    try:
        build_entity_graph(chapters, rules, gaps, declarations)
    except ValueError as exc:
        assert "ui_element" in str(exc)
    else:
        raise AssertionError("unknown EntityType must be rejected")
