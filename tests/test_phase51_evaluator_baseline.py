import hashlib
import json

from scripts.evaluate_phase51_baseline import evaluate_baseline


def _artifact_hash(value):
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def test_baseline_contains_all_scores_gates_findings_and_legacy_isolation(tmp_path):
    report = evaluate_baseline(tmp_path)
    assert len(report["paradigmAlignment"]["dimensions"]) == 6
    assert len(report["executionCompleteness"]["dimensions"]) == 5
    assert len(report["hardGates"]) == 5
    assert "granularityReport" in report
    assert "attributedFindings" in report
    assert "targetDelta" in report
    assert "minimumNextFixModule" in report
    assert report["qualificationStatus"] in {"not_qualified", "pending", "fail"}
    assert report["scoreIndependence"]["legacyEvaluatorInputsUsed"] is False

    legacy = json.loads((tmp_path / "legacy-comparison.json").read_text(encoding="utf-8"))
    assert legacy["classification"] == "legacy false-negative baseline metrics"
    assert legacy["includedInNewScore"] is False
    assert legacy["qualityScore"] == 91


def test_single_baseline_run_cannot_claim_qualified(tmp_path):
    report = evaluate_baseline(tmp_path)
    assert report["qualificationStatus"] != "qualified"
    provenance = json.loads((tmp_path / "provenance.json").read_text(encoding="utf-8"))
    assert provenance["sourceFilesUnchanged"] is True
    assert provenance["modifiedBodyCount"] == 0
    assert provenance["parameterResolverInvoked"] is False


def test_baseline_explainability_snapshot_is_stable(tmp_path):
    report = evaluate_baseline(tmp_path)
    leading = report["attributedFindings"][0]
    assert set(leading) == {"metric", "observed", "reference", "impact", "ownerLayer", "minimalFix"}
    snapshot = json.loads((tmp_path / "explainability-snapshot.json").read_text(encoding="utf-8"))
    assert snapshot["paradigmAlignmentTotal"] == report["paradigmAlignment"]["total"]
    assert snapshot["leadingFinding"] == leading
    assert snapshot["minimumNextFixModule"] == report["minimumNextFixModule"]
    assert report["paradigmAlignment"] == {
        "total": 90.42,
        "dimensions": {
            "chapterOrganization": 14.29,
            "bodyGranularity": 17.13,
            "planningLanguage": 20,
            "informationDensity": 14.0,
            "mechanismBlockOrganization": 15,
            "deliveryLayering": 10,
        },
    }
    assert report["executionCompleteness"] == {
        "total": 39.57,
        "dimensions": {
            "mechanismChainCompleteness": 8.92,
            "programExecutability": 23.33,
            "qaTestability": 7.32,
            "parameterContractCompleteness": 0.0,
            "gapClosure": 0.0,
        },
    }
    assert {key: leading[key] for key in ("metric", "impact", "ownerLayer", "minimalFix")} == {
        "metric": "completeness.mechanism_chain",
        "impact": -21.08,
        "ownerLayer": "Gap",
        "minimalFix": "Review the open SchemaSlot Gaps; add only evidence-backed Rules for confirmed answers.",
    }
    assert report["minimumNextFixModule"] == "Gap"


def test_baseline_persists_the_exact_evaluated_delivery_and_hash(tmp_path):
    report = evaluate_baseline(tmp_path)
    snapshot = json.loads((tmp_path / "evaluated_delivery_snapshot.json").read_text(encoding="utf-8"))

    assert (tmp_path / "evaluated_delivery_snapshot.md").read_text(encoding="utf-8").startswith(
        "# Evaluated ExecutionDelivery Snapshot"
    )
    assert report["evaluatedArtifactHash"] == snapshot["evaluatedArtifactHash"]
    assert snapshot["evaluatedArtifactHash"] == _artifact_hash(snapshot["executionDelivery"])
    assert snapshot["executionDelivery"]["deliveryVersion"] == "logic-delivery-v1"
    assert all(prefix not in snapshot["executionDelivery"]["markdown"] for prefix in ("VIS-RULE-", "RULE-", "MB-", "GAP-"))
    assert all(
        {"paragraphId", "supportingRuleIds", "mechanismBlockId", "carrierType", "containsVisualBlockReference"}
        <= set(paragraph)
        for chapter in snapshot["annotatedChapters"]
        for paragraph in chapter["paragraphs"]
    )
