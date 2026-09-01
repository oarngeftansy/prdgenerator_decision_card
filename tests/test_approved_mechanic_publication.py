import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "artifacts/mechanic-design-synthesis-2026-08-18"
FINAL = ROOT / "artifacts/mechanic-requirement-closure-publication-2026-08-18"


def test_all_approved_mechanic_rules_reach_clean_final_publication():
    approved = json.loads((DESIGN / "approved-mechanic-rules.json").read_text(encoding="utf-8"))["rules"]
    markdown = (FINAL / "human-planning-preview.md").read_text(encoding="utf-8")
    integrity = json.loads((FINAL / "publication-integrity.json").read_text(encoding="utf-8"))
    chains = json.loads((FINAL / "gameplay-rule-chains.json").read_text(encoding="utf-8"))

    assert len(approved) == 18
    assert all(rule["text"] in markdown for rule in approved)
    assert {rule["ruleId"] for rule in approved} <= {
        rule_id for chain in chains for rule_id in chain["supportingRuleIds"]
    }
    assert integrity["publishedApprovedMechanicRuleCount"] == 18
    assert integrity["unpublishedApprovedMechanicRuleIds"] == []
    assert integrity["placeholderCount"] == 0
    assert integrity["duplicateApprovedRuleCount"] == 0
    assert integrity["reviewLanguageTerms"] == []
    assert integrity["internalIdTerms"] == []
    assert all("/" not in line for line in markdown.splitlines() if line.startswith("#"))
