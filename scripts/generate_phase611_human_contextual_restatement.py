from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from backend.human_planning_contextual_restatement import (
    build_human_planning_restatements,
    evaluate_human_planning_readability,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "references": ROOT / "artifacts/planning-content-phase6.1-cross-system-references-2026-08-17/cross-system-reference-plans.json",
    "chapterPreviews": ROOT / "artifacts/planning-content-phase6.1-cross-system-references-2026-08-17/chapter-reference-previews.json",
    "rules": ROOT / "artifacts/planning-content-phase3-2026-08-17/phase-3-gap-result.json",
    "expansions": ROOT / "artifacts/planning-content-phase6.0-parameter-integration-2026-08-17/corrected-rule-expansion-plans.json",
    "parameters": ROOT / "artifacts/planning-content-phase6.0-parameter-integration-2026-08-17/parameter-placement-plans.json",
}
OUT = ROOT / "artifacts/planning-content-phase6.1.1-human-context-2026-08-17"
ORDER = ["V2CH-017", "V2CH-009", "V2CH-005", "V2CH-011", "V2CH-018"]


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _human_preview(chapters: list[dict[str, Any]]) -> str:
    by_id = {chapter["chapterId"]: chapter for chapter in chapters}
    lines = ["# Phase 6.1.1 Human Planning Contextual Restatement Preview", "",
             "> 以下为拟进入策划文档的阅读结构；机器引用关系不参与正文措辞。", ""]
    for chapter_id in ORDER:
        chapter = by_id.get(chapter_id)
        if not chapter:
            continue
        lines += [f"## {chapter['chapterTitle']}", ""]
        lines += [f"- {item['text']}" for item in chapter["statements"]]
        lines.append("")
    return "\n".join(lines)


def _audit(chapters: list[dict[str, Any]], reference_plans: list[dict[str, Any]], gate: dict[str, Any]) -> str:
    lines = ["# Phase 6.1.1 Provenance & Readability Audit", "",
             "> 本文件属于机器审计层，内部 ID 不进入 human-readable preview。", ""]
    for chapter in chapters:
        lines += [f"## {chapter['chapterTitle']} ({chapter['chapterId']})", ""]
        for item in chapter["statements"]:
            lines += [f"- `{item['statementId']}` {item['mode']}：{item['text']}",
                      f"  - Rules: {', '.join(item['supportingRuleIds']) or '-'}",
                      f"  - References: {', '.join(item['sourceReferenceIds']) or '-'}"]
        lines.append("")
    lines += ["## Human Planning Readability Gate", "", f"- qualityGate: `{gate['qualityGate']}`",
              f"- duplicated_full_rule_block: {gate['duplicatedFullRuleBlockCount']}",
              f"- contextual_restatement: {gate['contextualRestatementCount']}",
              f"- audit structure leak: {gate['auditStructureLeakCount']}",
              f"- owner/reference language: {gate['ownerReferenceLanguageCount']}",
              f"- relation translation tone: {gate['relationTranslationToneCount']}",
              f"- internal ID leak: {gate['internalIdLeakCount']}",
              f"- standalone readability failure: {gate['standaloneReadabilityFailureCount']}",
              f"- planner plausibility failure: {gate['plannerPlausibilityFailureCount']}", ""]
    return "\n".join(lines)


def generate(output_dir: Path = OUT) -> dict[str, Any]:
    before = {str(path.relative_to(ROOT)): _sha(path) for path in SOURCES.values()}
    references = _load(SOURCES["references"])
    previews = _load(SOURCES["chapterPreviews"])
    rules = _load(SOURCES["rules"])["rules"]
    expansions = _load(SOURCES["expansions"])
    parameters = _load(SOURCES["parameters"])
    reference_hash_before = _sha(SOURCES["references"])
    chapters = build_human_planning_restatements(references, previews, rules, expansions, parameters)
    gate = evaluate_human_planning_readability(chapters)
    reference_hash_after = _sha(SOURCES["references"])
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "human-planning-chapters.json").write_text(
        json.dumps(chapters, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "human-readable-five-chapter-preview.md").write_text(
        _human_preview(chapters), encoding="utf-8")
    (output_dir / "provenance-audit.md").write_text(
        _audit(chapters, references, gate), encoding="utf-8")
    (output_dir / "human-planning-readability-gate.json").write_text(
        json.dumps(gate, ensure_ascii=False, indent=2), encoding="utf-8")
    after = {str(path.relative_to(ROOT)): _sha(path) for path in SOURCES.values()}
    summary = {"phase": "6.1.1-human-planning-contextual-restatement", "chapterCount": len(chapters),
               "statementCount": gate["statementCount"], "contextualRestatementCount": gate["contextualRestatementCount"],
               "qualityGate": gate["qualityGate"], "sourceFilesUnchanged": before == after,
               "crossSystemReferencePlanUnchanged": reference_hash_before == reference_hash_after,
               "modifiedRuleCount": 0, "modifiedScopeCount": 0, "modifiedParameterCount": 0,
               "modifiedPrimaryOwnerCount": 0, "finalDocumentGenerated": False}
    (output_dir / "phase611-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "provenance.json").write_text(json.dumps({"sourceHashes": before, **summary}, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(generate(), ensure_ascii=False, indent=2))
