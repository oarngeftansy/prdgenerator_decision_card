from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.mechanic_design_synthesis import accept_mechanic_design


ART = ROOT / "artifacts/mechanic-design-synthesis-2026-08-18"
PROPOSALS = ROOT / "artifacts/mechanic-requirement-ai-proposals-2026-08-18/ai-proposed-rules.json"

ACCEPTANCES = {
    "MDES-WEAPON": {
        "MDI-DD15DBE1BA5C0D5C": "新武器自动进入首个空栏并立即参与自动攻击；重复获得同一武器时，用于强化已有武器。",
        "MDI-2B655BEF0F01A087": "武器以投射物命中或持续区域结算作为伤害触发方式。",
    },
    "MDES-DRAW": {
        "MDI-362AF7662DEBB88D": "完成当前三选一后暂停战斗，进入独立抽取并自动开始滚动。",
        "MDI-6C8E8F172A77D0C2": "滚动停止后展示3项结果，并一次性确认本次抽取结果。",
        "MDI-781B9EEE9C9F3163": "抽取结果确认后调用已批准的武器结果处理；处理完成后退出抽取并返回战斗。",
    },
    "MDES-CHOICE": {
        "MDI-8E527CB9420B71D6": "三选一界面打开后暂停关卡计时、怪物移动和武器攻击；选择期间保留当前战斗对象与累计数据。",
        "MDI-2B5B4FCBEF6A1C5F": "玩家确认候选后立即应用对应效果；应用完成后关闭三选一界面，并恢复关卡计时、怪物移动和武器攻击。",
    },
    "MDES-MONSTER": {
        "MDI-701DC39277A22F6A": "怪物进入战区后以载具为目标持续移动；与载具接触时停止本次移动。",
        "MDI-F2B427DA81AD20E1": "怪物首次与载具接触时停止移动，并立即结算一次接触伤害。",
        "MDI-C521DA033850103E": "怪物与载具保持接触期间，按攻击间隔周期造成伤害；接触结束后停止本次接触伤害。",
        "MDI-902792D32C73DEE7": "接触结束且怪物仍存活时，怪物恢复向载具移动并尝试再次接触。",
        "MDI-343F0657859BD453": "怪物死亡时停止移动，并取消尚未结算的后续接触伤害。",
    },
    "MDES-BOSS": {
        "MDI-C155B64BFD094EE1": "普通阶段完成后停止生成普通敌人；显示首领来袭提示，提示结束后生成 Boss、启用 Boss 血条并进入首领阶段。",
        "MDI-4C7B4D9B00297774": "Boss 生命值归零时移除 Boss 与 Boss 血条，并停止 Boss 行为；场上残余普通怪物和玩家武器继续运行。",
    },
    "MDES-STATS": {
        "MDI-25AEEECF0E06DCB7": "本局进入可战斗状态时开始累计各武器伤害；进入选择或抽取界面时保留累计值。",
        "MDI-C904655E8D9E0CB2": "关卡完成或失败判定成立时停止累计并冻结本局伤害结果；结算读取该冻结结果。",
    },
    "MDES-OUTCOME": {
        "MDI-2B754262114389EE": "成功或失败判定成立后锁定结果，停止新增刷怪、怪物移动、武器攻击和玩家战斗输入；随后进入对应结算流程。",
        "MDI-9B6FBFA32D18B52F": "玩家点击返回后离开结算，并回到当前挑战的关卡入口页。",
    },
}


def main() -> None:
    payload = json.loads((ART / "mechanic-design-syntheses.json").read_text(encoding="utf-8"))
    proposal_payload = json.loads(PROPOSALS.read_text(encoding="utf-8"))
    dimension_by_requirement = {
        item["originRequirementId"]: item["executionDimensionId"]
        for item in proposal_payload["proposals"]
    }
    results = []
    decisions = []
    for mechanic_design_id, accepted_texts in ACCEPTANCES.items():
        synthesis = next(item for item in payload["syntheses"]
                         if item["mechanicDesignId"] == mechanic_design_id)
        result = accept_mechanic_design(
            synthesis, accepted_text_by_design_item=accepted_texts,
            dimension_by_requirement=dimension_by_requirement,
        )
        results.append(result)
        decisions.append({
            "mechanicDesignId": mechanic_design_id, "action": "accept_mechanic",
            "approvalGranularity": "design_item",
            "designItemDecisions": [
                {"designItemId": rule["sourceDesignItemId"], "action": "accept",
                 "approvedRuleId": rule["ruleId"],
                 "satisfiesRequirementIds": rule["satisfiesRequirementIds"]}
                for rule in result["approvedRules"]
            ],
            "mergedMechanicRuleCount": 0,
        })
    approved_rules = [rule for result in results for rule in result["approvedRules"]]
    closure_overlay = {requirement_id: status for result in results
                       for requirement_id, status in result["requirementClosureOverlay"].items()}
    updated_by_mechanic = {result["mechanicDesignId"]: result["updatedSynthesis"] for result in results}
    review_state = {
        "mechanics": [
            {"mechanicDesignId": item["mechanicDesignId"],
             "approvalState": "approved" if item["mechanicDesignId"] in ACCEPTANCES else "pending_review"}
            for item in payload["syntheses"]
        ],
        "approvedMechanicCount": len(ACCEPTANCES),
        "pendingMechanicCount": len(payload["syntheses"]) - len(ACCEPTANCES),
        "formalPublicationMutationCount": 0, "jobMutationCount": 0,
    }
    outputs = {
        "mechanic-review-decisions.json": {"decisions": decisions},
        "approved-mechanic-rules.json": {"rules": approved_rules,
                                           "approvedRuleCount": len(approved_rules)},
        "requirement-closure-overlay.json": {
            "requirements": [{"requirementId": requirement_id, "status": status,
                              "satisfiedByRuleIds": [rule["ruleId"] for rule in approved_rules
                                                     if requirement_id in rule["satisfiesRequirementIds"]]}
                             for requirement_id, status in closure_overlay.items()],
            "sourceRequirementMutationCount": 0,
        },
        "mechanic-design-review-state.json": review_state,
        "mechanic-design-syntheses-after-review.json": {
            **payload,
            "syntheses": [updated_by_mechanic.get(item["mechanicDesignId"], item)
                           for item in payload["syntheses"]],
        },
    }
    for name, value in outputs.items():
        (ART / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
