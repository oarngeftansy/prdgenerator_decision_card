from __future__ import annotations

import re
from typing import Any


_INTERNAL_TERMS = {
    "entry": "页面",
    "result": "结果",
    "component": "页面元素",
    "unknown": "待确认",
    "hud": "状态栏",
    "boss": "首领",
    "toast": "提示",
    "modal": "弹窗",
}
_UNCERTAIN_MARKERS = ("待确认", "未知", "可能", "推测", "推断", "无法确认", "不确定")
_DESKTOP_TERMS = re.compile(
    r"\b(?:mouse|cursor|hover|keyboard|right[- ]?click|double[- ]?click|scroll(?:\s+wheel)?|ctrl|shift|alt)\b",
    flags=re.I,
)


def _confirmed(item: dict[str, Any]) -> bool:
    return (item.get("confirmation") or {}).get("confirmed") is True


def planner_board_text(value: Any) -> str:
    """Convert evidence text into the shared, planner-facing Chinese copy."""
    if isinstance(value, dict):
        parts: list[str] = []
        for key in ("description", "text", "action", "details", "feedback", "result", "afterState"):
            if key not in value:
                continue
            part = planner_board_text(value.get(key))
            if part and part not in parts:
                parts.append(part)
        return "；".join(parts)
    if isinstance(value, (list, tuple)):
        parts = []
        for item in value:
            part = planner_board_text(item)
            if part and part not in parts:
                parts.append(part)
        return "；".join(parts)
    text = str(value or "").strip()
    text = re.sub(r"Roguelike", "随机成长", text, flags=re.I)
    text = re.sub(r"\bLv\.?\s*", "等级", text, flags=re.I)
    text = re.sub(r"\bHUD\b", "顶部信息", text, flags=re.I)
    text = re.sub(r"S\s*型", "弯曲", text, flags=re.I)
    text = re.sub(r"(?<=[\u4e00-\u9fff）)])/(?=[\u4e00-\u9fff（(])", "或", text)
    text = re.sub(
        r"(?:鼠标光标|鼠标指针|鼠标|光标)(?:[（(][^）)]*[）)])?(?:移动|位于|停留|悬停)[^，,；;。]*(?:[，,；;。]|$)",
        "",
        text,
    )
    text = re.sub(r"(?:鼠标光标|鼠标指针|鼠标|光标)(?:点击|单击)", "点击", text)
    desktop_clauses = re.split(r"([，,；;。])", text)
    text = "".join(
        clause if index % 2 or not _DESKTOP_TERMS.search(clause) else ""
        for index, clause in enumerate(desktop_clauses)
    )
    text = re.sub(r"[（(]\s*inferred from damage numbers\s*[）)]", "（根据伤害数字推测）", text, flags=re.I)
    text = re.sub(r"damage numbers?", "伤害数字", text, flags=re.I)
    for term, replacement in _INTERNAL_TERMS.items():
        text = re.sub(rf"(?<![A-Za-z]){term}(?![A-Za-z])", replacement, text, flags=re.I)
    text = re.sub(
        r"\b[A-Za-z_][A-Za-z0-9_]*\s*[:=]\s*(?:[A-Za-z][A-Za-z0-9_-]*|\d+)",
        "",
        text,
    )
    text = re.sub(r"\b(?:[A-Za-z]+[-_][A-Za-z0-9_-]*|[A-Za-z]+\d+[A-Za-z0-9_-]*)\b", "", text)
    text = re.sub(r"\b[A-Za-z]+\b", "", text)
    text = re.sub(r"(?P<label>[\u4e00-\u9fff]{1,6})（\s*(?P=label)\s*）", r"\g<label>", text)
    text = text.replace("……", "").replace("…", "").replace("...", "")
    text = re.sub(r"['‘’\"]\s*['‘’\"]", "", text)
    text = re.sub(r"(?:未发生|没有发生|未检测到)(?:任何)?(?:点击|操作)(?:输入|事件|动作)?", "", text)
    # Keep the facts inside the HUD, but hide its implementation-facing
    # container label from planner copy.
    text = text.replace("状态栏显示", "").replace("状态栏", "区域")
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[，,；;。]\s*[，,；;。]+", "；", text)
    text = text.strip(" ，,；;。:：'‘’\"“”?!？！（）()")
    if re.search(r"数字快捷键(?:提示)?[^。；]*入口$", text):
        return ""
    return text if re.search(r"[\w\u4e00-\u9fff]", text) else ""


def _known_text(value: Any) -> str:
    """Keep visible facts while excluding speculative clauses and HUD-only evidence."""
    text = planner_board_text(value)
    if not text:
        return ""
    if "需要配置视觉模型" in text:
        return ""
    text = re.sub(
        r"[（(][^）)]*(?:待确认|未知|可能|推测|推断|无法确认|不确定)[^）)]*[）)]",
        "",
        text,
    )
    clauses = []
    for clause in re.split(r"[；;。]\s*", text):
        clause = clause.strip(" ，,；;。")
        if not clause or any(marker in clause for marker in _UNCERTAIN_MARKERS):
            continue
        if re.search(r"鼠标|光标|悬停", clause):
            continue
        if "状态栏" in clause:
            continue
        clauses.append(clause)
    return "；".join(clauses)


def _abstract_page_structure(value: Any) -> str:
    """Keep element/function concepts while removing screenshot transcription."""
    text = planner_board_text(value)
    text = re.sub(r"(?:鼠标光标|鼠标指针|鼠标|光标|悬停)[^，,；;。]*", "", text)
    text = re.sub(r"(?:标题为|标题)\s*[:：]?\s*[\"'“‘][^\"'”’]+[\"'”’]?", "", text)
    text = re.sub(r"[\"'“”‘’][^\"'“”‘’]+[\"'“”‘’]", "", text)
    text = re.sub(r"[（(][^）)]*\d[^）)]*[）)]", "", text)
    text = re.sub(r"\b\d{1,2}:\d{2}(?::\d{2})?\b", "", text)
    text = re.sub(r"(?<!第)\d+(?:\.\d+)?%?", "", text)
    text = re.sub(r"\bRoguelike\b", "随机成长", text, flags=re.I)
    # Visual responses often contain half-open parentheses. A page inventory
    # remains clearer when the explanatory phrase is flattened into plain text.
    text = re.sub(r"[（）()]", " ", text)
    text = re.sub(r"(?:标题为|标题)\s*[:：]?\s*(?=$|[，,。；;])", "", text)
    text = re.sub(r"(?:以及|和)\s*(?:的)?按钮(?=$|[，,。；;])", "", text)
    text = re.sub(r"[（(]\s*[、，,\s]*[）)]", "", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[，,、；;]\s*[，,、；;]+", "、", text)
    return text.strip(" ，,、；;。:：()（）")


def _split_top_level_once(value: str) -> tuple[str, str]:
    depth = 0
    for index, character in enumerate(value):
        if character in "（(":
            depth += 1
        elif character in "）)":
            depth = max(0, depth - 1)
        elif character in "，," and depth == 0:
            return value[:index], value[index + 1:]
    return value, ""


def _analysis_text(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("description") or value.get("text") or ""
    raw = str(value or "")
    latin_count = len(re.findall(r"[A-Za-z]", raw))
    han_count = len(re.findall(r"[\u4e00-\u9fff]", raw))
    # Some legacy visual responses are English sentences with a few quoted
    # Chinese UI labels. Stripping the English leaves punctuation and isolated
    # labels that look like corrupted planner copy. Treat the whole field as
    # unusable evidence instead of publishing those fragments.
    if latin_count >= 20 and latin_count > max(1, han_count):
        return ""
    return _known_text(value)


def _representative_fallback(
    stage: dict[str, Any], frames: dict[str, dict[str, Any]], field: str, *, reverse: bool = False,
) -> str:
    representatives = list(stage.get("representativeFrames") or [])
    if reverse:
        representatives.reverse()
    for representative in representatives:
        analysis = (frames.get(str(representative.get("frameId") or "")) or {}).get("analysis") or {}
        if text := _analysis_text(analysis.get(field)):
            return text
    return ""


def _page_title(stage: dict[str, Any], frames: dict[str, dict[str, Any]]) -> str:
    candidate = _known_text(stage.get("name"))
    mechanical = re.fullmatch(r"场景\s*\d+|确认第\s*\d+\s*步操作", candidate or "")
    action_title = bool(re.match(r"^(?:查看|确认|持续|操控|点击|选择|进入)", candidate or ""))
    if not candidate or mechanical or action_title or all(word in {"页面", "结果", "页面元素", "待确认"} for word in candidate.split()):
        for representative in stage.get("representativeFrames") or []:
            analysis = (frames.get(str(representative.get("frameId") or "")) or {}).get("analysis") or {}
            proposed = _analysis_text(analysis.get("what"))
            if proposed:
                candidate = proposed
                break
    candidate = re.sub(r"^(?:游戏内|游戏)?[‘'\"]?", "", candidate)
    candidate = re.split(r"[，,；;]", candidate, maxsplit=1)[0]
    candidate = re.sub(r"[（(](?:随机成长)?机制[）)]", "", candidate)
    candidate = re.sub(r"(?:模态)?弹窗界面$|(?<!主)界面$", "", candidate)
    candidate = candidate.replace("/", "或").translate(str.maketrans("", "", "'\"‘’")).strip()
    if "：" in candidate and len(candidate.split("：", 1)[0]) <= 12:
        candidate = candidate.split("：", 1)[0]
    if candidate.startswith("查看"):
        candidate = f"{candidate[2:]}页面"
    if candidate.endswith("进行中"):
        candidate = f"{candidate[:-3]}界面"
    if not candidate or re.fullmatch(r"(?:页面|结果|页面元素|待确认|\s)+", candidate):
        return "未命名页面"
    return candidate


def _transition_label(item: dict[str, Any]) -> str:
    raw_label = item.get("triggerLabel")
    explicit = _known_text(raw_label)
    if explicit and (
        not re.search(r"[\u4e00-\u9fff0-9]", explicit)
        or explicit in {"无明确操作", "未知待确认", "待确认", "系统自动进入"}
        or any(marker in explicit for marker in ("未进行显式", "根据游戏逻辑", "无法确定操作", "未检测到明确"))
    ):
        explicit = ""
    if explicit:
        return explicit
    if raw_label not in (None, ""):
        return ""
    return {
        "tap": "点击后",
        "click": "点击后",
        "long_press": "长按后",
        "swipe": "滑动后",
        "drag": "拖动后",
        "animation_end": "动画结束后",
        "media_end": "播放结束后",
        "timeout": "等待结束后",
        "condition_met": "满足条件后",
        "system_event": "系统自动进入",
    }.get(str(item.get("triggerType") or "").lower(), "")


def _group_title(field: str, text: str) -> str:
    """Derive a group heading from the page evidence instead of a fixed schema."""
    compact = re.sub(r"^(?:玩家)?(?:点击|选择|展示|显示|进入|从|在|后)", "", text).strip(" ，,；;。")
    if "返回" in text:
        return text[text.index("返回"):].strip(" ，,；;。")
    if "进入" in text:
        return text[text.index("进入"):].strip(" ，,；;。")
    if field == "trigger":
        if "升级" in text:
            return "升级操作"
        choice = re.search(r"选择(?:一个|一项)?(.+)", text)
        if choice:
            return f"选择{choice.group(1).strip(' ，,；;。')}"
    if field == "feedback":
        compact = re.sub(r"^(?:展示|显示)", "", text).strip(" ，,；;。")
    if field == "result":
        compact = re.sub(r"^.+?后", "", compact).strip(" ，,；;。")
    return compact or text


def _page_groups(record: dict[str, Any]) -> list[dict[str, Any]]:
    values = (
        ("entry", record["entry"]),
        ("trigger", record["trigger"]),
        ("feedback", record["feedback"]),
        ("result", record["result"]),
        ("exit", record["exit"]),
    )
    groups: list[dict[str, Any]] = []
    for field, text in values:
        if not text:
            continue
        title = _group_title(field, text)
        existing = next((group for group in groups if group["title"] == title), None)
        if existing:
            existing["items"].append({"text": text, "children": []})
        else:
            groups.append({"title": title, "items": [{"text": text, "children": []}]})
    return groups


def _atomic_facts(value: Any) -> list[str]:
    """Turn one reviewed rule field into planner-sized facts."""
    text = _known_text(value)
    if not text:
        return []
    return [part.strip(" ，,；;。") for part in re.split(r"[；;。]\s*", text) if part.strip(" ，,；;。")]


def _fact_key(value: str) -> str:
    return re.sub(r"[\s，,；;。:：()（）【】\[\]]+", "", value).lower()


def _damaged_or_placeholder(value: str) -> bool:
    return (
        not value
        or not bool(re.search(r"[\u4e00-\u9fff]", value))
        or bool(re.fullmatch(r"顶部信息\s*[-_/]*", value))
        or bool(re.search(r"[\uac00-\ud7af�]", value))
        # “战斗期间持续显示”“顶部显示关卡时间”是完整的页面规则，不能仅因
        # 以“显示”结尾就当成残句。这里只拦截确实悬空的连接词和动作词。
        or bool(re.search(r"(?:与|及|或|从|向|点击|进入|抽取器)$", value))
        or value.lower() in {"component", "页面元素", "区域", "待确认", "顶部信息", "顶部状态栏", "状态栏"}
    )


def _region_area(region: dict[str, Any]) -> tuple[str, int]:
    name = _known_text(region.get("name"))
    bounds = region.get("bounds") if isinstance(region.get("bounds"), dict) else {}
    try:
        x = float(bounds.get("x", 0.5))
        y = float(bounds.get("y", 0.5))
        width = float(bounds.get("width", 0.0))
        height = float(bounds.get("height", 0.0))
    except (TypeError, ValueError):
        x, y, width, height = 0.5, 0.5, 0.0, 0.0
    if "弹窗" in name or "浮层" in name:
        return "弹窗", 2
    if y + height <= 0.26:
        return "顶部区域（从左到右）", 0
    if y >= 0.72:
        return "底部区域（从左到右）", 4
    if x + width <= 0.27 and height >= 0.16:
        return "左侧区域（从上到下）", 1
    if x >= 0.73 and height >= 0.16:
        return "右侧区域（从上到下）", 3
    return "主要内容区（从上到下）", 2


def _region_groups(stage_ids: set[str], review: dict[str, Any]) -> list[dict[str, Any]]:
    """Build sample-aligned page copy: spatial element tree with attached functions."""
    regions = [
        region for region in review.get("regions") or []
        if isinstance(region, dict)
        and str(region.get("stageId") or "") in stage_ids
        and _confirmed(region)
    ]
    if not regions:
        return []

    def coordinate(region: dict[str, Any], key: str) -> float:
        bounds = region.get("bounds") if isinstance(region.get("bounds"), dict) else {}
        try:
            return float(bounds.get(key, 0.5))
        except (TypeError, ValueError):
            return 0.5

    regions.sort(key=lambda region: (_region_area(region)[1], coordinate(region, "y"), coordinate(region, "x"), int(region.get("displayOrder") or 0)))
    groups: list[dict[str, Any]] = []
    by_title: dict[str, dict[str, Any]] = {}
    seen_facts: set[str] = set()
    for region in regions:
        group_title, _ = _region_area(region)
        name = _known_text(region.get("name"))
        if _damaged_or_placeholder(name) or re.fullmatch(r"(?:页面)?区域\s*\d+", name):
            continue
        rule = region.get("rule") if isinstance(region.get("rule"), dict) else {}
        facts: list[str] = []
        for field in ("display", "condition", "action", "feedback", "result"):
            for fact in _atomic_facts(rule.get(field)):
                if _damaged_or_placeholder(fact):
                    continue
                key = _fact_key(fact)
                if key and key not in seen_facts:
                    seen_facts.add(key)
                    facts.append(fact)
        name_key = _fact_key(name)
        facts = [fact for fact in facts if _fact_key(fact) != name_key]
        item = {"text": name, "children": [{"text": fact, "children": []} for fact in facts]}
        bounds = region.get("bounds") if isinstance(region.get("bounds"), dict) else {}
        if region.get("id") and region.get("frameId") and all(key in bounds for key in ("x", "y", "width", "height")):
            item["cropIds"] = [str(region["id"])]
        group = by_title.get(group_title)
        if group is None:
            group = {"title": group_title, "items": []}
            by_title[group_title] = group
            groups.append(group)
        group["items"].append(item)
    return groups


def _valid_normalized_bounds(value: Any) -> dict[str, float] | None:
    if not isinstance(value, dict):
        return None
    try:
        bounds = {key: float(value[key]) for key in ("x", "y", "width", "height")}
    except (KeyError, TypeError, ValueError):
        return None
    if bounds["width"] <= 0 or bounds["height"] <= 0:
        return None
    if bounds["x"] < 0 or bounds["y"] < 0 or bounds["x"] + bounds["width"] > 1 or bounds["y"] + bounds["height"] > 1:
        return None
    return bounds


def _detail_crops(
    stage_ids: set[str], frame_ids: set[str], review: dict[str, Any], frames: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    crops = []
    for region in review.get("regions") or []:
        if not isinstance(region, dict) or not _confirmed(region):
            continue
        if str(region.get("stageId") or "") not in stage_ids:
            continue
        frame_id = str(region.get("frameId") or "")
        if frame_id not in frame_ids:
            continue
        title = _known_text(region.get("name"))
        bounds = _valid_normalized_bounds(region.get("bounds"))
        if _damaged_or_placeholder(title) or re.fullmatch(r"(?:页面)?区域\s*\d+", title) or bounds is None:
            continue
        rule = region.get("rule") if isinstance(region.get("rule"), dict) else {}
        facts = [fact for field in ("display", "condition", "action", "feedback", "result") for fact in _atomic_facts(rule.get(field))]
        if not facts:
            continue
        group_title, _ = _region_area(region)
        frame = frames.get(frame_id) or {}
        crops.append({
            "id": str(region.get("id") or f"crop-{len(crops) + 1}"),
            "frameId": frame_id,
            "title": title,
            "description": "；".join(dict.fromkeys(facts[:3])),
            "bounds": bounds,
            "groupTitle": group_title,
            "sourceWidth": _source_dimension(frame, "sourceWidth", "width"),
            "sourceHeight": _source_dimension(frame, "sourceHeight", "height"),
        })
    if crops:
        return crops
    for frame_id in frame_ids:
        frame = frames.get(frame_id) or {}
        analysis = frame.get("analysis") if isinstance(frame.get("analysis"), dict) else {}
        region_structure = analysis.get("regionStructure") if isinstance(analysis.get("regionStructure"), dict) else {}
        modal = next((region_structure.get(key) for key in ("modal", "popup", "dialog") if isinstance(region_structure.get(key), (dict, str))), None)
        if modal is None:
            modal = next((
                value for value in region_structure.values()
                if isinstance(value, (dict, str))
                and any(word in planner_board_text(value) for word in ("候选", "选项", "选择面板", "九宫格", "抽取武器"))
            ), None)
        structure = frame.get("structure") if isinstance(frame.get("structure"), dict) else {}
        if modal is None or int(structure.get("elementCount") or 0) < 8:
            continue
        width, height = structure.get("width"), structure.get("height")
        if not isinstance(width, (int, float)) or width <= 0 or not isinstance(height, (int, float)) or height <= 0:
            continue
        boxes = [item.get("bbox") for item in structure.get("elements") or [] if isinstance(item, dict) and item.get("class") == "component"]
        boxes = [box for box in boxes if isinstance(box, list) and len(box) == 4 and all(isinstance(value, (int, float)) for value in box)]
        boxes = [
            box for box in boxes
            if 0.08 <= (box[0] + box[2]) / 2 / width <= 0.92
            and 0.15 <= (box[1] + box[3]) / 2 / height <= 0.85
            and (box[2] - box[0]) * (box[3] - box[1]) < width * height * 0.35
        ]
        if not boxes:
            continue
        left, top = min(box[0] for box in boxes), min(box[1] for box in boxes)
        right, bottom = max(box[2] for box in boxes), max(box[3] for box in boxes)
        pad_x, pad_y = width * 0.03, height * 0.025
        left, top = max(0, left - pad_x), max(0, top - pad_y)
        right, bottom = min(width, right + pad_x), min(height, bottom + pad_y)
        if (right - left) / width >= 0.94 or (bottom - top) / height >= 0.94:
            continue
        modal_text = planner_board_text(modal)
        title = next((word for word in ("选择武器", "抽取武器", "技能选择", "天赋选择", "强化选择") if word in modal_text), "弹窗")
        if isinstance(modal, dict):
            title = _abstract_page_structure(modal.get("title") or modal.get("name") or title) or title
        crops.append({
            "id": f"auto-crop-{frame_id}", "frameId": frame_id, "title": f"{title}局部说明",
            "description": f"用于核对{title}中的选项、操作入口与反馈状态。",
            "bounds": {"x": left / width, "y": top / height, "width": (right - left) / width, "height": (bottom - top) / height},
            "groupTitle": "弹窗", "sourceWidth": width, "sourceHeight": height,
        })
        if len(crops) >= 2:
            break
    return crops


def _frame_state_title(frame: dict[str, Any]) -> str:
    analysis = frame.get("analysis") if isinstance(frame.get("analysis"), dict) else {}
    title = _analysis_text(analysis.get("what"))
    if not title:
        return ""
    title = re.split(r"[，,；;]", title, maxsplit=1)[0]
    title = title.translate(str.maketrans("", "", "'\"‘’")).replace("/", "或").strip()
    return title


def _page_subflow(page_id: str, screenshots: list[dict[str, Any]], frames: dict[str, dict[str, Any]], label: str) -> dict[str, Any] | None:
    candidates = []
    for screenshot in screenshots:
        frame_id = str(screenshot.get("frameId") or "")
        title = _frame_state_title(frames.get(frame_id) or {})
        if title:
            candidates.append((frame_id, title))
    if len(candidates) < 2 or len({title for _, title in candidates}) < 2:
        return None
    states = [
        {"id": f"{page_id}-state-{index}", "frameId": frame_id, "title": title, "order": index}
        for index, (frame_id, title) in enumerate(candidates, 1)
    ]
    steps = [
        {
            "id": f"{page_id}-step-{index}",
            "sourceStateId": states[index - 1]["id"],
            "targetStateId": states[index]["id"],
            "label": label or "继续",
        }
        for index in range(1, len(states))
    ]
    return {"states": states, "steps": steps}


_STRUCTURE_AREAS = {
    "header": ("顶部区域（从左到右）", 0),
    "top": ("顶部区域（从左到右）", 0),
    "sidebar-left": ("左侧区域（从上到下）", 1),
    "left": ("左侧区域（从上到下）", 1),
    "main-playfield": ("主要内容区（从上到下）", 2),
    "main": ("主要内容区（从上到下）", 2),
    "content": ("主要内容区（从上到下）", 2),
    "hud-overlay": ("主要内容区（从上到下）", 2),
    "overlay": ("弹窗", 2),
    "modal": ("弹窗", 2),
    "sidebar-right": ("右侧区域（从上到下）", 3),
    "right": ("右侧区域（从上到下）", 3),
    "control-bar-bottom": ("底部区域（从左到右）", 4),
    "footer": ("底部区域（从左到右）", 4),
    "bottom": ("底部区域（从左到右）", 4),
}


def _nested_structure_items(value: Any) -> list[dict[str, Any]]:
    """Convert visual-model objects into planner copy without exposing JSON keys."""
    if isinstance(value, (list, tuple)):
        items: list[dict[str, Any]] = []
        for child in value:
            items.extend(_nested_structure_items(child))
        return items
    if isinstance(value, dict):
        description = _abstract_page_structure(value.get("description") or value.get("title") or value.get("name") or "")
        elements = value.get("elements") or value.get("items") or value.get("children") or []
        if elements and (not description or description in {"顶部区域", "底部区域", "左侧区域", "右侧区域", "主要内容区"}):
            return _nested_structure_items(elements)
        if description:
            return [{"text": description, "children": _nested_structure_items(elements)}]
        items = []
        for child in value.values():
            items.extend(_nested_structure_items(child))
        return items
    text = _abstract_page_structure(value)
    if not text or _damaged_or_placeholder(text):
        return []
    return [{"text": text, "children": []}]


def _structure_groups(frame_ids: list[str], frames: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    order_by_title: dict[str, int] = {}
    seen: set[str] = set()
    for frame_id in frame_ids:
        analysis = (frames.get(frame_id) or {}).get("analysis") or {}
        structure = analysis.get("regionStructure") if isinstance(analysis.get("regionStructure"), dict) else {}
        for raw_key, raw_value in structure.items():
            key = str(raw_key or "").strip().lower()
            group_title, order = _STRUCTURE_AREAS.get(key, ("主要内容区（从上到下）", 2))
            if isinstance(raw_value, (dict, list, tuple)):
                group = grouped.setdefault(group_title, {"title": group_title, "items": []})
                order_by_title[group_title] = order
                for item in _nested_structure_items(raw_value):
                    item_key = _fact_key(item["text"])
                    if not item_key or item_key in seen:
                        continue
                    seen.add(item_key)
                    unique_children = []
                    for child in item.get("children") or []:
                        child_key = _fact_key(child["text"])
                        if child_key and child_key not in seen:
                            seen.add(child_key)
                            unique_children.append(child)
                    group["items"].append({"text": item["text"], "children": unique_children})
                continue
            # Page specifications need side/top/bottom element descriptions; avoid
            # the generic HUD label while retaining the actual visible elements.
            text = _abstract_page_structure(str(raw_value or "").replace("状态栏", "区域"))
            if _damaged_or_placeholder(text):
                continue
            item_title, detail_text = _split_top_level_once(text)
            item_title = item_title.strip(" ：:")
            detail_text = re.sub(r"^(?:包含|显示|提供|排列有)\s*", "", detail_text)
            children = [
                child.strip(" ，,、；;。")
                for child in re.split(r"[、；;]", detail_text)
                if child.strip(" ，,、；;。") and child.strip(" ，,、；;。") not in {"分别标记", "包含", "显示"}
            ]
            title_key = _fact_key(item_title)
            if not title_key or title_key in seen:
                continue
            seen.add(title_key)
            unique_children = []
            for child in children:
                child_key = _fact_key(child)
                if child_key and child_key not in seen:
                    seen.add(child_key)
                    unique_children.append({"text": child, "children": []})
            group = grouped.setdefault(group_title, {"title": group_title, "items": []})
            order_by_title[group_title] = order
            group["items"].append({"text": item_title, "children": unique_children})
    return sorted(grouped.values(), key=lambda group: order_by_title[group["title"]])


def _planner_page_purpose(title: str, observed: Any) -> str:
    """Turn an observed state into the page-level purpose used by planners."""
    clean_title = planner_board_text(title)
    if any(word in clean_title for word in ("升级", "强化", "词条", "武器选择", "技能选择")):
        return "供玩家查看候选强化并完成选择"
    if "首领" in clean_title or "Boss" in clean_title:
        return "供玩家查看首领战状态并进行战斗操作"
    if any(word in clean_title for word in ("战斗", "关卡", "游戏主界面")):
        return "供玩家查看战斗状态并进行局内操作"
    purpose = _abstract_page_structure(observed)
    if purpose and not re.search(r"受到攻击|产生伤害|血量为|位于底部|显示伤害数字", purpose):
        return purpose
    subject = re.sub(r"(?:页面|界面)$", "", clean_title).strip()
    return f"供玩家查看{subject}并完成对应操作" if subject else "供玩家查看当前状态并完成对应操作"


def _page_context_groups(records: list[dict[str, Any]], merged: dict[str, str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    purposes = []
    seen: set[str] = set()
    for record in records:
        purpose = _planner_page_purpose(str(record.get("title") or ""), record.get("purpose"))
        key = _fact_key(purpose)
        if purpose and key and key not in seen:
            seen.add(key)
            purposes.append({"text": f"页面用途：{purpose}", "children": []})
    if not purposes and records:
        title = planner_board_text(records[0].get("title"))
        subject = re.sub(r"(?:页面|界面)$", "", title).strip()
        if subject:
            purposes.append({"text": f"页面用途：供玩家查看{subject}", "children": []})
    page_info = [{"title": "页面信息", "items": purposes}] if purposes else []

    labels = (
        ("entry", "显示时机"),
        ("trigger", "可进行的操作"),
        ("feedback", "操作后的变化"),
        ("result", "完成后的状态"),
        ("exit", "离开方式"),
    )
    functions = []
    seen.clear()
    for field, label in labels:
        text = _abstract_page_structure(merged.get(field))
        if text in {"已确认触发", "已确认反馈", "已确认内容", "已确认条件", "已确认结果"}:
            continue
        key = _fact_key(text)
        if not text or not key or key in seen:
            continue
        seen.add(key)
        functions.append({"text": f"{label}：{text}", "children": []})
    function_groups = [{"title": "功能说明", "items": functions}] if functions else []
    return page_info, function_groups


def _planner_reading_group(merged: dict[str, str], layout_groups: list[dict[str, Any]]) -> dict[str, Any]:
    labels = (("entry", "进入条件"), ("trigger", "玩家操作"), ("feedback", "系统反馈"), ("result", "状态保留"), ("exit", "离开方式"))
    # This is a reading index. Repeating the same dynamic rule here made one
    # confirmed fact appear twice in the exported page.
    fallback = {
        "entry": "由相邻页面关系进入",
        "trigger": "按本页可操作内容执行",
        "feedback": "系统反馈与画面变化同步出现",
        "result": "保留操作完成后的页面状态",
        "exit": "按页面关系返回或进入下一页",
    }
    items = [{"text": f"{label}：{fallback[field]}", "children": []} for field, label in labels]
    region_names = "、".join(re.sub(r"[（(][^）)]*[）)]", "", group.get("title") or "") for group in layout_groups if group.get("title"))
    items.insert(1, {"text": f"区域与元素：{region_names or '按页面画面展示'}", "children": []})
    return {"title": "完整策划阅读", "items": items}


def _dedupe_function_groups(function_groups: list[dict[str, Any]], content_groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    visible = {
        _fact_key(str(item.get("text") or ""))
        for group in content_groups
        for item in group.get("items") or []
        if isinstance(item, dict)
    }
    result = []
    for group in function_groups:
        items = []
        for item in group.get("items") or []:
            value = str(item.get("text") or "")
            content = value.split("：", 1)[1] if "：" in value else value
            if _fact_key(content) not in visible:
                items.append(item)
        if items:
            result.append({**group, "items": items})
    return result


def _stage_record(stage: dict[str, Any], frames: dict[str, dict[str, Any]]) -> dict[str, Any]:
    loop = stage.get("smallLoop") or {}
    values = (stage.get("entryCondition"), stage.get("exitCondition"), loop.get("trigger"), loop.get("feedback"), loop.get("result"))
    use_representative_fallback = not any(_known_text(value) for value in values)
    entry = _known_text(stage.get("entryCondition"))
    exit_condition = _known_text(stage.get("exitCondition"))
    trigger = _known_text(loop.get("trigger"))
    feedback = _known_text(loop.get("feedback"))
    result = _known_text(loop.get("result"))
    if use_representative_fallback:
        entry = _representative_fallback(stage, frames, "beforeState")
        exit_condition = _representative_fallback(stage, frames, "afterState", reverse=True)
        trigger = _representative_fallback(stage, frames, "userAction")
        feedback = _representative_fallback(stage, frames, "systemResponse")
        result = _representative_fallback(stage, frames, "afterState", reverse=True)
    return {
        "stageId": str(stage.get("id") or ""),
        "title": _page_title(stage, frames),
        "purpose": _known_text(stage.get("objective")),
        "state": _known_text(stage.get("pageState") or stage.get("state") or stage.get("status")),
        "entry": entry,
        "trigger": trigger,
        "feedback": feedback,
        "result": result,
        "exit": exit_condition,
        "frameIds": [str(item.get("frameId")) for item in stage.get("representativeFrames") or [] if item.get("frameId")],
        "sourceFrameIds": [str(frame_id) for frame_id in stage.get("sourceFrameIds") or [] if frame_id],
        "humanEdited": bool(set(stage.get("humanEditedFields") or []) & {"name", "objective", "purpose", "pageName"}),
    }


def _source_dimension(frame: dict[str, Any], source_key: str, fallback_key: str) -> int:
    structure = frame.get("structure") if isinstance(frame.get("structure"), dict) else {}
    for value in (frame.get(source_key), frame.get(fallback_key), structure.get(fallback_key)):
        if type(value) is int and value > 0:
            return value
    return 0


def _frame_image_url(frame: dict[str, Any]) -> str:
    return str(frame.get("imageUrl") or frame.get("imagePath") or "").strip()


def _screenshots(frame_ids: list[str], frames: dict[str, dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return image data plus trace-only source references; neither is planner copy."""
    screenshots = []
    refs = []
    for frame_id in frame_ids:
        frame = frames.get(frame_id) or {}
        image_url = _frame_image_url(frame)
        if not frame or not image_url:
            continue
        screenshots.append({
            "frameId": frame_id,
            "imageUrl": image_url,
            "sequenceIndex": frame.get("sequenceIndex"),
            "sourceWidth": _source_dimension(frame, "sourceWidth", "width"),
            "sourceHeight": _source_dimension(frame, "sourceHeight", "height"),
        })
        refs.append({"type": "frame", "frameId": frame_id})
    return screenshots, refs


def _semantic_frame_ids(record: dict[str, Any], frames: dict[str, dict[str, Any]]) -> list[str]:
    def repair(value: Any) -> str:
        text = str(value or "")
        def run(match: re.Match[str]) -> str:
            try:
                return match.group(0).encode("latin-1").decode("utf-8")
            except (UnicodeEncodeError, UnicodeDecodeError):
                return match.group(0)
        return re.sub(r"[\x80-\xff]{2,}", run, text)
    title = planner_board_text(repair(record.get("title")))
    keywords = re.findall(r"[\u4e00-\u9fff]{2}", title)
    matched = []
    reliable: list[str] = []
    for frame_id in record.get("frameIds") or []:
        frame = frames.get(str(frame_id)) or {}
        analysis = frame.get("analysis") if isinstance(frame.get("analysis"), dict) else {}
        evidence = planner_board_text(repair(analysis.get("pageName") or analysis.get("what") or analysis.get("purpose")))
        if evidence:
            reliable.append(evidence)
        if evidence and any(token in evidence or all(char in evidence for char in token) for token in keywords):
            matched.append(str(frame_id))
    if matched:
        return matched
    original = [str(frame_id) for frame_id in record.get("frameIds") or [] if _frame_image_url(frames.get(str(frame_id)) or {})]
    if record.get("humanEdited") or not reliable:
        return original
    def category(text: str) -> str:
        for name, terms in (
            ("选择", ("选择", "强化", "升级", "候选")),
            ("战斗", ("战斗", "攻击", "敌人", "伤害")),
            ("抽取", ("抽取", "九宫格", "老虎机")),
            ("首领", ("首领", "Boss")),
            ("结算", ("结算", "胜利", "失败", "奖励")),
        ):
            if any(term in text for term in terms):
                return name
        return ""
    # A conflicting legacy frame analysis is not sufficient evidence to erase
    # a confirmed page.  When one of several frames matches we still select it
    # above; otherwise retain the confirmed material and let the review UI flag
    # the mismatch instead of silently deleting the page.
    return original


def _notes_for_page(stage_ids: set[str], review: dict[str, Any]) -> list[dict[str, str]]:
    notes = []
    def add(value: Any, *, require_decision: bool = False) -> None:
        text = planner_board_text(value)
        technical = any(marker in text for marker in ("解析失败", "请求失败", "技术失败", "模型失败", "JSON"))
        generic_uncertainty = text in {"待确认", "未知待确认", "未知", "无法确认", "不确定"} or text.startswith(("可能", "推测", "疑似", "无法确认"))
        decision = bool(re.search(r"是否|何时|何种|哪种|哪一|如何|多久|时长|范围|条件|规则|状态|保留|清空|返回|退出|关闭|确认", text))
        if text and not technical and not generic_uncertainty and (not require_decision or decision):
            notes.append({"text": text})

    for item in review.get("crossStateConstraints") or []:
        if not isinstance(item, dict) or str(item.get("stageId") or "") not in stage_ids:
            continue
        add(item.get("text"))
        for unknown in item.get("unknowns") or []:
            add(unknown, require_decision=True)
    for item in [*(review.get("stages") or []), *(review.get("components") or [])]:
        if not isinstance(item, dict):
            continue
        stage_id = str(item.get("stageId") or item.get("id") or "")
        if stage_id not in stage_ids:
            continue
        for unknown in item.get("unknowns") or []:
            add(unknown, require_decision=True)
    return notes


def _global_notes(review: dict[str, Any]) -> list[dict[str, str]]:
    notes: list[dict[str, str]] = []

    def add(value: Any, *, require_decision: bool = False) -> None:
        text = planner_board_text(value)
        technical = any(marker in text for marker in ("解析失败", "请求失败", "技术失败", "模型失败", "JSON"))
        generic_uncertainty = text in {"待确认", "未知待确认", "未知", "无法确认", "不确定"} or text.startswith(("可能", "推测", "疑似", "无法确认"))
        decision = bool(re.search(r"是否|何时|何种|哪种|哪一|如何|多久|时长|范围|条件|规则|状态|保留|清空|返回|退出|关闭|确认", text))
        if text and not technical and not generic_uncertainty and (not require_decision or decision):
            notes.append({"text": text})

    for item in review.get("crossStateConstraints") or []:
        if not isinstance(item, dict) or str(item.get("stageId") or ""):
            continue
        add(item.get("text"))
        for unknown in item.get("unknowns") or []:
            add(unknown, require_decision=True)
    return notes


def _page_attribute_groups(frame_ids: list[str], frames: dict[str, dict[str, Any]], review: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract only explicit, screenshot-backed attributes for the planning board."""
    buckets: dict[str, list[str]] = {
        "关卡状态与资源": [], "生存属性": [], "武器与强化属性": [], "规则信息": [],
    }
    seen: set[str] = set()

    def add(group: str, value: Any) -> None:
        text = planner_board_text(value)
        key = _fact_key(text)
        if not text or _damaged_or_placeholder(text) or not key or key in seen:
            return
        seen.add(key)
        buckets[group].append(text)

    def classify(value: Any, preferred: str = "") -> None:
        text = planner_board_text(value)
        if not text:
            return
        if preferred:
            add(preferred, text); return
        if re.search(r"生命|血量|护盾|减伤|生存", text):
            add("生存属性", text)
        elif re.search(r"武器|喷射|炮|伤害|范围|频率|等级|强化|攻击", text):
            add("武器与强化属性", text)
        elif re.search(r"时间|倒计时|进度|次数|资源|货币|关卡", text):
            add("关卡状态与资源", text)
        else:
            add("规则信息", text)

    def walk_component(component: Any) -> None:
        if isinstance(component, list):
            for item in component:
                walk_component(item)
            return
        if not isinstance(component, dict):
            return
        kind = str(component.get("type") or "")
        title = planner_board_text(component.get("title") or component.get("label"))
        description = planner_board_text(component.get("description") or component.get("subtext") or component.get("content"))
        if kind == "OptionCard" and title:
            add("武器与强化属性", f"{title} - {description}" if description else title)
        elif description:
            classify(description)
        for key in ("children", "items", "options"):
            walk_component(component.get(key))

    review_sources = review.get("sources") if isinstance(review.get("sources"), dict) else {}
    for frame_id in frame_ids:
        frame = frames.get(frame_id) or {}
        analysis = frame.get("analysis") if isinstance(frame.get("analysis"), dict) else {}
        walk_component(analysis.get("components"))
        for rule in analysis.get("rules") or []:
            classify(rule, "规则信息")
        classify(analysis.get("gameMechanics"), "规则信息")
        source = review_sources.get(frame_id) if isinstance(review_sources.get(frame_id), dict) else {}
        for item in source.get("secondaryInformation") or []:
            classify(item)
    return [{"title": title, "items": [{"text": text, "children": []} for text in items]} for title, items in buckets.items() if items]


def _dict_items(value: Any) -> list[dict[str, Any]]:
    """Return only mapping entries from a schema collection, never coercing data."""
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _legacy_page_records(job: dict[str, Any]) -> list[dict[str, Any]]:
    """Translate pre-review planning output into the canonical page-spec input.

    This is deliberately a read-only compatibility layer: historic jobs retain
    their planning model while every current renderer receives only pages.
    """
    planning = job.get("planningModel") if isinstance(job.get("planningModel"), dict) else {}
    records: list[dict[str, Any]] = []
    for index, event in enumerate(_dict_items(planning.get("events")), 1):
        frame_ids = [
            str(item.get("sourceId") or "")
            for item in _dict_items(event.get("evidence"))
            if item.get("sourceId")
        ]
        records.append({
            "id": f"legacy-{str(event.get('id') or f'EVENT-{index:03d}')}",
            "sourceId": str(event.get("id") or f"EVENT-{index:03d}"),
            "sceneId": str(event.get("sceneId") or ""),
            "sourceTransitionId": str(event.get("sourceTransitionId") or event.get("transitionId") or ""),
            "targetId": str(event.get("targetEventId") or event.get("targetPageId") or event.get("targetStageId") or ""),
            "resultType": str(event.get("resultType") or ""),
            "direction": str(event.get("direction") or ""),
            "title": _known_text(event.get("afterState") or event.get("response") or event.get("action")) or "历史页面",
            "entry": _known_text(event.get("beforeState")),
            "trigger": _known_text(event.get("action") or event.get("trigger")),
            "feedback": _known_text(event.get("response")),
            "result": _known_text(event.get("afterState")),
            "exit": "",
            "frameIds": frame_ids,
        })
    if records:
        return records

    hierarchy = planning.get("loopHierarchy")
    if not isinstance(hierarchy, dict):
        return records
    for large in _dict_items(hierarchy.get("largeLoops")):
        for stage in _dict_items(large.get("stages")):
            for small in _dict_items(stage.get("smallLoops")):
                for step in _dict_items(small.get("steps")):
                    index = len(records) + 1
                    frame_ids = [
                        str(item.get("sourceId") or "")
                        for item in _dict_items(step.get("evidence"))
                        if item.get("sourceId")
                    ]
                    records.append({
                        "id": f"legacy-STEP-{index:03d}",
                        "sourceId": str(step.get("id") or f"STEP-{index:03d}"),
                        "sceneId": str(step.get("sceneId") or stage.get("id") or ""),
                        "sourceTransitionId": str(step.get("sourceTransitionId") or step.get("transitionId") or ""),
                        "targetId": str(step.get("targetStepId") or step.get("targetPageId") or step.get("targetStageId") or ""),
                        "resultType": str(step.get("resultType") or ""),
                        "direction": str(step.get("direction") or ""),
                        "title": _known_text(step.get("title") or stage.get("title")) or "历史页面",
                        "entry": _known_text(stage.get("title")),
                        "trigger": _known_text(step.get("userAction") or step.get("action")),
                        "feedback": _known_text(step.get("systemResponse") or step.get("response")),
                        "result": _known_text(step.get("resultState") or step.get("afterState")),
                        "exit": "",
                        "frameIds": frame_ids,
                    })
    return records


def _legacy_page_specs(job: dict[str, Any], frames: dict[str, dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    records = _legacy_page_records(job)
    pages: list[dict[str, Any]] = []
    retained: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for record in records:
        screenshots = []
        source_refs = []
        for frame_id in dict.fromkeys(record["frameIds"]):
            frame = frames.get(frame_id)
            if not frame:
                continue
            image_url = _frame_image_url(frame)
            if not image_url:
                continue
            screenshots.append({
                "frameId": frame_id,
                "imageUrl": image_url,
                "sequenceIndex": frame.get("sequenceIndex"),
                "sourceWidth": _source_dimension(frame, "sourceWidth", "width"),
                "sourceHeight": _source_dimension(frame, "sourceHeight", "height"),
            })
            source_refs.append({"type": "frame", "frameId": frame_id})
        if screenshots:
            page = {
                "id": record["id"], "title": record["title"], "screenshots": screenshots,
                "groups": _page_groups(record), "notes": [], "sourceRefs": source_refs,
            }
            pages.append(page)
            retained.append((page, record))
    relations = []
    for page, record in retained:
        target_id = str(record.get("targetId") or "")
        if not target_id:
            continue
        target = next((
            candidate_page
            for candidate_page, candidate_record in retained
            if candidate_page["id"] != page["id"]
            and target_id in {
                candidate_page["id"],
                str(candidate_record.get("sourceId") or ""),
                str(candidate_record.get("sceneId") or ""),
            }
        ), None)
        if target is None:
            continue
        relation_source_id = str(record.get("sourceTransitionId") or record.get("sourceId") or len(relations) + 1)
        returning = str(record.get("resultType") or "") in {"return", "close_overlay", "loop"} or record.get("direction") == "return"
        relations.append({
            "id": f"legacy-relation-{relation_source_id}",
            "sourcePageId": page["id"],
            "targetPageId": target["id"],
            "label": _known_text(record.get("trigger")) or "继续",
            "lineStyle": "dashed" if returning else "solid",
        })
    return pages, relations


def _annotate_page_topology(pages: list[dict[str, Any]], relations: list[dict[str, Any]]) -> None:
    """Attach a stable tree projection without changing the confirmed page order."""
    page_ids = [str(page.get("id") or "") for page in pages]
    page_set = set(page_ids)
    parent: dict[str, str] = {}
    for relation in relations:
        if relation.get("lineStyle") == "dashed":
            continue
        source = str(relation.get("sourcePageId") or "")
        target = str(relation.get("targetPageId") or "")
        if source in page_set and target in page_set and source != target and target not in parent:
            parent[target] = source
    children: dict[str, list[str]] = {page_id: [] for page_id in page_ids}
    for child, parent_id in parent.items():
        children[parent_id].append(child)

    depth: dict[str, int] = {}
    def resolve_depth(page_id: str, trail: set[str] | None = None) -> int:
        if page_id in depth:
            return depth[page_id]
        trail = set(trail or ())
        if page_id in trail or page_id not in parent:
            depth[page_id] = 0
            return 0
        trail.add(page_id)
        depth[page_id] = resolve_depth(parent[page_id], trail) + 1
        return depth[page_id]
    for page_id in page_ids:
        resolve_depth(page_id)

    columns: dict[str, float] = {}
    next_column = 0.0
    def place(page_id: str) -> float:
        nonlocal next_column
        if page_id in columns:
            return columns[page_id]
        child_ids = children.get(page_id) or []
        if child_ids:
            child_columns = [place(child_id) for child_id in child_ids]
            columns[page_id] = sum(child_columns) / len(child_columns)
        else:
            columns[page_id] = next_column
            next_column += 1.0
        return columns[page_id]
    roots = [page_id for page_id in page_ids if page_id not in parent]
    parallel_roots = len(roots) > 1
    for root in roots:
        place(root)
    for page_id in page_ids:
        place(page_id)

    for page in pages:
        page_id = str(page.get("id") or "")
        page["topology"] = {
            "parentPageId": parent.get(page_id, ""),
            "depth": depth.get(page_id, 0),
            "column": columns.get(page_id, 0.0),
            "branching": parallel_roots or len(children.get(page_id) or []) > 1,
        }


def build_planning_board_model(job: dict) -> dict:
    review = job.get("reviewModel") if isinstance(job.get("reviewModel"), dict) else {}
    global_notes = _global_notes(review)
    has_modern_stage_contract = isinstance(review.get("stages"), list)
    stages = sorted(
        (item for item in review.get("stages") or [] if isinstance(item, dict) and _confirmed(item)),
        key=lambda item: (item.get("order", 0), str(item.get("id") or "")),
    )
    frames = {str(item.get("id") or ""): item for item in job.get("frames") or [] if isinstance(item, dict)}
    stage_records = [_stage_record(stage, frames) for stage in stages]
    represented_frame_ids = {
        frame_id
        for record in stage_records
        for frame_id in record["frameIds"]
        if _frame_image_url(frames.get(frame_id) or {})
    }
    for record in stage_records:
        valid_representatives = [
            frame_id for frame_id in record["frameIds"]
            if _frame_image_url(frames.get(frame_id) or {})
        ]
        if not valid_representatives:
            continue
        supplemental = [
            frame_id for frame_id in record.pop("sourceFrameIds", [])
            if frame_id not in represented_frame_ids and _frame_image_url(frames.get(frame_id) or {})
        ]
        record["frameIds"] = list(dict.fromkeys([*valid_representatives, *supplemental]))

    if not stage_records and not has_modern_stage_contract:
        pages, relations = _legacy_page_specs(job, frames)
        _annotate_page_topology(pages, relations)
        return {"pages": pages, "relations": relations, "notes": global_notes, "showUeMarkers": False}

    pages: list[dict[str, Any]] = []
    page_by_stage: dict[str, str] = {}
    for record in stage_records:
        record["frameIds"] = _semantic_frame_ids(record, frames)
        if not record["frameIds"]:
            continue
        previous = pages[-1] if pages else None
        purposes = previous["_purposes"] if previous else set()
        states = previous["_states"] if previous else set()
        same_purpose = bool(record["purpose"] and record["purpose"] in purposes)
        same_state = bool(record["state"] and record["state"] in states)
        purpose_conflict = bool(record["purpose"] and purposes and record["purpose"] not in purposes)
        state_conflict = bool(record["state"] and states and record["state"] not in states)
        if (
            previous
            and previous["title"] == record["title"]
            and (same_purpose or same_state)
            and not purpose_conflict
            and not state_conflict
        ):
            page = previous
            page["_records"].append(record)
            if record["purpose"]:
                page["_purposes"].add(record["purpose"])
            if record["state"]:
                page["_states"].add(record["state"])
        else:
            page = {
                "id": record["stageId"],
                "title": record["title"],
                "_purposes": {record["purpose"]} if record["purpose"] else set(),
                "_states": {record["state"]} if record["state"] else set(),
                "_records": [record],
            }
            pages.append(page)
        page_by_stage[record["stageId"]] = page["id"]

    all_notes = list(global_notes)
    for page in pages:
        records = page.pop("_records")
        page.pop("_purposes")
        page.pop("_states")
        frame_ids = list(dict.fromkeys(frame_id for record in records for frame_id in record["frameIds"]))
        screenshots, source_refs = _screenshots(frame_ids, frames)
        merged = {key: "；".join(record[key] for record in records if record[key]) for key in ("entry", "trigger", "feedback", "result", "exit")}
        stage_ids = {record["stageId"] for record in records}
        page_info, function_groups = _page_context_groups(records, merged)
        layout_groups = _region_groups(stage_ids, review) or _structure_groups(frame_ids, frames)
        if layout_groups:
            content_groups = layout_groups
        else:
            content_groups = _page_groups(merged)
        visible_keys = {
            _fact_key(str(item.get("text") or ""))
            for group in content_groups
            for item in group.get("items") or []
            if isinstance(item, dict)
        }
        attribute_groups = []
        for group in _page_attribute_groups(frame_ids, frames, review):
            items = [item for item in group["items"] if _fact_key(item["text"]) not in visible_keys]
            if items:
                visible_keys.update(_fact_key(item["text"]) for item in items)
                attribute_groups.append({**group, "items": items})
        function_groups = _dedupe_function_groups(function_groups, content_groups)
        reading_items = _planner_reading_group(merged, layout_groups)["items"]
        if function_groups:
            function_groups[0]["items"].extend(reading_items)
        elif content_groups:
            content_groups[-1]["items"].extend(reading_items)
        else:
            page_info = [*page_info, {"title": "页面说明", "items": reading_items}]
        groups = [*page_info, *content_groups, *attribute_groups, *function_groups]
        detail_crops = _detail_crops(stage_ids, set(frame_ids), review, frames)
        screenshot_details = []
        for frame_id in frame_ids:
            frame = frames.get(frame_id) or {}
            analysis = frame.get("analysis") if isinstance(frame.get("analysis"), dict) else {}
            title = planner_board_text(analysis.get("what") or analysis.get("pageName") or _frame_state_title(frame))
            screenshot_details.append({
                "frameId": frame_id,
                "title": title or "补充画面",
                "groups": _structure_groups([frame_id], frames),
            })
        subflow = _page_subflow(str(page["id"]), screenshots, frames, merged.get("trigger") or "")
        page_notes = _notes_for_page({record["stageId"] for record in records}, review)
        page.update({
            "screenshots": screenshots,
            "groups": groups,
            "screenshotDetails": screenshot_details,
            "detailCrops": detail_crops,
            "notes": page_notes,
            "sourceRefs": source_refs,
        })
        if subflow is not None:
            page["subflow"] = subflow
        all_notes.extend({"pageId": page["id"], **note} for note in page_notes)

    visible_page_ids = {page["id"] for page in pages}
    relations = []
    for item in sorted(review.get("transitions") or [], key=lambda row: str(row.get("id") or "")):
        if not isinstance(item, dict) or not item.get("included") or not _confirmed(item):
            continue
        source_page_id = page_by_stage.get(str(item.get("sourceStageId") or ""))
        target_page_id = page_by_stage.get(str(item.get("targetStageId") or ""))
        label = _transition_label(item)
        uncertain_sequence = not label and str(item.get("targetBasis") or "") == "sequence_candidate"
        if uncertain_sequence:
            label = "素材顺序（触发条件待确认）"
        if not source_page_id or not target_page_id or source_page_id == target_page_id or not label:
            continue
        if source_page_id not in visible_page_ids or target_page_id not in visible_page_ids:
            continue
        returning = str(item.get("resultType") or "") in {"return", "close_overlay", "loop"} or item.get("direction") == "return"
        relations.append({
            "id": str(item.get("id") or ""),
            "sourcePageId": source_page_id,
            "targetPageId": target_page_id,
            "label": label,
            "lineStyle": "dashed" if returning or uncertain_sequence else "solid",
        })
    _annotate_page_topology(pages, relations)
    return {"pages": pages, "relations": relations, "notes": all_notes, "showUeMarkers": False}
