from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
JOB_PATH = ROOT / "data" / "jobs" / "8312a91c89e144e6a59f81b982f14c06" / "job.json"

ACCEPTANCE = {
    "GCH-001": [("正常移动", "载具持续前进且横向操作不会被系统复位"), ("生命归零", "立即结束本局并进入失败结果")],
    "GCH-003": [("目标进入范围", "对应武器自动攻击并显示命中反馈"), ("目标离开范围", "该武器不继续对目标造成伤害")],
    "GCH-006": [("进入首领阶段", "先出现首领警告，再展示首领生命值并继续战斗"), ("首领被击败", "停止战斗并进入成功结算")],
    "GCH-010": [("挑战成功", "结算同时显示通关时间、奖励和武器伤害统计"), ("载具生命归零", "不得显示挑战成功结果")],
    "GCH-012": [("确认一个强化", "只应用所选强化并关闭选择界面"), ("执行刷新", "替换候选但不自动应用任何强化")],
    "GCH-016": [("确认终极词条", "攻击方式与卡片说明一致，收益和代价同时生效"), ("条件未满足", "普通候选不得冒充终极词条")],
    "GCH-018": [("滚动结束", "界面形成一个可确认的抽取结果"), ("规则证据不足", "不展示未经确认的权重、保底或消耗结论")],
}


def main() -> None:
    job = json.loads(JOB_PATH.read_text(encoding="utf-8"))
    review_revision = int((job.get("reviewModel") or {}).get("revision") or 0)
    gameplay = job["gameplayReviewModel"]
    gameplay["interactionRevision"] = review_revision
    for chapter in gameplay.get("chapters") or []:
        rows = ACCEPTANCE.get(str(chapter.get("id") or ""), [])
        chapter["acceptanceCases"] = [
            {"id": f"{chapter['id']}-AC-{index:02d}", "scenario": scenario, "expected": expected, "source": "stage5_quality_gate"}
            for index, (scenario, expected) in enumerate(rows, 1)
        ]
    gameplay["revision"] = int(gameplay.get("revision") or 0) + 1
    gameplay.setdefault("reviewState", {})["previewRevision"] = None
    job["updatedAt"] = datetime.now(timezone.utc).isoformat()
    temporary = JOB_PATH.with_suffix(".stage5-depth.tmp")
    temporary.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(JOB_PATH)
    print(json.dumps({"interactionRevision": review_revision, "gameplayRevision": gameplay["revision"], "chapters": len(ACCEPTANCE)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
