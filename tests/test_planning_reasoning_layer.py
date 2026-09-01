from copy import deepcopy
from pathlib import Path

from backend.planning_reasoning_corpus import load_planning_reasoning_corpus
from backend.planning_reasoning_layer import build_planning_mechanism_models
from backend.planning_reasoning_depth_evaluator import evaluate_planning_reasoning_depth


ROOT = Path(__file__).resolve().parents[1]
CORPUS = load_planning_reasoning_corpus(ROOT / "data/quality/gve16-planning-reasoning-corpus-v1.json")


def test_reasoning_corpus_has_ten_content_free_chapter_type_templates():
    assert set(CORPUS["templates"]) == {
        "movement", "attack", "damage_death", "randomization", "unlock_progression",
        "slot", "spawn", "level_flow", "settlement", "statistics",
    }
    assert CORPUS["contentAuthority"] == "none"
    assert CORPUS["provisional"] is True
    assert all(template["sourceEvidence"] for template in CORPUS["templates"].values())


def test_planning_model_has_four_strict_statuses_and_fact_evidence_traceability():
    chapters = [{"chapterId": "C1", "object": "武器", "title": "攻击", "chapterType": "attack", "mechanicVariant": "ranged"}]
    rules = [
        {"ruleId": "R1", "ownerChapterId": "C1", "ruleType": "logic", "schemaSlot": "attack_target", "subject": "武器", "behavior": "武器选择射程内敌人作为攻击目标", "reviewStatus": "approved", "semanticValidity": "valid", "sourceFactIds": ["F1"], "evidenceIds": ["E1"]},
    ]
    facts = [{"factId": "F1", "evidenceIds": ["E1"], "evidenceLevel": "observed"}]
    gaps = [{"gapId": "G1", "chapterId": "C1", "schemaSlot": "attack_exit_condition", "question": "何时退出攻击？", "status": "open"}]
    inputs = (chapters, rules, gaps, facts, {"entities": []})
    before = deepcopy(inputs)

    model = build_planning_mechanism_models(*inputs, CORPUS)[0]
    nodes = {node["mechanismNode"]: node for node in model["nodes"]}

    assert inputs == before
    assert nodes["target_selection"]["reasoningStatus"] == "confirmed"
    assert nodes["target_selection"]["supportingFactIds"] == ["F1"]
    assert nodes["target_selection"]["supportingEvidenceIds"] == ["E1"]
    assert nodes["exit_condition"]["reasoningStatus"] == "unresolved"
    assert nodes["exit_condition"]["gapLocations"] == [{"gapId": "G1", "mechanicId": model["mechanicId"], "mechanismNode": "exit_condition"}]
    assert nodes["target_set_build"]["reasoningStatus"] == "derived_structure"
    assert nodes["retarget_policy"]["reasoningStatus"] == "hypothesis"
    assert nodes["target_set_build"]["content"] is None
    assert nodes["retarget_policy"]["content"] is None
    assert model["supportingFactIds"] == ["F1"]
    assert set(model["lifecycle"]) == {"initialize", "persist", "reset"}


def test_reasoning_depth_counts_unknown_structure_but_not_as_execution_completeness():
    model = {
        "mechanicId": "M1", "actors": ["A"], "objects": ["O"], "states": ["N-state"],
        "entryConditions": ["N-entry"], "triggers": ["N-trigger"], "preconditions": ["N-pre"],
        "processingStages": ["N-process"], "stateTransitions": ["N-transition"], "outputs": ["N-output"],
        "exitConditions": ["N-exit"], "exceptions": ["N-exception"], "boundaries": ["N-boundary"],
        "parameters": ["N-parameter"], "configSources": ["N-config"],
        "upstreamMechanics": ["N-up"], "downstreamMechanics": ["N-down"],
        "lifecycle": {"initialize": ["N-init"], "persist": ["N-persist"], "reset": ["N-reset"]},
        "nodes": [
            {"mechanismNode": "state", "reasoningStatus": "derived_structure", "gapLocations": []},
            {"mechanismNode": "exit", "reasoningStatus": "unresolved", "gapLocations": [{"gapId": "G1", "mechanicId": "M1", "mechanismNode": "exit"}]},
        ],
        "unmappedGapIds": [],
    }
    report = evaluate_planning_reasoning_depth([model])
    assert report["total"] == 100
    assert report["dimensions"] == {
        "mechanicAbstraction": 15, "stateModel": 15, "conditionAndTransition": 15,
        "processingChain": 15, "boundaryAndException": 10, "crossSystemDependency": 10,
        "lifecycle": 10, "parameterConfigAwareness": 5, "gapLocalization": 5,
    }
    assert report["executionCompletenessContribution"] == 0
