from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from typing import Any

from backend.document_density_review_state_rendering import evaluate_document_density_gate


_TOPIC_CHAPTER = {
    "移动规则": "载具移动", "攻击规则": "武器攻击", "成长与词条": "词条",
    "选择结果": "词条", "可获取词条": "三选一", "触发与选择": "三选一",
    "刷新": "刷新", "接触伤害": "怪物攻击", "关卡推进": "关卡流程",
    "胜负衔接": "胜负判定", "结算结果": "结算", "数据记录": "结算",
}

_PENDING_LABELS = {
    "candidate_eligibility": "可获取词条范围", "growth_source": "成长规则",
    "upgrade_basis": "成长规则", "damage_model": "伤害计算", "refresh_rule": "刷新规则",
    "contact_damage_mode": "接触伤害方式", "movement_speed": "移动速度",
    "weapon_slot_capacity": "武器栏容量", "attack_range": "攻击范围",
    "attack_interval": "攻击间隔", "time_limit": "关卡时限",
}


def _id(chapter: str, semantic: str, state: str) -> str:
    digest = hashlib.sha1(f"{chapter}:{semantic}:{state}".encode("utf-8")).hexdigest()[:12].upper()
    return f"RICH-{digest}"


def _chapter_for(topic: str, decision_key: str | None = None, has_detail: bool = False) -> str | None:
    if topic == "获取与栏位":
        return "武器栏" if decision_key == "weapon_slot_capacity" or not has_detail else "武器获取"
    return _TOPIC_CHAPTER.get(topic)


def _line(chapter: str, semantic: str, text: str, *, state: str = "approved",
          rule_ids: list[str] | None = None, detail_ids: list[str] | None = None,
          decision_ids: list[str] | None = None, decision_keys: list[str] | None = None,
          source_text: str = "") -> dict[str, Any]:
    return {"lineId": _id(chapter, semantic, state), "semantic": semantic, "text": text,
            "state": state, "supportingRuleIds": rule_ids or [],
            "sourceDetailIds": detail_ids or [], "sourceDecisionIds": decision_ids or [],
            "sourceDecisionKeys": decision_keys or [],
            "sourceText": source_text}


def _render_confirmed(topic: str, details: list[dict[str, Any]]) -> list[dict[str, Any]]:
    texts = [item["text"] for item in details]
    all_rules = list(dict.fromkeys(rule for item in details for rule in item.get("sourceRuleIds", [])))
    all_ids = [item["detailId"] for item in details]
    source = "；".join(texts)
    if topic == "移动规则":
        return [_line("载具移动", "lateral_control", "使用虚拟摇杆或按键横向微调载具。",
                      rule_ids=all_rules, detail_ids=all_ids, source_text=source)]
    if topic == "获取与栏位":
        return [_line("武器获取", "weapon_acquisition", "武器抽取滚动结束后随机定格，获得武器或技能。",
                      rule_ids=all_rules, detail_ids=all_ids, source_text=source)] if details else []
    if topic == "攻击规则":
        result = []
        targeting = [item for item in details if "瞄准" in item["text"] or "攻击目标" in item["text"]]
        method = [item for item in details if "投射物" in item["text"] or "伤害区域" in item["text"]]
        if targeting:
            result.append(_line("武器攻击", "automatic_targeting", "武器自动攻击射程内敌人，无需玩家手动瞄准。",
                rule_ids=list(dict.fromkeys(r for x in targeting for r in x.get("sourceRuleIds", []))),
                detail_ids=[x["detailId"] for x in targeting], source_text="；".join(x["text"] for x in targeting)))
        if method:
            result.append(_line("武器攻击", "attack_method", "武器攻击时，向目标发射投射物或生成持续伤害区域。",
                rule_ids=list(dict.fromkeys(r for x in method for r in x.get("sourceRuleIds", []))),
                detail_ids=[x["detailId"] for x in method], source_text="；".join(x["text"] for x in method)))
        return result
    if topic in {"成长与词条", "选择结果"}:
        result = []
        generic = [item for item in details if not any(token in item["text"] for token in ("30%", "100%", "四"))]
        generic_rules = [rule for item in generic for rule in item.get("sourceRuleIds", [])]
        generic_ids = [item["detailId"] for item in generic]
        for item in details:
            text = item["text"]
            if "30%" in text:
                rendered, semantic = "火焰喷射：攻击范围+30%。", "fire_range"
            elif "100%" in text:
                rendered, semantic = "雷暴枪：伤害+100%。", "thunder_damage"
            elif "四" in text and "方向" in text:
                rendered, semantic = "终极词条：喷射方向由单方向改为四向。", "ultimate_direction"
            else:
                continue  # The generic modifier summary is represented by the concrete effects.
            result.append(_line("词条", semantic, rendered,
                rule_ids=list(dict.fromkeys(item.get("sourceRuleIds", []) + generic_rules)),
                detail_ids=list(dict.fromkeys([item["detailId"]] + generic_ids)), source_text=text))
        return result
    if topic == "触发与选择":
        trigger = [item for item in details if "触发" in item["text"] or "暂停" in item["text"]]
        choice = [item for item in details if "选择" in item["text"]]
        result = []
        if trigger:
            result.append(_line("三选一", "three_choice_trigger",
                "战斗等级提升时暂停战斗，并生成3张候选。",
                rule_ids=list(dict.fromkeys(r for x in trigger for r in x.get("sourceRuleIds", []))),
                detail_ids=[x["detailId"] for x in trigger], source_text="；".join(x["text"] for x in trigger)))
        if choice:
            result.append(_line("三选一", "three_choice_selection", "玩家从3项中选择1项，获得对应强化。",
                rule_ids=list(dict.fromkeys(r for x in choice for r in x.get("sourceRuleIds", []))),
                detail_ids=[x["detailId"] for x in choice], source_text="；".join(x["text"] for x in choice)))
        return result
    if topic == "刷新":
        relevant = [item for item in details if "点击" in item["text"] or "替换" in item["text"]]
        return [_line("刷新", "refresh_candidates", "点击刷新后替换当前3项候选。",
            rule_ids=list(dict.fromkeys(r for x in relevant for r in x.get("sourceRuleIds", []))),
            detail_ids=[x["detailId"] for x in relevant], source_text="；".join(x["text"] for x in relevant))] if relevant else []
    if topic == "接触伤害":
        return [_line("怪物攻击", "contact_damage", "怪物接触载具后造成伤害。",
                      rule_ids=all_rules, detail_ids=all_ids, source_text=source)] if details else []
    if topic == "胜负衔接":
        return [_line("胜负判定", "vehicle_zero_hp_failure", "载具生命值归零时关卡失败。",
                      rule_ids=all_rules, detail_ids=all_ids, source_text=source)] if details else []
    return []


def build_content_richness_preview(expansion_plans: list[dict[str, Any]],
                                   review_decisions: list[dict[str, Any]],
                                   parameter_placements: list[dict[str, Any]],
                                   human_chapters: list[dict[str, Any]],
                                   scope_corrections: list[dict[str, Any]]) -> dict[str, Any]:
    del parameter_placements, scope_corrections
    chapters: dict[str, dict[str, Any]] = {}

    def add(chapter_title: str, item: dict[str, Any]) -> None:
        chapter = chapters.setdefault(chapter_title, {"chapterTitle": chapter_title, "lines": [], "sourceLayoutIds": []})
        if not any(line["semantic"] == item["semantic"] and line["text"] == item["text"] for line in chapter["lines"]):
            chapter["lines"].append(item)

    for plan in expansion_plans:
        title = _chapter_for(plan["ruleTopic"], has_detail=bool(plan.get("confirmedDetails")))
        if title:
            chapter = chapters.setdefault(title, {"chapterTitle": title, "lines": [], "sourceLayoutIds": []})
            chapter["sourceLayoutIds"].append(plan["layoutId"])
        for item in _render_confirmed(plan["ruleTopic"], plan.get("confirmedDetails", [])):
            add(item["text"] and _chapter_for(plan["ruleTopic"], has_detail=True) or title, item)

    # Contextual relations are already ownership-audited in Phase 6.1.1.
    allowed_human_semantics = {"level_up_to_three_choice", "affix_changes_attack", "vehicle_zero_hp_failure"}
    for chapter in human_chapters:
        title = chapter["chapterTitle"]
        if title not in {"关卡流程", "武器攻击", "胜负判定"}:
            continue
        for statement in chapter.get("statements", []):
            if statement.get("semantic") not in allowed_human_semantics:
                continue
            add(title, _line(title, statement["semantic"], statement["text"],
                rule_ids=statement.get("supportingRuleIds", []), source_text=statement["text"]))

    rendered_pending: set[tuple[str, str]] = set()
    for decision in review_decisions:
        if decision.get("route") not in {"P4", "P6"} or decision.get("approvalStatus") == "approved":
            continue
        if decision.get("route") == "P6" and decision.get("dependency"):
            continue
        key = decision.get("decisionKey", "")
        label = _PENDING_LABELS.get(key)
        title = _chapter_for(decision.get("ruleTopic", ""), key)
        if not label or not title:
            continue
        if (title, label) in rendered_pending:
            existing = next(line for line in chapters[title]["lines"] if line["text"] == f"{label}：待确认。")
            existing["sourceDecisionIds"].append(decision["decisionId"])
            existing["sourceDecisionKeys"].append(key)
            continue
        rendered_pending.add((title, label))
        support_rules: list[str] = []
        support_details: list[str] = []
        if key == "refresh_rule":
            for plan in expansion_plans:
                if plan.get("ownerChapter") == decision.get("ownerChapter") and plan.get("ruleTopic") == "刷新":
                    for detail in plan.get("confirmedDetails", []):
                        if "消耗或替代" in detail.get("text", ""):
                            support_rules += detail.get("sourceRuleIds", [])
                            support_details.append(detail["detailId"])
        add(title, _line(title, key, f"{label}：待确认。",
            state="p4_pending" if decision["route"] == "P4" else "p6_pending",
            rule_ids=list(dict.fromkeys(support_rules)), detail_ids=support_details,
            decision_ids=[decision["decisionId"]], decision_keys=[key]))

    # Fixed natural reading order. Empty evidence-only chapters are omitted.
    order = ["载具移动", "武器获取", "武器栏", "武器攻击", "词条", "三选一", "刷新",
             "怪物攻击", "关卡流程", "胜负判定", "结算"]
    rendered = [chapters[title] for title in order if title in chapters and chapters[title]["lines"]]
    omitted = []
    if not any(item["chapterTitle"] == "结算" for item in rendered) and any(
            plan["ruleTopic"] in {"结算结果", "数据记录"} for plan in expansion_plans):
        omitted.append({"chapterTitle": "结算", "reason": "evidence_recheck_or_scope_unsupported"})
    return {"chapters": rendered, "omittedChapters": omitted}


def evaluate_content_richness(preview: dict[str, Any], expansion_plans: list[dict[str, Any]],
                              review_decisions: list[dict[str, Any]],
                              scope_corrections: list[dict[str, Any]]) -> dict[str, Any]:
    by_title = {item["chapterTitle"]: item for item in preview["chapters"]}
    plan_by_title: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for plan in expansion_plans:
        title = _chapter_for(plan["ruleTopic"], has_detail=bool(plan.get("confirmedDetails")))
        if title:
            plan_by_title[title].append(plan)
        if plan["ruleTopic"] == "获取与栏位":
            plan_by_title["武器栏"].append(plan)
    decisions_by_title: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for decision in review_decisions:
        title = _chapter_for(decision.get("ruleTopic", ""), decision.get("decisionKey"))
        if title:
            decisions_by_title[title].append(decision)

    chapter_reports = []
    all_titles = list(dict.fromkeys(list(by_title) + list(plan_by_title)))
    for title in all_titles:
        chapter = by_title.get(title, {"lines": []})
        lines = chapter["lines"]
        plans = plan_by_title.get(title, [])
        decisions = decisions_by_title.get(title, [])
        rendered_details = {detail for line in lines for detail in line.get("sourceDetailIds", [])}
        rendered_decisions = {decision for line in lines for decision in line.get("sourceDecisionIds", [])}
        supported_missing = [item for plan in plans for item in plan.get("missingExecutionDetails", [])
                             if item.get("scopeStatus") in {"confirmed", "strongly_implied"}]
        active_params = [item for plan in plans for item in plan.get("gameplayParameters", [])
                         if item.get("applicability") == "active"]
        actionable_decisions = [item for item in decisions if item.get("route") in {"P4", "P6"}
                                and not (item.get("route") == "P6" and item.get("dependency"))]
        not_rendered = []
        if title != "武器栏":  # The shared source layout's confirmed acquisition rule belongs to 武器获取.
            for plan in plans:
                for item in plan.get("confirmedDetails", []):
                    if item.get("detailId") not in rendered_details:
                        not_rendered.append(f"confirmed:{item.get('detailId')}")
        for item in supported_missing:
            source_ids = set(item.get("sourceMissingIds", []))
            matching = [d for d in actionable_decisions if d.get("sourceMissingId") in source_ids or
                        d.get("decisionKey") == item.get("semantic") or
                        (item.get("semantic") == "damage_resolution" and d.get("decisionKey") == "damage_model") or
                        (item.get("semantic") == "growth_accumulation" and d.get("decisionKey") in {"growth_source", "upgrade_basis"}) or
                        (item.get("semantic") == "refresh_cost_or_condition" and d.get("decisionKey") == "refresh_rule")]
            if matching and not any(d["decisionId"] in rendered_decisions for d in matching):
                not_rendered.append(item["semantic"])
        for item in active_params:
            matching = [d for d in actionable_decisions if d.get("decisionKey") == item.get("semantic")]
            if matching and not any(d["decisionId"] in rendered_decisions for d in matching):
                not_rendered.append(item["semantic"])
        rejected = [item.get("candidateDimension") for plan in plans for item in plan.get("stopReasons", [])]
        rejected += [item.get("scopeItem") for item in scope_corrections
                     if item.get("chapterId") in {plan.get("ownerChapter") for plan in plans}]
        confirmed_rules = {rule for line in lines for rule in line.get("supportingRuleIds", [])}
        pending_lines = [line for line in lines if line.get("state") in {"p4_pending", "p6_pending"}]
        report = {"chapterTitle": title, "confirmedRuleCount": len(confirmed_rules),
            "approvedReviewRuleCount": sum(1 for item in decisions if item.get("approvalStatus") == "approved"),
            "pendingRuleDimensionCount": sum(len(line.get("sourceDecisionKeys") or [line["semantic"]])
                                             for line in pending_lines if line["state"] == "p4_pending"),
            "gameplayParameterCount": sum(1 for line in pending_lines if line["state"] == "p6_pending"),
            "crossSystemRelationCount": sum(1 for line in lines if line["semantic"] in {
                "level_up_to_three_choice", "affix_changes_attack"}),
            "concreteValueCount": sum(1 for line in lines if re.search(r"\d|\+", line["text"])),
            "unsupportedDimensionCount": len([item for item in rejected if item]),
            "presentRuleDimensions": [line["semantic"] for line in lines],
            "supportedButNotRenderedDimensions": sorted(set(not_rendered)),
            "pendingReviewDimensions": [key for line in pending_lines
                                         for key in (line.get("sourceDecisionKeys") or [line["semantic"]])],
            "correctlyRejectedDimensions": list(dict.fromkeys(item for item in rejected if item))}
        report["tooThin"] = report["supportedButNotRenderedDimensions"]
        chapter_reports.append(report)

    density_gate = evaluate_document_density_gate({"chapters": preview["chapters"], "audit": {}})
    lines = [line for chapter in preview["chapters"] for line in chapter["lines"]]
    effective = {"effectiveGameplayRules": sum(1 for line in lines if line["state"] == "approved"),
        "concreteNumericRules": sum(1 for line in lines if re.search(r"\d|\+", line["text"])),
        "meaningfulConstraints": sum(1 for line in lines if line["state"] == "approved" and any(
            term in line["text"] for term in ("无需", "范围", "归零", "仅", "最多"))),
        "crossSystemLinks": sum(item["crossSystemRelationCount"] for item in chapter_reports),
        "unresolvedButActionableRules": sum(1 for line in lines if line["state"] in {"p4_pending", "p6_pending"}),
        "fillerSentences": density_gate["commonSenseExplanationCount"],
        "implementationSentences": sum(1 for line in lines if any(term in line["text"] for term in (
            "轮询", "同帧", "缓存", "原子提交", "事件排序")))}
    return {"chapters": chapter_reports, "effectiveRuleDensity": effective,
            "densityGate": density_gate,
            "tooThin": [{"chapterTitle": item["chapterTitle"], "dimensions": item["tooThin"]}
                        for item in chapter_reports if item["tooThin"]],
            "tooVerbose": density_gate["findings"]}
