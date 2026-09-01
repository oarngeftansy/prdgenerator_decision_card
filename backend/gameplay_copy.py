from __future__ import annotations

import re
from copy import deepcopy
import hashlib
import json
from typing import Any

from .gameplay_flow_semantics import repair_legacy_flow_ownership


_INTERACTION_ONLY = re.compile(
    r"(?:画面(?:中|显示)?|屏幕(?:上方|下方|左侧|右侧|中央|底部)?|左上角|右上角|左侧|右侧|上方|下方|中央|底部|界面|弹窗|按钮|图标|边框|背景|特效|小地图|虚拟摇杆|按键|显示|展示|\bUI\b|\bHUD\b)",
    re.I,
)
_DIRECTORY_UI_TITLE = re.compile(r"(?:页面|界面|弹窗|面板|信息板|显示|展示|提示|图标|按钮|状态)$")


def _abstract_structure_observation(text: str, scope: str) -> str:
    value = normalize_game_term(text)
    if "沿预设路线" in value and any(term in value for term in ("横向微调", "虚拟摇杆", "按键")):
        return "载具沿预设路线自动前进；玩家可控制载具横向移动，以调整行进位置、规避敌人或对准攻击目标。"
    if "血条" in value and "归零" in value:
        return "载具拥有独立生命值；受到伤害时扣减生命值，生命值归零时本局失败。"
    if "无需手动瞄准" in value and any(term in value for term in ("射程内", "自动")):
        return "载具武器会自动寻找射程内的有效敌人并发动攻击；不同武器按照各自的攻击方式造成伤害。"
    if "三个" in value and "选择" in value and any(term in value for term in ("升级", "强化", "卡片")):
        return "玩家满足局内成长条件后，从三项候选强化中选择一项；选择结果立即作用于本局能力。"
    if "选择后" in value and "武器栏" in value:
        return "候选强化可包含尚未拥有的新武器；玩家确认后解锁该武器并加入本局可用武器，使攻击方式发生变化。"
    if "刷新" in value and any(term in value for term in ("三个选项", "三项", "重置当前")):
        return "玩家满足刷新条件后，可将当前三项候选强化替换为新候选；刷新消耗和可用次数按对应规则执行。"
    if "伤害" in value and any(term in value for term in ("飘出", "数字", "红色", "白色")):
        return "攻击命中后会生成对应的伤害结果；普通伤害与特殊伤害使用不同的数值反馈。"

    templates = (
        (("移动", "行进", "路线"), "玩家可调整载具的行进位置；自动前进、可控方向和移动边界由本机制统一定义。"),
        (("生命", "血量", "受击"), "玩法单位拥有独立生命值；受到伤害时扣减，生命值归零时进入失败或死亡状态。"),
        (("索敌", "攻击", "武器"), "武器按照目标筛选、射程和攻击间隔自动处理攻击，并将命中结果交给伤害结算。"),
        (("槽位", "切换"), "载具可承载多个武器槽位；各槽位的启用、切换和同时生效规则在本机制中确定。"),
        (("怪物", "刷新", "生成"), "关卡推进过程中，系统按既定条件生成敌人；刷新时机、数量和强度由关卡规则决定。"),
        (("首领",), "关卡满足指定条件后进入首领阶段；首领的登场、阶段变化、失败和击败结果在本机制中处理。"),
        (("计时", "进度"), "系统持续记录关卡时间与推进进度，并以此驱动阶段切换和结算判断。"),
        (("胜利", "失败", "结算"), "系统根据关卡目标完成情况判定胜负，并将本局结果交给结算流程。"),
        (("强化", "升级", "成长"), "玩家满足成长条件后获得候选强化；确认选择后，本局能力立即发生对应变化。"),
        (("抽取", "随机"), "系统从当前可用内容池中随机产生候选结果；抽取范围、消耗和刷新规则由本机制定义。"),
    )
    for keywords, template in templates:
        if any(keyword in scope or keyword in value for keyword in keywords):
            return template
    return f"当前素材只确认了“{scope}”这一机制名称，具体触发、玩家操作、系统反馈和结果仍需策划确认。"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _directory_title_key(value: Any) -> str:
    title = re.sub(r"[\s\-—_·:：/（）()]+", "", _text(value).casefold())
    return re.sub(r"(?:玩法)?(?:系统|子系统|机制|规则)$", "", title)


def gameplay_structure_quality_errors(model: dict) -> list[str]:
    """Audit only hierarchy shape and naming; never reinterpret planner-confirmed rules."""
    errors: list[str] = []
    directory = model.get("directory") if isinstance(model.get("directory"), dict) else {}
    chapters = {item.get("id"): item for item in model.get("chapters") or [] if isinstance(item, dict)}
    seen_titles: set[str] = set()
    for entry in directory.get("entries") or []:
        if not isinstance(entry, dict):
            continue
        title = _text(entry.get("title") or (chapters.get(entry.get("chapterId")) or {}).get("scope"))
        key = _directory_title_key(title)
        if key in seen_titles:
            errors.append(f"重复机制：{title}")
        elif key:
            seen_titles.add(key)
        if _DIRECTORY_UI_TITLE.search(title):
            errors.append(f"界面名称被当成机制：{title}")
    for system in model.get("systems") or []:
        if not isinstance(system, dict):
            continue
        system_key = _directory_title_key(system.get("name"))
        for subsystem in system.get("subsystems") or []:
            if not isinstance(subsystem, dict):
                continue
            subsystem_key = _directory_title_key(subsystem.get("name"))
            if system_key and subsystem_key == system_key:
                errors.append(f"系统与子系统重名：{_text(system.get('name'))}")
            chapter_ids = [item for item in subsystem.get("chapterIds") or [] if item in chapters]
            if len(chapter_ids) > 8:
                errors.append(f"单个子系统包含 {len(chapter_ids)} 个机制，需要按业务责任拆分")
            for chapter_id in chapter_ids:
                chapter_key = _directory_title_key((chapters.get(chapter_id) or {}).get("scope"))
                if chapter_key and chapter_key in {system_key, subsystem_key}:
                    errors.append(f"层级标题重复：{_text((chapters.get(chapter_id) or {}).get('scope'))}")
    return list(dict.fromkeys(errors))


def normalize_game_term(text: str, *, first_use: bool = False) -> str:
    value = _text(text)
    if first_use and "终极词条" in value:
        value = value.replace("终极词条", "终极强化（素材中称‘__ORIGINAL_TERM__’）", 1)
    else:
        value = value.replace("终极词条", "终极强化")
    value = value.replace("词条库", "强化库").replace("词条", "强化效果")
    value = re.sub(r"Roguelike\s*式?", "局内随机成长", value, flags=re.I)
    value = re.sub(r"Buff", "强化效果", value, flags=re.I)
    value = re.sub(r"Build", "能力组合", value, flags=re.I)
    value = re.sub(r"Boss", "首领", value, flags=re.I)
    value = value.replace("强化效果强化效果", "强化效果")
    value = value.replace("局内随机成长局内成长", "局内随机成长")
    return value.replace("__ORIGINAL_TERM__", "终极词条")


def chapter_gameplay_summary(chapter: dict, *, first_use: bool = False) -> str:
    mechanism = chapter.get("mechanism") if isinstance(chapter.get("mechanism"), dict) else {}
    description = _text(mechanism.get("description"))
    scope = _text(chapter.get("scope")) or "该玩法的核心机制"
    if not description or _INTERACTION_ONLY.search(description) or description == scope:
        description = _abstract_structure_observation(description, scope)
    return normalize_game_term(description, first_use=first_use)


def _gameplay_family(chapters: list[dict]) -> tuple[str, list[str]]:
    names = [
        _text(value) for chapter in chapters if isinstance(chapter, dict)
        for value in (chapter.get("systemName"), chapter.get("subsystemName"), chapter.get("scope"))
        if _text(value)
    ]
    joined = " ".join(names)
    combat = any(term in joined for term in ("战斗", "攻击", "武器", "首领", "敌人", "伤害", "载具"))
    growth = any(term in joined for term in ("成长", "强化", "升级", "抽取"))
    if combat and growth:
        primary = "战斗推进与局内成长"
    elif combat:
        primary = "战斗与关卡"
    elif growth:
        primary = "局内成长"
    else:
        primary = "待策划确认"
    systems = []
    for chapter in chapters:
        name = _text(chapter.get("systemName"))
        if name and name not in systems:
            systems.append(name)
    return primary, systems[:4]


def build_gameplay_overview(chapters: list[dict]) -> str:
    valid = [item for item in chapters if isinstance(item, dict)]
    summaries = [(_text(item.get("scope")), _text(item.get("plannerSummary")) or chapter_gameplay_summary(item)) for item in valid]
    def pick(*keywords: str) -> str:
        return next((summary for scope, summary in summaries if any(word in scope + summary for word in keywords)), "")

    def pick_scope(*keywords: str) -> str:
        return next((summary for scope, summary in summaries if any(word in scope for word in keywords)), "")

    operation = pick_scope("移动", "操作", "控制", "拖动", "摆放") or pick("移动", "操作", "控制", "拖动", "摆放")
    combat = pick_scope("战斗", "攻击", "射击", "索敌", "敌人") or pick("战斗", "攻击", "射击", "索敌", "敌人")
    growth = pick_scope("成长", "强化", "升级", "选择", "抽取") or pick("成长", "强化", "升级", "选择", "抽取")
    win_scope, win_summary = next(((scope, summary) for scope, summary in summaries if any(word in scope for word in ("胜利", "通关"))), ("", ""))
    win = win_summary
    if win_scope and not any(word in win_summary for word in ("触发胜利", "完成关卡", "进入结算")):
        win = "玩家完成关卡目标或击败首领后获得胜利，并进入本局结算。"
    win = win or pick_scope("结算") or pick("触发胜利", "完成关卡", "击败首领")
    failure = pick_scope("失败", "生命值") or pick("生命值归零", "本局失败")
    sentences: list[str] = []
    for value in (operation, combat, growth, win, failure):
        value = _text(value)
        if value and value not in sentences:
            sentences.append(value.rstrip("。") + "。")
    if not sentences and summaries:
        sentences.append(summaries[0][1].rstrip("。") + "。")
    return "\n\n".join(sentences[:4]) or "当前素材尚不足以确认玩家目标、主要操作和玩法循环。"


def build_structure_overview(chapters: list[dict]) -> tuple[str, str, list[str]]:
    """Describe only the current confirmed hierarchy; do not infer a game loop from directory labels."""
    systems = list(dict.fromkeys(
        _text(chapter.get("systemName")) for chapter in chapters
        if isinstance(chapter, dict) and _text(chapter.get("systemName"))
    ))
    mechanisms = list(dict.fromkeys(
        _text(chapter.get("scope")) for chapter in chapters
        if isinstance(chapter, dict) and _text(chapter.get("scope"))
    ))
    primary = systems[0] if systems else "待策划确认"
    supporting = systems[1:4]
    system_copy = "、".join(systems) if systems else "尚待确认的玩法系统"
    mechanism_copy = "、".join(mechanisms[:8]) if mechanisms else "尚待确认的具体机制"
    summary = f"当前素材识别出的玩法范围：{system_copy}。本轮目录包含：{mechanism_copy}。本阶段只确认系统、子系统和具体机制的组织，不推断尚未生成的目标、操作、循环或胜负规则。"
    return summary, primary, supporting


def _legacy_gameplay_overview(chapters: list[dict]) -> str:
    sentences: list[str] = []
    for chapter in chapters:
        summary = _text(chapter.get("plannerSummary")) or chapter_gameplay_summary(chapter)
        for sentence in re.split(r"(?<=[。！？])", summary):
            sentence = sentence.strip()
            if sentence and sentence not in sentences:
                sentences.append(sentence)
            if len(sentences) >= 4:
                return "".join(sentences)
    return "".join(sentences)


def refresh_directory_copy(model: dict) -> dict:
    directory = model.get("directory") if isinstance(model.get("directory"), dict) else {}
    model["directory"] = directory
    chapters = {item.get("id"): item for item in model.get("chapters") or [] if isinstance(item, dict)}
    for chapter in chapters.values():
        repair_legacy_flow_ownership(chapter)
    ordered: list[dict] = []
    for index, entry in enumerate(directory.get("entries") or []):
        if not isinstance(entry, dict):
            continue
        chapter = chapters.get(entry.get("chapterId"))
        if not chapter:
            continue
        summary = chapter_gameplay_summary(chapter, first_use=index == 0)
        normalized_title = normalize_game_term(_text(entry.get("title") or chapter.get("scope")))
        if normalized_title:
            entry["title"] = normalized_title
            chapter["scope"] = normalized_title
        if entry.get("summarySource") != "planner" and chapter.get("plannerSummarySource") != "planner":
            chapter["plannerSummary"] = summary
        if entry.get("summarySource") != "planner":
            entry["summary"] = summary
        ordered.append(chapter)
    understanding = directory.setdefault("understanding", {})
    legacy_summary = _legacy_gameplay_overview(ordered)
    is_legacy_generated_copy = _text(understanding.get("summary")) == legacy_summary
    current_summary = _text(understanding.get("summary"))
    is_previous_schema_copy = all(label in current_summary for label in ("核心目标：", "基础操作：", "核心循环：", "胜败条件："))
    if directory.get("understandingSource") != "planner" or is_legacy_generated_copy or is_previous_schema_copy:
        structure_phase = _text((model.get("reviewState") or {}).get("structurePhase"))
        if structure_phase in {"systems", "mechanisms", "confirmed"}:
            overview, primary, systems = build_structure_overview(ordered)
            understanding["summary"] = overview
        else:
            understanding["summary"] = build_gameplay_overview(ordered)
            primary, systems = _gameplay_family(ordered)
        understanding["primaryFamily"] = primary
        understanding["supportingMechanics"] = systems
        understanding["uncertainties"] = [] if primary != "待策划确认" else ["需要策划根据完整素材确认主玩法类型"]
    directory["presentationVersion"] = 13
    return model


def _remove_inferred_placeholders(model: dict) -> None:
    """Drop legacy keyword templates that were never supported by source evidence."""
    for chapter in model.get("chapters") or []:
        if not isinstance(chapter, dict):
            continue
        rows = chapter.get("parameterSchema") or []
        def inferred_placeholder(item: Any) -> bool:
            source = str(item.get("deliverySource") or item.get("configurationSource") or item.get("source") or "").strip() if isinstance(item, dict) else ""
            return (
                isinstance(item, dict)
                and item.get("evidenceLevel") == "根据素材推断"
                and not source.startswith(("策划人工", "配置表", "参考文档", "素材明确"))
            )
        if isinstance(rows, dict):
            chapter["parameterSchema"] = {key: value for key, value in rows.items() if not inferred_placeholder(value)}
        else:
            chapter["parameterSchema"] = [item for item in rows if not inferred_placeholder(item)]
        formulae = chapter.get("formulae") or []
        removed_formula = any(
            isinstance(item, dict) and item.get("evidenceLevel") == "根据素材推断"
            for item in formulae
        )
        chapter["formulae"] = [item for item in formulae if not (
            isinstance(item, dict) and item.get("evidenceLevel") == "根据素材推断"
        )]
        if removed_formula:
            chapter.pop("configurationSources", None)


def _digest(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def consolidate_gameplay_chapters(model: dict, groups: list[dict]) -> dict:
    """Merge evidence-adjacent fragments into business-sized chapters.

    Every original claim, source frame, planner section and inline evidence is
    retained.  The first chapter id in each group remains canonical so links
    can be rewritten without inventing a parallel identity.
    """
    chapters = {item.get("id"): item for item in model.get("chapters") or [] if isinstance(item, dict)}
    entries = {item.get("chapterId"): item for item in (model.get("directory") or {}).get("entries") or [] if isinstance(item, dict)}
    consumed: set[str] = set()
    merged_chapters: list[dict] = []
    merged_entries: list[dict] = []
    id_map: dict[str, str] = {}

    def unique(items: list[Any]) -> list[Any]:
        result: list[Any] = []
        seen: set[str] = set()
        for item in items:
            key = _digest(item)
            if key not in seen:
                seen.add(key)
                result.append(deepcopy(item))
        return result

    for order, spec in enumerate(groups, 1):
        source_ids = [value for value in spec.get("chapterIds") or [] if value in chapters]
        if not source_ids:
            continue
        canonical_id = source_ids[0]
        sources = [chapters[value] for value in source_ids]
        merged = deepcopy(sources[0])
        merged["scope"] = spec["title"]
        merged["systemName"] = spec.get("systemName", merged.get("systemName"))
        merged["subsystemName"] = spec.get("subsystemName", merged.get("subsystemName"))
        for field in ("claims", "evidenceClaims", "sourceFrameIds", "inlineEvidence", "dependencies", "acceptanceCases", "unknowns", "decisionCards", "parameterSchema", "formulae"):
            merged[field] = unique([item for source in sources for item in (source.get(field) or [])])
        section_keys = ("normalFlow", "keyRules", "specialCases", "acceptanceExamples")
        merged["plannerSections"] = {
            "summary": spec["summary"],
            **{key: unique([item for source in sources for item in (source.get("plannerSections") or {}).get(key, [])]) for key in section_keys},
        }
        merged["plannerSummary"] = spec["summary"]
        merged["plannerSummarySource"] = "planner"
        descriptions = unique([
            (source.get("mechanism") or {}).get("description")
            for source in sources if _text((source.get("mechanism") or {}).get("description"))
        ])
        merged["mechanism"] = {"type": "custom", "description": "".join(_text(item) for item in descriptions)}
        merged_chapters.append(merged)
        base_entry = deepcopy(entries.get(canonical_id) or {"id": f"GDE-{order:03d}", "chapterId": canonical_id})
        base_entry.update({"chapterId": canonical_id, "title": spec["title"], "summary": spec["summary"], "order": order, "summarySource": "planner"})
        merged_entries.append(base_entry)
        for source_id in source_ids:
            consumed.add(source_id)
            id_map[source_id] = canonical_id

    for chapter in model.get("chapters") or []:
        if isinstance(chapter, dict) and chapter.get("id") not in consumed:
            merged_chapters.append(deepcopy(chapter))
    for entry in (model.get("directory") or {}).get("entries") or []:
        if isinstance(entry, dict) and entry.get("chapterId") not in consumed:
            extra = deepcopy(entry)
            extra["order"] = len(merged_entries) + 1
            merged_entries.append(extra)
    for collection in ("tables", "diagrams"):
        for artifact in model.get(collection) or []:
            if isinstance(artifact, dict):
                artifact["chapterIds"] = list(dict.fromkeys(id_map.get(value, value) for value in artifact.get("chapterIds") or []))
    model["chapters"] = merged_chapters
    directory = model.setdefault("directory", {})
    directory["entries"] = merged_entries
    directory["revision"] = int(directory.get("revision") or 0) + 1
    model["revision"] = int(model.get("revision") or 0) + 1
    model.setdefault("reviewState", {})["previewRevision"] = None
    return model


def _planner_owned_snapshot(model: dict) -> dict:
    directory = model.get("directory") if isinstance(model.get("directory"), dict) else {}
    chapters = []
    for chapter in model.get("chapters") or []:
        if not isinstance(chapter, dict):
            continue
        chapters.append({
            "id": chapter.get("id"),
            "plannerSummary": chapter.get("plannerSummary") if chapter.get("plannerSummarySource") == "planner" else None,
            "claims": [item for item in chapter.get("claims") or [] if isinstance(item, dict) and item.get("source") == "planner"],
        })
    return {
        "understanding": directory.get("understanding") if directory.get("understandingSource") == "planner" else None,
        "entries": [
            {"chapterId": item.get("chapterId"), "title": item.get("title"), "summary": item.get("summary")}
            for item in directory.get("entries") or []
            if isinstance(item, dict) and (item.get("summarySource") == "planner" or item.get("titleSource") == "planner")
        ],
        "chapters": chapters,
    }


def _migration_counts(model: dict) -> dict[str, int]:
    inferred_parameters = inferred_formulae = 0
    for chapter in model.get("chapters") or []:
        if not isinstance(chapter, dict):
            continue
        inferred_parameters += sum(
            isinstance(item, dict) and item.get("evidenceLevel") == "根据素材推断"
            for item in (chapter.get("parameterSchema") or []) if isinstance(chapter.get("parameterSchema"), list)
        )
        inferred_formulae += sum(
            isinstance(item, dict) and item.get("evidenceLevel") == "根据素材推断"
            for item in chapter.get("formulae") or []
        )
    return {
        "inferredParameters": inferred_parameters,
        "inferredFormulae": inferred_formulae,
        "historySnapshots": sum(len(item.get("undo") or []) + len(item.get("redo") or []) for item in model.get("editHistory") or [] if isinstance(item, dict)),
        "tables": sum(isinstance(item, dict) and item.get("status") != "deleted" for item in model.get("tables") or []),
        "diagrams": sum(isinstance(item, dict) and item.get("status") != "deleted" for item in model.get("diagrams") or []),
    }


def _rebuild_derived_artifacts(model: dict) -> dict:
    from .gameplay_diagrams import auto_generate_diagrams
    from .gameplay_tables import auto_generate_tables

    reviewed_rows: dict[tuple[str, str], dict] = {}
    for table in model.get("tables") or []:
        if not isinstance(table, dict) or table.get("status") != "reviewed":
            continue
        chapter_id = next(iter(table.get("chapterIds") or []), "")
        for index, row in enumerate(table.get("rows") or []):
            if not isinstance(row, list) or not row:
                continue
            review = next((item for item in table.get("rowReviews") or [] if item.get("rowIndex") == index and item.get("confirmed")), None)
            if review:
                reviewed_rows[(chapter_id, str(row[0]))] = deepcopy(review)
    curated_diagrams = [
        deepcopy(item) for item in model.get("diagrams") or []
        if isinstance(item, dict) and item.get("generationMode") == "curated" and item.get("status") != "deleted"
    ]
    deleted_diagrams = {
        (tuple(item.get("chapterIds") or []), item.get("type")): deepcopy(item.get("feedback") or [])
        for item in model.get("diagrams") or [] if isinstance(item, dict) and item.get("status") == "deleted"
    }
    model["tables"] = []
    model["diagrams"] = []
    rebuilt = auto_generate_tables(model, model.get("revision", 0))
    rebuilt = auto_generate_diagrams(rebuilt, rebuilt.get("revision", 0))
    for table in rebuilt.get("tables") or []:
        chapter_id = next(iter(table.get("chapterIds") or []), "")
        reviews = []
        for index, row in enumerate(table.get("rows") or []):
            preserved = reviewed_rows.get((chapter_id, str(row[0]) if row else ""))
            if preserved:
                preserved["rowIndex"] = index
                reviews.append(preserved)
                if len(row) > 4:
                    row[3] = str(preserved.get("value", row[3]))
                    row[4] = "已确认"
        if reviews:
            table["rowReviews"] = reviews
            if len(reviews) == len(table.get("rows") or []):
                table["status"] = "reviewed"
    for diagram in rebuilt.get("diagrams") or []:
        key = (tuple(diagram.get("chapterIds") or []), diagram.get("type"))
        if key in deleted_diagrams:
            diagram.update({"status": "deleted", "feedback": deleted_diagrams[key]})
    if curated_diagrams:
        curated_keys = {(tuple(item.get("chapterIds") or []), item.get("type")) for item in curated_diagrams}
        generated = [
            item for item in rebuilt.get("diagrams") or []
            if (tuple(item.get("chapterIds") or []), item.get("type")) not in curated_keys
        ]
        rebuilt["diagrams"] = [*curated_diagrams, *generated]
    return rebuilt


def migrate_gameplay_presentation(job: dict, *, dry_run: bool = False, rebuild_derived: bool = False) -> dict:
    """Clean legacy presentation data and rebuild current-revision derivatives.

    Default calls retain the historical compatibility behavior.  ``dry_run``
    returns a report and never mutates the supplied job.
    """
    working = deepcopy(job) if dry_run else job
    model = working.get("gameplayReviewModel")
    if not isinstance(model, dict):
        return {"dryRun": dry_run, "changed": False, "reason": "gameplayReviewModel 缺失"} if dry_run else job
    if not dry_run and not rebuild_derived:
        _remove_inferred_placeholders(model)
        if (model.get("directory") or {}).get("presentationVersion", 0) < 13:
            refresh_directory_copy(model)
        structure_errors = gameplay_structure_quality_errors(model)
        review_state = model.setdefault("reviewState", {})
        if structure_errors:
            review_state["structureQualityErrors"] = structure_errors
            if (model.get("directory") or {}).get("status") != "confirmed":
                model["lifecycleState"] = "generation_required"
                model["contentState"] = "pending"
                review_state["status"] = "generation_required"
        else:
            review_state.pop("structureQualityErrors", None)
        return job
    before = _migration_counts(model)
    planner_before = _digest(_planner_owned_snapshot(model))
    _remove_inferred_placeholders(model)
    refresh_directory_copy(model)
    model["editHistory"] = []
    rebuilt = _rebuild_derived_artifacts(model)
    working["gameplayReviewModel"] = rebuilt
    planner_after = _digest(_planner_owned_snapshot(rebuilt))
    if planner_before != planner_after:
        raise ValueError("migration would overwrite planner-owned content")
    after = _migration_counts(rebuilt)
    report = {
        "dryRun": dry_run,
        "jobId": working.get("id"),
        "beforeRevision": model.get("revision"),
        "afterRevision": rebuilt.get("revision"),
        "before": before,
        "after": after,
        "plannerContentPreserved": True,
        "removed": {key: before[key] - after[key] for key in ("inferredParameters", "inferredFormulae", "historySnapshots")},
        "rebuilt": {"tables": after["tables"], "diagrams": after["diagrams"]},
    }
    if dry_run:
        return report
    working["gameplayMigration"] = report
    return job
