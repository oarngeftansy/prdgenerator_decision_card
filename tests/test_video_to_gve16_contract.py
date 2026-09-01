import json

import pytest

from backend.planner import generate_plan
from backend.planning_model import validate_planning_model
from backend.quality import reconcile_and_audit


def _contract_job(mode: str) -> dict:
    frames = []
    for index, action in enumerate(("未知待确认", {"type": "tap", "target": "confirm"}), 1):
        frames.append({
            "id": f"F{index:04d}",
            "sceneId": 0,
            "timestamp": float(index),
            "structure": {"engine": "ScreenCoder-compatible-CV", "elements": [], "regionCounts": {}},
            "analysis": {
                "what": "确认流程",
                "eventType": "unknown" if index == 1 else "tap",
                "beforeState": {"dialog": "open"},
                "userAction": action,
                "systemResponse": "未知待确认" if index == 1 else {"dialog": "closed"},
                "afterState": {"dialog": "open" if index == 1 else "closed"},
                "evidenceLevel": "未知待确认" if index == 1 else "明确展示",
                "confidence": "低" if index == 1 else "高",
                "unknowns": ["触发原因不可见"] if index == 1 else [],
            },
        })
    return {
        "id": f"contract-{mode}",
        "metadata": {"mode": mode, "projectName": "契约样例", "scope": "GVE16"},
        "video": {"filename": "contract.mp4", "duration": 10.0},
        "frames": frames,
        "scenes": [{
            "id": 0, "start": 0.0, "end": 10.0, "frameIds": ["F0001", "F0002"],
            "analysis": {
                "title": "确认", "sceneType": "结算" if mode == "gameplay" else "确认弹窗",
                "summary": "确认后关闭", "objective": "完成确认",
                "entryCondition": {"dialog": "open"}, "exitCondition": {"dialog": "closed"},
                "visibleRules": [], "stateChanges": [{"from": "open", "to": "closed"}],
                "evidenceLevel": "明确展示", "confidence": "高",
            },
        }],
        "componentTracks": [],
        "analysisSummary": {"detailFrameCount": 2, "modelEnabled": True},
    }


@pytest.mark.parametrize("mode", ["gameplay", "interaction"])
def test_video_evidence_compiles_to_matching_model_and_document(mode):
    job = _contract_job(mode)
    facts, review, report = reconcile_and_audit(job)
    job.update(factTable=facts, reviewQueue=review, qualityReport=report)

    document = generate_plan(job)
    model = job["planningModel"]

    assert validate_planning_model(model) == []
    assert json.loads(json.dumps(model, ensure_ascii=False)) == model
    assert all(event["id"] not in document for event in model["events"])
    assert all(scene["id"] not in document for scene in model["scenes"])
    assert model[mode] is not None
    assert model["designHandoff"]["generatedArtifacts"] == []
