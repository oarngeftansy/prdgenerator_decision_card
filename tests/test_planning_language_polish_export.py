import importlib.util
import json

import scripts.polish_yilu_final_delivery_v3 as exporter


def test_v3_export_module_exists_without_touching_rule_pipeline():
    assert importlib.util.find_spec("scripts.polish_yilu_final_delivery_v3") is not None


def test_v3_export_preserves_projection_and_feedback_trace_bytes_and_writes_text_diff(tmp_path):
    source = tmp_path / "v2"
    output = tmp_path / "v3"
    source.mkdir()
    document = {
        "title": "执行案 v2", "status": "reference_preview_with_open_gaps",
        "systems": [{"title": "成长", "objects": [{"title": "选择", "chapters": [{
            "chapterId": "C1", "title": "选择", "foldIntoObject": True,
            "groups": [{"title": "机制流程", "sentences": [{
                "text": "玩家点击刷新按钮，随后选择流程刷新后替换当前三项候选。",
                "sourceRuleIds": ["R1"], "sourceFactIds": ["F1"], "evidenceIds": ["E1"],
            }]}],
            "reviewedGaps": [{"gapId": "G1", "question": "速度变化的触发条件待确认。"}],
        }]}]}],
    }
    projection_bytes = b'{"rules":[{"ruleId":"R1"}],"facts":[{"factId":"F1"}]}'
    trace = {
        "schemaVersion": "feedback-trace-v1",
        "records": [{
            "feedbackId": f"PF-{index:02d}", "verificationStatus": "fully_reflected",
            "lastVerifiedRevision": 1, "affected": {},
        } for index in range(1, 13)],
    }
    (source / "result-a-final.json").write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    (source / "result-a-final.md").write_text("# 执行案 v2\n\n- 玩家点击刷新按钮，随后选择流程刷新后替换当前三项候选。\n", encoding="utf-8")
    (source / "mechanic-reconstruction-projection.json").write_bytes(projection_bytes)
    (source / "feedback-trace.json").write_text(json.dumps(trace, ensure_ascii=False), encoding="utf-8")

    audit = exporter.build_v3_artifacts(source, output, delivery_title="执行案 v3 / Planner Review Ready")

    assert (output / "mechanic-reconstruction-projection.json").read_bytes() == projection_bytes
    assert (output / "feedback-trace.json").read_bytes() == (source / "feedback-trace.json").read_bytes()
    assert audit["projectionHashBefore"] == audit["projectionHashAfter"]
    assert audit["feedbackTraceHashBefore"] == audit["feedbackTraceHashAfter"]
    assert audit["feedbackCoverage"] == {"fully_reflected": 12, "partially_reflected": 0, "regressed": 0}
    assert audit["documentStructureUnchanged"] is True
    diff = (output / "v2-to-v3.diff").read_text(encoding="utf-8")
    assert "-# 执行案 v2" in diff
    assert "+# 执行案 v3 / Planner Review Ready" in diff
    assert "随后选择流程刷新后" in diff
    assert "点击刷新按钮后，替换当前三项候选" in diff
    assert not any(line.endswith(" \n") for line in diff.splitlines(keepends=True))
