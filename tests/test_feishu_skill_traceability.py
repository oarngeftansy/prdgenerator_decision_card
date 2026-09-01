import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_every_distilled_technique_reaches_skill_project_test_and_delivery():
    matrix = json.loads((ROOT / "data/calibration/gve16/skill-traceability.json").read_text(encoding="utf-8"))

    assert len(matrix["techniques"]) >= 18
    for item in matrix["techniques"]:
        assert item["sourceBlockIds"], item["id"]
        assert item["contentLogic"], item["id"]
        assert item["languageLogic"], item["id"]
        assert item["skillRule"], item["id"]
        assert item["projectLocations"], item["id"]
        assert item["testIds"], item["id"]
        assert item["deliveryEffect"] in {"generation", "P7", "feishu", "P7_and_feishu"}, item["id"]
        assert item["status"] == "implemented", item["id"]


def test_traceability_has_no_revoked_source_or_orphan_project_gate():
    matrix = json.loads((ROOT / "data/calibration/gve16/skill-traceability.json").read_text(encoding="utf-8"))
    encoded = json.dumps(matrix, ensure_ascii=False)

    assert "GVE5矿坑" not in encoded
    assert "迷雾事件池" not in encoded
    assert matrix["coverage"]["sourceToSkill"] == 1.0
    assert matrix["coverage"]["skillToProject"] == 1.0
    assert matrix["coverage"]["projectToTest"] == 1.0
    assert matrix["coverage"]["deliveryCoverage"] == 1.0
