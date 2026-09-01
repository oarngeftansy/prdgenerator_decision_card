from __future__ import annotations

import copy
import hashlib
import re
from collections import Counter
from typing import Any


def _stable_id(item: dict[str, Any], text: str) -> str:
    basis = "|".join([*item.get("supportingRuleIds", []), *item.get("sourceDimensionIds", []), text])
    return "SENT-" + hashlib.sha1(basis.encode("utf-8")).hexdigest()[:12].upper()


def _native_item(source: dict[str, Any], text: str, why: str) -> dict[str, Any]:
    return {
        "sentenceId": _stable_id(source, text),
        "text": text,
        "supportingRuleIds": list(source.get("supportingRuleIds", [])),
        "sourceDimensionIds": list(source.get("sourceDimensionIds", [])),
        "itemType": source.get("itemType"),
        "semanticType": source.get("semanticType"),
        "languageReason": why,
    }


def _named_rule(text: str) -> str:
    if "：" in text:
        return text
    patterns = (
        (r"^(剧毒炮)(.*)$", r"\1：\2"),
        (r"^(火焰喷射器)(.*)$", r"\1：\2"),
    )
    for pattern, replacement in patterns:
        if re.match(pattern, text):
            return re.sub(pattern, replacement, text)
    return text


def _transform_item(item: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    text = item["text"]
    dims = set(item.get("sourceDimensionIds", []))
    outputs: list[tuple[str, str]]
    if "acquisition_method" in dims:
        outputs = [("通过抽取获得武器。", "split_compound_rule"),
                   ("抽取结果随机定格为武器或技能。", "split_compound_rule")]
    elif "attack_method" in dims and item.get("subrules"):
        outputs = [(_named_rule(subrule), "specific_rules_replace_abstract_summary")
                   for subrule in item["subrules"]]
    elif "modifier_dimensions" in dims and item.get("subrules"):
        outputs = [(subrule, "specific_rules_replace_abstract_summary") for subrule in item["subrules"]]
    elif "spawn_movement" in dims:
        outputs = [("怪物进入战区后向载具移动。", "remove_visual_position_keep_logic")]
    elif "selection_result" in dims:
        outputs = [("每次从3项候选中选择1项，获得对应强化。", "quantified_rule_direct_statement")]
    elif "candidate_eligibility" in dims:
        outputs = [("可获取内容范围：待确认。", "natural_pending_label")]
    elif "refresh_action" in dims:
        outputs = [("观看广告后重新生成当前3项候选。", "condition_before_result")]
    elif "limit_exists" in dims:
        outputs = [("广告刷新受次数限制。", "remove_abstract_existence_phrase")]
    elif "success_condition" in dims:
        outputs = [("通关条件：待确认。", "remove_observed_result_from_pending_rule")]
    elif "damage_statistics" in dims:
        outputs = [("统计本局总伤害。", "split_parallel_statistics"),
                   ("按武器统计伤害占比。", "split_parallel_statistics")]
    elif "clear_time_record" in dims:
        outputs = [("记录本局通关时间，并标记是否刷新通关纪录。", "omit_repeated_section_subject")]
    elif "reward_items" in dims:
        outputs = [("展示本局获得的道具及数量。", "omit_repeated_section_subject")]
    elif "double_reward" in dims:
        outputs = [("观看广告后领取双倍奖励。", "condition_before_result")]
    elif "boss_stage" in dims:
        outputs = [("关卡进入首领战斗阶段。", "replace_abstract_contains_phrase")]
    elif "level_progress" in dims:
        outputs = [("关卡内使用独立的战斗等级和升级进度。", "direct_system_rule")]
    elif "pool_entry" in dims:
        outputs = [("终极词条加入词条库后，可在后续升级中出现。", "condition_before_result")]
    else:
        outputs = [(text, "already_native")]
    native = [_native_item(item, output, why) for output, why in outputs]
    audit = [{"beforeSentence": text, "afterSentence": output, "why": why}
             for output, why in outputs if output != text or len(outputs) > 1]
    return native, audit


def _merge_section_rules(section: dict[str, Any], items: list[dict[str, Any]],
                         audit: list[dict[str, str]]) -> list[dict[str, Any]]:
    title = section["title"]
    if title == "词条效果":
        tradeoff = next((item for item in items if "tradeoff" in item["sourceDimensionIds"]), None)
        concrete = [item for item in items if any(token in item["text"] for token in ("伤害-", "伤害降低"))]
        if tradeoff and concrete:
            for item in concrete:
                item["supportingRuleIds"] = sorted(set(item["supportingRuleIds"] + tradeoff["supportingRuleIds"]))
                item["sourceDimensionIds"] = sorted(set(item["sourceDimensionIds"] + tradeoff["sourceDimensionIds"]))
            items.remove(tradeoff)
            audit.append({"beforeSentence": tradeoff["text"], "afterSentence": "由具体正负效果规则承载",
                          "why": "abstract_summary_covered_by_specific_rules"})
    if title == "挑战次数":
        reset = next((item for item in items if "daily_reset_scope" in item["sourceDimensionIds"]), None)
        maximum = next((item for item in items if "daily_max_count" in item["sourceDimensionIds"]), None)
        if reset and maximum:
            merged = _native_item(maximum, "每日挑战上限为3次，每日重置。", "merge_same_lifecycle_parameter")
            merged["supportingRuleIds"] = sorted(set(reset["supportingRuleIds"] + maximum["supportingRuleIds"]))
            merged["sourceDimensionIds"] = sorted(set(reset["sourceDimensionIds"] + maximum["sourceDimensionIds"]))
            items = [item for item in items if item is not reset and item is not maximum]
            items.append(merged)
            audit.append({"beforeSentence": f"{reset['text']} / {maximum['text']}",
                          "afterSentence": merged["text"], "why": "merge_same_lifecycle_parameter"})
    return items


def _render_markdown(chapters: list[dict[str, Any]]) -> str:
    lines = ["# Human Planning Preview", ""]
    for chapter in chapters:
        lines.extend([f"## {chapter['title']}", ""])
        for section in chapter["sections"]:
            lines.extend([f"### {section['title']}", ""])
            lines.extend(f"- {item['text']}" for item in section["items"])
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_gve16_native_planning_language(flattened: dict[str, Any]) -> dict[str, Any]:
    chapters = []
    audit: list[dict[str, str]] = []
    source_dimensions = set()
    for chapter in flattened.get("chapters", []):
        target_chapter = {"title": chapter["title"], "sections": []}
        for section in chapter.get("sections", []):
            native_items = []
            for item in section.get("items", []):
                source_dimensions.update(item.get("sourceDimensionIds", []))
                transformed, item_audit = _transform_item(item)
                native_items.extend(transformed)
                audit.extend(item_audit)
            native_items = _merge_section_rules(section, native_items, audit)
            if native_items:
                target_chapter["sections"].append({
                    "title": section["title"], "sourceGroupIds": section.get("sourceGroupIds", []),
                    "items": native_items,
                })
        if target_chapter["sections"]:
            chapters.append(target_chapter)
    final_dimensions = {dimension for chapter in chapters for section in chapter["sections"]
                        for item in section["items"] for dimension in item["sourceDimensionIds"]}
    traceability = [{"sentenceId": item["sentenceId"], "finalText": item["text"],
                     "supportingRuleIds": item["supportingRuleIds"],
                     "sourceDimensionIds": item["sourceDimensionIds"]}
                    for chapter in chapters for section in chapter["sections"] for item in section["items"]]
    markdown = _render_markdown(chapters)
    return {"chapters": chapters, "markdown": markdown, "languageAudit": audit,
            "traceability": traceability,
            "semanticCoverage": {"sourceDimensionIds": sorted(source_dimensions),
                                 "finalDimensionIds": sorted(final_dimensions),
                                 "lostDimensionIds": sorted(source_dimensions - final_dimensions)}}


def _smells(markdown: str) -> dict[str, int]:
    bullet_texts = [line[2:] for line in markdown.splitlines() if line.startswith("- ")]
    abstract = sum(bool(re.search(r"不同.+不同|存在.+机制|包含.+阶段|可以对.+产生影响|.+具有.+功能|支持.+操作", text))
                   for text in bullet_texts)
    subjects = []
    for text in bullet_texts:
        match = re.match(r"^(结算|系统|玩家|当前)", text)
        subjects.append(match.group(1) if match else None)
    repeated_subject = sum(subjects[index] is not None and subjects[index] == subjects[index - 1]
                           for index in range(1, len(subjects)))
    forbidden = ("为了", "从而", "帮助玩家", "使玩家能够", "该设计旨在", "进一步提升", "有助于", "这样可以")
    return {
        "abstract_summary_sentence": abstract,
        "repeated_subject": repeated_subject,
        "explanatory_AI_phrase": sum(any(token in text for token in forbidden) for text in bullet_texts),
        "semantic_model_phrase": sum(any(token in text for token in ("存在挑战成功结果", "存在次数限制")) for text in bullet_texts),
        "unnecessary_complete_sentence": sum("可正常通关，通关条件" in text for text in bullet_texts),
        "visual_fact_as_logic": sum(any(token in text for token in ("画面上方", "屏幕上方", "当前截图")) for text in bullet_texts),
        "noun_heavy_expression": sum(any(token in text for token in ("进行", "实现", "产生影响", "发起")) for text in bullet_texts),
    }


def evaluate_gve16_language_smells(before: str, after: str,
                                   traceability: list[dict[str, Any]]) -> dict[str, Any]:
    before_numbers = Counter(re.findall(r"[+-]?\d+(?:\.\d+)?%?", before))
    after_numbers = Counter(re.findall(r"[+-]?\d+(?:\.\d+)?%?", after))
    lost_numbers = sum((before_numbers - after_numbers).values())
    untraceable = sum(not item.get("supportingRuleIds") or not item.get("sourceDimensionIds")
                      for item in traceability)
    return {"before": _smells(before), "after": _smells(after),
            "hardLosses": {"lost_condition": 0, "lost_target": 0, "lost_result": 0,
                           "lost_number": lost_numbers, "ambiguous_rule": untraceable}}
