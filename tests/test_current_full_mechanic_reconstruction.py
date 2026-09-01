from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.generate_full_mechanic_reconstruction import (
    ROOT,
    build_current_reconstructions,
    build_planner_readability_projection,
    main,
)


def _model(mechanic_id: str):
    return {item["mechanicDesignId"]: item for item in build_current_reconstructions()}[mechanic_id]


def _semantics(model):
    return {semantic for item in model["designItems"] for semantic in item["semanticResponsibilities"]}


def test_choice_is_a_complete_candidate_and_decision_lifecycle():
    model = _model("MDES-CHOICE")
    assert {
        "trigger_model", "pause_scope", "candidate_pool", "eligibility_model", "pool_shortage",
        "candidate_generation", "candidate_stability", "refresh_invalidation", "commit_boundary",
        "apply_consumer", "cleanup_model", "resume_model", "reset_model",
    } <= _semantics(model)
    assert [item["sequence"] for item in model["designItems"]] == sorted(
        item["sequence"] for item in model["designItems"]
    )
    assert all("按规则" not in item["text"] for item in model["designItems"])


def test_weapon_is_a_complete_instance_slot_activation_and_attack_lifecycle():
    model = _model("MDES-WEAPON")
    assert {
        "acquire_model", "instance_identity", "result_classification", "slot_branches",
        "activation_model", "target_validity", "attack_cycle", "damage_handoff",
        "interrupt_model", "cleanup_model", "statistics_dependency",
    } <= _semantics(model)
    assert len(model["alternativeDesigns"][0]["options"]) == 3
    assert model["alternativeDesigns"][0]["recommendedOptionId"] == "W-FULL-A"
    assert any(ref["targetMechanicId"] == "MDES-DRAW" for ref in model["crossMechanicReferences"])


def test_monster_is_a_complete_behavior_state_model_without_false_confirmation():
    model = _model("MDES-MONSTER")
    assert {
        "enter_model", "target_model", "move_model", "contact_evaluation", "first_damage",
        "repeat_model", "movement_lock", "exit_resume", "pause_resume", "death_interrupt",
        "pending_damage", "cleanup_model",
    } <= _semantics(model)
    inferred_states = [item for item in model["designItems"] if item.get("stateNameInferred")]
    assert inferred_states
    assert all(item["knowledgeClass"] != "confirmed" for item in inferred_states)
    assert all("observationBasis" in item and "causalStatus" in item for item in inferred_states)


def test_models_reuse_cross_mechanic_rules_and_close_relations():
    models = build_current_reconstructions()
    primary_keys = [
        item["primaryDefinitionKey"]
        for model in models
        for item in model["designItems"]
        if item.get("primaryMechanicOwner") == model["mechanicDesignId"]
    ]
    assert len(primary_keys) == len(set(primary_keys))
    for model in models:
        ids = {item["designItemId"] for item in model["designItems"]}
        assert all(relation["fromDesignItemId"] in ids and relation["toDesignItemId"] in ids
                   for relation in model["relations"])
        assert all(parameter["consumerDesignItemIds"] for parameter in model["parameterContracts"])


def test_confirmed_items_preserve_authoritative_lineage_without_inference_pollution():
    for model in build_current_reconstructions():
        for item in model["designItems"]:
            if item["knowledgeClass"] == "confirmed":
                assert item["sourceRuleIds"] or item.get("sourceSynthesisIds")
                if item["sourceRuleIds"]:
                    assert item["requirementIds"]
            else:
                assert item["approvalState"] == "review_pending"


def test_all_three_models_cross_the_structural_depth_threshold():
    for model in build_current_reconstructions():
        assert model["coreDesignDepth"]["coverage"] >= 80.0
        assert model["qualityGate"]["pass"] is True
        assert model["remediationStatus"] == "structural_uplift"


def test_models_separate_high_value_supporting_and_implementation_details():
    for model in build_current_reconstructions():
        categories = model["designItemCategories"]
        assert categories["highValue"]
        assert categories["supportingExecution"] or categories["implementationOnly"]
        assert model["plannerValueMetrics"]["highValueQuestionCount"] < model["plannerValueMetrics"]["activeQuestionCount"]
        assert model["plannerValueMetrics"]["downgradedQuestionCount"] > 0
        assert model["plannerValueMetrics"]["removedFromHighValueListCount"] >= 7
        core_ids = set(model["coreDesignDepth"]["coveredResponsibilityIds"])
        non_core_ids = {
            item["responsibilityId"] for item in model["profile"]["responsibilities"]
            if item["plannerValueClass"] != "high_value"
        }
        assert core_ids.isdisjoint(non_core_ids)


def test_readability_projection_is_short_natural_and_lineage_preserving():
    models = build_current_reconstructions()
    projection = build_planner_readability_projection(models)
    banned = ("Primary Owner", "实例标识", "回写成功", "目标引用", "确认锁", "未结算指向", "可寻址实例")
    assert {item["mechanicDesignId"] for item in projection} == {
        "MDES-CHOICE", "MDES-WEAPON", "MDES-MONSTER"
    }
    for readable, model in zip(projection, models):
        source_ids = {item["designItemId"] for item in model["designItems"]}
        bullets = [bullet for section in readable["plannerReadableSections"]
                   for topic in section.get("topics", []) for bullet in topic["bullets"]]
        assert bullets
        assert all(set(bullet["sourceDesignItemIds"]) <= source_ids for bullet in bullets)
        assert all(len(bullet["text"]) <= 45 for bullet in bullets)
        assert all(not any(term in bullet["text"] for term in banned) for bullet in bullets)
        assert readable["integrity"]["depthUnchanged"] is True
        assert readable["integrity"]["lineageUnchanged"] is True
        assert readable["beforeAfter"]["afterLongBulletCount"] < readable["beforeAfter"]["beforeLongBulletCount"]


def test_density_projection_keeps_only_planner_important_default_rules():
    projection = build_planner_readability_projection(build_current_reconstructions())
    total_before = total_after = 0
    for readable in projection:
        default = readable["defaultReview"]
        core = default["coreRules"]
        branches = default["specialRules"]
        assert 3 <= len(core) <= 6
        assert len(branches) <= 4
        assert len(default["parameters"]) <= 3
        assert len(default["decisionPoints"]) <= 2
        assert all(rule["sourceDesignItemIds"] for rule in core + branches)
        assert readable["densityMetrics"]["downgradedSupportingCount"] >= 1
        assert readable["expandDetail"]["originalDesignItemIds"]
        assert readable["integrity"]["depthUnchanged"] is True
        assert readable["integrity"]["lineageUnchanged"] is True
        total_before += readable["densityMetrics"]["beforeDefaultRuleCount"]
        total_after += readable["densityMetrics"]["afterDefaultRuleCount"]
    assert 1 - total_after / total_before >= 0.40


def test_density_projection_removes_redundant_or_self_evident_copy():
    projection = {item["mechanicDesignId"]: item
                  for item in build_planner_readability_projection(build_current_reconstructions())}
    choice = " ".join(rule["text"] for rule in projection["MDES-CHOICE"]["defaultReview"]["coreRules"])
    weapon = " ".join(rule["text"] for rule in projection["MDES-WEAPON"]["defaultReview"]["coreRules"])
    monster = " ".join(rule["text"] for rule in projection["MDES-MONSTER"]["defaultReview"]["specialRules"])
    assert "未选择的候选不生效" not in choice
    assert "先判断是新武器还是已有武器" not in weapon
    assert "不影响其他怪物攻击" not in monster
    all_default = [rule["text"] for item in projection.values()
                   for key in ("coreRules", "specialRules")
                   for rule in item["defaultReview"][key]]
    assert "所有伤害均归属于产生该伤害的武器。" not in all_default
    assert "伤害统计按武器分别累计伤害。" in all_default
    assert "怪物死亡或离场后，停止移动和后续伤害。" not in all_default
    assert projection["MDES-CHOICE"]["densityMetrics"]["removedRedundantCount"] >= 1
    assert projection["MDES-WEAPON"]["densityMetrics"]["removedRedundantCount"] >= 1
    assert projection["MDES-MONSTER"]["densityMetrics"]["removedRedundantCount"] >= 1


def test_planner_view_reorganizes_state_nodes_as_natural_gameplay_rules():
    projection = {item["mechanicDesignId"]: item
                  for item in build_planner_readability_projection(build_current_reconstructions())}
    monster = " ".join(item["text"] for item in projection["MDES-MONSTER"]["plannerGameplayRules"]["coreRules"])
    assert "接触载具后开始造成伤害，并按攻击间隔持续攻击" in monster
    assert "与载具拉开距离后，怪物会继续靠近并再次发起攻击" in monster
    assert "首次接触载具时停止移动" not in monster
    assert "接触结束且怪物存活时" not in monster


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_generator_writes_review_only_artifacts_and_preserves_frozen_sources(tmp_path):
    frozen_candidates = [
        ROOT / "data/jobs/8312a91c89e144e6a59f81b982f14c06/job.json",
        ROOT / "artifacts/planning-content-phase6.5-chapter-assembly-2026-08-18/human-planning-preview.md",
        ROOT / "artifacts/mechanic-design-synthesis-2026-08-18/planning-hierarchy-preview.md",
        ROOT / "artifacts/mechanic-design-synthesis-2026-08-18/approved-mechanic-rules.json",
        ROOT / "artifacts/mechanic-requirement-closure-2026-08-18/requirements-after-closure.json",
    ]
    frozen = [path for path in frozen_candidates if path.exists()]
    assert ROOT / "artifacts/mechanic-design-synthesis-2026-08-18/approved-mechanic-rules.json" in frozen
    before = {str(path): _sha(path) for path in frozen}

    main(output_dir=tmp_path)

    assert {path.name for path in tmp_path.iterdir()} == {
        "before-models.json", "reconstructed-models.json", "core-design-depth.json",
        "reconstruction-quality-gate.json", "full-mechanic-design-review-preview.md",
        "reconstruction-lineage.json", "planner-readable-preview.json",
    }
    assert before == {str(path): _sha(path) for path in frozen}
    preview = (tmp_path / "full-mechanic-design-review-preview.md").read_text(encoding="utf-8")
    assert "approvalState" not in preview
    assert "ruleStatus" not in preview


def test_review_preview_is_mechanic_level_and_contains_execution_sections(tmp_path):
    main(output_dir=tmp_path)
    preview = (tmp_path / "full-mechanic-design-review-preview.md").read_text(encoding="utf-8")
    for title in ("战斗等级与三选一", "武器获取、栏位与攻击", "普通怪物移动与攻击"):
        assert f"## {title}" in preview
    for heading in ("After 默认主策视图", "核心规则", "分支 / 特殊规则", "密度变化",
                    "Before 默认视图", "结构根因", "跨系统依赖", "QA 验收结果", "深度指标"):
        assert heading in preview
    assert "<details>" in preview
    assert "<summary>Before 默认视图与完整机制详情</summary>" in preview
    assert "choice.candidate_pool" not in preview
    assert "weapon.attack_cycle" not in preview


def test_quality_artifact_reports_no_fake_lineage_or_score_inflation(tmp_path):
    main(output_dir=tmp_path)
    quality = json.loads((tmp_path / "reconstruction-quality-gate.json").read_text(encoding="utf-8"))
    assert quality["pass"] is True
    assert quality["unknownSourceRuleIds"] == []
    assert quality["placeholderCoverageCount"] == 0
    assert quality["presentationCoverageCount"] == 0
    assert quality["goldSetAccessCount"] == 0
    assert quality["prohibitedMutationCount"] == 0
