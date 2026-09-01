from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from backend.gap_decision_worthiness import filter_reasoning_gaps
from backend.reasoning_gap_quality_evaluator import evaluate_reasoning_gap_quality


ROOT = Path(__file__).resolve().parents[1]
EXPANSION = ROOT / "artifacts/planning-content-phase5.4-2026-08-17/reasoning-gap-expansion.json"
GRAPHS = ROOT / "artifacts/planning-content-phase5.3.2-2026-08-17/semantic-grounded-mechanic-graphs.json"
SOURCE = ROOT / "artifacts/planning-content-phase3-2026-08-17/phase-3-gap-result.json"
DEFAULT_OUT = ROOT / "artifacts/planning-content-phase5.4.1-decision-worthiness-2026-08-17"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _audit(gaps: list[dict[str, Any]], graphs: list[dict[str, Any]], report: dict[str, Any], quality: dict[str, Any]) -> str:
    gap_by_id = {gap["gapId"]: gap for gap in gaps}
    result_by_id = {item["gapId"]: item for item in report["results"]}
    quality_by_id = {item["gapId"]: item for item in quality["perGap"]}
    lines = ["# Phase 5.4.1 Decision Worthiness：32 条 Candidate Gap 审计", "",
             "> 本轮只判断问题是否值得交给策划。未生成 plannerQuestion，未修改 ReasoningGap／Approved Gap／P4／正文。", ""]
    for graph in graphs:
        chapter_gaps = [gap for gap in gaps if gap["mechanicId"] == graph["mechanicId"]]
        lines += [f"## {graph['name']}", ""]
        if not chapter_gaps:
            lines.append("- 无 Candidate ReasoningGap。")
        for index, gap in enumerate(chapter_gaps, start=1):
            result = result_by_id[gap["gapId"]]
            q = quality_by_id[gap["gapId"]]
            lines += [f"### {index}. {gap['question']}", "",
                      f"- Decision：`{result['decisionWorthiness']}`",
                      f"- Reason code：`{result['reasonCode']}`",
                      f"- Reason：{result['reason']}",
                      f"- Graph breakpoint：sourceNodeIds={gap['sourceNodeIds']}；missingNode=`{gap['missingNodeSemantic']}`；missingRelation=`{gap['missingRelation']}`",
                      f"- Alternative interpretations：{'；'.join(result['alternativeInterpretations']) or '无第二种同等合理解释'}",
                      f"- Gameplay impact：{result['gameplayImpact']}",
                      f"- Program impact：{result['implementationImpact']}",
                      f"- QA impact：{result['qaImpact']}",
                      f"- Qualifying criteria：{', '.join(result['qualifyingCriteria']) or '无'}",
                      f"- Decision-aware Gap Quality：{q['score']} / 100", ""]
    lines += ["## 汇总", "",
              f"- Candidate：{report['candidateCount']}",
              f"- keep：{report['counts']['keep']}",
              f"- suppress：{report['counts']['suppress']}",
              f"- defer：{report['counts']['defer']}",
              f"- PlannerQuestion generated：{report['plannerQuestionGeneratedCount']}", ""]
    return "\n".join(lines)


def generate_phase541(output_dir: Path = DEFAULT_OUT) -> dict[str, Any]:
    sources = (EXPANSION, GRAPHS, SOURCE)
    before = {path: _sha(path) for path in sources}
    expansion = json.loads(EXPANSION.read_text(encoding="utf-8"))
    graphs = json.loads(GRAPHS.read_text(encoding="utf-8"))
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    gaps = expansion["reasoningGaps"]
    rules = [rule for rule in source["rules"] if rule.get("semanticValidity") == "valid"]
    report = filter_reasoning_gaps(gaps, graphs, rules, source.get("facts", []))
    quality = evaluate_reasoning_gap_quality(gaps, graphs, decision_results=report["results"])
    reason_counts: dict[str, int] = {}
    for item in report["results"]:
        reason_counts[item["reasonCode"]] = reason_counts.get(item["reasonCode"], 0) + 1
    kept = [gap for gap in gaps if gap["gapId"] in set(report["keptGapIds"])]
    kept_quality = evaluate_reasoning_gap_quality(kept, graphs, decision_results=report["results"])
    summary = {"phase": "5.4.1-decision-worthiness", "candidateCount": report["candidateCount"], "counts": report["counts"],
               "reasonCounts": reason_counts, "candidateQualityScore": quality["total"], "keptQualityScore": kept_quality["total"],
               "plannerQuestionGeneratedCount": 0, "modifiedReasoningGapCount": 0, "modifiedApprovedGapCount": 0,
               "p4WriteCount": 0, "rendererInvoked": False, "parameterResolverInvoked": False}
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, payload in (("decision-worthiness-report.json", report), ("decision-aware-gap-quality-report.json", quality),
                          ("kept-gap-quality-report.json", kept_quality), ("phase541-summary.json", summary)):
        (output_dir / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "candidate-gap-decision-audit.md").write_text(_audit(gaps, graphs, report, quality), encoding="utf-8")
    after = {path: _sha(path) for path in sources}
    (output_dir / "provenance.json").write_text(json.dumps({"sourceHashes": {str(path.relative_to(ROOT)): value for path, value in before.items()},
        "sourceFilesUnchanged": before == after, "modifiedReasoningGapCount": 0, "modifiedApprovedGapCount": 0,
        "p4WriteCount": 0, "plannerQuestionGeneratedCount": 0, "rendererInvoked": False, "parameterResolverInvoked": False}, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(generate_phase541(), ensure_ascii=False, indent=2))
