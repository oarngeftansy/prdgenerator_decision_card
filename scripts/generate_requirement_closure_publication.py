from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.game_rule_synthesis import attach_approved_requirement_rules
from backend.gameplay_rule_chain_reconstruction import (
    attach_approved_requirement_rules as attach_approved_rules_to_chains,
)
from backend.gve16_carrier_selection import append_synthesis_rules_to_chapters, build_carrier_plan, enrich_structured_chapters
from backend.gve16_chapter_assembly import assemble_gve16_chapters
from backend.mechanic_requirement_discovery import build_mechanic_skeleton_placeholder
from backend.rule_provenance_bridge import build_rule_provenance_bridge, project_chains_to_synthesized_rules


ART = ROOT / "artifacts"
DISCOVERY = ART / "mechanic-requirement-discovery-2026-08-18"
CLOSURE = ART / "mechanic-requirement-closure-2026-08-18"
OUT = ART / "mechanic-requirement-closure-publication-2026-08-18"


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(name: str, value) -> None:
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def append_placeholder(chapters: list[dict], placeholder: dict) -> None:
    chapter = next((item for item in chapters if item["title"] == placeholder["ownerChapter"]), None)
    if chapter is None:
        chapter = {"title": placeholder["ownerChapter"], "sections": []}
        chapters.append(chapter)
    section = next((item for item in chapter["sections"] if item["title"] == placeholder["ruleGroup"]), None)
    if section is None:
        section = {"title": placeholder["ruleGroup"], "sourceGroupIds": [], "items": []}
        chapter["sections"].append(section)
    section["items"].insert(0, {
        "text": placeholder["text"], "supportingRuleIds": [], "sourceDimensionIds": [],
        "itemType": placeholder["itemType"], "requirementIds": placeholder["requirementIds"],
        "isValidRule": False,
    })


def approved_publication_only(chapters: list[dict]) -> list[dict]:
    """Strip Review Layer data while preserving approved rule structure."""
    review_terms = ("待确认", "待审核", "AI建议", "AI推演", "推荐方案")
    for chapter in chapters:
        kept_sections = []
        for section in chapter.get("sections", []):
            kept_items = []
            for item in section.get("items", []):
                if item.get("isValidRule") is False or any(term in item.get("text", "") for term in review_terms):
                    continue
                item.pop("reviewAttachments", None)
                if "parameterAttachments" in item:
                    item["parameterAttachments"] = [
                        attachment for attachment in item["parameterAttachments"]
                        if not any(term in attachment.get("text", "") for term in review_terms)
                    ]
                    if not item["parameterAttachments"]:
                        item.pop("parameterAttachments")
                kept_items.append(item)
            if kept_items:
                section["items"] = kept_items
                kept_sections.append(section)
        chapter["sections"] = kept_sections
    return [chapter for chapter in chapters if chapter.get("sections")]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    synthesis = read(ART / "planning-content-phase6.2.2-game-rule-synthesis-2026-08-17/game-rule-synthesis.json")
    approved_mechanic_rules = read(
        ART / "mechanic-design-synthesis-2026-08-18/approved-mechanic-rules.json"
    )["rules"]
    approved_owner_map = {
        rule["mechanicId"]: {
            "ownerChapter": rule["planningOwnerPath"][0],
            "ruleGroup": " / ".join(rule["planningOwnerPath"][1:]),
        }
        for rule in approved_mechanic_rules if rule.get("planningOwnerPath")
    }
    synthesis = attach_approved_requirement_rules(
        synthesis, approved_mechanic_rules, owner_by_mechanic=approved_owner_map)
    synthesis = attach_approved_requirement_rules(
        synthesis, read(DISCOVERY / "approved-business-rules.json"), owner_by_mechanic={
            "PMECH-B1DB0C6035A1": {"ownerChapter": "关卡结束", "ruleGroup": "战斗统计"},
            "PMECH-BBD7CED5E8D0": {"ownerChapter": "关卡推进", "ruleGroup": "关卡流程"},
        })
    closure_rules = read(CLOSURE / "closure-rules.json")
    owner_specs = {
        "RULE-CF719EA1E5E4": {"ownerChapter": "局内成长", "ruleGroup": "独立抽取"},
        "RULE-6297BE181A80": {"ownerChapter": "关卡推进", "ruleGroup": "关卡流程"},
        "RULE-6D655A0E67FF": {"ownerChapter": "关卡推进", "ruleGroup": "胜负判定"},
    }
    for rule in closure_rules:
        synthesis = attach_approved_requirement_rules(
            synthesis, [rule], owner_by_mechanic={rule["mechanicId"]: owner_specs[rule["ruleId"]]})

    native = read(ART / "planning-content-phase6.3-native-language-2026-08-18/native-language-result.json")
    baseline_ids = {item["ruleId"] for item in native.get("rules", [])}
    added_syn = [item for item in synthesis["gameRules"] if item.get("sourceRuleIds")]
    chapters = append_synthesis_rules_to_chapters(native["chapters"], added_syn)

    requirement_report = read(CLOSURE / "requirements-after-closure.json")
    requirements = requirement_report["requirements"]
    skeleton_specs = [
        ("monster", "PMECH-2C4FBE5EC68C", "怪物", "移动与攻击闭环", [
            {"text": "怪物向载具移动"}, {"text": "接触载具后造成伤害"},
            {"requirementId": "REQ-D8ED31CA831ACC91", "placeholder": "攻击退出条件待确认"},
            {"requirementId": "REQ-F43B939B70489678", "placeholder": "退出后状态待确认"}]),
        ("weapon", "PMECH-831F3EDC1472", "核心战斗", "武器执行闭环", [
            {"text": "获得武器"}, {"requirementId": "REQ-F61EFECBFE1093E8", "placeholder": "栏位激活规则待确认"},
            {"text": "自动攻击射程内敌人"}, {"requirementId": "REQ-2CA80CDD2FD5C988", "placeholder": "伤害触发方式待确认"},
            {"text": "伤害归属于对应武器"}]),
        ("choice", "PMECH-79F65266B17C", "局内成长", "三选一闭环", [
            {"text": "战斗等级提升"}, {"text": "生成3张候选"}, {"text": "选择并生效"},
            {"requirementId": "REQ-0CD68EDF526496E5", "placeholder": "退出条件待确认"}]),
        ("draw", "PMECH-831F3EDC1472", "局内成长", "独立抽取闭环", [
            {"requirementId": "REQ-CC85AEBF7CB1C8BE", "placeholder": "进入条件待确认"},
            {"text": "滚动并展示3项结果"},
            {"requirementId": "REQ-04DCE92677DEB71C", "placeholder": "结果确认方式待确认"},
            {"requirementId": "REQ-E0ABE960A787E54B", "placeholder": "返回战斗条件待确认"}]),
        ("boss", "PMECH-BBD7CED5E8D0", "关卡推进", "Boss 与关卡完成闭环", [
            {"text": "普通战斗"}, {"text": "首领来袭并进入首领战"},
            {"text": "Boss 消失后继续清理残敌"},
            {"requirementId": "REQ-48739C98EAF115E3", "placeholder": "关卡正式完成条件待确认"},
            {"text": "成功结算"}]),
        ("statistics", "PMECH-B1DB0C6035A1", "关卡结束", "伤害统计闭环", [
            {"requirementId": "REQ-1F2D406715B8BE19", "placeholder": "统计开始时机待确认"},
            {"text": "按武器累计本局伤害"}, {"text": "结算展示总伤害与各武器占比"},
            {"requirementId": "REQ-D71ECA4159A4E92B", "placeholder": "统计结束时机待确认"}]),
        ("outcome", "PMECH-B1DB0C6035A1", "关卡推进", "胜负与结算闭环", [
            {"text": "载具生命值归零触发失败"}, {"text": "关卡完成后进入成功结算"},
            {"requirementId": "REQ-BE6353FE4885C26C", "placeholder": "结算后状态待确认"}]),
    ]
    # Review placeholders never enter the Final Publication. Approved rules above
    # either provide a viable mechanic, or the unresolved slot remains internal.
    placeholders = []

    source_lines = [line for chapter in read(ART / "planning-content-phase6.2-content-richness-density-2026-08-17/all-chapter-preview.json")["chapters"]
                    for line in chapter.get("lines", [])]
    bridge = build_rule_provenance_bridge(synthesis["gameRules"], source_lines)
    chains = attach_approved_rules_to_chains(
        read(DISCOVERY / "gameplay-rule-chains-with-requirements.json"),
        approved_mechanic_rules,
    )
    projection = project_chains_to_synthesized_rules(chains, bridge)
    typed = read(ART / "planning-content-phase6.2.4-instance-value-gate-2026-08-18/semantic-typed-synthesized-rules.json") + added_syn
    chapters = enrich_structured_chapters(
        chapters, typed, read(ART / "current-system-hierarchy-audit-2026-08-18/current-system-hierarchy-audit.json"), projection)
    chapters = approved_publication_only(chapters)
    plans = build_carrier_plan(chapters)
    assembly = assemble_gve16_chapters(plans, list(dict.fromkeys(plan["chapter"] for plan in plans)))
    markdown = assembly["markdown"]
    (OUT / "human-planning-preview.md").write_text(markdown, encoding="utf-8")
    write("game-rule-synthesis.json", synthesis)
    write("gameplay-rule-chains.json", chains)
    write("mechanic-skeleton-placeholders.json", placeholders)
    write("structured-chapters.json", chapters)
    write("carrier-plan.json", plans)
    write("chapter-assembly-result.json", assembly)
    write("publication-integrity.json", {
        "sha256": hashlib.sha256(markdown.encode()).hexdigest().upper(),
        "placeholderCount": len(placeholders),
        "placeholderRuleCount": 0,
        "publishedApprovedMechanicRuleCount": sum(
            rule["text"] in markdown for rule in approved_mechanic_rules),
        "unpublishedApprovedMechanicRuleIds": [
            rule["ruleId"] for rule in approved_mechanic_rules if rule["text"] not in markdown
        ],
        "duplicateApprovedRuleCount": sum(
            max(0, markdown.count(rule["text"]) - 1) for rule in approved_mechanic_rules
        ),
        "reviewLanguageTerms": [
            term for term in ("待确认", "待审核", "AI建议", "AI推演", "推荐方案") if term in markdown
        ],
        "internalIdTerms": [
            term for term in ("proposalId", "requirementId", "executionDimensionId", "MDES-", "REQ-")
            if term in markdown
        ],
        "publishedClosureRuleIds": [item["ruleId"] for item in closure_rules],
        "unmappedClosureRuleIds": [item["ruleId"] for item in closure_rules
                                   if not bridge["ruleToSyn"].get(item["ruleId"])],
        "forbiddenImmediateBossSettlement": "立即结算" in markdown,
        "lowLevelImplementationTerms": [term for term in ("DamageEvent", "底层事件", "监听哪些具体事件") if term in markdown],
    })


if __name__ == "__main__":
    main()
