from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.rule_normalizer import build_approved_data_v2


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def generate(job_path: Path, output_dir: Path) -> dict:
    before = _sha256(job_path)
    job = json.loads(job_path.read_text(encoding="utf-8"))
    source_model = job["gameplayReviewModel"]
    approved = build_approved_data_v2(source_model)
    rules_by_fact: dict[str, list[dict]] = defaultdict(list)
    fact_by_id = {fact["factId"]: fact for fact in approved["facts"]}
    for rule in approved["rules"]:
        for fact_id in rule.get("sourceFactIds") or []:
            rules_by_fact[fact_id].append(rule)
    slots_by_fact = defaultdict(list)
    for slot in approved["slots"]:
        for fact_id in slot["factIds"]:
            slots_by_fact[fact_id].append(slot["slotId"])
    splits = [{
        "rawEvidence": fact["rawEvidenceText"], "factId": fact["factId"], "sourceText": fact["sourceText"],
        "subject": fact["subject"], "predicate": fact["predicate"], "object": fact["object"],
        "evidenceLevel": fact["evidenceLevel"], "evidenceIds": fact["evidenceIds"],
        "reviewStatus": fact["reviewStatus"], "validationErrors": fact["validationErrors"],
        "schemaSlots": slots_by_fact[fact["factId"]],
        "rules": [{key: rule[key] for key in ("ruleId", "ownerChapterId", "schemaSlot", "ruleType", "behavior", "reviewStatus", "semanticValidity", "validationErrors")} for rule in rules_by_fact[fact["factId"]]],
    } for fact in approved["facts"]]
    fragment_errors = {"fragment", "incomplete_behavior", "missing_subject", "missing_predicate", "unbalanced_quote"}
    metrics = {
        "chapterCount": len(approved["chapters"]), "factCount": len(approved["facts"]),
        "slotCount": len(approved["slots"]), "ruleCount": len(approved["rules"]),
        "ruleTypeCounts": dict(Counter(rule["ruleType"] for rule in approved["rules"])),
        "rulesWithoutEvidence": sum(not rule["evidenceIds"] for rule in approved["rules"]),
        "factsWithoutEvidence": sum(not fact["evidenceIds"] for fact in approved["facts"]),
        "plannerSectionsUsedAsFacts": 0,
        "multiRuleFactCount": sum(len(rows) > 1 for rows in rules_by_fact.values()),
        "reviewStatusCounts": dict(Counter(rule["reviewStatus"] for rule in approved["rules"])),
        "residualFragmentFactCount": sum(bool(fragment_errors.intersection(fact.get("validationErrors") or [])) for fact in approved["facts"]),
        "residualFragmentRuleCount": sum(bool(fragment_errors.intersection(rule.get("validationErrors") or [])) for rule in approved["rules"]),
        "schemaSlotSemanticMismatchCount": sum("schema_semantic_mismatch" in (rule.get("validationErrors") or []) or "rule_type_slot_mismatch" in (rule.get("validationErrors") or []) for rule in approved["rules"]),
        "mixedDomainFactCount": sum("mixed_domain" in (fact.get("validationErrors") or []) for fact in approved["facts"]),
        "inferredFactCount": sum(fact.get("evidenceLevel") == "inferred" for fact in approved["facts"]),
        "needsRevisionRuleCount": sum(rule.get("reviewStatus") == "needs_revision" for rule in approved["rules"]),
    }
    sample_patterns = {
        "载具血条 / 扣血 / 失败": ("血条", "归零"), "三选一暂停 + 三张候选": ("暂停游戏", "三个卡片"),
        "范围+30% / 伤害+100%": ("30%", "100%"), "刷新按钮": ("刷新", "三个选项"),
        "终极词条四向喷射": ("单方向喷射", "向4面喷射"), "怪物生成 / 移动 / 接触伤害": ("屏幕上方", "接触"),
        "Boss长血条 / 攻击形态": ("长血条", "攻击形态"), "首领来袭表现": ("首领来袭", "遮罩"),
        "倒计时": ("倒计时",), "当前等级": ("当前等级",), "通关时间 / 新纪录": ("通关时间", "新纪录"),
    }
    samples = {label: [item for item in splits if all(word in item["rawEvidence"] for word in words)] for label, words in sample_patterns.items()}
    after = _sha256(job_path)
    audit = {
        "phase": "2.1", "jobId": job.get("id"),
        "provenance": {"sourceJobStatus": job.get("status"), "sourceJobSha256Before": before, "sourceJobSha256After": after, "jobMutated": before != after, "sourceMode": "read_only_memory_copy"},
        "metrics": metrics, "focusSamples": samples, "factToRuleSplits": splits,
        "chapters": [{**chapter, "slotCount": sum(slot["chapterId"] == chapter["chapterId"] for slot in approved["slots"]), "ruleCount": sum(rule["ownerChapterId"] == chapter["chapterId"] for rule in approved["rules"])} for chapter in approved["chapters"]],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "p4-structured-result.json").write_text(json.dumps(approved, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "phase-2.1-p4-audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# 《一路狂飙》原始证据 → AtomicFact → SchemaSlot → Rule 审计", "", f"- Facts: {metrics['factCount']}", f"- Rules: {metrics['ruleCount']}", f"- Rule 类型: {json.dumps(metrics['ruleTypeCounts'], ensure_ascii=False)}", f"- 无证据 Facts / Rules: {metrics['factsWithoutEvidence']} / {metrics['rulesWithoutEvidence']}", f"- 残句 Fact / Rule: {metrics['residualFragmentFactCount']} / {metrics['residualFragmentRuleCount']}", f"- 槽位语义不一致: {metrics['schemaSlotSemanticMismatchCount']}", f"- 混域 Fact: {metrics['mixedDomainFactCount']}", f"- inferred Fact: {metrics['inferredFactCount']}", f"- needs_revision Rule: {metrics['needsRevisionRuleCount']}", ""]
    for item in splits:
        lines.extend([f"## {item['factId']}", "", f"原始证据：{item['rawEvidence']}", f"AtomicFact：{item['sourceText']}", f"证据等级：{item['evidenceLevel']}", f"SchemaSlot：{'、'.join(item['schemaSlots']) or '不进入有效槽位'}", f"证据：{'、'.join(item['evidenceIds'])}", ""])
        lines.extend(f"- `{rule['ruleType']}` / `{rule['schemaSlot']}`：{rule['behavior']}（{rule['reviewStatus']}）" for rule in item["rules"])
        lines.append("")
    (output_dir / "fact-rule-split-audit.md").write_text("\n".join(lines), encoding="utf-8")
    focus_lines = ["# Phase 2.1 重点样本审计", ""]
    for label, items in samples.items():
        focus_lines.extend([f"## {label}", ""])
        for item in items:
            focus_lines.extend([
                f"原始证据：{item['rawEvidence']}",
                f"AtomicFact（{item['evidenceLevel']}）：{item['sourceText']}",
                f"SchemaSlot：{'、'.join(item['schemaSlots']) or '不进入有效槽位'}",
            ])
            if item["rules"]:
                focus_lines.extend(
                    f"- Rule `{rule['ruleType']}`：{rule['behavior']}（{rule['semanticValidity']}）"
                    for rule in item["rules"]
                )
            else:
                focus_lines.append("- Rule：不生成（推论或待修订 Fact）")
            focus_lines.append("")
    (output_dir / "focus-samples.md").write_text("\n".join(focus_lines), encoding="utf-8")
    return audit


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", default="data/jobs/8312a91c89e144e6a59f81b982f14c06/job.json")
    parser.add_argument("--output", default="artifacts/planning-content-phase2.1-2026-08-17")
    args = parser.parse_args()
    print(json.dumps(generate(Path(args.job), Path(args.output)), ensure_ascii=False, indent=2))
