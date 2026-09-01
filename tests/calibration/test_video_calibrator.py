from backend.calibration.video_calibrator import validate_video_calibration


def test_rejects_core_event_without_complete_chain():
    result = validate_video_calibration({
        "duration": 600,
        "sampledUntil": 600,
        "events": [{"importance": "core", "beforeState": "主页", "action": "点击开始"}],
    })
    assert "core event missing systemResponse and afterState" in result


def test_rejects_incomplete_duration_coverage():
    result = validate_video_calibration({"duration": 600, "sampledUntil": 580, "events": []})
    assert "video duration is not fully covered" in result

