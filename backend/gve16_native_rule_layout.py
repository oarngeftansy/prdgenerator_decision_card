from __future__ import annotations

import hashlib
from typing import Any, Mapping


INTERNAL_TITLES = {"trigger", "condition", "processing", "result", "restriction", "parameter",
                   "node", "edge", "breakpoint", "pipeline", "contract"}
UNIFORM_SCHEMA_TITLES = {"条件", "处理", "结果", "限制", "参数", "异常", "配置"}


def _id(owner: str, group_id: str) -> str:
    return "LAYOUT-" + hashlib.sha1(f"{owner}:{group_id}".encode("utf-8")).hexdigest()[:12].upper()


def _projection_maps(projection_set: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    return ({item["sourceRuleId"]: item for item in projection_set.get("ruleProjections", [])},
            {item["sourceParameterId"]: item for item in projection_set.get("parameterProjections", [])})


def _owner_for_group(group: dict[str, Any], projection_set: dict[str, Any], rule_map: dict[str, dict[str, Any]]) -> str | None:
    for skeleton in projection_set.get("systemChapterSkeletons", []):
        if group["groupId"] in {item["groupId"] for item in skeleton.get("ruleGroups", [])}:
            return skeleton["chapterOwner"]
    candidates = []
    for rule in group.get("knownRules", []):
        projection = rule_map.get(rule["ruleId"])
        if projection:
            candidates.extend([projection["primaryOwner"], *projection.get("referenceOwners", [])])
    skeleton_owners = {item["chapterOwner"] for item in projection_set.get("systemChapterSkeletons", [])}
    selected = next((candidate for candidate in candidates if candidate in skeleton_owners), candidates[0] if candidates else None)
    if selected:
        return selected
    title_semantics = {"可获取词条": {"candidate_filter"}, "关卡推进": {"player_level_up"},
                       "结算结果": {"displayed_data"}}
    semantics = title_semantics.get(group.get("title"), set())
    return next((item.get("primaryOwner") for item in projection_set.get("missingLinkProjections", [])
                 if item.get("semanticKey") in semantics), None)


def _parameter_details(chains: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {item.get("sourceId"): item for chain in chains for item in chain.get("gameplayParameters", []) if item.get("sourceId")}


def _missing_for_group(group: dict[str, Any], owner: str, projection_set: dict[str, Any]) -> list[dict[str, Any]]:
    title = group.get("title")
    semantics = {
        "可获取词条": {"candidate_filter"}, "随机规则": {"resume_combat"},
        "攻击规则": {"damage_resolution"}, "关卡推进": {"player_level_up"},
        "胜负规则": {"victory_path"}, "结算结果": {"displayed_data"},
    }.get(title, set())
    projected = [item for item in projection_set.get("missingLinkProjections", [])
                 if item.get("primaryOwner") == owner and item.get("semanticKey") in semantics]
    existing_semantics = {item.get("semanticKey") for item in projected}
    for item in group.get("missingRules", []):
        if item.get("semantic") not in existing_semantics:
            projected.append({"projectionId": item.get("sourceId"), "semanticKey": item.get("semantic"),
                              "question": item.get("semantic"), "primaryOwner": owner})
    return projected


def _subsection(title: str, purpose: str, rules: list[str] | None = None, refs: list[str] | None = None,
                missing: list[str] | None = None, parameters: list[str] | None = None) -> dict[str, Any]:
    return {"title": title, "purpose": purpose, "supportingRuleIds": rules or [], "referenceRuleIds": refs or [],
            "missingRuleIds": missing or [], "parameterCarrierIds": parameters or []}


def _native_subsections(group: dict[str, Any], full: list[dict[str, Any]], refs: list[dict[str, Any]],
                        missing: list[dict[str, Any]], params: list[tuple[dict[str, Any], dict[str, Any]]]) -> tuple[str, list[dict[str, Any]]]:
    title = group.get("title")
    by_role: dict[str, list[str]] = {}
    for item in full:
        by_role.setdefault(item.get("ruleRole", "game_rule"), []).append(item["sourceRuleId"])
    missing_by_semantic = {item.get("semanticKey"): item["projectionId"] for item in missing}
    param_by_semantic = {detail.get("semantic"): projection["projectionId"] for projection, detail in params}

    if title == "攻击规则":
        sections = []
        automatic_rules = by_role.get("input_constraint", []) + by_role.get("target_selection", [])
        automatic_params = [param_by_semantic[s] for s in ("attack_entry", "next_attack_trigger") if s in param_by_semantic]
        if automatic_rules or automatic_params:
            sections.append(_subsection("自动攻击", "说明自动攻击方式、目标选择和直接影响攻击节奏的参数。",
                                        automatic_rules, parameters=automatic_params))
        if by_role.get("processing"):
            sections.append(_subsection("攻击方式", "说明武器如何对目标执行攻击。", by_role["processing"]))
        damage_missing = [missing_by_semantic[s] for s in ("damage_resolution",) if s in missing_by_semantic]
        damage_params = [param_by_semantic[s] for s in ("damage_output",) if s in param_by_semantic]
        if damage_missing or damage_params:
            sections.append(_subsection("伤害结算", "承载攻击伤害规则断点及对应玩法参数。",
                                        missing=damage_missing, parameters=damage_params))
        return "攻击规则", sections

    if title == "随机规则":
        sections = []
        trigger_rules = by_role.get("trigger_and_generation", []) + by_role.get("state_change", [])
        if trigger_rules:
            sections.append(_subsection("触发与候选生成", "按玩法入口说明触发、暂停及候选生成。", trigger_rules))
        choice_rules = by_role.get("player_choice", [])
        resume = [missing_by_semantic[s] for s in ("resume_combat",) if s in missing_by_semantic]
        if choice_rules or resume:
            sections.append(_subsection("玩家选择", "说明玩家选择行为以及选择后的流程衔接。",
                                        choice_rules, missing=resume))
        return "触发与选择", sections

    if title == "关卡推进":
        level_missing = [missing_by_semantic[s] for s in ("player_level_up",) if s in missing_by_semantic]
        sections = [_subsection("局内成长", "定位战斗成长与升级触发的规则衔接。", missing=level_missing)] if level_missing else []
        return "关卡推进", sections

    natural_title = {"刷新规则": "刷新", "选择结果": "选择结果", "接触伤害": "接触伤害",
                     "可获取词条": "可获取词条", "胜负规则": "胜负衔接"}.get(title, title)
    return natural_title, []


def reconstruct_native_rule_layouts(projection_set: dict[str, Any], game_rule_groups: list[dict[str, Any]],
                                    chains: list[dict[str, Any]], corpora: Mapping[str, Any]) -> list[dict[str, Any]]:
    rule_map, parameter_map = _projection_maps(projection_set)
    parameter_details = _parameter_details(chains)
    plans = []
    for group in game_rule_groups:
        owner = _owner_for_group(group, projection_set, rule_map)
        if not owner:
            continue
        full = [rule_map[r["ruleId"]] for r in group.get("knownRules", [])
                if r["ruleId"] in rule_map and rule_map[r["ruleId"]]["primaryOwner"] == owner]
        refs = [rule_map[r["ruleId"]] for r in group.get("knownRules", [])
                if r["ruleId"] in rule_map and owner in rule_map[r["ruleId"]].get("referenceOwners", [])]
        missing = _missing_for_group(group, owner, projection_set)
        params = []
        for parameter_id, detail in parameter_details.items():
            projection = parameter_map.get(parameter_id)
            if projection and projection.get("primaryOwner") == owner and detail.get("sourceGroupId") == group["groupId"]:
                params.append((projection, detail))
        section_title, subsections = _native_subsections(group, full, refs, missing, params)
        all_full = [item["sourceRuleId"] for item in full]
        all_refs = [item["sourceRuleId"] for item in refs]
        all_missing = [item["projectionId"] for item in missing]
        all_params = [item[0]["projectionId"] for item in params]
        content_count = len(all_full) + len(all_refs) + len(all_missing) + len(all_params)
        if not content_count:
            continue
        mechanic_type = corpora.get("ownerMechanicTypes", {}).get(owner)
        corpus_mechanic_type = "attack" if mechanic_type == "monster_attack" else mechanic_type
        pattern = next((item for item in corpora.get("gve16Structure", {}).get("patterns", [])
                        if item.get("mechanicType") == corpus_mechanic_type), None)
        source_ref = pattern.get("evidenceSourceRef") if pattern else "GVE16/ANON-GROUPING-POLICY"
        mode = "subsections" if len(subsections) >= 2 else "direct_bullets"
        if mode == "direct_bullets":
            subsections = []
        plans.append({"layoutId": _id(owner, group["groupId"]), "ownerChapter": owner,
                      "ruleGroupId": group["groupId"], "sectionTitle": section_title,
                      "layoutMode": mode, "subsectionOrder": [s["title"] for s in subsections],
                      "subsectionPurpose": [s["purpose"] for s in subsections],
                      "supportingRuleIds": all_full, "referenceRuleIds": all_refs,
                      "missingRuleIds": all_missing, "parameterCarrierIds": all_params,
                      "layoutPatternSource": f"current_project_rule_chain > {source_ref}",
                      "subsections": subsections})
    return plans


def evaluate_layout_quality(plans: list[dict[str, Any]]) -> dict[str, Any]:
    empty = []
    internal = []
    uniform = []
    excessive = []
    one_rule_heading = []
    natural_order = []
    for plan in plans:
        titles = [plan.get("sectionTitle", ""), *plan.get("subsectionOrder", [])]
        for title in titles:
            normalized = title.strip().lower()
            if normalized in INTERNAL_TITLES or "_" in normalized:
                internal.append(f"{plan.get('layoutId')}:{title}")
            if title in UNIFORM_SCHEMA_TITLES or normalized in INTERNAL_TITLES:
                uniform.append(f"{plan.get('layoutId')}:{title}")
        if len(plan.get("subsectionOrder", [])) > 5:
            excessive.append(plan.get("layoutId"))
        for subsection in plan.get("subsections", []):
            count = sum(len(subsection.get(field, [])) for field in
                        ("supportingRuleIds", "referenceRuleIds", "missingRuleIds", "parameterCarrierIds"))
            if count == 0:
                empty.append(f"{plan.get('layoutId')}:{subsection.get('title')}")
            if count == 1 and len(plan.get("subsections", [])) == 1:
                one_rule_heading.append(f"{plan.get('layoutId')}:{subsection.get('title')}")
    by_owner: dict[str, list[str]] = {}
    for plan in plans:
        by_owner.setdefault(plan.get("ownerChapter"), []).append(plan.get("sectionTitle"))
    expected_sequences = (["可获取词条", "触发与选择", "刷新", "选择结果"], ["关卡推进", "胜负衔接"])
    for owner, titles in by_owner.items():
        for expected in expected_sequences:
            present = [title for title in expected if title in titles]
            actual = [title for title in titles if title in expected]
            if len(present) >= 2 and actual != present:
                natural_order.append(owner)
    findings = empty + internal + uniform + excessive + one_rule_heading + natural_order
    gve16_backed = sum("GVE16/" in plan.get("layoutPatternSource", "") for plan in plans)
    return {"qualityGate": "pass" if not findings else "fail", "layoutCount": len(plans),
            "emptyHeadingCount": len(empty), "internalSemanticHeadingCount": len(internal),
            "uniformSchemaTraceCount": len(uniform), "overDepthCount": len(excessive),
            "oneRuleOneHeadingCount": len(one_rule_heading), "naturalOrderViolationCount": len(set(natural_order)),
            "gve16PatternBackedCount": gve16_backed,
            "gve16PatternBackedRate": round(gve16_backed / len(plans), 4) if plans else 1.0,
            "findings": findings}
