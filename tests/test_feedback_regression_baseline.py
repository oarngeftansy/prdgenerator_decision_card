import ast
import json
from pathlib import Path

from scripts.generate_yilu_final_mechanic_reconstruction import _feedback_trace_records


ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "data" / "planner_knowledge" / "yilu-feedback-regression-baseline-v1.json"


def _test_functions(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}


def test_twelve_planner_feedback_items_are_fixed_to_executable_regression_contracts():
    payload = json.loads(BASELINE.read_text(encoding="utf-8"))
    records = payload["records"]

    assert len(records) == 12
    assert len({item["feedbackId"] for item in records}) == 12
    assert sum(item["expectedStatus"] == "fully_reflected" for item in records) == 12
    partial = [item for item in records if item["expectedStatus"] == "partially_reflected"]
    assert partial == []
    assert not any(item["expectedStatus"] in {"registered_only", "regressed", "not_reflected"} for item in records)

    for record in records:
        assert record["testIds"], record["feedbackId"]
        for nodeid in record["testIds"]:
            relative, function_name = nodeid.split("::", 1)
            path = ROOT / relative
            assert path.is_file(), nodeid
            assert function_name in _test_functions(path), nodeid


def test_internal_default_lifecycle_semantics_complete_feedback_even_when_project_evidence_is_missing():
    projection = {"rules": [], "gaps": [{
            "gapId": "G-CLEAR",
            "finalRequirementClass": "implicit_system_semantics",
            "finalPublicationRequired": False,
        }]}
    audit = {
        "unsupportedFormula": 0, "unsupportedProbability": 0, "unsupportedWeight": 0,
        "approvedInformationRecoveredRules": 0, "undefinedReferencedEntities": 0,
        "unresolvedMechanicReferences": 0, "orphanRules": 0,
        "trivialDerivedClausesSuppressed": 0, "runSpecificValuesSuppressed": 0,
        "temporalMechanismsRecovered": 0, "rateChangeCandidates": 0,
    }
    records = _feedback_trace_records(
        projection, "", audit,
        {"result": "evidence_missing", "matchingGapIds": ["G-CLEAR"]},
    )
    status = next(item["verificationStatus"] for item in records if item["feedbackId"] == "PF-20260820-02")

    assert status == "fully_reflected"
