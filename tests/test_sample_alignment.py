from backend.sample_alignment import sample_alignment_report


def test_complex_chapter_is_compared_only_on_evidence_applicable_dimensions():
    model = {"chapters": [{
        "id": "C1", "scope": "奖励候选", "mechanism": {"type": "random_pool"},
        "granularityEvidence": {
            "contentInventory": {"sourceIds": ["D1"]},
            "executionSequence": {"sourceIds": ["D2"]},
            "boundary": {"sourceIds": ["D3"]},
            "formula": {"applicable": False},
        },
        "contentInventory": ["候选奖励"],
        "boundaryRules": ["候选不足时只展示已有结果"],
        "plannerSections": {"summary": "系统筛选可用奖励后展示候选项。"},
    }]}

    report = sample_alignment_report(model)
    rows = {row["axis"]: row for row in report["chapters"][0]["granularity"]}

    assert rows["contentInventory"]["status"] == "satisfied"
    assert rows["executionSequence"]["status"] == "missing"
    assert rows["formula"]["status"] == "not_applicable"
    assert not report["passed"]


def test_simple_chapter_can_match_sample_method_without_formula_configuration_or_lifecycle():
    model = {"chapters": [{
        "id": "C2", "scope": "载具移动", "mechanism": {"type": "simple_state"},
        "granularityEvidence": {"boundary": {"sourceIds": ["F1"]}},
        "boundaryRules": ["拖动超出范围时停在边界"],
        "plannerSections": {"summary": "进入战斗后，载具沿路线自动前进；玩家拖动载具时，只改变横向位置。"},
    }]}

    report = sample_alignment_report(model)
    rows = {row["axis"]: row for row in report["chapters"][0]["granularity"]}

    assert rows["formula"]["status"] == "not_applicable"
    assert rows["configuration"]["status"] == "not_applicable"
    assert rows["lifecycle"]["status"] == "not_applicable"
    assert report["passed"]


def test_alignment_explains_sources_expected_facts_coverage_and_not_applicable_basis():
    model = {"chapters": [{
        "id": "C3", "scope": "奖励候选", "mechanism": {"type": "random_pool"},
        "granularityEvidence": {
            "executionSequence": {
                "sourceIds": ["DOC-21", "TABLE-03"],
                "sourceType": "reference_document",
                "requiredFacts": ["排除未解锁奖励", "按优先级填充候选位"],
            },
            "formula": {"applicable": False, "notApplicableReason": "素材只规定候选顺序，没有提供概率或计算表达式"},
        },
        "executionSequence": ["排除未解锁奖励"],
    }]}

    report = sample_alignment_report(model)
    rows = {row["axis"]: row for row in report["chapters"][0]["granularity"]}

    sequence = rows["executionSequence"]
    assert sequence["status"] == "missing"
    assert sequence["sourceIds"] == ["DOC-21", "TABLE-03"]
    assert sequence["requiredFacts"] == ["排除未解锁奖励", "按优先级填充候选位"]
    assert sequence["coveredFacts"] == ["排除未解锁奖励"]
    assert sequence["missingFacts"] == ["按优先级填充候选位"]
    assert "按优先级填充候选位" in sequence["basis"]

    formula = rows["formula"]
    assert formula["status"] == "not_applicable"
    assert formula["basis"] == "素材只规定候选顺序，没有提供概率或计算表达式"


def test_alignment_summary_counts_satisfied_missing_and_not_applicable_separately():
    model = {"chapters": [{
        "id": "C4", "scope": "载具移动",
        "granularityEvidence": {
            "boundary": {"sourceIds": ["F1"], "requiredFacts": ["拖动超出范围时停在边界"]},
            "formula": {"applicable": False, "notApplicableReason": "素材没有计算关系"},
        },
        "boundaryRules": ["拖动超出范围时停在边界"],
    }]}

    report = sample_alignment_report(model)

    assert report["summary"]["satisfied"] == 1
    assert report["summary"]["missing"] == 0
    assert report["summary"]["notApplicable"] == 12
