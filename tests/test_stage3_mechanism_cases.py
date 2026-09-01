import hashlib
import json
import copy
from pathlib import Path

from backend.granularity_audit import granularity_audit_report
from backend.feishu_language_quality import language_quality_report
from backend.sample_alignment import sample_alignment_report
from backend.gameplay_rule_copy import planner_sections


ROOT = Path(__file__).resolve().parents[1]
CASES = json.loads((ROOT / "data/calibration/gve16/stage3-mechanism-cases.json").read_text(encoding="utf-8"))["cases"]


def _digest(value):
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def test_tc12_to_tc19_have_independent_inputs_and_bodies():
    assert [item["id"] for item in CASES] == [f"S3-TC{index}" for index in range(12, 20)]
    assert len({_digest(item["model"]) for item in CASES}) == 8
    bodies = [item["model"]["chapters"][0]["plannerSections"]["summary"] for item in CASES]
    assert len(set(bodies)) == 8


def test_tc12_to_tc19_use_the_real_audit_chain_and_reach_the_expected_result():
    for item in CASES:
        granularity = granularity_audit_report(item["model"])
        language = language_quality_report(item["model"])
        alignment = sample_alignment_report(item["model"])
        actual = granularity["passed"] and language["passed"] and alignment["passed"]
        assert actual is item["expectedPassed"], {
            "case": item["id"],
            "granularity": granularity["findings"],
            "language": language["findings"],
        }


def test_tc13_fails_for_specific_missing_facts_not_for_an_injected_result():
    case = next(item for item in CASES if item["id"] == "S3-TC13")
    report = granularity_audit_report(case["model"])
    messages = "\n".join(item["message"] for item in report["findings"])

    assert "排除未解锁奖励" in messages
    assert "排除本局已经出现的奖励" in messages
    assert "按来源表优先级排序" in messages
    assert "候选不足时只展示已有结果" in messages


def test_tc14_has_no_formula_configuration_or_lifecycle_copy():
    case = next(item for item in CASES if item["id"] == "S3-TC14")
    chapter = case["model"]["chapters"][0]
    serialized = json.dumps(chapter.get("plannerSections"), ensure_ascii=False)

    assert "公式" not in serialized
    assert "配置" not in serialized
    assert "生命周期" not in serialized
    rows = {row["axis"]: row for row in sample_alignment_report(case["model"])["chapters"][0]["granularity"]}
    assert rows["formula"]["status"] == "not_applicable"
    assert rows["configuration"]["status"] == "not_applicable"
    assert rows["lifecycle"]["status"] == "not_applicable"


def test_tc12_to_tc19_run_through_real_section_composition_before_v2_audit():
    for item in CASES:
        model = copy.deepcopy(item["model"])
        model["granularityAuditVersion"] = 2
        chapter = model["chapters"][0]
        source_summary = chapter.pop("plannerSections")["summary"]
        chapter.setdefault("mechanism", {})["description"] = source_summary
        chapter["plannerSections"] = planner_sections(chapter)

        report = granularity_audit_report(model)
        assert report["passed"] is item["expectedPassed"], {
            "case": item["id"],
            "sections": chapter["plannerSections"],
            "findings": report["findings"],
        }


def test_tc15_missing_required_table_column_is_blocked_with_table_remediation():
    model = copy.deepcopy(next(item for item in CASES if item["id"] == "S3-TC15")["model"])
    model["tables"][0]["rows"][0].remove("失败处理")
    model["tables"][0]["rows"][1].pop(5)

    report = granularity_audit_report(model)

    finding = next(item for item in report["findings"] if item["code"] == "GRANULARITY_CONFIGURATION_COLUMNS_MISSING")
    assert "失败处理" in finding["message"]
    assert finding["remediation"]["carrier"] == "配置表"


def test_tc16_reordered_algorithm_is_blocked_and_tells_where_to_reorder():
    model = copy.deepcopy(next(item for item in CASES if item["id"] == "S3-TC16")["model"])
    model["chapters"][0]["executionSequence"] = list(reversed(model["chapters"][0]["executionSequence"]))

    report = granularity_audit_report(model)

    finding = next(item for item in report["findings"] if item["code"] == "GRANULARITY_EXECUTIONSEQUENCE_ORDER_INVALID")
    assert "来源顺序" in finding["message"]
    assert finding["remediation"]["action"]


def test_tc17_tc18_tc19_each_fail_when_their_decisive_fact_is_removed():
    removals = {
        "S3-TC17": ("formulae", "example"),
        "S3-TC18": ("lifecycle", "异常退出不清空本局余额"),
        "S3-TC19": ("boundaryRules", "资源不足时不扣除资源"),
    }
    for case_id, (field, removed) in removals.items():
        model = copy.deepcopy(next(item for item in CASES if item["id"] == case_id)["model"])
        chapter = model["chapters"][0]
        if field == "formulae":
            chapter[field][0].pop(removed)
        else:
            chapter[field].remove(removed)
        report = granularity_audit_report(model)
        assert not report["passed"], case_id
        assert all(item.get("remediation") for item in report["findings"])
