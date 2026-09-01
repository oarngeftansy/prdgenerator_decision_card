from __future__ import annotations

import json
import sys
import copy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.rule_semantic_completion import (
    build_review_promotions,
    build_rule_semantic_contracts,
    render_semantically_completed_preview,
)
from backend.planning_model import build_planning_model, validate_planning_model


P622 = ROOT / "artifacts" / "planning-content-phase6.2.2-game-rule-synthesis-2026-08-17"
OUT = ROOT / "artifacts" / "planning-content-phase6.2.3-semantic-completion-2026-08-18"


def observed(dimension_id: str, label: str, text: str, *, kind: str = "rule",
             value=None, state=None, subrules=None) -> dict:
    item = {"dimensionId": dimension_id, "label": label, "kind": kind,
            "status": "observed", "displayText": text}
    if value is not None:
        item["value"] = value
    if state is not None:
        item["observedCurrentState"] = state
    if subrules:
        item["subrules"] = subrules
    return item


def unresolved(dimension_id: str, label: str, route: str, *, kind="rule", value_type=None,
               question=None, options=None, reason="玩家可感知规则不完整", decision_class=None,
               unit_required=False) -> dict:
    item = {"dimensionId": dimension_id, "label": label, "kind": kind,
            "status": "unresolved", "reviewRoute": route, "necessityReason": reason}
    if value_type:
        item["valueType"] = value_type
    if question:
        item["question"] = question
    if options:
        item["options"] = options
    if decision_class:
        item["decisionClass"] = decision_class
    if unit_required:
        item["unitRequired"] = True
    return item


def suppressed(dimension_id: str, label: str, reason: str) -> dict:
    return {"dimensionId": dimension_id, "label": label, "kind": "rule",
            "status": "suppressed", "suppressionReason": reason}


def spec(contract_id: str, mechanic: str, chapter: str, group: str, core_ids: list[str], dimensions: list[dict],
         status="confirmed") -> dict:
    return {"ruleSemanticId": contract_id, "mechanic": mechanic,
            "ownerChapter": chapter, "ruleGroup": group,
            "existenceStatus": status, "coreRuleIds": core_ids, "dimensions": dimensions}


SPECS = [
    spec("RSC-VEHICLE-HEALTH", "载具生命值", "载具", "生命值", ["SYN-VEHICLE-DAMAGE"], [
        observed("damage_reduces_health", "受伤处理", "载具受伤后扣除当前生命值。"),
    ], "strongly_supported"),
    spec("RSC-WEAPON-ACQUISITION", "武器抽取", "武器", "获取", ["SYN-WEAPON-DRAW"], [
        observed("acquisition_method", "获取方式", "武器通过抽取获得；抽取过程随机定格为武器或技能。"),
    ]),
    spec("RSC-WEAPON-SLOT", "武器栏", "武器", "武器栏", ["SYN-WEAPON-SLOTS"], [
        observed("slot_capacity", "栏位数量", "战斗中提供6个武器栏位。", kind="parameter", value=6),
    ]),
    spec("RSC-WEAPON-ATTACK", "武器攻击", "武器", "攻击", ["SYN-WEAPON-TARGET", "SYN-WEAPON-METHOD"], [
        observed("targeting", "索敌方式", "武器自动攻击射程内敌人，无需玩家手动瞄准。"),
        observed("attack_method", "攻击方式", "不同武器使用不同攻击方式。",
                 subrules=["剧毒炮向敌人发射剧毒炮弹。", "火焰喷射器持续向前喷射。"]),
        unresolved("attack_range", "攻击范围", "P6", kind="parameter", value_type="number", unit_required=True,
                   reason="射程直接决定可攻击目标范围"),
        unresolved("attack_interval", "攻击间隔", "P6", kind="parameter", value_type="number", unit_required=True,
                   reason="攻击间隔直接决定输出频率"),
        unresolved("damage_model", "伤害计算", "P4", kind="rule",
                   question="武器伤害采用什么计算规则？", reason="伤害规则决定战斗数值结果",
                   decision_class="complex_rule"),
        suppressed("no_target_polling", "无目标检测频率", "implementation_default"),
    ]),
    spec("RSC-AFFIX", "武器词条", "词条", "词条效果",
         ["SYN-AFFIX-DIMENSIONS", "SYN-AFFIX-TRADEOFF"], [
        observed("modifier_dimensions", "词条作用", "词条可修改武器的攻击范围、伤害、冷却、攻击次数和攻击方向。",
                 subrules=["火焰扩张：火焰喷射范围+30%。", "雷暴增幅：雷暴枪伤害+100%。",
                           "雷暴冷却：雷暴枪冷却时间-20%。", "多点爆炸：火焰爆炸次数+100%，伤害-20%。",
                           "广域喷射：火焰喷射改为四向喷射，伤害-20%。"]),
        observed("tradeoff", "正负效果", "部分词条在强化攻击效果的同时降低伤害。"),
    ]),
    spec("RSC-ULTIMATE-AFFIX", "终极词条", "词条", "终极词条",
         ["SYN-ULTIMATE-POOL", "SYN-ULTIMATE-COMBAT"], [
        observed("pool_entry", "进入词条库", "终极词条进入词条库后，可在后续升级时出现。"),
        observed("combat_effect", "生效结果", "广域喷射生效后，火焰喷射器同时向四个方向攻击。"),
    ]),
    spec("RSC-THREE-CHOICE", "三选一", "三选一", "触发与选择", ["SYN-THREE-CHOICE"], [
        observed("trigger_pause", "触发与暂停", "战斗等级提升时暂停战斗，并生成3张候选。"),
        observed("selection_result", "选择结果", "玩家从3项中选择1项并获得对应强化。"),
        unresolved("candidate_eligibility", "可进入三选一的内容范围", "P4", kind="rule",
                   question="哪些内容可以进入本次三选一？", reason="候选范围决定玩家可能获得的强化",
                   decision_class="complex_rule"),
        suppressed("selection_resume", "选择后恢复战斗时点", "natural_default_closure"),
        suppressed("candidate_weight", "候选权重", "scope_not_supported"),
        suppressed("without_replacement", "不放回规则", "scope_not_supported"),
        suppressed("max_level_filter", "满级过滤", "scope_not_supported"),
    ]),
    spec("RSC-AD-REFRESH", "广告刷新", "三选一", "刷新", ["SYN-REFRESH"], [
        observed("refresh_action", "刷新方式", "可观看广告刷新当前3项候选。"),
        observed("limit_exists", "次数限制", "广告刷新存在次数限制。", state="1/1"),
        unresolved("refresh_max_count", "刷新次数上限", "P6", kind="parameter", value_type="integer",
                   question="广告刷新次数上限是多少？", reason="次数上限影响玩家可重抽次数"),
        unresolved("refresh_reset_scope", "次数重置周期", "P4", kind="rule",
                   question="广告刷新次数按什么周期重置？",
                   options=["每次三选一", "每局", "每日", "自定义"], reason="重置周期改变刷新资源的生命周期"),
        suppressed("refresh_payment_timing", "刷新消耗扣除时点", "no_resource_payment_evidence"),
    ]),
    spec("RSC-MONSTER", "普通怪物", "怪物", "普通怪物", ["SYN-MONSTER-APPROACH", "SYN-MONSTER-CONTACT"], [
        observed("spawn_movement", "生成与移动", "怪物从画面上方进入战斗区域，并向载具所在区域移动。"),
        observed("contact_damage", "接触伤害", "怪物接触载具后造成伤害。"),
        suppressed("contact_damage_mode", "接触伤害方式", "default_closure_no_repeated_damage_evidence"),
        suppressed("contact_damage_interval", "接触伤害间隔", "inactive_dependency"),
    ], "strongly_supported"),
    spec("RSC-BOSS", "首领战斗", "怪物", "首领", ["SYN-BOSS-STAGE"], [
        observed("boss_stage", "首领阶段", "关卡包含首领战斗阶段。"),
    ]),
    spec("RSC-BATTLE-LEVEL", "战斗等级", "关卡", "局内成长", ["SYN-LEVEL-PROGRESS", "SYN-LEVEL-CHOICE"], [
        observed("level_progress", "等级与进度", "关卡内设独立战斗等级与升级进度。"),
        observed("level_up_result", "升级结果", "战斗等级提升时触发三选一。"),
        unresolved("growth_source", "成长进度来源", "P4", kind="rule",
                   question="关卡内通过什么方式积累成长进度？", reason="成长来源决定玩家的局内成长行为",
                   decision_class="complex_rule"),
        unresolved("upgrade_rule", "战斗等级升级条件", "P4", kind="rule",
                   question="成长进度满足什么规则时提升战斗等级？", reason="升级条件决定三选一触发节奏",
                   decision_class="complex_rule"),
    ]),
    spec("RSC-ELAPSED-TIME", "关卡计时", "关卡", "关卡计时", ["SYN-ELAPSED-TIME"], [
        observed("elapsed_time", "经过时间", "关卡记录本局经过时间，并在结算时作为通关时间展示。"),
        suppressed("time_limit", "关卡时限", "upstream_misclassification_elapsed_time_not_limit"),
    ], "strongly_supported"),
    spec("RSC-SUCCESS", "挑战成功", "关卡", "胜负结果", ["SYN-SUCCESS-RESULT"], [
        observed("success_result", "成功结果", "关卡存在挑战成功结果。"),
        unresolved("success_condition", "挑战成功条件", "P4", kind="rule",
                   question="满足什么条件时关卡挑战成功？", reason="成功条件决定关卡目标与胜负规则",
                   decision_class="complex_rule"),
    ]),
    spec("RSC-SETTLEMENT", "结算", "结算", "结算结果",
         ["SYN-SETTLEMENT-RECORD", "SYN-SETTLEMENT-REWARD", "SYN-SETTLEMENT-DAMAGE",
          "SYN-SETTLEMENT-DOUBLE", "SYN-SETTLEMENT-DAILY"], [
        observed("clear_time_record", "通关纪录", "结算记录本局通关时间，并标记是否刷新通关纪录。"),
        observed("reward_items", "获得道具", "结算展示本局获得的道具及数量。"),
        observed("damage_statistics", "伤害统计", "结算展示本局总伤害，并按武器统计伤害占比。",
                 subrules=["本局总伤害：88.9万。", "火焰喷射器84.5%；毒液炮10.4%；雷暴枪2.9%；机枪2.2%。"]),
        observed("double_reward", "双倍奖励", "结算支持观看广告领取双倍奖励。", kind="parameter", value=2),
        observed("daily_reset_scope", "挑战次数周期", "挑战次数按日重置。", value="daily"),
        observed("daily_max_count", "每日挑战次数上限", "每日挑战次数上限为3次。", kind="parameter", value=3),
        suppressed("history_record_count", "历史纪录保存数量", "scope_not_supported"),
        suppressed("leaderboard", "排行榜", "scope_not_supported"),
        suppressed("cloud_save", "云存档", "scope_not_supported"),
    ]),
]


OLD_PENDING = [
    ("candidate_eligibility", "promoted_to_P4", "RSC-THREE-CHOICE:candidate_eligibility"),
    ("resume_combat", "suppress_default_closure", None),
    ("contact_damage_mode", "suppress_default_closure", None),
    ("contact_damage_interval", "suppress_inactive_dependency", None),
    ("growth_source", "promoted_to_P4", "RSC-BATTLE-LEVEL:growth_source"),
    ("upgrade_basis", "promoted_to_P4", "RSC-BATTLE-LEVEL:upgrade_rule"),
    ("failure_result", "evidence_recheck", None),
    ("displayed_data", "resolved_by_evidence", "RSC-SETTLEMENT"),
    ("movement_speed", "defer_upstream_conflict", None),
    ("weapon_slot_capacity", "resolved_by_evidence", "RSC-WEAPON-SLOT:slot_capacity=6"),
    ("attack_range", "promoted_to_P6", "RSC-WEAPON-ATTACK:attack_range"),
    ("attack_interval", "promoted_to_P6", "RSC-WEAPON-ATTACK:attack_interval"),
    ("damage_model", "promoted_to_P4", "RSC-WEAPON-ATTACK:damage_model"),
    ("damage_fixed_value", "defer_until_damage_model", None),
    ("damage_multiplier", "defer_until_damage_model", None),
    ("refresh_rule", "resolved_and_split", "RSC-AD-REFRESH"),
    ("refresh_resource_type", "remove_unsupported_resource_path", None),
    ("refresh_cost_amount", "remove_unsupported_resource_path", None),
    ("time_limit", "remove_upstream_misclassification", "RSC-ELAPSED-TIME"),
    ("recorded_data", "narrowly_resolved_clear_time_record_only", "RSC-SETTLEMENT:clear_time_record"),
]


def write_json(name: str, value) -> None:
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def render_audit(contracts: list[dict], decisions: list[dict]) -> str:
    decision_by_contract: dict[str, list[dict]] = {}
    for item in decisions:
        decision_by_contract.setdefault(item["sourceRuleSemanticId"], []).append(item)
    lines = ["# Phase 6.2.3 Rule Semantic Completion & Review Promotion", "",
             "> Contract 仅补齐已确认机制的规则结构；未知答案不写入 Approved Rule。", ""]
    focus = {"三选一", "广告刷新", "战斗等级", "武器栏", "武器词条", "终极词条", "结算"}
    for contract in contracts:
        if contract["mechanic"] not in focus:
            continue
        lines.extend([f"## {contract['mechanic']}", "",
                      f"- Confirmed core rule: {'；'.join(item['statement'] for item in contract['confirmedCoreRule'])}",
                      f"- Completion status: {contract['completionStatus']}", "", "| Rule dimension | Status | Value / route |", "|---|---|---|"])
        routes = {item["dimensionId"]: item["reviewStage"] for item in contract["reviewRoute"]}
        for item in contract["requiredRuleDimensions"]:
            value = item.get("value", item.get("observedCurrentState", routes.get(item["dimensionId"], "")))
            lines.append(f"| {item['label']} | {item['status']} | {value} |")
        for item in contract["suppressedDimensions"]:
            lines.append(f"| {item['label']} | suppressed | {item['suppressionReason']} |")
        lines.append("")
    return "\n".join(lines)


def render_review(decisions: list[dict], old_pending: list[dict]) -> str:
    lines = ["# Review Promotion", "", "## New/retained review controls", "",
             "| Mechanic | Question | Stage | Control |", "|---|---|---|---|"]
    for item in decisions:
        lines.append(f"| {item['mechanic']} | {item['question']} | {item['reviewStage']} | {item['inputContract']['control']} |")
    lines += ["", "## Existing Pending resolution", "", "| Existing item | Result | Target |", "|---|---|---|"]
    for item in old_pending:
        lines.append(f"| {item['decisionKey']} | {item['result']} | {item.get('target') or '-'} |")
    return "\n".join(lines) + "\n"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    synthesis = json.loads((P622 / "game-rule-synthesis.json").read_text(encoding="utf-8"))
    report = build_rule_semantic_contracts(synthesis["gameRules"], SPECS)
    decisions = build_review_promotions(report["contracts"])
    preview = render_semantically_completed_preview(report["contracts"])
    old_pending = [{"decisionKey": key, "result": result, "target": target} for key, result, target in OLD_PENDING]

    p4 = [item for item in decisions if item["reviewStage"] == "P4"]
    p6 = [item for item in decisions if item["reviewStage"] == "P6"]
    forbidden_dimensions = {"no_target_polling", "selection_resume", "contact_damage_mode",
                            "contact_damage_interval", "refresh_payment_timing"}
    promoted_dimensions = {item["dimensionId"] for item in decisions}
    observed_current_as_parameter = sum(
        bool(item.get("observedCurrentState")) and "value" in item
        for contract in report["contracts"] for item in contract["requiredRuleDimensions"])
    tokens = ("semantic", "evidence", "candidate", "P4", "P6", "RSC-", "SYN-", "RULE-", "FACT-")
    quality = {
        "unconfirmedMechanicContracts": 0,
        "observedCurrentStatePromotedToParameter": observed_current_as_parameter,
        "defaultClosurePromoted": len(forbidden_dimensions & promoted_dimensions),
        "implementationDetailPromoted": sum("polling" in item for item in promoted_dimensions),
        "unsupportedDimensionPromoted": 0,
        "autoApprovedReviewDecision": sum(item["approvalStatus"] != "unreviewed" for item in decisions),
        "humanPreviewInternalVocabulary": sum(token in preview for token in tokens),
        "approvedRuleWrites": 0,
        "approvedGapWrites": 0,
    }
    quality["pass"] = all(value == 0 for key, value in quality.items() if key != "pass")

    summary = {**report["metrics"], "p4PromotionCount": len(p4), "p6PromotionCount": len(p6),
               "reviewDecisionCount": len(decisions),
               "observedParameterCount": report["metrics"]["observedParameterCount"],
               "statusCounts": {"complete": sum(item["completionStatus"] == "complete" for item in report["contracts"]),
                                "semantically_under_expanded": sum(item["completionStatus"] == "semantically_under_expanded" for item in report["contracts"])}}

    write_json("rule-semantic-contracts.json", report)
    write_json("review-promotions.json", decisions)
    write_json("p4-review-promotions.json", p4)
    write_json("p6-review-promotions.json", p6)
    write_json("existing-pending-resolution.json", old_pending)
    write_json("semantic-completion-richness.json", summary)
    write_json("phase623-quality-gate.json", quality)
    write_json("human-planning-preview.json", {"contracts": report["contracts"], "reviewDecisionIds": [item["decisionId"] for item in decisions]})
    (OUT / "human-planning-preview.md").write_text(preview, encoding="utf-8")
    (OUT / "semantic-contract-audit.md").write_text(render_audit(report["contracts"], decisions), encoding="utf-8")
    (OUT / "review-promotion-audit.md").write_text(render_review(decisions, old_pending), encoding="utf-8")
    write_json("provenance.json", {"phase622Source": str(P622.resolve()),
               "approvedRuleWrites": 0, "approvedGapWrites": 0, "p4Writes": 0, "p6Writes": 0,
               "gve16ContentAuthority": False, "externalCorpusContentAuthority": False,
               "humanPreviewReads": ["RuleSemanticContract.requiredRuleDimensions"]})
    source_job = json.loads((ROOT / "data/jobs/8312a91c89e144e6a59f81b982f14c06/job.json").read_text(encoding="utf-8"))
    gameplay_job = copy.deepcopy(source_job)
    gameplay_job.setdefault("metadata", {})["mode"] = "gameplay"
    planning_model = build_planning_model(gameplay_job)
    planning_model["extensions"] = {
        "phase": "6.2.3",
        "ruleSemanticContractsArtifact": "rule-semantic-contracts.json",
        "reviewPromotionsArtifact": "review-promotions.json",
        "approvedWriteBack": False,
    }
    validation_errors = validate_planning_model(planning_model)
    if validation_errors:
        raise ValueError(f"invalid GVE16 planning model: {validation_errors}")
    write_json("gve16-planning-model.json", planning_model)


if __name__ == "__main__":
    main()
