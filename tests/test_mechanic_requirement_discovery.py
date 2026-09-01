from __future__ import annotations

import inspect

import backend.mechanic_requirement_discovery as discovery


def _mechanic(signals: list[str] | None = None) -> dict:
    return {
        "mechanicId": "MECH-MONSTER",
        "mechanicType": "monster_movement_attack",
        "ownerPath": {"system": "战斗", "subsystem": "怪物", "mechanic": "怪物行为"},
        "existenceSignals": signals or [],
    }


def test_requirement_id_is_stable_and_does_not_depend_on_labels_or_status():
    first = discovery.stable_requirement_id("MECH-MONSTER", "attack.exit")
    second = discovery.stable_requirement_id("MECH-MONSTER", "attack.exit")
    assert first == second
    assert first.startswith("REQ-")
    assert first != discovery.stable_requirement_id("MECH-OTHER", "attack.exit")


def test_conditional_dimension_requires_its_own_existence_signal():
    without_repeat = discovery.discover_requirements([_mechanic()])
    repeat = next(item for item in without_repeat if item["executionDimensionId"] == "attack.repeat.exists")
    assert repeat["status"] == "dormant_optional"

    with_repeat = discovery.discover_requirements([_mechanic(["repeat_attack_exists"])])
    repeat = next(item for item in with_repeat if item["executionDimensionId"] == "attack.repeat.exists")
    assert repeat["status"] == "evidence_probe"
    interval = next(item for item in with_repeat if item["executionDimensionId"] == "attack.repeat.interval")
    assert interval["status"] == "dormant_optional"


def test_dimension_contract_does_not_accept_merely_related_rule():
    related = [{
        "ruleId": "RULE-1", "mechanicId": "MECH-MONSTER",
        "dimensionIds": ["attack.exit"], "valid": True,
        "satisfactionFacets": ["exit_condition"],
    }]
    requirements = discovery.discover_requirements([_mechanic()], rules=related)
    exit_req = next(item for item in requirements if item["executionDimensionId"] == "attack.exit")
    assert exit_req["status"] != "resolved"

    sufficient = [{**related[0], "satisfactionFacets": ["exit_condition", "exit_result"]}]
    requirements = discovery.discover_requirements([_mechanic()], rules=sufficient)
    exit_req = next(item for item in requirements if item["executionDimensionId"] == "attack.exit")
    assert exit_req["status"] == "resolved"
    assert exit_req["satisfiedByRuleIds"] == ["RULE-1"]


def test_temporal_dimensions_choose_continuous_evidence_first():
    source = discovery.select_evidence_source(
        [{"mode": "temporal", "priority": 1}, {"mode": "static", "priority": 2}],
        {"videoAvailable": True, "orderedScreenshotCoverage": 0.9},
    )
    assert source["strategy"] == "video_or_continuous_frames"


def test_probe_cannot_be_exhausted_until_every_condition_is_met():
    incomplete = discovery.evaluate_probe({
        "fullSelectedSourceScanned": True,
        "allAnchorWindowsScanned": True,
        "allCandidateWindowsExpanded": False,
        "noNewCandidateWindows": True,
        "auditTrailRecorded": True,
        "candidates": [],
    })
    assert incomplete["status"] == "evidence_probe"

    exhausted = discovery.evaluate_probe({
        "fullSelectedSourceScanned": True,
        "allAnchorWindowsScanned": True,
        "allCandidateWindowsExpanded": True,
        "noNewCandidateWindows": True,
        "auditTrailRecorded": True,
        "candidates": [],
    })
    assert exhausted == {"status": "evidence_unknown", "reopenable": True}


def test_candidate_separates_order_correlation_and_causality():
    candidate = discovery.build_evidence_candidate(
        requirement_id="REQ-X",
        source_id="VIDEO-1",
        before={"timestampMs": 100, "frameRef": "f1", "state": "moving"},
        transition={"timestampMs": 200, "frameRef": "f2", "event": "contact"},
        after={"timestampMs": 300, "frameRef": "f3", "state": "damaged"},
        event_confidence=0.9,
        causality_confidence=0.4,
        causal_conditions_verified=False,
    )
    assert candidate["observedOrder"] == "before<transition<after"
    assert candidate["stateCorrelation"] == "uncertain"
    assert candidate["causalSupport"] == "uncertain"
    assert candidate["eventRecognitionConfidence"] == 0.9
    assert candidate["transitionCausalityConfidence"] == 0.4


def test_high_temporal_confidence_cannot_replace_verified_causal_conditions():
    candidate = discovery.build_evidence_candidate(
        requirement_id="REQ-X", source_id="VIDEO-1",
        before={"timestampMs": 100, "frameRef": "f1", "state": "A"},
        transition={"timestampMs": 200, "frameRef": "f2", "event": "B"},
        after={"timestampMs": 300, "frameRef": "f3", "state": "C"},
        event_confidence=0.95, causality_confidence=0.95,
        causal_conditions_verified=False,
    )
    assert candidate["causalSupport"] == "uncertain"
    assert candidate["transitionCausalityConfidence"] < 0.7


def test_state_transition_candidate_can_advance_without_claiming_causality():
    candidate = discovery.build_evidence_candidate(
        requirement_id="REQ-X", source_id="VIDEO-1",
        before={"timestampMs": 100, "frameRef": "f1", "state": "battle"},
        transition={"timestampMs": 200, "frameRef": "f2", "event": "selection_ui_visible"},
        after={"timestampMs": 300, "frameRef": "f3", "state": "selection"},
        event_confidence=0.95, causality_confidence=0.85,
        causal_conditions_verified=False, claim_mode="state_transition",
        observed_facets=["temporary_state_entry"],
    )
    assert candidate["causalSupport"] == "uncertain"
    assert discovery.evaluate_probe({"candidates": [candidate]})["status"] == "evidence_resolvable"


def test_review_routing_uses_existing_status_taxonomy_only():
    behavior = discovery.route_hidden_requirement("hidden_behavior")
    parameter = discovery.route_hidden_requirement("hidden_parameter")
    assert behavior == {"status": "review_required", "reviewType": "behavior", "routingTarget": "P4"}
    assert parameter == {"status": "review_required", "reviewType": "parameter", "routingTarget": "P6"}
    assert "parameter_required" not in discovery.CLOSURE_STATUSES


def test_review_item_keeps_owner_and_requirement_without_dumping_probe_debug():
    requirement = {
        "requirementId": "REQ-1", "mechanicId": "MECH-MONSTER",
        "executionDimensionId": "attack.exit", "status": "review_required",
        "reviewType": "behavior", "routingTarget": "P4",
        "ownerPath": {"system": "战斗", "subsystem": "怪物", "mechanic": "怪物行为"},
    }
    item = discovery.build_review_item(
        requirement,
        confirmed_context=["怪物会向载具移动", "接触载具后会造成伤害"],
        question="怪物进入攻击状态后，什么条件结束该状态？",
        probe_summary_ref="PRB-1",
    )
    assert item["requirementId"] == "REQ-1"
    assert item["ownerPath"]["mechanic"] == "怪物行为"
    assert item["defaultView"]["confirmed"] == ["怪物会向载具移动", "接触载具后会造成伤害"]
    assert "frame" not in str(item["defaultView"]).lower()


def test_p4_review_item_defaults_to_proposal_review_when_proposal_exists():
    requirement = {"requirementId": "REQ-1", "mechanicId": "M",
                   "executionDimensionId": "attack.exit", "status": "review_required",
                   "reviewType": "behavior", "routingTarget": "P4", "ownerPath": {}}
    proposal = discovery.build_ai_proposed_rule(
        requirement, proposal_text="脱离接触后退出攻击。", known_context_refs=["RULE-1"],
        proposal_bases=[{"type": "rule_gap", "ref": "REQ-1"}], uncertainties=["距离未知"],
        assumption_level="medium", proposal_mode="behavior_hypothesis",
        unsupported_specificity=["new_exit_condition: 脱离接触"],
        information_gain=[{"type": "trigger_condition", "decision": "载具接触结束时停止接触伤害"}])
    item = discovery.build_review_item(
        requirement, confirmed_context=["接触造成伤害"], question="如何退出？",
        probe_summary_ref="PRB", proposal=proposal)
    assert item["defaultView"]["mode"] == "proposal_review"
    assert item["defaultView"]["aiProposedRule"] == "AI推测：脱离接触后退出攻击。"
    assert item["defaultView"]["actions"] == ["accept", "edit", "reject", "defer"]


def test_evidence_resolvable_candidate_promotes_to_fact_but_not_rule():
    candidate = discovery.build_evidence_candidate(
        requirement_id="REQ-X", source_id="VIDEO-1",
        before={"timestampMs": 100, "frameRef": "f1", "state": "battle"},
        transition={"timestampMs": 200, "frameRef": "f2", "event": "settlement_visible"},
        after={"timestampMs": 300, "frameRef": "f3", "state": "settlement"},
        event_confidence=0.95, causality_confidence=0.8,
        causal_conditions_verified=False, claim_mode="state_transition",
        observed_facets=["settlement_state"],
        execution_dimension_id="settlement.entry",
    )
    promoted = discovery.promote_candidates_to_evidence_facts([candidate])
    assert len(promoted["evidence"]) == 1
    assert promoted["facts"][0]["originRequirementIds"] == ["REQ-X"]
    assert promoted["facts"][0]["causalClaimAllowed"] is False
    assert promoted["rules"] == []


def test_exhausted_partial_fact_becomes_reopenable_evidence_unknown():
    requirement = {
        "requirementId": "REQ-1", "status": "evidence_resolvable",
        "satisfactionContract": {"criteria": ["completion_condition", "completion_result"]},
    }
    facts = [{
        "originRequirementIds": ["REQ-1"],
        "observedFacets": ["post_boss_cleanup_observed"],
    }]
    result = discovery.finalize_requirement_after_probe(requirement, facts, probe_exhausted=True)
    assert result["status"] == "evidence_unknown"
    assert result["reopenable"] is True
    assert result["unresolvedCriteria"] == ["completion_condition", "completion_result"]


def test_valid_rule_closes_requirement_at_exact_dimension_only():
    requirement = {
        "requirementId": "REQ-1", "mechanicId": "MECH-MONSTER",
        "executionDimensionId": "attack.exit", "status": "review_required",
    }
    wrong_dimension = {
        "ruleId": "RULE-X", "mechanicId": "MECH-MONSTER", "valid": True,
        "satisfiesRequirementIds": ["REQ-1"], "dimensionIds": ["attack.entry"],
    }
    assert discovery.reassess_requirement(requirement, [wrong_dimension])["status"] == "review_required"

    valid = {**wrong_dimension, "ruleId": "RULE-Y", "dimensionIds": ["attack.exit"]}
    resolved = discovery.reassess_requirement(requirement, [valid])
    assert resolved["status"] == "resolved"
    assert resolved["satisfiedByRuleIds"] == ["RULE-Y"]


def test_fact_bundle_promotes_only_when_full_contract_is_observed_and_keeps_lineage():
    requirement = {"requirementId": "REQ-X", "mechanicId": "M",
                   "executionDimensionId": "stage.transition",
                   "satisfactionContract": {"criteria": ["stage_exit", "next_stage_entry"]}}
    facts = [{"factId": "FACT-X", "sourceEvidenceIds": ["EVD-X"],
              "originRequirementIds": ["REQ-X"],
              "observedFacets": ["stage_exit", "next_stage_entry"],
              "causalClaimAllowed": False}]
    rule = discovery.promote_fact_bundle_to_rule(
        requirement, facts, rule_text="普通战斗之后进入首领战。", claim_semantics="observed_sequence")
    assert rule["sourceFactIds"] == ["FACT-X"]
    assert rule["sourceEvidenceIds"] == ["EVD-X"]
    assert rule["satisfiesRequirementIds"] == ["REQ-X"]
    assert discovery.reassess_requirement(requirement, [rule])["status"] == "resolved"


def test_partial_or_noncausal_fact_cannot_promote_causal_rule():
    requirement = {"requirementId": "REQ-X", "mechanicId": "M",
                   "executionDimensionId": "attack.exit",
                   "satisfactionContract": {"criteria": ["exit_condition", "exit_result"]}}
    partial = [{"factId": "F", "sourceEvidenceIds": ["E"], "originRequirementIds": ["REQ-X"],
                "observedFacets": ["exit_result"], "causalClaimAllowed": False}]
    assert discovery.promote_fact_bundle_to_rule(
        requirement, partial, rule_text="退出。", claim_semantics="observed_sequence") is None
    complete = [{**partial[0], "observedFacets": ["exit_condition", "exit_result"]}]
    assert discovery.promote_fact_bundle_to_rule(
        requirement, complete, rule_text="条件导致退出。", claim_semantics="causal_rule") is None


def test_mechanic_skeleton_placeholder_is_not_a_rule_and_only_keeps_unresolved_slots():
    requirements = [
        {"requirementId": "REQ-A", "status": "resolved"},
        {"requirementId": "REQ-B", "status": "evidence_probe"},
    ]
    placeholder = discovery.build_mechanic_skeleton_placeholder(
        skeleton_id="monster_attack", mechanic_id="M", owner_chapter="怪物", rule_group="攻击",
        segments=[{"text": "进入攻击状态"},
                  {"requirementId": "REQ-A", "placeholder": "执行方式待确认"},
                  {"requirementId": "REQ-B", "placeholder": "退出条件待确认"}],
        requirements=requirements,
    )
    assert placeholder["text"] == "进入攻击状态 → [退出条件待确认]"
    assert placeholder["itemType"] == "mechanic_skeleton_placeholder"
    assert placeholder["publicationEligible"] is True
    assert placeholder["isValidRule"] is False
    assert placeholder["requirementIds"] == ["REQ-B"]


def test_ai_proposed_rule_is_lineaged_reviewable_and_never_valid_or_publishable():
    requirement = {"requirementId": "REQ-X", "mechanicId": "M",
                   "executionDimensionId": "attack.exit", "status": "evidence_unknown"}
    proposal = discovery.build_ai_proposed_rule(
        requirement, proposal_text="攻击条件不成立时退出攻击状态。",
        known_context_refs=["RULE-MOVE", "FACT-CONTACT"],
        proposal_bases=[{"type": "mechanic_execution_prior", "ref": "attack.exit"}],
        uncertainties=["退出后的具体状态尚未确认"],
        assumption_level="medium", proposal_mode="behavior_hypothesis",
        unsupported_specificity=["new_exit_condition: 攻击条件不成立"],
        information_gain=[{"type": "trigger_condition", "decision": "目标离开接触范围时结束攻击"}],
    )
    assert proposal["originRequirementId"] == "REQ-X"
    assert proposal["proposalStatus"] == "proposed"
    assert proposal["valid"] is False
    assert proposal["publicationEligible"] is False
    assert proposal["countsAsConfirmedRule"] is False
    assert proposal["reviewActions"] == ["accept", "edit", "reject", "defer"]


def test_p4_review_view_prefers_ai_proposal_but_can_fall_back_to_question():
    proposal = {"proposalId": "PROP-X", "proposalText": "建议规则。",
                "uncertainties": ["条件未知"]}
    view = discovery.build_proposal_review_view(
        confirmed_context=["怪物会向载具移动。"], question="攻击如何退出？", proposal=proposal)
    assert view["confirmedContext"] == ["怪物会向载具移动。"]
    assert view["aiProposedRule"] == "建议规则。"
    assert view["actions"] == ["accept", "edit", "reject", "defer"]
    fallback = discovery.build_proposal_review_view(
        confirmed_context=[], question="攻击如何退出？", proposal=None)
    assert fallback["mode"] == "question_only"


def test_only_accept_or_edit_can_promote_proposal_to_approved_rule():
    requirement = {"requirementId": "REQ-X", "mechanicId": "M",
                   "executionDimensionId": "attack.exit",
                   "satisfactionContract": {"criteria": ["exit_condition", "exit_result"]}}
    proposal = discovery.build_ai_proposed_rule(
        {**requirement, "status": "review_required"}, proposal_text="失去攻击条件时退出。",
        known_context_refs=[], proposal_bases=[{"type": "rule_gap", "ref": "REQ-X"}],
        uncertainties=["退出结果待主策确认"], assumption_level="medium",
        proposal_mode="behavior_hypothesis", unsupported_specificity=["new_exit_condition"],
        information_gain=[{"type": "lifecycle_result", "decision": "退出后恢复移动"}])
    assert discovery.promote_reviewed_proposal_to_rule(requirement, proposal, action="defer") is None
    approved = discovery.promote_reviewed_proposal_to_rule(
        requirement, proposal, action="edit", edited_text="失去攻击条件时退出攻击并恢复移动。")
    assert approved["valid"] is True
    assert approved["sourceProposalId"] == proposal["proposalId"]
    assert approved["satisfiesRequirementIds"] == ["REQ-X"]


def test_low_proposal_rejects_unsupported_specificity_but_design_inference_is_reviewable():
    requirement = {"requirementId": "REQ-1", "mechanicId": "M",
                   "executionDimensionId": "attack.exit", "status": "evidence_probe"}
    try:
        discovery.build_ai_proposed_rule(
            requirement, proposal_text="脱离后恢复移动。", known_context_refs=[],
            proposal_bases=[{"type": "mechanic_execution_prior", "ref": "attack.exit"}],
            uncertainties=["无视频证据"], assumption_level="low",
            proposal_mode="minimal_completion", unsupported_specificity=["new_post_state"],
            information_gain=[{"type": "state_change", "decision": "退出后恢复移动"}])
        assert False, "low proposal must not contain unsupported specificity"
    except ValueError:
        pass
    high = discovery.build_ai_proposed_rule(
        requirement, proposal_text="接触结束后可能恢复移动。", known_context_refs=[],
        proposal_bases=[{"type": "mechanic_execution_prior", "ref": "attack.exit"}],
        uncertainties=["无项目证据"], assumption_level="high",
        proposal_mode="behavior_hypothesis", unsupported_specificity=["new_post_state"],
        proposal_type="design_inference", reasoning_basis=["通用追击循环"],
        conflicting_evidence=[],
        information_gain=[{"type": "state_change", "decision": "接触结束后恢复追击"}])
    view = discovery.build_proposal_review_view(
        confirmed_context=[], question="退出后如何处理？", proposal=high)
    assert high["defaultReviewEligible"] is True
    assert view["mode"] == "proposal_review"
    assert view["proposalType"] == "design_inference"
    assert view["aiProposedRule"].startswith("接触结束后")


def test_medium_proposal_is_visibly_marked_as_ai_hypothesis():
    requirement = {"requirementId": "REQ-1", "mechanicId": "M",
                   "executionDimensionId": "statistics.start", "status": "review_required"}
    medium = discovery.build_ai_proposed_rule(
        requirement, proposal_text="从战斗开始累计。", known_context_refs=["RULE-STATS"],
        proposal_bases=[{"type": "rule_gap", "ref": "REQ-1"}], uncertainties=["起点未确认"],
        assumption_level="medium", proposal_mode="behavior_hypothesis",
        unsupported_specificity=["new_lifecycle_start"],
        information_gain=[{"type": "trigger_condition", "decision": "进入可战斗状态时开始累计"}])
    view = discovery.build_proposal_review_view(
        confirmed_context=[], question="何时开始？", proposal=medium)
    assert view["aiProposedRule"].startswith("AI推测：")


def test_alternative_design_requires_complete_options_and_supports_one_click_choice():
    requirement = {"requirementId": "REQ-1", "mechanicId": "M",
                   "executionDimensionId": "weapon.slot_full", "status": "review_required",
                   "satisfactionContract": {"criteria": ["full_slot_behavior"]}}
    options = [{
        "alternativeId": key, "text": text, "gameplayImpact": "改变满栏获取流程",
        "advantages": ["流程完整"], "risks": ["需要额外交互"], "compatibility": "兼容现有栏位",
    } for key, text in (("A", "同武器升级，新武器进入替换选择。"),
                        ("B", "满栏后只出现已有武器升级。"))]
    proposal = discovery.build_ai_proposed_rule(
        requirement, proposal_text=options[0]["text"], known_context_refs=["SLOT-EXISTS"],
        proposal_bases=[{"type": "planner_knowledge", "ref": "slot_full_patterns"}],
        uncertainties=["项目未定义满栏目标"], assumption_level="medium",
        proposal_mode="behavior_hypothesis", unsupported_specificity=["new_full_slot_behavior"],
        proposal_type="alternative_design", reasoning_basis=["避免抽取结果无去向"],
        conflicting_evidence=[], alternatives=options, recommended_alternative_id="A",
        information_gain=[{"type": "branch_handling", "decision": "满栏时按所选方案处理新武器"}])
    view = discovery.build_proposal_review_view(
        confirmed_context=["存在武器栏"], question="满栏如何处理？", proposal=proposal)
    assert view["mode"] == "alternative_design_review"
    assert view["actions"] == ["accept_recommended", "choose_alternative", "edit", "reject"]
    approved = discovery.promote_reviewed_proposal_to_rule(
        requirement, proposal, action="choose_alternative", chosen_alternative_id="B")
    assert approved["text"] == options[1]["text"]


def test_information_gain_gate_rejects_semantic_completion_and_accepts_executable_decision():
    requirement = {"requirementId": "REQ-I", "mechanicId": "M",
                   "executionDimensionId": "statistics.start", "status": "review_required"}
    kwargs = dict(requirement=requirement, proposal_text="统计开始后进行统计。",
                  known_context_refs=[], proposal_bases=[{"type": "rule_gap", "ref": "REQ-I"}],
                  uncertainties=["起点未知"], assumption_level="medium",
                  proposal_mode="behavior_hypothesis", unsupported_specificity=[])
    try:
        discovery.build_ai_proposed_rule(**kwargs, information_gain=[
            {"type": "trigger_condition", "decision": "满足统计条件后开始统计"}])
        assert False, "generic semantic completion must fail information gain gate"
    except ValueError:
        pass
    proposal = discovery.build_ai_proposed_rule(**kwargs, information_gain=[
        {"type": "trigger_condition", "decision": "关卡进入可战斗状态时创建本局统计记录"},
        {"type": "data_source", "decision": "累计来源为各武器归属后的伤害值"},
    ])
    assert proposal["informationGainCount"] == 2


def test_benchmark_mechanic_recognition_uses_structured_chain_and_fact_signals():
    models = [{
        "mechanicId": "M-CHOICE", "mechanicType": "randomization",
        "chapterId": "growth", "name": "选择", "knownGameRules": [],
    }, {
        "mechanicId": "M-STAGE", "mechanicType": "level_flow",
        "chapterId": "level", "name": "关卡", "knownGameRules": [],
    }]
    chains = [{
        "chainType": "three_choice_core", "mechanicIds": ["M-CHOICE"],
        "entry": {"semantic": "upgrade_trigger"},
        "systemResponse": [{"semantic": "pause_combat"}],
        "playerAction": [{"semantic": "refresh_candidates"}],
        "progressionResult": [], "stateChange": [], "exitOrNext": [],
    }]
    recognized = discovery.recognize_benchmark_mechanics(models, chains, ["boss_arrival"])
    choice = next(item for item in recognized if item["mechanicId"] == "M-CHOICE")
    stage = next(item for item in recognized if item["mechanicId"] == "M-STAGE")
    assert choice["executionPriorTypes"] == ["battle_level_three_choice"]
    assert choice["existenceSignals"] == ["pause_exists", "refresh_exists"]
    assert stage["executionPriorTypes"] == ["stage_boss_end"]


def test_observed_reward_output_does_not_activate_reward_calculation_requirement():
    models = [{
        "mechanicId": "M-SETTLE", "mechanicType": "settlement",
        "chapterId": "settlement", "name": "结算", "knownGameRules": [],
    }]
    recognized = discovery.recognize_benchmark_mechanics(
        models, [], ["victory_result", "settlement_reward_items"]
    )
    requirements = discovery.discover_requirements(recognized)
    reward = next(item for item in requirements
                  if item["executionDimensionId"] == "settlement.reward_calculation")
    assert reward["status"] == "dormant_optional"


def test_planner_relevance_gate_suppresses_internal_event_architecture_questions():
    internal = discovery.evaluate_planner_relevance({
        "decisionImpacts": ["internal_event_dispatch", "listener_implementation"],
    })
    planner = discovery.evaluate_planner_relevance({
        "decisionImpacts": ["qa_acceptance", "player_state"],
    })
    assert internal["action"] == "suppress_implementation_detail"
    assert planner["action"] == "retain"


def test_chain_satisfaction_projection_uses_semantics_and_keeps_partial_contract_open():
    chains = [{
        "chainId": "CHAIN-1", "mechanicId": "M-CHOICE",
        "entry": {"semantic": "upgrade_trigger", "ruleIds": ["R1"]},
        "playerAction": [{"semantic": "select_candidate", "ruleIds": ["R2"]}],
        "systemResponse": [], "stateChange": [], "progressionResult": [], "exitOrNext": [],
    }]
    projected = discovery.project_chain_dimension_satisfaction(chains)
    trigger = next(item for item in projected if item["ruleId"] == "R1")
    confirm = next(item for item in projected if item["ruleId"] == "R2")
    assert trigger["dimensionIds"] == ["choice.trigger"]
    assert trigger["satisfactionFacets"] == ["trigger_condition"]
    assert confirm["satisfactionFacets"] == ["confirmation_action"]

    mechanics = [{
        "mechanicId": "M-CHOICE", "executionPriorTypes": ["battle_level_three_choice"],
        "ownerPath": {}, "existenceSignals": [],
    }]
    requirements = discovery.discover_requirements(mechanics, rules=projected)
    assert next(item for item in requirements if item["executionDimensionId"] == "choice.trigger")["status"] == "resolved"
    assert next(item for item in requirements if item["executionDimensionId"] == "choice.confirm")["status"] != "resolved"


def test_dimension_contract_can_be_satisfied_by_multiple_explicit_rules():
    mechanics = [{
        "mechanicId": "M-CHOICE", "executionPriorTypes": ["battle_level_three_choice"],
        "ownerPath": {}, "existenceSignals": [],
    }]
    rules = [{
        "ruleId": "R-ACTION", "mechanicId": "M-CHOICE", "valid": True,
        "dimensionIds": ["choice.confirm"], "satisfactionFacets": ["confirmation_action"],
    }, {
        "ruleId": "R-RESULT", "mechanicId": "M-CHOICE", "valid": True,
        "dimensionIds": ["choice.confirm"], "satisfactionFacets": ["committed_result"],
    }]
    confirm = next(item for item in discovery.discover_requirements(mechanics, rules=rules)
                   if item["executionDimensionId"] == "choice.confirm")
    assert confirm["status"] == "resolved"
    assert confirm["satisfiedByRuleIds"] == ["R-ACTION", "R-RESULT"]


def test_one_rule_can_explicitly_satisfy_cross_mechanic_transition_without_duplication():
    mechanics = [{
        "mechanicId": "M-LEVEL", "executionPriorTypes": ["stage_boss_end"],
        "ownerPath": {}, "existenceSignals": [],
    }]
    rule = {
        "ruleId": "R-NEXT", "mechanicId": "M-SETTLEMENT",
        "satisfiesMechanicIds": ["M-LEVEL", "M-SETTLEMENT"], "valid": True,
        "dimensionIds": ["battle.next_state"], "satisfactionFacets": ["next_state"],
    }
    next_state = next(item for item in discovery.discover_requirements(mechanics, rules=[rule])
                      if item["executionDimensionId"] == "battle.next_state")
    assert next_state["status"] == "resolved"


def test_production_module_cannot_reference_benchmark_gold_set():
    source = inspect.getsource(discovery)
    assert "benchmark_expected_dimensions_gold_v1" not in source
