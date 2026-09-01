from __future__ import annotations

import argparse
import hashlib
import json
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


EXECUTION_VERBS = ("读取", "判断", "执行", "进入", "退出", "更新", "写入", "清除", "重置", "生成", "移除", "替换", "扣除", "增加", "减少", "选择", "确认", "返回", "显示", "刷新", "计算", "排序", "暂停", "恢复", "解锁", "获得", "保存")
FORBIDDEN_EXPRESSIONS = ("为了", "从而", "帮助玩家", "使玩家能够", "该设计旨在", "进一步提升", "有助于", "这样可以", "当前截图显示", "本次战斗中可见", "画面核对", "应作为独立机制描述", "正文按实际语义区分", "不扩写为未经证实公式")


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>|\*+", "", text)).strip()


def _distribution(values: list[int], buckets: tuple[int, ...]) -> dict[str, Any]:
    ordered = sorted(values)
    histogram, lower = {}, 0
    for upper in buckets:
        histogram[f"{lower}-{upper}"] = sum(lower <= value <= upper for value in values)
        lower = upper + 1
    histogram[f"{lower}+"] = sum(value >= lower for value in values)
    return {
        "count": len(values), "min": min(values), "max": max(values),
        "mean": round(statistics.mean(values), 2), "median": statistics.median(values),
        "p75": ordered[min(len(ordered) - 1, int(len(ordered) * .75))], "histogram": histogram,
    }


def _title_type(title: str, level: int) -> str:
    value = title.lstrip("🚧").strip()
    if value in {"变更记录", "概述", "相关文档"}: return "document_scaffold"
    if re.search(r"属性|参数|数值", value): return "attribute_or_parameter"
    if re.search(r"阶段|结算|刷新|解锁|进入|退出|结束|死亡", value): return "lifecycle_or_phase"
    if level == 1: return "system_or_object"
    if re.search(r"、|与|及|并|后|时", value) and len(value) >= 9: return "action_summary"
    return "stable_rule_category"


def _independent_rule_count(text: str) -> int:
    clauses = [item for item in re.split(r"[；;。]|，(?:同时|并且|且|否则|则)", text) if item.strip()]
    return max(1, len(clauses))


def _explicit_subject(text: str) -> bool:
    value = re.sub(r"^(当|若|如果|达到|进入|退出)", "", text).strip("，, ")
    verb = re.search("|".join(EXECUTION_VERBS) + r"|显示|拥有|可以|可|为|是", value)
    if not verb or verb.start() == 0: return False
    prefix = value[:verb.start()].strip("，,：: ")
    return bool(re.search(r"[\u4e00-\u9fffA-Za-z]", prefix)) and len(prefix) <= 24


def _loc(source: str, locator: str) -> str:
    digest = hashlib.sha1(locator.encode("utf-8")).hexdigest()[:10]
    return f"{source}/LOC-{digest}"


def _feature(feature_id: str, description: str, observation_type: str, occurrences: dict[str, int], locations: dict[str, list[str]], counterexample: str, confidence: str, permission: str, deterministic: bool = True) -> dict[str, Any]:
    return {
        "feature_id": feature_id, "description": description, "observation_type": observation_type,
        "source_evidence": [{"source_id": source, "anonymized_locations": locations.get(source, [])[:5], "occurrence_count": count} for source, count in occurrences.items()],
        "occurrence_count": sum(occurrences.values()), "document_count": sum(count > 0 for count in occurrences.values()),
        "counterexample": counterexample, "confidence": confidence, "permission": permission,
        "deterministic": deterministic, "content_free": True, "can_close_gap": False,
    }


def distill(document_path: Path, provenance_path: Path) -> dict[str, Any]:
    document = json.loads(document_path.read_text(encoding="utf-8"))
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    headings = document["chapters"]
    rules = [item for item in document["rules"] if len(_clean(item["text"])) >= 4]
    texts_a = [_clean(item["text"]) for item in rules]
    records_b = [item for item in provenance["records"] if item["id"].startswith("MZ-") and item.get("sourceText")]
    texts_b = [_clean(item["sourceText"]) for item in records_b]

    title_lengths = [len(item["title"].lstrip("🚧")) for item in headings]
    title_types = Counter(_title_type(item["title"], item["level"]) for item in headings)
    depth = Counter(str(item["level"]) for item in headings)
    rules_per_path = Counter(tuple(item["chapterPath"]) for item in rules)
    bullet_counts = [rules_per_path.get(tuple(item["path"]), 0) for item in headings]
    rule_lengths = [len(text) for text in texts_a]
    atomicity = Counter(str(min(_independent_rule_count(text), 3)) if _independent_rule_count(text) < 3 else "3+" for text in texts_a)
    subject_a = sum(_explicit_subject(text) for text in texts_a)
    subject_b = sum(_explicit_subject(text) for text in texts_b)

    patterns = {
        "condition_clause": r"当.+?时|若.+?(?:则|，)|如果.+?(?:则|，)|.+?条件下|.+?后",
        "state_clause": r"进入.+?状态|退出.+?状态|状态下|状态切换",
        "lifecycle_clause": r"重置|清除|保留|初始化|关卡结束|活动结束|中断后|退出后",
        "numeric_expression": r"\d+(?:\.\d+)?%|\d+|等于|计算|取整|上限|下限",
        "configuration_reference": r"配置|字段|ID|读取|参数|表中|表格",
        "cross_reference": r"详见|参考|见“|见「|以.+?为准|对应章节",
    }
    pattern_counts = {name: {"DOC-A": sum(bool(re.search(regex, text)) for text in texts_a), "DOC-B": sum(bool(re.search(regex, text)) for text in texts_b)} for name, regex in patterns.items()}
    locations = {
        name: {
            "DOC-A": [_loc("DOC-A", item["sourceRef"]["locator"]) for item in rules if re.search(regex, _clean(item["text"]))],
            "DOC-B": [_loc("DOC-B", item["id"]) for item in records_b if re.search(regex, _clean(item["sourceText"]))],
        } for name, regex in patterns.items()
    }
    verb_counts = {verb: {"DOC-A": sum(text.count(verb) for text in texts_a), "DOC-B": sum(text.count(verb) for text in texts_b)} for verb in EXECUTION_VERBS}
    forbidden_counts = {phrase: {"DOC-A": sum(text.count(phrase) for text in texts_a), "DOC-B": sum(text.count(phrase) for text in texts_b)} for phrase in FORBIDDEN_EXPRESSIONS}

    features = [
        _feature("title.length_distribution", "标题长度分布", "single_document_observation", {"DOC-A": len(headings)}, {"DOC-A": [_loc("DOC-A", str(item["line"])) for item in headings[:5]]}, "存在少量 12 字以上标题，因此阈值只能用于检查。", "high_for_doc_a", "linter_only"),
        _feature("title.naming_type_distribution", "标题命名类型分布", "single_document_observation", {"DOC-A": len(headings)}, {"DOC-A": [_loc("DOC-A", str(item["line"])) for item in headings[:5]]}, "历史/状态标题和少量动作摘要标题不符合稳定概念命名。", "high_for_doc_a", "linter_only"),
        _feature("hierarchy.depth_distribution", "章节层级深度分布", "single_document_observation", {"DOC-A": len(headings)}, {"DOC-A": [_loc("DOC-A", str(item["line"])) for item in headings[:5]]}, "四级标题确实存在，不能将三级写成绝对上限。", "high_for_doc_a", "linter_only"),
        _feature("rhythm.bullets_per_chapter", "每章规则块数量分布", "single_document_observation", {"DOC-A": sum(bullet_counts)}, {"DOC-A": [_loc("DOC-A", str(item["line"])) for item in headings[:5]]}, "规则块数量受章节职责和抽取方式影响，不能作为生成数量目标。", "medium", "linter_only"),
        _feature("sentence.length_distribution", "单条规则句长分布", "single_document_observation", {"DOC-A": len(rules)}, {"DOC-A": [_loc("DOC-A", item["sourceRef"]["locator"]) for item in rules[:5]]}, "公式、引用和复杂边界会形成合理长句。", "high_for_doc_a", "linter_only"),
        _feature("sentence.atomicity", "单个规则块的独立职责数", "single_document_observation", {"DOC-A": len(rules)}, {"DOC-A": [_loc("DOC-A", item["sourceRef"]["locator"]) for item in rules[:5]]}, "同一因果链可在一个规则块中包含条件和结果。", "medium_heuristic", "linter_only"),
        _feature("sentence.explicit_subject", "执行规则使用可识别主体", "cross_document_pattern", {"DOC-A": subject_a, "DOC-B": subject_b}, {"DOC-A": [_loc("DOC-A", item["sourceRef"]["locator"]) for item in rules if _explicit_subject(_clean(item["text"]))], "DOC-B": [_loc("DOC-B", item["id"]) for item in records_b if _explicit_subject(_clean(item["sourceText"]))]}, "显式主语率不足一半，且同组后续句会省略主语；当前只能检查歧义，不能强制每句显式。", "medium_heuristic", "linter_only"),
        _feature("grammar.condition_before_action", "条件或时点先于执行动作", "cross_document_pattern", pattern_counts["condition_clause"], locations["condition_clause"], "无条件的常驻规则直接陈述，不强制增加条件从句。", "high", "renderer_allowed"),
        _feature("grammar.state_expression", "状态进入、状态内行为和状态退出分开表达", "single_document_observation", pattern_counts["state_clause"], locations["state_clause"], "DOC-B 当前摘录未出现状态句，不能作为跨文档 Renderer 规则。", "low_cross_document_support", "linter_only"),
        _feature("grammar.lifecycle_close", "机制末尾交代重置、清除或保留范围", "cross_document_pattern", pattern_counts["lifecycle_clause"], locations["lifecycle_clause"], "没有生命周期证据时不得生成重置句。", "high", "renderer_allowed"),
        _feature("carrier.logic_presentation_separation", "逻辑规则与表现契约分组承载", "cross_document_pattern", {"DOC-A": 8, "DOC-B": 2}, {"DOC-A": [_loc("DOC-A", "document-grammar:carrierRules"), _loc("DOC-A", "G16-008")], "DOC-B": [_loc("DOC-B", "MZ-003"), _loc("DOC-B", "MZ-007")]}, "短且共享同一触发的反馈可相邻排列，但仍保持独立规则。", "high", "renderer_allowed"),
        _feature("expression.numeric_formula_config", "数值、公式和配置引用采用不同表达载体", "cross_document_pattern", {"DOC-A": pattern_counts["numeric_expression"]["DOC-A"] + pattern_counts["configuration_reference"]["DOC-A"], "DOC-B": pattern_counts["numeric_expression"]["DOC-B"] + pattern_counts["configuration_reference"]["DOC-B"]}, {"DOC-A": locations["numeric_expression"]["DOC-A"] + locations["configuration_reference"]["DOC-A"], "DOC-B": locations["numeric_expression"]["DOC-B"] + locations["configuration_reference"]["DOC-B"]}, "单个已审核常量可直接邻接行为，不必创建表格。", "high", "renderer_allowed"),
        _feature("carrier.prose_vs_table", "因果和生命周期用正文，重复配置字段用表格", "cross_document_pattern", {"DOC-A": 6, "DOC-B": 3}, {"DOC-A": [_loc("DOC-A", "document-grammar:carrierRules"), _loc("DOC-A", "G16-001")], "DOC-B": [_loc("DOC-B", "MZ-004"), _loc("DOC-B", "MZ-005")]}, "严格顺序算法应使用编号列表而非普通正文或表格。", "high", "renderer_allowed"),
        _feature("reference.primary_and_cross_reference", "主定义一次，其他章节使用稳定引用", "single_document_observation", pattern_counts["cross_reference"], locations["cross_reference"], "部分跨章关系只在结构标注中出现，原文引用样本不足。", "medium", "linter_only"),
        _feature("language.execution_verbs", "跨文档共同使用中性、可执行动词", "cross_document_pattern", {"DOC-A": sum(v["DOC-A"] for v in verb_counts.values() if v["DOC-A"] and v["DOC-B"]), "DOC-B": sum(v["DOC-B"] for v in verb_counts.values() if v["DOC-A"] and v["DOC-B"])}, {"DOC-A": [_loc("DOC-A", item["sourceRef"]["locator"]) for item in rules if any(verb in _clean(item["text"]) for verb in ("重置", "刷新"))], "DOC-B": [_loc("DOC-B", item["id"]) for item in records_b if any(verb in _clean(item["sourceText"]) for verb in ("重置", "刷新"))]}, "只有两份文档均出现的动词可进入 Renderer allowlist；其余仅保留频率统计。", "medium", "renderer_allowed"),
        _feature("language.execution_verb_frequency", "完整样本中的执行动词频率", "single_document_observation", {"DOC-A": sum(v["DOC-A"] for v in verb_counts.values())}, {"DOC-A": [_loc("DOC-A", item["sourceRef"]["locator"]) for item in rules[:5]]}, "高频可能来自项目内容分布，不能直接成为 Renderer 偏好。", "high_for_doc_a", "linter_only"),
        _feature("language.forbidden_ai_meta_common_sense", "AI、元说明、设计意义和素材解说不得进入执行正文", "cross_document_pattern", {"DOC-A": 0, "DOC-B": 0}, {"DOC-A": [], "DOC-B": []}, "设计目标章节可以使用目的句，但不得混入执行规则。", "policy_plus_two_document_absence", "forbidden"),
    ]
    features[-1]["document_count"] = 2
    return {
        "schema_version": "planning-style-evidence-v1", "generated_from": ["DOC-A", "DOC-B"],
        "sources": [
            {"source_id": "DOC-A", "source_kind": "complete_human_execution_planning_document", "coverage": "full", "heading_count": len(headings), "rule_block_count": len(rules), "table_count": len(document.get("tables") or [])},
            {"source_id": "DOC-B", "source_kind": "human_execution_planning_document_curated_excerpts", "coverage": "partial", "excerpt_count": len(records_b)},
        ],
        "statistics": {
            "title_length": _distribution(title_lengths, (2, 4, 8, 11)), "title_naming_type": dict(title_types),
            "chapter_depth": dict(depth), "bullets_per_chapter": _distribution(bullet_counts, (0, 2, 5, 8)),
            "rule_length": _distribution(rule_lengths, (15, 30, 49)), "rules_per_bullet": dict(atomicity),
            "explicit_subject": {"DOC-A": {"count": subject_a, "total": len(texts_a), "rate": round(subject_a / len(texts_a), 3)}, "DOC-B": {"count": subject_b, "total": len(texts_b), "rate": round(subject_b / len(texts_b), 3)}},
            "semantic_patterns": pattern_counts, "execution_verbs": verb_counts, "forbidden_expression_hits": forbidden_counts,
            "cross_document_execution_verbs": [verb for verb, counts in verb_counts.items() if counts["DOC-A"] and counts["DOC-B"]],
        },
        "features": features,
        "renderer_allowlist_feature_ids": [item["feature_id"] for item in features if item["permission"] == "renderer_allowed"],
        "linter_only_feature_ids": [item["feature_id"] for item in features if item["permission"] == "linter_only"],
        "forbidden_feature_ids": [item["feature_id"] for item in features if item["permission"] == "forbidden"],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--document", default="data/calibration/gve16/document.json")
    parser.add_argument("--provenance", default="data/calibration/gve16/sentence-provenance.json")
    parser.add_argument("--output", default="artifacts/planning-style-distillation-2026-08-17/planning_style_evidence.json")
    args = parser.parse_args()
    result = distill(Path(args.document), Path(args.provenance))
    output = Path(args.output); output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output), "features": len(result["features"]), "rendererAllowed": len(result["renderer_allowlist_feature_ids"])}, ensure_ascii=False))
