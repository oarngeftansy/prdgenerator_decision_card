import json
from pathlib import Path

from backend.granularity_audit import granularity_audit_report


ROOT = Path(__file__).resolve().parents[1]
CASES = {
    item["id"]: item
    for item in json.loads((ROOT / "data/calibration/gve16/provenance-reasoning-cases.json").read_text(encoding="utf-8"))["cases"]
}


def test_tc4_context_inference_is_replayable_and_publishable():
    case = CASES["S3-TC04"]
    inference = {key: case[key] for key in ("premises", "steps", "alternatives", "confidence", "publicationAllowed", "publicationReason")}
    model = {"chapters": [{
        "id": "TC04", "scope": "奖励确认跳转",
        "provenanceClaims": [{"text": case["claim"], "sourceType": case["sourceType"], "inference": inference}],
    }]}

    assert granularity_audit_report(model)["passed"]
    assert all(item["excludedBy"] for item in case["alternatives"])


def test_tc5_screenshot_boundaries_cover_hidden_calculation_responsibility_and_time():
    case = CASES["S3-TC05"]
    forbidden = "\n".join(case["forbiddenConclusions"])

    assert "概率" in forbidden and "公式" in forbidden
    assert "客户端还是服务端" in forbidden
    assert "重置" in forbidden and "跨关卡保存" in forbidden
    assert set(case["observableFacts"]).isdisjoint(case["forbiddenConclusions"])


def test_tc6_has_four_distinct_omission_reasons_with_concrete_examples():
    omissions = CASES["S3-TC06"]["omissions"]

    assert [item["type"] for item in omissions] == [
        "没有证据所以不写", "对制作无新增价值所以不写", "表格已经承载所以正文不重复", "画板已经承载所以正文不复述"
    ]
    assert all(len(item["example"]) >= 20 for item in omissions)


def test_tc7_assigns_distinct_content_to_all_four_delivery_carriers():
    carriers = CASES["S3-TC07"]["carriers"]

    assert [item["carrier"] for item in carriers] == ["策划草图", "正文", "配置表", "公式"]
    assert len({item["content"] for item in carriers}) == 4
    assert all(item["reason"] for item in carriers)
