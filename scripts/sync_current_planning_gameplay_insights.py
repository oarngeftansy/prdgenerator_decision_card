from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from backend.planning_gameplay_sync import planning_gameplay_sync_report, sync_planning_gameplay_insights


ROOT = Path(__file__).resolve().parents[1]
JOB_ID = "8312a91c89e144e6a59f81b982f14c06"
JOB_PATH = ROOT / "data" / "jobs" / JOB_ID / "job.json"

INSIGHTS = {
    "STG-001": [{"id": "PGI-001", "targetChapterId": "GCH-012", "carrier": "keyRules", "sourceFrameIds": ["F0001", "F0002"], "text": "武器属性至少包含武器名称、等级和本次强化涉及的属性；这些信息同时用于强化选择与战斗结果判断。"}],
    "STG-002": [{"id": "PGI-002", "targetChapterId": "GCH-016", "carrier": "normalFlow", "sourceFrameIds": ["F0005", "F0006"], "text": "玩家确认终极词条后，武器攻击方式发生结构性变化，例如由单向喷射改为同时向四个方向喷射。"}],
    "STG-003": [{"id": "PGI-003", "targetChapterId": "GCH-018", "carrier": "keyRules", "sourceFrameIds": ["F0007", "F0008"], "text": "抽取滚动区域会同时展示武器与技能图标，停止后读取中间结果框中的最终结果。"}],
    "STG-005": [{"id": "PGI-004", "targetChapterId": "GCH-006", "carrier": "normalFlow", "sourceFrameIds": ["F0011", "F0012"], "text": "到达首领阶段后，系统先显示首领来袭警告，再进入首领战。"}],
    "STG-006": [{"id": "PGI-005", "targetChapterId": "GCH-006", "carrier": "normalFlow", "sourceFrameIds": ["F0013", "F0014"], "text": "首领生命值归零后结束战斗并进入关卡结算。"}],
    "STG-007": [{"id": "PGI-006", "targetChapterId": "GCH-010", "carrier": "normalFlow", "sourceFrameIds": ["F0015"], "text": "伤害统计按武器汇总本局输出，帮助玩家判断本局主要伤害来源。"}],
}


def main() -> None:
    job = json.loads(JOB_PATH.read_text(encoding="utf-8"))
    gameplay = job["gameplayReviewModel"]
    chapters = {str(item.get("id")): item for item in gameplay.get("chapters") or []}
    for old in gameplay.get("planningGameplayTrace") or []:
        if old.get("status") != "delivered":
            continue
        chapter = chapters.get(str(old.get("targetChapterId") or ""))
        values = ((chapter or {}).get("plannerSections") or {}).get(str(old.get("carrier") or ""))
        if isinstance(values, list):
            values[:] = [item for item in values if item != old.get("text")]
    for stage in (job.get("reviewModel") or {}).get("stages") or []:
        stage["gameplayInsights"] = INSIGHTS.get(str(stage.get("id") or ""), [{
            "id": f"PGI-BOARD-{stage.get('id')}", "text": "页面截图的具体空间排版只保留在策划草图。",
            "gameplayRelevant": False, "reason": "页面空间布局不需要重复写入玩法正文",
            "sourceFrameIds": [str(item.get("frameId")) for item in stage.get("representativeFrames") or [] if item.get("frameId")],
        }])
    model = sync_planning_gameplay_insights(job, gameplay)
    model["revision"] = int(model.get("revision") or 0) + 1
    model["interactionRevision"] = int((job.get("reviewModel") or {}).get("revision") or 0)
    model.setdefault("reviewState", {})["previewRevision"] = None
    job["gameplayReviewModel"] = model
    job["updatedAt"] = datetime.now(timezone.utc).isoformat()
    report = planning_gameplay_sync_report(job, model)
    if not report["passed"]:
        raise RuntimeError(json.dumps(report, ensure_ascii=False))
    temporary = JOB_PATH.with_suffix(".planning-gameplay-sync.tmp")
    temporary.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(JOB_PATH)
    output = ROOT / "artifacts" / "stage5-refined-browser" / "planning-gameplay-sync-report.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
