from backend.document_assembler import build_final_document, document_to_markdown


def test_canonical_final_never_renders_unresolved_planning_questions() -> None:
    document = build_final_document({
        "rules": [{
            "ruleId": "D",
            "behavior": "普通怪物接触载具后造成伤害",
            "intent": "Damage",
            "schemaSlot": "damage",
            "ruleType": "logic",
            "subject": "普通怪物",
            "ownerChapterId": "MONSTER",
            "reviewStatus": "approved",
            "semanticValidity": "valid",
            "evidenceIds": ["E-D"],
            "sourceFactIds": ["F-D"],
        }],
        "chapters": [{
            "chapterId": "MONSTER",
            "title": "普通怪物",
            "system": "关卡",
            "object": "普通怪物",
        }],
        "gaps": [
            {
                "gapId": "Q",
                "chapterId": "MONSTER",
                "status": "reviewed_open",
                "gapDomain": "planning",
                "question": "怪物命中目标前依次执行哪些攻击处理？",
            },
            {
                "gapId": "T",
                "chapterId": "MONSTER",
                "status": "reviewed_open",
                "gapDomain": "technical",
                "question": "读取哪项配置？",
            },
            {
                "gapId": "P",
                "chapterId": "MONSTER",
                "status": "reviewed_open",
                "gapDomain": "planning",
                "question": "怪物接触载具并造成伤害后，是继续移动、停留攻击，还是离开战场？",
                "specificity": "concrete_decision",
            },
        ],
    })
    text = document_to_markdown(document)

    assert "接触载具后造成伤害" in text
    assert "依次执行哪些攻击处理" not in text
    assert "读取哪项配置" not in text
    assert "继续移动、停留攻击，还是离开战场" not in text
    assert "待确认" not in text
    assert "可能" not in text
