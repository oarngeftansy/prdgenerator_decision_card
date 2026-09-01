from __future__ import annotations

import hashlib
import re

from .planning_content_models import AtomicFact, Rule


_PRESENTATION = re.compile(r"刷新(?:当前)?生命条|显示(?:本次)?伤害跳字|(?:画面|界面|屏幕|头顶|左上角|右侧)[^，。；]*(?:显示|出现|飘出|列出|增加)|显示[^，。；]*(?:界面|图标|数值|文字|血条|等级)|弹出[^，。；]*界面|播放[^，。；]*(?:动画|音效|特效)|(?:伤害)?跳字|红色遮罩|金色边框|高亮|闪烁")
_INTERACTION = re.compile(r"点击|拖拽|长按|滑动|确认选择|按钮")
_NUMERIC = re.compile(r"\d+(?:\.\d+)?%?|公式|倍率|上限|下限|每级|数量|频率|距离|冷却")
_FLOW = re.compile(r"进入[^，。；]*状态|退出[^，。；]*状态|停止对局|进入结算|阶段切换|流程结束|暂停|恢复")
_CONFIG = re.compile(r"读取[^，。；]*配置|独立配置|配置项|配置表")


def _key(owner: str, slot: str, rule_type: str, behavior: str) -> str:
    digest = hashlib.sha1(f"{owner}|{slot}|{rule_type}|{behavior}".encode("utf-8")).hexdigest()[:12]
    return f"{owner}:{slot}:{rule_type}:{digest}"


def _rule(fact: AtomicFact, owner: str, slot: str, rule_type: str, behavior: str, index: int, needs_revision: bool = False) -> Rule:
    semantic_key = _key(owner, slot, rule_type, behavior)
    errors = list(fact.validation_errors)
    cleaned = behavior.strip(" ，,；;。")
    if not cleaned or cleaned.startswith(("的", "间", "点", "及", "与", "并", "）")):
        errors.append("fragment")
    if fact.subject and fact.subject not in cleaned:
        errors.append("missing_subject")
    invalid = needs_revision or fact.review_status == "needs_revision" or fact.evidence_level == "inferred" or bool(errors)
    return Rule(
        rule_id=f"RULE-{hashlib.sha1(f'{fact.fact_id}|{index}|{semantic_key}'.encode()).hexdigest()[:12].upper()}",
        semantic_key=semantic_key, owner_chapter_id=owner, definition_mode="primary",
        rule_type=rule_type, schema_slot=slot, subject=fact.subject,
        trigger=str(fact.qualifiers.get("trigger") or "") or None,
        behavior=cleaned, evidence_ids=fact.evidence_ids, source_fact_ids=(fact.fact_id,),
        review_status="needs_revision" if invalid else "unreviewed",
        semantic_validity="invalid" if errors else ("inferred" if fact.evidence_level == "inferred" else "valid"),
        validation_errors=tuple(dict.fromkeys(errors + (["inferred_evidence"] if fact.evidence_level == "inferred" else []))),
    )


def _classify(clause: str) -> str:
    if _PRESENTATION.search(clause): return "presentation"
    if _INTERACTION.search(clause): return "interaction"
    if _CONFIG.search(clause): return "config"
    if _FLOW.search(clause): return "flow"
    if _NUMERIC.search(clause): return "numeric"
    return "logic"


def separate_atomic_fact(fact: AtomicFact, owner_chapter_id: str, schema_slot: str) -> tuple[Rule, ...]:
    """Construct one independently reviewable Rule per business-atomic fact."""
    source = fact.source_text or fact.object
    if "扣除生命值" in source and "刷新生命条" in source and "伤害跳字" in source:
        subject = fact.subject or "载具"
        return (
            _rule(fact, owner_chapter_id, schema_slot, "logic", f"{subject}受到攻击后扣除生命值。", 1),
            _rule(fact, owner_chapter_id, schema_slot, "presentation", f"{subject}生命值变化后刷新生命条。", 2),
            _rule(fact, owner_chapter_id, schema_slot, "presentation", f"{subject}受到伤害时显示伤害跳字。", 3),
        )
    return (_rule(fact, owner_chapter_id, schema_slot, fact.semantic_type, source, 1),)
