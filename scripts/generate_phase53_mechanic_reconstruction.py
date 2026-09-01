from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from backend.mechanic_depth_evaluator import evaluate_mechanic_depth
from backend.mechanic_model_builder import build_mechanic_models
from backend.mechanic_structure_corpus import load_mechanic_structure_corpus


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "artifacts/planning-content-phase3-2026-08-17/phase-3-gap-result.json"
ENTITY_GRAPH = ROOT / "artifacts/planning-content-phase5-2026-08-17/entity-graph.json"
EXECUTION_DELIVERY = ROOT / "artifacts/planning-content-phase5.1-2026-08-17/phase51-delivery.json"
CORPUS_PATH = ROOT / "data/quality/gve16-mechanic-structure-corpus-v1.json"
DEFAULT_OUT = ROOT / "artifacts/planning-content-phase5.3-2026-08-17"
FOCUS_CHAPTER_IDS = {
    "V2CH-001", "V2CH-005", "V2CH-009", "V2CH-010", "V2CH-015", "V2CH-017", "V2CH-020", "V2CH-021",
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _approved_rules(source: dict[str, Any]) -> list[dict[str, Any]]:
    rules = json.loads(json.dumps(source["rules"], ensure_ascii=False))
    for rule in rules:
        if rule.get("semanticValidity") == "valid":
            rule["reviewStatus"] = "approved"
    return rules


def _audit_markdown(models: list[dict[str, Any]], rules_by_id: dict[str, dict[str, Any]], depth: dict[str, Any]) -> str:
    lines = [
        "# Phase 5.3 六章 Mechanic Reasoning & System Reconstruction", "",
        "> 本产物只重建机制节点。inferred_structure / unresolved 不产生 Rule 内容、不关闭 Gap、不进入正文。", "",
    ]
    depth_by_id = {item["mechanicId"]: item for item in depth["perMechanic"]}
    for model in models:
        lines += [f"## {model['name']}", "", "### 现有 Approved Rule", ""]
        if model["supportingRuleIds"]:
            for rule_id in model["supportingRuleIds"]:
                rule = rules_by_id[rule_id]
                lines.append(f"- `{rule_id}`：{rule.get('behavior')}")
        else:
            lines.append("- 无 Logic / Flow / Numeric / Config / Interaction Approved Rule。")
        lines += ["", "### MechanicModel", "", f"- mechanicId: `{model['mechanicId']}`", f"- mechanicType: `{model['mechanicType']}`", f"- purpose: {model['purpose']}", f"- actors: {', '.join(model['actors']) or '未识别'}", f"- confidence: {model['confidence']}", "", "### 完整机制骨架", ""]
        for index, node in enumerate(model["nodes"], start=1):
            suffix = []
            if node["supportingRuleIds"]:
                suffix.append("Rule=" + ",".join(node["supportingRuleIds"]))
            if node["supportingGapIds"]:
                suffix.append("Gap=" + ",".join(node["supportingGapIds"]))
            lines.append(f"{index}. {node['label']} — **{node['status']}**" + (f"（{'; '.join(suffix)}）" if suffix else ""))
        confirmed = len(model["confirmedNodes"])
        inferred = len(model["inferredNodes"])
        unresolved = len(model["unresolvedNodes"])
        low_rules = [item["ruleId"] for item in model["ruleMechanicalInformationGain"] if item["classification"] == "low_abstraction"]
        lines += ["", "### 当前为什么显得浅", ""]
        if not model["supportingRuleIds"]:
            lines.append("- 当前只有表现观察或 Gap，没有可承载系统行为的 Approved Rule，因此无法形成确认机制链。")
        else:
            lines.append(f"- 当前仅 {confirmed} 个节点有 Rule 支撑；另有 {inferred} 个结构节点和 {unresolved} 个未解决节点不能写成确认规则。")
        if low_rules:
            lines.append(f"- 低抽象层级 Rule：{', '.join(low_rules)}；它们提供输入或单步事实，但尚未同时说明处理后果或边界。")
        lines += [f"- Mechanic Depth Score：{depth_by_id[model['mechanicId']]['score']} / 100", ""]
    return "\n".join(lines)


def generate_phase53_artifacts(output_dir: Path = DEFAULT_OUT) -> dict[str, Any]:
    sources = (SOURCE, ENTITY_GRAPH, EXECUTION_DELIVERY, CORPUS_PATH)
    before = {path: _sha(path) for path in sources}
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    graph = json.loads(ENTITY_GRAPH.read_text(encoding="utf-8"))
    corpus = load_mechanic_structure_corpus(CORPUS_PATH)
    chapters = [chapter for chapter in source["chapters"] if chapter["chapterId"] in FOCUS_CHAPTER_IDS]
    rules = _approved_rules(source)
    models = build_mechanic_models(chapters, rules, source["gaps"], {}, graph, corpus)
    depth = evaluate_mechanic_depth(models)
    rules_by_id = {rule["ruleId"]: rule for rule in rules}
    observation_only = [
        item["name"] for item in depth["perMechanic"] if item["observationOnlyWithoutSystemAbstraction"]
    ]
    status_counts = {
        status: sum(node["status"] == status for model in models for node in model["nodes"])
        for status in ("confirmed", "inferred_structure", "unresolved", "not_applicable")
    }
    result = {
        "phase": "5.3",
        "mechanicModelCount": len(models),
        "nodeStatusCounts": status_counts,
        "unmappedGapCount": sum(len(model["unmappedGapIds"]) for model in models),
        "observationOnlyMechanics": observation_only,
        "mechanicDepthScore": depth["total"],
        "mechanicalInformationGain": depth["mechanicalInformationGain"],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "mechanic-models.json").write_text(json.dumps(models, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "mechanic-depth-report.json").write_text(json.dumps(depth, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "phase53-summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "six-mechanic-reconstruction-audit.md").write_text(_audit_markdown(models, rules_by_id, depth), encoding="utf-8")
    (output_dir / "mechanic-structure-corpus-audit.md").write_text(
        "# MechanicStructureCorpus Audit\n\n"
        "- source scope: single_document_observation\n"
        "- provisional: true\n"
        "- content authority: none\n"
        "- can close Gap: false\n"
        "- runtime excludes: raw sentences, project fields, values, rules, chapter tree and Gap answers\n",
        encoding="utf-8",
    )
    after = {path: _sha(path) for path in sources}
    provenance = {
        "sourceHashes": {str(path.relative_to(ROOT)): digest for path, digest in before.items()},
        "sourceFilesUnchanged": before == after,
        "modifiedRuleCount": 0,
        "modifiedGapCount": 0,
        "modifiedEntityGraphCount": 0,
        "modifiedExecutionDocumentCount": 0,
        "modifiedP7Count": 0,
        "modifiedUiCount": 0,
        "parameterResolverInvoked": False,
        "inferredStructurePromotedToRuleCount": 0,
    }
    (output_dir / "provenance.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps(generate_phase53_artifacts(), ensure_ascii=False, indent=2))
