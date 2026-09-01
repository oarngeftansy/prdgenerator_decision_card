from __future__ import annotations

import copy
import re
from typing import Any


_INDEPENDENT_SINGLE_RULE_GROUPS = {
    "RSC-WEAPON-ACQUISITION", "RSC-WEAPON-SLOT", "RSC-BOSS",
    "RSC-ELAPSED-TIME", "RSC-SUCCESS", "RSC-ULTIMATE-AFFIX",
}


def _published(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [copy.deepcopy(item) for item in items
            if item.get("publishWorthiness") != "suppress_common_sense"]


def _information_count(items: list[dict[str, Any]]) -> int:
    return sum(1 + len(item.get("subrules", [])) for item in items)


def _make_section(title: str, group_id: str, items: list[dict[str, Any]],
                  reason: str | None = None) -> dict[str, Any]:
    if reason is None:
        reason = "multiple_rules" if _information_count(items) >= 2 else "independent_submechanic"
    return {"title": title, "sourceGroupIds": [group_id], "items": items,
            "headingRetentionReason": reason}


def _stitch_success_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    success = next((item for item in items if "success_result" in item.get("sourceDimensionIds", [])), None)
    condition = next((item for item in items if "success_condition" in item.get("sourceDimensionIds", [])), None)
    if not success or not condition:
        return items
    stitched = copy.deepcopy(success)
    stitched.update({
        "text": "关卡可正常通关，通关条件：待确认。",
        "supportingRuleIds": sorted(set(success["supportingRuleIds"] + condition["supportingRuleIds"])),
        "sourceDimensionIds": sorted(set(success["sourceDimensionIds"] + condition["sourceDimensionIds"])),
        "synthesisLevel": "composite_rule",
        "subrules": [],
    })
    return [stitched, *[item for item in items if item is not success and item is not condition]]


def _merge_duplicate_concrete_rules(chapter: dict[str, Any]) -> list[dict[str, Any]]:
    """Remove repeated named examples while transferring their provenance."""
    audit: list[dict[str, Any]] = []
    named_owner: dict[str, dict[str, Any]] = {}
    for section in chapter["sections"]:
        kept = []
        for item in section["items"]:
            for subrule in item.get("subrules", []):
                if "：" in subrule:
                    named_owner.setdefault(subrule.split("：", 1)[0], item)
            matched_name = next((name for name in named_owner if item["text"].startswith(name)), None)
            if matched_name and named_owner[matched_name] is not item:
                owner = named_owner[matched_name]
                owner["supportingRuleIds"] = sorted(set(owner["supportingRuleIds"] + item["supportingRuleIds"]))
                owner["sourceDimensionIds"] = sorted(set(owner["sourceDimensionIds"] + item["sourceDimensionIds"]))
                audit.append({"suppressedText": item["text"], "coveredByConcreteRule": matched_name,
                              "transferredRuleIds": item["supportingRuleIds"],
                              "transferredDimensionIds": item["sourceDimensionIds"]})
                continue
            kept.append(item)
        section["items"] = kept
    return audit


def flatten_mechanic_rule_hierarchy(hierarchy: dict[str, Any]) -> dict[str, Any]:
    result = {"chapters": [], "flatteningAudit": {"foldedHeadings": [], "deduplicatedRules": []}}
    before_dimensions = set()
    for chapter in hierarchy.get("chapters", []):
        target = {"title": chapter["title"], "sections": []}
        for group in chapter.get("ruleGroups", []):
            direct_items = _published(group.get("items", []))
            subgroup_items = [(subgroup, _published(subgroup.get("items", [])))
                              for subgroup in group.get("subgroups", [])]
            for item in direct_items:
                before_dimensions.update(item.get("sourceDimensionIds", []))
            for _, items in subgroup_items:
                for item in items:
                    before_dimensions.update(item.get("sourceDimensionIds", []))
            if group["groupId"] == "RSC-SETTLEMENT" or group["title"] == "结算结果":
                for subgroup, items in subgroup_items:
                    if items:
                        target["sections"].append(_make_section(
                            subgroup["title"], group["groupId"], items, "independent_submechanic"))
                result["flatteningAudit"]["foldedHeadings"].append({
                    "chapter": chapter["title"], "removed": group["title"],
                    "reason": "parent_repeated_chapter_scope",
                })
                continue
            flattened_items = direct_items[:]
            for subgroup, items in subgroup_items:
                if items:
                    flattened_items.extend(items)
                    result["flatteningAudit"]["foldedHeadings"].append({
                        "chapter": chapter["title"], "removed": subgroup["title"],
                        "mergedInto": group["title"], "reason": "insufficient_independent_content",
                    })
            group_dimensions = {dimension_id for item in flattened_items
                                for dimension_id in item.get("sourceDimensionIds", [])}
            if group["groupId"] == "RSC-SUCCESS" or {"success_result", "success_condition"} <= group_dimensions:
                flattened_items = _stitch_success_items(flattened_items)
            if not flattened_items:
                continue
            reason = ("independent_submechanic" if group["groupId"] in _INDEPENDENT_SINGLE_RULE_GROUPS
                      else None)
            title = {"RSC-THREE-CHOICE": "主体规则", "RSC-AD-REFRESH": "刷新",
                     "RSC-SUCCESS": "胜负"}.get(group["groupId"],
                    "胜负" if {"success_result", "success_condition"} <= group_dimensions else group["title"])
            target["sections"].append(_make_section(title, group["groupId"], flattened_items, reason))
        if target["sections"]:
            result["flatteningAudit"]["deduplicatedRules"].extend(_merge_duplicate_concrete_rules(target))
            target["sections"] = [section for section in target["sections"] if section["items"]]
            result["chapters"].append(target)
    after_dimensions = {
        dimension_id for chapter in result["chapters"] for section in chapter["sections"]
        for item in section["items"] for dimension_id in item.get("sourceDimensionIds", [])
    }
    result["semanticCoverage"] = {
        "beforeDimensionIds": sorted(before_dimensions),
        "afterDimensionIds": sorted(after_dimensions),
        "lostDimensionIds": sorted(before_dimensions - after_dimensions),
    }
    return result


def render_flattened_mechanic_preview(flattened: dict[str, Any]) -> str:
    lines = ["# Human Planning Preview", ""]
    for chapter in flattened["chapters"]:
        lines.extend([f"## {chapter['title']}", ""])
        for section in chapter["sections"]:
            lines.extend([f"### {section['title']}", ""])
            for item in section["items"]:
                lines.append(f"- {item['text']}")
                lines.extend(f"  - {subrule}" for subrule in item.get("subrules", []))
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def markdown_hierarchy_metrics(markdown: str) -> dict[str, int]:
    lines = markdown.splitlines()
    headings = [(index, len(match.group(1)), match.group(2)) for index, line in enumerate(lines)
                if (match := re.match(r"^(#{2,})\s+(.+)$", line))]
    single = 0
    for position, (line_index, level, _) in enumerate(headings):
        end = headings[position + 1][0] if position + 1 < len(headings) else len(lines)
        direct_bullets = sum(lines[index].startswith("- ") for index in range(line_index + 1, end))
        if direct_bullets == 1:
            single += 1
    concrete_names = []
    for line in lines:
        stripped = line.strip().removeprefix("- ")
        if "：" in stripped and not stripped.endswith("待确认。"):
            concrete_names.append(stripped.split("：", 1)[0])
    return {
        "headingCount": len(headings),
        "maxNestingDepth": max((level for _, level, _ in headings), default=1),
        "singleRuleHeadingCount": single,
        "duplicatedConcreteRuleCount": len(concrete_names) - len(set(concrete_names)),
    }
