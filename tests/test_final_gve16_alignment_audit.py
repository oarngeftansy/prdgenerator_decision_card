from backend.final_gve16_alignment_audit import (
    apply_publication_recovery,
    audit_publication_chain,
    classify_alignment_gaps,
)


def test_existing_failure_rule_is_recovered_but_upstream_conflict_is_not():
    rules = [
        {"ruleId": "R-FAIL", "semanticValidity": "valid", "ruleType": "flow",
         "behavior": "载具当前生命值归零后触发失败事件"},
        {"ruleId": "R-MOVE", "semanticValidity": "valid", "ruleType": "logic",
         "behavior": "载具沿预设路线自动行进"},
    ]
    audit = audit_publication_chain(
        rules,
        phase621_approved_texts=["载具生命值归零时关卡失败。"],
        phase622_rule_texts=[],
        downstream_texts=[],
        upstream_conflict_rule_ids={"R-MOVE"},
    )

    assert audit[0]["disposition"] == "pipeline_missing_recoverable"
    assert audit[0]["lossStage"] == "Phase 6.2.2 Evidence → Game Rule Synthesis"
    assert audit[0]["recovery"]["closureStatus"] == "resolved"
    assert audit[1]["disposition"] == "upstream_conflict"


def test_recovery_restores_rule_and_completes_parameter_semantics_without_values():
    preview = """# Preview

## 武器

### 攻击

- 每种武器独立配置攻击范围。
- 每种武器独立配置攻击间隔。

## 关卡

### 胜负

- 击败首领后本关挑战成功，并进入结算。
"""
    recovered = apply_publication_recovery(preview)

    assert "载具生命值归零时关卡失败。" in recovered
    assert "攻击范围：每种武器独立配置，用于限制该武器可攻击的目标范围。" in recovered
    assert "攻击间隔：每种武器独立配置，用于控制同一武器连续两次攻击之间的时间。" in recovered
    assert "5m" not in recovered and "300px" not in recovered
    assert "武器伤害占比 =" not in recovered


def test_gap_classification_excludes_dormant_and_not_applicable_from_missing():
    result = classify_alignment_gaps(
        pipeline_missing=1,
        review_required=11,
        evidence_unknown=4,
        evidence_probe=1,
        candidate_only=1,
        dormant_optional=10,
        true_not_applicable=4,
    )

    assert result["currentDocumentGapCount"] == 18
    assert result["correctlyAbsentCount"] == 14
    assert result["tiers"]["P4"]["count"] == 14
    assert result["tiers"]["P4"]["countsAsMissing"] is False
