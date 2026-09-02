from __future__ import annotations

from backend.document_assembler import build_final_document, document_to_markdown


def _publication(subject: str, steps: list[dict], *, system: str = "玩法") -> dict:
    return {
        "chapters": [{
            "chapterId": "M-1",
            "title": subject,
            "object": subject,
            "system": system,
            "publicationEligibility": "eligible",
        }],
        "rules": [],
        "gaps": [],
        "mechanicFlows": [{
            "mechanicId": "MECH-1",
            "chapterId": "M-1",
            "sourceChapterIds": ["M-1"],
            "subject": subject,
            "steps": steps,
        }],
    }


def _step(rule_id: str, text: str, intent: str) -> dict:
    return {
        "ruleId": rule_id,
        "sourceRuleIds": [rule_id],
        "text": text,
        "intent": intent,
        "publicationState": "confirmed",
    }


def test_final_preserves_canonical_flow_order_without_injecting_selection_sample_copy() -> None:
    publication = _publication("选择", [
        _step("TRIGGER", "升级时触发选择", "trigger"),
        _step("PAUSE", "进入选择状态时暂停战斗", "state_enter"),
        _step("CANDIDATE", "系统生成新武器候选", "candidate_generation"),
        _step("SELECT", "玩家选择一项", "selection"),
        _step("EFFECT", "确认后应用所选效果", "effect"),
        _step("EXIT", "玩家确认后退出选择界面", "state_exit"),
        _step("REFRESH", "玩家点击刷新按钮，随后替换当前候选", "refresh"),
        _step("NUM", "强化使攻击范围扩大30%", "numeric_example"),
    ], system="成长")
    text = document_to_markdown(build_final_document(publication, title="选择系统"))
    markers = [
        "升级时触发选择",
        "进入选择状态时暂停战斗",
        "系统生成新武器候选",
        "玩家选择一项",
        "确认后应用所选效果",
        "玩家确认后退出选择界面",
        "玩家点击刷新按钮，随后替换当前候选",
        "强化使攻击范围扩大30%",
    ]
    positions = [text.index(marker) for marker in markers]
    assert positions == sorted(positions)
    assert "当前已观察到的候选内容包括" not in text


def test_final_preserves_unrelated_mechanic_flow_order_without_selection_vocabulary() -> None:
    publication = _publication("制作", [
        _step("OPEN", "玩家打开制作功能", "entry"),
        _step("CHECK", "系统校验配方材料是否满足", "condition"),
        _step("COST", "材料满足时一次性扣除对应资源", "resource_cost"),
        _step("CREATE", "扣除成功后生成制作产物", "result"),
        _step("FAIL", "任一材料不足时不扣除资源并保持原库存", "failure"),
    ], system="经济")
    text = document_to_markdown(build_final_document(publication, title="制作系统"))
    markers = [
        "玩家打开制作功能",
        "系统校验配方材料是否满足",
        "材料满足时一次性扣除对应资源",
        "扣除成功后生成制作产物",
        "任一材料不足时不扣除资源并保持原库存",
    ]
    positions = [text.index(marker) for marker in markers]
    assert positions == sorted(positions)
    assert "候选" not in text
    assert "武器" not in text
    assert "刷新按钮" not in text
