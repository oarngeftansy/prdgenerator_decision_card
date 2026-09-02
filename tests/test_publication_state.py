from backend.document_assembler import build_final_document, document_to_markdown
from backend.planning_language_renderer import render_rule
from backend.publication_state import normalize_publication_state


def _rule(state: str, review_status: str | None = None):
    return {
        "ruleId": f"R-{state}",
        "ownerChapterId": "CH-1",
        "ruleType": "logic",
        "behavior": "系统从当前可用技能池中随机抽取3个候选技能",
        "semanticValidity": "valid",
        "reviewStatus": review_status or state,
        "publicationState": state,
    }


def test_publication_state_visual_semantics():
    assert normalize_publication_state({"evidenceLevel": "observed"}) == "confirmed"
    assert render_rule(_rule("confirmed"))["visual"]["highlight"] is None
    assert render_rule(_rule("inferred"))["visual"]["highlight"] == "yellow"
    assert render_rule(_rule("proposed"))["visual"]["highlight"] == "yellow"
    assert render_rule(_rule("conflict", "confirmed"))["visual"]["highlight"] == "red"


def test_inferred_and_proposed_rules_are_decisive_copy_without_meta_labels():
    for state in ("inferred", "proposed"):
        result = render_rule(_rule(state))
        assert result["status"] == "rendered"
        assert result["publicationState"] == state
        assert result["text"] == "系统从当前可用技能池中随机抽取3个候选技能。"
        assert "推断" not in result["text"]
        assert "待确认" not in result["text"]
        assert "建议" not in result["text"]


def test_final_turns_planner_completion_into_yellow_rule_and_hides_open_question():
    approved = {
        "chapters": [{"chapterId": "CH-1", "system": "局内成长", "object": "技能选择", "title": "技能选择"}],
        "rules": [],
        "gaps": [
            {
                "chapterId": "CH-1",
                "gapDomain": "planning",
                "applicabilityStatus": "applicable",
                "specificity": "concrete_decision",
                "displayMode": "proposal",
                "proposal": "已满级技能移出候选池，同次候选不重复",
            },
            {
                "chapterId": "CH-1",
                "gapDomain": "planning",
                "applicabilityStatus": "applicable",
                "specificity": "concrete_decision",
                "question": "权重配置来源是什么？",
            },
        ],
    }
    document = build_final_document(approved)
    sentence = document["systems"][0]["objects"][0]["chapters"][0]["groups"][0]["sentences"][0]
    assert sentence["publicationState"] == "proposed"
    assert sentence["visual"]["highlight"] == "yellow"
    assert sentence["text"] == "已满级技能移出候选池，同次候选不重复。"
    assert document["unresolvedDiagnostics"][0]["question"] == "权重配置来源是什么？"

    markdown = document_to_markdown(document)
    assert "策划建议（待确认）" not in markdown
    assert "**待确认**" not in markdown
    assert "已满级技能移出候选池，同次候选不重复。" in markdown
