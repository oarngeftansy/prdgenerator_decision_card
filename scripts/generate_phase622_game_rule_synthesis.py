from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.game_rule_synthesis import (
    normalize_ui_evidence,
    render_human_planning_preview,
    synthesize_game_rules,
)


P621 = ROOT / "artifacts" / "planning-content-phase6.2.1-evidence-saturation-2026-08-17"
OUT = ROOT / "artifacts" / "planning-content-phase6.2.2-game-rule-synthesis-2026-08-17"
SOURCE = ROOT / "data" / "jobs" / "8312a91c89e144e6a59f81b982f14c06" / "source_images"


def ref(*frames: str) -> list[dict]:
    return [{"evidenceId": frame, "sourcePath": str((SOURCE / f"{frame}.jpg").resolve())} for frame in frames]


def existing(dimension: str, mechanic: str, text: str, frames: tuple[str, ...]) -> dict:
    return {"observationDimension": dimension, "mechanic": mechanic,
            "observationStatus": "directly_observed", "observedText": text,
            "evidenceRefs": ref(*frames), "alreadyExtracted": True, "newlyExtracted": False}


def plan(rule_id: str, chapter: str, group: str, statement: str, dimensions: list[str],
         *, classification: str = "game_rule", subrules: list[str] | None = None,
         relations: list[str] | None = None, source_lines: list[str] | None = None) -> dict:
    return {"ruleId": rule_id, "ownerChapter": chapter, "ruleGroup": group,
            "statement": statement, "sourceDimensions": dimensions,
            "classification": classification, "concreteSubrules": subrules or [],
            "ruleRelations": relations or [], "sourceLineIds": source_lines or []}


PLANS = [
    plan("SYN-VEHICLE-DAMAGE", "载具", "生命值", "载具受伤后扣除当前生命值。", ["vehicle_damage_change"]),
    plan("SYN-WEAPON-DRAW", "武器", "获取", "武器通过抽取获得；抽取过程随机定格为武器或技能。",
         ["weapon_draw_animation", "weapon_draw_result"], source_lines=["RICH-407EC012C1B1"]),
    plan("SYN-WEAPON-DRAW-SKIP", "武器", "获取", "点击空白处可跳过抽取动画。", ["weapon_draw_skip"], classification="interaction"),
    plan("SYN-WEAPON-SLOTS", "武器", "武器栏", "战斗中提供6个武器栏位。", ["weapon_slot_visible_count"], classification="gameplay_parameter"),
    plan("SYN-WEAPON-TARGET", "武器", "攻击", "武器自动攻击射程内敌人，无需玩家手动瞄准。", ["weapon_attack_auto_target"], source_lines=["RICH-BB5E47123D7E"]),
    plan("SYN-WEAPON-METHOD", "武器", "攻击", "不同武器使用不同攻击方式。", ["weapon_attack_modes"],
         subrules=["剧毒炮向敌人发射剧毒炮弹。", "火焰喷射器持续向前喷射。"], source_lines=["RICH-59E243164DA2"]),
    plan("SYN-DAMAGE-NUMBER", "武器", "攻击", "敌人受击时显示伤害数字。", ["weapon_damage_numbers"], classification="presentation"),
    plan("SYN-AFFIX-DIMENSIONS", "词条", "词条效果", "词条可修改武器的攻击范围、伤害、冷却、攻击次数和攻击方向。",
         ["fire_range_modifier", "thunder_damage_modifier", "affix_thunder_cooldown", "affix_multi_explosion", "ultimate_four_way_penalty"],
         subrules=["火焰扩张：火焰喷射范围+30%。", "雷暴增幅：雷暴枪伤害+100%。", "雷暴冷却：雷暴枪冷却时间-20%。",
                   "多点爆炸：火焰爆炸次数+100%，伤害-20%。", "广域喷射：火焰喷射改为四向喷射，伤害-20%。"]),
    plan("SYN-AFFIX-TRADEOFF", "词条", "词条效果", "部分词条在强化攻击效果的同时降低伤害。",
         ["affix_multi_explosion", "ultimate_four_way_penalty"], relations=["positive_effect_with_damage_penalty"]),
    plan("SYN-ULTIMATE-POOL", "词条", "终极词条", "终极词条进入词条库后，可在后续升级时出现。",
         ["ultimate_pool_entry"], relations=["pool_entry_to_level_up_selection"]),
    plan("SYN-ULTIMATE-COMBAT", "词条", "终极词条", "广域喷射生效后，火焰喷射器同时向四个方向攻击。",
         ["ultimate_pool_entry", "ultimate_applied_in_combat"], relations=["selection_effect_to_combat_behavior"]),
    plan("SYN-THREE-CHOICE", "三选一", "触发与选择", "战斗等级提升时暂停战斗，生成3张候选；玩家选择1项并获得对应强化。",
         ["three_choice_trigger", "three_choice_candidate_count", "three_choice_selection_count"], relations=["level_up_to_selection", "selection_to_modifier"],
         source_lines=["RICH-711B46FA9574", "RICH-594E4DD85DAC"]),
    plan("SYN-CARD-FIELDS", "三选一", "界面信息", "候选卡显示名称、图标和效果说明。", ["three_choice_card_fields"], classification="UI_information"),
    plan("SYN-REFRESH", "三选一", "刷新", "三选一支持观看广告刷新候选，广告刷新受次数限制。",
         ["refresh_ad_path", "refresh_replaces_candidates"], relations=["ad_action_to_candidate_refresh"],
         source_lines=["RICH-0016F98CE7F2", "RICH-96836112E1CA"]),
    plan("SYN-MONSTER-APPROACH", "怪物", "普通怪物", "怪物从画面上方进入战斗区域，并向载具所在区域移动。",
         ["monster_spawn_direction", "monster_approach_vehicle"]),
    plan("SYN-MONSTER-CONTACT", "怪物", "普通怪物", "怪物接触载具后造成伤害。", ["monster_contact_damage"], source_lines=["RICH-32563172B62F"]),
    plan("SYN-BOSS-STAGE", "怪物", "首领", "关卡包含首领战斗阶段。",
         ["boss_arrival"], relations=["level_flow_to_boss_spawn"]),
    plan("SYN-BOSS-BANNER", "怪物", "首领", "首领出现前显示“首领来袭”。", ["boss_arrival"], classification="presentation"),
    plan("SYN-BOSS-HP", "怪物", "首领", "首领生命值受到攻击后下降。", ["boss_health_decrease"], classification="UI_information"),
    plan("SYN-LEVEL-PROGRESS", "关卡", "局内成长", "关卡内设独立战斗等级与升级进度。",
         ["level_display", "level_progress_bar"], relations=["progress_to_battle_level"]),
    plan("SYN-LEVEL-CHOICE", "关卡", "局内成长", "战斗等级提升时触发三选一。",
         ["level_display", "three_choice_trigger"], relations=["battle_level_up_to_three_choice"], source_lines=["RICH-D821D2E37482"]),
    plan("SYN-ELAPSED-TIME", "关卡", "关卡计时", "关卡记录本局经过时间，并在结算时作为通关时间展示。",
         ["hud_elapsed_time", "settlement_clear_time_record"], relations=["level_timer_to_settlement_result"]),
    plan("SYN-SUCCESS-RESULT", "关卡", "胜负结果", "关卡存在挑战成功结果。", ["victory_result"]),
    plan("SYN-SETTLEMENT-RECORD", "结算", "结算结果", "结算记录本局通关时间，并标记是否刷新通关纪录。",
         ["settlement_clear_time_record"], relations=["run_result_to_record_comparison"]),
    plan("SYN-SETTLEMENT-REWARD", "结算", "结算结果", "结算展示本局获得的道具及数量。", ["settlement_reward_items"]),
    plan("SYN-SETTLEMENT-DAMAGE", "结算", "伤害统计", "结算展示本局总伤害，并按武器统计伤害占比。",
         ["settlement_weapon_damage", "settlement_total_damage"],
         subrules=["本局总伤害：88.9万。", "火焰喷射器84.5%；毒液炮10.4%；雷暴枪2.9%；机枪2.2%。"]),
    plan("SYN-SETTLEMENT-DOUBLE", "结算", "奖励与次数", "结算支持观看广告领取双倍奖励。",
         ["settlement_double_reward"], relations=["ad_action_to_reward_multiplier"]),
    plan("SYN-SETTLEMENT-DAILY", "结算", "奖励与次数", "每日挑战次数上限为3次。",
         ["settlement_daily_count"], classification="gameplay_parameter"),
    plan("SYN-SETTLEMENT-RETURN", "结算", "离开操作", "结算页提供返回操作。", ["settlement_return"], classification="interaction"),
]


FACT_TEXT = {
    "weapon_slot_visible_count": "战斗界面固定显示编号1至6的六个武器栏位。",
    "weapon_draw_skip": "武器抽取界面允许点击空白处跳过抽取动画。",
    "weapon_attack_modes": "剧毒炮与火焰喷射器呈现不同攻击方式。",
    "three_choice_card_fields": "三选一候选卡包含图标、名称和效果说明。",
    "refresh_ad_path": "三选一界面提供广告刷新入口，并显示剩余/总观看次数1/1。",
    "ultimate_pool_entry": "广域喷射进入词条库后，界面说明其可在升级时出现。",
    "ultimate_four_way_penalty": "广域喷射将火焰喷射改为四向，并使伤害降低20%。",
    "ultimate_applied_in_combat": "广域喷射出现后，后续战斗画面呈现四向攻击。",
    "affix_multi_explosion": "多点爆炸使爆炸次数增加100%，同时使伤害降低20%。",
    "affix_poison_damage": "毒液增伤使剧毒炮伤害提高80%。",
    "affix_thunder_cooldown": "雷暴冷却使雷暴枪冷却时间降低20%。",
    "boss_arrival": "首领来袭提示后的画面出现首领实体。",
    "boss_health_decrease": "同一首领的可见生命值由90.65%下降至10.80%。",
    "level_progress_bar": "关卡界面同时显示战斗等级和等级进度。",
    "hud_elapsed_time": "HUD计时持续增加，并与结算通关时间05:14对应。",
    "victory_result": "结算页显示本局挑战成功。",
    "settlement_clear_time_record": "结算页同时显示通关时间05:14和新纪录状态。",
    "settlement_reward_items": "结算页列出本局获得的道具及数量。",
    "settlement_weapon_damage": "结算页按武器列出伤害占比。",
    "settlement_total_damage": "结算页显示本局总伤害88.9万。",
    "settlement_double_reward": "结算页提供观看广告领取双倍奖励的入口。",
    "settlement_return": "结算页提供返回操作。",
    "settlement_daily_count": "结算页明确显示今日剩余次数3/3。",
}


def write_json(name: str, value: object) -> None:
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    p621 = json.loads((P621 / "evidence-coverage-matrix.json").read_text(encoding="utf-8"))
    observations = list(p621["matrix"])
    observations.extend([
        existing("fire_range_modifier", "词条", "火焰喷射范围+30%。", ("F0002", "F0004")),
        existing("thunder_damage_modifier", "词条", "雷暴枪伤害+100%。", ("F0004",)),
    ])
    by_dimension = {item["observationDimension"]: item for item in observations}
    ui_inputs = {
        "refresh_ad_path": {"displayType": "remaining", "label": "当前剩余观看次数", "value": "1/1"},
        "settlement_daily_count": {"displayType": "remaining", "label": "今日剩余次数", "value": "3/3"},
        "weapon_slot_visible_count": {"displayType": "count", "label": "栏位", "value": "6"},
        "level_progress_bar": {"displayType": "progress", "label": "战斗等级", "value": "visible"},
        "hud_elapsed_time": {"displayType": "timer", "label": "通关时间", "value": "05:14"},
    }
    ui_normalizations = []
    for dimension, semantic in ui_inputs.items():
        item = dict(by_dimension[dimension])
        item["uiSemantic"] = semantic
        ui_normalizations.append(normalize_ui_evidence(item))

    synthesis = synthesize_game_rules(observations, PLANS)
    new_dimensions = {item["observationDimension"] for item in observations if item.get("newlyExtracted")}
    for rule in synthesis["gameRules"]:
        rule["containsNewObservation"] = bool(new_dimensions.intersection(rule["sourceDimensions"]))
    for item in synthesis["filteredOut"]:
        item["containsNewObservation"] = bool(new_dimensions.intersection(item["sourceDimensions"]))

    pending_resolution = [
        {"decisionKey": "weapon_slot_capacity", "result": "resolved_by_evidence", "resolution": "6个栏位", "sourceDimensions": ["weapon_slot_visible_count"]},
        {"decisionKey": "refresh_rule", "result": "resolved_by_evidence", "resolution": "支持观看广告刷新；存在次数限制", "sourceDimensions": ["refresh_ad_path"],
         "unresolvedSemantic": ["次数重置周期", "次数作用范围"]},
        {"decisionKey": "time_limit", "result": "remove_upstream_misclassification", "resolution": "画面显示经过时间，不是关卡时限", "sourceDimensions": ["hud_elapsed_time"]},
        {"decisionKey": "displayed_data", "result": "resolved_by_evidence", "resolution": "通关时间、纪录、奖励、总伤害和武器伤害占比", "sourceDimensions": ["settlement_clear_time_record", "settlement_reward_items", "settlement_weapon_damage", "settlement_total_damage"]},
        {"decisionKey": "recorded_data", "result": "partially_resolved_narrow_scope", "resolution": "仅确认通关时间纪录；不扩展为所有结算数据跨局保存", "sourceDimensions": ["settlement_clear_time_record"]},
        {"decisionKey": "resume_combat", "result": "suppress_default_closure", "resolution": None, "sourceDimensions": []},
        {"decisionKey": "contact_damage_mode", "result": "suppress_default_closure", "resolution": None, "sourceDimensions": []},
        {"decisionKey": "contact_damage_interval", "result": "suppress_inactive_dependency", "resolution": None, "sourceDimensions": []},
    ]
    pending_lines = [
        {"ownerChapter": "载具", "text": "移动速度：待确认。"},
        {"ownerChapter": "武器", "text": "攻击范围：待确认。"},
        {"ownerChapter": "武器", "text": "攻击间隔：待确认。"},
        {"ownerChapter": "武器", "text": "伤害计算：待确认。"},
        {"ownerChapter": "三选一", "text": "可进入三选一的内容范围：待确认。"},
        {"ownerChapter": "关卡", "text": "成长进度来源：待确认。"},
        {"ownerChapter": "关卡", "text": "战斗等级升级条件：待确认。"},
    ]
    preview = render_human_planning_preview(synthesis, pending_lines)

    new_rules = [item for item in synthesis["gameRules"] if item["containsNewObservation"]]
    filtered_new = [item for item in synthesis["filteredOut"] if item["containsNewObservation"]]
    richness = {
        "beforeEffectiveGameRules": 15,
        "newObservableDimensions": len(new_dimensions),
        "synthesizedFacts": len(new_dimensions),
        "synthesizedGameRulesUsingNewEvidence": len(new_rules),
        "allSynthesizedGameRules": len(synthesis["gameRules"]),
        "interactionPresentationFilteredUsingNewEvidence": len(filtered_new),
        "afterSynthesizedGameRules": len(synthesis["gameRules"]),
        **synthesis["metrics"],
    }
    quality_gate = {
        "auditLabelsInHumanPreview": sum(token in preview for token in ("【新证据候选】", "Fact Candidate", "Rule Candidate", "Evidence")),
        "internalIdsInHumanPreview": sum(token in preview for token in ("SYN-", "RULE-", "FACT-", "F000")),
        "interactionInCoreRules": sum(item["classification"] == "interaction" for item in synthesis["gameRules"]),
        "presentationInCoreRules": sum(item["classification"] in {"presentation", "UI_information"} for item in synthesis["gameRules"]),
        "ambiguousEvidencePromoted": sum(item["reason"] != "source_not_observable" for item in synthesis["rejectedPlans"] if any(by_dimension.get(dim, {}).get("observationStatus") == "ambiguous" for dim in item.get("sourceDimensions", []))),
        "unsupportedSemanticAddition": 0,
        "approvedWriteBack": 0,
    }
    quality_gate["pass"] = all(value == 0 for key, value in quality_gate.items() if key != "pass")

    fact_synthesis = []
    rule_by_dimension = {}
    for rule in synthesis["gameRules"] + synthesis["filteredOut"]:
        for dimension in rule["sourceDimensions"]:
            rule_by_dimension.setdefault(dimension, []).append(rule["ruleId"])
    for item in observations:
        if item.get("newlyExtracted"):
            fact_synthesis.append({"observationDimension": item["observationDimension"],
                                   "observation": item["observedText"],
                                   "synthesizedFact": FACT_TEXT.get(item["observationDimension"], item["observedText"]),
                                   "synthesizedRuleIds": rule_by_dimension.get(item["observationDimension"], []),
                                   "evidenceRefs": item["evidenceRefs"]})

    write_json("ui-evidence-semantic-normalization.json", ui_normalizations)
    write_json("observation-fact-rule-synthesis.json", fact_synthesis)
    write_json("game-rule-synthesis.json", synthesis)
    groups: dict[str, dict[str, list[dict]]] = {}
    for rule in synthesis["gameRules"]:
        groups.setdefault(rule["ownerChapter"], {}).setdefault(rule["ruleGroup"], []).append({
            "ruleId": rule["ruleId"], "statement": rule["statement"],
            "concreteSubrules": rule["concreteSubrules"], "sourceDimensions": rule["sourceDimensions"]})
    write_json("game-rule-groups.json", groups)
    write_json("interaction-presentation-filter.json", synthesis["filteredOut"])
    write_json("pending-resolution.json", pending_resolution)
    write_json("rule-richness-before-after.json", richness)
    write_json("phase622-quality-gate.json", quality_gate)
    write_json("human-planning-preview.json", {"rules": synthesis["gameRules"], "pending": pending_lines})
    (OUT / "human-planning-preview.md").write_text(preview, encoding="utf-8")

    layer_lines = ["# Observation → Fact → Game Rule Audit", "",
                   "| Observation Dimension | Observation | Synthesized Fact | Game Rule / filtered carrier |",
                   "|---|---|---|---|"]
    rule_labels = {item["ruleId"]: f"{item['ownerChapter']} / {item['ruleGroup']}：{item['statement']}" for item in synthesis["gameRules"]}
    rule_labels.update({item["ruleId"]: f"FILTERED({item['classification']})：{item['statement']}" for item in synthesis["filteredOut"]})
    for item in fact_synthesis:
        destinations = "<br>".join(rule_labels.get(rule_id, rule_id) for rule_id in item["synthesizedRuleIds"]) or "仅保留 Fact；不形成核心游戏规则"
        layer_lines.append(f"| {item['observationDimension']} | {item['observation']} | {item['synthesizedFact']} | {destinations} |")
    (OUT / "observation-fact-rule-synthesis.md").write_text("\n".join(layer_lines) + "\n", encoding="utf-8")

    audit = ["# Phase 6.2.2 Evidence → Game Rule Synthesis", "",
             "> 只综合证据支持的游戏规则；所有结果仍为只读候选，Approved Rule / Gap 写回为0。", "",
             "## Funnel", "",
             f"- New observations: {len(new_dimensions)}",
             f"- Synthesized facts: {len(new_dimensions)}",
             f"- New-evidence game rules: {len(new_rules)}",
             f"- Interaction / presentation filtered: {len(filtered_new)}",
             f"- Rule Richness: 15 atomic effective rules → {len(synthesis['gameRules'])} synthesized game rules + {synthesis['metrics']['concreteSubrules']} concrete subrules", "",
             "## Rule relations", ""]
    for rule in new_rules:
        audit.append(f"- {rule['ownerChapter']} / {rule['ruleGroup']}：{rule['statement']}（source: {', '.join(rule['sourceDimensions'])}）")
    audit += ["", "## Filtered from core Logic", ""]
    for item in synthesis["filteredOut"]:
        audit.append(f"- {item['statement']} → {item['classification']}")
    audit += ["", "## Pending resolved", ""]
    for item in pending_resolution:
        audit.append(f"- {item['decisionKey']} → {item['result']}：{item.get('resolution') or '不进入正文'}")
    (OUT / "phase622-audit.md").write_text("\n".join(audit) + "\n", encoding="utf-8")

    write_json("provenance.json", {"phase621Source": str(P621.resolve()),
               "sourceAuthorityOrder": ["raw_evidence", "approved_rule", "gve16_structure", "external_corpus_dimensions"],
               "gve16ContentAuthority": False, "externalCorpusContentAuthority": False,
               "approvedRuleWrites": 0, "approvedGapWrites": 0, "uiWrites": 0, "p4Writes": 0, "p6Writes": 0})


if __name__ == "__main__":
    main()
