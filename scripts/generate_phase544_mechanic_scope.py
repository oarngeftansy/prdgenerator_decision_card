from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from backend.game_rule_reconstruction import build_game_rule_models, load_game_rule_corpus
from backend.mechanic_scope_inference import apply_mechanic_scope, evaluate_scope_precision, infer_mechanic_scopes


ROOT = Path(__file__).resolve().parents[1]
GRAPHS = ROOT / "artifacts/planning-content-phase5.3.2-2026-08-17/semantic-grounded-mechanic-graphs.json"
RULES = ROOT / "artifacts/planning-content-phase3-2026-08-17/phase-3-gap-result.json"
ROUTING = ROOT / "artifacts/planning-content-phase5.4.2-gap-routing-2026-08-17/gap-routing-report.json"
ENTITY = ROOT / "artifacts/planning-content-phase5-2026-08-17/entity-graph.json"
CORPUS = ROOT / "data/calibration/gve16/game-rule-corpus.json"
DEFAULT_OUT = ROOT / "artifacts/planning-content-phase5.4.4-mechanic-scope-2026-08-17"

TYPE_BY_MECHANIC = {"PMECH-510C9B81F0BD": "movement", "PMECH-831F3EDC1472": "attack",
                    "PMECH-79F65266B17C": "randomization", "PMECH-2C4FBE5EC68C": "monster_attack",
                    "PMECH-BBD7CED5E8D0": "level_flow", "PMECH-B1DB0C6035A1": "settlement"}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _chapters(graphs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for graph in graphs:
        object_name, _, title = graph["name"].partition(" / ")
        result.append({"mechanicId": graph["mechanicId"], "chapterId": graph["chapterId"],
                       "chapterType": TYPE_BY_MECHANIC[graph["mechanicId"]], "object": object_name,
                       "title": title or object_name, "supportingRuleIds": graph.get("supportingRuleIds", [])})
    return result


def _markdown(models: list[dict[str, Any]], precision: dict[str, Any]) -> str:
    lines = ["# Phase 5.4.4 Mechanic Scope Audit", "",
             "> 先证明子机制存在，再展开规则。possible / unsupported / contradicted 只保留为探索或复核，不生成 missingGameRules。", ""]
    for model in models:
        lines += [f"## {model['name']}", ""]
        for status in ("confirmed", "strongly_implied", "possible", "unsupported", "contradicted"):
            items = [item for item in model["mechanicScopes"] if item["existenceStatus"] == status]
            lines += [f"### {status}", ""]
            lines += [f"- `{item['scopeItem']}`：{item['applicabilityReason']}"
                      f"（Rule={','.join(item['ruleBasis']) or '-'}；UI={','.join(item['uiBasis']) or '-'}；Relation={','.join(item['relationshipBasis']) or '-'}）"
                      for item in items] or ["- 无。"]
            lines.append("")
        lines += ["### knownGameRules", ""]
        lines += [f"- {item['text']}（{item['ruleId']}）" for item in model["knownGameRules"]] or ["- 无。"]
        lines += ["", "### missingGameRules（仅 active scope）", ""]
        lines += [f"- `{item['semantic']}` / scope=`{item['scopeItem']}` / {item['scopeStatus']}" for item in model["missingGameRules"]] or ["- 无。"]
        lines += ["", "### gameplayParameters", ""]
        lines += [f"- `{item['semantic']}` → `{item.get('contract') or '待定义'}`" for item in model["gameplayParameters"]] or ["- 无。"]
        lines += ["", "### conditional gameplayParameters", ""]
        lines += [f"- `{item['semantic']}`：{item['applicability']}" for item in model["conditionalGameplayParameters"]] or ["- 无。"]
        lines += ["", "### Implementation Detail（隐藏层）", ""]
        lines += [f"- `{item['semantic']}`：{item['reason']}" for item in model["implementationDetails"]] or ["- 无。"]
        lines.append("")
    lines += ["## Scope Precision", "", f"- qualityGate：`{precision['qualityGate']}`",
              f"- unsupported mechanic instantiated：{precision['unsupportedInstantiatedCount']}",
              f"- template-only mechanic instantiated：{precision['templateOnlyInstantiatedCount']}",
              f"- current-evidence-supported scope ratio：{precision['currentEvidenceSupportedScopeRatio'] * 100:.2f}%", ""]
    return "\n".join(lines)


def generate_phase544(output_dir: Path = DEFAULT_OUT) -> dict[str, Any]:
    sources = (GRAPHS, RULES, ROUTING, ENTITY, CORPUS)
    before = {path: _sha(path) for path in sources}
    graphs = json.loads(GRAPHS.read_text(encoding="utf-8")); source = json.loads(RULES.read_text(encoding="utf-8"))
    routing = json.loads(ROUTING.read_text(encoding="utf-8")); entity = json.loads(ENTITY.read_text(encoding="utf-8"))
    corpus = load_game_rule_corpus(CORPUS); chapters = _chapters(graphs)
    scopes = infer_mechanic_scopes(chapters, source["rules"], routing["results"], entity, corpus)
    scope_rules: dict[str, set[str]] = {}
    for scope in scopes:
        scope_rules.setdefault(scope["mechanicId"], set()).update(scope["ruleBasis"])
    for chapter in chapters:
        chapter["supportingRuleIds"] = sorted(set(chapter.get("supportingRuleIds", [])) | scope_rules.get(chapter["mechanicId"], set()))
    base = build_game_rule_models(chapters, source["rules"], routing["results"], corpus)
    models = apply_mechanic_scope(base, scopes); precision = evaluate_scope_precision(scopes, models)
    status_counts = {status: sum(item["existenceStatus"] == status for item in scopes)
                     for status in ("confirmed", "strongly_implied", "possible", "unsupported", "contradicted")}
    summary = {"phase": "5.4.4-mechanic-scope-inference", "scopeCount": len(scopes), "scopeStatusCounts": status_counts,
               "instantiatedMissingGameRuleCount": sum(len(model["missingGameRules"]) for model in models),
               "gameplayParameterCount": sum(len(model["gameplayParameters"]) for model in models),
               "conditionalGameplayParameterCount": sum(len(model["conditionalGameplayParameters"]) for model in models),
               "implementationDetailCount": sum(len(model["implementationDetails"]) for model in models),
               "scopePrecision": precision, "finalDocumentGenerated": False, "modifiedApprovedGapCount": 0,
               "p4WriteCount": 0, "parameterResolverInvoked": False}
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, payload in (("mechanic-scopes.json", scopes), ("scoped-game-rule-models.json", models),
                          ("scope-precision.json", precision), ("phase544-summary.json", summary)):
        (output_dir / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "six-chapter-scope-audit.md").write_text(_markdown(models, precision), encoding="utf-8")
    after = {path: _sha(path) for path in sources}
    (output_dir / "provenance.json").write_text(json.dumps({"sourceHashes": {str(p.relative_to(ROOT)): v for p, v in before.items()},
        "sourceFilesUnchanged": before == after, "modifiedApprovedGapCount": 0, "p4WriteCount": 0,
        "finalDocumentGenerated": False, "parameterResolverInvoked": False}, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(generate_phase544(), ensure_ascii=False, indent=2))
