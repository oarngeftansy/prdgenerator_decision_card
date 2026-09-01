from backend.planner import generate_plan
from backend.quality import reconcile_and_audit


def _job(mode="gameplay"):
    return {
        "id": "job-nested-state",
        "metadata": {"mode": mode, "projectName": "嵌套状态", "scope": ""},
        "video": {"filename": "nested.mp4", "duration": 8.0},
        "frames": [{
            "id": "F0001",
            "sceneId": 0,
            "timestamp": 2.5,
            "structure": {"engine": "ScreenCoder-UIED", "regionCounts": {}, "elements": []},
            "analysis": {
                "what": {"page": "level", "modal": None},
                "eventType": "tap",
                "beforeState": {"page": "menu", "button": {"enabled": True}},
                "userAction": {"type": "tap", "target": "start"},
                "systemResponse": ["按钮反馈", {"navigate": "level"}],
                "afterState": {"page": "level", "hud": {"visible": True}},
                "evidenceLevel": "明确展示",
                "confidence": "高",
                "unknowns": [],
            },
        }],
        "scenes": [{
            "id": 0,
            "start": 0.0,
            "end": 8.0,
            "frameIds": ["F0001"],
            "analysis": {
                "title": "开始关卡",
                "sceneType": "入口",
                "summary": "从菜单进入关卡",
                "objective": "开始游戏",
                "entryCondition": {"page": "menu"},
                "exitCondition": {"page": "level"},
                "visibleRules": [{"trigger": "tap", "result": "navigate"}],
                "stateChanges": [{"from": "menu", "to": "level"}],
                "evidenceLevel": "明确展示",
                "confidence": "高",
            },
        }],
        "componentTracks": [],
        "analysisSummary": {"detailFrameCount": 1, "modelEnabled": True},
        "qualityReport": {"score": 90, "reviewItemCount": 0, "checks": []},
    }


def test_nested_model_values_are_audited_without_unhashable_error():
    facts, review, report = reconcile_and_audit(_job())

    assert facts[0]["state"] == {"page": "level", "hud": {"visible": True}}
    assert not any(item["type"] == "causal-gap" for item in review)
    assert report["score"] == 100


def test_generate_plan_persists_validated_model_and_renders_stable_ids():
    job = _job("interaction")
    document = generate_plan(job)

    assert job["planningModel"]["standard"] == "GVE16"
    assert job["planningModel"]["scenes"][0]["id"] == "SCN-001"
    assert job["planningModel"]["events"][0]["id"] == "EVT-001"
    assert "SCN-001" not in document
    assert "EVT-001" not in document
    assert "Evidence" not in document
    assert "证据索引" not in document
    assert "交互策划案" in document
    assert "schema-ready" in document


def test_image_sequence_plan_uses_screenshot_order_instead_of_video_time():
    job = _job("interaction")
    job["metadata"]["inputType"] = "image_sequence"
    job["frames"][0]["sequenceIndex"] = 1
    job["frames"][0]["sourceName"] = "01-首页.png"

    document = generate_plan(job)

    assert "原始截图" in document
    assert "第 1 张" in document
    assert "原视频" not in document
    assert "截图未展示项均标记为待确认" in document
    assert "视频未展示项" not in document


def test_auxiliary_video_findings_stay_inside_existing_exception_section():
    job = _job("interaction")
    job["metadata"]["inputType"] = "image_sequence"
    job["frames"][0]["sequenceIndex"] = 1
    job["auxiliaryVideo"] = {"analysis": {
        "status": "completed",
        "transitions": [{"fromFrameId": "F0001", "toFrameId": "F0002", "motion": "淡入"}],
        "temporaryPrompts": ["短暂出现保存成功"],
        "operationTiming": [],
        "uncertainties": [],
    }}

    document = generate_plan(job)

    assert "辅助视频合理推断" in document
    assert "淡入" in document
    assert document.count("## 8. 异常、边界状态与响应式") == 1


def test_confirmed_delivery_drops_structured_garbage_and_unproven_transition_copy():
    from tests.review_fixtures import make_confirmed_job

    job = make_confirmed_job()
    transition = job["reviewModel"]["transitions"][0]
    transition["triggerLabel"] = "', ."
    transition["condition"] = {"type": "Passive / None", "description": "系统自动触发"}
    transition["response"] = {"action": "Trigger Boss Warning Overlay", "details": [{"description": "显示首领来袭提示"}]}

    document = generate_plan(job)

    assert "', ." not in document
    assert "Passive" not in document
    assert "Trigger Boss" not in document
    assert "{'" not in document
