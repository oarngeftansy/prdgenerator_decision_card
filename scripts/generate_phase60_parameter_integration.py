from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from backend.parameter_config_integration import (
    build_parameter_placement_plans,
    evaluate_gve16_parameter_integration,
    prepare_phase60_inputs,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "expansions": ROOT / "artifacts/planning-content-phase5.9.1-full-expansion-depth-2026-08-17/rule-expansion-plans.json",
    "layouts": ROOT / "artifacts/planning-content-phase5.8-native-rule-layouts-2026-08-17/rule-layout-plans.json",
    "groups": ROOT / "artifacts/planning-content-phase5.5-game-rule-groups-2026-08-17/game-rule-groups.json",
    "scopes": ROOT / "artifacts/planning-content-phase5.4.4-mechanic-scope-2026-08-17/scoped-game-rule-models.json",
    "rules": ROOT / "artifacts/planning-content-phase3-2026-08-17/phase-3-gap-result.json",
}
OUT = ROOT / "artifacts/planning-content-phase6.0-parameter-integration-2026-08-17"
PREVIEW = {"V2CH-005": "武器攻击", "V2CH-009": "三选一", "V2CH-001": "载具移动", "V2CH-017": "关卡流程"}


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _render_value(item: dict[str, Any]) -> str:
    if item["parameterClass"] == "observed_value":
        unit = item.get("unit") or ""
        if isinstance(item.get("observedValue"), str) and unit and unit in item["observedValue"]:
            unit = ""
        return f"{item['displayLabel']}：{item['observedValue']}{unit}（已观察）"
    return f"{item['displayLabel']}：待确认"


def _preview(plans: list[dict[str, Any]], placements: list[dict[str, Any]], corrections: list[dict[str, Any]],
             gate: dict[str, Any]) -> str:
    lines = ["# Phase 6.0 GVE16 Parameter & Config Integration Preview", "",
             "> 仅展示参数嵌入 Rule Layout 后的结构，不是最终策划正文。", ""]
    for owner, title in PREVIEW.items():
        lines += [f"## {title}", ""]
        owner_plans = [plan for plan in plans if plan["ownerChapter"] == owner]
        if owner == "V2CH-005":
            owner_plans = [plan for plan in owner_plans if plan["ruleTopic"] == "攻击规则"]
        for plan in owner_plans:
            lines += [f"### {plan['ruleTopic']}", "",
                      f"- Rule Depth：`{plan['depthStatus']}`",
                      f"- Parameter Completeness：`{plan['parameterCompletenessStatus']}`"]
            for detail in plan.get("confirmedDetails", []):
                lines.append(f"- {detail['text']}")
            for detail in plan.get("missingExecutionDetails", []):
                lines.append(f"- {detail['question']}：待确认")
            attached = [item for item in placements if item["ownerLayout"] == plan["layoutId"]]
            confirmed_rule_ids = {rule_id for detail in plan.get("confirmedDetails", [])
                                  for rule_id in detail.get("sourceRuleIds", [])}
            # Observed values already present in a confirmed Rule stay inline there; do not print them twice.
            visible_parameters = [item for item in attached if not (
                item["parameterClass"] == "observed_value" and
                set(item.get("sourceRuleIds", [])) <= confirmed_rule_ids)]
            lines += [f"  - {_render_value(item)}" for item in visible_parameters]
            lines.append("")
    lines += ["## recorded_data Scope 复核", ""]
    lines += ([f"- {item['chapterId']}：{item['previousStatus']} → {item['correctedStatus']}；{item['reason']}"
               for item in corrections] or ["- 无修正。"])
    lines += ["", "## GVE16 Parameter Integration Gate", "",
              f"- qualityGate：`{gate['qualityGate']}`", f"- 参数总数：{gate['parameterCount']}",
              f"- 无归属参数：{gate['orphanParameterCount']}", f"- 内部字段名：{gate['internalFieldLabelCount']}",
              f"- 无证据配置引用：{gate['unsupportedConfigReferenceCount']}",
              f"- 无证据公式：{gate['unsupportedFormulaCount']}",
              f"- 遗失已观察数值：{gate['lostObservedValueCount']}",
              f"- 无必要表格：{gate['unnecessaryTableCount']}",
              f"- 待确认玩法参数：{gate['unresolvedParameterCount']}", ""]
    return "\n".join(lines)


def generate(output_dir: Path = OUT) -> dict[str, Any]:
    before = {str(path.relative_to(ROOT)): _sha(path) for path in SOURCES.values()}
    expansions = _load(SOURCES["expansions"])
    layouts = _load(SOURCES["layouts"])
    groups = _load(SOURCES["groups"])
    scopes = _load(SOURCES["scopes"])
    rules = _load(SOURCES["rules"])["rules"]
    preflight = prepare_phase60_inputs(expansions, scopes, rules)
    placements = build_parameter_placement_plans(preflight["expansionPlans"], layouts, groups, rules, scopes)
    gate = evaluate_gve16_parameter_integration(placements, rules)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "corrected-rule-expansion-plans.json").write_text(
        json.dumps(preflight["expansionPlans"], ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "scope-corrections.json").write_text(
        json.dumps(preflight["scopeCorrections"], ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "parameter-placement-plans.json").write_text(
        json.dumps(placements, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "parameter-integration-gate.json").write_text(
        json.dumps(gate, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "four-chapter-parameter-preview.md").write_text(
        _preview(preflight["expansionPlans"], placements, preflight["scopeCorrections"], gate), encoding="utf-8")
    after = {str(path.relative_to(ROOT)): _sha(path) for path in SOURCES.values()}
    summary = {"phase": "6.0-gve16-parameter-config-integration", "previewChapterCount": 4,
               "parameterPlacementCount": len(placements), "scopeCorrectionCount": len(preflight["scopeCorrections"]),
               "qualityGate": gate["qualityGate"], "sourceFilesUnchanged": before == after,
               "newMechanicCount": 0, "newScopeCount": 0, "newConfigTableCount": 0,
               "inventedConfigFieldCount": 0, "inventedFormulaCount": 0,
               "finalDocumentGenerated": False}
    (output_dir / "phase60-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "provenance.json").write_text(json.dumps({"sourceHashes": before, **summary}, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(generate(), ensure_ascii=False, indent=2))
