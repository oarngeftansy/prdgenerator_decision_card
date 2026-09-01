import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "artifacts/gve16-complete-delivery-gap-audit-2026-08-19/一路狂飙-GVE16-最完整差异审计.md"
MATRIX = AUDIT.parent / "alignment-closure-matrix.json"


def test_alignment_closure_matrix_is_complete_and_current():
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/build_alignment_closure_matrix.py"), "--check"],
        cwd=ROOT,
        check=True,
    )
    audit_ids = set(re.findall(r"(?m)^\|\s*((?:H|UE|W|C|D|M|L|S|P5|P6|PR)-\d+)\s*\|", AUDIT.read_text(encoding="utf-8")))
    payload = json.loads(MATRIX.read_text(encoding="utf-8"))
    items = payload["items"]
    matrix_ids = {item["auditId"] for item in items if not item["auditId"].startswith("X-")}
    assert matrix_ids == audit_ids
    assert payload["summary"] == {"total": 195, "atomic": 186, "crossDelivery": 9, "closedBaseline": 141, "evidenceResolved": 2, "approvedDesign": 24, "parameterResolved": 20, "scopeConfirmedNotApplicable": 5, "blocked": 3, "closed": 195, "open": 0}


def test_every_open_item_has_route_landing_and_acceptance():
    items = json.loads(MATRIX.read_text(encoding="utf-8"))["items"]
    allowed_targets = {
        "fixed", "approved_design", "evidence_resolved", "parameter_resolved",
        "scope_confirmed_not_applicable", "blocked_by_missing_source",
    }
    for item in items:
        assert item["targetState"] in allowed_targets
        assert item["actions"]
        assert item["affectedArtifacts"]
        assert item["acceptanceCriteria"]
        if item["closureState"] == "in_progress":
            assert item["verification"]
            assert item["remainingRisk"]
    blocked = {item["auditId"]: item for item in items if item["closureState"] == "blocked_by_missing_source"}
    assert set(blocked) == {"W-18", "P6-06", "L-13"}
    assert all(item["remainingRisk"] and item["afterEvidence"] for item in blocked.values())
    assert all(item["closureState"] != "in_progress" for item in items)
