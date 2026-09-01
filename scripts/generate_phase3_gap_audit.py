from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.rule_normalizer import build_approved_data_v2


FOCUS = {
    "武器攻击": lambda c: c["object"] == "武器" and c["title"] == "攻击",
    "载具栏位": lambda c: c["object"] == "载具" and c["title"] == "栏位",
    "三选一": lambda c: c.get("mechanicVariant") == "three_choice",
    "武器抽取": lambda c: c.get("mechanicVariant") == "roulette",
    "怪物刷新": lambda c: c["object"] == "怪物" and c["title"] == "刷新",
    "怪物移动": lambda c: c["object"] == "怪物" and c["title"] == "移动",
    "怪物攻击": lambda c: c["object"] == "怪物" and c["title"] == "攻击",
    "关卡流程": lambda c: c["title"] == "关卡流程",
    "胜负判定": lambda c: c["title"] == "胜负判定",
    "结算": lambda c: c["title"] == "结算",
}

LEGACY_COMPARISONS = [
    ("候选池来源：待确认（建议）", "三选一的候选池读取哪份配置或已确认数据集合？"),
    ("是否重复：待确认（建议）", "同一次生成的三张候选卡是否允许出现相同候选项？"),
    ("刷新消耗：待确认（建议）", "刷新采用资源消耗还是广告条件；资源类型、数量和扣除时点分别是什么？"),
    ("移动停止：待确认（建议）", "怪物在什么条件下停止移动？"),
    ("结算离开：待确认（建议）", "玩家通过哪些操作离开结算，分别进入哪个后续状态？"),
]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def generate(job_path: Path, output_dir: Path) -> dict:
    before = _sha(job_path)
    job = json.loads(job_path.read_text(encoding="utf-8"))
    result = build_approved_data_v2(job["gameplayReviewModel"])
    chapters = {chapter["chapterId"]: chapter for chapter in result["chapters"]}
    gaps_by_chapter = {}
    for gap in result["gaps"]:
        gaps_by_chapter.setdefault(gap["chapterId"], []).append(gap)
    focus = {}
    for label, predicate in FOCUS.items():
        selected = [chapter for chapter in result["chapters"] if predicate(chapter)]
        focus[label] = [{
            **next(row for row in result["chapterCoverage"] if row["chapterId"] == chapter["chapterId"]),
            "system": chapter["system"], "object": chapter["object"],
            "gaps": gaps_by_chapter.get(chapter["chapterId"], []),
        } for chapter in selected]
    after = _sha(job_path)
    audit = {
        "phase": "3", "jobId": job.get("id"), "metrics": result["metrics"],
        "provenance": {"sourceJobStatus": job.get("status"), "sourceJobSha256Before": before, "sourceJobSha256After": after, "jobMutated": before != after, "sourceMode": "read_only_memory_copy"},
        "chapterCoverage": result["chapterCoverage"], "focusChapters": focus,
        "legacyComparisons": [{"legacy": old, "phase3": new} for old, new in LEGACY_COMPARISONS],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "phase-3-gap-result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "phase-3-gap-audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# 《一路狂飙》Phase 3 Gap 审计", "", f"- Gap 总数：{result['metrics']['gapCount']}", f"- implementation_blocking：{result['metrics']['implementationBlocking']}", f"- qa_blocking：{result['metrics']['qaBlocking']}", f"- documentation_gap：{result['metrics']['documentationGap']}", f"- inferred Fact 关闭 Gap：{result['metrics']['inferredFactsClosingGaps']}", f"- 重复 Gap：{result['metrics']['duplicateGapCount']}", ""]
    for label, rows in focus.items():
        lines.extend([f"## {label}", ""])
        for row in rows:
            path = row["title"] if row["object"] == row["title"] else f"{row['object']} → {row['title']}"
            lines.append(f"### {path}（required {row['required']} / covered {row['covered']} / open {row['openGap']}）")
            lines.append("")
            if row["coveredSlots"]: lines.append("已覆盖：" + "、".join(row["coveredSlots"]))
            for gap in row["gaps"]:
                lines.append(f"- [{gap['severity']}] `{gap['schemaSlot']}`：{gap['question']}")
            lines.append("")
    lines.extend(["## 旧版低质量待确认 → 新版业务 Gap", ""])
    for old, new in LEGACY_COMPARISONS:
        lines.extend([f"- 旧：{old}", f"  新：{new}"])
    (output_dir / "gap-audit.md").write_text("\n".join(lines), encoding="utf-8")
    return audit


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", default="data/jobs/8312a91c89e144e6a59f81b982f14c06/job.json")
    parser.add_argument("--output", default="artifacts/planning-content-phase3-2026-08-17")
    args = parser.parse_args()
    print(json.dumps(generate(Path(args.job), Path(args.output)), ensure_ascii=False, indent=2))
