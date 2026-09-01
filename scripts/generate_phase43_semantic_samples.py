"""Generate Phase 4.3 six-chapter semantic-role and final-carrier samples."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from backend.chapter_schema_library import SCHEMA_VERSION, chapter_schema_library
from backend.mechanism_block_renderer import render_mechanism_block
from backend.mechanism_composer import FIELDS, compose_mechanism_blocks


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "artifacts/planning-content-phase3-2026-08-17/phase-3-gap-result.json"
OLD = ROOT / "artifacts/planning-content-phase4.2-2026-08-17/mechanism-samples.json"
JOB = ROOT / "data/jobs/8312a91c89e144e6a59f81b982f14c06/job.json"
DEFAULT_OUT = ROOT / "artifacts/planning-content-phase4.3-2026-08-17"

FOCUS = {
    "载具移动": ["V2CH-001"], "武器攻击": ["V2CH-005"],
    "三选一": ["V2CH-009", "V2CH-010"], "怪物攻击": ["V2CH-015"],
    "关卡流程": ["V2CH-017"], "结算": ["V2CH-020", "V2CH-021"],
}

STYLE = {
    "contentAuthority": "none",
    "organization_rules": {
        "contextual_subject_omission": True, "parallel_rules": "bullets",
        "strict_confirmed_sequence": "numbered", "repeated_configuration_fields": "table",
        "unresolved_dependency": "open_decision_summary",
    },
    "forbiddenRuntimeInputs": ["raw_gve16_sentences", "gve16_project_fields", "gve16_values", "gve16_rules"],
}


def _project(data: dict[str, Any]) -> dict[str, Any]:
    copied = json.loads(json.dumps(data, ensure_ascii=False))
    for rule in copied["rules"]:
        if rule.get("semanticValidity") == "valid":
            rule["reviewStatus"] = "approved"
    for gap in copied["gaps"]:
        gap["status"] = "reviewed_open"
    return copied


def _old_roles() -> dict[str, str]:
    old = json.loads(OLD.read_text(encoding="utf-8"))
    roles: dict[str, str] = {}
    old_fields = ("definition", "trigger", "condition", "processing", "state_change", "result", "exit_or_boundary", "presentation", "config_reference")
    for chapter in old["chapters"].values():
        for block in chapter["blocks"]:
            for role in old_fields:
                for entry in block.get(role, []):
                    roles.setdefault(entry["ruleId"], role)
    return roles


def _primary_assignments(blocks: list[dict[str, Any]], behavior_by_id: dict[str, str]) -> dict[str, dict[str, Any]]:
    assignments = {}
    for block in blocks:
        for role in FIELDS:
            for entry in block.get(role, []):
                rid = entry["ruleId"]
                if entry.get("text") == behavior_by_id.get(rid) or rid not in assignments:
                    assignments[rid] = entry
    return assignments


def _render_final(chapters: dict[str, Any]) -> tuple[str, set[str], int, int, int]:
    lines = ["# Phase 4.3 六章机制正文样板", "", "> 仅使用已批准规则；未解决依赖与开放问题不写入确认正文。", ""]
    traced: set[str] = set()
    units = one_rule_units = stitched_sentences = semicolon_stitches = 0
    for name, item in chapters.items():
        status_label = {"partial_mechanism_chain": "信息不完整", "evidence_insufficient": "证据不足", "confirmed_mechanism_chain": "已确认"}[item["classification"]]
        lines += [f"## {name}", "", f"章节状态：{status_label}", ""]
        wrote = False
        for rendered in item["renderedBlocks"]:
            if rendered["paragraphs"] or rendered["openDecisionSummary"]:
                lines += [f"### {rendered['heading']}", ""]
            for section in rendered["paragraphs"]:
                wrote = True
                traced.update(section["ruleIds"])
                if section["format"] == "sentence":
                    lines += [section["text"], ""]
                    units += 1
                    one_rule_units += int(len(section["ruleIds"]) == 1)
                    if len(section["ruleIds"]) > 1:
                        stitched_sentences += 1
                        semicolon_stitches += int("；" in section["text"])
                elif section["format"] == "numbered":
                    for index, entry in enumerate(section["items"], 1):
                        lines.append(f"{index}. {entry['text']}")
                        traced.update(entry["ruleIds"])
                        units += 1
                        one_rule_units += int(len(entry["ruleIds"]) == 1)
                    lines.append("")
                else:
                    for entry in section["items"]:
                        lines.append(f"- {entry['text']}")
                        traced.update(entry["ruleIds"])
                        units += 1
                        one_rule_units += int(len(entry["ruleIds"]) == 1)
                    lines.append("")
            if rendered["openDecisionSummary"]:
                lines += ["**开放决策摘要**", ""]
                for decision in rendered["openDecisionSummary"]:
                    lines.append(f"- {decision['text']}（具体内容与执行方式仍待确认）")
                    traced.update(decision["ruleIds"])
                    units += 1
                    one_rule_units += int(len(decision["ruleIds"]) == 1)
                lines.append("")
        if not wrote and item["classification"] == "evidence_insufficient":
            lines += ["证据不足，当前不生成执行正文。", ""]
        gap_count = len({gid for block in item["blocks"] for gid in block.get("unabsorbedGapIds", [])})
        if gap_count:
            lines += [f"> 本章另有 {gap_count} 项开放问题，保留在审核层。", ""]
    return "\n".join(lines), traced, units, one_rule_units, (stitched_sentences, semicolon_stitches)


def _audit_markdown(audit: list[dict[str, Any]]) -> str:
    lines = ["# Phase 4.2 → 4.3 Role Audit", "", "| ruleId | oldRole | newRole | roleAssignmentReason | resolution_status |", "|---|---|---|---|---|"]
    lines += [f"| {item['ruleId']} | {item['oldRole']} | {item['newRole']} | {item['roleAssignmentReason']} | {item['resolution_status']} |" for item in audit]
    return "\n".join(lines) + "\n"


def generate(output_dir: Path = DEFAULT_OUT) -> dict[str, Any]:
    data = _project(json.loads(SOURCE.read_text(encoding="utf-8")))
    old_roles = _old_roles()
    chapter_by_id = {chapter["chapterId"]: chapter for chapter in data["chapters"]}
    result: dict[str, Any] = {"chapters": {}, "roleAudit": []}
    focused_rules = []
    all_blocks = []
    unsupported = 0
    for name, chapter_ids in FOCUS.items():
        blocks = []
        rendered = []
        rules = [rule for rule in data["rules"] if rule.get("ownerChapterId") in chapter_ids and rule.get("reviewStatus") == "approved"]
        focused_rules.extend(rules)
        for chapter_id in chapter_ids:
            chapter = chapter_by_id[chapter_id]
            schema = chapter_schema_library.resolve(chapter["chapterType"], chapter.get("mechanicVariant"), SCHEMA_VERSION)
            current = compose_mechanism_blocks(chapter, rules, data["gaps"], schema)
            blocks.extend(current)
            rendered.extend(render_mechanism_block(block, STYLE) for block in current)
        all_blocks.extend(blocks)
        unsupported += sum(item["unsupportedSemanticAdditionCount"] for item in rendered)
        if all(block["status"] == "evidence_insufficient" for block in blocks):
            classification = "evidence_insufficient"
        elif any(block["status"] == "partial_mechanism_chain" for block in blocks):
            classification = "partial_mechanism_chain"
        else:
            classification = "confirmed_mechanism_chain"
        result["chapters"][name] = {"classification": classification, "rules": rules, "blocks": blocks, "renderedBlocks": rendered}

    behavior_by_id = {rule["ruleId"]: rule["behavior"] for rule in focused_rules}
    assignments = _primary_assignments(all_blocks, behavior_by_id)
    for rule in focused_rules:
        entry = assignments[rule["ruleId"]]
        result["roleAudit"].append({
            "ruleId": rule["ruleId"], "oldRole": old_roles.get(rule["ruleId"], "unassigned"),
            "newRole": entry["semanticRole"], "roleAssignmentReason": entry["roleAssignmentReason"],
            "resolution_status": entry["resolutionStatus"],
        })

    final_markdown, traced, units, one_rule_units, stitch_counts = _render_final(result["chapters"])
    stitched_sentences, semicolon_stitches = stitch_counts
    focused_ids = {rule["ruleId"] for rule in focused_rules}
    internal_labels = ("mechanism", "presentation", "config_reference")
    title_groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for block in all_blocks:
        title_groups.setdefault((block["chapterId"], block["mechanismSemantic"]), []).append(block)
    conflicts = sum(1 for blocks in title_groups.values() if len({(block.get("owner"), block.get("compatibleRoleDomain")) for block in blocks}) > 1)
    metrics = {
        "semanticRoleCorrectionCount": sum(1 for item in result["roleAudit"] if item["oldRole"] != item["newRole"]),
        "unresolvedDependencyCount": sum(1 for item in result["roleAudit"] if item["resolution_status"] == "unresolved_dependency"),
        "synonymousBlockMergeCount": sum(block.get("synonymousBlockMergeCount", 0) for block in all_blocks),
        "roleConflictCount": conflicts + sum(len(block.get("roleConflicts", [])) for block in all_blocks),
        "finalMarkdownInternalTypeLabelCount": sum(final_markdown.count(label) for label in internal_labels),
        "unsupportedSemanticAdditionCount": unsupported,
        "ruleToRoleToBlockToFinalParagraphTraceabilityRate": round(len(focused_ids & traced) / len(focused_ids), 4) if focused_ids else 1.0,
        "oneRuleOneSentenceRatio": round(one_rule_units / units, 4) if units else 0.0,
        "semicolonStitchingRatio": round(semicolon_stitches / stitched_sentences, 4) if stitched_sentences else 0.0,
        "focusedRuleCount": len(focused_ids), "tracedRuleCount": len(focused_ids & traced),
    }
    result["metrics"] = metrics
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "six-chapter-final.md").write_text(final_markdown, encoding="utf-8")
    (output_dir / "mechanism-role-blocks.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "role-audit.json").write_text(json.dumps(result["roleAudit"], ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "role-audit.md").write_text(_audit_markdown(result["roleAudit"]), encoding="utf-8")
    (output_dir / "phase43-quality-report.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    provenance = {
        "sourceJobStatus": json.loads(JOB.read_text(encoding="utf-8")).get("status"),
        "sourceJobSha256": hashlib.sha256(JOB.read_bytes()).hexdigest(),
        "sourceStructuredDataSha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "phase42BaselineSha256": hashlib.sha256(OLD.read_bytes()).hexdigest(),
        "gve16RuntimeAccess": "abstract organization/style rules only",
    }
    (output_dir / "provenance.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps(generate()["metrics"], ensure_ascii=False, indent=2))
