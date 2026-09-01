"""Text-only polish for an already assembled Final planning document."""

from __future__ import annotations

from copy import deepcopy
import re
from typing import Any


def _polish_sentence(text: str) -> str:
    value = str(text or "")
    value = re.sub(
        r"^(.+?点击刷新按钮)，随后.+?刷新后替换(.+?)(。?)$",
        r"\1后，替换\2\3",
        value,
    )
    value = value.replace("随后随后", "随后")
    return value


def _polish_question(text: str) -> str:
    value = str(text or "").strip()
    match = re.fullmatch(r"(.+?)的触发条件待确认[。？]?", value)
    if match:
        return f"什么条件会触发{match.group(1)}？"
    value = re.sub(
        r"^(.+?)在当前阶段何时开始生成，满足什么条件后停止生成？$",
        r"\1何时开始生成，何时停止生成？",
        value,
    )
    value = value.replace("滚动在什么条件下停止，最终获得结果在什么时点确定？", "滚动何时停止，最终结果何时确定？")
    value = value.replace("是否共用同一入选条件；若不共用，分别是什么？", "是否采用相同的入选条件？若不同，请分别说明。")
    value = value.replace(
        "刷新是否消耗资源或需要其他条件；若存在，具体消耗与扣除时点是什么？",
        "刷新是否需要消耗资源或满足其他条件？如需消耗，消耗内容及扣除时点是什么？",
    )
    value = re.sub(r"[，；]确保.{0,40}(?:可以|能够)?判定[。？]?$", "？", value)
    return value


def polish_final_document(document: dict[str, Any]) -> dict[str, Any]:
    """Polish only visible text fields on an isolated Final Document copy."""
    result = deepcopy(document)
    for system in result.get("systems") or []:
        for obj in system.get("objects") or []:
            for chapter in obj.get("chapters") or []:
                numeric_label_added = False
                for group in chapter.get("groups") or []:
                    for sentence in group.get("sentences") or []:
                        text = _polish_sentence(str(sentence.get("text") or ""))
                        if not numeric_label_added and re.search(r"\d+(?:\.\d+)?%", text):
                            text = "数值示例：" + text
                            numeric_label_added = True
                        sentence["text"] = text
                for gap in chapter.get("reviewedGaps") or []:
                    if gap.get("proposal"):
                        gap["proposal"] = _polish_sentence(str(gap["proposal"]))
                    if gap.get("question"):
                        gap["question"] = _polish_question(str(gap["question"]))
    return result
