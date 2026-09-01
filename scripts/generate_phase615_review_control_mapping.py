from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from backend.missing_decision_review_control_mapping import (
    evaluate_review_control_quality,
    map_missing_items_to_review_controls,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "expansions": ROOT / "artifacts/planning-content-phase6.0-parameter-integration-2026-08-17/corrected-rule-expansion-plans.json",
    "parameters": ROOT / "artifacts/planning-content-phase6.0-parameter-integration-2026-08-17/parameter-placement-plans.json",
    "scopeCorrections": ROOT / "artifacts/planning-content-phase6.0-parameter-integration-2026-08-17/scope-corrections.json",
    "rules": ROOT / "artifacts/planning-content-phase3-2026-08-17/phase-3-gap-result.json",
}
OUT = ROOT / "artifacts/planning-content-phase6.1.5-review-controls-2026-08-17"


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _route_label(item: dict[str, Any]) -> str:
    return item["route"]


def _option_text(item: dict[str, Any]) -> str:
    labels = [option["label"] for option in item.get("options", [])]
    if item.get("allowCustom"):
        labels.append("自定义")
    return " / ".join(labels) or "—"


def _dependency_text(item: dict[str, Any], by_id: dict[str, dict[str, Any]]) -> str:
    dependency = item.get("dependency")
    if not dependency:
        return "无"
    parent = by_id.get(dependency["decisionId"], {})
    option = dependency.get("whenOption") or "、".join(dependency.get("whenOptionIn", []))
    option_labels = {option_item["optionId"]: option_item["label"] for option_item in parent.get("options", [])}
    labels = "、".join(option_labels.get(key, key) for key in option.split("、"))
    return f"仅当“{parent.get('question', '前置决策')}”选择“{labels}”后显示"


def _mapping(decisions: list[dict[str, Any]]) -> str:
    by_id = {item["decisionId"]: item for item in decisions}
    lines = ["# Phase 6.1.5 Missing Decision → Review Control Mapping", "",
             "> 内部来源 ID 仅保存在 JSON；本表使用策划可读语言。", "",
             "| Item | Decision Class | Route | UI Control | Candidate Options | Dependency | Why |",
             "|---|---|---|---|---|---|---|"]
    for item in decisions:
        values = [item["question"], item["decisionClass"], _route_label(item), item["uiControl"],
                  _option_text(item), _dependency_text(item, by_id), item["why"]]
        lines.append("| " + " | ".join(value.replace("|", "／").replace("\n", " ") for value in values) + " |")
    lines.append("")
    return "\n".join(lines)


def _p4_preview(decisions: list[dict[str, Any]]) -> str:
    lines = ["# P4 规则审核 · 只读控件示意", "",
             "> 这些控件只收集用户决策；AI 推荐不会自动写入 Approved Rule。", ""]
    for item in [decision for decision in decisions if decision["route"] == "P4"]:
        lines += [f"## {item['question']}", "", f"控件：`{item['uiControl']}`", ""]
        for option in item["options"]:
            marker = "□" if item["decisionClass"] == "multi_select_rule" else "○"
            lines.append(f"{marker} {option['label']}")
        fields = item.get("inputContract", {}).get("fields", [])
        for field in fields:
            lines.append(f"填写：{field['label']} [　　　　　　]")
        if item["allowCustom"] and item["options"]:
            lines.append("○ 自定义")
        lines += ["", f"说明：{item['why']}", "AI 推荐：无（当前证据不足）", ""]
    return "\n".join(lines)


def _p6_preview(decisions: list[dict[str, Any]]) -> str:
    by_id = {item["decisionId"]: item for item in decisions}
    lines = ["# P6 参数审核 · 只读控件示意", "",
             "> P6 只填写已确认存在的参数；依赖的 P4 规则未确认前，条件参数不显示。", ""]
    for item in [decision for decision in decisions if decision["route"] == "P6"]:
        dependency = _dependency_text(item, by_id)
        lines += [f"## {item['question']}", "", f"控件：`{item['uiControl']}`"]
        if dependency != "无":
            lines.append(f"显示条件：{dependency}")
        lines += [f"填写约束：`{json.dumps(item['inputContract'], ensure_ascii=False)}`", ""]
    return "\n".join(lines)


def generate(output_dir: Path = OUT) -> dict[str, Any]:
    before = {str(path.relative_to(ROOT)): _sha(path) for path in SOURCES.values()}
    expansions = _load(SOURCES["expansions"])
    parameters = _load(SOURCES["parameters"])
    corrections = _load(SOURCES["scopeCorrections"])
    rules = _load(SOURCES["rules"])["rules"]
    decisions = map_missing_items_to_review_controls(expansions, parameters, corrections, rules, {}, {})
    gate = evaluate_review_control_quality(decisions)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "review-decisions.json").write_text(json.dumps(decisions, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "missing-to-review-control-mapping.md").write_text(_mapping(decisions), encoding="utf-8")
    (output_dir / "p4-review-controls-preview.md").write_text(_p4_preview(decisions), encoding="utf-8")
    (output_dir / "p6-parameter-controls-preview.md").write_text(_p6_preview(decisions), encoding="utf-8")
    (output_dir / "review-control-quality-gate.json").write_text(json.dumps(gate, ensure_ascii=False, indent=2), encoding="utf-8")
    after = {str(path.relative_to(ROOT)): _sha(path) for path in SOURCES.values()}
    summary = {"phase": "6.1.5-missing-decision-review-control-mapping", "decisionCount": len(decisions),
               "p4DecisionCount": gate["p4DecisionCount"], "p6DecisionCount": gate["p6DecisionCount"],
               "evidenceRecheckCount": gate["evidenceRecheckCount"], "suppressedCount": gate["suppressedCount"],
               "qualityGate": gate["qualityGate"], "sourceFilesUnchanged": before == after,
               "modifiedEightStepFlow": False, "modifiedApprovedRuleCount": 0,
               "modifiedApprovedParameterCount": 0, "finalDocumentGenerated": False}
    (output_dir / "phase615-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "provenance.json").write_text(json.dumps({"sourceHashes": before, **summary}, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(generate(), ensure_ascii=False, indent=2))
