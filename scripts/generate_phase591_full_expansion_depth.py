from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from backend.rule_expansion_depth import calibrate_rule_expansion_depth, evaluate_expansion_stop_gate


ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "layouts": ROOT / "artifacts/planning-content-phase5.8-native-rule-layouts-2026-08-17/rule-layout-plans.json",
    "projections": ROOT / "artifacts/planning-content-phase5.7-core-loop-projection-2026-08-17/rule-projections.json",
    "groups": ROOT / "artifacts/planning-content-phase5.5-game-rule-groups-2026-08-17/game-rule-groups.json",
    "chains": ROOT / "artifacts/planning-content-phase5.6-gameplay-rule-chains-2026-08-17/gameplay-rule-chains.json",
    "scopes": ROOT / "artifacts/planning-content-phase5.4.4-mechanic-scope-2026-08-17/scoped-game-rule-models.json",
    "rules": ROOT / "artifacts/planning-content-phase3-2026-08-17/phase-3-gap-result.json",
    "corpus": ROOT / "data/quality/gve16-mechanic-structure-corpus-v2.json",
}
OUT = ROOT / "artifacts/planning-content-phase5.9.1-full-expansion-depth-2026-08-17"
OWNERS = {
    "V2CH-001": "载具移动", "V2CH-005": "武器", "V2CH-009": "三选一",
    "V2CH-015": "怪物攻击", "V2CH-017": "关卡", "V2CH-020": "结算",
}


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _items(items: list[dict[str, Any]], key: str) -> list[str]:
    return [f"- {item[key]}" for item in items] or ["- 无"]


def _markdown(plans: list[dict[str, Any]], report: dict[str, Any]) -> str:
    lines = ["# Phase 5.9.1 Full GVE16 Rule Expansion Depth Pass", "",
             "> 覆盖 Phase 5.8 的全部 13 个 RuleLayoutPlan。仅校准规则展开深度，不生成最终正文。", ""]
    for owner, owner_title in OWNERS.items():
        lines += [f"## {owner_title}", ""]
        for plan in [item for item in plans if item["ownerChapter"] == owner]:
            lines += [f"### {plan['ruleTopic']}", "", f"- Depth Status：`{plan['depthStatus']}`",
                      f"- Target Depth：`{plan['targetDepth']}`", "", "#### Confirmed Detail", ""]
            lines += _items(plan["confirmedDetails"], "text")
            lines += ["", "#### Missing Execution Detail", ""]
            lines += _items(plan["missingExecutionDetails"], "question")
            lines += ["", "#### Gameplay Parameter", ""]
            lines += _items(plan["gameplayParameters"], "label")
            lines += ["", "#### Stop Here", ""]
            lines += ([f"- {item['candidateDimension']}：{item['reason']}（{item['scopeStatus']}）"
                       for item in plan["stopReasons"]] or ["- 无"])
            lines.append("")
    lines += ["## Global Check", "", f"- total layouts：{report['totalLayouts']}",
              f"- appropriate：{report['appropriate']}", f"- under-expanded：{report['underExpanded']}",
              f"- over-expanded：{report['overExpanded']}",
              f"- scope violations：{report['scopeViolationCount']}",
              f"- implementation leakage：{report['implementationLeakCount']}", "",
              "### GVE16 需要、当前项目缺失的执行规则", ""]
    lines += [f"- {item['ruleTopic']}：{item['question']}" for item in report["gve16RequiredMissingExecutionRules"]] or ["- 无"]
    lines += ["", "### 当前系统比 GVE16 多追问的低价值细节", ""]
    lines += [f"- {item['ruleTopic']} / {item['candidateDimension']}：{item['reason']}"
              for item in report["lowValueDetailsStopped"]] or ["- 无"]
    lines.append("")
    return "\n".join(lines)


def generate(output_dir: Path = OUT) -> dict[str, Any]:
    before = {str(path.relative_to(ROOT)): _sha(path) for path in SOURCES.values()}
    layouts = _load(SOURCES["layouts"])
    scopes = _load(SOURCES["scopes"])
    plans = calibrate_rule_expansion_depth(
        layouts, _load(SOURCES["projections"]), _load(SOURCES["groups"]), _load(SOURCES["chains"]),
        scopes, _load(SOURCES["rules"])["rules"], _load(SOURCES["corpus"]),
    )
    report = evaluate_expansion_stop_gate(plans, scopes)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "rule-expansion-plans.json").write_text(json.dumps(plans, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "full-expansion-depth-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "all-layout-expansion-preview.md").write_text(_markdown(plans, report), encoding="utf-8")
    after = {str(path.relative_to(ROOT)): _sha(path) for path in SOURCES.values()}
    summary = {"phase": "5.9.1-full-gve16-rule-expansion-depth-pass", "totalLayouts": len(plans),
               "appropriate": report["appropriate"], "underExpanded": report["underExpanded"],
               "overExpanded": report["overExpanded"], "qualityGate": report["qualityGate"],
               "sourceFilesUnchanged": before == after, "modifiedScopeCount": 0,
               "modifiedApprovedRuleCount": 0, "modifiedApprovedGapCount": 0,
               "parameterResolverInvoked": False, "finalDocumentGenerated": False}
    (output_dir / "phase591-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "provenance.json").write_text(json.dumps({"sourceHashes": before, **summary}, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(generate(), ensure_ascii=False, indent=2))
