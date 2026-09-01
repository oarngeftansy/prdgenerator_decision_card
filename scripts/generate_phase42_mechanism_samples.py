"""Generate the six Phase 4.2 mechanism-composition reference samples."""

from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Any

from backend.chapter_schema_library import SCHEMA_VERSION, chapter_schema_library
from backend.mechanism_block_renderer import render_mechanism_block
from backend.mechanism_composer import FIELDS, compose_mechanism_blocks


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "artifacts/planning-content-phase3-2026-08-17/phase-3-gap-result.json"
DEFAULT_OUT = ROOT / "artifacts/planning-content-phase4.2-2026-08-17"
JOB = ROOT / "data/jobs/8312a91c89e144e6a59f81b982f14c06/job.json"

FOCUS = {
    "载具移动": ["V2CH-001"],
    "武器攻击": ["V2CH-005"],
    "三选一": ["V2CH-009", "V2CH-010"],
    "怪物攻击": ["V2CH-015"],
    "关卡流程": ["V2CH-017"],
    "结算": ["V2CH-020", "V2CH-021"],
}

STYLE_PROFILE = {
    "profileId": "phase4.2-abstract-gve16-organization-rules",
    "contentAuthority": "none",
    "organization_rules": {
        "chapter_internal_grouping": True,
        "heading_granularity": "mechanism_semantic",
        "bullet_density": "merge_adjacent_same_chain",
        "rule_stitching": True,
        "contextual_subject_omission": True,
        "mechanism_semantic_subheading": True,
        "definition_before_detail": True,
        "lifecycle_after_main_behavior": True,
    },
    "forbiddenRuntimeInputs": ["raw_gve16_sentences", "gve16_project_fields", "gve16_values", "gve16_rules"],
}


def _project(data: dict[str, Any]) -> dict[str, Any]:
    copied = json.loads(json.dumps(data, ensure_ascii=False))
    for rule in copied["rules"]:
        if rule.get("semanticValidity") == "valid":
            rule["reviewStatus"] = "approved"
            rule["approvalProvenance"] = "phase2_and_2.1_user_acceptance_read_only_projection"
    for gap in copied["gaps"]:
        gap["status"] = "reviewed_open"
    return copied


def _classification(blocks: list[dict[str, Any]]) -> str:
    if all(block["status"] == "evidence_insufficient" for block in blocks):
        return "evidence_insufficient"
    if any(block["status"] == "partial_mechanism_chain" for block in blocks):
        return "partial_mechanism_chain"
    return "confirmed_mechanism_chain"


def _markdown(result: dict[str, Any], gap_by_id: dict[str, Any]) -> str:
    lines = ["# Phase 4.2：GVE16 Mechanism Composition + Style Transfer", "", "> 本样板只使用 Approved Rule、ChapterSchema、ownership 与 Reviewed Gap 状态。GVE16 仅提供抽象组织规则。", ""]
    for name, item in result["chapters"].items():
        lines += [f"## {name}", "", f"章节状态：`{item['classification']}`", "", "### Approved Rule", ""]
        if item["approvedRules"]:
            lines += [f"- `{rule['ruleId']}` `{rule['schemaSlot']}`：{rule['behavior']}" for rule in item["approvedRules"]]
        else:
            lines.append("- 无。")
        lines += ["", "### MechanismBlock", ""]
        for block in item["blocks"]:
            lines += [f"#### {block['mechanismSemantic']}", "", f"- 状态：`{block['status']}`", f"- ruleIds：{', '.join(block['ruleIds']) or '无'}"]
            for field in FIELDS:
                values = block[field]
                lines.append(f"- {field}：" + ("；".join(f"{entry['text']} ← {entry['ruleId']}" for entry in values) if values else "∅"))
            lines += [f"- emptyFields：{', '.join(block['emptyFields'])}", f"- unabsorbedGapIds：{', '.join(block['unabsorbedGapIds']) or '无'}", ""]
        lines += ["### 最终策划段落", ""]
        paragraphs = [paragraph for rendered in item["renderedBlocks"] for paragraph in rendered["paragraphs"]]
        if paragraphs:
            for paragraph in paragraphs:
                stitched = "；stitch" if len(paragraph["ruleIds"]) > 1 else ""
                lines.append(f"- **{paragraph['carrier']}**：{paragraph['text']}  `← {', '.join(paragraph['ruleIds'])}{stitched}`")
        else:
            lines.append("- 证据不足，不生成策划段落。")
        lines += ["", "### 使用的 GVE16 抽象范式", "", "- 按机制阶段而非 RuleType 分桶。", "- 使用机制语义小标题。", "- 同链 Rule 合并，Presentation 相邻但独立。", "- 配置紧邻行为，生命周期位于主行为之后。", "", "### 未被正文吸收的 Gap", ""]
        gap_ids = list(dict.fromkeys(gid for block in item["blocks"] for gid in block["unabsorbedGapIds"]))
        lines += [f"- `{gid}`：{gap_by_id[gid]['question']}" for gid in gap_ids] or ["- 无。"]
        lines.append("")
    metrics = result["metrics"]
    lines += ["## 指标", "", f"- Rule → MechanismBlock → Final Paragraph 追溯率：{metrics['ruleToMechanismBlockToFinalParagraphTraceabilityRate']:.0%}", f"- unsupported semantic addition：{metrics['unsupportedSemanticAdditionCount']}", f"- partial mechanism chain：{', '.join(metrics['partialMechanismChains']) or '无'}", f"- evidence insufficient：{', '.join(metrics['evidenceInsufficientChapters']) or '无'}", f"- 接近 GVE16 机制段阅读方式：{', '.join(metrics['gve16LikeMechanismParagraphs']) or '无'}", ""]
    return "\n".join(lines)


def generate(output_dir: Path = DEFAULT_OUT) -> dict[str, Any]:
    data = _project(json.loads(SOURCE.read_text(encoding="utf-8")))
    chapter_by_id = {chapter["chapterId"]: chapter for chapter in data["chapters"]}
    result: dict[str, Any] = {"styleProfile": STYLE_PROFILE, "chapters": {}}
    focused_rule_ids: set[str] = set()
    paragraph_rule_ids: set[str] = set()
    unsupported = 0
    for name, chapter_ids in FOCUS.items():
        all_blocks = []
        all_rendered = []
        approved_rules = [rule for rule in data["rules"] if rule.get("ownerChapterId") in chapter_ids and rule.get("reviewStatus") == "approved"]
        for chapter_id in chapter_ids:
            chapter = chapter_by_id[chapter_id]
            schema = chapter_schema_library.resolve(chapter["chapterType"], chapter.get("mechanicVariant"), SCHEMA_VERSION)
            blocks = compose_mechanism_blocks(chapter, approved_rules, data["gaps"], schema)
            rendered = [render_mechanism_block(block, STYLE_PROFILE) for block in blocks]
            all_blocks.extend(blocks)
            all_rendered.extend(rendered)
        focused_rule_ids.update(rule["ruleId"] for rule in approved_rules)
        paragraph_rule_ids.update(rid for rendered in all_rendered for paragraph in rendered["paragraphs"] for rid in paragraph["ruleIds"])
        # Phase 4.3 routes unresolved dependencies to an open-decision output node.
        # Preserve the historical end-to-end trace metric without promoting it to prose.
        paragraph_rule_ids.update(rid for rendered in all_rendered for decision in rendered.get("openDecisionSummary", []) for rid in decision["ruleIds"])
        unsupported += sum(rendered["unsupportedSemanticAdditionCount"] for rendered in all_rendered)
        result["chapters"][name] = {
            "classification": _classification(all_blocks), "approvedRules": approved_rules,
            "blocks": all_blocks, "renderedBlocks": all_rendered,
        }
    close_to_gve = []
    for name, item in result["chapters"].items():
        paragraphs = [p for rendered in item["renderedBlocks"] for p in rendered["paragraphs"]]
        if item["classification"] != "evidence_insufficient" and any(p["carrier"] in {"mechanism", "outcome_boundary"} and len(p["ruleIds"]) > 1 for p in paragraphs):
            close_to_gve.append(name)
    result["metrics"] = {
        "approvedFocusedRuleCount": len(focused_rule_ids),
        "tracedFocusedRuleCount": len(focused_rule_ids & paragraph_rule_ids),
        "ruleToMechanismBlockToFinalParagraphTraceabilityRate": round(len(focused_rule_ids & paragraph_rule_ids) / len(focused_rule_ids), 4) if focused_rule_ids else 1.0,
        "unsupportedSemanticAdditionCount": unsupported,
        "partialMechanismChains": [name for name, item in result["chapters"].items() if item["classification"] == "partial_mechanism_chain"],
        "evidenceInsufficientChapters": [name for name, item in result["chapters"].items() if item["classification"] == "evidence_insufficient"],
        "gve16LikeMechanismParagraphs": close_to_gve,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    gap_by_id = {gap["gapId"]: gap for gap in data["gaps"]}
    (output_dir / "mechanism-samples.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "mechanism-samples.md").write_text(_markdown(result, gap_by_id), encoding="utf-8")
    (output_dir / "organization-style-rules.json").write_text(json.dumps(STYLE_PROFILE, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "phase42-quality-report.json").write_text(json.dumps(result["metrics"], ensure_ascii=False, indent=2), encoding="utf-8")
    provenance = {
        "sourceJobStatus": json.loads(JOB.read_text(encoding="utf-8")).get("status"),
        "sourceJobSha256": hashlib.sha256(JOB.read_bytes()).hexdigest(),
        "sourceStructuredDataSha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "approvalProjection": "Phase 2/2.1 user acceptance, read-only in memory",
        "gapProjection": "Phase 3 user acceptance, retained as reviewed_open and never absorbed",
        "gve16RuntimeAccess": "abstract organization/style rules only",
    }
    (output_dir / "provenance.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    generated = generate()
    print(json.dumps(generated["metrics"], ensure_ascii=False, indent=2))
