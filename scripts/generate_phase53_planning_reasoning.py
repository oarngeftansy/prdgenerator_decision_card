from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from backend.planning_reasoning_corpus import load_planning_reasoning_corpus
from backend.planning_reasoning_depth_evaluator import evaluate_planning_reasoning_depth
from backend.planning_reasoning_layer import build_planning_mechanism_models


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "artifacts/planning-content-phase3-2026-08-17/phase-3-gap-result.json"
ENTITY_GRAPH = ROOT / "artifacts/planning-content-phase5-2026-08-17/entity-graph.json"
EXECUTION = ROOT / "artifacts/planning-content-phase5.1-2026-08-17/phase51-delivery.json"
CORPUS_PATH = ROOT / "data/quality/gve16-planning-reasoning-corpus-v1.json"
DEFAULT_OUT = ROOT / "artifacts/planning-content-phase5.3-planning-reasoning-2026-08-17"
FOCUS = {"V2CH-001", "V2CH-005", "V2CH-009", "V2CH-010", "V2CH-015", "V2CH-017", "V2CH-020", "V2CH-021"}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _approved_rules(source: dict[str, Any]) -> list[dict[str, Any]]:
    rules = json.loads(json.dumps(source["rules"], ensure_ascii=False))
    for rule in rules:
        if rule.get("semanticValidity") == "valid":
            rule["reviewStatus"] = "approved"
    return rules


def _audit(models: list[dict[str, Any]], rules: dict[str, dict[str, Any]], depth: dict[str, Any]) -> str:
    depth_by_id = {item["mechanicId"]: item for item in depth["perMechanic"]}
    lines = [
        "# Phase 5.3 Planning Reasoning Layer：六章只读重建", "",
        "> derived_structure 只证明节点必须被思考；hypothesis 只作为审核建议；二者与 unresolved 均不得生成 Approved Rule、关闭 Gap 或进入正文。", "",
    ]
    for model in models:
        lines += [f"## {model['name']}", "", "### 现有 Rule", ""]
        if model["supportingRuleIds"]:
            lines.extend(f"- `{rule_id}`：{rules[rule_id].get('behavior')}" for rule_id in model["supportingRuleIds"])
        else:
            lines.append("- 无可作为系统行为依据的 Approved Rule。")
        lines += ["", "### PlanningMechanismModel", "", f"- mechanicId: `{model['mechanicId']}`", f"- mechanicType: `{model['mechanicType']}`", f"- actors: {', '.join(model['actors']) or '无确认 actor'}", f"- objects: {', '.join(model['objects']) or '无确认 object'}", "", "### 完整机制骨架", ""]
        for index, node in enumerate(model["nodes"], start=1):
            refs = []
            if node["supportingRuleIds"]:
                refs.append("Rule=" + ",".join(node["supportingRuleIds"]))
            if node["gapLocations"]:
                refs.append("Gap=" + ",".join(item["gapId"] for item in node["gapLocations"]))
            lines.append(f"{index}. `{node['axis']}` / `{node['mechanismNode']}` — **{node['reasoningStatus']}**" + (f"（{'; '.join(refs)}）" if refs else ""))
        for status, key in (("confirmed", "confirmedNodes"), ("derived_structure", "derivedStructureNodes"), ("hypothesis", "hypothesisNodes"), ("unresolved", "unresolvedNodes")):
            lines += ["", f"### {status}", ""]
            selected = model[key]
            lines.extend(f"- `{node['mechanismNode']}`" for node in selected) if selected else lines.append("- 无。")
        lines += ["", "### Gap location", ""]
        if model["localizedGaps"]:
            lines.extend(f"- `{item['gapId']}` → `{item['mechanicId']} / {item['mechanismNode']}`" for item in model["localizedGaps"])
        else:
            lines.append("- 无当前开放 Gap。")
        lines += ["", f"Planning Reasoning Depth：{depth_by_id[model['mechanicId']]['score']} / 100", ""]
    return "\n".join(lines)


def generate_phase53_planning_reasoning(output_dir: Path = DEFAULT_OUT) -> dict[str, Any]:
    sources = (SOURCE, ENTITY_GRAPH, EXECUTION, CORPUS_PATH)
    before = {path: _sha(path) for path in sources}
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    graph = json.loads(ENTITY_GRAPH.read_text(encoding="utf-8"))
    corpus = load_planning_reasoning_corpus(CORPUS_PATH)
    chapters = [chapter for chapter in source["chapters"] if chapter["chapterId"] in FOCUS]
    rules = _approved_rules(source)
    models = build_planning_mechanism_models(chapters, rules, source["gaps"], source["facts"], graph, corpus)
    depth = evaluate_planning_reasoning_depth(models)
    locations = [item for model in models for item in model["localizedGaps"]]
    summary = {
        "phase": "5.3-planning-reasoning", "modelCount": len(models),
        "nodeStatusCounts": depth["nodeStatusCounts"], "localizedGapCount": len(locations),
        "unmappedGapCount": sum(len(model["unmappedGapIds"]) for model in models),
        "planningReasoningDepth": depth["total"], "executionCompletenessContribution": 0,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "planning-mechanism-models.json").write_text(json.dumps(models, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "planning-reasoning-depth-report.json").write_text(json.dumps(depth, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "gap-location-index.json").write_text(json.dumps(locations, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "phase53-planning-reasoning-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "six-chapter-planning-reconstruction.md").write_text(_audit(models, {rule["ruleId"]: rule for rule in rules}, depth), encoding="utf-8")
    after = {path: _sha(path) for path in sources}
    provenance = {
        "sourceHashes": {str(path.relative_to(ROOT)): digest for path, digest in before.items()},
        "sourceFilesUnchanged": before == after, "modifiedRuleCount": 0, "modifiedGapCount": 0,
        "modifiedEntityGraphCount": 0, "modifiedExecutionDocumentCount": 0, "modifiedP7Count": 0,
        "modifiedUiCount": 0, "parameterResolverInvoked": False,
        "derivedStructurePromotedToRuleCount": 0, "hypothesisPromotedToRuleCount": 0,
    }
    (output_dir / "provenance.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(generate_phase53_planning_reasoning(), ensure_ascii=False, indent=2))
