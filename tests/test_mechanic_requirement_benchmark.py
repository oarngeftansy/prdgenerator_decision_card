from __future__ import annotations

import json
from pathlib import Path

from backend.mechanic_requirement_discovery import discover_requirements


FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_independent_gold_set_activation_metrics_clear_first_round_thresholds():
    mechanics = _load("benchmark_mechanic_conditions_v1.json")
    gold = _load("benchmark_expected_dimensions_gold_v1.json")
    requirements = discover_requirements(mechanics)

    expected_core = {(mid, dim) for mid, values in gold.items() for dim in values["core"]}
    expected_active = expected_core | {
        (mid, dim) for mid, values in gold.items() for dim in values["activeConditional"]
    }
    actual_active = {
        (item["mechanicId"], item["executionDimensionId"])
        for item in requirements
        if item["status"] not in {"dormant_optional", "not_applicable"}
    }
    actual_core = {
        pair for pair in actual_active
        if next(item for item in requirements
                if (item["mechanicId"], item["executionDimensionId"]) == pair)["dimensionRole"] == "core"
    }
    core_recall = len(actual_core & expected_core) / len(expected_core)
    overall_recall = len(actual_active & expected_active) / len(expected_active)
    unsupported_rate = len(actual_active - expected_active) / len(actual_active)

    assert core_recall >= 0.90
    assert overall_recall >= 0.80
    assert unsupported_rate <= 0.05
    assert core_recall == 1.0
    assert overall_recall == 1.0
    assert unsupported_rate == 0.0


def test_gold_set_has_dimensions_only_and_contains_no_rule_answers():
    gold = _load("benchmark_expected_dimensions_gold_v1.json")
    assert set(next(iter(gold.values()))) == {"core", "activeConditional"}
    serialized = json.dumps(gold, ensure_ascii=False)
    assert "ruleText" not in serialized
    assert "answer" not in serialized


def test_routing_accuracy_uses_independent_routing_gold():
    mechanics = _load("benchmark_mechanic_conditions_v1.json")
    routing_gold = _load("benchmark_expected_routing_gold_v1.json")
    requirements = discover_requirements(mechanics)
    expected_p4 = set(routing_gold["P4"])
    expected_p6 = set(routing_gold["P6"])
    correct = 0
    active = [item for item in requirements if item["status"] != "dormant_optional"]
    for item in active:
        key = f"{item['mechanicId']}:{item['executionDimensionId']}"
        expected = "P4" if key in expected_p4 else "P6" if key in expected_p6 else "PROBE"
        actual = item.get("routingTarget", "PROBE")
        correct += actual == expected
    assert correct / len(active) >= 0.90
    assert correct == len(active)
