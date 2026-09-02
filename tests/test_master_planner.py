import json

import pytest

from backend.ai_provider import ProviderConfig
from backend.master_planner import MasterPlannerError, apply_planner_decisions, complete_execution_plan


def _projection():
    return {
        "publication": {
            "chapters": [{
                "chapterId": "CH-RANDOM",
                "system": "局内成长",
                "subsystem": "技能构筑",
                "object": "技能选择",
                "title": "候选生成",
                "publicationEligibility": "eligible",
                "gaps": [],
            }],
            "rules": [{
                "ruleId": "R-1",
                "canonicalOwner": "CH-RANDOM",
                "ownerChapterId": "CH-RANDOM",
                "ruleType": "logic",
                "behavior": "玩家升级时进入技能选择",
                "semanticValidity": "valid",
                "reviewStatus": "confirmed",
                "confirmationStatus": "confirmed",
                "publicationEligibility": "eligible",
            }],
            "gaps": [{
                "gapId": "G-POOL",
                "chapterId": "CH-RANDOM",
                "schemaSlot": "candidate_pool_source",
                "intent": "CandidateGeneration",
                "gapDomain": "planning",
                "applicabilityStatus": "applicable",
                "specificity": "concrete_decision",
                "status": "open",
                "question": "候选池如何过滤满级技能？",
            }],
            "finalPlanningGaps": [],
        }
    }


def test_apply_planner_decision_closes_gap_and_publishes_yellow_rule():
    result = apply_planner_decisions(_projection(), [{
        "gapId": "G-POOL",
        "publicationState": "proposed",
        "decision": "已满级技能移出候选池，同次候选不重复。",
        "ruleType": "logic",
        "conditions": [],
        "dependencies": [],
        "acceptanceCases": ["存在3个以上可用技能时返回3个不同候选"],
    }])
    publication = result["publication"]
    added = next(rule for rule in publication["rules"] if rule["ruleId"].startswith("RULE-MP-"))
    assert added["publicationState"] == "proposed"
    assert added["confirmationStatus"] == "confirmed"
    assert added["publicationEligibility"] == "eligible"
    assert added["behavior"] == "已满级技能移出候选池，同次候选不重复"
    assert publication["finalPlanningGaps"] == []
    assert publication["gaps"][0]["status"] == "planner_resolved"
    assert publication["chapters"][0]["closureStatus"] == "closed"
    assert publication["masterPlanner"]["proposedCount"] == 1


def test_complete_execution_plan_uses_structured_model_decision_without_meta_copy():
    def transport(url, headers, body, timeout):
        request_payload = json.loads(body.decode("utf-8"))
        prompt = request_payload["messages"][0]["content"]
        assert "evidence 不足不是停止条件" in prompt
        content = json.dumps({
            "decisions": [{
                "gapId": "G-POOL",
                "publicationState": "inferred",
                "decision": "系统从当前可用技能池中抽取3个不同候选技能，已满级技能不进入候选池",
                "ruleType": "logic",
                "trigger": "玩家升级并进入技能选择",
                "conditions": [],
                "result": "等待玩家确认其中1个技能",
                "dependencies": [],
                "acceptanceCases": [],
            }]
        }, ensure_ascii=False)
        return 200, json.dumps({"choices": [{"message": {"content": content}}]}).encode("utf-8")

    result = complete_execution_plan(
        _projection(),
        ProviderConfig(api_key="secret"),
        transport=transport,
    )
    added = next(rule for rule in result["publication"]["rules"] if rule["ruleId"].startswith("RULE-MP-"))
    assert added["publicationState"] == "inferred"
    assert "待确认" not in added["behavior"]
    assert "推测" not in added["behavior"]
    assert result["publication"]["masterPlanner"]["decisionCount"] == 1


def test_master_planner_rejects_meta_language_in_final_rule():
    projection = _projection()

    def transport(url, headers, body, timeout):
        content = json.dumps({
            "decisions": [{
                "gapId": "G-POOL",
                "publicationState": "proposed",
                "decision": "根据素材推测，候选池可能排除满级技能",
                "ruleType": "logic",
            }]
        }, ensure_ascii=False)
        return 200, json.dumps({"choices": [{"message": {"content": content}}]}).encode("utf-8")

    with pytest.raises(MasterPlannerError):
        complete_execution_plan(projection, ProviderConfig(api_key="secret"), transport=transport)
