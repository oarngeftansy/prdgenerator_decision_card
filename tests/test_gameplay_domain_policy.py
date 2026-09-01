from backend.gameplay_domain_policy import classify_domain_modules, provenance_scope_report


def test_sparse_movement_does_not_activate_unrelated_domains():
    states = classify_domain_modules({"movement", "health"}, set())

    assert states["movement"] == "applicable"
    assert states["combat"] == "applicable"
    assert states["inventory"] == "not_applicable"
    assert states["sweep"] == "not_applicable"


def test_unresolved_random_algorithm_requires_decision():
    states = classify_domain_modules(
        {"random_choice"},
        {"weights", "replacement"},
    )

    assert states["random"] == "decision_required"


def test_sample_reserve_cannot_publish_current_fact():
    sentence = "进入关卡时包含1个默认武器栏和4个自选栏。"
    model = {
        "chapters": [
            {
                "id": "C1",
                "scope": "载具",
                "plannerSections": {"keyRules": [sentence]},
                "provenanceClaims": [
                    {
                        "text": sentence,
                        "sourceScope": "sample_reserve",
                        "publicationAllowed": True,
                    }
                ],
            }
        ]
    }

    report = provenance_scope_report(model)

    assert report["passed"] is False
    assert report["findings"][0]["code"] == "SAMPLE_RESERVE_PUBLISHED_AS_FACT"


def test_sample_reserve_can_support_a_question_without_becoming_a_fact():
    model = {
        "chapters": [
            {
                "id": "C2",
                "provenanceClaims": [
                    {
                        "text": "栏位数量是否固定？",
                        "sourceScope": "sample_reserve",
                        "publicationAllowed": False,
                        "usage": "decision_question",
                    }
                ],
            }
        ]
    }

    assert provenance_scope_report(model)["passed"] is True


def test_domain_activation_is_not_bound_to_vehicle_gameplay():
    states = classify_domain_modules(
        {"placement_grid", "inventory_slot", "buff_duration"},
        set(),
    )

    assert states["placement"] == "applicable"
    assert states["inventory"] == "applicable"
    assert states["buff"] == "applicable"
    assert states["movement"] == "not_applicable"
