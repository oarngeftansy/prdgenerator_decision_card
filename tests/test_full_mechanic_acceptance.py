from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.apply_full_mechanic_acceptance import ROOT, main


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_accept_all_approves_visible_inferences_without_copying_confirmed_rules(tmp_path):
    main(output_dir=tmp_path)
    approval = json.loads((tmp_path / "approved-review-rules.json").read_text(encoding="utf-8"))
    decisions = json.loads((tmp_path / "review-decisions.json").read_text(encoding="utf-8"))
    rules = approval["rules"]
    assert approval["approvedRuleCount"] == 14
    assert decisions["retainedConfirmedRuleCount"] == 5
    assert len({rule["ruleId"] for rule in rules}) == 14
    assert all(rule["satisfiesRequirementIds"] for rule in rules)
    assert all(rule["sourceReviewRuleId"].startswith("DENS-") for rule in rules)
    assert all(rule["sourceDesignItemIds"] for rule in rules)
    assert all(rule["ruleStatus"] == "approved_review" for rule in rules)
    assert all(len(rule["planningOwnerPath"]) >= 3 for rule in rules)
    assert all(term not in rule["text"] for rule in rules
               for term in ("AI", "待确认", "建议", "Primary Owner", "实例标识"))


def test_accept_all_registers_only_missing_lineage_and_closes_via_rule_ids(tmp_path):
    main(output_dir=tmp_path)
    registered = json.loads((tmp_path / "registered-requirements.json").read_text(encoding="utf-8"))
    closure = json.loads((tmp_path / "requirement-closure-overlay.json").read_text(encoding="utf-8"))
    assert {item["executionDimensionId"] for item in registered["requirements"]} == {
        "attack.multiple_attackers", "attack.pause_resume"
    }
    assert all(item["requirementId"].startswith("REQ-") for item in registered["requirements"])
    assert all(item["priorSource"]["type"] == "rule_gap" for item in registered["requirements"])
    assert closure["sourceRequirementMutationCount"] == 0
    assert all(item["status"] == "resolved" and item["satisfiedByRuleIds"]
               for item in closure["requirements"])


def test_accept_all_chooses_recommended_full_slot_option_and_preserves_frozen_files(tmp_path):
    frozen = [
        ROOT / "data/jobs/8312a91c89e144e6a59f81b982f14c06/job.json",
        ROOT / "artifacts/planning-content-phase6.5-chapter-assembly-2026-08-18/human-planning-preview.md",
        ROOT / "artifacts/full-mechanic-reconstruction-2026-08-19/reconstructed-models.json",
    ]
    frozen = [path for path in frozen if path.exists()]
    before = {str(path): _sha(path) for path in frozen}
    main(output_dir=tmp_path)
    decisions = json.loads((tmp_path / "review-decisions.json").read_text(encoding="utf-8"))
    assert decisions["alternativeDecisions"] == [{
        "alternativeId": "ALT-WEAPON-FULL-SLOT",
        "selectedOptionId": "W-FULL-A",
        "action": "accept_recommended",
    }]
    assert before == {str(path): _sha(path) for path in frozen}
