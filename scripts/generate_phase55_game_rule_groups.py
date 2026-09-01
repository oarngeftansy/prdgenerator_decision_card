from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from backend.game_rule_decision_reconstruction import evaluate_rule_group_granularity, reconstruct_game_rule_groups


ROOT = Path(__file__).resolve().parents[1]
SCOPED = ROOT / "artifacts/planning-content-phase5.4.4-mechanic-scope-2026-08-17/scoped-game-rule-models.json"
RULES = ROOT / "artifacts/planning-content-phase3-2026-08-17/phase-3-gap-result.json"
ENTITY = ROOT / "artifacts/planning-content-phase5-2026-08-17/entity-graph.json"
GVE16 = ROOT / "data/calibration/gve16/game-rule-corpus.json"
EXTERNAL = ROOT / "data/calibration/external-game-design-corpus.json"
DEFAULT_OUT = ROOT / "artifacts/planning-content-phase5.5-game-rule-groups-2026-08-17"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _md(models: list[dict[str, Any]], groups: list[dict[str, Any]], report: dict[str, Any]) -> str:
    by_mechanic: dict[str, list[dict[str, Any]]] = {}
    for group in groups:
        by_mechanic.setdefault(group["mechanicId"], []).append(group)
    lines = ["# Phase 5.5 Game Rule Decision Reconstruction", "",
             "> 本产物只组织已通过 Scope Gate 的玩法规则。未生成正文，未修改 Approved Rule / Gap，未调用 ParameterResolver。", ""]
    for model in models:
        lines += [f"## {model['name']}", "", "### Current Confirmed Scope", ""]
        active = [s for s in model.get("mechanicScopes", []) if s["existenceStatus"] in {"confirmed", "strongly_implied"}]
        lines += [f"- `{s['scopeItem']}`（{s['existenceStatus']}）" for s in active] or ["- 无。"]
        lines += ["", "### GameRuleGroup", ""]
        for group in by_mechanic.get(model["mechanicId"], []):
            lines += [f"#### {group['title']}", "", f"- ruleCategory：`{group['ruleCategory']}`", "- Known Rules："]
            lines += [f"  - {r['text']}（{r['ruleId']}）" for r in group["knownRules"]] or ["  - 无。"]
            lines += ["- Missing Game Rules："]
            lines += [f"  - `{r['semantic']}`（{r['sourceId']}）" for r in group["missingRules"]] or ["  - 无。"]
            lines += ["- Gameplay Parameters："]
            lines += [f"  - `{p['semantic']}` → `{p.get('contract', '待定义')}`" for p in group["gameplayParameters"]] or ["  - 无。"]
            lines += ["- Related Systems："]
            lines += [f"  - `{r}`" for r in group["relatedSystems"]] or ["  - 无。"]
            lines.append("")
        rejected = [s for s in model.get("mechanicScopes", []) if s["existenceStatus"] not in {"confirmed", "strongly_implied"}]
        lines += ["### Rejected possible / unsupported dimensions", ""]
        lines += [f"- `{s['scopeItem']}`（{s['existenceStatus']}）" for s in rejected] or ["- 无。"]
        lines += ["", "### Implementation details excluded", ""]
        lines += [f"- `{x['semantic']}`" for x in model.get("implementationDetails", [])] or ["- 无。"]
        lines.append("")
    lines += ["## Rule Group Granularity Gate", "", f"- qualityGate：`{report['qualityGate']}`",
              f"- groupCount：{report['groupCount']}", f"- one Gap one heading：{report['oneGapOneHeadingCount']}",
              f"- parameter promoted to group：{report['parameterPromotedToGroupCount']}",
              f"- implementation pollution：{report['implementationDetailPollutionCount']}",
              f"- duplicate sibling group：{report['duplicateSiblingGroupCount']}",
              f"- non-gameplay theme title：{report['nonGameplayThemeTitleCount']}",
              f"- unsupported scope group：{report['unsupportedScopeGroupCount']}", ""]
    return "\n".join(lines)


def generate_phase55(output_dir: Path = DEFAULT_OUT) -> dict[str, Any]:
    sources = [SCOPED, RULES, ENTITY, GVE16, EXTERNAL]
    before = {str(p.relative_to(ROOT)): _sha(p) for p in sources}
    models = json.loads(SCOPED.read_text(encoding="utf-8"))
    rule_payload = json.loads(RULES.read_text(encoding="utf-8"))
    entity = json.loads(ENTITY.read_text(encoding="utf-8"))
    corpora = {"gve16": json.loads(GVE16.read_text(encoding="utf-8")),
               "external": json.loads(EXTERNAL.read_text(encoding="utf-8"))}
    groups = reconstruct_game_rule_groups(models, rule_payload["rules"], entity, corpora)
    report = evaluate_rule_group_granularity(groups, models)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "game-rule-groups.json").write_text(json.dumps(groups, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "rule-group-granularity-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "six-chapter-game-rule-groups.md").write_text(_md(models, groups, report), encoding="utf-8")
    after = {str(p.relative_to(ROOT)): _sha(p) for p in sources}
    summary = {"phase": "5.5-game-rule-decision-reconstruction", "groupCount": len(groups),
               "granularityGate": report["qualityGate"], "sourceFilesUnchanged": before == after,
               "modifiedApprovedRuleCount": 0, "modifiedApprovedGapCount": 0,
               "finalDocumentGenerated": False, "parameterResolverInvoked": False}
    (output_dir / "phase55-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "provenance.json").write_text(json.dumps({"sourceHashes": before, **summary}, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(generate_phase55(), ensure_ascii=False, indent=2))
