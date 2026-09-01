from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


FORBIDDEN = re.compile(r"\b(scope|component|entry|result|unknown|pending_details)\b", re.I)
GARBLED = re.compile(r"(?:锛|绱|娴|璇|鈫|浜や|Ã|Â|â€™|�)")
PARAMETERIZED = {"formula", "progression", "random_pool", "economy_reward", "level_wave", "buff_chain", "statistics_feedback"}


def validate(model: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    chapters = [item for item in model.get("chapters") or [] if isinstance(item, dict)]
    if not chapters:
        return ["玩法文档没有可审核章节"]
    for index, chapter in enumerate(chapters, 1):
        label = str(chapter.get("id") or chapter.get("scope") or f"第{index}章")
        planner_text = json.dumps({
            "title": chapter.get("scope"),
            "plannerSections": chapter.get("plannerSections"),
            "claims": chapter.get("claims"),
            "decisions": chapter.get("unknowns"),
        }, ensure_ascii=False)
        if FORBIDDEN.search(planner_text):
            errors.append(f"{label}: 策划正文包含内部英文")
        if GARBLED.search(planner_text):
            errors.append(f"{label}: 策划正文包含乱码")
        if not (chapter.get("sourceFrameIds") or chapter.get("referenceSource") or chapter.get("evidenceClaims")):
            errors.append(f"{label}: 缺少证据来源")
        mechanism = chapter.get("mechanism") if isinstance(chapter.get("mechanism"), dict) else {}
        mechanism_type = str(mechanism.get("type") or "custom")
        if mechanism_type in PARAMETERIZED and not chapter.get("parameterSchema"):
            errors.append(f"{label}: 参数化机制缺少结构化字段")
        if mechanism_type == "formula" and not chapter.get("formulae"):
            errors.append(f"{label}: 计算机制缺少公式")
        for formula in chapter.get("formulae") or []:
            required = ("name", "expression", "calculationOrder", "rounding", "evidenceLevel")
            if not isinstance(formula, dict) or not all(formula.get(key) for key in required):
                errors.append(f"{label}: 公式缺少名称、表达式、计算顺序、取整或证据")
    return list(dict.fromkeys(errors))


def main() -> int:
    parser = argparse.ArgumentParser(description="检查飞书玩法文档是否达到执行级颗粒度")
    parser.add_argument("model", type=Path)
    args = parser.parse_args()
    payload = json.loads(args.model.read_text(encoding="utf-8"))
    model = payload.get("gameplayReviewModel") if isinstance(payload, dict) else None
    errors = validate(model if isinstance(model, dict) else payload)
    print(json.dumps({"passed": not errors, "errors": errors}, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
