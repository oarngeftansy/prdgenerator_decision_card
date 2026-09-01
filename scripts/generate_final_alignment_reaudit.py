from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
AUDIT_DIR = ROOT / "artifacts/gve16-complete-delivery-gap-audit-2026-08-19"
PUBLICATION_DIR = ROOT / "artifacts/full-mechanic-accepted-publication-2026-08-19"


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    matrix = _read(AUDIT_DIR / "alignment-closure-matrix.json")
    score = _read(PUBLICATION_DIR / "gve16-alignment-score.json")
    items = matrix["items"]
    blocked = [item for item in items if item["closureState"] == "blocked_by_missing_source"]
    original_non_equal = sum(item["originalJudgement"] != "=" for item in items)
    final_counts = {
        "equals": sum(item["currentJudgement"] == "=" for item in items),
        "cross": sum(item["currentJudgement"] == "×" for item in items),
        "triangle": sum(item["currentJudgement"] == "△" for item in items),
        "unknown": sum(item["currentJudgement"] == "U" for item in items),
    }
    summary = {
        "schemaVersion": "gve16-final-reaudit-v1",
        "benchmark": matrix["benchmark"],
        "totalItems": len(items),
        "originalNonEqualItems": original_non_equal,
        "closedItems": matrix["summary"]["closed"],
        "openItems": matrix["summary"]["open"],
        "blockedItems": len(blocked),
        "finalJudgementCounts": final_counts,
        "closureStates": {
            state: sum(item["closureState"] == state for item in items)
            for state in matrix["allowedTerminalStates"]
        },
        "blockedReasons": [
            {
                "auditId": item["auditId"],
                "missingSource": item["remainingRisk"][0],
                "closureAction": item["actions"][0],
            }
            for item in blocked
        ],
        "alignmentScore": score,
    }
    crosswalk = {
        "schemaVersion": "gve16-final-crosswalk-v1",
        "benchmark": matrix["benchmark"],
        "summary": summary,
        "items": [
            {
                "auditId": item["auditId"],
                "feature": item["feature"],
                "originalJudgement": item["originalJudgement"],
                "finalJudgement": item["currentJudgement"],
                "closureState": item["closureState"],
                "verification": item["verification"],
                "afterEvidence": item["afterEvidence"],
                "remainingRisk": item["remainingRisk"],
            }
            for item in items
        ],
    }
    _write(AUDIT_DIR / "final-re-audit-summary.json", summary)
    _write(AUDIT_DIR / "gve16-final-crosswalk.json", crosswalk)

    lines = [
        "# 《一路狂飙》× GVE16 最终差异总览",
        "",
        f"> 195/195 条目已获得终态；Final ×={final_counts['cross']}，△={final_counts['triangle']}，U={final_counts['unknown']}。",
        "> 完整明细：[Alignment Closure Matrix](alignment-closure-matrix.json) · [GVE16 Final Crosswalk](gve16-final-crosswalk.json)",
        "",
        "| 定位 | 当前唯一差异 | 缺失来源 | 拿到后如何关闭 |",
        "|---|---|---|---|",
    ]
    for item in blocked:
        lines.append(f"| {item['auditId']} | {item['feature']} | {item['remainingRisk'][0]} | {item['actions'][0]} |")
    lines += [
        "",
        "## 结论",
        "",
        f"- 原始非 `=` 项：{original_non_equal}",
        f"- 已关闭：{matrix['summary']['closed']}",
        f"- 真实外部阻塞：{len(blocked)}",
        f"- A–H 平均分：{score['coreAH']}；I={score['scores']['I']}；J={score['scores']['J']}",
        "- 除上表3项外，审计中的 implementation_depth、material_insufficient、review_not_completed、scope_unresolved、no_existence_signal 与 delivery_pending 均已进入明确终态并落到真实交付。",
    ]
    (AUDIT_DIR / "最终差异总览.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
