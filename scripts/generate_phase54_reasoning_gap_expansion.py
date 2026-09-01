from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from backend.reasoning_gap_expander import expand_reasoning_gaps
from backend.reasoning_gap_quality_evaluator import evaluate_reasoning_gap_quality


ROOT = Path(__file__).resolve().parents[1]
GRAPHS = ROOT / "artifacts/planning-content-phase5.3.2-2026-08-17/semantic-grounded-mechanic-graphs.json"
SOURCE = ROOT / "artifacts/planning-content-phase3-2026-08-17/phase-3-gap-result.json"
DEFAULT_OUT = ROOT / "artifacts/planning-content-phase5.4-2026-08-17"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _audit(graphs: list[dict[str, Any]], expansion: dict[str, Any], existing_by_id: dict[str, dict[str, Any]], quality: dict[str, Any]) -> str:
    gaps_by_mechanic: dict[str, list[dict[str, Any]]] = {}
    for gap in expansion["reasoningGaps"]:
        gaps_by_mechanic.setdefault(gap["mechanicId"], []).append(gap)
    audit_by_mechanic = {item["mechanicId"]: item for item in expansion["mechanisms"]}
    score_by_gap = {item["gapId"]: item for item in quality["perGap"]}
    lines = ["# Phase 5.4 Reasoning-aware Gap Expansion：六章只读审计", "",
             "> ReasoningGap 仅用于策划审核；不修改 Approved Gap、不写回 P4、不生成 Approved Rule 或最终正文。", ""]
    for graph in graphs:
        audit = audit_by_mechanic[graph["mechanicId"]]
        gaps = gaps_by_mechanic.get(graph["mechanicId"], [])
        lines += [f"## {graph['name']}", "", "### Existing Grounded Graph", ""]
        grounded = [node for node in graph["nodes"] if node["status"] in {"confirmed", "derived_structure"}]
        if grounded:
            lines += [f"- `{node['semantic']}` / `{node['status']}`" for node in grounded]
            names = {node["nodeId"]: node["semantic"] for node in graph["nodes"]}
            lines += [f"- Edge：`{names[edge['fromNodeId']]}` —{edge['relationType']}→ `{names[edge['toNodeId']]}`" for edge in graph["edges"]]
        else:
            lines.append("- 无 grounded node；禁止从模板扩写 ReasoningGap。")
        lines += ["", "### Graph breakpoint → Existing Gap → ReasoningGap", ""]
        if not gaps:
            lines.append(f"- 未生成 ReasoningGap：{audit['suppressionReason'] or '没有满足必要性门槛的 graph breakpoint'}。")
        for gap in gaps:
            old = [existing_by_id[gap_id] for gap_id in gap["existingGapIds"] if gap_id in existing_by_id]
            lines += [f"#### {gap['question']}", "",
                      f"- Graph breakpoint：sourceNodeIds={gap['sourceNodeIds']}；missingNode=`{gap['missingNodeSemantic']}`；missingRelation=`{gap['missingRelation']}`",
                      f"- Existing Gap：{'；'.join(item['question'] for item in old) or '无'}",
                      f"- 处置：`{gap['disposition']}`",
                      f"- 必要性：{gap['derivationReason']}",
                      f"- Program impact：{gap['implementationImpact']}",
                      f"- QA impact：{gap['qaImpact']}",
                      f"- Priority：`{gap['blockingLevel']}`",
                      f"- Gap Quality：{score_by_gap[gap['gapId']]['score']} / 100（{score_by_gap[gap['gapId']]['qualityGate']}）", ""]
        lines += ["### Existing Gap disposition", "",
                  f"- 已有 Gap 可复用：{', '.join(audit['reusedExistingGapIds']) or '无'}",
                  f"- 已有 Gap 需要改写：{', '.join(audit['rewrittenExistingGapIds']) or '无'}",
                  f"- 应删除的低价值 Gap：{', '.join(audit['deleteLowValueGapIds']) or '无'}",
                  f"- 等待 grounded 后再判断：{', '.join(audit['deferUntilGroundedGapIds']) or '无'}", ""]
    return "\n".join(lines)


def generate_phase54(output_dir: Path = DEFAULT_OUT) -> dict[str, Any]:
    sources = (GRAPHS, SOURCE)
    before = {path: _sha(path) for path in sources}
    graphs = json.loads(GRAPHS.read_text(encoding="utf-8"))
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    expansion = expand_reasoning_gaps(graphs, source["gaps"])
    quality = evaluate_reasoning_gap_quality(expansion["reasoningGaps"], graphs)
    dispositions = {key: sum(gap["disposition"] == key for gap in expansion["reasoningGaps"])
                    for key in ("reuse_existing", "rewrite_existing", "new")}
    summary = {"phase": "5.4", "mechanicCount": len(graphs), "reasoningGapCount": len(expansion["reasoningGaps"]),
               "dispositions": dispositions, "deleteLowValueExistingGapCount": sum(len(item["deleteLowValueGapIds"]) for item in expansion["mechanisms"]),
               "deferUntilGroundedExistingGapCount": sum(len(item["deferUntilGroundedGapIds"]) for item in expansion["mechanisms"]),
               "gapQualityScore": quality["total"], "qualityPassedCount": quality["passedCount"], "qualityFailedCount": quality["failedCount"],
               "modifiedApprovedGapCount": 0, "modifiedApprovedRuleCount": 0, "p4WriteCount": 0, "rendererInvoked": False, "parameterResolverInvoked": False}
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, payload in (("reasoning-gap-expansion.json", expansion), ("reasoning-gap-quality-report.json", quality), ("phase54-summary.json", summary)):
        (output_dir / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    existing_by_id = {gap["gapId"]: gap for gap in source["gaps"]}
    (output_dir / "six-chapter-reasoning-gap-audit.md").write_text(_audit(graphs, expansion, existing_by_id, quality), encoding="utf-8")
    after = {path: _sha(path) for path in sources}
    (output_dir / "provenance.json").write_text(json.dumps({"sourceHashes": {str(path.relative_to(ROOT)): digest for path, digest in before.items()},
        "sourceFilesUnchanged": before == after, "modifiedApprovedGapCount": 0, "modifiedApprovedRuleCount": 0,
        "p4WriteCount": 0, "rendererInvoked": False, "parameterResolverInvoked": False}, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(generate_phase54(), ensure_ascii=False, indent=2))
