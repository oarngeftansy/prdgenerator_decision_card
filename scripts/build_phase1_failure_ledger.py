from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import xml.etree.ElementTree as ET


OBSOLETE_FEISHU = {
    "test_publisher_requires_two_distinct_whiteboard_tokens",
    "test_gameplay_publisher_preserves_pre_migration_three_board_delivery",
    "test_competitor_failure_resumes_without_rewriting_planning",
    "test_publisher_rejects_three_whiteboard_occurrences_even_with_two_unique_tokens",
    "test_publisher_maps_two_ue_boards_before_an_approved_gameplay_diagram",
    "test_board_idempotency_tokens_are_unique_and_within_feishu_limit",
}


def _classification(classname: str, name: str) -> dict[str, object]:
    if classname in {"tests.test_full_mechanic_accepted_publication", "tests.test_gve16_delivery_alignment_regression"}:
        return dict(classification="real_regression", involved_modules="scripts/generate_full_mechanic_accepted_publication.py", original_contract="正式产物生成应完整投影全部已批准 Alignment Rule。", current_behavior="生成因 L-15/PR-19 失败结算规则缺失而中止。", change_reason="关卡 Owner 重组遗漏失败页正式定义，同一根因级联阻断产物断言。", requires_code_change=True, requires_test_change=False, policy_basis="Approved structured Rule must reach its canonical Final owner exactly once.")
    if classname == "tests.test_review_workspace_ui_contract":
        return dict(classification="real_regression", involved_modules="index.html, js/backend.js", original_contract="P1-P7 导航遵循当前七阶段产品流程。", current_behavior="UI 仍暴露 UE flow 子步骤和 2.1/2.2 编号。", change_reason="planning-only 策略落到 Final 后，旧 UE 审核入口未同步移除。", requires_code_change=True, requires_test_change=True, policy_basis="UE flow is not an active Final/review step; planning sketch is the sole board carrier.")
    if classname == "tests.test_feishu_publish":
        if name in OBSOLETE_FEISHU:
            return dict(classification="obsolete_expectation", involved_modules="backend/feishu_publish.py, tests/test_feishu_publish.py", original_contract="发布两个或三个原生画板并维护 competitor/UE checkpoint。", current_behavior="只发布 planning board，旧 checkpoint 不重新激活。", change_reason="产品策略由多画板改为 planning-only。", requires_code_change=False, requires_test_change=True, policy_basis="Final allows planning board only; UE and competitor boards must remain absent.")
        return dict(classification="implementation_coupled_test", involved_modules="backend/feishu_publish.py, tests/test_feishu_publish.py", original_contract="验证发布重试、幂等、媒体、token 语义映射或冲突处理。", current_behavior="目标行为仍保留，但 FakeCli 固定伪造两个 board tokens，测试在目标断言前失败。", change_reason="共享测试夹具绑定旧双画板实现数量。", requires_code_change=False, requires_test_change=True, policy_basis="Publisher behavior remains covered through a one-planning-board public contract.")
    if classname in {"tests.test_current_native_whiteboard_delivery", "tests.test_feishu_sample_aligned_board", "tests.test_review_api", "tests.test_review_model", "tests.test_review_workflow_integration"}:
        return dict(classification="obsolete_expectation", involved_modules=classname.replace("tests.", "tests/").replace(".", "/") + ".py", original_contract="要求 UE/competitor 画板、其 warning 或额外确认阶段存在。", current_behavior="Final、Preview 与审核导航只保留 planning board。", change_reason="测试表达已废止的多画板产品策略。", requires_code_change=False, requires_test_change=True, policy_basis="Planning-only board policy; forbidden presentation carriers have zero Final presence.")
    if classname == "tests.test_phase56_generation":
        return dict(classification="implementation_coupled_test", involved_modules="scripts/generate_phase56.py, tests/test_phase56_generation.py", original_contract="支持链集合被写死为恰好三条。", current_behavior="已有受证据支持的 monster_movement_contact 第四条链。", change_reason="测试绑定固定集合数量而非受支持链的可追溯性。", requires_code_change=False, requires_test_change=True, policy_basis="Supported mechanic chains are data-driven; Pattern is not a project answer.")
    if classname == "tests.test_fully_resolved_diagnostic_preview":
        return dict(classification="workspace_contamination", involved_modules="artifacts/planning-content-phase6.5*, tests/test_fully_resolved_diagnostic_preview.py", original_contract="用两份历史复制文件永久字节相等证明诊断不写回。", current_behavior="历史正式预览已独立演进，但 audit 仍证明 source closure 前后哈希一致。", change_reason="跨日期静态产物漂移被误判为运行时写回。", requires_code_change=False, requires_test_change=True, policy_basis="Diagnostic overrides are temporary, writeBackAllowed=false, and source closure hash remains unchanged.")
    raise ValueError(f"unclassified failure: {classname}::{name}")


def build(junit_path: Path) -> dict[str, object]:
    root = ET.parse(junit_path).getroot()
    failures = []
    for case in root.iter("testcase"):
        failure = case.find("failure")
        if failure is None:
            continue
        classname, name = case.get("classname", ""), case.get("name", "")
        item = {
            "test_file": classname.replace("tests.", "tests/").replace(".", "/") + ".py",
            "test_name": name,
            "failure_message": failure.get("message") or (failure.text or "").splitlines()[-1],
            **_classification(classname, name),
            "requires_test_deletion": False,
        }
        failures.append(item)
    failures.append({
        "test_file": "tests/test_gameplay_video_context.py",
        "test_name": "test_context_endpoint_persists_only_completed_context_and_stales_affected_chapter",
        "failure_message": "Exact response-key assertion rejected anchorAuthority and observationAuthority.",
        "involved_modules": "backend/server.py, backend/auxiliary_video.py",
        "original_contract": "Context API key set was fixed and did not distinguish anchor from observation authority.",
        "current_behavior": "Response adds backward-compatible authority fields; observation remains observed_unreviewed.",
        "change_reason": "Test was coupled to an exact dictionary key set.",
        "classification": "implementation_coupled_test",
        "requires_code_change": False,
        "requires_test_change": True,
        "requires_test_deletion": False,
        "policy_basis": "Manual timestamp confirms evidence location only and never confirms Observation or Rule authority.",
    })
    counts = Counter(item["classification"] for item in failures)
    if len(failures) != 71 or sum(counts.values()) != 71:
        raise ValueError(f"expected 71 failures, got {len(failures)}")
    return {
        "schema_version": "phase1-closure-failure-ledger-v1",
        "baseline_head": "95e89483261846c8c133812c038c5d8dc9287cde",
        "original_failure_count": 71,
        "classification_counts": dict(sorted(counts.items())),
        "failures": failures,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("junit", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    payload = build(args.junit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
