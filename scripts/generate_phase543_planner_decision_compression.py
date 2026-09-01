from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from backend.planner_decision_compression import compress_planner_decisions, evaluate_planner_decision_granularity


ROOT = Path(__file__).resolve().parents[1]
ROUTING = ROOT / "artifacts/planning-content-phase5.4.2-gap-routing-2026-08-17/gap-routing-report.json"
GRAPHS = ROOT / "artifacts/planning-content-phase5.3.2-2026-08-17/semantic-grounded-mechanic-graphs.json"
SOURCE = ROOT / "artifacts/planning-content-phase3-2026-08-17/phase-3-gap-result.json"
DEFAULT_OUT = ROOT / "artifacts/planning-content-phase5.4.3-decision-compression-2026-08-17"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rules_by_mechanic(source: dict[str, Any], graphs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rule_by_id = {rule["ruleId"]: rule for rule in source["rules"]}
    enriched = []
    for graph in graphs:
        for rule_id in graph.get("supportingRuleIds", []):
            if rule_id in rule_by_id:
                enriched.append({**rule_by_id[rule_id], "mechanicId": graph["mechanicId"]})
    return enriched


def _markdown(report: dict[str, Any], granularity: dict[str, Any], planner_gaps: list[dict[str, Any]]) -> str:
    gap_by_id = {item["gapId"]: item for item in planner_gaps}
    lines = ["# Phase 5.4.3 Planner Decision Compression", "",
             "> ReasoningGap 是底层缺口；PlannerDecision 是主策审核粒度。本产物不生成最终 plannerQuestion。", "",
             "## 压缩结果", "",
             f"- Before Planner Review：{report['beforePlannerReviewCount']}",
             f"- After PlannerDecision：{report['afterPlannerDecisionCount']}",
             f"- Compression ratio：{report['compressionRatio'] * 100:.2f}%", ""]
    for decision in report["plannerDecisions"]:
        lines += [f"## {decision['title']}", "", f"- decisionId：`{decision['decisionId']}`",
                  f"- mechanicId：`{decision['mechanicId']}`", f"- designLever：`{decision['designLever']}`",
                  f"- sourceReasoningGapIds：{', '.join(decision['sourceReasoningGapIds'])}",
                  f"- coreQuestion：{decision['coreQuestion']}", "- subQuestions："]
        for gap_id in decision["sourceReasoningGapIds"]:
            lines.append(f"  - {gap_by_id[gap_id]['originalGap']}")
        lines += [f"- currentKnownRules：{'；'.join(decision['currentKnownRules']) or '无'}",
                  f"- unresolvedDimensions：{', '.join(decision['unresolvedDimensions'])}",
                  f"- gameplayImpact：{decision['gameplayImpact']}",
                  f"- 合并原因：同一机制内共同控制 `{decision['designLever']}`，可由同一策划结论统一回答。", ""]
    lines += ["## 压缩后移出 Planner Review", ""]
    for item in report["compressedOut"]:
        original = gap_by_id[item["gapId"]]["originalGap"]
        lines += [f"- {original}", f"  - → `{item['routeTarget']}` / `{item['reasonCode']}`",
                  f"  - 原因：{item['reason']}"]
    lines += ["", "## Planner Decision Granularity Gate", "",
              f"- qualityGate：`{granularity['qualityGate']}`", f"- findingCount：{granularity['findingCount']}",
              "- 内部参数、QA Case 和 Graph breakpoint 均未成为独立 PlannerDecision。", ""]
    return "\n".join(lines)


def generate_phase543(output_dir: Path = DEFAULT_OUT) -> dict[str, Any]:
    sources = (ROUTING, GRAPHS, SOURCE)
    before = {path: _sha(path) for path in sources}
    routing = json.loads(ROUTING.read_text(encoding="utf-8"))
    graphs = json.loads(GRAPHS.read_text(encoding="utf-8"))
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    planner_gaps = [item for item in routing["results"] if item.get("plannerReviewEligible")]
    rules = _rules_by_mechanic(source, graphs)
    report = compress_planner_decisions(planner_gaps, routing["results"], rules)
    granularity = evaluate_planner_decision_granularity(report["plannerDecisions"])
    summary = {"phase": "5.4.3-planner-decision-compression",
               "beforePlannerReviewCount": report["beforePlannerReviewCount"],
               "afterPlannerDecisionCount": report["afterPlannerDecisionCount"],
               "compressionRatio": report["compressionRatio"],
               "compressedOutCount": len(report["compressedOut"]),
               "granularityGate": granularity["qualityGate"], "granularityFindingCount": granularity["findingCount"],
               "plannerQuestionGeneratedCount": 0, "modifiedApprovedGapCount": 0, "p4WriteCount": 0,
               "parameterResolverInvoked": False}
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, payload in (("planner-decisions.json", report), ("planner-decision-granularity.json", granularity),
                          ("phase543-summary.json", summary)):
        (output_dir / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "planner-decision-compression-audit.md").write_text(
        _markdown(report, granularity, planner_gaps), encoding="utf-8")
    after = {path: _sha(path) for path in sources}
    (output_dir / "provenance.json").write_text(json.dumps({
        "sourceHashes": {str(path.relative_to(ROOT)): value for path, value in before.items()},
        "sourceFilesUnchanged": before == after, "modifiedApprovedGapCount": 0, "p4WriteCount": 0,
        "plannerQuestionGeneratedCount": 0, "parameterResolverInvoked": False,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(generate_phase543(), ensure_ascii=False, indent=2))
