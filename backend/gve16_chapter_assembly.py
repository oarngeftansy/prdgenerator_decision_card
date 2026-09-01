from __future__ import annotations

import re
from collections import Counter
from typing import Any


_INTERNAL_TITLE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z0-9_]+)+$")


def _publication_title(plan: dict[str, Any]) -> str:
    """Use an explicit planning-language title; never publish a dimension id as a heading."""
    title = str(plan.get("planningTitle") or plan["ruleGroup"]).strip()
    if _INTERNAL_TITLE_PATTERN.fullmatch(title):
        raise ValueError(f"internal execution dimension cannot be a publication title: {title}")
    return title


def assemble_gve16_chapters(carrier_plan: list[dict[str, Any]],
                            chapter_order: list[str]) -> dict[str, Any]:
    grouped: dict[tuple[str, ...], dict[str, list[dict[str, Any]]]] = {}
    path_to_legacy: dict[tuple[str, ...], str] = {}
    for raw in carrier_plan:
        plan = dict(raw)
        plan.setdefault("publishStatus", "publishable")
        path = tuple(plan.get("ownerPath") or [plan["chapter"]])
        for title in path:
            if _INTERNAL_TITLE_PATTERN.fullmatch(str(title).strip()):
                raise ValueError(f"internal execution dimension cannot be an owner heading: {title}")
        path_to_legacy.setdefault(path, plan["chapter"])
        grouped.setdefault(path, {}).setdefault(_publication_title(plan), []).append(plan)

    lines = ["# Human Planning Preview", ""]
    assembly_plans = []
    candidate_suppressed = 0
    published_texts = []
    root_order: dict[str, int] = {}
    for plan in carrier_plan:
        path = tuple(plan.get("ownerPath") or [plan["chapter"]])
        root_order.setdefault(path[0], len(root_order))
    ordered_paths = sorted(grouped, key=lambda path: (
        root_order[path[0]], len(path),
        next(index for index, plan in enumerate(carrier_plan)
             if tuple(plan.get("ownerPath") or [plan["chapter"]]) == path),
    ))
    previous_path: tuple[str, ...] = ()
    for path in ordered_paths:
        chapter = path_to_legacy[path]
        shared = 0
        for left, right in zip(previous_path, path):
            if left != right:
                break
            shared += 1
        for depth, title in enumerate(path[shared:], 2 + shared):
            heading = "#" * min(depth, 6)
            lines.extend([f"{heading} {title}", ""])
        previous_path = path
        group_plans = grouped[path]
        chapter_primary = []
        chapter_refs = []
        pending_placement = {}
        carriers = {}
        ordered_groups = sorted(group_plans.items(), key=lambda pair: (
            min((plan.get("chainPosition") if plan.get("chainPosition") is not None else 10_000
                 for plan in pair[1]), default=10_000),
            list(group_plans).index(pair[0]),
        ))
        for group, plans in ordered_groups:
            publishable = [plan for plan in plans if plan["publishStatus"] == "publishable"]
            suppressed = [plan for plan in plans if plan["publishStatus"] != "publishable"]
            candidate_suppressed += sum(len(plan["sourceTexts"]) for plan in suppressed)
            if not publishable:
                continue
            group_heading = "#" * min(len(path) + 2, 6)
            if group != path[-1]:
                lines.extend([f"{group_heading} {group}", ""])
            carrier_names = [plan["selectedCarrier"] for plan in publishable]
            carriers[group] = carrier_names
            all_texts = [text for plan in publishable for text in plan["sourceTexts"]]
            pending = [text for text in all_texts if "待确认" in text]
            formula_texts = [text for plan in publishable if plan["selectedCarrier"] == "formula"
                             for text in plan["sourceTexts"]]
            core = [text for text in all_texts if "待确认" not in text and text not in formula_texts]
            for text in core:
                if chapter == "关卡" and "触发三选一" in text:
                    chapter_refs.append(text)
                else:
                    chapter_primary.append(text)

            if chapter == "三选一" and group == "主体规则" and "ordered_steps" in carrier_names:
                steps = next(plan["sourceTexts"] for plan in publishable
                             if plan["selectedCarrier"] == "ordered_steps")
                lines.append(f"1. {steps[0]}")
                step_plan = next(plan for plan in publishable if plan["selectedCarrier"] == "ordered_steps")
                source_items = step_plan.get("sourceItems", [])
                if source_items:
                    for attachment in source_items[0].get("reviewAttachments", []):
                        lines.append(f"   - 待确认：{attachment['text']}")
                    for attachment in source_items[0].get("parameterAttachments", []):
                        lines.append(f"   - 参数：{attachment['text']}")
                for text in pending:
                    lines.append(f"   - {text}")
                lines.append(f"2. {steps[1]}")
                pending_placement[group] = "adjacent_to_candidate_generation"
            elif any(carrier in {"ordered_steps", "lifecycle_sequence", "condition_branch"}
                     for carrier in carrier_names):
                step_number = 0
                for plan in publishable:
                    for source_index, text in enumerate(plan["sourceTexts"]):
                        step_number += 1
                        prefix = f"{step_number}." if plan["selectedCarrier"] != "condition_branch" else f"- 分支 {step_number}："
                        lines.append(f"{prefix} {text}")
                        source_items = plan.get("sourceItems", [])
                        if source_index < len(source_items):
                            rule_ids = set(source_items[source_index].get("supportingRuleIds", []))
                        else:
                            fallback_ids = plan.get("sourceRuleIds", [])
                            rule_ids = {fallback_ids[source_index]} if source_index < len(fallback_ids) else set()
                        local_reviews = (source_items[source_index].get("reviewAttachments", [])
                                         if source_index < len(source_items) else plan.get("reviewAttachments", []))
                        local_parameters = (source_items[source_index].get("parameterAttachments", [])
                                            if source_index < len(source_items) else plan.get("parameterAttachments", []))
                        for attachment in local_reviews:
                            if not attachment.get("consumerRuleId") or attachment["consumerRuleId"] in rule_ids:
                                lines.append(f"   - 待确认：{attachment['text']}")
                        for attachment in local_parameters:
                            if not attachment.get("consumerRuleId") or attachment["consumerRuleId"] in rule_ids:
                                unit = f"（单位：{attachment['unit']}）" if attachment.get("unit") else ""
                                lines.append(f"   - 参数：{attachment['text']}{unit}")
                pending_placement[group] = "attached_to_consumer_rule"
            elif "table" in carrier_names:
                texts = next(plan["sourceTexts"] for plan in publishable if plan["selectedCarrier"] == "table")
                lines.extend(["| 词条 | 作用对象 | 效果 |", "|---|---|---|"])
                for text in texts:
                    name, target, effect = _affix_columns(text)
                    lines.append(f"| {name} | {target} | {effect} |")
                pending_placement[group] = "none"
            else:
                for text in core:
                    lines.append(f"- {text}")
                    source_item = next((item for plan in publishable
                                        for item in plan.get("sourceItems", [])
                                        if item.get("text") == text), None)
                    if source_item:
                        for attachment in source_item.get("reviewAttachments", []):
                            lines.append(f"  - 待确认：{attachment['text']}")
                        for attachment in source_item.get("parameterAttachments", []):
                            unit = f"（单位：{attachment['unit']}）" if attachment.get("unit") else ""
                            lines.append(f"  - 参数：{attachment['text']}{unit}")
                if pending:
                    if any(plan["selectedCarrier"] == "parameter_list" for plan in publishable):
                        lines.extend(["", "参数："])
                        pending_placement[group] = "parameter_list_after_core"
                    elif core:
                        lines.extend(["", "待确认："])
                        pending_placement[group] = "pending_block_after_core"
                    else:
                        pending_placement[group] = "only_available_content"
                    lines.extend(f"- {text}" for text in pending)
                for plan in publishable:
                    if plan["selectedCarrier"] == "formula":
                        lines.extend(["", "> **计算规则**"])
                        lines.extend(f"> {text}" for text in plan["sourceTexts"])
            published_texts.extend(all_texts)
            lines.append("")

        assembly_plans.append({
            "chapter": chapter,
            "orderedRuleGroups": list(group_plans),
            "primaryDefinitions": chapter_primary,
            "contextualReferences": chapter_refs,
            "pendingPlacement": pending_placement,
            "carrierPlacement": carriers,
            "assemblyReason": _assembly_reason(chapter),
        })
    markdown = "\n".join(lines).rstrip() + "\n"
    duplicates = sum(count - 1 for count in Counter(published_texts).values() if count > 1)
    return {"markdown": markdown, "chapterAssemblyPlan": assembly_plans,
            "metrics": {"publishedRuleItemCount": len(published_texts),
                        "candidateOnlyItemsSuppressed": candidate_suppressed,
                        "duplicatedExactRuleCount": duplicates}}


def _assembly_reason(chapter: str) -> str:
    return {
        "武器": "按获取、容器、攻击及其参数组织，先建立使用前提，再展开战斗规则。",
        "词条": "具体效果集中比较，终极词条的出现规则独立承载。",
        "三选一": "主体选择流程与可选刷新行为分离，未决候选范围贴近候选生成。",
        "怪物": "普通怪物行为与首领阶段分开，不扩展未激活的攻击状态机。",
        "关卡": "按局内成长、计时、胜负排列，跨系统入口只保留必要上下文。",
        "结算": "按战斗结果、统计、奖励、挑战次数排列。",
    }.get(chapter, "按当前规则之间的自然阅读关系排列。")


def _affix_columns(text: str) -> tuple[str, str, str]:
    name, body = text.rstrip("。").split("：", 1)
    for pattern in (r"^(火焰喷射)(范围.+)$", r"^(雷暴枪)(伤害.+|冷却时间.+)$",
                    r"^(火焰爆炸)(次数.+)$", r"^(火焰喷射)(改为.+)$"):
        match = re.match(pattern, body)
        if match:
            return name, match.group(1), match.group(2)
    return name, "—", body
