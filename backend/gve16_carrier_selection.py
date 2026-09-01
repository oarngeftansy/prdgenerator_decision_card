from __future__ import annotations

import copy
import re
from collections import Counter
from typing import Any


_PARAMETER_TOKENS = ("范围：", "间隔：", "伤害计算：", "次数上限：", "重置周期：")


def append_synthesis_rules_to_chapters(
        chapters: list[dict[str, Any]], synthesis_rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Append explicit synthesized rules under their structured dynamic owners."""
    result = copy.deepcopy(chapters)
    superseded = {rule_id for rule in synthesis_rules
                  for rule_id in rule.get("supersedesSynthesisRuleIds", [])}
    if superseded:
        for chapter in result:
            for section in chapter.get("sections", []):
                section["items"] = [
                    item for item in section.get("items", [])
                    if not set(item.get("supportingRuleIds", [])) & superseded
                ]
    published = {
        rule_id
        for chapter in result for section in chapter.get("sections", [])
        for item in section.get("items", []) for rule_id in item.get("supportingRuleIds", [])
    }
    for rule in synthesis_rules:
        rule_id = rule.get("ruleId")
        owner_path = rule.get("planningOwnerPath", [])
        chapter_title = owner_path[0] if owner_path else rule.get("ownerChapter")
        group_title = owner_path[-1] if owner_path else rule.get("ruleGroup")
        if not rule_id or rule_id in published or not chapter_title or not group_title:
            continue
        chapter = next((item for item in result if item.get("title") == chapter_title), None)
        if chapter is None:
            chapter = {"title": chapter_title, "sections": []}
            result.append(chapter)
        section = next((item for item in chapter["sections"] if item.get("title") == group_title), None)
        if section is None:
            section = {"title": group_title, "sourceGroupIds": [], "items": []}
            chapter["sections"].append(section)
        section["items"].append({
            "text": rule["statement"],
            "supportingRuleIds": [rule_id],
            "sourceDimensionIds": list(rule.get("sourceDimensions", [])),
            "itemType": "coreRule",
            "semanticType": "persistent_game_rule",
            "languageReason": "approved_requirement_rule",
            **({"ownerPath": owner_path} if owner_path else {}),
        })
        published.add(rule_id)
    return result


def enrich_structured_chapters(chapters: list[dict[str, Any]],
                               typed_rules: list[dict[str, Any]],
                               owner_audit: dict[str, Any] | None = None,
                               chain_projection: dict[str, list[dict[str, Any]]] | None = None) -> list[dict[str, Any]]:
    """Attach existing publication metadata without deriving gameplay content."""
    result = copy.deepcopy(chapters)
    rules = {rule["ruleId"]: rule for rule in typed_rules}
    owner_paths = _owner_paths(owner_audit or {})
    chain_projection = chain_projection or {}
    for chapter in result:
        for section in chapter.get("sections", []):
            path = owner_paths.get(section["title"]) or owner_paths.get(chapter["title"])
            retained = []
            attachments = []
            for item in section.get("items", []):
                source_rules = [rules[rule_id] for rule_id in item.get("supportingRuleIds", []) if rule_id in rules]
                if path and not item.get("ownerPath"):
                    item["ownerPath"] = path
                primary = next((rule.get("primaryOwner") or rule.get("ruleGroup") for rule in source_rules
                                if rule.get("primaryOwner") or rule.get("ruleGroup")), None)
                chapter_owner = next((rule.get("chapterOwner") or rule.get("ownerChapter") for rule in source_rules
                                      if rule.get("chapterOwner") or rule.get("ownerChapter")), None)
                if primary:
                    item["primaryOwner"] = primary
                if chapter_owner:
                    item["chapterOwner"] = chapter_owner
                item["relations"] = [
                    {"type": _relation_type(relation), "sourceRuleId": rule["ruleId"], "relationKey": relation}
                    for rule in source_rules for relation in rule.get("ruleRelations", [])
                ]
                chain_nodes = [node for rule_id in item.get("supportingRuleIds", [])
                               for node in chain_projection.get(rule_id, [])]
                if chain_nodes:
                    item["chainNodes"] = copy.deepcopy(chain_nodes)
                    item["chainIds"] = list(dict.fromkeys(node["chainId"] for node in chain_nodes))
                    item["chainPosition"] = min(node["chainPosition"] for node in chain_nodes)
                    item["relations"] = [
                        {"type": relation_type, "chainId": node["chainId"],
                         "predecessorSynRuleIds": node.get("predecessorSynRuleIds", []),
                         "successorSynRuleIds": node.get("successorSynRuleIds", [])}
                        for node in chain_nodes for relation_type in node.get("relationTypes", [])
                    ]
                if item.get("itemType") == "pending":
                    consumer = next(iter(item.get("supportingRuleIds", [])), None)
                    field = "parameterAttachments" if item.get("semanticType") == "gameplay_parameter" else "reviewAttachments"
                    attachments.append((field, {"consumerRuleId": consumer, "text": item["text"]}))
                else:
                    retained.append(item)
            for field, attachment in attachments:
                consumer = attachment.get("consumerRuleId")
                target = next((item for item in retained if consumer in item.get("supportingRuleIds", [])), None)
                if target is None and retained:
                    target = retained[-1]
                if target is not None:
                    target.setdefault(field, []).append(attachment)
                else:
                    retained.append({"text": attachment["text"], "itemType": "pending",
                                     "supportingRuleIds": [consumer] if consumer else [],
                                     "sourceDimensionIds": [], **({"ownerPath": path} if path else {})})
            section["items"] = retained
    return result


def _relation_type(relation: str) -> str:
    lowered = relation.lower()
    if any(token in lowered for token in ("branch", "choice_between", "condition")):
        return "branch"
    if any(token in lowered for token in ("reset", "persist", "lifecycle")):
        return "lifecycle"
    if "_to_" in lowered:
        return "sequence"
    return "dependency"


def _owner_paths(audit: dict[str, Any]) -> dict[str, list[str]]:
    paths: dict[str, list[str]] = {}
    for system in audit.get("systems", []):
        system_path = [system["title"]]
        paths.setdefault(system["title"], system_path)
        for subsystem in system.get("subsystems", []):
            subsystem_path = [*system_path, subsystem["title"]]
            paths.setdefault(subsystem["title"], subsystem_path)
            for group in subsystem.get("ruleGroups", []):
                paths.setdefault(group, subsystem_path)
            for mechanism in subsystem.get("mechanisms", []):
                mechanism_path = (subsystem_path if mechanism.get("chapterDecision") in {
                    "merge_into_parent", "merge_or_reference", "defer"
                } else [*subsystem_path, mechanism["title"]])
                paths.setdefault(mechanism["title"], mechanism_path)
                for group in mechanism.get("ruleGroups", []):
                    paths.setdefault(group, mechanism_path)
    for correction in audit.get("ownerCorrections", []):
        target = correction.get("to")
        if correction.get("node") and isinstance(target, str) and "/" in target:
            components = [re.sub(r"\s+(rule group|chapter)$", "", item, flags=re.IGNORECASE)
                          for item in target.split("/")]
            if all(component and ";" not in component for component in components):
                paths[correction["node"]] = components
    return paths


def parse_human_preview(markdown: str) -> list[dict[str, Any]]:
    chapters: list[dict[str, Any]] = []
    chapter = None
    section = None
    for line in markdown.splitlines():
        if line.startswith("## "):
            chapter = {"title": line[3:], "sections": []}
            chapters.append(chapter)
        elif line.startswith("### ") and chapter is not None:
            section = {"title": line[4:], "items": []}
            chapter["sections"].append(section)
        elif line.startswith("- ") and section is not None:
            section["items"].append({"text": line[2:]})
    return chapters


def build_carrier_plan(chapters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    plans: list[dict[str, Any]] = []
    for chapter in chapters:
        for section in chapter.get("sections", []):
            items = section.get("items", [])
            indexed = list(enumerate(items))
            verified = [item for item in items if item.get("chainPosition") is not None]
            shared_chain_ids = set.intersection(*(
                set(item.get("chainIds", [])) for item in verified
            )) if verified and len(verified) == len(items) else set()
            if shared_chain_ids and len({item["chainPosition"] for item in verified}) == len(verified):
                indexed.sort(key=lambda pair: pair[1]["chainPosition"])
            relation_types = {
                relation.get("type")
                for item in items for relation in item.get("relations", [])
                if relation.get("type")
            }
            verified_chain_positions = {
                item.get("chainPosition") for item in items if item.get("chainPosition") is not None
            }
            if any(item.get("chainNodes") for item in items) and len(verified_chain_positions) < 2:
                relation_types = set()
            if _is_affix_table(chapter["title"], section["title"], items):
                plans.append(_plan(chapter, section, "table", indexed,
                                   "同构词条名称、作用对象和效果适合横向扫描。",
                                   ["rule_bullets：具体效果较多，比较效率较低。",
                                    "parameter_table：该表承载规则效果，不是参数配置表。"] ))
                continue
            if len(items) >= 2 and relation_types & {"branch", "condition_branch"}:
                plans.append(_plan(chapter, section, "condition_branch", indexed,
                                   "已确认的分支 Relation 需要保留条件与去向。",
                                   ["rule_bullets：会抹平已确认的分支关系。"] ))
                continue
            if len(items) >= 2 and relation_types & {"sequence", "precedes", "state_transition", "lifecycle"}:
                carrier = "lifecycle_sequence" if relation_types & {"state_transition", "lifecycle"} else "ordered_steps"
                plans.append(_plan(chapter, section, carrier, indexed,
                                   "已确认的 Relation 定义了规则执行顺序。",
                                   ["rule_bullets：会抹平已确认的先后关系。"] ))
                continue
            if _is_affix_table(chapter["title"], section["title"], items):
                plans.append(_plan(chapter, section, "table", indexed,
                                   "同构词条名称、作用对象和效果适合横向扫描。",
                                   ["rule_bullets：具体效果较多，比较效率较低。",
                                    "parameter_table：该表承载规则效果，不是参数配置表。"]))
                continue

            formula = [(index, item) for index, item in indexed if _is_formula(item["text"])]
            remaining = [(index, item) for index, item in indexed if not _is_formula(item["text"])]
            if _is_three_choice_main(chapter["title"], section["title"], remaining):
                core = [(index, item) for index, item in remaining if "待确认" not in item["text"]]
                pending = [(index, item) for index, item in remaining if "待确认" in item["text"]]
                plans.append(_plan(chapter, section, "ordered_steps", core,
                                   "升级、暂停、生成候选与选择结果存在明确先后依赖。",
                                   ["rule_bullets：不如编号清楚地表达主流程顺序。",
                                    "condition_branch：刷新不属于主体流程的必经分支。"] ))
                if pending:
                    plans.append(_plan(chapter, section, "rule_bullets", pending,
                                       "未决候选范围不是流程步骤，独立保留规则项。",
                                       ["ordered_steps：待确认维度没有已确认顺序。"] ))
            else:
                parameters = [(index, item) for index, item in remaining
                              if any(token in item["text"] for token in _PARAMETER_TOKENS)]
                rules = [(index, item) for index, item in remaining if (index, item) not in parameters]
                if rules:
                    plans.append(_plan(chapter, section, "rule_bullets", rules,
                                       "规则数量少且相互独立，bullet 已能清楚表达。",
                                       _default_rejections(rules)))
                if parameters:
                    plans.append(_plan(chapter, section, "parameter_list", parameters,
                                       "少量玩法参数紧邻所属规则，列表比空字段表更自然。",
                                       ["parameter_table：对象不足且多数值未知，不具备同构比较收益。"] ))
            if formula:
                plans.append(_plan(chapter, section, "formula", formula,
                                   "内容包含明确计算关系，公式块比普通句更易识别。",
                                   ["rule_bullets：会弱化计算关系。", "parameter_table：不存在对象×字段矩阵。"] ))
    return plans


def render_carrier_preview(chapters: list[dict[str, Any]], plans: list[dict[str, Any]]) -> dict[str, Any]:
    by_section: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for plan in plans:
        by_section.setdefault((plan["chapter"], plan["ruleGroup"]), []).append(plan)
    lines = ["# Human Planning Preview", ""]
    raw_source_count = sum(len(section.get("items", [])) for chapter in chapters for section in chapter["sections"])
    suppressed_count = sum(len(plan.get("sourceTexts", [])) for plan in plans
                           if plan.get("publishStatus") == "candidate_only")
    source_count = raw_source_count - suppressed_count
    rendered_count = 0
    for chapter in chapters:
        lines.extend([f"## {chapter['title']}", ""])
        for section in chapter["sections"]:
            lines.extend([f"### {section['title']}", ""])
            section_plans = by_section[(chapter["title"], section["title"])]
            section_plans.sort(key=lambda item: min(item["sourceItemIndexes"]))
            for plan in section_plans:
                if plan.get("publishStatus") == "candidate_only":
                    continue
                texts = plan["sourceTexts"]
                rendered_count += len(texts)
                carrier = plan["selectedCarrier"]
                if carrier in {"rule_bullets", "parameter_list"}:
                    lines.extend(f"- {text}" for text in texts)
                elif carrier in {"ordered_steps", "lifecycle_sequence"}:
                    lines.extend(f"{index}. {text}" for index, text in enumerate(texts, 1))
                elif carrier == "condition_branch":
                    lines.extend(f"- 分支 {index}：{text}" for index, text in enumerate(texts, 1))
                elif carrier == "formula":
                    lines.extend(["> **计算规则**", *[f"> {text}" for text in texts]])
                elif carrier == "table":
                    lines.extend(["| 词条 | 作用对象 | 效果 |", "|---|---|---|"])
                    for text in texts:
                        name, target, effect = _affix_columns(text)
                        lines.append(f"| {name} | {target} | {effect} |")
                lines.append("")
    carrier_counts = Counter(plan["selectedCarrier"] for plan in plans)
    metrics = {"sourceRuleItemCount": source_count, "rawSourceItemCount": raw_source_count,
               "candidateOnlyItemsSuppressed": suppressed_count, "renderedRuleItemCount": rendered_count,
               "semanticLoss": abs(source_count - rendered_count),
               "carrierCounts": dict(carrier_counts)}
    return {"markdown": "\n".join(lines).rstrip() + "\n", "metrics": metrics,
            "carrierPlan": copy.deepcopy(plans)}


def _plan(chapter, section, carrier, indexed, reason, rejected):
    items = [item for _, item in indexed]
    def unique(field):
        return list(dict.fromkeys(value for item in items for value in item.get(field, [])))
    owner_paths = [item.get("ownerPath") for item in items if item.get("ownerPath")]
    relations = [relation for item in items for relation in item.get("relations", [])]
    chain_positions = [item["chainPosition"] for item in items if item.get("chainPosition") is not None]
    return {"chapter": chapter["title"], "ruleGroup": section["title"],
            "carrierSegment": len(indexed) and indexed[0][0], "selectedCarrier": carrier,
            "reason": reason, "alternativesRejected": rejected,
            "sourceItemIndexes": [index for index, _ in indexed],
            "sourceTexts": [item["text"] for item in items],
            "sourceItems": copy.deepcopy(items),
            "sourceRuleIds": unique("supportingRuleIds"),
            "sourceDimensionIds": unique("sourceDimensionIds"),
            "chainIds": unique("chainIds"),
            "chainPositions": chain_positions,
            "chainPosition": min(chain_positions) if chain_positions else None,
            "relations": copy.deepcopy(relations),
            "relationTypes": list(dict.fromkeys(relation.get("type") for relation in relations if relation.get("type"))),
            "ownerPath": owner_paths[0] if owner_paths else chapter.get("ownerPath"),
            "primaryOwners": list(dict.fromkeys(item["primaryOwner"] for item in items if item.get("primaryOwner"))),
            "chapterOwners": list(dict.fromkeys(item["chapterOwner"] for item in items if item.get("chapterOwner"))),
            "reviewAttachments": [attachment for item in items for attachment in item.get("reviewAttachments", [])],
            "parameterAttachments": [attachment for item in items for attachment in item.get("parameterAttachments", [])],
            "approvalMutation": False}


def _is_formula(text: str) -> bool:
    return "=" in text and any(token in text for token in ("÷", "/", "×", "+", "-"))


def _is_affix_table(chapter: str, section: str, items: list[dict[str, Any]]) -> bool:
    return chapter == "词条" and section == "词条效果" and len(items) >= 4 and all("：" in item["text"] for item in items)


def _is_three_choice_main(chapter: str, section: str, indexed) -> bool:
    texts = "".join(item["text"] for _, item in indexed)
    return chapter == "三选一" and section == "主体规则" and "等级提升" in texts and "选择1项" in texts


def _default_rejections(indexed):
    return ["ordered_steps：规则之间没有已确认的严格步骤依赖。",
            "table：缺少多个对象与同构字段。",
            "formula：没有已确认计算关系。"]


def _affix_columns(text: str) -> tuple[str, str, str]:
    name, body = text.rstrip("。").split("：", 1)
    patterns = (
        (r"^(火焰喷射)(范围.+)$", 1),
        (r"^(雷暴枪)(伤害.+|冷却时间.+)$", 1),
        (r"^(火焰爆炸)(次数.+)$", 1),
        (r"^(火焰喷射)(改为.+)$", 1),
    )
    for pattern, _ in patterns:
        match = re.match(pattern, body)
        if match:
            return name, match.group(1), match.group(2)
    return name, "—", body
