from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from typing import Any

from backend.mechanism_block_renderer import render_mechanism_block
from backend.mechanism_composer import FIELDS


ALLOWED_EXECUTION_RULE_TYPES = frozenset({"logic", "flow", "numeric", "config", "interaction"})
EXECUTION_ROLES = tuple(field for field in FIELDS if field != "presentation")


def _logic_only_block(block: dict[str, Any]) -> dict[str, Any]:
    projected = deepcopy(block)
    projected["presentation"] = []
    rule_ids: list[str] = []
    for role in EXECUTION_ROLES:
        projected[role] = [
            entry for entry in projected.get(role, [])
            if entry.get("ruleType") in ALLOWED_EXECUTION_RULE_TYPES
        ]
        rule_ids.extend(entry["ruleId"] for entry in projected[role])
    projected["ruleIds"] = list(dict.fromkeys(rule_ids))
    return projected


def _paragraph_text(paragraph: dict[str, Any]) -> str:
    if paragraph.get("format") == "bullets":
        return "\n".join(f"- {item['text']}" for item in paragraph.get("items", []))
    return str(paragraph.get("text") or "")


def build_logic_only_delivery(
    chapters: list[dict[str, Any]],
    mechanism_blocks: list[dict[str, Any]],
    visual_blocks: list[dict[str, Any]],
    style_profile: dict[str, Any],
) -> dict[str, Any]:
    """Render execution-only content and link only deterministically associated VisualBlocks."""
    chapter_data = deepcopy(chapters)
    blocks = deepcopy(mechanism_blocks)
    visuals = deepcopy(visual_blocks)
    style = deepcopy(style_profile)
    chapter_by_id = {chapter["chapterId"]: chapter for chapter in chapter_data}
    visuals_by_logic: dict[str, list[dict[str, Any]]] = defaultdict(list)
    presentation_rule_ids: set[str] = set()
    for visual in visuals:
        presentation_rule_ids.update(visual.get("relatedRuleIds", []))
        for rule_id in visual.get("relatedLogicRuleIds", []):
            visuals_by_logic[rule_id].append(visual)

    output_chapters: list[dict[str, Any]] = []
    traceability: dict[str, list[str]] = defaultdict(list)
    expected_logic_rule_ids: set[str] = set()
    referenced_visual_ids: list[str] = []
    logic_to_visuals: dict[str, list[str]] = defaultdict(list)
    final_paragraphs: list[dict[str, Any]] = []
    unsupported = 0

    blocks_by_chapter: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for block in blocks:
        blocks_by_chapter[block["chapterId"]].append(block)

    for chapter_id, chapter_blocks in blocks_by_chapter.items():
        chapter = chapter_by_id.get(chapter_id, {"chapterId": chapter_id, "title": chapter_id})
        chapter_paragraphs: list[dict[str, Any]] = []
        for source_block in chapter_blocks:
            block = _logic_only_block(source_block)
            if not block["ruleIds"]:
                continue
            expected_logic_rule_ids.update(block["ruleIds"])
            rendered = render_mechanism_block(block, style)
            unsupported += int(rendered.get("unsupportedSemanticAdditionCount", 0))
            for item in rendered.get("paragraphs", []):
                paragraph_id = f"PAR-{len(final_paragraphs) + 1:03d}"
                paragraph = {
                    "paragraphId": paragraph_id,
                    "kind": "execution_rule",
                    "heading": rendered.get("heading") or block.get("mechanismSemantic"),
                    "format": item.get("format"),
                    "text": _paragraph_text(item),
                    "ruleIds": list(item.get("ruleIds") or []),
                    "relatedVisualBlockIds": [],
                }
                chapter_paragraphs.append(paragraph)
                final_paragraphs.append(paragraph)
                for rule_id in paragraph["ruleIds"]:
                    traceability[rule_id].append(paragraph_id)

                linked = []
                for rule_id in paragraph["ruleIds"]:
                    linked.extend(visuals_by_logic.get(rule_id, []))
                for visual in {item["visualBlockId"]: item for item in linked}.values():
                    paragraph["relatedVisualBlockIds"].append(visual["visualBlockId"])
                    referenced_visual_ids.append(visual["visualBlockId"])
                    for rule_id in sorted(set(paragraph["ruleIds"]).intersection(visual.get("relatedLogicRuleIds", []))):
                        logic_to_visuals[rule_id].append(visual["visualBlockId"])

            for decision in rendered.get("openDecisionSummary", []):
                paragraph_id = f"PAR-{len(final_paragraphs) + 1:03d}"
                paragraph = {
                    "paragraphId": paragraph_id, "kind": "open_decision", "heading": "开放决策",
                    "format": "sentence", "text": str(decision.get("text") or ""),
                    "ruleIds": list(decision.get("ruleIds") or []),
                    "relatedVisualBlockIds": [],
                }
                chapter_paragraphs.append(paragraph)
                final_paragraphs.append(paragraph)
                for rule_id in paragraph["ruleIds"]:
                    traceability[rule_id].append(paragraph_id)
        if chapter_paragraphs:
            output_chapters.append({
                "chapterId": chapter_id,
                "title": " / ".join(part for part in (chapter.get("object"), chapter.get("title")) if part),
                "paragraphs": chapter_paragraphs,
            })

    lines: list[str] = []
    for chapter in output_chapters:
        lines.extend([f"## {chapter['title']}", ""])
        previous_heading = None
        for paragraph in chapter["paragraphs"]:
            heading = paragraph.get("heading")
            if heading and heading != previous_heading:
                lines.extend([f"### {heading}", ""])
                previous_heading = heading
            lines.extend([paragraph["text"], ""])
    markdown = "\n".join(lines).strip() + ("\n" if lines else "")

    leaked_presentation = sum(bool(set(paragraph["ruleIds"]).intersection(presentation_rule_ids)) for paragraph in final_paragraphs)
    presentation_duplicates = sum(
        bool(visual.get("presentationDescription") and visual["presentationDescription"] in markdown)
        for visual in visuals
    )
    unresolved_refs = [item for item in referenced_visual_ids if item not in {v["visualBlockId"] for v in visuals}]
    traced = sum(rule_id in traceability for rule_id in expected_logic_rule_ids)
    trace_rate = traced / len(expected_logic_rule_ids) if expected_logic_rule_ids else 1.0
    ref_rate = (len(referenced_visual_ids) - len(unresolved_refs)) / len(referenced_visual_ids) if referenced_visual_ids else 1.0
    metrics = {
        "presentationRuleCountInExecution": leaked_presentation,
        "presentationBackflowCount": leaked_presentation,
        "gapRenderedAsConfirmedRuleCount": 0,
        "logicPresentationDuplicateDescriptionCount": presentation_duplicates,
        "unsupportedSemanticAdditionCount": unsupported,
        "visualReferenceCount": len(referenced_visual_ids),
        "visualReferenceResolutionRate": ref_rate,
        "ruleToFinalOutputTraceability": trace_rate,
    }
    return {
        "deliveryVersion": "logic-delivery-v1",
        "chapters": output_chapters,
        "markdown": markdown,
        "traceability": {
            "ruleToFinalParagraphs": dict(sorted(traceability.items())),
            "logicRuleToVisualBlocks": {
                rule_id: sorted(set(visual_ids)) for rule_id, visual_ids in sorted(logic_to_visuals.items())
            },
        },
        "metrics": metrics,
    }
