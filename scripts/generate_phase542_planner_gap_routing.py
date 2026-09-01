from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from backend.planner_gap_routing import evaluate_planner_routing_quality, evaluate_planner_signal_to_noise, route_candidate_gaps


ROOT = Path(__file__).resolve().parents[1]
EXPANSION = ROOT / "artifacts/planning-content-phase5.4-2026-08-17/reasoning-gap-expansion.json"
GRAPHS = ROOT / "artifacts/planning-content-phase5.3.2-2026-08-17/semantic-grounded-mechanic-graphs.json"
SOURCE = ROOT / "artifacts/planning-content-phase3-2026-08-17/phase-3-gap-result.json"
DEFAULT_OUT = ROOT / "artifacts/planning-content-phase5.4.2-gap-routing-2026-08-17"
MOVEMENT_RULE_ID = "RULE-246A8B1E9DF1"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _movement_audit(source: dict[str, Any]) -> dict[str, Any]:
    rule = next(rule for rule in source["rules"] if rule["ruleId"] == MOVEMENT_RULE_ID)
    fact_ids = set(rule.get("sourceFactIds", []))
    facts = [fact for fact in source["facts"] if fact.get("factId") in fact_ids]
    return {
        "movementRouteRule": {
            "status": "conflict",
            "ruleId": MOVEMENT_RULE_ID,
            "trace": {"evidenceIds": rule.get("evidenceIds", []), "factIds": sorted(fact_ids), "ruleIds": [MOVEMENT_RULE_ID]},
            "observedProvenance": [fact.get("rawEvidenceText") for fact in facts],
            "reason": "来源为静态帧及其生成式画面描述；静态帧不足以区分玩家直接控制路线与载具自动沿预设路线移动，且人工复核提出相反解释。Rule 应先回到 Evidence → Fact → Rule 审核。",
            "reviewRequired": True,
            "approvedRuleModified": False,
        }
    }


def _markdown(gaps: list[dict[str, Any]], graphs: list[dict[str, Any]], report: dict[str, Any],
              signal: dict[str, Any], movement_audit: dict[str, Any]) -> str:
    by_gap = {item["gapId"]: item for item in report["results"]}
    lines = ["# Phase 5.4.2 Planner Significance & Gap Routing", "",
             "> 本阶段仅分流 32 条 Candidate ReasoningGap；未生成 plannerQuestion，未修改 Approved Gap，未写回 P4，未调用 ParameterResolver。", "",
             "## Upstream Contradiction Audit：载具移动", "",
             f"- Rule：`{MOVEMENT_RULE_ID}` / 载具沿预设路线自动行进", 
             f"- Evidence：{', '.join(movement_audit['movementRouteRule']['trace']['evidenceIds'])}",
             f"- 结论：`upstream_conflict → Rule Review`", f"- 原因：{movement_audit['movementRouteRule']['reason']}", ""]
    for graph in graphs:
        chapter = [gap for gap in gaps if gap["mechanicId"] == graph["mechanicId"]]
        if not chapter:
            continue
        lines += [f"## {graph['name']}", ""]
        for index, gap in enumerate(chapter, 1):
            result = by_gap[gap["gapId"]]
            lines += [f"### {index}. {gap['question']}", "",
                      f"- gapDisposition：`{result['gapDisposition']}`",
                      f"- plannerSalience：`{result['plannerSalience']}`",
                      f"- routeTarget：`{result['routeTarget']}`",
                      f"- reducedContract：`{result['reducedContract'] or '无'}`",
                      f"- reason：{result['reason']}", ""]
    lines += ["## Signal-to-Noise", "",
              f"- Candidate：{signal['candidateCount']}",
              f"- Planner Review：{signal['plannerReviewCount']}",
              f"- Planner Review noise：{signal['plannerReviewNoiseCount']}",
              f"- Planner Signal-to-Noise Ratio：{signal['plannerSignalToNoiseRatio'] * 100:.2f}%",
              f"- Candidate Signal Rate：{signal['candidateSignalRate'] * 100:.2f}%", ""]
    return "\n".join(lines)


def generate_phase542(output_dir: Path = DEFAULT_OUT) -> dict[str, Any]:
    sources = (EXPANSION, GRAPHS, SOURCE)
    before = {path: _sha(path) for path in sources}
    expansion = json.loads(EXPANSION.read_text(encoding="utf-8"))
    graphs = json.loads(GRAPHS.read_text(encoding="utf-8"))
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    gaps = expansion["reasoningGaps"]
    rules = [rule for rule in source["rules"] if rule.get("semanticValidity") == "valid"]
    audit = _movement_audit(source)
    report = route_candidate_gaps(gaps, graphs, rules, audit)
    signal = evaluate_planner_signal_to_noise(report)
    quality = evaluate_planner_routing_quality(report)
    summary = {"phase": "5.4.2-planner-significance-gap-routing", "candidateCount": len(gaps),
               "dispositionCounts": report["dispositionCounts"], "plannerSignalToNoise": signal,
               "plannerRoutingQuality": quality,
               "plannerQuestionGeneratedCount": 0, "modifiedApprovedGapCount": 0, "p4WriteCount": 0,
               "parameterResolverInvoked": False, "rendererInvoked": False}
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, payload in (("gap-routing-report.json", report), ("upstream-contradiction-audit.json", audit),
                          ("planner-routing-quality.json", quality),
                          ("planner-signal-to-noise.json", signal), ("phase542-summary.json", summary)):
        (output_dir / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "candidate-gap-routing-audit.md").write_text(_markdown(gaps, graphs, report, signal, audit), encoding="utf-8")
    after = {path: _sha(path) for path in sources}
    (output_dir / "provenance.json").write_text(json.dumps({
        "sourceHashes": {str(path.relative_to(ROOT)): value for path, value in before.items()},
        "sourceFilesUnchanged": before == after, "modifiedApprovedGapCount": 0, "p4WriteCount": 0,
        "plannerQuestionGeneratedCount": 0, "parameterResolverInvoked": False,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(generate_phase542(), ensure_ascii=False, indent=2))
