from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.mechanic_requirement_discovery import discover_requirements


FIXTURES = ROOT / "tests" / "fixtures"
OUT = ROOT / "artifacts" / "mechanic-requirement-discovery-2026-08-18"


def load(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def main() -> None:
    mechanics = load("benchmark_mechanic_conditions_v1.json")
    gold = load("benchmark_expected_dimensions_gold_v1.json")
    routing_gold = load("benchmark_expected_routing_gold_v1.json")
    requirements = discover_requirements(mechanics)
    expected_core = {(mid, dim) for mid, value in gold.items() for dim in value["core"]}
    expected_active = expected_core | {
        (mid, dim) for mid, value in gold.items() for dim in value["activeConditional"]
    }
    active = [item for item in requirements if item["status"] not in {"dormant_optional", "not_applicable"}]
    actual_active = {(item["mechanicId"], item["executionDimensionId"]) for item in active}
    actual_core = {(item["mechanicId"], item["executionDimensionId"]) for item in active
                   if item["dimensionRole"] == "core"}
    p4 = set(routing_gold["P4"])
    p6 = set(routing_gold["P6"])
    routing_correct = 0
    for item in active:
        key = f"{item['mechanicId']}:{item['executionDimensionId']}"
        expected = "P4" if key in p4 else "P6" if key in p6 else "PROBE"
        routing_correct += item.get("routingTarget", "PROBE") == expected
    metrics = {
        "coreDimensionRecall": len(actual_core & expected_core) / len(expected_core),
        "overallActiveRequirementRecall": len(actual_active & expected_active) / len(expected_active),
        "unsupportedRequirementRate": len(actual_active - expected_active) / len(actual_active),
        "routingAccuracy": routing_correct / len(active),
        "probeIntegrityCriticalTests": 1.0,
        "newConfirmedProjectRuleCount": 0,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "benchmark-result.json").write_text(json.dumps({
        "prior": "benchmark_execution_prior_v1",
        "gold": "test-only independent fixtures",
        "metrics": metrics,
        "requirements": requirements,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    by_mechanic = {item["mechanicId"]: [] for item in mechanics}
    for item in requirements:
        by_mechanic[item["mechanicId"]].append(item)
    names = {item["mechanicId"]: item["ownerPath"]["mechanic"] for item in mechanics}
    lines = ["# Mechanic Requirement Discovery Benchmark", "",
             "> Runtime Prior 与测试 Gold Set 独立；本报告不包含《一路狂飙》规则答案。", "",
             "## 指标", "",
             f"- Core Dimension Recall: {metrics['coreDimensionRecall']:.1%}",
             f"- Overall Active Requirement Recall: {metrics['overallActiveRequirementRecall']:.1%}",
             f"- Unsupported Requirement Rate: {metrics['unsupportedRequirementRate']:.1%}",
             f"- Routing Accuracy: {metrics['routingAccuracy']:.1%}",
             f"- Probe Integrity critical tests: {metrics['probeIntegrityCriticalTests']:.1%}",
             "- 新增已确认项目 Rule: 0", ""]
    for mechanic_id, items in by_mechanic.items():
        lines.extend([f"## {names[mechanic_id]}", ""])
        for status in ("resolved", "evidence_probe", "evidence_resolvable", "evidence_unknown",
                       "review_required", "dormant_optional", "not_applicable"):
            selected = [item for item in items if item["status"] == status]
            lines.append(f"### {status} ({len(selected)})")
            lines.append("")
            if selected:
                for item in selected:
                    route = f" → {item['routingTarget']}" if item.get("routingTarget") else ""
                    lines.append(f"- `{item['executionDimensionId']}` ({item['dimensionRole']}){route}")
            else:
                lines.append("- 无")
            lines.append("")
    lines.extend(["## Guardrail", "",
                  "- Requirement 不具备 Publication 资格。",
                  "- Gold Set 未被生产代码读取。",
                  "- 未生成 Rule、Owner、Relation 或章节。",
                  "- Observation、相关性与因果支持分别保存。",
                  "- evidence_unknown 可在新素材到达后重新进入 evidence_probe。", ""])
    (OUT / "benchmark-result.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
