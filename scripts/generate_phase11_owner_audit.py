from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from backend.phase1_directory import build_phase1_directory
from scripts.generate_phase1_directory_audit import _blind_fixture


ROOT = Path(__file__).resolve().parents[1]
JOB_PATH = ROOT / "data/jobs/8312a91c89e144e6a59f81b982f14c06/job.json"
PHASE1_AUDIT = ROOT / "artifacts/planning-content-phase1-2026-08-14/phase1_audit.json"
OUTPUT_DIR = ROOT / "artifacts/planning-content-phase1.1-2026-08-17"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _object(result: dict[str, Any], title: str) -> dict[str, Any]:
    return next(obj for system in result["tree"] for obj in system["objects"] if obj["title"] == title)


def _acceptance(result: dict[str, Any], blind: dict[str, Any]) -> dict[str, bool]:
    level = _object(result, "关卡")
    settlement = _object(result, "结算")
    monster = _object(result, "怪物")
    vehicle = _object(result, "载具")
    weapon = _object(result, "武器")
    blind_outcome = _object(blind, "胜负")
    titles = lambda obj: [chapter["title"] for chapter in obj.get("chapters") or []]
    slot_definitions = [
        (obj["title"], chapter)
        for system in result["tree"]
        for obj in system["objects"]
        for chapter in obj.get("chapters") or []
        if chapter.get("semanticDomain") == "weapon_slot" and chapter.get("definitionMode") == "primary"
    ]
    return {
        "no_level_damage_death": "受击及死亡" not in titles(level),
        "settlement_parent_carries_schema": settlement.get("chapterType") == "settlement",
        "no_settlement_same_name_child": "结算" not in titles(settlement),
        "blind_outcome_not_damage_death": "受击及死亡" not in titles(blind_outcome),
        "one_primary_weapon_slot": len(slot_definitions) == 1 and slot_definitions[0][0] == "载具",
        "weapon_has_no_duplicate_slot": "栏位" not in titles(weapon),
        "vehicle_keeps_primary_slot": "栏位" in titles(vehicle),
        "monster_has_no_level_flow": "关卡流程" not in titles(monster),
        "custom_zero": result["qualityReport"]["customCount"] == 0,
        "unknown_zero": result["qualityReport"]["unknownCount"] == 0,
        "no_summary_style_titles": all(
            result["qualityReport"][key] == 0
            for key in ("twelveOrMoreTitleCount", "dunhaoTitleCount", "multipleActionsCount", "sentenceLikeCount", "containsResultCount")
        ),
    }


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    before = _sha256(JOB_PATH)
    job = json.loads(JOB_PATH.read_text(encoding="utf-8"))
    result = build_phase1_directory(job["gameplayReviewModel"])
    blind = build_phase1_directory(_blind_fixture())
    phase1 = json.loads(PHASE1_AUDIT.read_text(encoding="utf-8"))
    checks = _acceptance(result, blind)
    after = _sha256(JOB_PATH)
    audit = {
        "phase": "Phase 1.1",
        "versionLabel": "B2",
        "jobId": job["id"],
        "sourceJobSha256Before": before,
        "sourceJobSha256After": after,
        "sourceJobUnchanged": before == after,
        "b1DirectoryTree": phase1["bDirectoryTree"],
        "b2DirectoryTree": result["humanReadableTree"],
        "titleQualityReport": result["qualityReport"],
        "ownershipDecisions": result["ownershipDecisions"],
        "acceptance": checks,
        "passed": all(checks.values()) and before == after,
    }
    _write_json(OUTPUT_DIR / "b2_directory.json", result)
    _write_json(OUTPUT_DIR / "owner_resolution_decisions.json", result["ownershipDecisions"])
    _write_json(OUTPUT_DIR / "title_quality_report.json", result["qualityReport"])
    _write_json(OUTPUT_DIR / "blind_test_result.json", blind)
    _write_json(OUTPUT_DIR / "phase11_audit.json", audit)
    (OUTPUT_DIR / "directory_trees.md").write_text(
        "# B1\n\n```text\n" + phase1["bDirectoryTree"] +
        "\n```\n\n# B2\n\n```text\n" + result["humanReadableTree"] + "\n```\n",
        encoding="utf-8",
    )
    if not audit["passed"]:
        raise RuntimeError(json.dumps(audit, ensure_ascii=False, indent=2))
    print(json.dumps({
        "output": str(OUTPUT_DIR),
        "passed": True,
        "sourceJobUnchanged": True,
        "acceptance": checks,
        "titleQualityReport": result["qualityReport"],
        "b2DirectoryTree": result["humanReadableTree"],
        "blindDirectoryTree": blind["humanReadableTree"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
