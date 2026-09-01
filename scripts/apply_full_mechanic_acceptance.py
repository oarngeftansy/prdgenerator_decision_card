from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RECONSTRUCTION = ROOT / "artifacts/full-mechanic-reconstruction-2026-08-19"
REQUIREMENTS = ROOT / "artifacts/mechanic-requirement-discovery-2026-08-18/current-requirements.json"
DEFAULT_OUTPUT = ROOT / "artifacts/full-mechanic-acceptance-2026-08-19"


REQUIREMENT_DIMENSIONS_BY_REVIEW_RULE = {
    "DENS-MDES-CHOICE-CORE-01": ["choice.trigger", "choice.candidate_generation"],
    "DENS-MDES-CHOICE-CORE-02": ["choice.pool_algorithm", "choice.duplicate_rule"],
    "DENS-MDES-CHOICE-CORE-03": ["choice.confirm", "choice.apply", "choice.exit", "choice.pause_resume"],
    "DENS-MDES-CHOICE-SPECIAL-01": ["choice.refresh.exists", "choice.refresh.cost"],
    "DENS-MDES-CHOICE-SPECIAL-02": ["choice.refresh.exists", "choice.candidate_generation"],
    "DENS-MDES-CHOICE-SPECIAL-03": ["choice.pool_algorithm"],
    "DENS-MDES-WEAPON-CORE-02": ["weapon.acquire", "weapon.slot_activation"],
    "DENS-MDES-WEAPON-CORE-03": ["weapon.slot_activation", "weapon.attack_trigger"],
    "DENS-MDES-WEAPON-CORE-04": ["weapon.cooldown", "weapon.damage_trigger"],
    "DENS-MDES-WEAPON-CORE-05": ["weapon.cooldown", "weapon.damage_trigger"],
    "DENS-MDES-WEAPON-SPECIAL-01": ["weapon.slot_full", "weapon.replacement_removal"],
    "DENS-MDES-MONSTER-CORE-02": ["attack.entry"],
    "DENS-MDES-MONSTER-SPECIAL-01": ["attack.multiple_attackers"],
    "DENS-MDES-MONSTER-SPECIAL-02": ["attack.pause_resume"],
}


MECHANIC_IDS = {
    "MDES-CHOICE": "PMECH-79F65266B17C",
    "MDES-WEAPON": "PMECH-831F3EDC1472",
    "MDES-MONSTER": "PMECH-2C4FBE5EC68C",
}

OWNER_PATH_BY_REVIEW_RULE = {
    "DENS-MDES-CHOICE-CORE-01": ["局内成长", "三选一", "触发"],
    "DENS-MDES-CHOICE-CORE-02": ["局内成长", "三选一", "候选生成"],
    "DENS-MDES-CHOICE-CORE-03": ["局内成长", "三选一", "选择与生效"],
    "DENS-MDES-CHOICE-SPECIAL-01": ["局内成长", "三选一", "刷新"],
    "DENS-MDES-CHOICE-SPECIAL-02": ["局内成长", "三选一", "刷新"],
    "DENS-MDES-CHOICE-SPECIAL-03": ["局内成长", "三选一", "候选不足"],
    "DENS-MDES-WEAPON-CORE-02": ["核心战斗", "武器", "武器栏"],
    "DENS-MDES-WEAPON-CORE-03": ["核心战斗", "武器", "攻击"],
    "DENS-MDES-WEAPON-CORE-04": ["核心战斗", "武器", "攻击"],
    "DENS-MDES-WEAPON-CORE-05": ["核心战斗", "武器", "攻击"],
    "DENS-MDES-WEAPON-SPECIAL-01": ["核心战斗", "武器", "武器栏"],
    "DENS-MDES-MONSTER-CORE-02": ["怪物", "普通怪物", "攻击"],
    "DENS-MDES-MONSTER-SPECIAL-01": ["怪物", "普通怪物", "攻击"],
    "DENS-MDES-MONSTER-SPECIAL-02": ["怪物", "普通怪物", "暂停与恢复"],
}


def _stable_id(prefix: str, value: str) -> str:
    return f"{prefix}-{hashlib.sha256(value.encode('utf-8')).hexdigest()[:16].upper()}"


def _write(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(output_dir: Path | None = None) -> None:
    output_dir = output_dir or DEFAULT_OUTPUT
    output_dir.mkdir(parents=True, exist_ok=True)
    projection = json.loads((RECONSTRUCTION / "planner-readable-preview.json").read_text(encoding="utf-8"))
    models = json.loads((RECONSTRUCTION / "reconstructed-models.json").read_text(encoding="utf-8"))
    requirement_payload = json.loads(REQUIREMENTS.read_text(encoding="utf-8"))
    requirement_by_dimension = {
        item["executionDimensionId"]: item for item in requirement_payload["requirements"]
    }
    model_by_id = {item["mechanicDesignId"]: item for item in models}
    registered_requirements = []
    approved_rules = []
    decisions = []
    retained_confirmed = 0
    closure: dict[str, list[str]] = {}

    for review in projection:
        mechanic_design_id = review["mechanicDesignId"]
        model_items = {item["designItemId"]: item for item in model_by_id[mechanic_design_id]["designItems"]}
        for group_name in ("coreRules", "specialRules"):
            for review_rule in review["defaultReview"][group_name]:
                if review_rule["knowledgeClass"] == "confirmed":
                    retained_confirmed += 1
                    decisions.append({
                        "sourceReviewRuleId": review_rule["reviewRuleId"],
                        "action": "retain_confirmed",
                        "sourceDesignItemIds": review_rule["sourceDesignItemIds"],
                    })
                    continue
                dimensions = REQUIREMENT_DIMENSIONS_BY_REVIEW_RULE.get(review_rule["reviewRuleId"])
                if not dimensions:
                    raise ValueError(f"accepted review rule lacks deterministic requirement mapping: {review_rule['reviewRuleId']}")
                requirement_ids = []
                for dimension in dimensions:
                    requirement = requirement_by_dimension.get(dimension)
                    if requirement is None:
                        requirement = {
                            "requirementId": _stable_id("REQ", f"{MECHANIC_IDS[mechanic_design_id]}:{dimension}"),
                            "mechanicId": MECHANIC_IDS[mechanic_design_id],
                            "executionDimensionId": dimension,
                            "status": "review_required",
                            "reopenable": False,
                            "priorSource": {"type": "rule_gap", "ref": review_rule["reviewRuleId"]},
                            "registeredFromAcceptedReviewRuleId": review_rule["reviewRuleId"],
                        }
                        requirement_by_dimension[dimension] = requirement
                        registered_requirements.append(requirement)
                    requirement_ids.append(requirement["requirementId"])
                source_items = [model_items[item_id] for item_id in review_rule["sourceDesignItemIds"]]
                rule_id = _stable_id("RULE", f"{review_rule['reviewRuleId']}:accept:{review_rule['text']}")
                rule = {
                    "ruleId": rule_id,
                    "mechanicId": MECHANIC_IDS[mechanic_design_id],
                    "mechanicDesignId": mechanic_design_id,
                    "valid": True,
                    "ruleStatus": "approved_review",
                    "sourceType": "planner_approved_mechanic_review",
                    "sourceReviewRuleId": review_rule["reviewRuleId"],
                    "sourceDesignItemIds": review_rule["sourceDesignItemIds"],
                    "sourceProposalIds": sorted({proposal_id for item in source_items
                                                 for proposal_id in item.get("sourceProposalIds", [])}),
                    "text": review_rule["text"],
                    "planningOwnerPath": OWNER_PATH_BY_REVIEW_RULE[review_rule["reviewRuleId"]],
                    "dimensionIds": dimensions,
                    "originRequirementIds": requirement_ids,
                    "satisfiesRequirementIds": requirement_ids,
                    "approvalAction": "accept_all_visible_inferences",
                }
                approved_rules.append(rule)
                decisions.append({
                    "sourceReviewRuleId": review_rule["reviewRuleId"],
                    "action": "accept",
                    "approvedRuleId": rule_id,
                    "sourceDesignItemIds": review_rule["sourceDesignItemIds"],
                    "satisfiesRequirementIds": requirement_ids,
                })
                for requirement_id in requirement_ids:
                    closure.setdefault(requirement_id, []).append(rule_id)

    alternative_decisions = []
    for review in projection:
        for alternative in review["defaultReview"]["decisionPoints"]:
            alternative_decisions.append({
                "alternativeId": alternative["alternativeId"],
                "selectedOptionId": alternative["recommendedOptionId"],
                "action": "accept_recommended",
            })

    _write(output_dir / "approved-review-rules.json", {
        "rules": approved_rules,
        "approvedRuleCount": len(approved_rules),
        "publicationEligible": False,
    })
    _write(output_dir / "review-decisions.json", {
        "action": "accept_all",
        "approvalGranularity": "visible_review_rule",
        "decisions": decisions,
        "retainedConfirmedRuleCount": retained_confirmed,
        "alternativeDecisions": alternative_decisions,
    })
    _write(output_dir / "registered-requirements.json", {
        "requirements": registered_requirements,
        "sourceRequirementMutationCount": 0,
    })
    _write(output_dir / "requirement-closure-overlay.json", {
        "requirements": [
            {"requirementId": requirement_id, "status": "resolved",
             "satisfiedByRuleIds": sorted(rule_ids)}
            for requirement_id, rule_ids in sorted(closure.items())
        ],
        "sourceRequirementMutationCount": 0,
    })


if __name__ == "__main__":
    main()
