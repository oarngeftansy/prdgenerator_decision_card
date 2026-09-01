from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from backend.graph_grounding_quality_evaluator import evaluate_effective_reconstruction_depth, evaluate_graph_grounding_quality
from backend.mechanic_graph_corpus import load_gve16_mechanic_structure_corpus
from backend.mechanic_reconstruction_depth_evaluator import evaluate_mechanic_reconstruction_depth
from backend.rule_semantic_grounding import decompose_rule_semantics, ground_mechanic_graphs


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "artifacts/planning-content-phase3-2026-08-17/phase-3-gap-result.json"
MODELS = ROOT / "artifacts/planning-content-phase5.3-planning-reasoning-2026-08-17/planning-mechanism-models.json"
PHASE531 = ROOT / "artifacts/planning-content-phase5.3.1-2026-08-17/mechanic-graphs.json"
CORPUS = ROOT / "data/quality/gve16-mechanic-structure-corpus-v2.json"
DEFAULT_OUT = ROOT / "artifacts/planning-content-phase5.3.2-2026-08-17"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _approved(source: dict[str, Any]) -> list[dict[str, Any]]:
    rules = json.loads(json.dumps(source["rules"], ensure_ascii=False))
    for rule in rules:
        if rule.get("semanticValidity") == "valid":
            rule["reviewStatus"] = "approved"
    return rules


def _readable(graphs: list[dict[str, Any]], old_graphs: list[dict[str, Any]], quality: dict[str, Any], effective: dict[str, Any]) -> str:
    old = {item["mechanicId"]: item for item in old_graphs}
    q = {item["mechanicId"]: item for item in quality["perMechanic"]}
    depth = {item["mechanicId"]: item for item in effective["perMechanic"]}
    lines = ["# Phase 5.3.2 六章 Semantic Grounding 与图质量正文", "",
             "> 本文是 Planning Reasoning 审计正文，不是最终执行策划正文；未新增 Rule、未关闭 Gap、未调用 Renderer。", ""]
    for graph in graphs:
        lines += [f"## {graph['name']}", "", "### Approved Rule → Semantic decomposition", ""]
        if not graph["ruleDecompositions"]:
            lines.append("- 本章没有可进入 Logic/Data 机制图的 Approved Rule。")
        for item in graph["ruleDecompositions"]:
            lines.append(f"- `{item['ruleId']}`：{item['sourceBehavior']}")
            lines += [f"  - `{part['semanticRole']}` → `{part['nodeSemantic']}`：{part['text']}" for part in item["components"]]
        for status, title in (("confirmed", "Grounded Nodes"), ("derived_structure", "Derived Nodes + provenance"),
                              ("hypothesis", "Hypothesis"), ("unresolved", "Unresolved")):
            lines += ["", f"### {title}", ""]
            selected = [node for node in graph["nodes"] if node["status"] == status]
            if not selected:
                lines.append("- 无。")
            for node in selected:
                if status == "derived_structure":
                    lines.append(f"- `{node['semantic']}`：{node['derivationType']}；sourceNodeIds={node['sourceNodeIds']}；sourceRuleIds={node['sourceRuleIds']}；{node['derivationReason']}")
                else:
                    refs = node["supportingRuleIds"] or node["supportingGapIds"]
                    lines.append(f"- `{node['semantic']}` / `{node['nodeType']}`（{', '.join(refs) or '无当前项目依据'}）")
        lines += ["", "### Grounded Edges", ""]
        names = {node["nodeId"]: node["semantic"] for node in graph["nodes"]}
        lines += [f"- `{names[edge['fromNodeId']]}` —{edge['relationType']}→ `{names[edge['toNodeId']]}`；support={','.join(edge['supportingRuleIds']) or edge['evidenceStatus']}；duration={edge.get('durationKind') or 'none'}" for edge in graph["edges"]] or ["- 无 grounded edge。"]
        lines += ["", "### Edge validation", ""]
        findings = q[graph["mechanicId"]]["findings"]
        lines += [f"- `{item['code']}`：{json.dumps(item, ensure_ascii=False)}" for item in findings] or ["- pass"]
        before = old[graph["mechanicId"]]
        old_status = {node["semantic"]: node["status"] for node in before["nodes"]}
        old_rule_nodes = {}
        for node in before["nodes"]:
            for rule_id in node.get("supportingRuleIds", []):
                old_rule_nodes.setdefault(rule_id, set()).add(node["semantic"])
        new_rule_nodes = {}
        for node in graph["nodes"]:
            for rule_id in node.get("supportingRuleIds", []):
                new_rule_nodes.setdefault(rule_id, set()).add(node["semantic"])
        relocations = [f"{rule_id}: {','.join(sorted(old_rule_nodes.get(rule_id, set())) or ['无'])} → {','.join(sorted(new_rule_nodes.get(rule_id, set())))}"
                       for rule_id in new_rule_nodes if old_rule_nodes.get(rule_id, set()) != new_rule_nodes[rule_id]]
        old_edges = {(edge["fromNodeId"], edge["toNodeId"]): edge["relationType"] for edge in before["edges"]}
        old_node_names = {node["nodeId"]: node["semantic"] for node in before["nodes"]}
        old_semantic_edges = {(old_node_names[a], old_node_names[b]): relation for (a, b), relation in old_edges.items()}
        new_semantic_edges = {(names[edge["fromNodeId"]], names[edge["toNodeId"]]): edge["relationType"] for edge in graph["edges"]}
        edge_changes = [f"{a} → {b}: {old_semantic_edges.get((a,b), '无')} → {relation}" for (a, b), relation in new_semantic_edges.items() if old_semantic_edges.get((a, b)) != relation]
        promoted = [node["semantic"] for node in graph["nodes"] if node["status"] == "confirmed" and old_status.get(node["semantic"]) != "confirmed"]
        relocated = [part["nodeSemantic"] for item in graph["ruleDecompositions"] for part in item["components"] if part["nodeSemantic"] not in old_status]
        lines += ["", "### Phase 5.3.1 → 5.3.2", "",
                  f"- hypothesis/unresolved → confirmed：{', '.join(promoted) or '无'}",
                  f"- 新增或重新定位 semantic：{', '.join(sorted(set(relocated))) or '无'}",
                  f"- Rule → Node relocation：{'；'.join(relocations) or '无'}",
                  f"- Edge relationType/direction 调整：{'；'.join(edge_changes) or '无'}",
                  f"- Lifecycle：{before['lifecycle']['status']} → {graph['lifecycle']['status']}（persists_until 仅计 transientStateDuration）",
                  f"- transientStateDuration：{sum(edge.get('durationKind') == 'transientStateDuration' for edge in graph['edges'])}",
                  f"- lifecyclePersistence：{len(graph['lifecycle']['lifecyclePersistence'])}",
                  f"- Graph Grounding Quality：{q[graph['mechanicId']]['score']}",
                  f"- Reconstruction Coverage：{depth[graph['mechanicId']]['reconstructionCoverage']}",
                  f"- Effective Reconstruction Depth：{depth[graph['mechanicId']]['effectiveReconstructionDepth']}", ""]
    return "\n".join(lines)


def generate_phase532(output_dir: Path = DEFAULT_OUT) -> dict[str, Any]:
    sources = (SOURCE, MODELS, PHASE531, CORPUS)
    before = {path: _sha(path) for path in sources}
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    models = json.loads(MODELS.read_text(encoding="utf-8"))
    old_graphs = json.loads(PHASE531.read_text(encoding="utf-8"))
    rules = _approved(source)
    corpus = load_gve16_mechanic_structure_corpus(CORPUS)
    graphs = ground_mechanic_graphs(models, rules, source["gaps"], corpus)
    decompositions = [item for graph in graphs for item in graph["ruleDecompositions"]]
    coverage = evaluate_mechanic_reconstruction_depth(graphs)
    quality = evaluate_graph_grounding_quality(graphs, decompositions)
    effective = evaluate_effective_reconstruction_depth(coverage, quality)
    summary = {"phase": "5.3.2", "mechanicCount": len(graphs), "reconstructionCoverage": coverage["total"],
               "graphGroundingQuality": quality["total"], "effectiveReconstructionDepth": effective["total"],
               "approvedRuleCount": len({item["ruleId"] for item in decompositions}),
               "semanticComponentCount": sum(item["componentCount"] for item in decompositions),
               "rendererInvoked": False, "parameterResolverInvoked": False, "modifiedApprovedRuleCount": 0, "closedGapCount": 0}
    output_dir.mkdir(parents=True, exist_ok=True)
    payloads = {"semantic-grounded-mechanic-graphs.json": graphs, "rule-semantic-decompositions.json": decompositions,
                "reconstruction-coverage-report.json": coverage, "graph-grounding-quality-report.json": quality,
                "effective-reconstruction-depth-report.json": effective, "phase532-summary.json": summary}
    for name, payload in payloads.items():
        (output_dir / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "six-chapter-semantic-grounding-audit.md").write_text(_readable(graphs, old_graphs, quality, effective), encoding="utf-8")
    after = {path: _sha(path) for path in sources}
    (output_dir / "provenance.json").write_text(json.dumps({"sourceHashes": {str(path.relative_to(ROOT)): value for path, value in before.items()},
        "sourceFilesUnchanged": before == after, "modifiedApprovedRuleCount": 0, "closedGapCount": 0,
        "rendererInvoked": False, "parameterResolverInvoked": False}, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(generate_phase532(), ensure_ascii=False, indent=2))
