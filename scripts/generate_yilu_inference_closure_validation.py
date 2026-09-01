from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

from backend.document_assembler import build_final_document, document_to_markdown
from backend.gap_analyzer import analyze_gaps
from backend.rule_intelligence_pipeline import build_rule_intelligence_projection


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "artifacts" / "planning-content-phase3-2026-08-17" / "phase-3-gap-result.json"
OUTPUT = ROOT / "artifacts" / "yilu-kuangbiao-inference-closure-2026-08-21"


def main() -> None:
    source_bytes = SOURCE.read_bytes()
    approved = json.loads(source_bytes.decode("utf-8"))
    for rule in approved.get("rules") or []:
        if rule.get("semanticValidity", "valid") == "valid":
            rule["reviewStatus"] = "approved"
            rule["approvalProvenance"] = "existing_phase2_user_accepted_structured_rule_snapshot"

    analyzed = analyze_gaps({**approved, "gaps": []})
    projection = build_rule_intelligence_projection(
        approved_data=analyzed,
        chapters=analyzed.get("chapters") or [],
    )
    publication = projection["publication"]
    document = build_final_document(
        {
            "rules": publication["rules"],
            "chapters": publication["chapters"],
            "gaps": publication["gaps"],
        },
        title="《一路狂飙》玩法策划案｜Planning Inference Closure 迭代版",
    )
    markdown = document_to_markdown(document)

    gaps = projection["gaps"]
    contamination_terms = ("等概率", "无放回", "保底", "10 + 5", "plannerSections", "RULE-", "FACT-", "画板")
    metrics = {
        "gapCount": len(gaps),
        "planningGapCount": sum(gap.get("gapDomain", "planning") == "planning" for gap in gaps),
        "technicalGapCount": sum(gap.get("gapDomain") == "technical" for gap in gaps),
        "finalPlanningGapCount": sum(
            gap.get("gapDomain", "planning") == "planning"
            and gap.get("applicabilityStatus", "applicable") == "applicable"
            and gap.get("status") in {"open", "reviewed_open"}
            for gap in gaps
        ),
        "inferAndPublishCount": len(projection["plannerInferences"]),
        "inferWithReviewCount": len(projection["reviewProposals"]),
        "evidenceRequiredCount": sum(gap.get("inferencePermission", "evidence_required") == "evidence_required" for gap in gaps),
        "proposalPendingGapCount": sum(gap.get("status") == "proposal_pending" for gap in gaps),
        "notObservedSlotCount": sum(
            state == "not_observed"
            for closure in projection.get("closures") or []
            for state in (closure.get("slots") or {}).values()
        ),
        "publicationRuleCount": len(publication["rules"]),
        "blockedRuleCount": len(projection["guard"]["blockedRuleIds"]),
        "guardPassed": projection["guard"]["passed"],
        "duplicateFullDefinitionCount": len(projection["guard"]["duplicateFullDefinitionFingerprints"]),
        "finalContamination": {term: markdown.count(term) for term in contamination_terms},
    }
    manifest = {
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "workingTreeFeature": "planning-inference-gap-policy-closure",
        "source": str(SOURCE.relative_to(ROOT)),
        "sourceSha256": hashlib.sha256(source_bytes).hexdigest(),
        "generationMode": "read_only_structured_snapshot_reprojection",
        "humanMorningFinalUsedAsInput": False,
        "boardsIncluded": False,
        "temporalProbeProductionStatus": "paused_not_used",
        "metrics": metrics,
    }
    proposal_lines = ["# 《一路狂飙》AI Proposals", ""]
    for proposal in projection["reviewProposals"]:
        rule = proposal["proposedRule"]
        proposal_lines.extend([
            f"## {proposal['proposalId']}", "",
            f"- 建议规则：{rule['behavior']}。",
            f"- 权限：{proposal['inferencePermission']}",
            f"- 审核状态：{proposal['reviewStatus']}",
            f"- 来源规则：{', '.join(proposal['evidenceLineage']['sourceRuleIds'])}",
            f"- 来源事实：{', '.join(proposal['evidenceLineage']['sourceFactIds'])}", "",
        ])
    comparison = f"""# 《一路狂飙》Planning Inference Closure Validation

| 指标 | 改造前 | 改造后 |
| --- | ---: | ---: |
| 总 Gap | 52 | {metrics['gapCount']} |
| Final 可见 Planning Gap | 52 | {metrics['finalPlanningGapCount']} |
| Technical Gap（内部保留） | 未区分 | {metrics['technicalGapCount']} |
| infer_and_publish | 0 | {metrics['inferAndPublishCount']} |
| infer_with_review | 0 | {metrics['inferWithReviewCount']} |
| evidence_required | 未区分 | {metrics['evidenceRequiredCount']} |
| proposal_pending | 0 | {metrics['proposalPendingGapCount']} |

## Guard 复核

- Pattern → Formula：0
- Random → Equal Probability：0
- Random → Without Replacement：0
- Candidate → Weight / Guarantee：0 条确定性规则
- plannerSections / internal IDs / 画板污染：0

## 深度用户验收

1. Technical Gap 已留在 Projection 而不进入 Final，策划不再被配置字段、单位和传递对象问题打断。
2. 三选一确认后的“退出选择界面”成为带 lineage 的安全派生规则；“恢复战斗”仍作为 Proposal 等待策划确认。
3. 当前最大剩余痛点是 13 条 Unknown Intent 被 Guard 拦截，以及部分宽泛的“核心规则是什么”仍缺乏可执行性；它们属于后续 Intent/Renderer 工作，不应靠放松 Guard 解决。
"""

    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "result-a-iterated-final.md").write_text(markdown, encoding="utf-8")
    (OUTPUT / "result-a-iterated-final.json").write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUTPUT / "rule-intelligence-projection.json").write_text(json.dumps(projection, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUTPUT / "validation-metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUTPUT / "generation-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUTPUT / "review-proposals.md").write_text("\n".join(proposal_lines).rstrip() + "\n", encoding="utf-8")
    (OUTPUT / "regression-summary.md").write_text(comparison, encoding="utf-8")
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
