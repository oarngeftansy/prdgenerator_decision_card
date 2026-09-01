from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from backend.mechanic_graph_corpus import load_gve16_mechanic_structure_corpus
from backend.mechanic_graph_reconstruction import reconstruct_mechanic_graphs
from backend.mechanic_reconstruction_depth_evaluator import evaluate_mechanic_reconstruction_depth


ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "artifacts/planning-content-phase5.3-planning-reasoning-2026-08-17/planning-mechanism-models.json"
OLD_DEPTH = ROOT / "artifacts/planning-content-phase5.3-planning-reasoning-2026-08-17/planning-reasoning-depth-report.json"
CORPUS = ROOT / "data/quality/gve16-mechanic-structure-corpus-v2.json"
DEFAULT_OUT = ROOT / "artifacts/planning-content-phase5.3.1-2026-08-17"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _markdown(graphs: list[dict[str, Any]], report: dict[str, Any]) -> str:
    scores = {item["mechanicId"]: item for item in report["perMechanic"]}
    lines = [
        "# Phase 5.3.1 六章有向机制重建", "",
        "> 旧 95 分仅表示 Template / Reasoning Coverage，不再作为 GVE16 Mechanic Reconstruction Depth。", "",
    ]
    for graph in graphs:
        lines += [f"## {graph.get('name')}", "", "### Existing Rules", ""]
        lines += [f"- `{rule_id}`" for rule_id in graph["supportingRuleIds"]] or ["- 无 Approved Rule。"]
        lines += ["", "### Mechanic Nodes", ""]
        for node in graph["nodes"]:
            reason = f"；{node['derivationReason']}" if node.get("derivationReason") else ""
            refs = ", ".join(node["supportingRuleIds"] + node["supportingGapIds"]) or "无"
            lines.append(f"- `{node['semantic']}` / `{node['nodeType']}` — **{node['status']}**（依据：{refs}{reason}）")
        lines += ["", "### Mechanic Edges", ""]
        node_names = {node["nodeId"]: node["semantic"] for node in graph["nodes"]}
        grounded = [edge for edge in graph["edges"] if edge["evidenceStatus"] != "unresolved"]
        lines += [f"- `{node_names[edge['fromNodeId']]}` —{edge['relationType']}→ `{node_names[edge['toNodeId']]}`（{edge['evidenceStatus']}）" for edge in graph["edges"]] or ["- 未建立关系。"]
        lines += ["", "### Lifecycle applicability", "",
                  f"- doesMechanicOwnPersistentState: `{str(graph['lifecycle']['doesMechanicOwnPersistentState']).lower()}`",
                  f"- status: `{graph['lifecycle']['status']}`",
                  f"- reason: {graph['lifecycle']['lifecycleApplicabilityReason']}", "",
                  "### 网络断点", ""]
        unresolved = [node for node in graph["nodes"] if node["status"] == "unresolved"]
        hypotheses = [node for node in graph["nodes"] if node["status"] == "hypothesis" and node.get("previousStatus") == "derived_structure"]
        lines += [f"- unresolved `{node['semantic']}` ← Gap {', '.join(node['supportingGapIds'])}" for node in unresolved] or ["- 无已审核 Gap 定位的断点。"]
        lines += [f"- downgraded `{node['semantic']}`：旧模板存在不能证明当前机制关系，降为 hypothesis。" for node in hypotheses]
        item = scores[graph["mechanicId"]]
        lines += ["", f"- Template / Reasoning Coverage Score：95（历史覆盖值）",
                  f"- Mechanic Reconstruction Depth：{item['score']} / 100",
                  f"- Grounded edges：{len(grounded)}", ""]
    return "\n".join(lines)


def generate_phase531(output_dir: Path = DEFAULT_OUT) -> dict[str, Any]:
    source_paths = (MODELS, OLD_DEPTH, CORPUS)
    before = {path: _sha(path) for path in source_paths}
    models = json.loads(MODELS.read_text(encoding="utf-8"))
    corpus = load_gve16_mechanic_structure_corpus(CORPUS)
    graphs = reconstruct_mechanic_graphs(models, [], [], corpus)
    report = evaluate_mechanic_reconstruction_depth(graphs)
    status_counts = {status: sum(node["status"] == status for graph in graphs for node in graph["nodes"])
                     for status in ("confirmed", "derived_structure", "hypothesis", "unresolved")}
    summary = {
        "phase": "5.3.1", "mechanicCount": len(graphs), "templateReasoningCoverageScore": 95,
        "mechanicReconstructionDepth": report["total"], "nodeStatusCounts": status_counts,
        "edgeCount": sum(len(graph["edges"]) for graph in graphs),
        "groundedEdgeCount": sum(edge["evidenceStatus"] != "unresolved" for graph in graphs for edge in graph["edges"]),
        "parameterResolverInvoked": False, "rendererInvoked": False,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "mechanic-graphs.json").write_text(json.dumps(graphs, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "mechanic-reconstruction-depth-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "reasoning-coverage-report.json").write_text(json.dumps({"score": 95, "label": "Template / Reasoning Coverage Score", "acceptanceUse": False}, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "gve16-mechanic-structure-corpus-audit.json").write_text(json.dumps({
        "sourceDocumentHash": corpus["evidenceSourceDocumentHash"], "patternCount": len(corpus["patterns"]),
        "provisional": corpus["provisional"], "contentAuthority": corpus["contentAuthority"],
        "storesRawSentences": False, "storesProjectObjects": False, "storesProjectFieldsOrValues": False,
        "patterns": [{"mechanicType": item["mechanicType"], "evidenceSourceRef": item["evidenceSourceRef"],
                      "nodeTypeCount": len(item["nodeTypes"]), "edgePatternCount": len(item["edgePatterns"])} for item in corpus["patterns"]],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "six-chapter-directed-reconstruction.md").write_text(_markdown(graphs, report), encoding="utf-8")
    (output_dir / "phase531-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    after = {path: _sha(path) for path in source_paths}
    (output_dir / "provenance.json").write_text(json.dumps({
        "sourceHashes": {str(path.relative_to(ROOT)): digest for path, digest in before.items()},
        "sourceFilesUnchanged": before == after, "modifiedRuleCount": 0, "modifiedGapCount": 0,
        "modifiedRendererCount": 0, "parameterResolverInvoked": False,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(generate_phase531(), ensure_ascii=False, indent=2))
