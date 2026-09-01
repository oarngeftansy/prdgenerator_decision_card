from __future__ import annotations

import copy
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.gve16_hierarchy_flattening import (
    flatten_mechanic_rule_hierarchy,
    markdown_hierarchy_metrics,
    render_flattened_mechanic_preview,
)
from backend.planning_model import validate_planning_model


P625 = ROOT / "artifacts" / "planning-content-phase6.2.5-mechanic-rule-structuring-2026-08-18"
OUT = ROOT / "artifacts" / "planning-content-phase6.2.6-hierarchy-flattening-2026-08-18"


def _read(name: str):
    return json.loads((P625 / name).read_text(encoding="utf-8"))


def _write(name: str, value) -> None:
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _audit_markdown(flattened: dict, comparison: dict, quality: dict) -> str:
    lines = ["# Phase 6.2.6 GVE16 Hierarchy Flattening Audit", "", "## Before / After", "",
             "| Metric | Before | After |", "|---|---:|---:|"]
    for key in ("headingCount", "maxNestingDepth", "singleRuleHeadingCount", "duplicatedConcreteRuleCount"):
        lines.append(f"| {key} | {comparison['before'][key]} | {comparison['after'][key]} |")
    lines.extend(["", "## Folded headings", ""])
    for item in flattened["flatteningAudit"]["foldedHeadings"]:
        destination = f" → {item['mergedInto']}" if item.get("mergedInto") else ""
        lines.append(f"- {item['chapter']} / {item['removed']}{destination}：{item['reason']}")
    lines.extend(["", "## Deduplicated concrete rules", ""])
    if not flattened["flatteningAudit"]["deduplicatedRules"]:
        lines.append("- 0")
    for item in flattened["flatteningAudit"]["deduplicatedRules"]:
        lines.append(f"- {item['suppressedText']} → {item['coveredByConcreteRule']}")
    lines.extend(["", "## Quality gate", ""])
    for key, value in quality.items():
        lines.append(f"- {key}: {value}")
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    hierarchy = _read("mechanic-rule-hierarchy.json")
    before_preview = (P625 / "human-planning-preview.md").read_text(encoding="utf-8")
    flattened = flatten_mechanic_rule_hierarchy(hierarchy)
    preview = render_flattened_mechanic_preview(flattened)
    comparison = {"before": markdown_hierarchy_metrics(before_preview),
                  "after": markdown_hierarchy_metrics(preview)}
    category_headings = {"触发", "候选", "选择结果", "自动攻击", "攻击方式",
                         "伤害结算", "出现与移动", "接触伤害", "成长规则", "升级结果",
                         "数值强化", "攻击形态", "复合效果"}
    sections = [section for chapter in flattened["chapters"] for section in chapter["sections"]]
    unjustified_single = sum(
        sum(1 + len(item.get("subrules", [])) for item in section["items"]) == 1
        and section["headingRetentionReason"] not in {"independent_submechanic"}
        for section in sections
    )
    quality = {
        "lostRuleSemanticCount": len(flattened["semanticCoverage"]["lostDimensionIds"]),
        "unjustifiedSingleRuleHeadingCount": unjustified_single,
        "redundantNestedHeadingCount": preview.count("#### "),
        "semanticCategoryAsHeadingCount": sum(section["title"] in category_headings for section in sections),
        "repeatedRuleAcrossCategoriesCount": comparison["after"]["duplicatedConcreteRuleCount"],
        "headingMoreVerboseThanContentCount": sum(
            len(section["title"]) > len(section["items"][0]["text"])
            for section in sections if len(section["items"]) == 1),
        "internalIdLeakCount": sum(token in preview for token in ("RSC-", "RULE-", "SYN-", "GAP-", "MB-", "VIS-")),
        "approvedRuleWrites": 0,
        "approvedGapWrites": 0,
    }
    quality["pass"] = all(value == 0 for key, value in quality.items() if key != "pass")
    _write("flattened-mechanic-rule-hierarchy.json", flattened)
    _write("hierarchy-comparison.json", comparison)
    _write("phase626-quality-gate.json", quality)
    (OUT / "human-planning-preview.md").write_text(preview, encoding="utf-8")
    (OUT / "hierarchy-flattening-audit.md").write_text(
        _audit_markdown(flattened, comparison, quality), encoding="utf-8")

    planning_model = copy.deepcopy(_read("gve16-planning-model.json"))
    planning_model.setdefault("extensions", {}).update({
        "phase": "6.2.6",
        "flattenedHierarchyArtifact": "flattened-mechanic-rule-hierarchy.json",
        "humanPlanningPreviewArtifact": "human-planning-preview.md",
        "approvedWriteBack": False,
    })
    errors = validate_planning_model(planning_model)
    if errors:
        raise ValueError(f"invalid GVE16 planning model: {errors}")
    _write("gve16-planning-model.json", planning_model)
    _write("provenance.json", {"phase625Source": str(P625.resolve()),
            "transformation": "hierarchy-only; rule semantics conserved",
            "approvedRuleWrites": 0, "approvedGapWrites": 0,
            "historicalArtifactsMutated": False})


if __name__ == "__main__":
    main()
