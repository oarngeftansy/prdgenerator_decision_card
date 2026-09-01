from __future__ import annotations

from typing import Any, Iterable


_FAILURE_MARKERS = ("生命值归零", "触发失败")


def audit_publication_chain(
    rules: list[dict[str, Any]],
    *,
    phase621_approved_texts: Iterable[str],
    phase622_rule_texts: Iterable[str],
    downstream_texts: Iterable[str],
    upstream_conflict_rule_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Audit valid upstream rules without treating conflicts as publication bugs."""
    approved = "\n".join(phase621_approved_texts)
    synthesized = "\n".join(phase622_rule_texts)
    downstream = "\n".join(downstream_texts)
    conflicts = upstream_conflict_rule_ids or set()
    rows: list[dict[str, Any]] = []
    for rule in rules:
        rule_id = str(rule.get("ruleId", ""))
        behavior = str(rule.get("behavior", rule.get("text", "")))
        if rule_id in conflicts:
            rows.append({"ruleId": rule_id, "behavior": behavior,
                         "disposition": "upstream_conflict", "lossStage": None})
            continue
        is_failure = any(marker in behavior for marker in _FAILURE_MARKERS)
        phase621_has_failure = "生命值归零时关卡失败" in approved
        later_has_failure = "生命值归零时关卡失败" in synthesized or "生命值归零时关卡失败" in downstream
        if is_failure and phase621_has_failure and not later_has_failure:
            rows.append({
                "ruleId": rule_id,
                "behavior": behavior,
                "disposition": "pipeline_missing_recoverable",
                "lossStage": "Phase 6.2.2 Evidence → Game Rule Synthesis",
                "recovery": {
                    "semanticKey": "vehicle_zero_hp_failure",
                    "publishedText": "载具生命值归零时关卡失败。",
                    "scope": "failure confirmed",
                    "gameRuleGroup": "关卡 / 胜负",
                    "primaryOwner": "胜负判定",
                    "semanticContractDimension": "failure_condition",
                    "closureStatus": "resolved",
                    "publishWorthiness": "publish_basic_but_meaningful",
                    "carrier": "rule_bullets",
                    "assemblyPlacement": "关卡 / 胜负",
                },
            })
        else:
            rows.append({"ruleId": rule_id, "behavior": behavior,
                         "disposition": "represented_or_routed", "lossStage": None})
    return rows


def apply_publication_recovery(markdown: str) -> str:
    """Apply a publication-only overlay; no upstream state is mutated."""
    result = markdown.replace(
        "- 每种武器独立配置攻击范围。",
        "- 攻击范围：每种武器独立配置，用于限制该武器可攻击的目标范围。",
    ).replace(
        "- 每种武器独立配置攻击间隔。",
        "- 攻击间隔：每种武器独立配置，用于控制同一武器连续两次攻击之间的时间。",
    )
    failure = "- 载具生命值归零时关卡失败。"
    if failure not in result:
        success = "- 击败首领后本关挑战成功，并进入结算。"
        if success in result:
            result = result.replace(success, f"{failure}\n{success}")
        else:
            result = result.rstrip() + f"\n\n## 关卡\n\n### 胜负\n\n{failure}\n"
    return result


def classify_alignment_gaps(**counts: int) -> dict[str, Any]:
    tiers = {
        "P0": {"label": "Pipeline Bug", "count": counts["pipeline_missing"], "countsAsMissing": True},
        "P1": {"label": "Existing Review Required", "count": counts["review_required"], "countsAsMissing": True},
        "P2": {"label": "Evidence Unknown worth rechecking",
               "count": counts["evidence_unknown"] + counts["evidence_probe"], "countsAsMissing": True},
        "P3": {"label": "Candidate awaiting review", "count": counts["candidate_only"], "countsAsMissing": True},
        "P4": {"label": "Correctly absent/dormant",
               "count": counts["dormant_optional"] + counts["true_not_applicable"], "countsAsMissing": False},
    }
    return {
        "sourceCounts": counts,
        "tiers": tiers,
        "currentDocumentGapCount": sum(item["count"] for item in tiers.values() if item["countsAsMissing"]),
        "correctlyAbsentCount": tiers["P4"]["count"],
    }
