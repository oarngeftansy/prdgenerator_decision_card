from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from backend.game_rule_reconstruction import build_game_rule_models, evaluate_game_mechanic_depth, load_game_rule_corpus


ROOT = Path(__file__).resolve().parents[1]
GRAPHS = ROOT / "artifacts/planning-content-phase5.3.2-2026-08-17/semantic-grounded-mechanic-graphs.json"
RULES = ROOT / "artifacts/planning-content-phase3-2026-08-17/phase-3-gap-result.json"
ROUTING = ROOT / "artifacts/planning-content-phase5.4.2-gap-routing-2026-08-17/gap-routing-report.json"
CORPUS = ROOT / "data/calibration/gve16/game-rule-corpus.json"
DEFAULT_OUT = ROOT / "artifacts/planning-content-phase5.4.3-game-rule-reconstruction-2026-08-17"

TYPE_BY_MECHANIC = {
    "PMECH-510C9B81F0BD": "movement", "PMECH-831F3EDC1472": "attack",
    "PMECH-79F65266B17C": "randomization", "PMECH-2C4FBE5EC68C": "monster_attack",
    "PMECH-BBD7CED5E8D0": "level_flow", "PMECH-B1DB0C6035A1": "settlement",
}


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


def _markdown(models: list[dict[str, Any]], depth: dict[str, Any]) -> str:
    lines = ["# Phase 5.4.3 Game Rule & Mechanic Reconstruction", "",
             "> 本阶段只重建玩家可感知的游戏规则空间。Implementation Detail 单独记录，不进入 missingGameRules 或 Planner Review。", ""]
    for model in models:
        known = [item for field in ("acquisitionRules", "usageRules", "unlockRules", "progressionRules", "randomRules",
                                     "stateRules", "limitationRules", "resourceRules", "rewardRules", "victoryFailureRules",
                                     "lifecycleRules") for item in model[field]]
        lines += [f"## {model['name']}", "", f"- gameplayPurpose：{model['gameplayPurpose']}", "",
                  "### 已知游戏规则", ""]
        lines += [f"- `{item['gameRuleType']}`：{item['text']}（{item['ruleId']}）" for item in known] or ["- 无。"]
        if model["rulesUnderReview"]:
            lines += ["", "### 上游规则复核", ""]
            lines += [f"- `{item['ruleId']}`：{item['reason']}" for item in model["rulesUnderReview"]]
        lines += ["", "### 游戏机制骨架", ""]
        lines += [f"- `{item['semantic']}`：{item['status']}" for item in model["gameRuleChecks"]]
        lines += ["", "### 仍缺少的游戏规则", ""]
        lines += [f"- `{item['gameRuleType']}` / `{item['semantic']}` / {item['status']}" for item in model["missingGameRules"]] or ["- 无。"]
        lines += ["", "### 参数需求", ""]
        lines += [f"- `{item['semantic']}` → `{item.get('contract') or '待定义'}`" for item in model["parameterNeeds"]] or ["- 无。"]
        lines += ["", "### Implementation Detail（隐藏层）", ""]
        lines += [f"- `{item['semantic']}`：{item['reason']}" for item in model["implementationDetails"]] or ["- 无。"]
        lines.append("")
    lines += ["## Game Mechanic Depth", "", f"- Total：{depth['total']} / 100"]
    lines += [f"- {key}：{value}" for key, value in depth["dimensions"].items()]
    lines += [f"- Implementation Detail count：{depth['implementationDetailCount']}",
              "- Implementation Details affect score：false", ""]
    return "\n".join(lines)


def generate_phase543_game_rules(output_dir: Path = DEFAULT_OUT) -> dict[str, Any]:
    sources = (GRAPHS, RULES, ROUTING, CORPUS)
    before = {path: _sha(path) for path in sources}
    graphs = json.loads(GRAPHS.read_text(encoding="utf-8"))
    source = json.loads(RULES.read_text(encoding="utf-8"))
    routing = json.loads(ROUTING.read_text(encoding="utf-8"))
    corpus = load_game_rule_corpus(CORPUS)
    models = build_game_rule_models(_chapters(graphs), source["rules"], routing["results"], corpus)
    depth = evaluate_game_mechanic_depth(models)
    summary = {"phase": "5.4.3-game-rule-mechanic-reconstruction", "modelCount": len(models),
               "confirmedGameRuleCount": sum(len(model["confirmedRules"]) for model in models),
               "missingGameRuleCount": sum(len(model["missingGameRules"]) for model in models),
               "parameterNeedCount": sum(len(model["parameterNeeds"]) for model in models),
               "implementationDetailCount": sum(len(model["implementationDetails"]) for model in models),
               "gameMechanicDepth": depth["total"], "implementationDetailsAffectScore": False,
               "finalDocumentGenerated": False, "modifiedApprovedGapCount": 0, "p4WriteCount": 0,
               "parameterResolverInvoked": False}
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, payload in (("game-rule-models.json", models), ("game-mechanic-depth.json", depth),
                          ("phase543-game-rule-summary.json", summary)):
        (output_dir / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "six-chapter-game-rule-reconstruction.md").write_text(_markdown(models, depth), encoding="utf-8")
    after = {path: _sha(path) for path in sources}
    (output_dir / "provenance.json").write_text(json.dumps({
        "sourceHashes": {str(path.relative_to(ROOT)): value for path, value in before.items()},
        "sourceFilesUnchanged": before == after, "modifiedApprovedGapCount": 0, "p4WriteCount": 0,
        "finalDocumentGenerated": False, "parameterResolverInvoked": False,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(generate_phase543_game_rules(), ensure_ascii=False, indent=2))
