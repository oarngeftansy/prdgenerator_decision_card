import pytest

from backend import analysis_service


def test_visual_requests_use_bounded_retry_policy(monkeypatch):
    captured = {}

    class FakeOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(analysis_service, "OpenAI", FakeOpenAI)

    assert analysis_service._client({"apiBase": "https://example.com/v1", "apiKey": "key"}) is not None
    assert captured["timeout"] == 90
    assert captured["max_retries"] == 2
    assert analysis_service.DETAIL_BATCH_SIZE == 6


def test_qwen36_visual_requests_disable_thinking(tmp_path):
    captured = {}
    image = tmp_path / "frame.jpg"
    image.write_bytes(b"image")

    class Completions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return type("Response", (), {
                "choices": [type("Choice", (), {
                    "message": type("Message", (), {"content": "{}"})()
                })()]
            })()

    client = type("Client", (), {
        "chat": type("Chat", (), {"completions": Completions()})()
    })()

    analysis_service._call(client, "qwen3.6-plus", "prompt", [("frame", image)])

    assert captured["extra_body"] == {"enable_thinking": False}
    assert captured["temperature"] == 0


def test_interaction_analysis_details_one_representative_frame_per_scene(tmp_path, monkeypatch):
    calls = []

    def fake_call(_client, _model, prompt, images, max_tokens=3000):
        calls.append([label for label, _path in images])
        if any(label.startswith("scene=") for label, _path in images):
            return {"scenes": [
                {"sceneId": 0, "summary": "场景一", "evidenceLevel": "明确展示", "confidence": "高"},
                {"sceneId": 1, "summary": "场景二", "evidenceLevel": "明确展示", "confidence": "高"},
            ]}
        return {"frames": [
            {
                "id": label.split()[0].removeprefix("frame="),
                "what": "代表帧界面",
                "userAction": "用户点击",
                "systemResponse": "页面响应",
                "afterState": "进入下一状态",
                "evidenceLevel": "明确展示",
                "confidence": "高",
            }
            for label, _path in images
        ]}

    monkeypatch.setattr(analysis_service, "_client", lambda _config: object())
    monkeypatch.setattr(analysis_service, "_call", fake_call)
    (tmp_path / "frames").mkdir()
    frames = [
        {"id": "F1", "timestamp": 0, "sceneId": 0, "imageUrl": "/frames/F1.jpg", "structure": {"regionCounts": {}}},
        {"id": "F2", "timestamp": 1, "sceneId": 0, "imageUrl": "/frames/F2.jpg", "structure": {"regionCounts": {}}},
        {"id": "F3", "timestamp": 2, "sceneId": 0, "imageUrl": "/frames/F3.jpg", "structure": {"regionCounts": {}}},
        {"id": "F4", "timestamp": 3, "sceneId": 1, "imageUrl": "/frames/F4.jpg", "structure": {"regionCounts": {}}},
        {"id": "F5", "timestamp": 4, "sceneId": 1, "imageUrl": "/frames/F5.jpg", "structure": {"regionCounts": {}}},
    ]
    scenes = [
        {"id": 0, "frameIds": ["F1", "F2", "F3"]},
        {"id": 1, "frameIds": ["F4", "F5"]},
    ]

    analyzed_frames, _scenes, summary = analysis_service.analyze_video(
        tmp_path, frames, scenes, {"model": "vision-model"}, "interaction", lambda *_args: None
    )

    assert summary["detailFrameCount"] == 2
    assert summary["estimatedModelCalls"] == 1
    assert summary["estimatedImageInputs"] == 2
    assert [frame["id"] for frame in analyzed_frames if frame["analysis"].get("isDetailFrame")] == ["F2", "F5"]
    assert not any(label.startswith("scene=") for call in calls for label in call)
    assert calls[-1] == ["frame=F2 time=1 scene=0", "frame=F5 time=4 scene=1"]


@pytest.mark.parametrize("frame_count", [6, 7])
def test_image_sequence_analysis_runs_single_screenshot_requests(
    tmp_path, monkeypatch, frame_count
):
    calls = []

    def fake_call(_client, _model, _prompt, images, max_tokens=3000):
        labels = [label for label, _path in images]
        calls.append(labels)
        return {"frames": [{
            "id": label.split()[0].removeprefix("frame="),
            "what": "页面", "userAction": "待确认", "systemResponse": "变化", "afterState": "下一页",
            "evidenceLevel": "合理推断", "confidence": "中",
        } for label in labels]}

    monkeypatch.setattr(analysis_service, "_client", lambda _config: object())
    monkeypatch.setattr(analysis_service, "_call", fake_call)
    (tmp_path / "frames").mkdir()
    frames = [{
        "id": f"F{index:04d}", "timestamp": index - 1, "sequenceIndex": index,
        "sceneId": index - 1, "imageUrl": f"/frames/F{index:04d}.jpg",
        "structure": {"regionCounts": {}},
    } for index in range(1, frame_count + 1)]
    scenes = [{"id": index, "frameIds": [frame["id"]]} for index, frame in enumerate(frames)]

    _frames, _scenes, summary = analysis_service.analyze_video(
        tmp_path, frames, scenes, {"model": "vision-model"}, "interaction", lambda *_args: None,
        input_type="image_sequence",
    )

    assert len(calls) == frame_count
    assert all(len(call) == 1 for call in calls)
    assert {call[0].split()[0] for call in calls} == {f"frame=F{index:04d}" for index in range(1, frame_count + 1)}
    assert summary["detailFrameCount"] == frame_count


def test_image_sequence_avoids_timeout_prone_large_visual_batches(tmp_path, monkeypatch):
    call_sizes = []

    def fake_call(_client, _model, _prompt, images, max_tokens=3000):
        call_sizes.append(len(images))
        if len(images) > 1:
            raise TimeoutError("large batch timed out")
        return {"frames": [{
            "id": label.split()[0].removeprefix("frame="),
            "what": "页面", "userAction": "点击", "systemResponse": "响应", "afterState": "下一状态",
        } for label, _path in images]}

    monkeypatch.setattr(analysis_service, "_client", lambda _config: object())
    monkeypatch.setattr(analysis_service, "_call", fake_call)
    (tmp_path / "frames").mkdir()
    frames = [{
        "id": f"F{index:04d}", "timestamp": index - 1, "sequenceIndex": index,
        "sceneId": index - 1, "imageUrl": f"/frames/F{index:04d}.jpg", "structure": {"regionCounts": {}},
    } for index in range(1, 7)]
    scenes = [{"id": index, "frameIds": [frame["id"]]} for index, frame in enumerate(frames)]

    analyzed, _scenes, summary = analysis_service.analyze_video(
        tmp_path, frames, scenes, {"model": "vision-model"}, "interaction", lambda *_args: None,
        input_type="image_sequence",
    )

    assert call_sizes == [1] * 6
    assert summary["qualifiedDetailFrameCount"] == 6
    assert summary["estimatedModelCalls"] == 6
    assert all(frame["analysis"].get("what") == "页面" for frame in analyzed)


def test_retry_only_requests_unqualified_screenshots_and_reports_partial_quality(tmp_path, monkeypatch):
    calls = []

    def fake_call(_client, _model, _prompt, images, max_tokens=3000):
        calls.extend(label.split()[0].removeprefix("frame=") for label, _path in images)
        return {"frames": [{
            "id": label.split()[0].removeprefix("frame="),
            "what": "page", "userAction": "click", "systemResponse": "update", "afterState": "next",
        } for label, _path in images]}

    monkeypatch.setattr(analysis_service, "_client", lambda _config: object())
    monkeypatch.setattr(analysis_service, "_call", fake_call)
    (tmp_path / "frames").mkdir()
    qualified = {"what": "existing", "userAction": "click", "systemResponse": "update", "afterState": "next"}
    frames = [
        {"id": "F0001", "timestamp": 0, "sceneId": 0, "imageUrl": "/frames/F0001.jpg", "structure": {"regionCounts": {}}, "analysis": qualified.copy()},
        {"id": "F0002", "timestamp": 1, "sceneId": 1, "imageUrl": "/frames/F0002.jpg", "structure": {"regionCounts": {}}, "analysis": {"what": "partial"}},
    ]
    scenes = [{"id": 0, "frameIds": ["F0001"]}, {"id": 1, "frameIds": ["F0002"]}]

    analyzed, _scenes, summary = analysis_service.analyze_video(
        tmp_path, frames, scenes, {"model": "vision-model"}, "interaction", lambda *_args: None,
        input_type="image_sequence",
    )

    assert calls == ["F0002"]
    assert analyzed[0]["analysis"]["what"] == "existing"
    assert summary["qualifiedDetailFrameCount"] == 2
    assert summary["requiredQualifiedDetailFrameCount"] == 2
    assert summary["qualityQualified"] is True


def test_partial_analysis_checkpoint_is_not_treated_as_fully_reusable():
    from backend import server

    job = {
        "checkpoint": "analysis-complete",
        "analysisSummary": {
            "modelEnabled": True,
            "qualifiedDetailFrameCount": 11,
            "detailFrameCount": 18,
            "qualityQualified": False,
        },
        "frames": [{"analysis": {"what": "saved result"}}],
    }

    assert server._has_reusable_analysis(job) is False


def test_static_screenshot_can_qualify_from_visible_evidence_without_invented_causality():
    assert analysis_service._analysis_is_qualified({
        "what": "武器详情页",
        "components": ["武器图标", "伤害数值", "升级按钮"],
        "userAction": "未知待确认",
        "systemResponse": "未知待确认",
        "afterState": "未知待确认",
    }, "image_sequence") is True
    assert analysis_service._analysis_is_qualified({
        "what": "武器详情页",
        "unknowns": ["请求超时"],
    }, "image_sequence") is False
    assert analysis_service._analysis_request_failed({"unknowns": ["逐帧请求失败：Connection error."]}) is True


def test_static_screenshot_wording_is_not_stored_as_a_player_action():
    assert hasattr(analysis_service, "_normalize_player_action_evidence")
    analysis = {
        "userAction": "未知待确认（当前帧为静态展示，未捕捉到点击或滑动操作）",
        "unknowns": [],
    }
    analysis_service._normalize_player_action_evidence(analysis)
    assert analysis["userAction"] == "未知待确认"
    assert analysis["unknowns"] == ["当前截图无法单独确认玩家操作，需结合相邻画面或视频证据。"]


def test_single_screenshot_retries_once_when_model_returns_malformed_json(tmp_path, monkeypatch):
    calls = []

    def fake_call(_client, _model, prompt, images, max_tokens=3000):
        calls.append(prompt)
        if len(calls) == 1:
            raise analysis_service.json.JSONDecodeError("missing comma", "{}", 1)
        return {"frames": [{
            "id": "F0007", "what": "升级选择页面", "userAction": "点选一项强化",
            "systemResponse": "应用所选强化", "afterState": "返回战斗",
        }]}

    monkeypatch.setattr(analysis_service, "_client", lambda _config: object())
    monkeypatch.setattr(analysis_service, "_call", fake_call)
    (tmp_path / "frames").mkdir()
    frames = [{
        "id": "F0007", "timestamp": 6, "sequenceIndex": 7, "sceneId": 6,
        "imageUrl": "/frames/F0007.jpg", "structure": {"regionCounts": {}},
    }]
    scenes = [{"id": 6, "frameIds": ["F0007"]}]

    analyzed, _scenes, summary = analysis_service.analyze_video(
        tmp_path, frames, scenes, {"model": "vision-model"}, "interaction", lambda *_args: None,
        input_type="image_sequence",
    )

    assert len(calls) == 2
    assert "JSON" in calls[1]
    assert analyzed[0]["analysis"]["what"] == "升级选择页面"
    assert summary["qualifiedDetailFrameCount"] == 1


def test_uploaded_frame_can_be_reanalyzed_without_a_source_video(tmp_path, monkeypatch):
    calls = []
    (tmp_path / "frames").mkdir()
    (tmp_path / "frames" / "F0007.jpg").write_bytes(b"image")
    frame = {"id": "F0007", "sceneId": 0, "imageUrl": "/artifacts/job/frames/F0007.jpg"}
    scene = {"id": 0, "analysis": {"summary": "升级选择"}}

    monkeypatch.setattr(analysis_service, "_client", lambda _config: object())
    monkeypatch.setattr(analysis_service, "_call", lambda _client, _model, prompt, images, max_tokens=3000: calls.append((prompt, images)) or {
        "id": "wrong", "what": "升级选择页面", "userAction": "点击一项强化",
        "systemResponse": "应用强化", "afterState": "返回战斗",
    })

    result = analysis_service.analyze_image_frame(tmp_path, frame, scene, {"model": "vision-model"}, "interaction")

    assert result["id"] == "F0007"
    assert calls[0][1][0][1].name == "F0007.jpg"
    assert not list(tmp_path.glob("source.*"))


def test_low_quality_screenshot_uses_bounded_auxiliary_video_context(tmp_path, monkeypatch):
    (tmp_path / "frames").mkdir()
    video = tmp_path / "auxiliary.mp4"
    video.write_bytes(b"video")
    frames = [{"id": "F0001", "timestamp": 0, "sceneId": 0, "imageUrl": "/frames/F0001.jpg", "structure": {"regionCounts": {}}}]
    scenes = [{"id": 0, "frameIds": ["F0001"]}]
    monkeypatch.setattr(analysis_service, "_client", lambda _config: object())
    monkeypatch.setattr(analysis_service, "_call", lambda *_args, **_kwargs: {"frames": [{"id": "F0001", "what": "抽奖页"}]})
    calls = []

    def context(**kwargs):
        calls.append(kwargs)
        return {"status": "completed", "facts": {"trigger": "点击抽奖", "process": "转盘播放", "result": "弹出奖励"}, "evidenceTimestamps": [1.0, 2.0]}

    monkeypatch.setattr("backend.auxiliary_video.analyze_context_window", context)
    analyzed, _scenes, summary = analysis_service.analyze_video(
        tmp_path, frames, scenes, {"model": "vision-model"}, "interaction", lambda *_args: None,
        input_type="image_sequence", auxiliary_video_path=video,
    )

    assert calls[0]["anchor_frame_id"] == "F0001"
    assert analyzed[0]["analysis"]["userAction"] == "点击抽奖"
    assert analyzed[0]["analysis"]["systemResponse"] == "转盘播放"
    assert analyzed[0]["analysis"]["afterState"] == "弹出奖励"
    assert summary["auxiliaryContextFrames"] == 1
