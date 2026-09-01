from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil
from typing import Any

from backend.feishu_language_quality import language_quality_report, rule_carrier, split_rule_carriers, three_reader_report
from backend.gameplay_domain_policy import classify_domain_modules, provenance_scope_report
from backend.granularity_audit import MECHANISM_RESPONSIBILITIES, mechanism_closure_report
from backend.planning_content_policy import carrier_policy_report, normalize_delivery_carriers


ROOT = Path(__file__).resolve().parents[1]

DOMAIN_PATTERNS: dict[str, re.Pattern[str]] = {
    "movement": re.compile(r"移动|前进|推进|路径|位移|道路"),
    "placement": re.compile(r"摆放|放置|占格|格子|建造位置"),
    "random_choice": re.compile(r"随机|候选|三选一|抽取|刷新|权重"),
    "combat": re.compile(r"战斗|攻击|伤害|命中|生命值|敌人|怪物|首领"),
    "growth": re.compile(r"升级|强化|成长|等级|经验"),
    "buff_duration": re.compile(r"\bBuff\b|增益|减益|状态效果"),
    "inventory_slot": re.compile(r"背包|仓库|物品栏|库存"),
    "level": re.compile(r"关卡|波次|通关|结算|胜利|失败|首领阶段"),
    "sweep": re.compile(r"扫荡"),
}

TITLE_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^局内升级与三选一强化$"), "局内强化"),
    (re.compile(r"^终极强化与攻击形态变化$"), "终极强化"),
    (re.compile(r"^武器抽取界面与结果确认$"), "武器抽取"),
    (re.compile(r"^关卡阶段与首领战$"), "关卡与首领"),
    (re.compile(r"^挑战成功、奖励与伤害统计$"), "结算"),
)

CURRENT_JOB_DIRECTORY_SUMMARIES = {
    "载具": "载具自动向前推进，玩家调整横向位置；生命值、等级、武器栏与特权状态共同决定本局生存和输出基础。",
    "武器": "各类武器按索敌范围、攻击间隔与伤害方式自动攻击；关卡外解锁养成，关卡内通过词条改变技能参数和效果。",
    "局内强化": "达到局内成长条件后暂停战斗并生成强化候选；玩家选择一项后写入本局状态，再恢复战斗。",
    "终极强化": "满足终极词条的前置条件后进入候选；确认后改变对应武器的攻击形态或关键效果，并在本局持续生效。",
    "武器抽取": "独立抽取界面展示武器或技能候选；候选池、刷新、重复处理和确认写入规则由本章统一约束。",
    "怪物": "怪物按关卡波次和刷怪点生成，随后执行移动、攻击、受击与死亡；属性倍率随关卡和波次参与计算。",
    "关卡": "关卡负责波次推进、首领阶段、整局计时与胜负触发；怪物实体行为和结算后的奖励处理分别由对应章节承载。",
    "结算": "关卡结束后按成功、失败或中断结果进入对应结算；记录统计与奖励状态，并阻止重复领取同一份奖励。",
}

CURRENT_JOB_UNDERSTANDING = {
    "summary": "玩家操控持续前进的载具，在生命值归零前清理沿途敌人并击败关卡首领。武器自动攻击，局内强化与武器抽取改变本局能力，击败首领后进入奖励和伤害统计结算。",
    "playerGoal": "在载具生命值归零前击败关卡首领。",
    "basicControls": "战斗中调整载具横向位置；成长界面选择、刷新或确认候选；结算时领取奖励并返回。",
    "coreLoop": "载具推进与自动攻击 → 获得局内强化或武器 → 进入首领阶段 → 击败首领并结算。",
    "progression": "载具和武器提供关卡外成长；普通强化、终极强化与武器抽取构成本局成长。",
    "completion": "击败关卡首领后进入成功结算。",
    "failure": "载具生命值归零时本局失败。",
    "primaryFamily": "战斗推进与局内成长",
    "supportingMechanics": ["载具", "武器", "局内强化", "终极强化", "武器抽取", "怪物", "结算"],
    "uncertainties": [],
}

CURRENT_PRESENTATION_REWRITES = {
    "达到首领阶段条件后，系统覆盖红色警示效果并显示“首领来袭”，背景战斗信息降为次要层级": "达到首领阶段条件后，进入首领来袭警告。",
    "警告结束后进入首领战，顶部显示首领名称、生命百分比和附加计数": "警告结束后进入首领战。",
}

DECISION_LIBRARY: dict[str, dict[str, Any]] = {
    "weights": {
        "question": "候选项按什么方式计算抽取权重？",
        "options": [
            ("equal", "所有符合条件的候选等权抽取"),
            ("configured", "按每个候选的配置权重抽取"),
        ],
    },
    "replacement": {
        "question": "本次抽取结束后，已抽中的候选是否放回候选池？",
        "options": [
            ("without_replacement", "本次候选组内不放回，确认或刷新后重建候选"),
            ("with_replacement", "每次抽取后立即放回，后续仍可再次抽中"),
        ],
    },
}


def _planner_text(chapter: dict[str, Any]) -> str:
    return json.dumps(
        {
            "scope": chapter.get("scope"),
            "plannerSections": chapter.get("plannerSections"),
            "contentInventory": chapter.get("contentInventory"),
        },
        ensure_ascii=False,
    )


def _activation_text(chapter: dict[str, Any], original_scope: str) -> str:
    planner = chapter.get("plannerSections") if isinstance(chapter.get("plannerSections"), dict) else {}
    attribute_headings = [
        str(item.get("heading") or "")
        for item in planner.get("attributeSections") or []
        if isinstance(item, dict)
    ]
    return json.dumps(
        {
            "scope": original_scope,
            "attributeHeading": planner.get("attributeHeading"),
            "attributeSections": attribute_headings,
            "contentInventory": chapter.get("contentInventory"),
        },
        ensure_ascii=False,
    )


def _scope_domains(scope: str, inferred_tags: set[str]) -> set[str]:
    if scope == "载具":
        return {"movement", "combat", "growth"}
    if scope == "武器":
        return {"combat", "growth", "random_choice"}
    if scope in {"局内强化", "终极强化"}:
        return {"random_choice", "growth"}
    if scope == "武器抽取":
        return {"random_choice"}
    if scope == "怪物":
        return {"movement", "combat", "level"}
    if scope == "结算":
        return {"level"}
    return inferred_tags


def _semantic_title(chapter: dict[str, Any]) -> str:
    planner = chapter.get("plannerSections") if isinstance(chapter.get("plannerSections"), dict) else {}
    object_title = str(planner.get("attributeHeading") or "").strip()
    if object_title:
        return object_title
    title = str(chapter.get("scope") or chapter.get("title") or "玩法规则").strip()
    for pattern, replacement in TITLE_RULES:
        if pattern.fullmatch(title):
            return replacement
    return title


def _rewrite_delivery_sentence(text: str) -> str:
    text = re.sub(
        r"当前项目应逐项保留而不是概括成[“\"]?[^。”\"]+[”\"]?",
        "各项内容按类别逐项展示",
        text,
    )
    text = re.sub(r"当前项目应", "", text)
    return text


def _rewrite_value(value: Any) -> Any:
    if isinstance(value, str):
        return _rewrite_delivery_sentence(value)
    if isinstance(value, list):
        return [_rewrite_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _rewrite_value(item) for key, item in value.items()}
    return value


def _derive_lifecycle_rules(planner: dict[str, Any]) -> list[str]:
    """Promote explicit lifecycle facts into the structured carrier without inventing rules."""
    candidates: list[str] = []
    for key in ("normalFlow", "keyRules", "specialCases"):
        value = planner.get(key)
        if isinstance(value, list):
            candidates.extend(str(item).strip() for item in value if str(item).strip())
        elif isinstance(value, str) and value.strip():
            candidates.append(value.strip())
    for section in planner.get("attributeSections") or []:
        if not isinstance(section, dict):
            continue
        candidates.extend(str(item).strip() for item in section.get("items") or [] if str(item).strip())
    lifecycle_pattern = re.compile(r"重置|清除解锁状态|不可逆|不可更换|不可卸除|不可切换|本局内|活动结束")
    return list(dict.fromkeys(item for item in candidates if lifecycle_pattern.search(item)))


def _route_presentation_rules(model: dict[str, Any], chapter: dict[str, Any], planner: dict[str, Any]) -> None:
    trace = model.get("planningGameplayTrace") if isinstance(model.get("planningGameplayTrace"), list) else []
    model["planningGameplayTrace"] = trace
    existing_board_copy = {str(item.get("text") or "").strip() for item in trace if isinstance(item, dict)}
    moved: list[str] = []
    for key in ("normalFlow", "keyRules", "specialCases"):
        values = planner.get(key)
        if not isinstance(values, list):
            continue
        kept: list[str] = []
        for value in values:
            text = str(value or "").strip()
            carrier = rule_carrier(text)
            if carrier == "presentation":
                moved.append(text)
                continue
            if carrier == "mixed":
                replacement = CURRENT_PRESENTATION_REWRITES.get(text.rstrip("。"))
                logic, presentation = split_rule_carriers(text)
                if replacement:
                    logic = replacement
                if logic:
                    kept.append(logic.rstrip("。") + "。")
                if presentation:
                    moved.append(presentation.rstrip("。") + "。")
                continue
            kept.append(value)
        planner[key] = kept
    for index, text in enumerate(moved, 1):
        if text in existing_board_copy:
            continue
        trace.append({
            "insightId": f"PGI-BOARD-{chapter.get('id')}-{index}",
            "stageId": "",
            "stageName": str(chapter.get("scope") or "对应页面"),
            "targetChapterId": "",
            "carrier": "planning_board",
            "text": text,
            "sourceFrameIds": list(chapter.get("sourceFrameIds") or []),
            "status": "board_only",
            "reason": "纯表现要求只进入策划草图，避免在玩法正文重复。",
        })
        existing_board_copy.add(text)


def _remove_published_fact(planner: dict[str, Any], fact: str) -> None:
    normalized = re.sub(r"\s+", "", fact)
    for key in ("normalFlow", "keyRules", "specialCases"):
        values = planner.get(key)
        if not isinstance(values, list):
            continue
        planner[key] = [
            item
            for item in values
            if re.sub(r"\s+", "", str(item or "")) != normalized
        ]
    if re.sub(r"\s+", "", str(planner.get("summary") or "")) == normalized:
        planner["summary"] = ""


def _decision_card(chapter: dict[str, Any], responsibility: str) -> dict[str, Any]:
    definition = DECISION_LIBRARY.get(responsibility) or {
        "question": f"{responsibility} 采用哪一种处理方式？",
        "options": [
            ("current_evidence", "按当前素材中已经展示的行为处理"),
            ("configuration", "由独立配置控制具体处理方式"),
        ],
    }
    chapter_id = str(chapter.get("id") or "chapter")
    return {
        "id": f"GDC-{chapter_id}-{responsibility}",
        "responsibility": responsibility,
        "question": definition["question"],
        "status": "pending",
        "selectionMode": "single",
        "allowCustom": True,
        "allowSkip": True,
        "options": [
            {"id": option_id, "label": label, "recommended": False, "reason": "当前素材不足以唯一判断。"}
            for option_id, label in definition["options"]
        ],
        "evidence": [
            {"frameId": frame_id, "label": "对应素材"}
            for frame_id in chapter.get("sourceFrameIds") or []
        ],
        "impacts": ["玩法正文", "策划草图", "配置表", "最终文档"],
    }


def _required_responsibilities(text: str, states: dict[str, str], scope: str) -> dict[str, list[str]]:
    required: dict[str, list[str]] = {}
    if states.get("movement") != "not_applicable":
        required["movement"] = ["constraint", "commit", "boundary"]
    if states.get("random") != "not_applicable":
        required["random"] = list(MECHANISM_RESPONSIBILITIES["random"])
    if states.get("combat") != "not_applicable":
        if scope == "怪物" or re.search(r"怪物|首领", scope):
            required["combat"] = ["target", "hit", "damage", "death"]
        elif scope == "载具":
            required["combat"] = ["hit", "damage", "death"]
        else:
            required["combat"] = ["target", "hit", "damage"]
    if states.get("growth") != "not_applicable":
        if "终极" in scope:
            required["growth"] = ["trigger", "effect"]
        elif scope == "载具":
            required["growth"] = ["trigger", "cost", "effect", "reset"]
        elif scope == "武器":
            required["growth"] = ["trigger", "cost", "effect", "cap", "reset"]
        else:
            required["growth"] = ["trigger", "effect", "reset"]
    if states.get("level") != "not_applicable":
        required["level"] = ["victory", "settlement"] if scope == "结算" else ["entry", "progress", "victory", "failure"]
    for domain in ("placement", "buff", "inventory", "sweep"):
        if states.get(domain) != "not_applicable":
            required[domain] = list(MECHANISM_RESPONSIBILITIES[domain])
    return required


def _annotate_existing_card(card: dict[str, Any]) -> None:
    card_id = str(card.get("id") or "")
    if not card.get("domain"):
        for domain in MECHANISM_RESPONSIBILITIES:
            if f"-{domain}-closure" in card_id:
                card["domain"] = domain
                break
    if card.get("responsibility") or card.get("responsibilities"):
        return
    question = str(card.get("question") or "")
    if re.search(r"候选池|刷新规则", question):
        card["responsibilities"] = ["eligibility", "pool", "weights"]
    elif re.search(r"抽取.+结果|结果.+结算", question):
        card["responsibilities"] = ["commit"]


def _card_responsibilities(card: dict[str, Any]) -> set[str]:
    values = card.get("responsibilities") or [card.get("responsibility")]
    return {str(item).strip() for item in values if str(item or "").strip()}


def _dedupe_generated_decision_cards(chapter: dict[str, Any], cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep one pending owner for each generated responsibility while preserving resolved history."""
    chapter_id = str(chapter.get("id") or "chapter")
    grouped_pending = set().union(*(
        [_card_responsibilities(card) for card in cards if card.get("status") != "resolved" and card.get("responsibilities")]
        or [set()]
    ))
    result: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for card in cards:
        card_id = str(card.get("id") or "")
        singular = str(card.get("responsibility") or "").strip()
        generated_singular_id = f"GDC-{chapter_id}-{singular}" if singular else ""
        if card.get("status") != "resolved" and singular in grouped_pending and card_id == generated_singular_id:
            continue
        if card_id and card_id in seen_ids:
            continue
        if card_id:
            seen_ids.add(card_id)
        result.append(card)
    return result


def _decision_card_overlap_report(model: dict[str, Any]) -> dict[str, Any]:
    overlaps: list[str] = []
    for chapter in model.get("chapters") or []:
        if not isinstance(chapter, dict):
            continue
        owners: dict[str, list[str]] = {}
        for card in chapter.get("decisionCards") or []:
            if not isinstance(card, dict) or card.get("status") == "resolved":
                continue
            domain = str(card.get("domain") or "unspecified")
            for responsibility in _card_responsibilities(card):
                owners.setdefault(f"{domain}:{responsibility}", []).append(str(card.get("id") or ""))
        overlaps.extend(
            f"{chapter.get('scope')}:{responsibility}:{','.join(card_ids)}"
            for responsibility, card_ids in owners.items() if len(card_ids) > 1
        )
    return {"passed": not overlaps, "overlaps": overlaps}


def _group_decision_card(chapter: dict[str, Any], domain: str, responsibilities: list[str]) -> dict[str, Any]:
    responsibility_set = set(responsibilities)
    if domain == "random" and responsibility_set <= {"filter", "duplicate", "empty"}:
        question = "无效、重复或不足三个候选时，候选列表如何处理？"
        options = [
            ("filter_and_shorten", "过滤无效和重复候选；不足三个时只展示实际可用项"),
            ("fallback_fill", "过滤无效候选；不足三个时使用保底候选补足"),
        ]
    elif domain == "random" and responsibility_set <= {"eligibility", "pool", "weights"}:
        question = "哪些内容可以进入候选池，候选之间如何计算抽取权重？"
        options = [
            ("unlocked_weighted", "只加入已解锁且满足前置条件的内容，并按配置权重抽取"),
            ("visible_equal", "加入当前可显示的全部内容，各候选等权抽取"),
        ]
    elif domain == "random" and responsibility_set <= {"commit"}:
        question = "玩家确认候选后，结果在什么时候写入本局状态？"
        options = [
            ("immediate", "确认后立即写入并生效，然后恢复原流程"),
            ("deferred", "确认后先保存临时结果，在当前阶段结束时统一写入"),
        ]
    elif domain == "random" and responsibility_set <= {"reset"}:
        question = "候选池和刷新次数在什么时候重置？"
        options = [
            ("per_choice", "每次确认强化后重建候选池，刷新次数按本次选择重置"),
            ("per_run", "候选池和刷新次数在整局战斗内累计，战斗结束后重置"),
        ]
    elif domain == "growth" and responsibility_set.intersection({"cap", "reset"}):
        question = "该成长的等级上限和保留周期如何处理？"
        options = [
            ("persistent", "达到配置上限后停止成长，并在后续关卡中保留"),
            ("activity_reset", "达到配置上限后停止成长，活动结束时重置"),
        ]
    else:
        question = f"《{chapter.get('scope') or domain}》缺少的规则如何确定：{'、'.join(responsibilities)}？"
        options = [
            ("current_evidence", "按当前素材中已展示的行为补齐"),
            ("configuration", "由独立配置控制，并按配置结果执行"),
        ]
    chapter_id = str(chapter.get("id") or "chapter")
    return {
        "id": f"GDC-{chapter_id}-{domain}-closure",
        "domain": domain,
        "responsibilities": responsibilities,
        "question": question,
        "status": "pending",
        "selectionMode": "single",
        "allowCustom": True,
        "allowSkip": True,
        "options": [
            {"id": option_id, "label": label, "recommended": False, "reason": "当前素材不足以唯一判断。"}
            for option_id, label in options
        ],
        "evidence": [
            {"frameId": frame_id, "label": "对应素材"}
            for frame_id in chapter.get("sourceFrameIds") or []
        ],
        "impacts": ["玩法正文", "策划草图", "配置表", "最终文档"],
    }
def _sample_alignment(chapter: dict[str, Any], model: dict[str, Any]) -> dict[str, str]:
    planner = chapter.get("plannerSections") if isinstance(chapter.get("plannerSections"), dict) else {}
    chapter_id = chapter.get("id")
    diagrams = [
        item for item in model.get("diagrams") or []
        if isinstance(item, dict) and chapter_id in (item.get("chapterIds") or []) and item.get("status") != "deleted"
    ]
    tables = [
        item for item in model.get("tables") or []
        if isinstance(item, dict) and chapter_id in (item.get("chapterIds") or []) and item.get("status") != "deleted"
    ]
    decisions = [item for item in chapter.get("decisionCards") or [] if isinstance(item, dict)]
    boundary = bool(planner.get("specialCases") or chapter.get("boundaryRules"))
    lifecycle = bool(chapter.get("lifecycle") or chapter.get("lifecycleRules"))
    return {
        "content_inventory": "covered" if chapter.get("contentInventory") else "missing",
        "owner_attribute_prose": "covered" if planner.get("attributeSections") else "not_applicable",
        "execution_sequence": "covered" if planner.get("normalFlow") else "missing",
        "configuration_mapping": "covered" if tables or chapter.get("configurationSources") else "not_applicable",
        "boundary_and_lifecycle": "covered" if boundary and lifecycle else ("decision_required" if decisions else "missing"),
        "local_visual": "covered" if diagrams or chapter.get("inlineFigures") else "not_applicable",
        "decision_coverage": "decision_required" if any(item.get("status") == "pending" for item in decisions) else "covered",
    }


def _current_job_p1_structure(model: dict[str, Any]) -> None:
    """Separate level orchestration from entity and settlement rules for the formal job only."""
    chapters = [item for item in model.get("chapters") or [] if isinstance(item, dict)]
    by_scope = {str(item.get("scope") or ""): item for item in chapters}
    legacy_scopes = {"载具", "武器", "局内强化", "终极强化", "武器抽取", "怪物", "结算"}
    if set(by_scope) != legacy_scopes:
        return

    monster = by_scope["怪物"]
    original_monster_planner = monster.get("plannerSections") or {}
    monster_attribute_sections = [
        item for item in original_monster_planner.get("attributeSections") or []
        if isinstance(item, dict) and not re.search(r"波次|刷怪点|怪物组", str(item.get("heading") or ""))
    ]
    level_attribute_sections = [
        item for item in original_monster_planner.get("attributeSections") or []
        if isinstance(item, dict) and re.search(r"波次|刷怪点|怪物组", str(item.get("heading") or ""))
    ]
    monster["plannerSections"] = {
        "summary": "怪物由关卡波次生成后，独立执行移动、索敌、攻击、受击与死亡。",
        "normalFlow": [
            "关卡生成怪物后，怪物按自身移动规则接近攻击目标。",
            "进入攻击条件后执行攻击；受到伤害时更新生命值，生命值归零后进入死亡处理。",
        ],
        "keyRules": ["怪物章的规则边界是单个实体从生成完成到死亡移除的生命周期。"],
        "specialCases": ["怪物属性和行为参数缺少当前项目依据时，进入对应决策卡，不使用样例项目数值。"],
        "attributeHeading": "怪物",
        "attributeSections": monster_attribute_sections,
        "acceptanceExamples": list(original_monster_planner.get("acceptanceExamples") or []),
    }

    level = {
        "id": "GCH-020",
        "scope": "关卡",
        "title": "关卡",
        "summary": CURRENT_JOB_DIRECTORY_SUMMARIES["关卡"],
        "plannerSections": {
            "summary": "关卡统一编排波次、首领阶段、整局时间与胜负触发。",
            "normalFlow": [
                "进入关卡后启动整局时间并按顺序推进波次。",
                "当前波次满足结束条件后进入下一波；达到首领阶段条件后切换到首领阶段。",
                "击败首领时触发胜利并移交结算；载具生命值归零时触发失败并移交结算。",
            ],
            "keyRules": [
                "关卡负责波次顺序、首领阶段切换、整局时间和胜负触发；怪物章只负责实体行为。",
            ],
            "specialCases": [
                "波次结束条件、首领阶段触发条件或时间限制缺少当前项目依据时，必须由决策卡补齐后才能通过。",
            ],
            "attributeHeading": "关卡",
            "attributeSections": level_attribute_sections,
        },
        "contentInventory": ["波次", "首领阶段", "整局时间", "胜利", "失败"],
        "sourceFrameIds": list(monster.get("sourceFrameIds") or []),
        "fieldDictionary": [],
        "formulae": [],
        "workedExamples": [],
        "configurationSources": [],
        "lifecycleRules": ["进入关卡时初始化波次与整局时间；胜利、失败或中断后停止本局推进。"],
        "unresolvedResponsibilities": ["entry", "progress", "victory", "failure", "interruption"],
        "decisionCards": [],
    }
    monster_schema = [item for item in monster.get("parameterSchema") or [] if isinstance(item, dict)]
    level_schema = [
        item for item in monster_schema
        if re.search(r"波次|首领|刷怪|整局时间", str(item.get("name") or ""))
    ]
    monster["parameterSchema"] = [item for item in monster_schema if item not in level_schema]
    level["parameterSchema"] = level_schema
    monster["formulae"] = [
        {
            "name": "怪物波次生命值",
            "expression": "当前生命值上限 = 怪物基础生命值 × 当前波次生命值倍率",
            "evidenceLevel": "reference_document",
            "referenceSource": "现有怪物属性正文与配置职责",
            "variables": [{"name": "怪物基础生命值"}, {"name": "当前波次生命值倍率"}],
        },
        {
            "name": "怪物波次攻击力",
            "expression": "当前攻击力 = 怪物基础攻击力 × 当前波次攻击力倍率",
            "evidenceLevel": "reference_document",
            "referenceSource": "现有怪物属性正文与配置职责",
            "variables": [{"name": "怪物基础攻击力"}, {"name": "当前波次攻击力倍率"}],
        },
    ]
    settlement = by_scope["结算"]
    settlement["plannerSections"] = {
        **(settlement.get("plannerSections") or {}),
        "summary": "关卡结束后按成功、失败或中断结果进入对应结算，并保证奖励只发放一次。",
        "normalFlow": [
            "收到胜利结果后生成成功结算，记录通关时间、奖励和伤害统计。",
            "收到失败结果后生成失败结算，不沿用成功奖励分支。",
            "发生中断时保存可恢复状态；恢复后继续未完成的结算步骤。",
        ],
        "keyRules": ["奖励领取必须幂等；重复进入或重复领取不得再次发放同一份奖励。"],
        "specialCases": ["失败后的重试、返回以及中断恢复位置缺少依据时，由决策卡确定。"],
    }
    settlement["unresolvedResponsibilities"] = sorted(set(
        settlement.get("unresolvedResponsibilities") or []
    ) | {"failure_settlement", "interruption_recovery", "reward_idempotency", "retry_return"})
    settlement["formulae"] = [{
        "name": "单武器伤害占比",
        "expression": "单武器伤害占比 = 单武器累计伤害 ÷ 本局全部武器累计伤害 × 100%",
        "evidenceLevel": "material",
        "sourceFrameIds": list(settlement.get("sourceFrameIds") or []),
        "variables": [{"name": "单武器累计伤害"}, {"name": "本局全部武器累计伤害"}],
    }]

    insert_at = chapters.index(monster) + 1
    chapters.insert(insert_at, level)
    model["chapters"] = chapters
    directory = model.get("directory") if isinstance(model.get("directory"), dict) else {}
    entries = [item for item in directory.get("entries") or [] if isinstance(item, dict)]
    monster_entry_index = next((i for i, item in enumerate(entries) if item.get("chapterId") == monster.get("id")), len(entries) - 1)
    entries.insert(monster_entry_index + 1, {
        "id": "GDE-P1-LEVEL",
        "chapterId": level["id"],
        "title": "关卡",
        "sectionTitle": str(entries[monster_entry_index].get("sectionTitle") or "关卡推进"),
        "order": monster_entry_index + 2,
        "summary": CURRENT_JOB_DIRECTORY_SUMMARIES["关卡"],
        "summarySource": "planner",
    })
    directory["entries"] = entries

    for chapter in chapters:
        schema = [item for item in chapter.get("parameterSchema") or [] if isinstance(item, dict)]
        chapter["fieldDictionary"] = [
            {
                "plannerName": str(item.get("name") or "未命名字段"),
                "suggestedCodeName": "待确认",
                "status": "decision_required",
                "source": str(item.get("configurationSource") or "当前任务参数结构"),
            }
            for item in schema
        ] or [{
            "plannerName": f"{chapter.get('scope')}配置字段",
            "suggestedCodeName": "待确认",
            "status": "decision_required",
            "source": "当前任务尚无权威字段映射",
        }]
        if chapter.get("formulae"):
            chapter["formulaStatus"] = "supported"
        elif chapter.get("scope") in {"局内强化", "终极强化", "武器抽取", "关卡"}:
            chapter["formulaStatus"] = "decision_required"
        else:
            chapter["formulaStatus"] = "not_applicable"
        if not chapter.get("lifecycleRules"):
            chapter["lifecycleRules"] = [f"{chapter.get('scope')}的初始化、持续与结束边界缺少依据时由决策卡补齐。"]

    level_id = level["id"]
    for diagram in model.get("diagrams") or []:
        if not isinstance(diagram, dict) or str(diagram.get("id") or "") not in {"GDI-101", "GDI-105"}:
            continue
        bindings = list(diagram.get("chapterIds") or [])
        if level_id not in bindings:
            bindings.append(level_id)
        diagram["chapterIds"] = bindings
        diagram["status"] = "stale"
        diagram["staleReason"] = "P1 章节职责已拆分，图解必须按新关卡归属重新生成并审核。"


def migrate_job(job: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(job)
    model = result.get("gameplayReviewModel")
    if not isinstance(model, dict):
        return result
    model["revision"] = int(model.get("revision") or 0) + 1
    model["granularityAuditVersion"] = max(4, int(model.get("granularityAuditVersion") or 0))
    review_state = model.get("reviewState") if isinstance(model.get("reviewState"), dict) else {}
    for field in ("previewRevision", "previewGeneratedAt", "pinnedPublicationRevision"):
        review_state.pop(field, None)
    model["reviewState"] = review_state

    _current_job_p1_structure(model)
    directory = model.get("directory") if isinstance(model.get("directory"), dict) else {}
    for entry in directory.get("entries") or []:
        if isinstance(entry, dict) and not entry.get("id"):
            entry["id"] = f"GDE-{entry.get('chapterId') or 'UNRESOLVED'}"
        if isinstance(entry, dict) and entry.get("title") == "关卡":
            entry["sectionTitle"] = "关卡推进"
    for order, entry in enumerate(directory.get("entries") or [], 1):
        if isinstance(entry, dict):
            entry["order"] = order

    for chapter in model.get("chapters") or []:
        if not isinstance(chapter, dict):
            continue
        planner = chapter.get("plannerSections") if isinstance(chapter.get("plannerSections"), dict) else {}
        chapter["plannerSections"] = _rewrite_value(planner)
        planner = chapter["plannerSections"]
        _route_presentation_rules(model, chapter, planner)
        if not chapter.get("lifecycle") and not chapter.get("lifecycleRules"):
            lifecycle_rules = _derive_lifecycle_rules(planner)
            if lifecycle_rules:
                chapter["lifecycleRules"] = lifecycle_rules
        for claim in chapter.get("provenanceClaims") or []:
            if not isinstance(claim, dict) or claim.get("sourceScope") != "sample_reserve":
                continue
            fact = str(claim.get("text") or "").strip()
            if fact:
                _remove_published_fact(planner, fact)
            claim["publicationAllowed"] = False
            claim["usage"] = "decision_question"

        original_scope = str(chapter.get("scope") or chapter.get("title") or "")
        chapter["scope"] = _semantic_title(chapter)
        text = _planner_text(chapter)
        activation_text = _activation_text(chapter, original_scope)
        inferred_tags = {tag for tag, pattern in DOMAIN_PATTERNS.items() if pattern.search(activation_text)}
        evidence_tags = _scope_domains(str(chapter.get("scope") or ""), inferred_tags)
        unresolved = {str(item).strip() for item in chapter.get("unresolvedResponsibilities") or [] if str(item).strip()}
        chapter["domainStates"] = classify_domain_modules(evidence_tags, unresolved)
        chapter["requiredResponsibilities"] = _required_responsibilities(text, chapter["domainStates"], str(chapter.get("scope") or ""))

        cards = [item for item in chapter.get("decisionCards") or [] if isinstance(item, dict)]
        for existing_card in cards:
            _annotate_existing_card(existing_card)
        cards = _dedupe_generated_decision_cards(chapter, cards)
        card_responsibilities = set().union(*(
            [_card_responsibilities(item) for item in cards if item.get("status") != "resolved"] or [set()]
        ))
        cards.extend(
            _decision_card(chapter, responsibility)
            for responsibility in sorted(unresolved)
            if responsibility not in card_responsibilities
        )
        chapter["decisionCards"] = cards
        closure = mechanism_closure_report({"chapters": [chapter]})
        missing_by_domain: dict[str, list[str]] = {}
        for finding in closure["findings"]:
            if finding.get("code") != "MECHANISM_RESPONSIBILITY_MISSING":
                continue
            missing_by_domain.setdefault(str(finding.get("domain")), []).append(str(finding.get("responsibility")))
        for domain, responsibilities in missing_by_domain.items():
            if not responsibilities:
                continue
            unique_responsibilities = list(dict.fromkeys(responsibilities))
            groups = [unique_responsibilities]
            if domain == "random":
                groups = [
                    [item for item in unique_responsibilities if item in {"eligibility", "pool", "weights"}],
                    [item for item in unique_responsibilities if item in {"filter", "duplicate", "empty"}],
                    [item for item in unique_responsibilities if item == "commit"],
                    [item for item in unique_responsibilities if item == "reset"],
                ]
                groups = [group for group in groups if group]
            for group_index, group in enumerate(groups, 1):
                decision = _group_decision_card(chapter, domain, group)
                if len(groups) > 1:
                    decision["id"] = f"{decision['id']}-{group_index}"
                cards.append(decision)
            unresolved.update(unique_responsibilities)
        chapter["decisionCards"] = cards
        chapter["unresolvedResponsibilities"] = sorted(unresolved)
        chapter["domainStates"] = classify_domain_modules(evidence_tags, unresolved)
        chapter["sampleAlignment"] = _sample_alignment(chapter, model)

    model = normalize_delivery_carriers(model)
    result["gameplayReviewModel"] = model
    title_by_id = {
        str(chapter.get("id")): str(chapter.get("scope"))
        for chapter in model.get("chapters") or [] if isinstance(chapter, dict)
    }
    directory = model.get("directory") if isinstance(model.get("directory"), dict) else {}
    if directory:
        directory["understanding"] = deepcopy(CURRENT_JOB_UNDERSTANDING)
    for entry in directory.get("entries") or []:
        if isinstance(entry, dict) and str(entry.get("chapterId")) in title_by_id:
            entry["title"] = title_by_id[str(entry.get("chapterId"))]
            entry["summary"] = CURRENT_JOB_DIRECTORY_SUMMARIES.get(entry["title"], entry.get("summary") or "")
            entry["summarySource"] = "planner"
    return result


def _apply(job_id: str) -> dict[str, Any]:
    job_path = ROOT / "data" / "jobs" / job_id / "job.json"
    source = json.loads(job_path.read_text(encoding="utf-8"))
    migrated = migrate_job(source)
    model = migrated.get("gameplayReviewModel") or {}
    alignment_missing = [
        f"{chapter.get('scope')}:{role}"
        for chapter in model.get("chapters") or []
        if isinstance(chapter, dict)
        for role, state in (chapter.get("sampleAlignment") or {}).items()
        if state == "missing"
    ]
    gates = {
        "language": language_quality_report(model)["passed"],
        "carrier": carrier_policy_report(model)["passed"],
        "provenance": provenance_scope_report(model)["passed"],
        "mechanismClosure": mechanism_closure_report(model)["passed"],
        "sampleAlignment": not alignment_missing,
        "decisionCardUniqueness": _decision_card_overlap_report(model)["passed"],
        "threeReader": three_reader_report(model)["passed"],
    }
    if not all(gates.values()):
        raise RuntimeError(
            "PRD depth migration blocked by quality gates: "
            + json.dumps({"gates": gates, "alignmentMissing": alignment_missing}, ensure_ascii=False)
        )
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = job_path.with_name(f"job.before-prd-depth-{timestamp}.json")
    shutil.copy2(job_path, backup_path)
    temporary_path = job_path.with_suffix(".prd-depth.tmp")
    temporary_path.write_text(json.dumps(migrated, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary_path.replace(job_path)
    return {
        "backupPath": str(backup_path),
        "previousRevision": (source.get("gameplayReviewModel") or {}).get("revision"),
        "newRevision": model.get("revision"),
        "chapterCount": len(model.get("chapters") or []),
        "decisionCardCount": sum(len(item.get("decisionCards") or []) for item in model.get("chapters") or [] if isinstance(item, dict)),
        "gatePassed": all(gates.values()),
        "gates": gates,
        "alignmentMissing": alignment_missing,
        "decisionCardOverlaps": _decision_card_overlap_report(model)["overlaps"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not args.apply:
        raise SystemExit("Use --apply to migrate the live job after tests pass.")
    print(json.dumps(_apply(args.job), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
