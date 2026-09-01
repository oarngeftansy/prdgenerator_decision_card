from pathlib import Path

from backend.server import full_mechanic_review_data, full_mechanic_review_page
from scripts.generate_full_mechanic_reconstruction import main as generate_reconstruction


def test_full_mechanic_review_page_uses_the_web_tool_shell():
    response = full_mechanic_review_page()
    assert str(response.path).endswith("mechanic-review.html")
    assert Path(response.path).exists()


def test_full_mechanic_review_data_exposes_three_review_models_without_approval_pollution():
    generate_reconstruction()
    payload = full_mechanic_review_data()
    assert payload["artifactType"] == "mechanic_design_review"
    assert payload["publicationEligible"] is False
    assert [model["mechanicDesignId"] for model in payload["models"]] == [
        "MDES-CHOICE", "MDES-WEAPON", "MDES-MONSTER"
    ]
    assert all(model["designItems"] for model in payload["models"])
    assert all(model["designItemCategories"]["highValue"] for model in payload["models"])
    assert all(model["plannerValueMetrics"]["downgradedQuestionCount"] > 0 for model in payload["models"])
    assert all(item["approvalState"] in {"approved_source", "review_pending"}
               for model in payload["models"] for item in model["designItems"])
    assert len(payload["plannerReadabilityProjection"]) == 3
    assert all(item["plannerReadableSections"] for item in payload["plannerReadabilityProjection"])


def test_review_api_projects_accept_all_decision_without_mutating_models():
    payload = full_mechanic_review_data()
    assert payload["reviewState"] == "accepted"
    assert payload["approvalSummary"]["action"] == "accept_all"
    assert payload["approvalSummary"]["approvedRuleCount"] == 14
    assert payload["approvalSummary"]["retainedConfirmedRuleCount"] == 5
    assert all(item["approvalState"] in {"approved_source", "review_pending"}
               for model in payload["models"] for item in model["designItems"])


def test_web_defaults_to_readability_projection_and_folds_internal_detail():
    script = Path("js/mechanic-review.js").read_text(encoding="utf-8")
    assert "plannerReadabilityProjection" in script
    assert "defaultReview" in script
    assert "AI 推荐" not in script
    assert "原始规则与依据" in script


def test_web_default_layer_uses_density_projection_and_one_expand_detail():
    script = Path("js/mechanic-review.js").read_text(encoding="utf-8")
    assert "defaultReview" in script
    assert "展开完整机制详情" in script
    assert "model.beforeCoreDesignDepth" not in script
    assert "model.coreDesignDepth" not in script
    assert 'section("QA 可验证结果")' not in script
    assert 'section("跨系统依赖")' not in script
    assert 'section("主策审核后仍需补齐")' not in script


def test_web_shows_one_batch_acceptance_summary_instead_of_per_rule_labels():
    script = Path("js/mechanic-review.js").read_text(encoding="utf-8")
    assert "approvalSummary" in script
    assert "本轮机制方案已全部接受" in script
