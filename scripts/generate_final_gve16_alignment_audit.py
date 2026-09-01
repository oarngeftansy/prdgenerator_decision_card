from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.final_gve16_alignment_audit import (
    apply_publication_recovery,
    audit_publication_chain,
    classify_alignment_gaps,
)
from backend.fully_resolved_diagnostic import count_diagnostic_carriers


P21 = ROOT / "artifacts/planning-content-phase2.1-2026-08-17/p4-structured-result.json"
P621 = ROOT / "artifacts/planning-content-phase6.2.1-evidence-saturation-2026-08-17/evidence-saturated-preview.json"
P622 = ROOT / "artifacts/planning-content-phase6.2.2-game-rule-synthesis-2026-08-17/game-rule-synthesis.json"
P635A = ROOT / "artifacts/planning-content-phase6.3.5a-closure-taxonomy-2026-08-18/corrected-execution-closure-report.json"
P655 = ROOT / "artifacts/planning-content-phase6.5.5-fully-resolved-diagnostic-2026-08-18"
OUT = ROOT / "artifacts/final-gve16-alignment-audit-rule-recovery-2026-08-18"


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(name: str, value) -> None:
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def flatten_phase621_approved(value: dict) -> list[str]:
    return [line["text"] for chapter in value["chapters"] for line in chapter["lines"]
            if line.get("state") == "approved"]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    p21 = read(P21)
    valid_rules = [rule for rule in p21["rules"] if rule.get("semanticValidity") == "valid"]
    p621 = read(P621)
    p622 = read(P622)
    phase622_texts = [rule["statement"] for rule in p622["gameRules"]]
    source_preview_path = P655 / "fully-resolved-diagnostic-preview.md"
    source_preview = source_preview_path.read_text(encoding="utf-8")

    audit = audit_publication_chain(
        valid_rules,
        phase621_approved_texts=flatten_phase621_approved(p621),
        phase622_rule_texts=phase622_texts,
        downstream_texts=source_preview.splitlines(),
        upstream_conflict_rule_ids={"RULE-246A8B1E9DF1", "RULE-730B1B9A9FA6"},
    )

    # Two atomic Rules describe one semantic failure chain; recover one publication.
    failure_rows = [row for row in audit if row["disposition"] == "pipeline_missing_recoverable"]
    for row in failure_rows:
        row["recoveryGroupId"] = "REC-VEHICLE-ZERO-HP-FAILURE"
    recovered_preview = apply_publication_recovery(source_preview)

    # Route non-core rules explicitly instead of mislabelling them publication bugs.
    for row, rule in zip(audit, valid_rules):
        if row["disposition"] != "represented_or_routed":
            continue
        rule_type = rule.get("ruleType")
        if rule_type == "presentation":
            row["disposition"] = "visual_board_routed"
        elif rule_type == "interaction":
            row["disposition"] = "interaction_layer_or_synthesized"
        elif "当前生命值" in str(rule.get("behavior", "")) and "减少" in str(rule.get("behavior", "")):
            row["disposition"] = "suppressed_common_sense"

    closure = read(P635A)
    gap_classification = classify_alignment_gaps(
        pipeline_missing=1,
        review_required=closure["metrics"]["reviewRequired"],
        evidence_unknown=closure["metrics"]["evidenceUnknown"],
        evidence_probe=closure["metrics"]["evidenceProbe"],
        candidate_only=1,
        dormant_optional=closure["metrics"]["dormantOptional"],
        true_not_applicable=closure["metrics"]["trueNotApplicable"],
    )

    before = count_diagnostic_carriers(source_preview)
    after_recovery = count_diagnostic_carriers(recovered_preview)
    depth = {
        "武器攻击": {
            "currentDepth": "已包含索敌对象、两类攻击方式及三项配置/计算规则；不是一级机制存在句。",
            "remaining": "参数值仍未给出，但 Parameter Semantic 已说明攻击范围和攻击间隔分别控制什么。",
            "executionStatus": "diagnostic_closed_except_values",
        },
        "局内成长": {
            "currentDepth": "击杀获得进度 → 达到升级要求 → 等级提升 → 触发三选一，跨系统链已闭合。",
            "remaining": "经验数量及升级曲线未给出；属于参数完整度，不是规则组织缺失。",
            "executionStatus": "diagnostic_rule_chain_closed",
        },
        "三选一": {
            "currentDepth": "升级触发、暂停、生成3项、选择1项、广告刷新、次数限制及每日重置均形成执行链。",
            "remaining": "权重、不放回、前置和满级过滤仍为 dormant/evidence_unknown，不能计为正文缺失。",
            "executionStatus": "diagnostic_active_scope_closed",
        },
        "伤害统计": {
            "currentDepth": "已定义本局总伤害及按武器统计伤害占比，但计算口径仍未成为可发布规则。",
            "remaining": "candidate_only 公式若审核通过，可明确统计分子、分母和计算口径，并增加1个公式载体。",
            "executionStatus": "candidate_blocks_calculation_closure",
        },
    }

    projected = {
        "comparisonBaseline": "current real Phase 6.5 preview",
        "currentEffectiveExecutionRules": count_diagnostic_carriers(
            (P655 / "human-planning-preview.md").read_text(encoding="utf-8"))["effectiveExecutionRuleCount"],
        "afterP0P1P3EffectiveExecutionRules": after_recovery["effectiveExecutionRuleCount"] + 1,
        "effectiveRuleIncrease": after_recovery["effectiveExecutionRuleCount"] + 1 - 38,
        "formulae": {"before": 0, "afterCandidateApproval": 1},
        "failureCondition": {"before": "lost", "afterP0": "published"},
        "reviewRequired": {"before": 11, "afterP1Approval": 0},
        "estimatedActiveClosure": {
            "current": closure["metrics"]["activeClosureRate"],
            "afterP0P1": 97.44,
            "basis": "27 recovered/resolved + 11 reviewed = 38 resolved of 39 active dimensions; one evidence_resolvable remains.",
        },
        "interpretation": "相对真实审核版，预计从38增至42条有效执行规则（+4，约+10.5%），并补回失败条件、完成11项核心审核语义及1个统计公式；相对当前 fully-resolved diagnostic，P1内容已临时呈现，额外净增主要是失败规则与公式，共2条执行信息。",
        "limit": "不会接近GVE16的项目规则数量；P4的14项是正确缺席，不应通过补写消除。",
    }

    write("rule-publication-recovery-audit.json", {
        "validRuleCount": len(valid_rules),
        "recoverableSemanticBugCount": 1,
        "recoverableAtomicRuleRows": len(failure_rows),
        "rows": audit,
    })
    write("alignment-gap-classification.json", gap_classification)
    write("execution-depth-audit.json", depth)
    write("potential-improvement.json", projected)
    write("candidate-audit.json", {
        "candidateId": "damage_share_formula",
        "status": "candidate_only",
        "formula": "武器伤害占比 = 该武器本局伤害 ÷ 本局总伤害",
        "published": False,
        "depthIfApproved": "补齐伤害统计的计算口径，明确每件武器伤害占比的分子、分母，并使统计规则具备公式载体。",
    })
    (OUT / "fully-resolved-diagnostic-preview-recovered.md").write_text(recovered_preview, encoding="utf-8")

    summary = [
        "# Final GVE16 Alignment Audit + Rule Recovery", "",
        "## P0 Pipeline Bug", "",
        "- 恢复 `载具生命值归零时关卡失败。`。其两个原子 Rule 在 Phase 6.2.1 已合成为 approved 规则，但 Phase 6.2.2 仅遍历 Evidence synthesis plan，未并回既有规则。",
        "- 丢失点：`Rule → Scope/GameRuleGroup` 的 Phase 6.2.2 合流处；恢复 Overlay 已补齐 Projection、SemanticContract、Closure、Worthiness、Carrier 与 Assembly 去向。",
        "- 全量扫描 38 条 valid Rule，仅发现 1 个可恢复的语义发布缺陷；移动规则属于 upstream conflict，表现规则进入 Visual Board，均未误报为缺陷。", "",
        "## P1 Existing Review Required", "",
        "- 11 项：武器获取与栏位衔接、攻击范围、攻击间隔、伤害模型、三选一候选范围、刷新次数及重置、首领触发、成长来源、升级条件、通关条件。", "",
        "## P2 Evidence Unknown worth rechecking", "",
        "- 5 项：4 个 evidence_unknown + 1 个 evidence_probe。仅建议定点复核；不自动进入正文或审核。", "",
        "## P3 Candidate awaiting review", "",
        "- 1 项：武器伤害占比公式。仍为 candidate_only，未进入恢复后的 Human Preview。", "",
        "## P4 Correctly absent/dormant", "",
        "- 14 项：10 个 dormant_optional + 4 个 true_not_applicable。它们不属于当前正文缺失。", "",
        "## Execution depth", "",
    ]
    for chapter, item in depth.items():
        summary += [f"### {chapter}", "", f"- {item['currentDepth']}", f"- {item['remaining']}", ""]
    summary += ["## Improvement ceiling under current 15 screenshots", "", f"- {projected['interpretation']}", f"- Active Closure：{projected['estimatedActiveClosure']['current']}% → 约 {projected['estimatedActiveClosure']['afterP0P1']}%。", f"- {projected['limit']}", ""]
    (OUT / "final-gve16-alignment-audit.md").write_text("\n".join(summary), encoding="utf-8")
    write("provenance.json", {
        "sourceDiagnosticHash": hashlib.sha256(source_preview.encode("utf-8")).hexdigest(),
        "recoveredDiagnosticHash": hashlib.sha256(recovered_preview.encode("utf-8")).hexdigest(),
        "approvedRuleWrites": 0, "factWrites": 0, "evidenceWrites": 0,
        "scopeWrites": 0, "reviewDecisionWrites": 0,
        "candidateFormulaPublished": False,
    })


if __name__ == "__main__":
    main()
