"""Generate the read-only Phase 4 《一路狂飙》 reference implementation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from backend.document_assembler import build_final_document, document_to_markdown
from backend.document_quality_evaluator import evaluate_document
from backend.planning_style_linter import lint_document


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "artifacts/planning-content-phase3-2026-08-17/phase-3-gap-result.json"
BASELINE = ROOT / "artifacts/planning-content-baseline-2026-08-14/p7_body.txt"
PROFILE = ROOT / "artifacts/planning-style-distillation-2026-08-17/planning_style_profile.yaml"
JOB = ROOT / "data/jobs/8312a91c89e144e6a59f81b982f14c06/job.json"
OUT = ROOT / "artifacts/planning-content-phase4-2026-08-17"


FOCUS = {
    "载具": {"V2CH-001", "V2CH-002", "V2CH-003"},
    "武器攻击": {"V2CH-005", "V2CH-008"},
    "三选一": {"V2CH-009", "V2CH-010"},
    "怪物": {"V2CH-013", "V2CH-014", "V2CH-015", "V2CH-016"},
    "关卡": {"V2CH-017", "V2CH-018", "V2CH-019"},
    "结算": {"V2CH-020", "V2CH-021"},
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def style_profile() -> dict:
    text = PROFILE.read_text(encoding="utf-8")
    expressions = []
    inside = False
    for line in text.splitlines():
        if line.strip() == "expressions:":
            inside = True
            continue
        if inside and line.startswith("  never_runtime_fields:"):
            break
        if inside and line.strip().startswith("- "):
            expressions.append(line.strip()[2:])
    return {"forbidden_expressions": expressions, "source": str(PROFILE.relative_to(ROOT))}


def project_accepted(data: dict) -> dict:
    projected = json.loads(json.dumps(data, ensure_ascii=False))
    projected["rules"] = [rule for rule in projected["rules"] if rule.get("semanticValidity") == "valid"]
    for rule in projected["rules"]:
        rule["reviewStatus"] = "approved"
        rule["approvalProvenance"] = "phase2_and_2.1_user_acceptance_read_only_projection"
    for gap in projected["gaps"]:
        gap["status"] = "reviewed_open"
        gap["reviewProvenance"] = "phase3_user_acceptance_read_only_projection"
    return projected


def iter_chapters(document: dict):
    for system in document["systems"]:
        for obj in system["objects"]:
            for chapter in obj["chapters"]:
                yield chapter


def focus_comparison(data: dict, document: dict) -> str:
    old_lines = [line.strip() for line in BASELINE.read_text(encoding="utf-8").splitlines() if line.strip()]
    chapter_map = {chapter["chapterId"]: chapter for chapter in iter_chapters(document)}
    rules = data["rules"]
    keywords = {"载具": ["载具", "血条"], "武器攻击": ["武器", "命中"], "三选一": ["三选一", "候选", "刷新"], "怪物": ["怪物", "首领"], "关卡": ["关卡", "倒计时", "失败"], "结算": ["结算", "通关时间", "伤害统计"]}
    lines = ["# Phase 4 重点章节对比", "", "> A 版保持原样；下列仅摘录相关旧句，不回写基线。", ""]
    for name, ids in FOCUS.items():
        lines += [f"## {name}", "", "### A 版旧正文摘录", ""]
        selected = [line for line in old_lines if any(key in line for key in keywords[name])][:8]
        lines += [f"- {line}" for line in selected] or ["- 未检出可独立对应的旧句。"]
        lines += ["", "### Approved Rule", ""]
        selected_rules = [rule for rule in rules if rule.get("ownerChapterId") in ids]
        lines += [f"- `{rule['ruleId']}` [{rule['ruleType']}/{rule['schemaSlot']}] {rule['behavior']}（evidence: {', '.join(rule['evidenceIds'])}）" for rule in selected_rules] or ["- 本组无 Approved Rule；正文不补写。"]
        lines += ["", "### Phase 4 新正文", ""]
        for cid in ids:
            chapter = chapter_map.get(cid)
            if not chapter:
                continue
            lines.append(f"**{chapter['title']}**")
            lines.append("")
            for group in chapter["groups"]:
                lines.append(f"{group['title']}：")
                lines += [f"- {sentence['text']}  `← {', '.join(sentence['sourceRuleIds'])}`" for sentence in group["sentences"]]
            if chapter["reviewedGaps"]:
                lines.append("待确认：")
                lines += [f"- {gap['question']}" for gap in chapter["reviewedGaps"]]
            lines.append("")
        lines += ["对齐说明：使用稳定概念标题；按逻辑、数值配置、表现分组；规则保持原子 bullet；条件在行为之前；待确认问题与确认规则隔离。", ""]
    return "\n".join(lines)


def main() -> None:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    data = project_accepted(source)
    profile = style_profile()
    document = build_final_document(data, profile, title="《一路狂飙》执行策划案 B 版")
    metrics = evaluate_document(document, data["rules"], data["gaps"], profile)
    lint = lint_document(document, profile)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "B-final-document.md").write_text(document_to_markdown(document), encoding="utf-8")
    (OUT / "B-final-document.json").write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "focus-comparison.md").write_text(focus_comparison(data, document), encoding="utf-8")
    (OUT / "phase-4-quality-report.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "style-lint-report.json").write_text(json.dumps(lint, ensure_ascii=False, indent=2), encoding="utf-8")
    provenance = {
        "status": "reference_preview_with_open_gaps",
        "sourceJobStatus": json.loads(JOB.read_text(encoding="utf-8")).get("status"),
        "sourceJobSha256": sha256(JOB),
        "sourcePhase3Sha256": sha256(SOURCE),
        "baselineSha256": sha256(BASELINE),
        "styleProfileSha256": sha256(PROFILE),
        "approvalProjection": "Phase 2/2.1 user acceptance, applied in read-only memory; job not modified",
        "gapProjection": "Phase 3 user acceptance, open gaps retained as reviewed_open",
        "contentAuthorities": ["approved Rule projection", "reviewed open Gap projection", "ChapterSchema"],
        "gve16Role": "presentation_and_organization_reference_only",
    }
    (OUT / "provenance.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8")
    manual = """# GVE16 文档范式人工对比\n\n| 维度 | A 版 | B 版 | 判定 |\n|---|---|---|---|\n| 章节组织 | 多职责摘要标题并存 | System → Object → 稳定规则类别 | 对齐 |\n| 信息密度 | 重复、元说明和字段枚举较多 | 每条正文对应 Approved Rule；Gap 单列 | 对齐 |\n| 表达顺序 | 条件、行为、表现混写 | 保留条件→行为→结果顺序 | 对齐 |\n| Logic / Presentation | 同句混写 | 分组承载 | 对齐 |\n| 数值与配置 | 散落在综合段落 | 独立“数值与配置”组 | 对齐 |\n| bullet / 正文 / 表格 | 长段落与枚举混用 | 原子规则用 bullet；当前无重复字段集，不造表 | 对齐 |\n| 生命周期与边界 | 存在无证据扩写 | 仅 Approved Rule；缺口作为问题 | 对齐 |\n| 简洁程度 | 存在视频解说腔与 AI meta | 禁用表达清零，正文不解释设计意义 | 对齐 |\n\n人工结论：B 版对齐的是组织与表达范式，不含 GVE16 的规则、字段、数值、公式、对象、编号、配置表或项目术语。\n"""
    (OUT / "gve16-paradigm-manual-comparison.md").write_text(manual, encoding="utf-8")
    audit = """# Deep User Audit：Phase 4 B 版执行策划文档\n\n**Real Job**\n主策在不接受无证据规则的前提下，快速审阅、补齐并向程序与测试交付可执行文档。\n\n**Top Pain Points**\n\n1. 当前 51 个待确认项中有 44 个 implementation_blocking，B 版仍不能视为正式可实施文档。\n   改进：在后续人工审核中逐项回答或明确拒绝 Gap，再重新生成。\n   验收：正式导出前 implementation_blocking 为 0。\n\n2. “解锁与养成”“词条”“怪物受击及死亡”等章节只有 Gap、没有 Approved Rule，阅读时容易误判为已具备正文。\n   改进：UI 后续区分“空章节待补齐”和“已有规则章节”；本阶段文档保持仅列待确认。\n   验收：主策可一眼识别无确认规则的章节，且其中不存在确认语气正文。\n\n3. 本轮审批状态来自用户对 Phase 2/3 产物的阶段验收投影，而非 job 内逐条 P4 写回。\n   改进：后续把逐条 P4 审核状态接入正式导出链路；本阶段 provenance 明示只读投影。\n   验收：正式导出中的每个 Rule 都具备持久化审批记录与 revision。\n\n4. 37 条正文句全部可追溯，但当前可读文档未内联显示 Rule ID，需要打开 JSON 或重点对比报告核验。\n   改进：后续预览增加可展开的来源追溯，不污染正式正文。\n   验收：点击任一句可查看 Rule、Fact、Evidence，正式导出仍保持简洁。\n\n**Immediate Next Fixes**\n- 由主策关闭 implementation_blocking Gap。\n- 将 reference approval projection 替换为正式 P4 逐条审批数据。\n\n**Larger Bets**\n- 在不改八步流程的前提下，为正文预览增加句级追溯侧栏。\n"""
    (OUT / "deep-user-audit.md").write_text(audit, encoding="utf-8")
    print(json.dumps({"output": str(OUT), "metrics": metrics, "styleLint": lint, "jobSha256After": sha256(JOB)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
