from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from backend.rule_expansion_depth import calibrate_rule_expansion_depth, evaluate_expansion_stop_gate


ROOT = Path(__file__).resolve().parents[1]
LAYOUTS = ROOT / "artifacts/planning-content-phase5.8-native-rule-layouts-2026-08-17/rule-layout-plans.json"
PROJECTIONS = ROOT / "artifacts/planning-content-phase5.7-core-loop-projection-2026-08-17/rule-projections.json"
GROUPS = ROOT / "artifacts/planning-content-phase5.5-game-rule-groups-2026-08-17/game-rule-groups.json"
CHAINS = ROOT / "artifacts/planning-content-phase5.6-gameplay-rule-chains-2026-08-17/gameplay-rule-chains.json"
SCOPES = ROOT / "artifacts/planning-content-phase5.4.4-mechanic-scope-2026-08-17/scoped-game-rule-models.json"
RULES = ROOT / "artifacts/planning-content-phase3-2026-08-17/phase-3-gap-result.json"
CORPUS = ROOT / "data/quality/gve16-mechanic-structure-corpus-v2.json"
OUT = ROOT / "artifacts/planning-content-phase5.9-rule-expansion-depth-2026-08-17"

CHAPTERS = {"V2CH-005": "武器攻击", "V2CH-009": "三选一", "V2CH-015": "怪物攻击", "V2CH-017": "关卡流程"}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _lines(items: list[dict[str, Any]], field: str, fallback: str) -> list[str]:
    return [f"- {item.get(field, fallback)}" for item in items] or ["- 无"]


def _markdown(plans: list[dict[str, Any]], gate: dict[str, Any]) -> str:
    lines = ["# Phase 5.9 GVE16 Rule Expansion Depth Calibration", "",
             "> 这是规则展开深度审计，不是最终策划正文；不产生新 Rule、Gap、Scope 或参数值。", ""]
    for owner, title in CHAPTERS.items():
        lines += [f"## {title}", ""]
        for plan in [item for item in plans if item["ownerChapter"] == owner]:
            lines += [f"### Current Layout：{plan['ruleTopic']}", "",
                      f"- Layout：`{plan['layoutId']}`", f"- Target Depth：`{plan['targetDepth']}`",
                      f"- 判断：`{plan['depthVerdict']}`", "", "#### Confirmed Detail", ""]
            lines += _lines(plan["confirmedDetails"], "text", "-")
            lines += ["", "#### Missing Execution Detail", ""]
            lines += _lines(plan["missingExecutionDetails"], "question", "-")
            lines += ["", "#### Gameplay Parameter", ""]
            lines += _lines(plan["gameplayParameters"], "label", "-")
            lines += ["", "#### Stop Here / Why", ""]
            if plan["stopReasons"]:
                lines += [f"- {item['candidateDimension']}：{item['reason']}（{item['scopeStatus']}）"
                          for item in plan["stopReasons"]]
            else:
                lines += ["- 当前没有需要额外声明的停止项。"]
            lines.append("")
    lines += ["## Expansion Stop Gate", "", f"- qualityGate：`{gate['qualityGate']}`",
              f"- Scope 越界：{gate['scopeViolationCount']}",
              f"- Implementation 泄漏：{gate['implementationLeakCount']}",
              f"- 缺少玩法影响依据：{gate['missingGameplayImpactCount']}", ""]
    return "\n".join(lines)


def generate(output_dir: Path = OUT) -> dict[str, Any]:
    sources = [LAYOUTS, PROJECTIONS, GROUPS, CHAINS, SCOPES, RULES, CORPUS]
    before = {str(path.relative_to(ROOT)): _sha(path) for path in sources}
    layouts = [item for item in _load(LAYOUTS) if item["ownerChapter"] in CHAPTERS]
    # Phase 5.9 calibrates only the requested weapon attack layout, not weapon acquisition/growth.
    layouts = [item for item in layouts if item["ownerChapter"] != "V2CH-005" or item["sectionTitle"] == "攻击规则"]
    rule_payload = _load(RULES)
    plans = calibrate_rule_expansion_depth(layouts, _load(PROJECTIONS), _load(GROUPS), _load(CHAINS),
                                           _load(SCOPES), rule_payload["rules"], _load(CORPUS))
    gate = evaluate_expansion_stop_gate(plans, _load(SCOPES))
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "rule-expansion-plans.json").write_text(json.dumps(plans, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "expansion-depth-report.json").write_text(json.dumps(gate, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "four-chapter-expansion-preview.md").write_text(_markdown(plans, gate), encoding="utf-8")
    after = {str(path.relative_to(ROOT)): _sha(path) for path in sources}
    summary = {"phase": "5.9-gve16-rule-expansion-depth-calibration", "chapterCount": 4,
               "expansionPlanCount": len(plans), "qualityGate": gate["qualityGate"],
               "sourceFilesUnchanged": before == after, "modifiedScopeCount": 0,
               "discoveredSystemCount": 0, "modifiedApprovedRuleCount": 0,
               "modifiedApprovedGapCount": 0, "parameterResolverInvoked": False,
               "finalDocumentGenerated": False}
    (output_dir / "phase59-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "provenance.json").write_text(json.dumps({"sourceHashes": before, **summary}, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(generate(), ensure_ascii=False, indent=2))
