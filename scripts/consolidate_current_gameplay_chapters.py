from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from backend.gameplay_copy import consolidate_gameplay_chapters, _rebuild_derived_artifacts
from backend.review_preview import build_final_review_preview
from scripts.migrate_current_gameplay_task import atomic_write, sha256


GROUPS = [
    {"chapterIds": ["GCH-001", "GCH-002"], "title": "战斗移动与生存", "subsystemName": "角色与载具控制", "summary": "载具沿预设路线自动前进，玩家可横向调整位置以规避敌人或对准目标；载具受击会损失生命值，生命值归零时本局失败。"},
    {"chapterIds": ["GCH-003", "GCH-004", "GCH-005"], "title": "武器攻击", "subsystemName": "武器射击机制", "summary": "武器自动攻击射程内敌人；不同槽位承载不同武器，命中后以对应伤害数字反馈结果。"},
    {"chapterIds": ["GCH-006", "GCH-007", "GCH-008", "GCH-009"], "title": "关卡战斗流程", "subsystemName": "敌人与关卡进程", "summary": "常规敌人随关卡进度持续出现；达到阶段条件后首领登场并切换攻击形态，关卡计时与推进状态共同反映当前战斗阶段。"},
    {"chapterIds": ["GCH-010", "GCH-011"], "title": "胜负与结算", "subsystemName": "关卡进程与结算", "summary": "击败首领后进入挑战成功结算，展示通关时间、奖励和伤害统计；载具生命值归零时本局失败。"},
    {"chapterIds": ["GCH-012", "GCH-013", "GCH-014", "GCH-015"], "title": "局内升级与强化", "systemName": "Roguelike成长系统", "subsystemName": "升级奖励选择", "summary": "升级时暂停战斗并提供三项强化，候选项可解锁新武器或增强已有武器；玩家也可通过刷新替换当前候选。"},
    {"chapterIds": ["GCH-016", "GCH-017"], "title": "终极词条", "systemName": "Roguelike成长系统", "subsystemName": "终极词条系统", "summary": "满足条件后出现带有特殊边框的终极词条；确认后改变武器的攻击逻辑，并可能同时附带属性代价。"},
    {"chapterIds": ["GCH-018"], "title": "随机武器抽取", "systemName": "Roguelike成长系统", "subsystemName": "老虎机抽奖机制", "summary": "老虎机式九宫格通过滚动随机定格武器或技能，其结果生成方式独立于普通三选一强化。"},
]


def execute(path: Path, *, apply: bool = False) -> dict:
    job = json.loads(path.read_text(encoding="utf-8"))
    before_hash = sha256(path)
    before_count = len((job.get("gameplayReviewModel") or {}).get("chapters") or [])
    candidate = json.loads(json.dumps(job, ensure_ascii=False))
    consolidate_gameplay_chapters(candidate["gameplayReviewModel"], GROUPS)
    result = {"mode": "apply" if apply else "dry-run", "jobId": job.get("id"), "beforeHash": before_hash, "beforeChapters": before_count, "afterChapters": len(candidate["gameplayReviewModel"]["chapters"]), "groups": GROUPS}
    if not apply:
        return result
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = path.with_name(f"job.before-chapter-consolidation-{stamp}.json")
    shutil.copy2(path, backup)
    try:
        candidate["gameplayReviewModel"] = _rebuild_derived_artifacts(candidate["gameplayReviewModel"])
        candidate["gameplayFinalPreview"] = build_final_review_preview(candidate, path.parent)
        candidate["chapterConsolidation"] = {**result, "backup": str(backup.resolve())}
        atomic_write(path, candidate)
    except Exception:
        shutil.copy2(backup, path)
        raise
    return {**result, "backup": str(backup.resolve()), "afterHash": sha256(path), "revision": candidate["gameplayReviewModel"]["revision"]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("job", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    result = execute(args.job.resolve(), apply=args.apply)
    encoded = json.dumps(result, ensure_ascii=False, indent=2)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(encoded, encoding="utf-8")
    print(encoded)


if __name__ == "__main__":
    main()
