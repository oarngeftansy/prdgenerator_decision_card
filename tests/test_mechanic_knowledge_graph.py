import json
from pathlib import Path

import pytest

from backend.mechanic_knowledge_graph import (
    MechanicKnowledgeGraph,
    load_mechanic_graph,
    validate_mechanic_graph,
)


def _graph():
    return {
        "schemaVersion": "1.0",
        "contentAuthority": "none",
        "nodes": [
            {"id": "domain.combat", "kind": "domain", "level": "L1", "name": "combat"},
            {"id": "family.attack", "kind": "family", "level": "L2", "name": "attack"},
            {
                "id": "pattern.projectile_attack",
                "kind": "pattern",
                "level": "L3",
                "name": "projectile_attack",
                "detection": {"allSignals": ["signal.projectile_spawn", "signal.projectile_hit"]},
            },
            {"id": "signal.projectile_spawn", "kind": "signal", "sourceModes": ["video", "entity_change"]},
            {"id": "signal.projectile_hit", "kind": "signal", "sourceModes": ["video", "state_change"]},
            {"id": "signal.penetration", "kind": "signal", "sourceModes": ["video"]},
            {
                "id": "responsibility.attack_trigger",
                "kind": "responsibility",
                "level": "L4",
                "question": "What triggers the attack?",
                "activation": {"alwaysForDetectedPattern": True},
            },
            {
                "id": "responsibility.penetration",
                "kind": "responsibility",
                "level": "L4",
                "question": "How does penetration terminate?",
                "activation": {"anySignals": ["signal.penetration"]},
            },
            {"id": "concept.projectile", "kind": "concept", "conceptType": "Entity"},
        ],
        "edges": [
            {"from": "domain.combat", "to": "family.attack", "type": "contains"},
            {"from": "family.attack", "to": "pattern.projectile_attack", "type": "contains"},
            {"from": "pattern.projectile_attack", "to": "responsibility.attack_trigger", "type": "may_activate"},
            {"from": "pattern.projectile_attack", "to": "responsibility.penetration", "type": "may_activate"},
            {"from": "pattern.projectile_attack", "to": "concept.projectile", "type": "shares_concept"},
        ],
    }


def test_loader_indexes_declarative_graph(tmp_path):
    path = tmp_path / "graph.json"
    path.write_text(json.dumps(_graph()), encoding="utf-8")
    graph = load_mechanic_graph(path)
    assert graph.pattern("projectile_attack")["id"] == "pattern.projectile_attack"
    assert [item["id"] for item in graph.responsibilities_for("pattern.projectile_attack")] == [
        "responsibility.attack_trigger",
        "responsibility.penetration",
    ]


def test_validator_rejects_dangling_edges_and_project_answers():
    dangling = _graph()
    dangling["edges"].append({"from": "pattern.missing", "to": "concept.projectile", "type": "shares_concept"})
    with pytest.raises(ValueError, match="dangling edge"):
        validate_mechanic_graph(dangling)

    answer = _graph()
    answer["nodes"][2]["projectAnswer"] = "boss dies after 8 seconds"
    with pytest.raises(ValueError, match="project answer"):
        validate_mechanic_graph(answer)


def test_validator_rejects_dangling_contract_references_and_orphan_levels():
    dangling_signal = _graph()
    dangling_signal["nodes"][2]["detection"] = {"allSignals": ["signal.not_declared"]}
    with pytest.raises(ValueError, match="undeclared signal"):
        validate_mechanic_graph(dangling_signal)

    orphan_pattern = _graph()
    orphan_pattern["edges"] = [
        edge for edge in orphan_pattern["edges"]
        if not (edge["type"] == "contains" and edge["to"] == "pattern.projectile_attack")
    ]
    with pytest.raises(ValueError, match="orphan pattern"):
        validate_mechanic_graph(orphan_pattern)

    orphan_responsibility = _graph()
    orphan_responsibility["edges"] = [
        edge for edge in orphan_responsibility["edges"]
        if edge.get("to") != "responsibility.attack_trigger"
    ]
    with pytest.raises(ValueError, match="orphan responsibility"):
        validate_mechanic_graph(orphan_responsibility)

    orphan_composition = _graph()
    orphan_composition["edges"] = [
        edge for edge in orphan_composition["edges"]
        if not (edge["type"] == "shares_concept" and edge["from"] == "pattern.projectile_attack")
    ]
    with pytest.raises(ValueError, match="pattern without shared concept"):
        validate_mechanic_graph(orphan_composition)


def test_real_graph_has_complete_declarative_hierarchy_and_contract_references():
    graph = json.loads(Path("data/planner_knowledge/mechanic-knowledge-graph-v1.json").read_text(encoding="utf-8"))
    validate_mechanic_graph(graph)


def test_detection_and_responsibility_activation_are_evidence_driven():
    graph = MechanicKnowledgeGraph(_graph())
    evidence = [
        {"evidenceId": "E1", "signalIds": ["signal.projectile_spawn"]},
        {"evidenceId": "E2", "signalIds": ["signal.projectile_hit"]},
    ]
    detected = graph.detect_mechanics(evidence, context={"genre": "roguelike"})
    assert [item["mechanicType"] for item in detected] == ["projectile_attack"]
    assert detected[0]["evidenceIds"] == ["E1", "E2"]
    active = graph.activate_responsibilities(detected, evidence=evidence, rules=[], relations=[])
    assert [item["responsibilityId"] for item in active] == ["responsibility.attack_trigger"]

    genre_only = graph.detect_mechanics([], context={"genre": "FPS"})
    assert genre_only == []


def test_optional_responsibility_activates_only_after_its_signal():
    graph = MechanicKnowledgeGraph(_graph())
    evidence = [{"evidenceId": "E1", "signalIds": [
        "signal.projectile_spawn", "signal.projectile_hit", "signal.penetration"
    ]}]
    detected = graph.detect_mechanics(evidence)
    active = graph.activate_responsibilities(detected, evidence=evidence, rules=[], relations=[])
    assert {item["responsibilityId"] for item in active} == {
        "responsibility.attack_trigger", "responsibility.penetration"
    }


def test_real_graph_detects_six_composed_combat_patterns():
    graph = load_mechanic_graph(Path("data/planner_knowledge/mechanic-knowledge-graph-v1.json"))
    evidence = [{"evidenceId": "VIDEO-1", "entityIds": ["player", "boss"], "signalIds": [
        "signal.rapid_displacement", "signal.dash_input",
        "signal.target_marker", "signal.camera_tracks_target",
        "signal.repeated_melee_input", "signal.combo_sequence_changes",
        "signal.timed_defense_input", "signal.enemy_attack_deflected",
        "signal.boss_entity", "signal.boss_health_state",
        "signal.boss_state_transition", "signal.boss_behavior_changes",
    ]}]
    detected = graph.detect_mechanics(evidence)
    assert {item["mechanicType"] for item in detected} == {
        "dash", "lock_on", "melee_combo", "parry", "boss_encounter", "boss_phase"
    }


def test_composition_links_patterns_through_shared_project_nodes():
    graph = load_mechanic_graph(Path("data/planner_knowledge/mechanic-knowledge-graph-v1.json"))
    evidence = [{"evidenceId": "E1", "entityIds": ["boss-01"], "signalIds": [
        "signal.boss_entity", "signal.boss_health_state",
        "signal.boss_state_transition", "signal.boss_behavior_changes",
    ]}]
    detected = graph.detect_mechanics(evidence)
    project = graph.compose_project_graph(
        detected,
        project_nodes=[{"id": "boss-01", "kind": "Entity"}],
        relations=[{"from": "boss-01", "to": "pattern.boss_phase", "type": "participates_in"}],
    )
    assert {node["id"] for node in project["nodes"]} >= {
        "pattern.boss_encounter", "pattern.boss_phase", "boss-01"
    }
    assert any(edge["type"] == "shared_concept" and edge["conceptId"] == "concept.boss"
               for edge in project["edges"])


def test_missing_requirements_include_only_active_unsatisfied_responsibilities():
    graph = MechanicKnowledgeGraph(_graph())
    evidence = [{"evidenceId": "E1", "signalIds": [
        "signal.projectile_spawn", "signal.projectile_hit", "signal.penetration"
    ]}]
    detected = graph.detect_mechanics(evidence)
    active = graph.activate_responsibilities(detected, evidence=evidence, rules=[], relations=[])
    missing = graph.discover_missing_requirements(active, rules=[{
        "ruleId": "R1", "reviewStatus": "approved",
        "satisfiesResponsibilityIds": ["responsibility.attack_trigger"],
    }])
    assert [item["responsibilityId"] for item in missing] == ["responsibility.penetration"]
    assert missing[0]["sourceEvidenceIds"] == ["E1"]


def test_responsibility_activation_interprets_approved_rule_and_relation_contracts_generically():
    payload = _graph()
    payload["nodes"].append({
        "id": "responsibility.resource_transfer",
        "kind": "responsibility",
        "level": "L4",
        "question": "How does the resource cross the system boundary?",
        "activation": {
            "anyApprovedRuleTags": ["resource_cost"],
            "anyRelationTypes": ["consumes"],
        },
    })
    payload["edges"].append({
        "from": "pattern.projectile_attack",
        "to": "responsibility.resource_transfer",
        "type": "may_activate",
    })
    graph = MechanicKnowledgeGraph(payload)
    evidence = [{"evidenceId": "E1", "signalIds": [
        "signal.projectile_spawn", "signal.projectile_hit"
    ]}]
    detected = graph.detect_mechanics(evidence)
    approved_rules = [{
        "ruleId": "R1", "reviewStatus": "approved", "tags": ["resource_cost"]
    }]
    relations = [{"from": "weapon", "to": "ammo", "type": "consumes"}]

    without_relation = graph.activate_responsibilities(
        detected, evidence=evidence, rules=approved_rules, relations=[]
    )
    without_rule = graph.activate_responsibilities(
        detected, evidence=evidence, rules=[], relations=relations
    )
    active = graph.activate_responsibilities(
        detected, evidence=evidence, rules=approved_rules, relations=relations
    )

    assert "responsibility.resource_transfer" not in {
        item["responsibilityId"] for item in without_relation + without_rule
    }
    assert "responsibility.resource_transfer" in {
        item["responsibilityId"] for item in active
    }
    transfer = next(item for item in active if item["responsibilityId"] == "responsibility.resource_transfer")
    assert transfer["activationRuleIds"] == ["R1"]
    assert transfer["activationRelationTypes"] == ["consumes"]


def test_unapproved_rule_never_activates_rule_driven_responsibility():
    payload = _graph()
    payload["nodes"].append({
        "id": "responsibility.rule_gated",
        "kind": "responsibility",
        "level": "L4",
        "question": "Which approved rule makes this responsibility applicable?",
        "activation": {"anyApprovedRuleTags": ["conditional_branch"]},
    })
    payload["edges"].append({
        "from": "pattern.projectile_attack",
        "to": "responsibility.rule_gated",
        "type": "may_activate",
    })
    graph = MechanicKnowledgeGraph(payload)
    evidence = [{"evidenceId": "E1", "signalIds": [
        "signal.projectile_spawn", "signal.projectile_hit"
    ]}]
    detected = graph.detect_mechanics(evidence)
    active = graph.activate_responsibilities(
        detected,
        evidence=evidence,
        rules=[{"ruleId": "R-DRAFT", "reviewStatus": "unreviewed", "tags": ["conditional_branch"]}],
        relations=[],
    )
    assert "responsibility.rule_gated" not in {item["responsibilityId"] for item in active}
