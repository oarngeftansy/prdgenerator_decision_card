from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.mechanic_requirement_discovery import (
    discover_requirements,
    project_chain_dimension_satisfaction,
    recognize_benchmark_mechanics,
    review_question_for_dimension,
    evaluate_planner_relevance,
)


MODEL_PATH = ROOT / "artifacts/planning-content-phase5.4.4-mechanic-scope-2026-08-17/scoped-game-rule-models.json"
CHAIN_PATH = ROOT / "artifacts/planning-content-phase5.6-gameplay-rule-chains-2026-08-17/gameplay-rule-chains.json"
FACT_PATH = ROOT / "artifacts/planning-content-phase6.2.2-game-rule-synthesis-2026-08-17/observation-fact-rule-synthesis.json"
OUT = ROOT / "artifacts/mechanic-requirement-discovery-2026-08-18"
APPROVED_RULES_PATH = OUT / "approved-business-rules.json"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    models = load(MODEL_PATH)
    chains = load(CHAIN_PATH)
    facts = load(FACT_PATH)
    observations = [item["observationDimension"] for item in facts]
    mechanics = recognize_benchmark_mechanics(models, chains, observations)
    projected_rules = project_chain_dimension_satisfaction(chains)
    approved_rules = load(APPROVED_RULES_PATH) if APPROVED_RULES_PATH.exists() else []
    projected_rules.extend(approved_rules)
    requirements = discover_requirements(mechanics, rules=projected_rules)
    review_items = []
    for item in requirements:
        if item["status"] != "review_required":
            continue
        impacts = {
            "statistics.additional_effect_attribution": ["gameplay_rule", "qa_acceptance"],
            "statistics.settlement_snapshot": ["qa_acceptance", "player_state"],
        }.get(item["executionDimensionId"], ["gameplay_rule"])
        relevance = evaluate_planner_relevance({"decisionImpacts": impacts})
        if relevance["action"] != "retain":
            continue
        review_items.append({
            "reviewItemId": f"{item['routingTarget']}-{item['requirementId'][4:]}",
            "requirementId": item["requirementId"],
            "ownerPath": item["ownerPath"],
            "executionDimensionId": item["executionDimensionId"],
            "reviewType": item["reviewType"],
            "routingTarget": item["routingTarget"],
            "question": review_question_for_dimension(item["executionDimensionId"]),
            "decisionImpacts": impacts,
            "plannerRelevance": relevance,
        })
    OUT.mkdir(parents=True, exist_ok=True)
    payload = {
        "sourceModels": str(MODEL_PATH.relative_to(ROOT)),
        "sourceChains": str(CHAIN_PATH.relative_to(ROOT)),
        "sourceFacts": str(FACT_PATH.relative_to(ROOT)),
        "mechanics": mechanics,
        "projectedSatisfactionRules": projected_rules,
        "requirements": requirements,
        "reviewItems": review_items,
        "publicationEligible": False,
    }
    (OUT / "current-requirements.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    names = {item["mechanicId"]: item["ownerPath"]["mechanic"] for item in mechanics}
    lines = ["# 《一路狂飙》Mechanic Requirements", "",
             "> 仅消费结构化 Mechanic、Phase 5.6 chain semantic 与现有 Fact；Requirement 不进入正式正文。", ""]
    for mechanic in mechanics:
        mechanic_id = mechanic["mechanicId"]
        lines.extend([f"## {names[mechanic_id]} (`{mechanic_id}`)", ""])
        items = [item for item in requirements if item["mechanicId"] == mechanic_id]
        for status in ("resolved", "evidence_probe", "evidence_resolvable", "evidence_unknown",
                       "review_required", "dormant_optional", "not_applicable"):
            selected = [item for item in items if item["status"] == status]
            lines.extend([f"### {status} ({len(selected)})", ""])
            lines.extend([f"- `{item['executionDimensionId']}`" +
                          (f" → {item['routingTarget']}" if item.get("routingTarget") else "")
                          for item in selected] or ["- 无"])
            lines.append("")
    lines.extend(["## P4/P6 新问题", ""])
    for route in ("P4", "P6"):
        lines.extend([f"### {route}", ""])
        selected = [item for item in review_items if item["routingTarget"] == route]
        lines.extend([f"- {item['ownerPath'].get('mechanic') or item['ownerPath'].get('system')} / "
                      f"`{item['executionDimensionId']}`：{item['question']}"
                      for item in selected] or ["- 无"])
        lines.append("")
    (OUT / "current-requirements.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
