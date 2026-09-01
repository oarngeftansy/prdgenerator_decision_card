from __future__ import annotations

import re
from typing import Any

from .gameplay_domain_policy import VALID_SOURCE_SCOPES


SOURCE_TYPES = {
    "screenshot_fact",
    "video_sequence",
    "reference_document",
    "configuration_table",
    "planner_decision",
    "context_inference",
}

AXES = {
    "overviewTraceability": ("概述到正文的落点", ("overviewTraceability",)),
    "contentInventory": ("内容清单", ("contentInventory",)),
    "objectState": ("对象、状态与关系", ("objectStates", "stateTransitions", "entityRelations")),
    "attributeNarrative": ("属性正文说明", ("attributeNarrative",)),
    "configuration": ("配置字段", ("parameterSchema", "parameters", "fieldDictionary", "configurationSources")),
    "executionSequence": ("执行顺序", ("executionSequence", "orderedSteps")),
    "formula": ("公式依据", ("formulae",)),
    "boundary": ("异常与边界", ("boundaryRules", "specialCases")),
    "lifecycle": ("生命周期", ("lifecycle", "lifecycleRules")),
    "interactionFeedback": ("玩家操作与系统反馈", ("interactionFeedback", "playerOperations", "systemFeedback")),
    "runtimeResponsibility": ("制作职责与同步时机", ("runtimeResponsibilities", "responsibilitySequence")),
    "presentationContract": ("表现与载体要求", ("presentationRules", "carrierContract")),
    "scopeStatus": ("版本范围与历史状态", ("scopeStatus", "versionScope")),
}

SOURCE_RESTRICTIONS = {
    "configuration": {"reference_document", "configuration_table", "planner_decision", "context_inference"},
    "formula": {"reference_document", "configuration_table", "planner_decision", "context_inference"},
    "lifecycle": {"reference_document", "configuration_table", "planner_decision", "context_inference"},
    "runtimeResponsibility": {"reference_document", "configuration_table", "planner_decision", "context_inference"},
}

PUBLISHED_CARRIERS = {
    "overviewTraceability": ("summary", "keyRules"),
    "contentInventory": ("summary", "keyRules"),
    "objectState": ("normalFlow", "keyRules", "specialCases"),
    "attributeNarrative": ("attributeSections",),
    "executionSequence": ("normalFlow",),
    "boundary": ("specialCases",),
    "lifecycle": ("keyRules", "specialCases"),
    "interactionFeedback": ("summary", "normalFlow", "keyRules"),
    "runtimeResponsibility": ("keyRules",),
    "presentationContract": ("keyRules", "specialCases"),
    "scopeStatus": ("keyRules", "specialCases"),
}

DIAGRAM_TRIGGER_RE = re.compile(r"流程|阶段|依次|顺序|循环|返回|继续|暂停|恢复|分支|若|否则|随机|抽取|刷新|权重|首领|结算|状态")

MECHANISM_RESPONSIBILITIES: dict[str, dict[str, tuple[str, ...]]] = {
    "movement": {
        "origin": ("当前位置", "起点", "原位置", "进入战斗"),
        "target": ("目标位置", "目标格", "终点", "横向位置"),
        "constraint": ("相邻", "可移动", "路径", "阻挡", "横向操作", "沿路线"),
        "commit": ("移动到", "到达", "更新位置", "保留新的横向位置", "恢复追踪移动", "继续推进"),
        "boundary": ("越界", "失败", "不可移动", "返回原位置"),
    },
    "placement": {
        "eligibility": ("可放置", "未占用", "形状匹配"),
        "occupancy": ("占用", "空格", "格子"),
        "commit": ("放入", "放置完成", "落位"),
        "failure": ("放置失败", "返回原位置", "不可放置"),
        "relocation": ("移动建筑", "换位", "重新放置"),
    },
    "random": {
        "eligibility": ("解锁条件", "进入随机池", "可抽取", "进入条件", "满足终极词条进入条件", "已解锁内容"),
        "pool": ("候选池", "随机池", "候选"),
        "filter": ("过滤", "排除", "移出随机池"),
        "weights": ("权重", "概率"),
        "duplicate": ("重复", "同一候选", "去重"),
        "empty": ("候选不足", "空结果", "无可用候选"),
        "commit": ("确认选择", "玩家确认", "词条确认后", "应用效果", "写入结果", "立即生效", "只应用该项"),
        "reset": ("重置", "下一局", "本局结束"),
    },
    "combat": {
        "target": ("目标", "索敌", "攻击距离"),
        "hit": ("命中", "闪避", "格挡"),
        "damage": ("伤害", "扣除生命值"),
        "death": ("死亡", "生命值归零", "击败"),
        "reset": ("复活", "战斗结束", "下一场"),
    },
    "growth": {
        "trigger": ("升级条件", "经验达到", "消耗", "进入条件", "满足终极词条进入条件"),
        "cost": ("升级消耗", "消耗数量", "所需道具"),
        "effect": ("升级后", "提升", "解锁", "攻击方式发生", "应用卡片中的收益和代价"),
        "cap": ("等级上限", "最大等级", "满级"),
        "reset": ("重置", "继承", "活动结束"),
    },
    "buff": {
        "apply": ("附加", "施加", "获得效果"),
        "duration": ("持续时间", "持续至", "到期"),
        "stack": ("叠加", "层数", "覆盖"),
        "remove": ("移除", "驱散", "失效"),
        "immunity": ("免疫", "不可附加"),
    },
    "inventory": {
        "capacity": ("容量", "栏位", "格子"),
        "placement": ("放入", "放置", "写入背包"),
        "stack": ("堆叠", "叠加", "数量上限"),
        "overflow": ("溢出", "放置失败", "返回原位置", "背包已满"),
        "remove": ("移除", "消耗", "丢弃"),
    },
    "level": {
        "entry": ("进入关卡", "开始挑战"),
        "progress": ("波次", "阶段", "推进"),
        "victory": ("胜利条件", "通关", "胜利", "成功结算", "挑战成功"),
        "failure": ("失败条件", "挑战失败", "失败"),
        "settlement": ("结算", "奖励"),
    },
    "sweep": {
        "eligibility": ("扫荡条件", "已通关", "解锁扫荡"),
        "cost": ("扫荡消耗", "消耗"),
        "limit": ("次数", "上限"),
        "reward": ("奖励", "掉落"),
        "reset": ("重置", "每日", "周期"),
    },
}


def _present(value: Any) -> bool:
    return value not in (None, "", [], {})


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return "\n".join(_text(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return "\n".join(_text(item) for item in value)
    return str(value)


def _normalized(value: Any) -> str:
    return re.sub(r"[\s，。；：、,.!?！？（）()\-—]", "", _text(value)).casefold()


def _required_facts(spec: Any) -> list[str]:
    if not isinstance(spec, dict):
        return []
    return [str(item).strip() for item in spec.get("requiredFacts") or [] if str(item).strip()]


def _axis_required(spec: Any) -> bool:
    if spec is True:
        return True
    if not isinstance(spec, dict):
        return False
    return bool(spec.get("applicable") or spec.get("sourceIds") or spec.get("sources"))


def _axis_value(chapter: dict[str, Any], fields: tuple[str, ...]) -> Any:
    planner = chapter.get("plannerSections") if isinstance(chapter.get("plannerSections"), dict) else {}
    values = []
    for field in fields:
        if _present(chapter.get(field)):
            values.append(chapter[field])
        elif _present(planner.get(field)):
            values.append(planner[field])
    return values or None


def _published_axis_value(chapter: dict[str, Any], axis: str, fields: tuple[str, ...]) -> Any:
    planner = chapter.get("plannerSections") if isinstance(chapter.get("plannerSections"), dict) else {}
    if axis == "contentInventory":
        return chapter.get("contentInventory")
    carrier_fields = PUBLISHED_CARRIERS.get(axis)
    if carrier_fields:
        return [planner.get(field) for field in carrier_fields if _present(planner.get(field))]
    # Configuration and formula content is intentionally carried by reviewed tables/formula blocks.
    return _axis_value(chapter, fields)


def _related_reviewed_tables(model: dict[str, Any], chapter_id: str) -> list[dict[str, Any]]:
    return [table for table in model.get("tables") or [] if isinstance(table, dict)
            and table.get("status") != "deleted" and chapter_id in (table.get("chapterIds") or [])]


def _table_headers(tables: list[dict[str, Any]]) -> set[str]:
    headers: set[str] = set()
    for table in tables:
        columns = table.get("columns") or []
        if columns:
            headers.update(str(item).strip() for item in columns if str(item).strip())
            continue
        rows = table.get("rows") or []
        if rows and isinstance(rows[0], list):
            headers.update(str(item).strip() for item in rows[0] if str(item).strip())
    return headers


def _remediation(title: str, label: str, item: dict[str, Any]) -> dict[str, str]:
    missing = "；".join(item.get("missingFacts") or []) or label
    sources = "、".join(item.get("sourceIds") or []) or "对应素材来源"
    carrier = {"configuration": "配置表", "formula": "公式块", "interactionFeedback": "策划草图"}.get(item.get("axis"), "玩法正文")
    return {
        "basis": f"根据 {sources} 核对{label}。",
        "action": f"在{carrier}补齐或修正：{missing}。",
        "carrier": carrier,
        "impact": "同步更新审核页、P7 预览和飞书文档；未修复前保持导出阻断。",
        "retest": f"保存后重新检查{label}，确认来源要求逐项覆盖且不再出现本问题。",
    }


def mechanism_closure_report(model: dict[str, Any]) -> dict[str, Any]:
    """Check closure only for domains explicitly activated by current evidence."""

    domain_reports: dict[str, dict[str, Any]] = {
        domain: {"status": "not_applicable", "covered": [], "missing": [], "chapterIds": []}
        for domain in MECHANISM_RESPONSIBILITIES
    }
    findings: list[dict[str, Any]] = []
    for chapter in model.get("chapters") or []:
        if not isinstance(chapter, dict):
            continue
        chapter_id = str(chapter.get("id") or "chapter")
        states = chapter.get("domainStates") if isinstance(chapter.get("domainStates"), dict) else {}
        body = _text([
            chapter.get("plannerSections"),
            chapter.get("executionSequence"),
            chapter.get("boundaryRules"),
            chapter.get("lifecycleRules"),
        ])
        unresolved = {str(item).strip() for item in chapter.get("unresolvedResponsibilities") or [] if str(item).strip()}
        cards = [item for item in chapter.get("decisionCards") or [] if isinstance(item, dict)]
        card_keys = {
            str(card.get(key) or "").strip()
            for card in cards
            for key in ("responsibility", "key", "topic", "id")
            if str(card.get(key) or "").strip()
        }
        card_keys.update(
            str(responsibility).strip()
            for card in cards
            for responsibility in (card.get("responsibilities") or [])
            if isinstance(card.get("responsibilities"), list) and str(responsibility).strip()
        )
        for domain, responsibilities in MECHANISM_RESPONSIBILITIES.items():
            state = str(states.get(domain) or "not_applicable")
            if state == "not_applicable":
                continue
            report = domain_reports[domain]
            report["chapterIds"].append(chapter_id)
            required_override = chapter.get("requiredResponsibilities")
            if isinstance(required_override, dict) and isinstance(required_override.get(domain), list):
                required = [key for key in required_override[domain] if key in responsibilities]
            else:
                required = list(responsibilities)
            covered = [
                key for key in required
                if any(token in body for token in responsibilities[key])
            ]
            missing = [key for key in required if key not in covered]
            report["covered"] = list(dict.fromkeys(report["covered"] + covered))
            report["missing"] = list(dict.fromkeys(report["missing"] + missing))
            report["status"] = "decision_required" if state == "decision_required" or unresolved else ("incomplete" if missing else "satisfied")
            for responsibility in missing:
                if responsibility in card_keys:
                    continue
                findings.append({
                    "chapterId": chapter_id,
                    "domain": domain,
                    "responsibility": responsibility,
                    "axis": "contentInventory",
                    "code": "MECHANISM_RESPONSIBILITY_MISSING",
                    "message": f"《{chapter.get('scope') or domain}》缺少 {responsibility} 对应的条件、处理或结果。",
                    "action": "补充该责任的玩法规则；若当前素材无法唯一判断，则建立决策卡。",
                })
            for responsibility in sorted(unresolved):
                if responsibility in card_keys:
                    continue
                findings.append({
                    "chapterId": chapter_id,
                    "domain": domain,
                    "responsibility": responsibility,
                    "axis": "contentInventory",
                    "code": "MECHANISM_DECISION_CARD_MISSING",
                    "message": f"《{chapter.get('scope') or domain}》的 {responsibility} 尚未确定，但没有对应决策卡。",
                    "action": "提供至少两个可执行选项、自己填写、暂时跳过、判断依据及保存影响。",
                })
    return {"passed": not findings, "findings": findings, "domains": domain_reports}


def granularity_audit_report(model: dict[str, Any]) -> dict[str, Any]:
    """Audit only evidence-applicable depth; never invent a section to satisfy a template."""
    findings: list[dict[str, str]] = []
    chapter_reports: list[dict[str, Any]] = []
    published_carrier_audit = int(model.get("granularityAuditVersion") or 1) >= 2
    for chapter in model.get("chapters") or []:
        if not isinstance(chapter, dict):
            continue
        chapter_id = str(chapter.get("id") or "chapter")
        title = str(chapter.get("scope") or chapter.get("title") or "当前章节")
        evidence = chapter.get("granularityEvidence") if isinstance(chapter.get("granularityEvidence"), dict) else {}
        if int(model.get("granularityAuditVersion") or 1) >= 5:
            source_ids = [str(item) for item in chapter.get("sourceFrameIds") or [] if str(item)]
            planner = chapter.get("plannerSections") if isinstance(chapter.get("plannerSections"), dict) else {}
            inferred: dict[str, dict[str, Any]] = {}
            if source_ids and (chapter.get("claims") or chapter.get("evidenceClaims")):
                inferred["overviewTraceability"] = {
                    "sourceIds": source_ids, "sourceType": "screenshot_fact",
                }
            if source_ids and planner.get("normalFlow"):
                inferred["executionSequence"] = {
                    "sourceIds": source_ids, "sourceType": "screenshot_fact",
                }
                inferred["interactionFeedback"] = {
                    "sourceIds": source_ids, "sourceType": "screenshot_fact",
                }
            if source_ids and chapter.get("presentationRules"):
                inferred["presentationContract"] = {
                    "sourceIds": source_ids, "sourceType": "screenshot_fact",
                }
            if chapter.get("parameterSchema"):
                references = [
                    str(item.get("referenceSource")) for item in chapter.get("parameterSchema") or []
                    if isinstance(item, dict) and str(item.get("referenceSource") or "").strip()
                ]
                inferred["configuration"] = {
                    "sourceIds": references or source_ids,
                    "sourceType": "reference_document" if references else "screenshot_fact",
                }
            if chapter.get("formulae"):
                references = [
                    str(item.get("referenceSource")) for item in chapter.get("formulae") or []
                    if isinstance(item, dict) and str(item.get("referenceSource") or "").strip()
                ]
                inferred["formula"] = {
                    "sourceIds": references or source_ids,
                    "sourceType": "reference_document" if references else "screenshot_fact",
                }
            evidence = {**inferred, **evidence}
        applicable: list[str] = []
        complete: list[str] = []
        axis_reports: dict[str, dict[str, Any]] = {}
        for axis, (label, fields) in AXES.items():
            spec = evidence.get(axis)
            if not _axis_required(spec):
                axis_reports[axis] = {
                    "status": "not_applicable", "sourceIds": [],
                    "requiredFacts": [], "coveredFacts": [], "missingFacts": [],
                }
                continue
            applicable.append(axis)
            source_type = str(spec.get("sourceType") or "") if isinstance(spec, dict) else ""
            source_ids = list(spec.get("sourceIds") or spec.get("sources") or []) if isinstance(spec, dict) else []
            required_facts = _required_facts(spec)
            allowed_sources = SOURCE_RESTRICTIONS.get(axis)
            unsupported = bool(source_type and allowed_sources and source_type not in allowed_sources)
            if unsupported:
                findings.append({
                    "chapterId": chapter_id,
                    "axis": axis,
                    "code": "GRANULARITY_EVIDENCE_SOURCE_UNSUPPORTED",
                    "message": f"《{title}》的{label}目前只有画面或时序线索，不能据此写成已确认结论。",
                })
            if axis == "configuration" and isinstance(spec, dict) and spec.get("requiredColumns"):
                required_columns = [str(item).strip() for item in spec.get("requiredColumns") or [] if str(item).strip()]
                headers = _table_headers(_related_reviewed_tables(model, chapter_id))
                missing_columns = [item for item in required_columns if item not in headers]
                if missing_columns:
                    findings.append({
                        "chapterId": chapter_id, "axis": axis,
                        "code": "GRANULARITY_CONFIGURATION_COLUMNS_MISSING",
                        "message": f"《{title}》的配置表缺少必需列：{'；'.join(missing_columns)}。正文中的说明不能代替配置表字段。",
                        "sourceIds": source_ids, "missingFacts": missing_columns,
                    })
            value = _published_axis_value(chapter, axis, fields) if published_carrier_audit else _axis_value(chapter, fields)
            normalized_value = _normalized(value)
            covered_facts = [fact for fact in required_facts if _normalized(fact) in normalized_value]
            missing_facts = [fact for fact in required_facts if fact not in covered_facts]
            positions = [normalized_value.find(_normalized(fact)) for fact in required_facts]
            order_invalid = bool(isinstance(spec, dict) and spec.get("ordered") and not missing_facts
                                 and positions != sorted(positions))
            if unsupported:
                status = "unsupported"
            elif not _present(value):
                status = "missing"
                missing_detail = f"，缺少：{'；'.join(missing_facts)}" if missing_facts else ""
                findings.append({
                    "chapterId": chapter_id,
                    "axis": axis,
                    "code": f"GRANULARITY_{axis.upper()}_MISSING",
                    "message": f"《{title}》已有{label}依据，但正文尚未写出{label}{missing_detail}。",
                })
            elif order_invalid:
                status = "missing"
                findings.append({
                    "chapterId": chapter_id,
                    "axis": axis,
                    "code": f"GRANULARITY_{axis.upper()}_ORDER_INVALID",
                    "message": f"《{title}》包含所需步骤，但没有按照来源顺序组织：{' → '.join(required_facts)}。",
                    "sourceIds": source_ids,
                    "missingFacts": [f"按来源顺序重排：{' → '.join(required_facts)}"],
                })
            elif missing_facts:
                status = "missing"
                findings.append({
                    "chapterId": chapter_id,
                    "axis": axis,
                    "code": f"GRANULARITY_{axis.upper()}_FACTS_MISSING",
                    "message": f"《{title}》的{label}尚未写全，缺少：{'；'.join(missing_facts)}。",
                })
            else:
                status = "satisfied"
                complete.append(axis)
            axis_reports[axis] = {
                "status": status,
                "sourceType": source_type or None,
                "sourceIds": source_ids,
                "requiredFacts": required_facts,
                "coveredFacts": covered_facts,
                "missingFacts": missing_facts,
            }

        for index, claim in enumerate(chapter.get("provenanceClaims") or [], 1):
            if not isinstance(claim, dict):
                continue
            source_type = str(claim.get("sourceType") or "")
            source_scope = str(claim.get("sourceScope") or "")
            if source_scope and source_scope not in VALID_SOURCE_SCOPES:
                findings.append({
                    "chapterId": chapter_id,
                    "axis": "provenance",
                    "code": "GRANULARITY_CLAIM_SCOPE_INVALID",
                    "message": f"《{title}》第 {index} 条结论使用了未知来源范围，无法判断它属于当前项目还是样例储备。",
                })
            if source_type not in SOURCE_TYPES:
                findings.append({
                    "chapterId": chapter_id,
                    "axis": "provenance",
                    "code": "GRANULARITY_CLAIM_SOURCE_MISSING",
                    "message": f"《{title}》第 {index} 条结论还没有可核对的信息来源。",
                })
            if source_type == "context_inference":
                inference = claim.get("inference") if isinstance(claim.get("inference"), dict) else {}
                required = ("premises", "steps", "alternatives", "confidence", "publicationAllowed", "publicationReason")
                alternatives = inference.get("alternatives") if isinstance(inference.get("alternatives"), list) else []
                alternatives_replayable = bool(alternatives) and all(
                    isinstance(item, dict) and _present(item.get("explanation")) and _present(item.get("excludedBy"))
                    for item in alternatives
                )
                if any(key not in inference or not _present(inference.get(key)) for key in required) or not alternatives_replayable:
                    findings.append({
                        "chapterId": chapter_id,
                        "axis": "provenance",
                        "code": "GRANULARITY_INFERENCE_CHAIN_INCOMPLETE",
                        "message": f"《{title}》第 {index} 条推断没有写清前提、推理过程、替代解释及排除理由、可信度和发布许可。",
                    })
        chapter_text = _text([
            chapter.get("executionSequence"), chapter.get("stateTransitions"),
            chapter.get("plannerSections"), chapter.get("mechanism"),
        ])
        sequence_count = len(chapter.get("executionSequence") or [])
        diagram_required = bool(sequence_count >= 3 or DIAGRAM_TRIGGER_RE.search(chapter_text))
        active_diagrams = [item for item in model.get("diagrams") or [] if isinstance(item, dict)
                           and item.get("status") != "deleted" and chapter_id in (item.get("chapterIds") or [])]
        exception = next((item for item in (model.get("diagramReview") or {}).get("exceptions") or []
                          if isinstance(item, dict) and item.get("chapterId") == chapter_id and item.get("reason")), None)
        if int(model.get("granularityAuditVersion") or 1) >= 3 and diagram_required and not active_diagrams and not exception:
            findings.append({
                "chapterId": chapter_id, "axis": "presentationContract",
                "code": "GRANULARITY_REQUIRED_DIAGRAM_MISSING",
                "message": f"《{title}》包含多步流程、判断、循环或状态变化，但尚未提供对应的玩法流程图。",
                "sourceIds": [], "missingFacts": ["补充玩家操作图、系统判定图、算法图或状态图"],
            })
        chapter_reports.append({"chapterId": chapter_id, "applicable": applicable, "complete": complete, "axes": axis_reports})

    coverage = model.get("contentCoverage") if isinstance(model.get("contentCoverage"), dict) else {}
    coverage_items = [item for item in coverage.get("items") or [] if isinstance(item, dict)]
    for item in coverage_items:
        status = str(item.get("status") or "").strip()
        carrier_ids = [str(value) for value in item.get("carrierIds") or [] if str(value)]
        source_ids = [str(value) for value in item.get("sourceIds") or [] if str(value)]
        if status not in {"covered", "decision_required", "not_applicable"} or (status == "covered" and not carrier_ids):
            findings.append({
                "chapterId": str(carrier_ids[0] if carrier_ids else "content-coverage"),
                "axis": "contentInventory", "code": "CONTENT_COVERAGE_ITEM_UNMAPPED",
                "message": f"内容《{item.get('label') or item.get('id') or '未命名内容'}》已有素材依据，但尚未落入正文、表格、图解或决策卡。",
                "sourceIds": source_ids, "missingFacts": [str(item.get("label") or "补充内容落点")],
            })
    if int(model.get("granularityAuditVersion") or 1) >= 3 and model.get("chapters") and not coverage_items:
        findings.append({
            "chapterId": "content-coverage", "axis": "contentInventory",
            "code": "CONTENT_COVERAGE_INVENTORY_MISSING",
            "message": "当前文档尚未建立全量内容盘点，不能仅根据已有章节判断内容完整。",
            "sourceIds": [], "missingFacts": ["建立来源到内容再到载体的全量映射"],
        })
    if int(model.get("granularityAuditVersion") or 1) >= 4:
        generic_header_schemas = (
            {"属性", "说明", "类型与单位", "配置或计算", "限制条件"},
            {"字段", "策划含义", "当前值与范围", "类型与单位", "配置来源"},
            {"名称", "填写格式", "单位", "默认值"},
        )
        for table in model.get("tables") or []:
            if not isinstance(table, dict) or table.get("status") == "deleted":
                continue
            headers = {str(item).strip() for item in table.get("columns") or [] if str(item).strip()}
            if any(schema.issubset(headers) for schema in generic_header_schemas):
                findings.append({
                    "chapterId": str((table.get("chapterIds") or ["configuration"])[0]),
                    "axis": "configuration", "code": "GRANULARITY_GENERIC_CONFIGURATION_TABLE",
                    "message": f"配置表《{table.get('title') or '未命名表格'}》仍使用万能字段审计表头，不能直接用于策划查配。",
                    "sourceIds": [],
                    "missingFacts": ["按机制拆成等级、消耗、属性、解锁、词条、怪物或波次等专用列"],
                })
    closure = mechanism_closure_report(model)
    findings.extend(closure["findings"])
    for item in findings:
        axis = item.get("axis") or "contentInventory"
        label = AXES.get(axis, ("信息来源", ()))[0]
        if "sourceIds" not in item:
            report = next((chapter for chapter in chapter_reports if chapter["chapterId"] == item.get("chapterId")), None)
            axis_report = (report or {}).get("axes", {}).get(axis, {})
            item["sourceIds"] = axis_report.get("sourceIds") or []
            item["missingFacts"] = axis_report.get("missingFacts") or []
        title = next((str(chapter.get("scope") or chapter.get("title") or "当前章节") for chapter in model.get("chapters") or [] if str(chapter.get("id") or "chapter") == item.get("chapterId")), "当前章节")
        item["remediation"] = _remediation(title, label, item)
    return {"passed": not findings, "findings": findings, "chapters": chapter_reports,
            "mechanismClosure": closure,
            "contentCoverage": {"total": len(coverage_items),
                                "covered": sum(item.get("status") == "covered" for item in coverage_items),
                                "decisionRequired": sum(item.get("status") == "decision_required" for item in coverage_items),
                                "notApplicable": sum(item.get("status") == "not_applicable" for item in coverage_items)}}


def granularity_blocker_ids(model: dict[str, Any]) -> list[str]:
    return list(dict.fromkeys(item["code"] for item in granularity_audit_report(model)["findings"]))
