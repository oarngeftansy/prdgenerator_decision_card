from __future__ import annotations

import copy
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.mechanic_rule_structuring import (
    build_mechanic_rule_hierarchy,
    count_internal_vocabulary_leaks,
    render_mechanic_rule_preview,
)
from backend.planning_model import validate_planning_model


P624 = ROOT / "artifacts" / "planning-content-phase6.2.4-instance-value-gate-2026-08-18"
OUT = ROOT / "artifacts" / "planning-content-phase6.2.5-mechanic-rule-structuring-2026-08-18"


def _read(name: str):
    return json.loads((P624 / name).read_text(encoding="utf-8"))


def _write(name: str, value) -> None:
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _all_items(hierarchy: dict):
    for chapter in hierarchy["chapters"]:
        for group in chapter["ruleGroups"]:
            yield from group["items"]
            for subgroup in group["subgroups"]:
                yield from subgroup["items"]


def _traceability(hierarchy: dict, preview: str) -> dict:
    source_by_text: dict[str, set[str]] = {}
    dimension_by_text: dict[str, set[str]] = {}
    for item in _all_items(hierarchy):
        texts = [item["text"], *item.get("subrules", [])]
        for text in texts:
            source_by_text.setdefault(text, set()).update(item["supportingRuleIds"])
            dimension_by_text.setdefault(text, set()).update(item["sourceDimensionIds"])
    rows = []
    for raw_line in preview.splitlines():
        stripped = raw_line.strip()
        if not stripped.startswith("- "):
            continue
        text = stripped[2:]
        rows.append({
            "text": text,
            "supportingRuleIds": sorted(source_by_text.get(text, set())),
            "sourceDimensionIds": sorted(dimension_by_text.get(text, set())),
        })
    return {"previewRules": rows,
            "untraceableCount": sum(not row["supportingRuleIds"] or not row["sourceDimensionIds"] for row in rows)}


def _audit_markdown(hierarchy: dict) -> str:
    lines = ["# Phase 6.2.5 Mechanic Rule Structuring Audit", "",
             "本阶段只组织 Phase 6.2.4 已通过 Gate 的规则与待审核维度；不新增 Evidence、Rule、Gap 或参数答案。", ""]
    for chapter in hierarchy["chapters"]:
        lines.extend([f"## {chapter['title']}", ""])
        for group in chapter["ruleGroups"]:
            lines.append(f"- {group['title']}：{group['synthesisLevel']}")
            for subgroup in group["subgroups"]:
                lines.append(f"  - {subgroup['title']} ← {', '.join(subgroup['sourceDimensionIds'])}")
        lines.append("")
    lines.extend(["## Richness metrics", ""])
    for key, value in hierarchy["metrics"].items():
        lines.append(f"- {key}: {value}")
    return "\n".join(lines).rstrip() + "\n"


def _worthiness_markdown(audit: dict) -> str:
    reason_labels = {
        "default_damage_semantics_without_special_rule": "未发现护盾、减伤、倍率或伤害转移等特殊受击规则，属于默认语义",
        "defines_numeric_or_quantified_rule": "定义了会影响玩法的数值或数量关系",
        "actionable_review_dimension": "已确认机制所需的可操作审核项",
        "defines_gameplay_outcome_or_transition": "定义玩法结果或状态转换",
        "defines_attack_trigger_and_cross_entity_effect": "定义攻击触发条件及对另一对象的影响",
        "defines_system_transition_or_cross_system_relation": "定义系统衔接或跨系统结果",
        "project_specific_confirmed_rule": "当前项目已确认的具体玩法规则",
    }
    lines = ["# Core Rule Worthiness Audit", "", "## Suppressed common-sense rules", ""]
    for item in audit["suppressedCommonSenseRules"]:
        lines.append(f"- {item['text']} — {reason_labels.get(item['reason'], item['reason'])}")
    lines.extend(["", "## Retained basic but meaningful rules", ""])
    for item in audit["retainedBasicButMeaningfulRules"]:
        lines.append(f"- {item['text']} — {reason_labels.get(item['reason'], item['reason'])}")
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    contracts = _read("gated-rule-semantic-contracts.json")["contracts"]
    typed_rules = _read("semantic-typed-synthesized-rules.json")
    core_rules = [item for item in typed_rules if item.get("semanticType") in {
        "persistent_game_rule", "gameplay_parameter"
    }]
    hierarchy = build_mechanic_rule_hierarchy(contracts, core_rules)
    preview = render_mechanic_rule_preview(hierarchy)
    traceability = _traceability(hierarchy, preview)
    suppressed_texts = [item["text"] for item in hierarchy["worthinessAudit"]["suppressedCommonSenseRules"]]
    quality = {
        **hierarchy["qualityGate"],
        "internalVocabularyLeakCount": count_internal_vocabulary_leaks(preview),
        "internalIdLeakCount": sum(token in preview for token in ("RSC-", "RULE-", "SYN-", "GAP-", "MB-", "VIS-")),
        "untraceablePreviewRuleCount": traceability["untraceableCount"],
        "instanceValueLeakCount": sum(value in preview for value in (
            "05:14", "1/1", "3/3", "88.9万", "84.5%", "10.4%", "2.9%", "2.2%", "90.65%")),
        "suppressedCommonSenseRuleInPreview": sum(text in preview for text in suppressed_texts),
        "approvedRuleWrites": 0,
        "approvedGapWrites": 0,
    }
    quality["pass"] = all(value == 0 for key, value in quality.items() if key != "pass")
    _write("mechanic-rule-hierarchy.json", hierarchy)
    _write("preview-rule-traceability.json", traceability)
    _write("phase625-richness-metrics.json", hierarchy["metrics"])
    _write("phase625-quality-gate.json", quality)
    _write("core-rule-worthiness-audit.json", hierarchy["worthinessAudit"])
    (OUT / "human-planning-preview.md").write_text(preview, encoding="utf-8")
    (OUT / "mechanic-rule-structuring-audit.md").write_text(_audit_markdown(hierarchy), encoding="utf-8")
    (OUT / "core-rule-worthiness-audit.md").write_text(
        _worthiness_markdown(hierarchy["worthinessAudit"]), encoding="utf-8")

    planning_model = copy.deepcopy(_read("gve16-planning-model.json"))
    planning_model.setdefault("extensions", {}).update({
        "phase": "6.2.5",
        "mechanicRuleHierarchyArtifact": "mechanic-rule-hierarchy.json",
        "humanPlanningPreviewArtifact": "human-planning-preview.md",
        "coreRuleWorthinessAuditArtifact": "core-rule-worthiness-audit.json",
        "approvedWriteBack": False,
    })
    errors = validate_planning_model(planning_model)
    if errors:
        raise ValueError(f"invalid GVE16 planning model: {errors}")
    _write("gve16-planning-model.json", planning_model)
    _write("provenance.json", {
        "phase624Source": str(P624.resolve()),
        "inputAuthority": "gated RuleSemanticContract only",
        "approvedRuleWrites": 0,
        "approvedGapWrites": 0,
        "historicalArtifactsMutated": False,
    })


if __name__ == "__main__":
    main()
