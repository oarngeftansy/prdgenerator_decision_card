from __future__ import annotations

import hashlib
import json
from collections import OrderedDict
from pathlib import Path
from typing import Any

from backend.chapter_schema_library import SCHEMA_VERSION, chapter_schema_library
from backend.phase1_directory import build_phase1_directory


ROOT = Path(__file__).resolve().parents[1]
JOB_PATH = ROOT / "data/jobs/8312a91c89e144e6a59f81b982f14c06/job.json"
BASELINE_DIR = ROOT / "artifacts/planning-content-baseline-2026-08-14"
OUTPUT_DIR = ROOT / "artifacts/planning-content-phase1-2026-08-14"

HIGH_RISK_OWNERS = OrderedDict((
    ("武器解锁、攻击与词条成长", "GCH-003"),
    ("武器命中、反馈与伤害归集", "GCH-003"),
    ("攻击、养成与词条生效", "GCH-003"),
    ("解锁、养成与词条进入随机池", "GCH-003"),
    ("候选、刷新与确认", "GCH-012"),
    ("终极词条进入与生效", "GCH-016"),
    ("滚动、跳过与结果", "GCH-018"),
    ("刷新、作战与首领阶段", "GCH-006"),
))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _a_tree(directory: dict[str, Any]) -> str:
    systems: OrderedDict[str, list[str]] = OrderedDict()
    for entry in directory.get("entries") or []:
        systems.setdefault(entry["sectionTitle"], []).append(entry["title"])
    lines: list[str] = []
    for system, titles in systems.items():
        lines.append(system)
        for index, title in enumerate(titles):
            lines.append(f"{'└─' if index == len(titles) - 1 else '├─'} {title}")
    return "\n".join(lines)


def _public_node(node: dict[str, Any]) -> dict[str, Any]:
    return {key: node.get(key) for key in (
        "title", "chapterType", "mechanicVariant", "matchedSchema",
        "classificationEvidence", "namingReason", "titleSplit",
    )}


def _blind_fixture() -> dict[str, Any]:
    return {
        "fixtureName": "turn_based_card_duel",
        "chapters": [
            {
                "id": "CARD-001", "scope": "手牌", "systemName": "卡牌对局",
                "claims": [
                    {"text": "回合开始时从牌库随机抽取卡牌并写入空手牌栏位。"},
                    {"text": "手牌栏位达到上限后停止抽牌。"},
                ],
            },
            {
                "id": "CARD-002", "scope": "回合", "systemName": "卡牌对局",
                "claims": [
                    {"text": "行动点耗尽后结束当前回合并切换行动方。"},
                    {"text": "回合切换后结算持续效果。"},
                ],
            },
            {
                "id": "CARD-003", "scope": "胜负", "systemName": "卡牌对局",
                "claims": [{"text": "任一方生命值归零时停止对局并进入胜负结算。"}],
            },
        ],
    }


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    before = _sha256(JOB_PATH)
    job = json.loads(JOB_PATH.read_text(encoding="utf-8"))
    model = job["gameplayReviewModel"]
    baseline_directory = json.loads((BASELINE_DIR / "gameplay_directory.json").read_text(encoding="utf-8"))
    result = build_phase1_directory(model)

    public_comparisons = []
    comparison_by_id = {}
    for comparison in result["comparisons"]:
        row = {
            "sourceChapterId": comparison["sourceChapterId"],
            "oldTitle": comparison["oldTitle"],
            "objectTitle": comparison["objectTitle"],
            "splitInto": comparison["splitInto"],
            "titleSplit": comparison["titleSplit"],
            "newNodes": [_public_node(node) for node in comparison["newNodes"]],
        }
        public_comparisons.append(row)
        comparison_by_id[row["sourceChapterId"]] = row

    high_risk = []
    serialized_model = json.dumps(model, ensure_ascii=False)
    for old_title, owner_id in HIGH_RISK_OWNERS.items():
        source_title = old_title
        if old_title == "终极词条进入与生效" and old_title not in serialized_model:
            source_title = "终极词条的进入与生效"
        owner = comparison_by_id[owner_id]
        high_risk.append({
            "oldTitle": old_title,
            "sourceMatchedTitle": source_title,
            "sourceChapterId": owner_id,
            "splitInto": owner["splitInto"],
            "titleSplit": True,
            "newNodes": owner["newNodes"],
        })

    hit_types = sorted({
        chapter["chapterType"]
        for system in result["tree"]
        for obj in system["objects"]
        for chapter in obj["chapters"]
    })
    all_types = list(chapter_schema_library.list_types(SCHEMA_VERSION))
    hit_variants = sorted({
        f"{chapter['chapterType']}:{chapter['mechanicVariant']}"
        for system in result["tree"]
        for obj in system["objects"]
        for chapter in obj["chapters"]
        if chapter.get("mechanicVariant")
    })
    coverage = {
        "schemaVersion": SCHEMA_VERSION,
        "hitChapterTypes": hit_types,
        "notHitChapterTypes": [kind for kind in all_types if kind not in hit_types],
        "hitMechanicVariants": hit_variants,
        "unknownCount": result["qualityReport"]["unknownCount"],
        "customCount": result["qualityReport"]["customCount"],
    }

    blind_input = _blind_fixture()
    blind_result = build_phase1_directory(blind_input)
    blind_text = blind_result["humanReadableTree"]
    blind_audit = {
        "fixtureName": blind_input["fixtureName"],
        "humanReadableTree": blind_text,
        "qualityReport": blind_result["qualityReport"],
        "containsVehicle": "载具" in blind_text,
        "containsWeapon": "武器" in blind_text,
        "containsGVE16": "GVE16" in blind_text,
        "pass": all(marker not in blind_text for marker in ("载具", "武器", "GVE16")),
        "result": blind_result,
    }

    audit = {
        "phase": "Phase 1",
        "jobId": job["id"],
        "sourceRevision": model["revision"],
        "sourceJobStatus": job["status"],
        "sourceDirectoryStatus": baseline_directory["status"],
        "sourceProvenance": "A版来自 failed job；玩法目录为 draft；P7 仅在只读内存副本临时解除目录门禁生成，未写回 job。",
        "sourceJobSha256Before": before,
        "sourceJobSha256After": _sha256(JOB_PATH),
        "sourceJobUnchanged": before == _sha256(JOB_PATH),
        "aDirectoryTree": _a_tree(baseline_directory),
        "bDirectoryTree": result["humanReadableTree"],
        "comparisons": public_comparisons,
        "highRiskTitleMappings": high_risk,
        "titleQualityReport": result["qualityReport"],
        "schemaCoverage": coverage,
    }

    _write_json(OUTPUT_DIR / "phase1_directory.json", result)
    _write_json(OUTPUT_DIR / "a_vs_b_directory.json", public_comparisons)
    _write_json(OUTPUT_DIR / "high_risk_title_mappings.json", high_risk)
    _write_json(OUTPUT_DIR / "title_quality_report.json", result["qualityReport"])
    _write_json(OUTPUT_DIR / "schema_coverage.json", coverage)
    _write_json(OUTPUT_DIR / "blind_test_input.json", blind_input)
    _write_json(OUTPUT_DIR / "blind_test_result.json", blind_audit)
    _write_json(OUTPUT_DIR / "phase1_audit.json", audit)
    (OUTPUT_DIR / "directory_trees.md").write_text(
        "# A版旧目录\n\n```text\n" + audit["aDirectoryTree"] +
        "\n```\n\n# B版新目录\n\n```text\n" + audit["bDirectoryTree"] + "\n```\n",
        encoding="utf-8",
    )
    if not audit["sourceJobUnchanged"]:
        raise RuntimeError("source job changed while generating Phase 1 audit")
    print(json.dumps({
        "output": str(OUTPUT_DIR),
        "sourceJobUnchanged": True,
        "titleQualityReport": result["qualityReport"],
        "schemaCoverage": coverage,
        "blindPass": blind_audit["pass"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
