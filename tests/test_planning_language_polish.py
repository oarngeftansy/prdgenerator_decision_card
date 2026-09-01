import importlib.util
from copy import deepcopy

from backend.planning_language_polish import polish_final_document


def test_planning_language_polish_module_exists_at_final_renderer_boundary():
    assert importlib.util.find_spec("backend.planning_language_polish") is not None


def _document():
    return {
        "title": "冻结执行案",
        "status": "reference_preview_with_open_gaps",
        "systems": [{
            "title": "成长", "objects": [{
                "title": "选择", "chapters": [{
                    "chapterId": "C1", "title": "三选一", "foldIntoObject": False,
                    "groups": [{"title": "机制流程", "sentences": [
                        {"text": "玩家点击刷新按钮，随后三选一刷新后替换当前三项候选。", "sourceRuleIds": ["R1"], "sourceFactIds": ["F1"], "evidenceIds": ["E1"], "schemaSlots": ["CandidateGeneration"]},
                        {"text": "火焰喷射攻击范围扩大30%。", "sourceRuleIds": ["R2"], "sourceFactIds": ["F2"], "evidenceIds": ["E2"], "schemaSlots": ["CandidateGeneration"]},
                        {"text": "雷暴枪伤害增加100%。", "sourceRuleIds": ["R3"], "sourceFactIds": ["F3"], "evidenceIds": ["E3"], "schemaSlots": ["CandidateGeneration"]},
                    ]}],
                    "reviewedGaps": [
                        {"gapId": "G1", "question": "速度变化的触发条件待确认。", "status": "reviewed_open"},
                        {"gapId": "G2", "question": "怪物在当前阶段何时开始生成，满足什么条件后停止生成？", "status": "reviewed_open"},
                        {"gapId": "G3", "question": "滚动在什么条件下停止，最终获得结果在什么时点确定？", "status": "reviewed_open"},
                        {"gapId": "G4", "question": "候选是否共用同一入选条件；若不共用，分别是什么？", "status": "reviewed_open"},
                        {"gapId": "G5", "question": "刷新是否消耗资源或需要其他条件；若存在，具体消耗与扣除时点是什么？", "status": "reviewed_open"},
                    ],
                }],
            }],
        }],
    }


def test_polish_removes_machine_repetition_and_labels_numeric_examples_in_place():
    result = polish_final_document(_document())
    sentences = result["systems"][0]["objects"][0]["chapters"][0]["groups"][0]["sentences"]

    assert [item["text"] for item in sentences] == [
        "玩家点击刷新按钮后，替换当前三项候选。",
        "数值示例：火焰喷射攻击范围扩大30%。",
        "雷暴枪伤害增加100%。",
    ]
    assert [item["sourceRuleIds"] for item in sentences] == [["R1"], ["R2"], ["R3"]]


def test_polish_rewrites_gap_questions_without_dropping_or_reordering_them():
    result = polish_final_document(_document())
    gaps = result["systems"][0]["objects"][0]["chapters"][0]["reviewedGaps"]

    assert [gap["gapId"] for gap in gaps] == ["G1", "G2", "G3", "G4", "G5"]
    assert [gap["question"] for gap in gaps] == [
        "什么条件会触发速度变化？",
        "怪物何时开始生成，何时停止生成？",
        "滚动何时停止，最终结果何时确定？",
        "候选是否采用相同的入选条件？若不同，请分别说明。",
        "刷新是否需要消耗资源或满足其他条件？如需消耗，消耗内容及扣除时点是什么？",
    ]


def test_polish_is_immutable_and_only_changes_allowed_text_fields():
    source = _document()
    before = deepcopy(source)
    result = polish_final_document(source)

    assert source == before
    before_sentence = before["systems"][0]["objects"][0]["chapters"][0]["groups"][0]["sentences"][0]
    after_sentence = result["systems"][0]["objects"][0]["chapters"][0]["groups"][0]["sentences"][0]
    assert {key: value for key, value in before_sentence.items() if key != "text"} == {
        key: value for key, value in after_sentence.items() if key != "text"
    }
    assert [system["title"] for system in result["systems"]] == ["成长"]
