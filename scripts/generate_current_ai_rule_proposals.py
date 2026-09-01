from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.mechanic_requirement_discovery import build_ai_proposed_rule, build_proposal_review_view


SOURCE = ROOT / "artifacts/mechanic-requirement-closure-2026-08-18/requirements-after-closure.json"
OUT = ROOT / "artifacts/mechanic-requirement-ai-proposals-2026-08-18"

ORIGINAL_PROPOSAL_TEXTS = {
    "REQ-F61EFECBFE1093E8": "获得武器后，将该武器加入本局可用武器栏位并激活。",
    "REQ-2CA80CDD2FD5C988": "武器投射物命中目标或持续伤害区域生效时，产生该武器的伤害。",
    "REQ-CC85AEBF7CB1C8BE": "进入独立武器抽取流程后，显示抽取界面并开始滚动结果。",
    "REQ-04DCE92677DEB71C": "滚动停止并展示结果列表后，将该列表作为本次抽取的待确认结果。",
    "REQ-E0ABE960A787E54B": "本次抽取结果提交后，将结果加入本局可用内容并返回战斗。",
    "REQ-194E59AB4BA912B4": "候选界面出现后进入临时选择状态，直到本次选择结果完成后离开该状态。",
    "REQ-0CD68EDF526496E5": "玩家完成一次候选选择并应用结果后，退出选择界面并返回战斗。",
    "REQ-AE2FD7AB7BEEB006": "怪物未进入攻击状态时，持续向载具方向移动。",
    "REQ-45E3E630542C22CC": "怪物与载具满足接触条件时，进入对载具造成伤害的攻击状态。",
    "REQ-D8ED31CA831ACC91": "怪物不再满足接触条件或怪物死亡时，退出当前攻击状态。",
    "REQ-F43B939B70489678": "怪物退出攻击状态且仍存活时，恢复向载具方向移动。",
    "REQ-E2B6EDA6773FB539": "怪物死亡时中断正在进行的移动与攻击处理。",
    "REQ-72A4E044E0DAA057": "普通战斗阶段结束并显示首领来袭提示后，首领进入战场并开始首领战。",
    "REQ-4E569528251014A2": "Boss 生命状态达到终止条件后，Boss 从战场消失并结束首领战阶段。",
    "REQ-1F2D406715B8BE19": "本局战斗开始时，开始累计纳入统计的各武器伤害。",
    "REQ-D71ECA4159A4E92B": "关卡完成时停止累计本局武器伤害，并将统计结果交给结算。",
    "REQ-BE81ACAECDE80CFE": "成功或失败判定成立后，终止当前战斗并进入对应结果流程。",
    "REQ-BE6353FE4885C26C": "玩家完成结算操作后离开结算，并返回关卡外的挑战入口。",
}


SPECS = {
    "REQ-F61EFECBFE1093E8": ("新武器自动填入首个空栏并立即参与自动攻击；同武器结果用于强化已有武器。", ["RULE-FFF28C63B44E"], "weapon.slot_activation", "当前素材未证明栏位填入和同武器处理", "medium", "behavior_hypothesis", ["new_resource_flow: 自动填入空栏", "new_lifecycle_result: 立即参与攻击", "new_duplicate_behavior: 同武器强化"]),
    "REQ-2CA80CDD2FD5C988": ("武器执行投射物攻击或持续区域攻击；各攻击类型的具体伤害结算时点仍需确认。", ["RULE-4CC81AFEE84D", "FACT-64D2669FB2AC"], "weapon.damage_trigger", "攻击表现已确认，但精确伤害触发帧未确认", "low", "minimal_completion", []),
    "REQ-CC85AEBF7CB1C8BE": ("完成当前三选一强化后暂停战斗，进入独立抽取界面并自动开始滚动。", ["EVC-CC85AEBF7CB1C8BE-01"], "draw.entry", "三选一到抽取之间存在采样间隔，该触发关系属于设计补全", "medium", "behavior_hypothesis", ["new_trigger_condition: 完成三选一", "new_state_change: 暂停战斗并开始滚动"]),
    "REQ-04DCE92677DEB71C": ("滚动停止后展示3项结果，并将这3项作为本次抽取结果一次性确认。", ["EVD-6922BDD765022667", "RULE-CF719EA1E5E4"], "draw.result_commitment", "素材只证明结果可见，未证明自动确认", "medium", "behavior_hypothesis", ["new_commit_behavior: 3项结果自动一次性确认"]),
    "REQ-E0ABE960A787E54B": ("抽取结果确认后写入本局可用内容；新武器进入空栏，同武器转为强化，处理完成后返回战斗。", ["RULE-FFF28C63B44E", "EVD-6922BDD765022667", "draw_window:return_to_battle"], "draw.downstream_effect", "结果写入和重复结果处理未被素材证明", "medium", "behavior_hypothesis", ["new_resource_flow: 写入本局可用内容", "new_slot_flow: 新武器进入空栏", "new_duplicate_behavior: 同武器强化"]),
    "REQ-194E59AB4BA912B4": ("三选一界面打开后暂停关卡计时、怪物移动与武器攻击；保留当前战斗对象和累计数据，等待玩家完成选择。", ["FACT-3B6FC33D7DD8D58E"], "choice.temporary_state", "暂停范围与数据保留属于设计补全", "medium", "behavior_hypothesis", ["new_pause_scope: 计时/怪物/武器", "new_persistence_behavior: 保留战斗对象和累计数据"]),
    "REQ-0CD68EDF526496E5": ("玩家确认候选后立即应用该项效果，关闭三选一界面，并在同一流程节点恢复关卡计时、怪物移动与武器攻击。", ["FACT-22928E1DCD150EDD", "RULE-D4EA9E7B723E"], "choice.exit", "应用与恢复的精确时序属于设计补全", "medium", "behavior_hypothesis", ["new_trigger_condition: 确认候选", "new_state_change: 应用效果并恢复战斗"]),
    "REQ-AE2FD7AB7BEEB006": ("怪物进入战区后以载具为移动目标持续接近；与载具接触时停止本次接近移动。", ["SYN-MONSTER-APPROACH"], "movement.state", "停止移动条件属于设计补全", "medium", "behavior_hypothesis", ["new_object_relation: 载具作为移动目标", "new_stop_condition: 接触载具"]),
    "REQ-45E3E630542C22CC": ("怪物首次与载具接触时停止移动并开始接触伤害循环；首次伤害在接触成立时结算。", ["RULE-00320555D7EA"], "attack.entry", "停止移动、循环与首次结算时点属于设计补全", "medium", "behavior_hypothesis", ["new_state_change: 停止移动", "new_trigger_condition: 接触成立开始伤害循环"]),
    "REQ-D8ED31CA831ACC91": ("怪物与载具保持接触时周期造成伤害；接触结束后停止本次接触伤害处理。", ["RULE-00320555D7EA", "benchmark_execution_prior_v1:attack.exit"], "attack.exit", "持续周期与退出条件属于设计补全", "medium", "behavior_hypothesis", ["new_repeat_behavior: 接触期间周期伤害", "new_exit_condition: 接触结束停止伤害"]),
    "REQ-F43B939B70489678": ("接触结束且怪物仍存活时，怪物继续向载具移动并尝试再次接触。", ["SYN-MONSTER-APPROACH", "benchmark_execution_prior_v1:attack.post_exit_state"], "attack.post_exit_state", "没有接触结束后的连续行为证据", "medium", "behavior_hypothesis", ["new_post_state: 继续追击", "new_causal_relation: 接触结束后恢复移动"]),
    "REQ-E2B6EDA6773FB539": ("怪物死亡时立即停止移动，并取消尚未结算的后续接触伤害。", ["benchmark_execution_prior_v1:attack.death_interrupt"], "attack.death_interrupt", "当前素材没有怪物死亡行为链", "medium", "behavior_hypothesis", ["new_interrupt_condition: 死亡", "new_lifecycle_result: 取消后续伤害"]),
    "REQ-72A4E044E0DAA057": ("普通阶段完成后停止继续生成普通敌人，显示首领来袭提示；提示结束后生成 Boss、启用 Boss 血条并进入首领战。", ["FACT-03541492113CA568", "RULE-6297BE181A80"], "boss.entry", "普通阶段完成条件和停止刷怪属于设计补全", "medium", "behavior_hypothesis", ["new_trigger_condition: 普通阶段完成", "new_state_change: 停止刷怪并生成 Boss"]),
    "REQ-4E569528251014A2": ("Boss 生命值归零时移除 Boss 与 Boss 血条、停止 Boss 行为；场上残余普通怪物和玩家武器继续运行。", ["FACT-CA1E6EF7244D1F95", "RULE-37CB76D8A11F"], "boss.termination", "生命值归零是最合理但未被数值直接读出的终止条件", "medium", "behavior_hypothesis", ["new_trigger_condition: Boss生命归零", "new_branch_handling: 残敌与武器继续运行"]),
    "REQ-1F2D406715B8BE19": ("本局进入可战斗状态时开始累计各武器伤害；进入选择或抽取界面时保留累计值。", ["RULE-A87C8D4C1A10", "benchmark_execution_prior_v1:statistics.start"], "statistics.start", "起算点和暂停界面期间的统计行为属于设计补全", "medium", "behavior_hypothesis", ["new_lifecycle_start: 进入可战斗状态", "new_persistence_behavior: 暂停界面保留累计值"]),
    "REQ-D71ECA4159A4E92B": ("关卡完成或失败判定成立时停止累计并冻结本局伤害结果，结算读取该冻结结果。", ["RULE-0D847899C3A9", "RULE-66E4A778C0D5", "RULE-6D655A0E67FF"], "statistics.end", "停止累计和冻结时点属于设计补全", "medium", "behavior_hypothesis", ["new_lifecycle_end: 胜负判定成立", "new_snapshot_behavior: 冻结统计结果"]),
    "REQ-BE81ACAECDE80CFE": ("成功或失败判定成立后立即锁定结果，停止新增刷怪、怪物移动、武器攻击和玩家战斗输入；随后进入对应结算流程。", ["RULE-66E4A778C0D5", "RULE-6D655A0E67FF"], "outcome.termination", "统一停止范围属于设计补全", "medium", "behavior_hypothesis", ["new_state_change: 锁定结果并停止战斗系统", "new_lifecycle_result: 进入对应结算"]),
    "REQ-BE6353FE4885C26C": ("玩家点击返回后离开结算并回到当前挑战的关卡入口页。", ["F0015"], "settlement.next_state", "素材只证明存在返回操作，未证明页面去向", "medium", "behavior_hypothesis", ["new_page_destination: 当前挑战关卡入口页"]),
}

PROPOSAL_TYPES = {
    "REQ-F61EFECBFE1093E8": "alternative_design",
    "REQ-CC85AEBF7CB1C8BE": "design_inference",
    "REQ-04DCE92677DEB71C": "design_inference",
    "REQ-E0ABE960A787E54B": "design_inference",
    "REQ-194E59AB4BA912B4": "design_inference",
    "REQ-0CD68EDF526496E5": "design_inference",
    "REQ-AE2FD7AB7BEEB006": "design_inference",
    "REQ-45E3E630542C22CC": "design_inference",
    "REQ-D8ED31CA831ACC91": "design_inference",
    "REQ-F43B939B70489678": "design_inference",
    "REQ-E2B6EDA6773FB539": "design_inference",
    "REQ-72A4E044E0DAA057": "design_inference",
    "REQ-4E569528251014A2": "design_inference",
    "REQ-1F2D406715B8BE19": "design_inference",
    "REQ-D71ECA4159A4E92B": "design_inference",
    "REQ-BE81ACAECDE80CFE": "design_inference",
    "REQ-BE6353FE4885C26C": "alternative_design",
}

INFORMATION_GAIN = {
    "REQ-F61EFECBFE1093E8": [{"type": "branch_handling", "decision": "空栏自动入栏；同武器转为强化"}, {"type": "lifecycle_result", "decision": "入栏后立即参与自动攻击"}],
    "REQ-2CA80CDD2FD5C988": [{"type": "trigger_condition", "decision": "投射物命中或持续区域结算 tick 时产生伤害"}, {"type": "object_relation", "decision": "伤害归属产生该攻击的武器"}],
    "REQ-CC85AEBF7CB1C8BE": [{"type": "trigger_condition", "decision": "完成当前三选一后进入独立抽取"}, {"type": "state_change", "decision": "暂停战斗并自动开始滚动"}],
    "REQ-04DCE92677DEB71C": [{"type": "lifecycle_result", "decision": "滚动停止后将展示的3项一次性确认为本次结果"}],
    "REQ-E0ABE960A787E54B": [{"type": "branch_handling", "decision": "新武器进入空栏，同武器转为强化"}, {"type": "lifecycle_result", "decision": "结果处理完成后返回战斗"}],
    "REQ-194E59AB4BA912B4": [{"type": "state_change", "decision": "选择期间暂停计时、怪物移动和武器攻击"}, {"type": "lifecycle_result", "decision": "保留战斗对象与累计数据"}],
    "REQ-0CD68EDF526496E5": [{"type": "trigger_condition", "decision": "确认候选后立即应用效果"}, {"type": "state_change", "decision": "关闭界面并恢复计时、怪物与武器"}],
    "REQ-AE2FD7AB7BEEB006": [{"type": "object_relation", "decision": "怪物以载具为持续移动目标"}, {"type": "trigger_condition", "decision": "接触载具时停止接近移动"}],
    "REQ-45E3E630542C22CC": [{"type": "trigger_condition", "decision": "首次接触成立时结算首次伤害并开始周期伤害"}, {"type": "state_change", "decision": "接触成立时停止移动"}],
    "REQ-D8ED31CA831ACC91": [{"type": "trigger_condition", "decision": "接触结束时停止本次接触伤害循环"}],
    "REQ-F43B939B70489678": [{"type": "state_change", "decision": "接触结束且存活时恢复向载具追击"}],
    "REQ-E2B6EDA6773FB539": [{"type": "exception_boundary", "decision": "死亡时取消移动与未结算的后续接触伤害"}],
    "REQ-72A4E044E0DAA057": [{"type": "state_change", "decision": "普通阶段完成后停止普通刷怪并生成 Boss"}, {"type": "lifecycle_result", "decision": "启用 Boss 血条并进入首领战"}],
    "REQ-4E569528251014A2": [{"type": "trigger_condition", "decision": "Boss生命归零时终止 Boss 行为"}, {"type": "branch_handling", "decision": "残余普通怪物和玩家武器继续运行"}],
    "REQ-1F2D406715B8BE19": [{"type": "trigger_condition", "decision": "进入可战斗状态时创建并开始本局统计"}, {"type": "data_source", "decision": "输入为归属到各武器的伤害值"}],
    "REQ-D71ECA4159A4E92B": [{"type": "trigger_condition", "decision": "成功或失败判定成立时停止累计"}, {"type": "lifecycle_result", "decision": "冻结结果供结算读取"}],
    "REQ-BE81ACAECDE80CFE": [{"type": "state_change", "decision": "锁定胜负后停止刷怪、移动、攻击与输入"}, {"type": "lifecycle_result", "decision": "停止完成后进入对应结算"}],
    "REQ-BE6353FE4885C26C": [{"type": "branch_handling", "decision": "返回操作在关卡入口页与主界面之间选择一个明确去向"}],
}

ALTERNATIVES = {
    "REQ-F61EFECBFE1093E8": [
        {"alternativeId": "A", "text": "新武器自动填入首个空栏并立即参战；同武器转为强化。", "gameplayImpact": "获取结果立即转化为战力", "advantages": ["流程快", "兼容自动战斗"], "risks": ["满栏仍需后续规则"], "compatibility": "与现有武器栏和自动攻击兼容"},
        {"alternativeId": "B", "text": "获得武器后进入栏位选择，由玩家确认放入位置。", "gameplayImpact": "增加配装决策", "advantages": ["玩家可控"], "risks": ["打断战斗节奏"], "compatibility": "需要新增栏位选择交互"},
        {"alternativeId": "C", "text": "获得结果先进入临时库存，战斗结束后统一配置。", "gameplayImpact": "局内获取不立即生效", "advantages": ["避免局内打断"], "risks": ["削弱即时成长反馈"], "compatibility": "需要新增临时库存"},
    ],
    "REQ-BE6353FE4885C26C": [
        {"alternativeId": "A", "text": "返回当前挑战的关卡入口页。", "gameplayImpact": "便于再次挑战或退出", "advantages": ["路径短", "符合挑战循环"], "risks": ["入口页需保留挑战上下文"], "compatibility": "与结算返回按钮兼容"},
        {"alternativeId": "B", "text": "返回游戏主界面。", "gameplayImpact": "结束当前挑战循环", "advantages": ["状态收口清晰"], "risks": ["再次挑战路径更长"], "compatibility": "不依赖关卡入口页状态"},
    ],
}

MECHANIC_LABELS = {
    "PMECH-831F3EDC1472": "武器获取、栏位、攻击与独立抽取",
    "PMECH-79F65266B17C": "三选一",
    "PMECH-2C4FBE5EC68C": "怪物移动与攻击",
    "PMECH-BBD7CED5E8D0": "Boss 与关卡阶段",
    "PMECH-B1DB0C6035A1": "伤害统计、胜负与结算",
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    existing_path = OUT / "ai-proposed-rules.json"
    previous = (json.loads(existing_path.read_text(encoding="utf-8"))["proposals"]
                if existing_path.exists() else [])
    previous_by_requirement = {item["originRequirementId"]: item for item in previous}
    report = json.loads(SOURCE.read_text(encoding="utf-8"))
    by_id = {item["requirementId"]: item for item in report["requirements"]}
    unresolved_core = [item for item in report["requirements"]
                       if item["dimensionRole"] == "core" and item["status"] != "resolved"]
    proposals = []
    review_queue = []
    for requirement in unresolved_core:
        requirement_id = requirement["requirementId"]
        text, refs, prior_ref, uncertainty, assumption_level, proposal_mode, unsupported = SPECS[requirement_id]
        proposal_type = PROPOSAL_TYPES.get(requirement_id, "conservative")
        alternatives = ALTERNATIVES.get(requirement_id, [])
        proposal = build_ai_proposed_rule(
            requirement,
            proposal_text=text,
            known_context_refs=refs,
            proposal_bases=[
                {"type": "existing_context", "ref": ref} for ref in refs
            ] + [{"type": "mechanic_execution_prior", "ref": prior_ref}],
            uncertainties=[uncertainty],
            assumption_level=assumption_level,
            proposal_mode=proposal_mode,
            unsupported_specificity=unsupported,
            proposal_type=proposal_type,
            reasoning_basis=(["当前玩法闭环需要该 Requirement 有可执行答案",
                              f"Execution Prior 仅提供检查维度：{prior_ref}",
                              "采用与现有上下游规则冲突最少的通用系统设计"]
                             if proposal_type != "conservative" else []),
            conflicting_evidence=[],
            alternatives=alternatives,
            recommended_alternative_id="A" if alternatives else None,
            information_gain=INFORMATION_GAIN[requirement_id],
        )
        proposals.append(proposal)
        review_queue.append({
            "requirementId": requirement_id,
            "ownerPath": requirement.get("ownerPath", {}),
            "executionDimensionId": requirement["executionDimensionId"],
            "reviewView": build_proposal_review_view(
                confirmed_context=refs,
                question=f"请审核 {requirement['executionDimensionId']} 的最小规则定义。",
                proposal=proposal,
            ),
        })
    payload = {
        "proposals": proposals,
        "metrics": {
            "unresolvedCoreRequirementCount": len(unresolved_core),
            "proposalCount": len(proposals),
            "proposalCoverageRate": round(len(proposals) / len(unresolved_core) * 100, 1),
            "validRuleCount": sum(item["valid"] for item in proposals),
            "publicationEligibleCount": sum(item["publicationEligible"] for item in proposals),
            "confirmedRuleCount": sum(item["countsAsConfirmedRule"] for item in proposals),
            "questionOnlyCount": 0,
            "proposalTypeCounts": {
                proposal_type: sum(item["proposalType"] == proposal_type for item in proposals)
                for proposal_type in ("conservative", "design_inference", "alternative_design")
            },
            "assumptionLevelCounts": {
                level: sum(item["assumptionLevel"] == level for item in proposals)
                for level in ("low", "medium", "high")
            },
            "unsupportedSpecificityProposalCount": sum(bool(item["unsupportedSpecificity"])
                                                        for item in proposals),
            "unsupportedSpecificityHitCount": sum(len(item["unsupportedSpecificity"])
                                                   for item in proposals),
            "returnedToProbeOrPlaceholderCount": sum(not item["defaultReviewEligible"]
                                                      for item in proposals),
            "defaultReviewEligibleCount": sum(item["defaultReviewEligible"] for item in proposals),
            "informationGainProposalCount": sum(bool(item["informationGain"]) for item in proposals),
            "informationGainItemCount": sum(item["informationGainCount"] for item in proposals),
            "informationGainTypeCounts": dict(sorted(Counter(
                gain["type"]
                for item in proposals
                for gain in item["informationGain"]
            ).items())),
            "informationGainGateFailureCount": 0,
        },
        "requirementStatusMutationCount": 0,
        "formalPublicationMutationCount": 0,
    }
    (OUT / "ai-proposed-rules.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT / "proposal-review-queue.json").write_text(
        json.dumps(review_queue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    comparison = [{
        "requirementId": item["originRequirementId"],
        "executionDimensionId": item["executionDimensionId"],
        "before": ORIGINAL_PROPOSAL_TEXTS[item["originRequirementId"]],
        "after": item["proposalText"],
        "assumptionLevel": item["assumptionLevel"],
        "proposalMode": item["proposalMode"],
        "unsupportedSpecificity": item["unsupportedSpecificity"],
        "supportingSources": item["knownContextRefs"],
        "informationGain": item["informationGain"],
        "defaultReviewEligible": item["defaultReviewEligible"],
    } for item in proposals]
    (OUT / "proposal-before-after.json").write_text(
        json.dumps(comparison, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# 《一路狂飙》AI 完整可玩设计审核稿", "",
             "> 本文是 AI Proposed Design，不是 Confirmed Rule，也不进入正式 Publication。", ""]
    for mechanic_id, label in MECHANIC_LABELS.items():
        lines.extend([f"## {label}", ""])
        for proposal in [item for item in proposals if item["mechanicId"] == mechanic_id]:
            lines.extend([f"### {proposal['executionDimensionId']}", "",
                          f"- 类型：`{proposal['proposalType']}`；假设等级：`{proposal['assumptionLevel']}`"])
            if proposal["proposalType"] == "alternative_design":
                for option in proposal["alternatives"]:
                    mark = "（推荐）" if option["alternativeId"] == proposal["recommendedAlternativeId"] else ""
                    lines.extend([f"- 方案 {option['alternativeId']}{mark}：{option['text']}",
                                  f"  - 玩法影响：{option['gameplayImpact']}",
                                  f"  - 优点：{'；'.join(option['advantages'])}",
                                  f"  - 风险：{'；'.join(option['risks'])}",
                                  f"  - 兼容性：{option['compatibility']}"])
            else:
                lines.append(f"- AI 推荐：{proposal['proposalText']}")
            lines.append("- 可执行信息增量：" + "；".join(
                f"{gain['type']}：{gain['decision']}" for gain in proposal["informationGain"]
            ))
            lines.extend([f"- 推定依据：{'；'.join(proposal['reasoningBasis']) or '当前项目 Evidence / Fact / Rule'}",
                          f"- 不确定点：{'；'.join(proposal['uncertainties'])}",
                          f"- 冲突证据：{'；'.join(proposal['conflictingEvidence']) or '无'}", ""])
    (OUT / "ai-playable-design-preview.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
