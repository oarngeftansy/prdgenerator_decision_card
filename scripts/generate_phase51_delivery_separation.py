from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from backend.logic_delivery import build_logic_only_delivery
from backend.visual_delivery import LOGIC_RULE_TYPES, build_visual_blocks


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "artifacts/planning-content-phase3-2026-08-17/phase-3-gap-result.json"
PHASE43_BLOCKS = ROOT / "artifacts/planning-content-phase4.3-2026-08-17/mechanism-role-blocks.json"
PHASE43_TEXT = ROOT / "artifacts/planning-content-phase4.3-2026-08-17/six-chapter-final.md"
ENTITY_GRAPH = ROOT / "artifacts/planning-content-phase5-2026-08-17/entity-graph.json"
JOB = ROOT / "data/jobs/8312a91c89e144e6a59f81b982f14c06/job.json"
DEFAULT_OUT = ROOT / "artifacts/planning-content-phase5.1-2026-08-17"

FOCUS = {
    "载具移动": ["V2CH-001"],
    "武器攻击": ["V2CH-005"],
    "三选一": ["V2CH-009", "V2CH-010"],
    "怪物攻击": ["V2CH-015"],
    "关卡": ["V2CH-017"],
    "结算": ["V2CH-020", "V2CH-021"],
}
PHASE43_NAME = {"关卡": "关卡流程"}
STYLE = {"organization_rules": {"contextual_subject_omission": True}}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _project_rules(source: dict[str, Any]) -> list[dict[str, Any]]:
    rules = json.loads(json.dumps(source["rules"], ensure_ascii=False))
    for rule in rules:
        if rule.get("semanticValidity") == "valid":
            rule["reviewStatus"] = "approved"
    return rules


def _evidence_index(job: dict[str, Any]) -> dict[str, Any]:
    screenshots = {}
    index: dict[str, Any] = {"screenshots": screenshots}
    for frame in job.get("frames", []):
        screenshot_id = frame.get("id")
        if not screenshot_id or not frame.get("imageUrl"):
            continue
        screenshots[screenshot_id] = {
            "kind": "screenshot", "imageUrl": frame["imageUrl"],
            "sourceName": frame.get("sourceName"), "sequenceIndex": frame.get("sequenceIndex"),
            "screen": "", "state": "",
        }
        index[screenshot_id] = {"screenshotIds": [screenshot_id]}
    return index


def _old_section(markdown: str, name: str) -> str:
    pattern = rf"(?ms)^## {re.escape(name)}\s*$\n(.*?)(?=^## |\Z)"
    match = re.search(pattern, markdown)
    return match.group(1).strip() if match else ""


def _logic_text(delivery: dict[str, Any], chapter_ids: list[str]) -> str:
    lines = []
    for chapter in delivery["chapters"]:
        if chapter["chapterId"] not in chapter_ids:
            continue
        lines.append(f"#### {chapter['title']}")
        for paragraph in chapter["paragraphs"]:
            lines.append(paragraph["text"])
        lines.append("")
    return "\n".join(lines).strip() or "证据不足，当前不生成 Logic-only 执行正文。"


def _comparison(
    phase43_markdown: str,
    delivery: dict[str, Any],
    visual_blocks: list[dict[str, Any]],
    presentation_by_id: dict[str, dict[str, Any]],
) -> str:
    lines = ["# Phase 5.1 六章 Logic / Presentation 交付分离对比", ""]
    for name, chapter_ids in FOCUS.items():
        old_name = PHASE43_NAME.get(name, name)
        chapter_visuals = [
            block for block in visual_blocks
            if presentation_by_id[block["relatedRuleIds"][0]].get("ownerChapterId") in chapter_ids
        ]
        lines += [f"## {name}", "", "### Phase 4.3 正文", "", _old_section(phase43_markdown, old_name) or "无正文。", "", "### Phase 5.1 Logic-only 正文", "", _logic_text(delivery, chapter_ids), "", "### VisualBlock", ""]
        if chapter_visuals:
            for block in chapter_visuals:
                logic = "、".join(block["relatedLogicRuleIds"]) or "无确定性 Logic 关联"
                screenshots = "、".join(block["sourceScreenshotIds"]) or "无真实截图索引"
                lines += [f"- `{block['visualBlockId']}`：{block['presentationDescription']}", f"  - Entity：{'、'.join(block['relatedEntityIds'])}", f"  - Logic：{logic}", f"  - Screenshot：{screenshots}"]
        else:
            lines.append("- 本章没有 Presentation Rule。")
        lines.append("")
    return "\n".join(lines)


def generate_phase51_artifacts(output_dir: Path = DEFAULT_OUT) -> dict[str, Any]:
    before = {path: _sha(path) for path in (SOURCE, PHASE43_BLOCKS, PHASE43_TEXT, ENTITY_GRAPH, JOB)}
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    phase43 = json.loads(PHASE43_BLOCKS.read_text(encoding="utf-8"))
    graph = json.loads(ENTITY_GRAPH.read_text(encoding="utf-8"))
    job = json.loads(JOB.read_text(encoding="utf-8"))
    rules = _project_rules(source)
    presentations = [rule for rule in rules if rule.get("ruleType") == "presentation" and rule.get("reviewStatus") == "approved"]
    logic_rules = [rule for rule in rules if rule.get("ruleType") in LOGIC_RULE_TYPES and rule.get("reviewStatus") == "approved"]
    visual_blocks = build_visual_blocks(presentations, logic_rules, graph, _evidence_index(job))

    mechanism_blocks = [block for chapter in phase43["chapters"].values() for block in chapter["blocks"]]
    focus_chapter_ids = {chapter_id for ids in FOCUS.values() for chapter_id in ids}
    chapters = [chapter for chapter in source["chapters"] if chapter["chapterId"] in focus_chapter_ids]
    delivery = build_logic_only_delivery(chapters, mechanism_blocks, visual_blocks, STYLE)
    presentation_by_id = {rule["ruleId"]: rule for rule in presentations}

    visual_with_logic = [block for block in visual_blocks if block["relatedLogicRuleIds"]]
    deterministic_links = sum(len(block["relatedLogicRuleIds"]) for block in visual_blocks)
    visual_rule_ids = {rule_id for block in visual_blocks for rule_id in block["relatedRuleIds"]}
    valid_entity_ids = {entity["entityId"] for entity in graph["entities"]}
    resolved_visuals = sum(bool(block["relatedEntityIds"]) and set(block["relatedEntityIds"]).issubset(valid_entity_ids) for block in visual_blocks)
    metrics = {
        "focusChapterCount": len(FOCUS),
        "presentationRuleCount": len(presentations),
        "visualBlockCount": len(visual_blocks),
        "presentationToVisualBlockCoverage": round(len(visual_rule_ids) / len(presentations), 4) if presentations else 1.0,
        "visualBlockEntityResolutionRate": round(resolved_visuals / len(visual_blocks), 4) if visual_blocks else 1.0,
        "visualBlockLogicDeterministicAssociationCount": len(visual_with_logic),
        "deterministicLogicLinkCount": deterministic_links,
        "emptyRelatedLogicRuleVisualBlockCount": len(visual_blocks) - len(visual_with_logic),
        "presentationBackflowCount": delivery["metrics"]["presentationBackflowCount"],
        "presentationRuleCountInExecution": delivery["metrics"]["presentationRuleCountInExecution"],
        "logicPresentationDuplicateDescriptionCount": delivery["metrics"]["logicPresentationDuplicateDescriptionCount"],
        "gapRenderedAsConfirmedRuleCount": delivery["metrics"]["gapRenderedAsConfirmedRuleCount"],
        "unsupportedSemanticAdditionCount": delivery["metrics"]["unsupportedSemanticAdditionCount"],
        "visualReferenceResolutionRate": delivery["metrics"]["visualReferenceResolutionRate"],
        "ruleToFinalOutputTraceability": delivery["metrics"]["ruleToFinalOutputTraceability"],
    }
    metrics["hardGatesPassed"] = all(metrics[key] == 0 for key in (
        "presentationBackflowCount", "presentationRuleCountInExecution",
        "gapRenderedAsConfirmedRuleCount", "unsupportedSemanticAdditionCount",
    )) and metrics["ruleToFinalOutputTraceability"] == 1.0

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "phase51-delivery.json").write_text(json.dumps(delivery, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "logic-only-execution.md").write_text(delivery["markdown"], encoding="utf-8")
    (output_dir / "visual-blocks.json").write_text(json.dumps(visual_blocks, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "quality-report.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "six-chapter-comparison.md").write_text(_comparison(PHASE43_TEXT.read_text(encoding="utf-8"), delivery, visual_blocks, presentation_by_id), encoding="utf-8")
    after = {path: _sha(path) for path in before}
    provenance = {
        "sources": {str(path.relative_to(ROOT)): digest for path, digest in before.items()},
        "allSourceHashesUnchanged": before == after,
        "sourceJobStatus": job.get("status"),
        "modifiedP7Count": 0, "modifiedUiCount": 0, "modifiedEntityGraphCount": 0,
        "modifiedRuleCount": 0, "modifiedGapCount": 0, "modifiedParameterCount": 0,
        "scope": "independent Phase 5.1 delivery reference; no product write-back",
    }
    (output_dir / "provenance.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8")
    return metrics


if __name__ == "__main__":
    print(json.dumps(generate_phase51_artifacts(), ensure_ascii=False, indent=2))
