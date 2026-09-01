from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from backend.cross_system_rule_reference import (
    build_cross_system_chapter_previews,
    build_cross_system_reference_plans,
    evaluate_gve16_cross_system_references,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "projections": ROOT / "artifacts/planning-content-phase5.7-core-loop-projection-2026-08-17/rule-projections.json",
    "chains": ROOT / "artifacts/planning-content-phase5.6-gameplay-rule-chains-2026-08-17/gameplay-rule-chains.json",
    "layouts": ROOT / "artifacts/planning-content-phase5.8-native-rule-layouts-2026-08-17/rule-layout-plans.json",
    "expansions": ROOT / "artifacts/planning-content-phase6.0-parameter-integration-2026-08-17/corrected-rule-expansion-plans.json",
    "parameters": ROOT / "artifacts/planning-content-phase6.0-parameter-integration-2026-08-17/parameter-placement-plans.json",
    "scopes": ROOT / "artifacts/planning-content-phase5.4.4-mechanic-scope-2026-08-17/scoped-game-rule-models.json",
    "rules": ROOT / "artifacts/planning-content-phase3-2026-08-17/phase-3-gap-result.json",
}
OUT = ROOT / "artifacts/planning-content-phase6.1-cross-system-references-2026-08-17"
ORDER = ["V2CH-017", "V2CH-009", "V2CH-005", "V2CH-011", "V2CH-018"]


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _markdown(previews: list[dict[str, Any]], plans: list[dict[str, Any]], gate: dict[str, Any]) -> str:
    by_id = {chapter["chapterId"]: chapter for chapter in previews}
    lines = ["# Phase 6.1 GVE16 Cross-System Rule Reference Preview", "",
             "> 仅展示完整定义、短跨系统衔接和重复定义抑制，不是最终正文。", ""]
    for chapter_id in ORDER:
        chapter = by_id.get(chapter_id)
        if not chapter:
            continue
        lines += [f"## {chapter['chapterTitle']}", "", "### Full definitions", ""]
        lines += ([f"- {item['text']}" for item in chapter["fullDefinitions"]] or ["- 当前没有由本章主定义的已确认 Rule。"])
        lines += ["", "### Short cross-system references", ""]
        lines += ([f"- {item['text']}" for item in chapter["shortCrossSystemReferences"]] or ["- 无。"])
        lines += ["", "### Suppressed duplicated definitions", ""]
        source_plans = [plan for plan in plans if plan["sourceChapter"] == chapter_id and
                        plan["referenceDepth"] != "no_reference_needed"]
        lines += ([f"- 不在本章重复展开“{plan['targetRuleGroup']}”；{plan['referencePurpose']}"
                   for plan in source_plans] or ["- 无重复定义。"])
        suppressed = [plan for plan in plans if plan["sourceChapter"] == chapter_id and
                      plan["referenceDepth"] == "no_reference_needed"]
        lines += [f"- 未生成“{plan['targetRuleGroup']}”引用：当前关系未获 Scope 支持。" for plan in suppressed]
        lines.append("")
    lines += ["## GVE16 Cross-System Gate", "", f"- qualityGate：`{gate['qualityGate']}`",
              f"- 完整规则重复定义：{gate['duplicateFullDefinitionCount']}",
              f"- 必要系统关系缺失：{gate['missingNecessaryRelationshipCount']}",
              f"- 无意义“详见”引用：{gate['meaninglessReferenceCount']}",
              f"- unsupported relation 引用：{gate['unsupportedRelationReferenceCount']}",
              f"- 内部 ID 泄漏：{gate['internalIdLeakCount']}", ""]
    return "\n".join(lines)


def generate(output_dir: Path = OUT) -> dict[str, Any]:
    before = {str(path.relative_to(ROOT)): _sha(path) for path in SOURCES.values()}
    projections = _load(SOURCES["projections"])
    chains = _load(SOURCES["chains"])
    layouts = _load(SOURCES["layouts"])
    expansions = _load(SOURCES["expansions"])
    parameters = _load(SOURCES["parameters"])
    scopes = _load(SOURCES["scopes"])
    rules = _load(SOURCES["rules"])["rules"]
    plans = build_cross_system_reference_plans(
        projections, chains, layouts, expansions, parameters, scopes, rules)
    previews = build_cross_system_chapter_previews(plans, projections, rules, expansions)
    gate = evaluate_gve16_cross_system_references(plans, previews)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "cross-system-reference-plans.json").write_text(
        json.dumps(plans, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "chapter-reference-previews.json").write_text(
        json.dumps(previews, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "cross-system-gate.json").write_text(
        json.dumps(gate, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "five-chapter-reference-preview.md").write_text(
        _markdown(previews, plans, gate), encoding="utf-8")
    after = {str(path.relative_to(ROOT)): _sha(path) for path in SOURCES.values()}
    summary = {"phase": "6.1-gve16-cross-system-rule-reference", "referencePlanCount": len(plans),
               "activeReferenceCount": gate["activeReferenceCount"], "previewChapterCount": len(previews),
               "qualityGate": gate["qualityGate"], "sourceFilesUnchanged": before == after,
               "newMechanicCount": 0, "newScopeCount": 0, "newRuleCount": 0,
               "newGapCount": 0, "newParameterCount": 0, "finalDocumentGenerated": False}
    (output_dir / "phase61-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "provenance.json").write_text(json.dumps({"sourceHashes": before, **summary}, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(generate(), ensure_ascii=False, indent=2))
