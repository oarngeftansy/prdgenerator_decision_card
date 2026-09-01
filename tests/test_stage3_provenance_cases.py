import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROVENANCE = json.loads((ROOT / "data/calibration/gve16/sentence-provenance.json").read_text(encoding="utf-8"))


def test_tc1_coverage_spans_both_samples_and_all_nine_information_dimensions():
    coverage = (ROOT / "docs/research/feishu-sample-chapter-coverage-2026-08-11.md").read_text(encoding="utf-8")
    maze_section, gve_section = coverage.split("## GVE16 revision 47")

    assert maze_section.count("| ") >= 8
    assert gve_section.count("| ") >= 8
    for label in ("玩家目标和胜负", "页面/交互反馈", "内容清单", "执行时序", "制作职责", "配置结构", "公式与展示", "边界与失败回退", "保存与重置"):
        assert label in coverage


def test_tc2_selected_sentences_are_complete_chinese_planner_readable_records():
    records = {item["id"]: item for item in PROVENANCE["records"]}
    selected = [records[item_id] for item_id in PROVENANCE["tc2SelectedIds"]]

    assert len(selected) == 10
    assert {item["id"].split("-")[0] for item in selected} == {"MZ", "G16"}
    for item in selected:
        assert item["blockIds"]
        for field in ("sourceText", "contentRole", "languageLogic", "omissionLogic"):
            assert re.search(r"[\u4e00-\u9fff]", item[field]), (item["id"], field)
            assert not re.search(r"\b(?:first|then|result|source|configuration|formula|rule)\b", item[field], re.I)


def test_tc3_source_categories_have_chinese_labels_and_do_not_merge_inference_with_fact():
    labels = PROVENANCE["sourceTypeLabels"]

    assert labels["screenshot_fact"] == "截图直接事实"
    assert labels["video_sequence"] == "视频时序事实"
    assert labels["reference_document"] == "参考文档事实"
    assert labels["context_inference"] == "上下文推断"
    assert len(set(labels.values())) == len(labels)


def test_tc8_revoked_sample_content_is_explicitly_quarantined():
    revoked = PROVENANCE["revokedAttributions"]
    serialized_records = json.dumps(PROVENANCE["records"], ensure_ascii=False)

    assert {"GVE5矿坑", "组队创建与请离", "地图生成与迷雾", "固定或随机事件池"} <= set(revoked)
    for item in revoked:
        assert item not in serialized_records
