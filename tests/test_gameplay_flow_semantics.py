import json
from copy import deepcopy
from pathlib import Path

from backend.gameplay_flow_semantics import flow_chain_report, route_structured_rules
from backend.gameplay_review_model import _sync_structured_review_cache


def test_rule_types_route_to_owned_sections_without_rewriting_approved_text():
    rules = [
        {"ruleType": "flow", "behavior": "玩家点击升级后，系统扣除钞票并提升店铺等级。"},
        {"ruleType": "presentation", "behavior": "底部面板显示当前等级。"},
        {"ruleType": "numeric", "behavior": "每秒收益等于基础收入加其他加成。"},
        {"ruleType": "logic", "behavior": "等级达到上限后不可继续升级。"},
        {"ruleType": "config", "behavior": "等级上限读取店铺配置表。"},
    ]

    routed = route_structured_rules(rules)

    assert routed == {
        "normalFlow": [rules[0]["behavior"]],
        "keyRules": [rules[3]["behavior"]],
        "presentationRules": [rules[1]["behavior"]],
        "numericRules": [rules[2]["behavior"]],
        "configurationRules": [rules[4]["behavior"]],
    }


def test_structured_review_cache_uses_the_shared_router():
    rules = [
        {"ruleId": "R-FLOW", "ruleType": "flow", "behavior": "玩家确认升级后，系统提升一级并刷新可购买内容。"},
        {"ruleId": "R-PRESENT", "ruleType": "presentation", "behavior": "界面显示当前店铺等级。"},
        {"ruleId": "R-NUMERIC", "ruleType": "numeric", "behavior": "每秒收益为4.9万。"},
    ]
    model = {
        "chapters": [{"scope": "店铺升级"}],
        "ruleIntelligenceProjection": {"reviewProjection": {"chapters": [{
            "title": "店铺升级", "ruleDefinitions": deepcopy(rules), "references": [],
        }]}}
    }

    _sync_structured_review_cache(model)

    sections = model["chapters"][0]["plannerSections"]
    assert sections["normalFlow"] == [rules[0]["behavior"]]
    assert sections["presentationRules"] == [rules[1]["behavior"]]
    assert sections["numericRules"] == [rules[2]["behavior"]]
    assert rules == model["ruleIntelligenceProjection"]["reviewProjection"]["chapters"][0]["ruleDefinitions"]


def test_four_projects_use_one_flow_contract_without_project_specific_branches():
    cases = json.loads((Path(__file__).parent / "fixtures" / "gameplay-flow-semantic-cases-v1.json").read_text(encoding="utf-8"))

    for case in cases:
        chapter = {
            "chapterType": case["chapterType"],
            "plannerSections": {
                "normalFlow": case.get("normalFlow", []),
                "presentationRules": case.get("presentationRules", []),
            },
        }
        report = flow_chain_report(chapter)
        assert report["passed"] is case["expectedPassed"], case["caseId"]


def test_static_values_and_formulae_cannot_satisfy_a_declared_gameplay_flow():
    report = flow_chain_report({
        "chapterType": "presentation",
        "plannerSections": {"normalFlow": [
            "当前画面显示店铺等级2767级。",
            "底部面板显示每秒收益4.9万。",
            "收益公式为基础收入加其他加成。",
        ]},
    })

    assert report["passed"] is False
    assert "STATIC_EVIDENCE_IS_NOT_FLOW" in report["errors"]


def test_project_identity_swap_never_changes_the_shared_semantic_result():
    chapter = {"chapterType": "custom", "plannerSections": {"normalFlow": [
        "玩家点击确认后提交选择。", "系统保存选择结果并进入下一页面。",
    ]}}

    first = flow_chain_report({**deepcopy(chapter), "jobId": "job-a", "projectName": "项目甲"})
    second = flow_chain_report({**deepcopy(chapter), "jobId": "job-b", "projectName": "项目乙"})

    assert first == second
