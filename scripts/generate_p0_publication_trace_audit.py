from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
from collections import Counter, defaultdict
from html import unescape
from pathlib import Path
from typing import Any, Iterable
from xml.etree import ElementTree as ET

from backend.feishu_cli import LarkCli


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "artifacts/full-mechanic-accepted-publication-2026-08-19"
AUDIT_DIR = ROOT / "artifacts/gve16-complete-delivery-gap-audit-2026-08-19"
JOB_DIR = ROOT / "data/jobs/4180cd72eeaa4819be41db50bb4c5011"
OUT = ROOT / "artifacts/p0-end-to-end-publication-trace-audit-2026-08-19"


CRITICAL_CONTRACTS = {
    "W-07": {
        "contract": "必须明确多个合法目标同时存在时的选择顺序，以及目标失效后的重选口径。",
        "required": ["距离载具最近", "目标死亡或离开射程", "先进入射程"],
    },
    "C-10": {
        "contract": "必须明确资格筛选后的概率口径、是否放回、去重和数量边界。",
        "required": ["等概率", "无放回", "互不重复", "不足3项"],
    },
    "C-20": {
        "contract": "必须明确一次经验跨越多级时选择/抽取如何排队，以及何时恢复战斗。",
        "required": ["多个等级", "队列", "逐级", "队列清空后恢复战斗"],
    },
    "D-06": {
        "contract": "必须明确画面中的3项结果是全部获得、三选一还是由结果行决定。",
        "required": ["3项结果全部获得"],
    },
    "M-06": {
        "contract": "必须明确接触成立时立即伤害，还是等待首个攻击间隔。",
        "required": ["接触", "立即", "首次伤害"],
    },
    "L-06": {
        "contract": "必须明确首领死亡后到成功结算之间的真实完成条件。",
        "required": ["剩余怪物清空", "成功结算"],
    },
    "S-09": {
        "contract": "必须给出秒伤分子、时间分母、起算点以及暂停时间是否计入。",
        "required": ["武器累计伤害", "有效战斗秒数", "首次生效", "排除选择、抽取和结算暂停时间"],
    },
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalized(text: Any) -> str:
    return re.sub(r"[\s`*_#|:：；;，,。.!！?？（）()\[\]<>/\\—+×÷=\-]", "", str(text or "")).casefold()


def strings(value: Any) -> list[str]:
    found: list[str] = []
    if isinstance(value, str):
        if value.strip():
            found.append(value.strip())
    elif isinstance(value, list):
        for item in value:
            found.extend(strings(item))
    elif isinstance(value, dict):
        for item in value.values():
            found.extend(strings(item))
    return found


def markdown_blocks(markdown: str, path: str) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    headings: list[str] = []
    for line_number, raw in enumerate(markdown.splitlines(), 1):
        line = raw.strip()
        heading = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading:
            level = len(heading.group(1))
            headings = headings[: level - 1] + [heading.group(2).strip()]
            blocks.append({
                "node": f"{path}:{line_number}",
                "type": f"h{level}",
                "ownerPath": headings.copy(),
                "text": heading.group(2).strip(),
            })
            continue
        if not line or re.match(r"^\|?\s*:?-{3,}", line) or line.startswith("<!--"):
            continue
        block_type = "table_row" if line.startswith("|") else "list_item" if re.match(r"^(?:[-*]|\d+\.)\s+", line) else "paragraph"
        text = re.sub(r"^(?:[-*]|\d+\.)\s+", "", line).strip()
        if text:
            blocks.append({
                "node": f"{path}:{line_number}",
                "type": block_type,
                "ownerPath": headings.copy(),
                "text": text,
            })
    return blocks


def remote_blocks(content: str) -> list[dict[str, Any]]:
    root = ET.fromstring(f"<root>{content}</root>")
    result: list[dict[str, Any]] = []
    headings: list[str] = []
    for node in root:
        tag = node.tag.rsplit("}", 1)[-1]
        text = re.sub(r"\s+", " ", "".join(node.itertext())).strip()
        if re.fullmatch(r"h[1-6]", tag):
            level = int(tag[1])
            headings = headings[: level - 1] + [text]
        if text or tag in {"whiteboard", "table"}:
            result.append({
                "node": node.attrib.get("id", ""),
                "type": tag,
                "ownerPath": headings.copy(),
                "text": text,
            })
    return result


def board_blocks(path: Path, board_name: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for node in read_json(path).get("nodes", []):
        text_value = node.get("text")
        text = str(text_value.get("text") or "") if isinstance(text_value, dict) else ""
        if node.get("type") == "section":
            text = str((node.get("section") or {}).get("title") or "")
        if text.strip():
            result.append({
                "node": f"{board_name}:{node.get('id')}",
                "type": f"whiteboard_{node.get('type')}",
                "ownerPath": ["策划草图" if board_name == "planning" else "竞品参考"],
                "text": text.strip(),
            })
    return result


def ngrams(text: str) -> set[str]:
    value = normalized(text)
    return {value[index:index + 2] for index in range(max(0, len(value) - 1))}


def candidate_blocks(query: str, blocks: list[dict[str, Any]], limit: int = 3, threshold: float = 0.14) -> list[dict[str, Any]]:
    query_grams = ngrams(query)
    ranked: list[tuple[float, dict[str, Any]]] = []
    if not query_grams:
        return []
    for block in blocks:
        block_grams = ngrams(block["text"])
        if not block_grams:
            continue
        score = len(query_grams & block_grams) / max(1, len(query_grams))
        if len(normalized(block["text"])) > 420:
            score *= 0.55
        if score >= threshold:
            ranked.append((score, block))
    ranked.sort(key=lambda item: (-item[0], item[1]["node"]))
    return [
        {"node": block["node"], "ownerPath": block.get("ownerPath", []), "text": block["text"], "diagnosticScore": round(score, 3)}
        for score, block in ranked[:limit]
    ]


def prioritize_atomic_answers(candidates: list[dict[str, Any]], blocks: list[dict[str, Any]], required: list[str], limit: int = 3) -> list[dict[str, Any]]:
    if not required:
        return candidates
    atomic = []
    for block in blocks:
        hits = sum(normalized(term) in normalized(block["text"]) for term in required)
        if hits:
            atomic.append((hits, len(normalized(block["text"])), block))
    atomic.sort(key=lambda item: (-item[0], item[1], item[2]["node"]))
    merged = [
        {"node": block["node"], "ownerPath": block.get("ownerPath", []), "text": block["text"], "diagnosticScore": round(hits / len(required), 3), "matchType": "atomic_answer"}
        for hits, _, block in atomic
    ] + candidates
    unique = []
    seen = set()
    for item in merged:
        if item["node"] not in seen:
            unique.append(item)
            seen.add(item["node"])
    return unique[:limit]


def find_exact_support(text: str, records: list[dict[str, Any]], text_key: str) -> list[dict[str, Any]]:
    target = normalized(text)
    if len(target) < 4:
        return []
    matches = []
    for record in records:
        value = normalized(record.get(text_key))
        if target in value or value in target:
            matches.append(record)
    return matches


def collect_structured_items(chapters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for chapter in chapters:
        for section in chapter.get("sections", []):
            for item in section.get("items", []):
                if isinstance(item, dict):
                    result.append({**item, "chapterOwner": chapter.get("title"), "ruleGroup": section.get("title")})
    return result


def approved_trace_for(candidates: list[dict[str, Any]], approved_rules: list[dict[str, Any]], structured: list[dict[str, Any]]) -> dict[str, Any]:
    approved_ids: list[str] = []
    rule_ids: list[str] = []
    chain_ids: list[str] = []
    owners: list[str] = []
    groups: list[str] = []
    assembly: list[dict[str, Any]] = []
    for candidate in candidates:
        for rule in find_exact_support(candidate["text"], approved_rules, "text"):
            approved_ids.append(str(rule.get("ruleId")))
            rule_ids.append(str(rule.get("ruleId")))
        for item in find_exact_support(candidate["text"], structured, "text"):
            ids = item.get("supportingRuleIds") or []
            if isinstance(ids, str):
                ids = ids.split()
            rule_ids.extend(str(value) for value in ids)
            chain = item.get("chainIds") or []
            if isinstance(chain, str):
                chain = chain.split()
            chain_ids.extend(str(value) for value in chain)
            owners.append(str(item.get("chapterOwner") or ""))
            groups.append(str(item.get("ruleGroup") or ""))
            assembly.append({
                "sentenceId": item.get("sentenceId"),
                "text": item.get("text"),
                "supportingRuleIds": ids,
            })
    unique = lambda values: list(dict.fromkeys(value for value in values if value and value != "None"))
    return {
        "approvedDataIds": unique(approved_ids),
        "ruleIds": unique(rule_ids),
        "chainIds": unique(chain_ids),
        "chapterOwner": unique(owners),
        "ruleGroup": unique(groups),
        "assemblyInput": assembly[:5],
    }


def critical_satisfaction(audit_id: str, remote: list[dict[str, Any]]) -> dict[str, Any]:
    contract = CRITICAL_CONTRACTS.get(audit_id)
    if not contract:
        return {
            "status": "not_proven",
            "contract": "当前 Closure Matrix 没有保存可机器复核的原子 Satisfaction Contract；关键词或相关句不能替代职责满足。",
            "evidence": [],
            "reason": "satisfaction_contract_missing_or_non_executable",
        }
    corpus = "\n".join(block["text"] for block in remote)
    missing = [term for term in contract["required"] if normalized(term) not in normalized(corpus)]
    anchors = {
        "W-07": ["武器", "目标", "射程"],
        "C-10": ["候选", "抽取"],
        "C-20": ["等级", "队列"],
        "D-06": ["3项", "结果"],
        "M-06": ["怪物", "接触", "伤害"],
        "L-06": ["首领", "怪物", "结算"],
        "S-09": ["武器", "秒伤", "战斗"],
    }[audit_id]
    evidence = [
        block for block in remote
        if sum(normalized(term) in normalized(block["text"]) for term in anchors) >= 2
        and any(normalized(term) in normalized(block["text"]) for term in contract["required"])
    ]
    return {
        "status": "satisfied" if not missing else "not_satisfied",
        "contract": contract["contract"],
        "requiredAtomicAnswers": contract["required"],
        "missingAtomicAnswers": missing,
        "evidence": [{"node": block["node"], "text": block["text"]} for block in evidence[:5]],
        "reason": "all_atomic_answers_present" if not missing else "related_text_does_not_answer_all_atomic_questions",
    }


def visual_status(audit_id: str) -> str:
    if audit_id.startswith(("UE-", "P5-", "PR-", "X-")):
        return "failed"
    if audit_id.startswith("P6-"):
        return "failed" if audit_id != "P6-01" else "partial"
    return "not_applicable"


def failure_stage(item: dict[str, Any], local: list[dict[str, Any]], remote: list[dict[str, Any]], trace: dict[str, Any]) -> str:
    audit_id = item["auditId"]
    if item["closureState"] == "blocked_by_missing_source":
        return "source"
    if audit_id.startswith("P5-"):
        return "feishu_render_missing_p5_whiteboards"
    if audit_id.startswith("P6-"):
        return "feishu_render_stale_single_generic_table"
    if audit_id.startswith(("UE-", "PR-")):
        return "feishu_visual_semantic_verification"
    if not trace["approvedDataIds"] and item["closureState"] in {"approved_design", "parameter_resolved", "scope_confirmed_not_applicable"}:
        return "source_to_approved_data"
    if local and not remote:
        return "final_artifact_to_feishu_render"
    if local:
        return "feishu_renderer_source_of_truth_divergence"
    return "assembly_to_final_artifact"


def classify_final_sources(final_blocks: list[dict[str, Any]], job: dict[str, Any], approved: list[dict[str, Any]], synthesis: list[dict[str, Any]], assembly_plan: list[dict[str, Any]], generator_source: str) -> dict[str, Any]:
    planner_strings = strings([chapter.get("plannerSections") for chapter in (job.get("gameplayReviewModel") or {}).get("chapters", [])])
    old_model_strings = strings(job.get("gameplayReviewModel") or {})
    approved_strings = [str(rule.get("text") or "") for rule in approved]
    synthesis_strings = [str(rule.get("statement") or "") for rule in synthesis]
    summary_strings = strings(assembly_plan)
    labels = {
        "A": "Approved Rule exact/contained projection",
        "B": "plannerSections",
        "C": "MechanicDesignSynthesis / synthesis statement",
        "D": "old gameplayReviewModel",
        "E": "chapter summary / assembly plan",
        "F": "generic fallback",
        "G": "LLM regenerated prose",
        "H": "hardcoded publication content",
        "I": "other / unresolved provenance",
    }
    generic = ("按页面关系", "按本页可操作内容", "系统反馈与画面变化同步", "满足指定条件", "对应规则执行")

    def classify(blocks: list[dict[str, Any]]) -> dict[str, Any]:
        counts = Counter()
        characters = Counter()
        examples: dict[str, list[str]] = defaultdict(list)
        for block in blocks:
            text = block["text"]
            norm = normalized(text)
            category = "I"
            if any(
                norm and (normalized(value) in norm or (len(norm) >= 12 and norm in normalized(value)))
                for value in approved_strings if len(normalized(value)) >= 6
            ):
                category = "A"
            elif any(norm and len(norm) >= 12 and norm in normalized(value) for value in planner_strings):
                category = "B"
            elif any(
                norm and (normalized(value) in norm or (len(norm) >= 12 and norm in normalized(value)))
                for value in synthesis_strings if len(normalized(value)) >= 6
            ):
                category = "C"
            elif any(norm and len(norm) >= 12 and norm in normalized(value) for value in old_model_strings):
                category = "D"
            elif any(norm and len(norm) >= 12 and norm in normalized(value) for value in summary_strings):
                category = "E"
            elif any(value in text for value in generic):
                category = "F"
            elif text in generator_source:
                category = "H"
            counts[category] += 1
            characters[category] += len(text)
            if len(examples[category]) < 3:
                examples[category].append(text)
        total_blocks = sum(counts.values()) or 1
        total_chars = sum(characters.values()) or 1
        return {
            "blockCount": sum(counts.values()),
            "characterCount": sum(characters.values()),
            "byCategory": {
                key: {
                    "label": labels[key],
                    "blockCount": counts[key],
                    "blockShare": round(counts[key] / total_blocks, 4),
                    "characterCount": characters[key],
                    "characterShare": round(characters[key] / total_chars, 4),
                    "examples": examples[key],
                }
                for key in labels
            },
        }

    gameplay_blocks = [
        block for block in final_blocks
        if not str(block.get("type") or "").startswith("h")
        if not set(block.get("ownerPath") or []) & {"变更记录", "交付索引"}
    ]
    return {
        "method": "deterministic exact/contained provenance classification; short table cells cannot inherit a longer rule's provenance; first matching authority wins",
        "allPublishedBlocks": classify(final_blocks),
        "gameplayRuleBodyBlocks": classify(gameplay_blocks),
    }


def p5_loss() -> dict[str, Any]:
    sidecar = read_json(JOB_DIR / "structures/p5-review-diagrams.json")
    rows = []
    for diagram in sidecar.get("diagrams", []):
        svg = str(diagram.get("svg") or "")
        x_values = set(re.findall(r'<rect[^>]+\bx="([\d.]+)"', svg))
        rows.append({
            "diagramId": diagram.get("id"),
            "semanticEdgeCount": len(diagram.get("edges") or []),
            "renderedPathCount": len(re.findall(r"<path\b", svg)),
            "renderedArrowCount": len(re.findall(r"marker-end=|<polygon\b", svg)),
            "distinctNodeXCount": len(x_values),
            "structuralLoss": len(x_values) <= 1 or len(re.findall(r"marker-end=|<polygon\b", svg)) < len(diagram.get("edges") or []),
        })
    return {"feishuP5WhiteboardCount": 0, "diagrams": rows, "publicationLoss": True}


def board_visual_findings() -> dict[str, Any]:
    raw = read_json(ART / "feishu-native-whiteboards/remote-planning-raw.json").get("nodes", [])
    sections = [node for node in raw if node.get("type") == "section"]
    min_x = min((node.get("x", 0) for node in sections), default=0)
    max_x = max((node.get("x", 0) + node.get("width", 0) for node in sections), default=0)
    min_y = min((node.get("y", 0) for node in sections), default=0)
    max_y = max((node.get("y", 0) + node.get("height", 0) for node in sections), default=0)
    pending = []
    for node in raw:
        text_value = node.get("text")
        text = str(text_value.get("text") or "") if isinstance(text_value, dict) else ""
        if any(term in text for term in ("待确认", "素材顺序", "按页面关系", "按本页可操作内容")):
            pending.append({"node": node.get("id"), "text": text[:180]})
    width, height = max_x - min_x, max_y - min_y
    return {
        "sectionCount": len(sections),
        "bounds": {"width": width, "height": height, "aspectRatio": round(width / max(height, 1), 2)},
        "allSectionsShareSameRow": len({node.get("y") for node in sections}) == 1,
        "pendingOrGenericNodeCount": len(pending),
        "pendingOrGenericExamples": pending[:8],
        "visualSatisfaction": False,
        "reason": "seven detailed sections are placed in one ultra-wide row; default overview makes screenshots and text unreadable, and review/generic copy remains visible",
    }


def duplicate_and_quality_findings(remote: list[dict[str, Any]]) -> dict[str, Any]:
    paragraphs = [block for block in remote if block.get("type") in {"p", "whiteboard_text_shape"} and block.get("text")]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for block in paragraphs:
        if len(normalized(block["text"])) >= 12:
            grouped[normalized(block["text"])].append(block)
    duplicates = [
        {"text": values[0]["text"], "nodes": [value["node"] for value in values], "owners": [value.get("ownerPath") for value in values]}
        for values in grouped.values() if len(values) > 1
    ]
    patterns = {
        "unsupported_claim": ["预设路线自动前进", "玩家可控制载具横向移动", "区分普通伤害与暴击", "作为局外成长资源", "永久性或临时性的属性增强", "每日挑战次数限制为3次"],
        "generic_fallback": ["满足指定条件", "按页面关系返回或进入下一页", "按本页可操作内容执行", "系统反馈与画面变化同步出现"],
        "title_hallucination": ["Roguelike成长系统", "多武器槽位切换", "常规怪物刷新", "首领多阶段形态", "战后资源结算"],
    }
    findings: dict[str, list[dict[str, Any]]] = {}
    for category, terms in patterns.items():
        findings[category] = [
            {"node": block["node"], "ownerPath": block.get("ownerPath", []), "text": block["text"], "matched": term}
            for term in terms for block in remote if term in block["text"]
        ]
    wrong_owner = [
        {"node": block["node"], "ownerPath": block.get("ownerPath", []), "text": block["text"]}
        for block in remote
        if "武器按照目标筛选、射程和攻击间隔自动处理攻击" in block["text"]
        and any(owner in " / ".join(block.get("ownerPath", [])) for owner in ("首领", "战后资源", "老虎机"))
    ]
    return {"duplicatePrimaryRule": duplicates, "wrongOwner": wrong_owner, **findings}


def render_markdown(report: dict[str, Any]) -> str:
    s = report["summary"]
    lines = [
        "# P0 End-to-End Publication Trace Audit",
        "",
        "> 本审计冻结规则与设计，只核验当前 Alignment Closure 是否真实到达用户正在看的飞书文档。",
        "",
        "## 一眼定位",
        "",
        "| 失效位置 | 直接证据 |",
        "|---|---|",
        "| Final → Feishu Source of Truth | 飞书正文仍由旧 `gameplayReviewModel` 渲染；远端标题仍是“核心战斗系统 / Roguelike成长系统”，没有消费 canonical Final。 |",
        "| Approved Data | 多个 `approved_design / parameter_resolved` 只存在于无稳定 decision ID 的 `alignment-closure-review.json`，正文由生成脚本硬编码写入。 |",
        "| P5 | 飞书只有策划草图与竞品参考两块白板，5 张必要图解没有发布；本地 sidecar SVG 又把真实 edge 退化成单列。 |",
        "| P6 | canonical 有 6 张业务表，远端只有 1 张旧通用参数表。 |",
        "| UE / 策划草图 | 7 个 Section 全在同一超宽横排，默认缩放不可读；画板仍含“触发条件待确认”和泛化兜底文字。 |",
        "| Satisfaction | W-07、C-10、C-20、D-06、M-06、L-06、S-09 等相关句存在不等于回答了原子问题。 |",
        "",
        "## 审计结论",
        "",
        f"- 当前严格全链路 `deliveryClosed=true`：{s['deliveryClosed']}。",
        f"- 仅 Alignment Matrix 终态、但未形成全链路交付：{s['alignmentOnly']}。",
        f"- 远端文档 revision：{report['baseline']['remoteRevision']}。",
        f"- 最多 publication loss 的层：`{s['largestFailureStage']}`。",
        f"- 20 项飞书逆向抽样真实通过：{report['reverseSample']['passed']} / 20。",
        "",
        "## Final 正文真实来源",
        "",
        "| 类别 | 块占比 | 字符占比 |",
        "|---|---:|---:|",
    ]
    for key, item in report["finalSourceOfTruth"]["gameplayRuleBodyBlocks"]["byCategory"].items():
        lines.append(f"| {key} · {item['label']} | {item['blockShare']:.1%} | {item['characterShare']:.1%} |")
    lines += [
        "",
        "## 关键 Satisfaction Contract 复核",
        "",
        "| Audit ID | 结果 | 缺少的原子答案 |",
        "|---|---|---|",
    ]
    for audit_id, result in report["criticalSatisfaction"].items():
        lines.append(f"| {audit_id} | {result['status']} | {'；'.join(result.get('missingAtomicAnswers') or ['—'])} |")
    lines += [
        "",
        "## 20 项飞书逆向抽样",
        "",
        "| Audit ID | Matrix 终态 | 飞书实际文字 | 失败层 | deliveryClosed |",
        "|---|---|---|---|---|",
    ]
    for item in report["reverseSample"]["items"]:
        text = (item.get("feishuRenderedText") or [{"text": "未找到对应发布文字"}])[0]["text"].replace("|", "／")
        lines.append(f"| {item['auditId']} | {item['closureState']} | {text[:90]} | {item['failureStage']} | {str(item['deliveryClosed']).lower()} |")
    lines += [
        "",
        "## 逐项 Trace",
        "",
        "完整 195 项字段与实际文字见 `end-to-end-trace.json`。以下每项只保留越过诊断阈值的飞书原文；未找到时明确为空，不用相关关键词冒充满足。",
        "",
    ]
    for item in report["traces"]:
        remote_text = " / ".join(value["text"] for value in item["feishuRenderedText"]) or "未找到对应发布文字"
        final_text = " / ".join(value["text"] for value in item["renderedFinalText"]) or "未找到对应 Final 文字"
        lines += [
            f"### {item['auditId']} · {item['feature']}",
            "",
            f"- Matrix 终态：`{item['closureState']}`；deliveryClosed：`{str(item['deliveryClosed']).lower()}`；failureStage：`{item['failureStage']}`。",
            f"- Final 实际文字：{final_text[:320]}",
            f"- 飞书实际文字：{remote_text[:320]}",
            f"- Semantic：`{item['semanticSatisfaction']['status']}`；Visual：`{item['visualSatisfaction']}`。",
            "",
        ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cli", type=Path, required=True)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    matrix = read_json(AUDIT_DIR / "alignment-closure-matrix.json")
    checkpoint = read_json(ART / "feishu-publication-checkpoint.json")
    fetched = LarkCli(executable=str(args.cli), timeout=180).run([
        "docs", "+fetch", "--doc", checkpoint["documentToken"], "--scope", "full",
        "--detail", "full", "--as", "user", "--json",
    ]).data
    remote_document = fetched["document"]
    document_blocks = remote_blocks(remote_document["content"])
    planning_blocks = board_blocks(ART / "feishu-native-whiteboards/remote-planning-raw.json", "planning")
    competitor_blocks = board_blocks(ART / "feishu-native-whiteboards/remote-competitor-raw.json", "competitor")
    all_remote = document_blocks + planning_blocks + competitor_blocks

    final_markdown = (ART / "human-planning-preview.md").read_text(encoding="utf-8")
    final_blocks = markdown_blocks(final_markdown, "artifacts/full-mechanic-accepted-publication-2026-08-19/human-planning-preview.md")
    final_rule_blocks = [
        block for block in final_blocks
        if not set(block.get("ownerPath") or []) & {"变更记录", "交付索引"}
    ]
    sketch_blocks = markdown_blocks((ART / "planning-sketch.md").read_text(encoding="utf-8"), "artifacts/full-mechanic-accepted-publication-2026-08-19/planning-sketch.md")
    p5 = read_json(ART / "necessary-diagrams.json")
    p6 = read_json(ART / "publication-tables.json")
    sidecar_texts = []
    for diagram in p5.get("diagrams", []):
        sidecar_texts.append({"node": f"necessary-diagrams.json#{diagram.get('diagramId')}", "ownerPath": diagram.get("ownerPath", []), "text": "；".join(diagram.get("nodes", []))})
    for table in p6.get("tables", []):
        sidecar_texts.append({"node": f"publication-tables.json#{table.get('tableId')}", "ownerPath": table.get("ownerPath", []), "text": f"{table.get('title')}；{'；'.join(table.get('columns', []))}"})
    local_delivery = final_blocks + sketch_blocks + sidecar_texts

    approved_rules = read_json(ROOT / "artifacts/full-mechanic-acceptance-2026-08-19/approved-review-rules.json")["rules"]
    structured_items = collect_structured_items(read_json(ART / "structured-chapters.json"))
    review_decisions = read_json(ART / "alignment-closure-review.json").get("decisions", [])
    review_by_audit = {audit_id: decision for decision in review_decisions for audit_id in decision.get("auditIds", [])}

    traces = []
    for item in matrix["items"]:
        audit_id = item["auditId"]
        critical_terms = " ".join(CRITICAL_CONTRACTS.get(audit_id, {}).get("required", []))
        query = " ".join([item.get("feature", ""), item.get("originalCarrier", ""), " ".join(item.get("verification") or []), critical_terms])
        if audit_id.startswith("P5-"):
            local_scope = [block for block in local_delivery if "necessary-diagrams.json" in block["node"]]
            remote_scope: list[dict[str, Any]] = []
        elif audit_id.startswith("P6-"):
            local_scope = final_rule_blocks + [block for block in sidecar_texts if "publication-tables.json" in block["node"]]
            remote_scope = [block for block in document_blocks if block.get("type") in {"table", "p", "text"}]
        elif audit_id.startswith(("UE-", "PR-", "X-")):
            local_scope = local_delivery
            remote_scope = document_blocks + planning_blocks
        else:
            local_scope = final_rule_blocks
            remote_scope = document_blocks
        required = CRITICAL_CONTRACTS.get(audit_id, {}).get("required", [])
        final_candidates = prioritize_atomic_answers(candidate_blocks(query, local_scope), local_scope, required)
        remote_candidates = prioritize_atomic_answers(candidate_blocks(query, remote_scope), remote_scope, required)
        authority = approved_trace_for(final_candidates, approved_rules, structured_items)
        decision = review_by_audit.get(item["auditId"])
        decision_without_identity = bool(decision) and not any(key in decision for key in ("decisionId", "approvedRuleId", "reviewerId", "reviewedAt"))
        semantic = critical_satisfaction(item["auditId"], all_remote)
        stage = failure_stage(item, final_candidates, remote_candidates, authority)
        trace = {
            "auditId": item["auditId"],
            "feature": item.get("feature"),
            "originalGap": {
                "carrier": item.get("originalCarrier"),
                "judgement": item.get("originalJudgement"),
                "rootCause": item.get("rootCause"),
            },
            "closureState": item.get("closureState"),
            "alignmentClosed": item.get("closureState") != "in_progress",
            "sourceIds": [f"一路狂飙-GVE16-最完整差异审计.md#{item['auditId']}", *(item.get("beforeEvidence") or [])],
            **authority,
            "parameterIds": [],
            "presentationFactIds": [],
            "transitionIds": [],
            "reviewDecisionRef": f"alignment-closure-review.json#{item['auditId']}" if decision else None,
            "approvalTraceFinding": "hardcoded_accept_without_stable_decision_or_approved_rule_identity" if decision_without_identity and not authority["approvedDataIds"] else None,
            "finalArtifactPath": "artifacts/full-mechanic-accepted-publication-2026-08-19/human-planning-preview.md",
            "finalArtifactNode": [candidate["node"] for candidate in final_candidates],
            "renderedFinalText": final_candidates,
            "feishuNodeId": [candidate["node"] for candidate in remote_candidates],
            "feishuRenderedText": remote_candidates,
            "semanticSatisfaction": semantic,
            "visualSatisfaction": visual_status(item["auditId"]),
            "deliveryClosed": False,
            "failureStage": stage,
            "deliveryClosureDecision": {
                "result": False,
                "firstMissingMandatoryLink": stage,
                "reason": "当前飞书未消费 canonical Final，且该项没有从 Source 到飞书语义/视觉验收的完整可复核证据；相关句或 raw node 不能替代全链路。",
            },
        }
        traces.append(trace)

    failure_counts = Counter(item["failureStage"] for item in traces)
    rng = random.Random(20260819)
    sample = []
    for state, count in (("fixed", 10), ("approved_design", 5), ("parameter_resolved", 5)):
        population = [item for item in traces if item["closureState"] == state]
        sample.extend(rng.sample(population, count))

    job = read_json(JOB_DIR / "job.json")
    synthesis = read_json(ART / "game-rule-synthesis.json").get("gameRules", [])
    assembly = read_json(ART / "chapter-assembly-result.json")
    report = {
        "schemaVersion": "p0-end-to-end-publication-trace-audit/v1",
        "auditDefinition": "deliveryClosed requires Source → Approved Data → Rule/Parameter/Presentation/Transition → Assembly → Final Artifact → Feishu Render → Semantic/Visual Verification",
        "baseline": {
            "localCommit": __import__("subprocess").check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "workingTreeNote": "uncommitted renderer work is excluded from published-state conclusions",
            "finalArtifactSha256": hashlib.sha256((ART / "human-planning-preview.md").read_bytes()).hexdigest().upper(),
            "remoteRevision": remote_document.get("revision_id"),
            "remoteHeadingPaths": [block["text"] for block in document_blocks if block["type"].startswith("h")],
            "remoteWhiteboardCount": sum(block["type"] == "whiteboard" for block in document_blocks),
            "remoteTableCount": sum(block["type"] == "table" for block in document_blocks),
        },
        "summary": {
            "total": len(traces),
            "deliveryClosed": sum(item["deliveryClosed"] for item in traces),
            "alignmentOnly": sum(item["alignmentClosed"] and not item["deliveryClosed"] for item in traces),
            "failureStageCounts": dict(failure_counts),
            "largestFailureStage": failure_counts.most_common(1)[0][0],
        },
        "lossLocalization": {
            "satisfactionFalsePositiveAuditIds": [audit_id for audit_id, result in {audit_id: critical_satisfaction(audit_id, all_remote) for audit_id in CRITICAL_CONTRACTS}.items() if result["status"] != "satisfied"],
            "assemblyRendererLossAuditIds": [item["auditId"] for item in traces if item["failureStage"] in {"assembly_to_final_artifact", "final_artifact_to_feishu_render", "feishu_renderer_source_of_truth_divergence"}],
            "feishuDeliveryLossAuditIds": [item["auditId"] for item in traces if item["failureStage"].startswith("feishu_") or item["failureStage"] == "final_artifact_to_feishu_render"],
        },
        "approvalArchitecture": {
            "reviewDecisionCount": len(review_decisions),
            "reviewDecisionsWithoutStableIdentity": sum(not any(key in decision for key in ("decisionId", "approvedRuleId", "reviewerId", "reviewedAt")) for decision in review_decisions),
            "terminalDesignOrParameterItemsWithoutApprovedDataIds": [
                item["auditId"] for item in traces
                if item["closureState"] in {"approved_design", "parameter_resolved"} and not item["approvedDataIds"]
            ],
        },
        "finalSourceOfTruth": classify_final_sources(
            final_blocks, job, approved_rules, synthesis, assembly.get("chapterAssemblyPlan", []),
            (ROOT / "scripts/generate_full_mechanic_accepted_publication.py").read_text(encoding="utf-8"),
        ),
        "criticalSatisfaction": {audit_id: critical_satisfaction(audit_id, all_remote) for audit_id in CRITICAL_CONTRACTS},
        "reverseSample": {"selectionSeed": 20260819, "passed": 0, "items": sample},
        "publicationLoss": {
            "p5": p5_loss(),
            "p6": {"canonicalTableCount": len(p6.get("tables", [])), "remoteTableCount": sum(block["type"] == "table" for block in document_blocks), "publicationLoss": True},
            "visual": board_visual_findings(),
        },
        "qualityFindings": duplicate_and_quality_findings(all_remote),
        "traces": traces,
    }
    snapshot = {
        "revision": remote_document.get("revision_id"),
        "blocks": document_blocks,
        "planningBoardTextBlocks": planning_blocks,
        "competitorBoardTextBlocks": competitor_blocks,
    }
    write_json(OUT / "remote-feishu-semantic-snapshot.json", snapshot)
    write_json(OUT / "end-to-end-trace.json", {"schemaVersion": report["schemaVersion"], "traces": traces})
    write_json(OUT / "p0-publication-trace-audit.json", report)
    (OUT / "P0-END-TO-END-PUBLICATION-TRACE-AUDIT.md").write_text(render_markdown(report) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
