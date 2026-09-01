from scripts.repair_current_workbench_from_accepted_source import (
    ACCEPTED_DIRECTORY_TITLES,
    repair_payload,
)


def test_repair_replaces_stale_gameplay_model_without_touching_ue_review() -> None:
    target = {
        "id": "target",
        "metadata": {"projectName": "移动端交互与玩法策划案"},
        "reviewModel": {"stages": [{"id": "UE-KEEP"}]},
        "gameplayReviewModel": {
            "revision": 122,
            "directory": {
                "entries": [{"title": "载具移动机制"}, {"title": "Roguelike成长系统"}],
            },
        },
    }
    source = {
        "id": "accepted-source",
        "gameplayReviewModel": {
            "revision": 369,
            "directory": {"entries": [{"title": title} for title in ACCEPTED_DIRECTORY_TITLES]},
            "systems": [{"name": "核心战斗"}, {"name": "局内成长"}, {"name": "关卡推进"}],
        },
    }

    repaired = repair_payload(target, source)

    assert repaired["reviewModel"] == target["reviewModel"]
    assert repaired["gameplayReviewModel"] == source["gameplayReviewModel"]
    assert [
        item["title"] for item in repaired["gameplayReviewModel"]["directory"]["entries"]
    ] == ACCEPTED_DIRECTORY_TITLES
    assert repaired["metadata"]["projectName"] == "一路狂飙交互与玩法策划案"
    assert repaired["workbenchRepair"]["sourceJobId"] == "accepted-source"


def test_repair_refuses_an_unreviewed_source_directory() -> None:
    target = {"gameplayReviewModel": {"directory": {"entries": []}}}
    source = {"gameplayReviewModel": {"directory": {"entries": [{"title": "旧目录"}]}}}

    try:
        repair_payload(target, source)
    except ValueError as exc:
        assert "directory drifted" in str(exc)
    else:
        raise AssertionError("repair must reject a source that no longer matches the accepted directory")
