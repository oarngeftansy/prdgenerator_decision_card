from scripts.generate_system_lesson_traceability import build_system_lesson_traceability


def test_every_feedback_maps_to_active_lesson_runtime_policy_and_existing_test():
    result = build_system_lesson_traceability()
    matrix = result["lessons"]

    assert len({feedback_id for row in matrix for feedback_id in row["sourceFeedbackIds"]}) == 16
    assert all(row["runtimePolicies"] and row["tests"] for row in matrix)
    assert all(row["verificationStatus"] == "verified" for row in matrix)
    assert result["summary"] == {
        "lessonCount": 15,
        "feedbackCount": 16,
        "verifiedLessonCount": 15,
        "danglingPolicyCount": 0,
        "missingTestCount": 0,
    }


def test_traceability_matrix_contains_no_project_specific_fixture_content():
    result = build_system_lesson_traceability()

    assert "一路狂飙" not in str(result)
