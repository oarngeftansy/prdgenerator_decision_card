from backend.planning_gameplay_sync import planning_gameplay_sync_report, sync_planning_gameplay_insights


def _job():
    return {
        "reviewModel": {"stages": [{
            "id": "STG-001", "name": "选择强化", "confirmation": {"confirmed": True},
            "gameplayInsights": [{
                "id": "PGI-001", "text": "强化卡片展示武器名称、等级和本次变化的属性。",
                "targetChapterId": "GCH-001", "carrier": "keyRules", "sourceFrameIds": ["F0001"],
            }],
        }]},
        "gameplayReviewModel": {"chapters": [{
            "id": "GCH-001", "scope": "局内升级与强化", "plannerSections": {
                "summary": "玩家选择一项强化。", "normalFlow": [], "keyRules": [], "specialCases": [],
            },
        }]},
    }


def test_confirmed_planning_insight_is_copied_to_its_gameplay_carrier_with_traceability():
    job = _job()

    model = sync_planning_gameplay_insights(job, job["gameplayReviewModel"])

    assert model["chapters"][0]["plannerSections"]["keyRules"] == [
        "强化卡片展示武器名称、等级和本次变化的属性。"
    ]
    assert model["planningGameplayTrace"] == [{
        "insightId": "PGI-001", "stageId": "STG-001", "stageName": "选择强化",
        "targetChapterId": "GCH-001", "carrier": "keyRules",
        "text": "强化卡片展示武器名称、等级和本次变化的属性。",
        "sourceFrameIds": ["F0001"], "status": "delivered",
    }]
    assert planning_gameplay_sync_report(job, model)["passed"]


def test_missing_target_or_missing_published_copy_blocks_delivery_with_improvement_path():
    job = _job()
    job["reviewModel"]["stages"][0]["gameplayInsights"].append({
        "id": "PGI-002", "text": "结算页展示各武器伤害占比。",
        "targetChapterId": "GCH-404", "carrier": "keyRules", "sourceFrameIds": ["F0015"],
    })

    model = sync_planning_gameplay_insights(job, job["gameplayReviewModel"])
    report = planning_gameplay_sync_report(job, model)

    assert not report["passed"]
    assert report["deliveredCount"] == 1
    assert report["missingCount"] == 1
    assert report["findings"][0]["insightId"] == "PGI-002"
    assert report["findings"][0]["improvementPath"]


def test_ui_only_board_note_does_not_get_duplicated_into_gameplay_prose():
    job = _job()
    job["reviewModel"]["stages"][0]["gameplayInsights"] = [{
        "id": "PGI-003", "text": "按钮位于页面右下角。", "gameplayRelevant": False,
        "reason": "仅描述页面空间布局", "sourceFrameIds": ["F0001"],
    }]

    model = sync_planning_gameplay_insights(job, job["gameplayReviewModel"])

    assert model["chapters"][0]["plannerSections"]["keyRules"] == []
    assert model["planningGameplayTrace"][0]["status"] == "board_only"
    assert planning_gameplay_sync_report(job, model)["passed"]


def test_confirmed_weapon_board_fact_is_copied_into_weapon_attribute_prose():
    job = _job()
    job["reviewModel"]["stages"][0]["gameplayInsights"] = [{
        "id": "PGI-004", "text": "迅猛喷射：本次画面显示火焰喷射器伤害频率提高 20%。",
        "targetChapterId": "GCH-001", "carrier": "attributeSections",
        "attributeHeading": "局内强化作用", "sourceFrameIds": ["F0001"],
    }]

    model = sync_planning_gameplay_insights(job, job["gameplayReviewModel"])

    assert model["chapters"][0]["plannerSections"]["attributeSections"] == [{
        "heading": "局内强化作用",
        "items": ["迅猛喷射：本次画面显示火焰喷射器伤害频率提高 20%。"],
    }]
    assert planning_gameplay_sync_report(job, model)["passed"]


def test_attribute_insight_without_business_heading_blocks_delivery():
    job = _job()
    job["reviewModel"]["stages"][0]["gameplayInsights"] = [{
        "id": "PGI-005", "text": "火焰扩张：范围扩大 30%。",
        "targetChapterId": "GCH-001", "carrier": "attributeSections", "sourceFrameIds": ["F0001"],
    }]

    report = planning_gameplay_sync_report(
        job, sync_planning_gameplay_insights(job, job["gameplayReviewModel"])
    )

    assert not report["passed"]
    assert report["findings"][0]["improvementPath"]
