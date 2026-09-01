from backend.loop_hierarchy import build_loop_hierarchy, loop_quality_gate, validate_loop_hierarchy


def _scene(index, kind, title):
    return {
        "id": index,
        "start": index * 10.0,
        "end": index * 10.0 + 9.0,
        "frameIds": [f"F{index + 1:04d}"],
        "analysis": {
            "sceneType": kind,
            "title": title,
            "objective": f"完成{title}",
            "entryCondition": f"进入{title}",
            "exitCondition": f"离开{title}",
            "summary": title,
            "confidence": "高",
        },
    }


def _job():
    scenes = [
        _scene(0, "主页面", "查看首页"),
        _scene(1, "主页面", "选择入口"),
        _scene(2, "选择弹窗", "打开选择"),
        _scene(3, "选择弹窗", "确认选择"),
        _scene(4, "结算页面", "查看结果"),
        _scene(5, "结算页面", "返回首页"),
    ]
    frames = [{"id": f"F{i + 1:04d}", "timestamp": i * 10.0, "sceneId": i} for i in range(6)]
    return {"id": "job-loop", "metadata": {"mode": "interaction", "projectName": "Demo"}, "scenes": scenes, "frames": frames}


def test_fallback_groups_visual_scenes_into_stages_and_small_loops():
    hierarchy = build_loop_hierarchy(_job())

    assert len(hierarchy["largeLoops"]) == 1
    large_loop = hierarchy["largeLoops"][0]
    assert [stage["title"] for stage in large_loop["stages"]] == ["主页面", "选择弹窗", "结算页面"]
    assert all(len(stage["smallLoops"]) == 1 for stage in large_loop["stages"])
    assert large_loop["entryCondition"]
    assert large_loop["repeatCondition"]
    assert large_loop["exitCondition"]


def test_hierarchy_keeps_evidence_at_step_level():
    hierarchy = build_loop_hierarchy(_job())
    first_step = hierarchy["largeLoops"][0]["stages"][0]["smallLoops"][0]["steps"][0]

    assert first_step["evidence"][0]["sourceId"] == "F0001"
    assert first_step["evidence"][0]["locator"] == "00:00.000"


def test_provider_hierarchy_can_preserve_multiple_large_loops():
    job = _job()
    job["analysisHierarchy"] = {
        "largeLoops": [
            {"id": "LOOP-001", "title": "养成循环", "stages": []},
            {"id": "LOOP-002", "title": "战斗循环", "stages": []},
        ]
    }

    hierarchy = build_loop_hierarchy(job)

    assert [item["title"] for item in hierarchy["largeLoops"]] == ["养成循环", "战斗循环"]


def test_validation_requires_closed_small_loops_and_evidence():
    hierarchy = build_loop_hierarchy(_job())
    hierarchy["largeLoops"][0]["stages"][0]["smallLoops"][0]["exitCondition"] = ""

    errors = validate_loop_hierarchy(hierarchy)

    assert any("exitCondition" in error for error in errors)


def test_quality_gate_blocks_low_confidence_flat_output():
    hierarchy = build_loop_hierarchy(_job())
    report = loop_quality_gate(hierarchy, {"score": 0, "uncertaintyRatio": 0.9209})

    assert report["status"] == "draft"
    assert report["publishable"] is False
    assert "quality-score" in report["failedChecks"]
    assert "uncertainty" in report["failedChecks"]


def test_confirmed_review_hierarchy_uses_planner_facing_step_names_only():
    job = _job()
    job["reviewModel"] = {
        "stages": [{
            "id": "STG-001", "order": 1, "name": "选择升级内容", "objective": "完成一次升级",
            "entryCondition": "升级选项出现", "exitCondition": "返回战斗",
            "representativeFrames": [
                {"frameId": "F0001", "role": "entry"},
                {"frameId": "F0002", "role": "change"},
                {"frameId": "F0003", "role": "result"},
            ],
            "smallLoop": {"display": "升级选择", "trigger": "选择一个选项", "feedback": "显示选中反馈", "result": "能力生效", "retry": "再次升级时重复"},
            "confirmation": {"confirmed": True},
        }]
    }

    hierarchy = build_loop_hierarchy(job)
    loop = hierarchy["largeLoops"][0]
    steps = loop["stages"][0]["smallLoops"][0]["steps"]

    assert loop["title"] == "玩家操作流程"
    assert [step["title"] for step in steps] == ["操作前", "变化过程", "操作后"]
    visible_titles = [loop["title"], *[step["title"] for step in steps]]
    assert not any(word in " ".join(visible_titles).lower() for word in ("entry", "change", "result", "confirmed interaction loop"))
