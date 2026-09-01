from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from backend.content_richness_density_calibration import (
    build_content_richness_preview,
    evaluate_content_richness,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "layouts": ROOT / "artifacts/planning-content-phase5.8-native-rule-layouts-2026-08-17/rule-layout-plans.json",
    "expansions": ROOT / "artifacts/planning-content-phase6.0-parameter-integration-2026-08-17/corrected-rule-expansion-plans.json",
    "parameters": ROOT / "artifacts/planning-content-phase6.0-parameter-integration-2026-08-17/parameter-placement-plans.json",
    "scopeCorrections": ROOT / "artifacts/planning-content-phase6.0-parameter-integration-2026-08-17/scope-corrections.json",
    "humanChapters": ROOT / "artifacts/planning-content-phase6.1.1-human-context-2026-08-17/human-planning-chapters.json",
    "decisions": ROOT / "artifacts/planning-content-phase6.1.5-review-controls-2026-08-17/review-decisions.json",
}
OUT = ROOT / "artifacts/planning-content-phase6.2-content-richness-density-2026-08-17"


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _preview_markdown(preview: dict[str, Any]) -> str:
    by_title = {chapter["chapterTitle"]: chapter for chapter in preview["chapters"]}
    lines = ["# Phase 6.2 GVE16 Content Richness & Density Preview", "",
             "> 仅消费 Approved Rule、已支持 Scope 的 ReviewDecision、已观察值和 Gameplay Parameter；不展示审核问题、候选项、Evidence Recheck、Suppress 或内部 ID。", ""]
    structure = [
        ("## 载具移动", ["载具移动"]),
        ("## 武器", []), ("### 武器获取", ["武器获取"]), ("### 武器栏", ["武器栏"]),
        ("### 武器攻击", ["武器攻击"]), ("### 词条", ["词条"]),
        ("## 三选一", ["三选一"]), ("### 刷新", ["刷新"]),
        ("## 怪物攻击", ["怪物攻击"]), ("## 关卡流程", ["关卡流程"]),
        ("## 胜负判定", ["胜负判定"]), ("## 结算", ["结算"]),
    ]
    for heading, titles in structure:
        if titles and not any(title in by_title for title in titles):
            continue
        lines += [heading, ""]
        for title in titles:
            chapter = by_title.get(title)
            if chapter:
                lines += [f"- {item['text']}" for item in chapter["lines"]]
        lines.append("")
    if preview.get("omittedChapters"):
        lines += ["> 注：证据回溯或 Scope 修正后没有可发布规则的章节未展开为空壳正文。", ""]
    return "\n".join(lines)


def _audit_markdown(report: dict[str, Any], preview: dict[str, Any]) -> str:
    lines = ["# Phase 6.2 Content Richness & Density Audit", ""]
    for chapter in report["chapters"]:
        lines += [f"## {chapter['chapterTitle']}", "",
            f"- confirmed_rule_count: {chapter['confirmedRuleCount']}",
            f"- approved_review_rule_count: {chapter['approvedReviewRuleCount']}",
            f"- pending_rule_dimension_count: {chapter['pendingRuleDimensionCount']}",
            f"- gameplay_parameter_count: {chapter['gameplayParameterCount']}",
            f"- cross_system_relation_count: {chapter['crossSystemRelationCount']}",
            f"- concrete_value_count: {chapter['concreteValueCount']}",
            f"- unsupported_dimension_count: {chapter['unsupportedDimensionCount']}",
            f"- Present Rule Dimensions: {', '.join(chapter['presentRuleDimensions']) or '无'}",
            f"- Supported-but-not-rendered Dimensions: {', '.join(chapter['supportedButNotRenderedDimensions']) or '无'}",
            f"- Pending Review Dimensions: {', '.join(chapter['pendingReviewDimensions']) or '无'}",
            f"- Correctly Rejected Dimensions: {', '.join(chapter['correctlyRejectedDimensions']) or '无'}", ""]
    lines += ["## Too Thin", ""]
    lines += [f"- {item['chapterTitle']}：{', '.join(item['dimensions'])}" for item in report["tooThin"]] or ["- 无。"]
    lines += ["", "## Too Verbose", ""]
    lines += [f"- {item['chapterTitle']}：{item['metric']} — {item['text']}" for item in report["tooVerbose"]] or ["- 无。"]
    lines += ["", "## Omitted Empty Chapters", ""]
    lines += [f"- {item['chapterTitle']}：{item['reason']}" for item in preview["omittedChapters"]] or ["- 无。"]
    lines.append("")
    return "\n".join(lines)


def generate(output_dir: Path = OUT) -> dict[str, Any]:
    before = {name: _sha(path) for name, path in SOURCES.items()}
    expansions = _load(SOURCES["expansions"])
    decisions = _load(SOURCES["decisions"])
    parameters = _load(SOURCES["parameters"])
    corrections = _load(SOURCES["scopeCorrections"])
    preview = build_content_richness_preview(
        expansions, decisions, parameters, _load(SOURCES["humanChapters"]), corrections)
    report = evaluate_content_richness(preview, expansions, decisions, corrections)
    if report["densityGate"]["qualityGate"] != "pass":
        raise RuntimeError(f"Density gate failed: {report['densityGate']['findings']}")
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "all-chapter-preview.json").write_text(json.dumps(preview, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "all-chapter-preview.md").write_text(_preview_markdown(preview), encoding="utf-8")
    (output_dir / "content-richness-audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "content-richness-audit.md").write_text(_audit_markdown(report, preview), encoding="utf-8")
    (output_dir / "effective-rule-density.json").write_text(
        json.dumps(report["effectiveRuleDensity"], ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "density-gate.json").write_text(json.dumps(report["densityGate"], ensure_ascii=False, indent=2), encoding="utf-8")
    after = {name: _sha(path) for name, path in SOURCES.items()}
    summary = {"phase": "6.2-gve16-content-richness-density", "renderedChapterCount": len(preview["chapters"]),
        "omittedChapterCount": len(preview["omittedChapters"]), "tooThinChapterCount": len(report["tooThin"]),
        "tooVerboseFindingCount": len(report["tooVerbose"]), "densityGate": report["densityGate"]["qualityGate"],
        "sourceFilesUnchanged": before == after, "modifiedRuleCount": 0, "modifiedScopeCount": 0,
        "modifiedMechanicCount": 0, "modifiedParameterCount": 0, "finalRendererImplemented": False}
    (output_dir / "phase62-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "provenance.json").write_text(json.dumps({"sourceHashes": before, **summary}, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(generate(), ensure_ascii=False, indent=2))
