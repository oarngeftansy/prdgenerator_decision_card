from copy import deepcopy


def make_image_job():
    return {
        "id": "job-1",
        "metadata": {
            "mode": "interaction",
            "inputType": "image_sequence",
            "projectName": "武器流程",
        },
        "frames": [
            {
                "id": "F0001",
                "sequenceIndex": 1,
                "sceneId": 0,
                "sourceName": "01.png",
                "imageUrl": "/artifacts/job-1/frames/F0001.jpg",
                "analysis": {
                    "what": "选择武器",
                    "userAction": "点击卡片",
                    "systemResponse": "卡片选中",
                    "afterState": "选择完成",
                    "beforeState": "进入关卡",
                    "evidenceLevel": "明确展示",
                    "confidence": "高",
                },
            },
            {
                "id": "F0002",
                "sequenceIndex": 2,
                "sceneId": 1,
                "sourceName": "02.png",
                "imageUrl": "/artifacts/job-1/frames/F0002.jpg",
                "analysis": {
                    "what": "进入战斗",
                    "userAction": "系统自动开始",
                    "systemResponse": "战斗开始",
                    "afterState": "战斗中",
                    "beforeState": "选择完成",
                    "evidenceLevel": "合理推断",
                    "confidence": "中",
                },
            },
        ],
        "scenes": [
            {
                "id": 0,
                "frameIds": ["F0001"],
                "analysis": {
                    "title": "选择武器",
                    "objective": "确认武器",
                    "entryCondition": "进入关卡",
                    "exitCondition": "选择完成",
                },
            },
            {
                "id": 1,
                "frameIds": ["F0002"],
                "analysis": {
                    "title": "战斗",
                    "objective": "完成战斗",
                    "entryCondition": "选择完成",
                    "exitCondition": "战斗结束",
                },
            },
        ],
        "componentTracks": [],
    }


def make_confirmed_job():
    from backend.review_model import build_review_model

    job = deepcopy(make_image_job())
    model = build_review_model(job)
    model["reviewState"].update(
        {
            "status": "preview",
            "flowConfirmed": True,
            "confirmedStageIds": [stage["id"] for stage in model["stages"]],
            "previewRevision": model["revision"],
        }
    )
    for stage in model["stages"]:
        stage["confirmation"] = {"confirmed": True, "revision": model["revision"]}
        stage["smallLoop"] = {
            "display": stage["name"],
            "trigger": "已确认触发",
            "feedback": "已确认反馈",
            "result": stage["exitCondition"],
            "retry": "待确认",
        }
    for transition in model["transitions"]:
        transition["triggerType"] = "tap" if transition["targetStageId"] else "system_event"
        transition["resultType"] = "navigate" if transition["targetStageId"] else "terminal"
        transition["confirmation"] = {"confirmed": True, "revision": model["revision"]}
    for index, stage in enumerate(model["stages"], 1):
        region_count = 2 if index == 1 else 1
        for _ in range(region_count):
            region_id = f"REG-{len(model['regions']) + 1:04d}"
            model["regions"].append(
                {
                    "id": region_id,
                    "stageId": stage["id"],
                    "frameId": stage["representativeFrames"][0]["frameId"],
                    "name": f"区域 {len(model['regions']) + 1}",
                    "bounds": {
                        "x": 0.1,
                        "y": 0.1 + len(model["regions"]) * 0.1,
                        "width": 0.3,
                        "height": 0.1,
                    },
                    "displayOrder": len(model["regions"]) + 1,
                    "displayNumber": len(model["regions"]) + 1,
                    "sourceType": "human",
                    "primary": True,
                    "rule": {
                        "display": "已确认内容",
                        "condition": "已确认条件",
                        "action": "已确认操作",
                        "feedback": "已确认反馈",
                        "result": "已确认结果",
                        "exception": "待确认",
                    },
                    "confirmation": {"confirmed": True},
                }
            )
            stage["regionIds"].append(region_id)
    job["reviewModel"] = model
    return job
