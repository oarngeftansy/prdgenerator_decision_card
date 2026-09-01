from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from backend.gve16_native_rule_layout import evaluate_layout_quality, reconstruct_native_rule_layouts


ROOT = Path(__file__).resolve().parents[1]
PROJECTIONS = ROOT / "artifacts/planning-content-phase5.7-core-loop-projection-2026-08-17/rule-projections.json"
GROUPS = ROOT / "artifacts/planning-content-phase5.5-game-rule-groups-2026-08-17/game-rule-groups.json"
CHAINS = ROOT / "artifacts/planning-content-phase5.6-gameplay-rule-chains-2026-08-17/gameplay-rule-chains.json"
SCOPED = ROOT / "artifacts/planning-content-phase5.4.4-mechanic-scope-2026-08-17/scoped-game-rule-models.json"
GVE16 = ROOT / "data/quality/gve16-mechanic-structure-corpus-v2.json"
EXTERNAL = ROOT / "data/calibration/external-game-design-corpus.json"
DEFAULT_OUT = ROOT / "artifacts/planning-content-phase5.8-native-rule-layouts-2026-08-17"
PREVIEW = {"V2CH-005": "武器攻击", "V2CH-009": "三选一", "V2CH-015": "怪物攻击", "V2CH-017": "关卡流程"}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _origins(plan: dict[str, Any], indent: str = "") -> list[str]:
    return [f"{indent}- Rule：{', '.join(plan['supportingRuleIds']) or '-'}",
            f"{indent}- Reference：{', '.join(plan['referenceRuleIds']) or '-'}",
            f"{indent}- Missing：{', '.join(plan['missingRuleIds']) or '-'}",
            f"{indent}- Parameter：{', '.join(plan['parameterCarrierIds']) or '-'}",
            f"{indent}- Pattern：`{plan['layoutPatternSource']}`"]


def _preview(plans: list[dict[str, Any]], report: dict[str, Any]) -> str:
    lines = ["# Phase 5.8 GVE16-native Rule Layout Preview", "",
             "> 仅输出栏目结构与来源追溯，不生成完整正文。栏目由当前内容动态实例化，不打印空模板。", ""]
    for owner, chapter_title in PREVIEW.items():
        chapter_plans = [p for p in plans if p["ownerChapter"] == owner]
        if owner == "V2CH-005":
            chapter_plans = [p for p in chapter_plans if p["sectionTitle"] == "攻击规则"]
        lines += [f"## {chapter_title}", ""]
        if not chapter_plans:
            lines += ["- 当前没有可生成的布局。", ""]
            continue
        for plan in chapter_plans:
            lines.append(f"├─ {plan['sectionTitle']}（{plan['layoutMode']}）")
            if plan["subsections"]:
                for subsection in plan["subsections"]:
                    lines += [f"│  ├─ {subsection['title']}",
                              f"│  │  - Rule：{', '.join(subsection['supportingRuleIds']) or '-'}",
                              f"│  │  - Reference：{', '.join(subsection['referenceRuleIds']) or '-'}",
                              f"│  │  - Missing：{', '.join(subsection['missingRuleIds']) or '-'}",
                              f"│  │  - Parameter：{', '.join(subsection['parameterCarrierIds']) or '-'}"]
            else:
                lines += _origins(plan, "│  ")
            lines.append("")
    lines += ["## Layout Quality Gate", "", f"- qualityGate：`{report['qualityGate']}`",
              f"- 空标题：{report['emptyHeadingCount']}", f"- 统一 Schema 痕迹：{report['uniformSchemaTraceCount']}",
              f"- 内部 semantic 标题：{report['internalSemanticHeadingCount']}",
              f"- 过度分层：{report['overDepthCount']}", f"- 一 Rule 一小标题：{report['oneRuleOneHeadingCount']}",
              f"- 自然顺序违规：{report['naturalOrderViolationCount']}",
              f"- GVE16 匿名布局证据覆盖：{report['gve16PatternBackedRate'] * 100:.2f}%", ""]
    return "\n".join(lines)


def generate_phase58(output_dir: Path = DEFAULT_OUT) -> dict[str, Any]:
    sources = [PROJECTIONS, GROUPS, CHAINS, SCOPED, GVE16, EXTERNAL]
    before = {str(path.relative_to(ROOT)): _sha(path) for path in sources}
    projection_set = json.loads(PROJECTIONS.read_text(encoding="utf-8"))
    groups = json.loads(GROUPS.read_text(encoding="utf-8"))
    chains = json.loads(CHAINS.read_text(encoding="utf-8"))
    models = json.loads(SCOPED.read_text(encoding="utf-8"))
    corpora = {"gve16Structure": json.loads(GVE16.read_text(encoding="utf-8")),
               "external": json.loads(EXTERNAL.read_text(encoding="utf-8")),
               "ownerMechanicTypes": {model["chapterId"]: model["mechanicType"] for model in models}}
    plans = reconstruct_native_rule_layouts(projection_set, groups, chains, corpora)
    report = evaluate_layout_quality(plans)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "rule-layout-plans.json").write_text(json.dumps(plans, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "layout-quality-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "four-chapter-layout-preview.md").write_text(_preview(plans, report), encoding="utf-8")
    after = {str(path.relative_to(ROOT)): _sha(path) for path in sources}
    summary = {"phase": "5.8-gve16-native-rule-layout-reconstruction", "layoutCount": len(plans),
               "previewChapterCount": len(PREVIEW), "layoutQualityGate": report["qualityGate"],
               "sourceFilesUnchanged": before == after, "modifiedApprovedRuleCount": 0,
               "modifiedApprovedGapCount": 0, "finalDocumentGenerated": False, "parameterResolverInvoked": False}
    (output_dir / "phase58-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "provenance.json").write_text(json.dumps({"sourceHashes": before, **summary}, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(generate_phase58(), ensure_ascii=False, indent=2))
