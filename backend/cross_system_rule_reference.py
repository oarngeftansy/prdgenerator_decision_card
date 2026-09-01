from __future__ import annotations

import hashlib
import re
from typing import Any


ACTIVE_SCOPE = {"confirmed", "strongly_implied"}
REQUIRED_RELATIONS = {
    "level_to_three_choice", "three_choice_to_affix", "weapon_attack_to_affix", "level_to_outcome",
}


def _id(source: str, target: str, relation: str) -> str:
    digest = hashlib.sha1(f"{source}:{target}:{relation}".encode("utf-8")).hexdigest()[:12].upper()
    return f"XREF-{digest}"


def _rule_map(projection_set: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["sourceRuleId"]: item for item in projection_set.get("ruleProjections", [])}


def _rules(approved_rules: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {item.get("ruleId") or item.get("id"): item for item in approved_rules}


def _chain_steps(chain: dict[str, Any]) -> list[dict[str, Any]]:
    steps = []
    if chain.get("entry"):
        steps.append(chain["entry"])
    for field in ("playerAction", "systemResponse", "stateChange", "progressionResult", "exitOrNext"):
        steps.extend(chain.get(field, []))
    return steps


def _step(chains: list[dict[str, Any]], semantic: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    for chain in chains:
        for item in _chain_steps(chain):
            if item.get("semantic") == semantic:
                return chain, item
    return None, None


def _owner_for_rule(rule_id: str, projections: dict[str, dict[str, Any]]) -> str | None:
    item = projections.get(rule_id)
    return item.get("primaryOwner") if item else None


def _chapter_by_title(projection_set: dict[str, Any], token: str, exclude: str | None = None) -> str | None:
    for item in projection_set.get("systemChapterSkeletons", []):
        title = item.get("chapterTitle", "")
        if token in title and (not exclude or exclude not in title):
            return item["chapterOwner"]
    return None


def _scope_status(scoped_models: list[dict[str, Any]], chapter: str, scope_item: str) -> str:
    model = next((item for item in scoped_models if item.get("chapterId") == chapter), {})
    scopes = model.get("mechanicScopes", model.get("scopeItems", []))
    return next((item.get("existenceStatus") for item in scopes if item.get("scopeItem") == scope_item), "unsupported")


def _plan(source: str, target: str, source_rule: str, target_group: str, relation_key: str,
          relation_type: str, purpose: str, depth: str, text: str, support: str,
          supporting_rules: list[str]) -> dict[str, Any]:
    return {"referenceId": _id(source, target, relation_key), "relationKey": relation_key,
            "sourceChapter": source, "targetChapter": target, "sourceRule": source_rule,
            "targetRuleGroup": target_group, "relationType": relation_type,
            "referencePurpose": purpose, "referenceDepth": depth, "referenceText": text,
            "supportStatus": support, "supportingRuleIds": supporting_rules,
            "suppressedDefinitionRuleIds": supporting_rules}


def build_cross_system_reference_plans(projection_set: dict[str, Any], chains: list[dict[str, Any]],
                                       layouts: list[dict[str, Any]], expansion_plans: list[dict[str, Any]],
                                       parameter_placements: list[dict[str, Any]], scoped_models: list[dict[str, Any]],
                                       approved_rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    projections = _rule_map(projection_set)
    plans: list[dict[str, Any]] = []

    _, enter_three = _step(chains, "enter_three_choice")
    if enter_three and enter_three.get("ruleIds"):
        rule_id = enter_three["ruleIds"][0]
        target = _owner_for_rule(rule_id, projections)
        source = _chapter_by_title(projection_set, "关卡流程")
        if source and target:
            plans.append(_plan(source, target, rule_id, "触发与选择", "level_to_three_choice", "triggers",
                "交代关卡成长进入三选一的流程出口；候选、刷新与选择规则留在三选一主定义章节。",
                "short_rule_reference", "达到升级条件后触发三选一。", "confirmed", [rule_id]))

    _, selected_effect = _step(chains, "apply_selected_effect")
    if selected_effect and selected_effect.get("ruleIds"):
        rule_ids = selected_effect["ruleIds"]
        target = next((_owner_for_rule(rule_id, projections) for rule_id in rule_ids
                       if _owner_for_rule(rule_id, projections)), None)
        three_rule = (_step(chains, "generate_candidates")[1] or _step(chains, "enter_three_choice")[1])
        source = _owner_for_rule(three_rule["ruleIds"][0], projections) if three_rule and three_rule.get("ruleIds") else None
        if source and target:
            plans.append(_plan(source, target, rule_ids[0], "词条效果", "three_choice_to_affix", "applies",
                "说明三选一选择行为产生词条生效结果；具体效果由词条章节集中定义。",
                "short_rule_reference", "选择后，对应词条效果生效。", "confirmed", rule_ids))

    _, weapon_modifier = _step(chains, "apply_weapon_modifier")
    if weapon_modifier and weapon_modifier.get("ruleIds"):
        rule_ids = weapon_modifier["ruleIds"]
        target = next((_owner_for_rule(rule_id, projections) for rule_id in rule_ids
                       if _owner_for_rule(rule_id, projections)), None)
        attack_step = _step(chains, "execute_attack")[1]
        source = _owner_for_rule(attack_step["ruleIds"][0], projections) if attack_step and attack_step.get("ruleIds") else None
        if source and target:
            plans.append(_plan(source, target, rule_ids[0], "词条效果", "weapon_attack_to_affix", "affects",
                "交代词条与武器攻击的影响关系；不在攻击章节复制具体词条效果。",
                "short_rule_reference", "部分词条可修改武器的攻击方式或攻击参数。", "confirmed", rule_ids))

    _, failure = _step(chains, "failure_exit")
    if failure and failure.get("ruleIds"):
        rule_id = failure["ruleIds"][0]
        target = _owner_for_rule(rule_id, projections)
        source = _chapter_by_title(projection_set, "关卡流程")
        if source and target:
            plans.append(_plan(source, target, rule_id, "胜负判定", "level_to_outcome", "transitions_to",
                "交代关卡流程的失败出口；生命归零与失败处理由胜负判定章节完整定义。",
                "inline_reference", "载具生命值归零后进入失败判定。", "confirmed", [rule_id]))

    outcome = next((item.get("primaryOwner") for item in projection_set.get("ruleProjections", [])
                    if item.get("ruleRole") == "failure_rule"), None)
    settlement = _chapter_by_title(projection_set, "结算")
    if outcome and settlement:
        failure_supported = _scope_status(scoped_models, settlement, "failure_trigger") in ACTIVE_SCOPE
        victory_supported = (_scope_status(scoped_models, outcome, "victory") in ACTIVE_SCOPE and
                             _scope_status(scoped_models, settlement, "victory_trigger") in ACTIVE_SCOPE)
        supported = failure_supported or victory_supported
        source_rule = next((item["sourceRuleId"] for item in projection_set.get("ruleProjections", [])
                            if item.get("primaryOwner") == outcome and item.get("ruleRole") == "failure_rule"), "")
        plans.append(_plan(outcome, settlement, source_rule, "结算入口", "outcome_to_settlement", "transitions_to",
            "只有已确认的胜负结果到结算入口关系才需要在胜负章节交代。",
            "short_rule_reference" if supported else "no_reference_needed",
            "失败后进入结算。" if failure_supported else ("胜利后进入结算。" if victory_supported else ""),
            "confirmed" if supported else "unsupported", [source_rule] if source_rule else []))
    return plans


def _chapter_name(chapter_id: str, projection_set: dict[str, Any]) -> str:
    title = next((item.get("chapterTitle") for item in projection_set.get("systemChapterSkeletons", [])
                  if item.get("chapterOwner") == chapter_id), chapter_id)
    if any(item.get("primaryOwner") == chapter_id and item.get("ruleRole") == "failure_rule"
           for item in projection_set.get("ruleProjections", [])):
        return "胜负判定"
    if "关卡流程" in title:
        return "关卡流程"
    if title.startswith("三选一"):
        return "三选一"
    if title.startswith("武器") and "攻击" in title:
        return "武器攻击"
    return title.replace(" / ", " · ")


def build_cross_system_chapter_previews(plans: list[dict[str, Any]], projection_set: dict[str, Any],
                                        approved_rules: list[dict[str, Any]],
                                        expansion_plans: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rules = _rules(approved_rules)
    chapter_ids = []
    for plan in plans:
        for chapter in (plan["sourceChapter"], plan["targetChapter"]):
            if chapter and chapter not in chapter_ids and chapter != _chapter_by_title(projection_set, "结算"):
                chapter_ids.append(chapter)
    previews = []
    for chapter in chapter_ids:
        chapter_title = next((item.get("chapterTitle", "") for item in projection_set.get("systemChapterSkeletons", [])
                              if item.get("chapterOwner") == chapter), "")
        definition_owners = {chapter}
        if chapter_title.startswith("三选一"):
            definition_owners.update(item["chapterOwner"] for item in projection_set.get("systemChapterSkeletons", [])
                                     if item.get("chapterTitle", "").startswith("三选一"))
        definitions = []
        for projection in projection_set.get("ruleProjections", []):
            if projection.get("primaryOwner") not in definition_owners:
                continue
            rule = rules.get(projection["sourceRuleId"], {})
            definitions.append({"ruleId": projection["sourceRuleId"],
                                "text": rule.get("behavior") or rule.get("text") or projection["sourceRuleId"]})
        active = [plan for plan in plans if plan["sourceChapter"] == chapter and
                  plan["referenceDepth"] != "no_reference_needed"]
        suppressed = []
        for plan in active:
            suppressed.extend(plan.get("suppressedDefinitionRuleIds", []))
        previews.append({"chapterId": chapter, "chapterTitle": _chapter_name(chapter, projection_set),
                         "fullDefinitions": definitions,
                         "shortCrossSystemReferences": [{"referenceId": plan["referenceId"],
                                                          "text": plan["referenceText"]} for plan in active],
                         "suppressedDuplicatedDefinitions": sorted(set(suppressed))})
    return previews


def evaluate_gve16_cross_system_references(plans: list[dict[str, Any]],
                                           chapter_previews: list[dict[str, Any]]) -> dict[str, Any]:
    occurrences: dict[str, int] = {}
    for chapter in chapter_previews:
        for definition in chapter.get("fullDefinitions", []):
            occurrences[definition["ruleId"]] = occurrences.get(definition["ruleId"], 0) + 1
    duplicate_count = sum(max(0, count - 1) for count in occurrences.values())
    active = [plan for plan in plans if plan.get("referenceDepth") != "no_reference_needed"]
    present = {plan.get("relationKey") for plan in active}
    missing = sorted(REQUIRED_RELATIONS - present)
    meaningless = [plan["referenceId"] for plan in active
                    if any(term in plan.get("referenceText", "") for term in ("详见", "参见", "请查看"))]
    unsupported = [plan["referenceId"] for plan in active if plan.get("supportStatus") != "confirmed"]
    leak_pattern = re.compile(r"\b(?:V2CH|RULE|ENT|XREF)-[A-Z0-9-]+\b")
    leaked = []
    for chapter in chapter_previews:
        for item in chapter.get("shortCrossSystemReferences", []):
            if leak_pattern.search(item.get("text", "")):
                leaked.append(chapter.get("chapterId"))
    findings = ([f"duplicate:{duplicate_count}"] if duplicate_count else []) + missing + meaningless + unsupported + leaked
    return {"qualityGate": "pass" if not findings else "fail",
            "referencePlanCount": len(plans), "activeReferenceCount": len(active),
            "duplicateFullDefinitionCount": duplicate_count,
            "missingNecessaryRelationshipCount": len(missing),
            "meaninglessReferenceCount": len(meaningless),
            "unsupportedRelationReferenceCount": len(unsupported),
            "internalIdLeakCount": len(leaked), "findings": findings}
