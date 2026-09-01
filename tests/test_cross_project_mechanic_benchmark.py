import json
from pathlib import Path

from backend.mechanic_knowledge_graph import evaluate_migration_benchmark, load_mechanic_graph


GRAPH = Path("data/planner_knowledge/mechanic-knowledge-graph-v1.json")
CASES = Path("tests/fixtures/cross-project-mechanic-cases-v1.json")


def _cases():
    return json.loads(CASES.read_text(encoding="utf-8"))["cases"]


def test_benchmark_has_at_least_25_sparse_cross_project_cases():
    cases = _cases()
    assert len(cases) >= 25
    assert {case["kind"] for case in cases} == {"system", "gameplay", "mixed"}
    assert all(1 < len(case["signals"]) <= 6 for case in cases)


def test_cross_project_pattern_and_responsibility_contracts():
    graph = load_mechanic_graph(GRAPH)
    for case in _cases():
        evidence = [{"evidenceId": f"E-{case['id']}", "signalIds": case["signals"]}]
        detected = graph.detect_mechanics(evidence, context={"genre": "must-not-activate"})
        patterns = {item["mechanicType"] for item in detected}
        assert set(case["expectedPatterns"]) <= patterns, case["id"]
        assert not (set(case.get("forbiddenPatterns", [])) & patterns), case["id"]
        active = graph.activate_responsibilities(detected, evidence=evidence, rules=[], relations=[])
        responsibilities = {item["responsibilityId"] for item in active}
        assert set(case["requiredResponsibilities"]) <= responsibilities, case["id"]
        assert not (set(case.get("dormantResponsibilities", [])) & responsibilities), case["id"]


def test_genre_and_taxonomy_labels_never_activate_patterns():
    graph = load_mechanic_graph(GRAPH)
    assert graph.detect_mechanics([], context={"genre": "MOBA", "taxonomy": ["roguelike"]}) == []


def test_benchmark_reports_recall_precision_gap_noise_and_leakage_metrics():
    report = evaluate_migration_benchmark(load_mechanic_graph(GRAPH), _cases())
    assert report["caseCount"] >= 25
    assert report["patternRecall"] >= 0.95
    assert report["patternPrecision"] >= 0.95
    assert report["responsibilityRecall"] >= 0.90
    assert report["responsibilityPrecision"] >= 0.90
    assert report["highValueGapRate"] >= 0.90
    assert report["noiseRate"] <= 0.05
    assert report["implementationLeakageRate"] == 0.0
    assert report["genreOnlyActivationCount"] == 0
    assert len(report["cases"]) == report["caseCount"]


def test_benchmark_reports_execution_dimension_and_delivery_integrity_coverage():
    report = evaluate_migration_benchmark(load_mechanic_graph(GRAPH), _cases())
    required_dimensions = {
        "planning_hierarchy", "lifecycle", "branch", "algorithm",
        "parameter_contract", "cross_system_relation",
    }
    assert required_dimensions <= {
        dimension for dimension, count in report["executionDimensionCoverage"].items() if count > 0
    }
    assert report["deliveryIntegrity"] == {
        "candidateToP5Count": 0,
        "candidateToP6Count": 0,
        "candidateToPresentationCount": 0,
        "candidateToFinalPublicationCount": 0,
    }
