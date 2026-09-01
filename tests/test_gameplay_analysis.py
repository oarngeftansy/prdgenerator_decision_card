from copy import deepcopy

import pytest

from tests.review_fixtures import make_image_job


def _job(frame_count=2):
    job = deepcopy(make_image_job())
    job["metadata"]["mode"] = "gameplay"
    frames = []
    for index in range(1, frame_count + 1):
        frame = deepcopy(job["frames"][(index - 1) % len(job["frames"])])
        frame.update(id=f"F{index:04d}", imageUrl=f"/artifacts/{job['id']}/frames/F{index:04d}.jpg")
        frames.append(frame)
    job["frames"] = frames
    return job


def _draft(frame_ids, title="Gem drag", mechanism_type="spatial_drag", source_type="material"):
    return {
        "title": title,
        "mechanismType": mechanism_type,
        "sourceFrameIds": frame_ids,
        "claims": [{
            "text": "Player drags the gem into its matching slot.",
            "sourceType": source_type,
            "sourceFrameIds": frame_ids,
        }],
        "mechanism": {"type": mechanism_type},
        "parameters": {},
        "dependencies": [],
        "acceptanceCases": [],
        "unknowns": [],
        "confidence": "high",
    }


def _configure(monkeypatch, response):
    from backend import gameplay_analysis

    monkeypatch.setattr(gameplay_analysis, "_client", lambda config: object())
    monkeypatch.setattr(gameplay_analysis, "_call", lambda *args, **kwargs: response)


def test_prompt_lists_every_supported_internal_mechanism_type():
    from backend.gameplay_analysis import _prompt
    from backend.gameplay_review_model import MECHANISM_SCHEMAS

    prompt = _prompt(["F0001"])

    for mechanism_type in MECHANISM_SCHEMAS:
        assert mechanism_type in prompt


def test_structure_generation_does_not_inject_absent_systems_and_accepts_new_gameplay(tmp_path, monkeypatch):
    from backend import gameplay_analysis

    job = _job(1)
    monkeypatch.setattr(gameplay_analysis, "_client", lambda config: object())
    monkeypatch.setattr(gameplay_analysis, "_call", lambda *args, **kwargs: {
        "systems": [{
            "name": "光路编织",
            "reason": "玩家连接画面中的光点",
            "subsystems": [{"name": "连接规则", "mechanisms": [{
                "name": "光点连线", "reason": "拖动后形成连续光路", "sourceFrameIds": ["F0001"],
            }]}],
        }],
    })

    model = gameplay_analysis.generate_gameplay_structure(job, tmp_path, {"model": "vision"})
    rendered = str(model["systems"])

    assert "光路编织" in rendered
    assert model["chapters"][0]["scope"] == "光点连线"
    assert "武器" not in rendered
    assert "敌人" not in rendered
    assert model["chapters"][0]["mechanism"]["type"] == "custom"
    assert model["reviewState"]["status"] == "system_directory_review"


@pytest.mark.parametrize("bad_name", ["收购信息面板", "对战匹配显示", "阵容配置界面", "地块触发提示"])
def test_structure_validator_rejects_page_and_interface_titles_as_gameplay_mechanisms(bad_name):
    from backend.gameplay_analysis import GameplayAnalysisQualityError, _validate_structure_response

    value = {"systems": [{"name": "城市收购", "subsystems": [{"name": "收购规则", "mechanisms": [
        {"name": bad_name, "reason": "截图中出现对应页面", "sourceFrameIds": ["F0001"]},
    ]}]}]}

    with pytest.raises(GameplayAnalysisQualityError, match="interface title"):
        _validate_structure_response(value, {"F0001"})


def test_structure_validator_rejects_duplicate_and_overloaded_directory_shapes():
    from backend.gameplay_analysis import GameplayAnalysisQualityError, _validate_structure_response

    duplicated = {"systems": [{"name": "城市收购", "subsystems": [{"name": "收购规则", "mechanisms": [
        {"name": "建筑收购", "reason": "选择建筑", "sourceFrameIds": ["F0001"]},
        {"name": "建筑收购", "reason": "再次选择建筑", "sourceFrameIds": ["F0002"]},
    ]}]}]}
    with pytest.raises(GameplayAnalysisQualityError, match="duplicate mechanism"):
        _validate_structure_response(duplicated, {"F0001", "F0002"})

    overloaded = {"systems": [{"name": "城市收购", "subsystems": [{"name": "全部规则", "mechanisms": [
        {"name": f"收购机制{index}", "reason": "收购规则", "sourceFrameIds": ["F0001"]}
        for index in range(1, 11)
    ]}]}]}
    with pytest.raises(GameplayAnalysisQualityError, match="overloaded subsystem"):
        _validate_structure_response(overloaded, {"F0001"})


def test_structure_validator_requires_distinct_system_subsystem_and_mechanism_titles():
    from backend.gameplay_analysis import GameplayAnalysisQualityError, _validate_structure_response

    value = {"systems": [{"name": "城市收购", "subsystems": [{"name": "城市收购", "mechanisms": [
        {"name": "城市收购", "reason": "选择并收购建筑", "sourceFrameIds": ["F0001"]},
    ]}]}]}

    with pytest.raises(GameplayAnalysisQualityError, match="hierarchy titles must be distinct"):
        _validate_structure_response(value, {"F0001"})


def test_detail_generation_preserves_confirmed_structure_and_enriches_rules(tmp_path, monkeypatch):
    from backend import gameplay_analysis

    job = _job(1)
    structure_response = {
        "systems": [{
            "name": "光路编织",
            "reason": "玩家连接画面中的光点",
            "subsystems": [{"name": "连接规则", "mechanisms": [{
                "name": "光点连线", "reason": "拖动后形成连续光路", "sourceFrameIds": ["F0001"],
            }]}],
        }],
    }
    detail_response = [{
        "title": "模型擅自改名",
        "mechanismType": "custom",
        "sourceFrameIds": ["F0001"],
        "claims": [{"text": "拖动光点形成连接", "sourceType": "material", "sourceFrameIds": ["F0001"]}],
        "mechanism": {
            "type": "custom", "goal": "连接全部目标光点", "inputs": "手指拖动",
            "stateChanges": "未连接变为已连接", "rules": "相邻光点按路径顺序连接",
        },
        "parameters": {"连接距离": {"value": "画面可见范围", "type": "text", "unit": "像素", "range": "待策划确认", "source": "F0001"}},
        "dependencies": [],
        "acceptanceCases": [{"scene": "正常连接", "action": "拖到相邻光点", "expected": "连接生效并保留路径"}],
        "formulae": [{
            "name": "连接距离判断",
            "expression": "可连接 = 距离 ≤ 连接上限",
            "calculationOrder": "读取距离与连接上限→比较→返回结果",
            "rounding": "不取整",
            "variables": [
                {"name": "距离", "evidenceLevel": "material", "sourceFrameIds": ["F0001"]},
                {"name": "连接上限", "evidenceLevel": "inference", "sourceFrameIds": ["F0001"]},
            ],
            "evidenceLevel": "inference", "sourceFrameIds": ["F0001"],
        }],
        "workedExamples": [],
        "unknowns": [],
        "confidence": "high",
    }]
    responses = iter([structure_response, detail_response])
    monkeypatch.setattr(gameplay_analysis, "_client", lambda config: object())
    monkeypatch.setattr(gameplay_analysis, "_call", lambda *args, **kwargs: next(responses))

    structure = gameplay_analysis.generate_gameplay_structure(job, tmp_path, {"model": "vision"})
    structure["directory"]["status"] = "confirmed"
    original_ids = [chapter["id"] for chapter in structure["chapters"]]
    detailed = gameplay_analysis.generate_gameplay_details(job, structure, tmp_path, {"model": "vision"}, lambda *_: None)

    assert [chapter["id"] for chapter in detailed["chapters"]] == original_ids
    assert detailed["chapters"][0]["scope"] == "光点连线"
    assert detailed["chapters"][0]["systemName"] == "光路编织"
    assert detailed["chapters"][0]["subsystemName"] == "连接规则"
    assert detailed["chapters"][0]["mechanism"] == {"type": "custom"}
    assert "formulae" not in detailed["chapters"][0]
    assert any("公式" in card["question"] for card in detailed["chapters"][0]["decisionCards"])
    assert any("操作" in card["question"] for card in detailed["chapters"][0]["decisionCards"])
    assert "workedExamples" not in detailed["chapters"][0]
    assert detailed["directory"]["status"] == "confirmed"
    assert detailed["reviewState"]["status"] == "chapter_review"


def test_detail_generation_resumes_from_last_validated_chapter_after_transport_failure(tmp_path, monkeypatch):
    from backend import gameplay_analysis

    job = _job(2)
    structure = {
        "revision": 7,
        "systems": [{"id": "GSY-001", "name": "经营系统"}],
        "directory": {"status": "confirmed", "understanding": {"summary": "玩家经营店铺并逐步扩展业务。"}, "entries": []},
        "reviewState": {"status": "system_directory_review"},
        "chapters": [
            {
                "id": "GCH-001", "scope": "店铺升级", "systemName": "经营系统", "subsystemName": "成长规则",
                "sourceFrameIds": ["F0001"], "mechanism": {"type": "custom"}, "confirmation": {"confirmed": False},
            },
            {
                "id": "GCH-002", "scope": "经营收益", "systemName": "经营系统", "subsystemName": "收益规则",
                "sourceFrameIds": ["F0002"], "mechanism": {"type": "custom"}, "confirmation": {"confirmed": False},
            },
        ],
    }

    def response(frame_id, title):
        return [{
            "title": title, "mechanismType": "custom", "sourceFrameIds": [frame_id],
            "claims": [{"text": f"{title}按已确认条件执行。", "sourceType": "material", "sourceFrameIds": [frame_id]}],
            "mechanism": {"type": "custom", "description": f"玩家执行{title}并获得对应结果。", "rule": f"{title}完成后更新经营状态。"},
            "parameters": {}, "dependencies": [],
            "acceptanceCases": [{"scene": "正常状态", "action": title, "expected": "经营状态更新"}],
            "unknowns": [], "decisionCards": [], "confidence": "high",
        }]

    calls = []

    def model_call(*_args, **_kwargs):
        calls.append(len(calls) + 1)
        if len(calls) == 1:
            return response("F0001", "店铺升级")
        if len(calls) == 2:
            raise RuntimeError("temporary upstream disconnect")
        return response("F0002", "经营收益")

    monkeypatch.setattr(gameplay_analysis, "_client", lambda _config: object())
    monkeypatch.setattr(gameplay_analysis, "_call", model_call)
    monkeypatch.setattr(gameplay_analysis, "validate_gameplay_review_model", lambda _model: [])
    monkeypatch.setattr(gameplay_analysis, "lead_planner_output_audit", lambda _model, _phase, **_kwargs: [])
    monkeypatch.setattr(gameplay_analysis, "_require_generation_quality", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(gameplay_analysis, "sync_planning_gameplay_insights", lambda _job, model: model)

    with pytest.raises(RuntimeError, match="temporary upstream disconnect"):
        gameplay_analysis._generate_gameplay_details_once(job, structure, tmp_path, {"model": "resume-test"})

    result = gameplay_analysis._generate_gameplay_details_once(job, structure, tmp_path, {"model": "resume-test"})

    assert calls == [1, 2, 3]
    assert [chapter["scope"] for chapter in result["chapters"]] == ["店铺升级", "经营收益"]


def test_rejects_placeholder_only_model_response(tmp_path, monkeypatch):
    from backend.gameplay_analysis import GameplayAnalysisQualityError, generate_gameplay_chapters

    job = _job()
    _configure(monkeypatch, [_draft(["F0001"], source_type="pending")])

    with pytest.raises(GameplayAnalysisQualityError, match="placeholder"):
        generate_gameplay_chapters(job, tmp_path, {"model": "vision"}, lambda *_: None)


def test_merges_multi_frame_candidates_into_one_chapter(tmp_path, monkeypatch):
    from backend.gameplay_analysis import generate_gameplay_chapters

    job = _job()
    _configure(monkeypatch, [_draft(["F0001"]), _draft(["F0002"])])

    model = generate_gameplay_chapters(job, tmp_path, {"model": "vision"}, lambda *_: None)

    assert len(model["chapters"]) == 1
    assert model["chapters"][0]["sourceFrameIds"] == ["F0001", "F0002"]
    assert len(model["chapters"][0]["claims"]) == 2


def test_limits_model_image_batches_to_three_in_user_order_and_reports_immediate_progress(tmp_path, monkeypatch):
    from backend import gameplay_analysis

    job = _job(7)
    calls = []
    token_limits = []
    progress = []
    monkeypatch.setattr(gameplay_analysis, "_client", lambda config: object())

    def call(_client, _model, _prompt, images, **_kwargs):
        frame_ids = [label.split()[0].split("=", 1)[1] for label, _path in images]
        calls.append(frame_ids)
        token_limits.append(_kwargs.get("max_tokens"))
        return [_draft(frame_ids)]

    monkeypatch.setattr(gameplay_analysis, "_call", call)

    gameplay_analysis.generate_gameplay_chapters(job, tmp_path, {"model": "vision"}, lambda value, message: progress.append((value, message)))

    assert calls == [["F0001", "F0002", "F0003"], ["F0004", "F0005", "F0006"], ["F0007"]]
    assert token_limits == [5000, 5000, 5000]
    assert progress[0][0] == 5
    assert progress[-1][0] == 100


def test_rejects_frame_ids_not_in_the_current_model_batch(tmp_path, monkeypatch):
    from backend.gameplay_analysis import GameplayAnalysisQualityError, generate_gameplay_chapters

    job = _job(7)
    _configure(monkeypatch, [_draft(["F0007"])])

    with pytest.raises(GameplayAnalysisQualityError, match="unknown frame"):
        generate_gameplay_chapters(job, tmp_path, {"model": "vision"}, lambda *_: None)


def test_rejects_unknown_frame_ids_from_model(tmp_path, monkeypatch):
    from backend.gameplay_analysis import GameplayAnalysisQualityError, generate_gameplay_chapters

    job = _job()
    _configure(monkeypatch, [_draft(["F9999"])])

    with pytest.raises(GameplayAnalysisQualityError, match="unknown frame"):
        generate_gameplay_chapters(job, tmp_path, {"model": "vision"}, lambda *_: None)


def test_invalid_mechanism_type_is_visible_in_diagnostic_error(tmp_path, monkeypatch):
    from backend.gameplay_analysis import GameplayAnalysisQualityError, generate_gameplay_chapters

    job = _job()
    _configure(monkeypatch, [_draft(["F0001"], mechanism_type="combat_system")])

    with pytest.raises(GameplayAnalysisQualityError, match="combat_system"):
        generate_gameplay_chapters(job, tmp_path, {"model": "vision"}, lambda *_: None)


def test_preserves_text_mechanism_and_parameter_list_from_model(tmp_path, monkeypatch):
    from backend.gameplay_analysis import generate_gameplay_chapters

    job = _job(1)
    draft = _draft(["F0001"])
    draft["mechanism"] = "玩家拖动宝石到对应槽位"
    draft["parameters"] = [
        {"name": "拖动次数", "value": "1", "unit": "次"},
        "错误放置后返回原位",
    ]
    _configure(monkeypatch, [draft])

    model = generate_gameplay_chapters(job, tmp_path, {"model": "vision"}, lambda *_: None)

    chapter = model["chapters"][0]
    assert chapter["mechanism"]["type"] == "spatial_drag"
    assert chapter["mechanism"]["description"] == "玩家拖动宝石到对应槽位"
    assert chapter["parameters"]["拖动次数"]["value"] == "1"
    assert chapter["parameters"]["补充说明2"]["value"] == "错误放置后返回原位"


def test_compiles_common_model_shortcuts_into_a_valid_review_model(tmp_path, monkeypatch):
    from backend.gameplay_analysis import generate_gameplay_chapters
    from backend.gameplay_review_model import validate_gameplay_review_model

    job = _job(1)
    draft = _draft(["F0001"])
    draft["mechanism"] = {"description": "拖动后进行位置判定"}
    draft["parameters"] = {"拖动次数": 1, "判定范围": {"value": "槽位内"}}
    draft["claims"] = ["玩家拖动宝石", {"text": "错误位置会返回"}]
    draft["dependencies"] = ["关卡流程", {"chapter": "奖励结算"}]
    draft["acceptanceCases"] = ["正确放置", {"case": "错误放置"}]
    draft["unknowns"] = [{"question": "是否限制拖动次数"}]
    _configure(monkeypatch, [draft])

    model = generate_gameplay_chapters(job, tmp_path, {"model": "vision"}, lambda *_: None)

    assert validate_gameplay_review_model(model) == []
    chapter = model["chapters"][0]
    assert chapter["mechanism"]["type"] == "spatial_drag"
    assert chapter["dependencies"] == []
    assert any("关卡流程" in item for item in chapter["unknowns"])
    assert all(isinstance(item, dict) for item in chapter["claims"])
    assert all(isinstance(item, dict) for item in chapter["acceptanceCases"])
    assert all(isinstance(item, dict) for item in chapter["parameters"].values())
