import json

from scripts.generate_final_alignment_reaudit import AUDIT_DIR, main


def test_final_reaudit_closes_the_full_union_and_keeps_only_real_external_blocks():
    main()

    summary = json.loads((AUDIT_DIR / "final-re-audit-summary.json").read_text(encoding="utf-8"))
    crosswalk = json.loads((AUDIT_DIR / "gve16-final-crosswalk.json").read_text(encoding="utf-8"))
    overview = (AUDIT_DIR / "最终差异总览.md").read_text(encoding="utf-8")

    assert summary["totalItems"] == 195
    assert summary["originalNonEqualItems"] == 109
    assert summary["closedItems"] == 195
    assert summary["openItems"] == 0
    assert summary["blockedItems"] == 3
    assert summary["finalJudgementCounts"] == {
        "equals": 186,
        "cross": 0,
        "triangle": 3,
        "unknown": 0,
    }
    assert len(crosswalk["items"]) == 195
    assert {item["auditId"] for item in summary["blockedReasons"]} == {"W-18", "L-13", "P6-06"}
    assert all(audit_id in overview for audit_id in ("W-18", "L-13", "P6-06"))
