"""Generate the machine-checkable Planner Feedback -> System Lesson baseline."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.system_lesson_registry import load_system_lesson_registry


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "artifacts" / "system-lessons-2026-08-24"


def _runtime_policy_evidence(policy_ref: str) -> list[str]:
    matches = []
    roots = [ROOT / "backend", ROOT / "data" / "planner_knowledge"]
    for base in roots:
        for path in sorted(base.rglob("*")):
            if not path.is_file() or path.name == "system-lessons-v1.json" or path.suffix not in {".py", ".json"}:
                continue
            if policy_ref in path.read_text(encoding="utf-8"):
                matches.append(path.relative_to(ROOT).as_posix())
    return matches


def _test_exists(node_id: str) -> bool:
    path_text, separator, function = node_id.partition("::")
    path = ROOT / path_text
    if not separator or not path.is_file():
        return False
    return f"def {function}(" in path.read_text(encoding="utf-8")


def build_system_lesson_traceability() -> dict[str, Any]:
    registry = load_system_lesson_registry()
    rows = []
    for lesson_id, lesson in registry.lessons_by_id.items():
        policies = [
            {"policyRef": policy_ref, "evidence": _runtime_policy_evidence(str(policy_ref))}
            for policy_ref in lesson["policyRefs"]
        ]
        tests = [
            {"nodeId": node_id, "exists": _test_exists(str(node_id))}
            for node_id in lesson["testRefs"]
        ]
        verified = (
            lesson["status"] == "approved"
            and all(item["evidence"] for item in policies)
            and all(item["exists"] for item in tests)
        )
        rows.append({
            "lessonId": lesson_id,
            "sourceFeedbackIds": list(lesson["sourceFeedbackIds"]),
            "lessonType": lesson["lessonType"],
            "decisionLogic": lesson["decisionLogic"],
            "runtimePolicies": policies,
            "tests": tests,
            "verificationStatus": "verified" if verified else "incomplete",
        })
    feedback_ids = {feedback_id for row in rows for feedback_id in row["sourceFeedbackIds"]}
    return {
        "schemaVersion": "feedback-system-lesson-traceability-v1",
        "lessons": rows,
        "summary": {
            "lessonCount": len(rows),
            "feedbackCount": len(feedback_ids),
            "verifiedLessonCount": sum(row["verificationStatus"] == "verified" for row in rows),
            "danglingPolicyCount": sum(not policy["evidence"] for row in rows for policy in row["runtimePolicies"]),
            "missingTestCount": sum(not test["exists"] for row in rows for test in row["tests"]),
        },
    }


def _markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Feedback → System Lesson → Runtime Policy → Test",
        "",
        "| Feedback | System Lesson | Runtime Policy | Test | Status |",
        "|---|---|---|---|---|",
    ]
    for row in result["lessons"]:
        feedback = "<br>".join(row["sourceFeedbackIds"])
        policies = "<br>".join(item["policyRef"] for item in row["runtimePolicies"])
        tests = "<br>".join(item["nodeId"] for item in row["tests"])
        lines.append(f"| {feedback} | {row['lessonId']} | {policies} | {tests} | {row['verificationStatus']} |")
    summary = result["summary"]
    lines.extend([
        "", "## Summary", "",
        f"- Lessons: {summary['lessonCount']}",
        f"- Feedback: {summary['feedbackCount']}",
        f"- Verified lessons: {summary['verifiedLessonCount']}",
        f"- Dangling policies: {summary['danglingPolicyCount']}",
        f"- Missing tests: {summary['missingTestCount']}",
    ])
    return "\n".join(lines) + "\n"


def main() -> None:
    result = build_system_lesson_traceability()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "feedback-system-lesson-matrix.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (OUTPUT_DIR / "FEEDBACK-SYSTEM-LESSON-MATRIX.md").write_text(
        _markdown(result), encoding="utf-8"
    )
    print(json.dumps(result["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
