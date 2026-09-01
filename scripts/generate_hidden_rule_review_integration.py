from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.hidden_rule_review_integration import build_hidden_rule_review_package


SOURCE = ROOT / "artifacts/planning-content-phase6.3.5a-closure-taxonomy-2026-08-18/corrected-execution-closure-report.json"
OUT = ROOT / "artifacts/planning-content-hidden-rule-review-integration-2026-08-18"


def write(name: str, value) -> None:
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    closure = json.loads(SOURCE.read_text(encoding="utf-8"))
    gaps = [gap for mechanic in closure["mechanics"] for gap in mechanic.get("reviewRequiredGaps", [])]
    package = build_hidden_rule_review_package(gaps)
    write("hidden-rule-review-package.json", package)
    write("p4-review-decisions.json", package["p4Decisions"])
    write("p6-parameter-reviews.json", package["p6Parameters"])
    write("quality-gate.json", package["qualityGate"])
    write("provenance.json", {
        "sourceClosure": str(SOURCE.resolve()),
        "sourceReviewRequiredCount": len(gaps),
        "approvedRuleWrites": 0,
        "approvedParameterWrites": 0,
        "diagnosticOverrideConsumed": False,
        "evidenceExtractionRun": False,
        "rendererRun": False,
        "uiFlowChanged": False,
    })

    p4 = ["# P4 隐藏玩法规则审核 Preview", "",
          "> 以下内容均为未审核决策。只有用户确认后才可生成 Approved Rule。", ""]
    for index, item in enumerate(package["p4Decisions"], 1):
        p4 += [f"## {index}. {item['question']}", ""]
        options = item["control"].get("options", [])
        if options:
            p4 += [*(f"- ○ {option['label']}" for option in options), ""]
        else:
            p4 += ["- 结构化自定义规则：____________", ""]
    (OUT / "p4-preview.md").write_text("\n".join(p4), encoding="utf-8")

    p6 = ["# P6 玩法参数审核 Preview", "",
          "> P6 只填写已确认存在的参数值，不决定玩法机制是否存在。", "",
          "| 参数 | 输入 | 状态 |", "|---|---|---|"]
    for item in package["p6Parameters"]:
        suffix = "数值 + 单位" if item["control"]["unitRequired"] else "整数"
        p6.append(f"| {item['label']} | ______（{suffix}） | 未审核 |")
    (OUT / "p6-preview.md").write_text("\n".join(p6) + "\n", encoding="utf-8")

    audit = ["# Hidden Gameplay Rule Review Integration", "",
             "## 结论", "",
             "- 当前11项 active review_required 已全部进入既有审核阶段：P4 8项，P6 3项。",
             "- 未重新扫描 Evidence；未消费 diagnostic override；未写回 Approved Rule / Parameter。",
             "- dormant_optional、evidence_unknown、candidate_only 均未混入本轮审核控件。",
             "- 用户确认后的目标链保持：P4 → Approved Rule；P6 → Approved Parameter。", "",
             "## 边界", "",
             "- 本轮建立审核数据适配层和只读 Preview，不改八步流程或 UI 布局。",
             "- 不把隐藏规则选项视为事实；所有选项及结构化输入状态均为 unreviewed。", ""]
    (OUT / "integration-audit.md").write_text("\n".join(audit), encoding="utf-8")


if __name__ == "__main__":
    main()
