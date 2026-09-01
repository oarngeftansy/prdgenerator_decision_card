from backend.gameplay_generation_quality import mechanism_closure_report


def random_model(*, normal_flow=None, unresolved=None, decision_cards=None):
    return {
        "chapters": [
            {
                "id": "R1",
                "scope": "三选一",
                "domainStates": {"random": "applicable"},
                "plannerSections": {"normalFlow": normal_flow or []},
                "unresolvedResponsibilities": sorted(unresolved or set()),
                "decisionCards": decision_cards or [],
            }
        ]
    }


def inventory_model(*, rules):
    return {
        "chapters": [
            {
                "id": "I1",
                "scope": "背包",
                "domainStates": {"inventory": "applicable"},
                "plannerSections": {"keyRules": rules},
                "decisionCards": [],
            }
        ]
    }


def test_random_choice_requires_pool_filter_commit_and_reset():
    model = random_model(normal_flow=["升级后显示三个候选，选择后继续战斗。"])

    report = mechanism_closure_report(model)
    missing = report["domains"]["random"]["missing"]

    assert {"eligibility", "filter", "duplicate", "empty", "commit", "reset"} <= set(missing)


def test_inventory_does_not_require_combat_formula():
    model = inventory_model(
        rules=[
            "物品只能放入未占用且形状匹配的格子。",
            "放置失败时物品返回原位置。",
        ]
    )

    report = mechanism_closure_report(model)

    assert report["domains"]["combat"]["status"] == "not_applicable"


def test_unknown_weight_rule_requires_decision_card():
    model = random_model(unresolved={"weights"}, decision_cards=[])

    report = mechanism_closure_report(model)

    assert any(
        item["code"] == "MECHANISM_DECISION_CARD_MISSING"
        for item in report["findings"]
    )


def test_an_unrelated_short_movement_rule_does_not_receive_random_filler():
    report = mechanism_closure_report(
        {
            "chapters": [
                {
                    "id": "M1",
                    "scope": "棋子移动",
                    "domainStates": {"movement": "applicable"},
                    "plannerSections": {
                        "normalFlow": ["玩家选择相邻空格后，棋子移动到目标格。"]
                    },
                }
            ]
        }
    )

    assert report["domains"]["random"]["status"] == "not_applicable"
    assert not any(item.get("domain") == "random" for item in report["findings"])


def test_decision_card_closes_only_the_named_unresolved_responsibility():
    report = mechanism_closure_report(
        random_model(
            unresolved={"weights", "replacement"},
            decision_cards=[{"responsibility": "weights", "status": "pending"}],
        )
    )

    missing_cards = {
        item["responsibility"]
        for item in report["findings"]
        if item["code"] == "MECHANISM_DECISION_CARD_MISSING"
    }
    assert missing_cards == {"replacement"}


def test_one_explicit_decision_card_can_cover_a_related_missing_rule_group():
    model = random_model(
        normal_flow=["升级后显示三个候选，玩家确认其中一项。"],
        unresolved={"filter", "duplicate", "empty"},
        decision_cards=[
            {
                "responsibilities": ["filter", "duplicate", "empty"],
                "question": "无效、重复或不足三个候选时如何处理？",
                "status": "pending",
            }
        ],
    )

    report = mechanism_closure_report(model)

    assert not any(
        item["responsibility"] in {"filter", "duplicate", "empty"}
        and item["code"] in {"MECHANISM_RESPONSIBILITY_MISSING", "MECHANISM_DECISION_CARD_MISSING"}
        for item in report["findings"]
    )
    assert report["domains"]["random"]["status"] == "decision_required"
