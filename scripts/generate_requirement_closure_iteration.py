from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.mechanic_requirement_discovery import promote_fact_bundle_to_rule, reassess_requirement


SOURCE = ROOT / "artifacts/mechanic-requirement-discovery-2026-08-18"
OUT = ROOT / "artifacts/mechanic-requirement-closure-2026-08-18"


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(name: str, value) -> None:
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    report = read(SOURCE / "current-requirements-probed.json")
    promoted = read(SOURCE / "promoted-evidence-facts.json")
    facts = promoted["facts"]
    by_id = {item["requirementId"]: item for item in report["requirements"]}

    rule_specs = {
        "REQ-D38D50123975DCD1": "抽取界面的滚动结果停止后，展示本次获得的3项结果。",
        "REQ-912EBF3C258D69BC": "普通战斗阶段结束后显示首领来袭提示，并进入首领战斗阶段。",
    }
    closure_rules = []
    for requirement_id, text in rule_specs.items():
        rule = promote_fact_bundle_to_rule(
            by_id[requirement_id], facts, rule_text=text, claim_semantics="observed_sequence")
        if rule:
            closure_rules.append(rule)

    # Existing authoritative Rule: enrich identity/coverage only; do not rewrite content.
    closure_rules.append({
        "ruleId": "RULE-6D655A0E67FF",
        "mechanicId": "PMECH-B1DB0C6035A1",
        "valid": True,
        "ruleStatus": "existing_valid",
        "sourceType": "existing_rule",
        "text": "关卡载具当前生命值归零后触发失败事件",
        "sourceFactIds": ["FACT-13D35B534775"],
        "sourceEvidenceIds": ["F0001", "F0012", "F0013"],
        "dimensionIds": ["outcome.failure_trigger"],
        "satisfactionFacets": ["failure_condition", "failure_result"],
        "originRequirementIds": ["REQ-7A9D457FE88C1DC7"],
        "satisfiesRequirementIds": ["REQ-7A9D457FE88C1DC7"],
    })

    before = Counter(item["status"] for item in report["requirements"])
    updated = [reassess_requirement(item, closure_rules) for item in report["requirements"]]
    after = Counter(item["status"] for item in updated)
    active = [item for item in updated if item["status"] not in {"dormant_optional", "not_applicable"}]
    core = [item for item in active if item["dimensionRole"] == "core"]

    per_mechanic = defaultdict(lambda: {"active": 0, "resolved": 0, "core": 0, "coreResolved": 0})
    for item in active:
        metrics = per_mechanic[item["mechanicId"]]
        metrics["active"] += 1
        metrics["resolved"] += item["status"] == "resolved"
        if item["dimensionRole"] == "core":
            metrics["core"] += 1
            metrics["coreResolved"] += item["status"] == "resolved"
    for metrics in per_mechanic.values():
        metrics["closureRate"] = round(metrics["resolved"] / metrics["active"] * 100, 1)
        metrics["coreClosureRate"] = round(metrics["coreResolved"] / metrics["core"] * 100, 1)

    write("closure-rules.json", closure_rules)
    write("requirements-after-closure.json", {
        **report, "requirements": updated,
        "closureIteration": {
            "activeRequirementCount": len(active),
            "beforeStatusCounts": dict(before),
            "afterStatusCounts": dict(after),
            "coreRequirementCount": len(core),
            "coreResolvedCount": sum(item["status"] == "resolved" for item in core),
            "coreClosureRate": round(sum(item["status"] == "resolved" for item in core) / len(core) * 100, 1),
            "perMechanic": dict(per_mechanic),
        },
    })
    write("closure-lineage.json", [{
        "requirementId": rule["satisfiesRequirementIds"][0],
        "ruleId": rule["ruleId"],
        "sourceFactIds": rule.get("sourceFactIds", []),
        "sourceEvidenceIds": rule.get("sourceEvidenceIds", []),
        "sourceType": rule["sourceType"],
    } for rule in closure_rules])


if __name__ == "__main__":
    main()
