import json

from scripts.generate_phase57_core_loop_projection import generate_phase57


def test_phase57_real_projection_has_unique_definitions_owned_missing_links_and_no_document_write(tmp_path):
    summary = generate_phase57(tmp_path)
    assert summary["integrityGate"] == "pass"
    assert summary["sourceFilesUnchanged"] is True
    assert summary["modifiedApprovedRuleCount"] == summary["modifiedApprovedGapCount"] == 0
    assert summary["finalDocumentGenerated"] is False
    assert summary["parameterResolverInvoked"] is False
    result = json.loads((tmp_path / "rule-projections.json").read_text(encoding="utf-8"))
    assert all(item["primaryOwner"] for item in result["ruleProjections"])
    assert all(item["primaryOwner"] for item in result["missingLinkProjections"])
    assert result["coreGameplayLoop"]["definitionMode"] == "overview_only"
    assert len({item["sourceRuleId"] for item in result["ruleProjections"]}) == len(result["ruleProjections"])
    by_rule = {item["sourceRuleId"]: item for item in result["ruleProjections"]}
    assert by_rule["RULE-4CC81AFEE84D"]["ruleRole"] == "processing"
    assert by_rule["RULE-56BF4482E94F"]["primaryOwner"] == "V2CH-011"
    assert by_rule["RULE-FFF28C63B44E"]["primaryOwner"] == "V2CH-012"
    assert by_rule["RULE-6D655A0E67FF"]["primaryOwner"] == "V2CH-018"
    missing = {item["semanticKey"]: item for item in result["missingLinkProjections"]}
    assert missing["loadout_capacity"]["primaryOwner"] == "V2CH-003"
