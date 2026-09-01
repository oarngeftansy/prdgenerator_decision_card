from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ChapterNamingInput:
    level: int
    system_name: str
    object_name: str | None
    chapter_type: str
    mechanic_variant: str | None
    user_visible_variant_name: str | None
    legacy_title: str | None


@dataclass(frozen=True)
class ChapterNamingResult:
    title: str
    naming_reason: str
    source: str
    title_split: bool
    quality_issues: tuple[str, ...]


_STABLE = {
    "attribute": "基础属性", "movement": "移动", "attack": "攻击",
    "damage_death": "受击及死亡", "slot": "栏位", "unlock_progression": "解锁与养成",
    "spawn": "刷新", "randomization": "随机", "state_machine": "状态",
    "combat_calculation": "战斗计算", "interaction": "交互", "presentation": "战斗表现",
    "settlement": "结算", "level_flow": "关卡流程", "content_catalog": "内容清单",
    "unknown": "待分类",
}
_WHITELIST = {"解锁与养成", "受击及死亡"}
_ACTIONS = re.compile(r"进入|生效|命中|反馈|归集|刷新|确认|跳过|作战|切换|解锁|攻击|养成|成长")
_RESULTS = re.compile(r"生效|结果|归集|完成|成功|失败|进入随机池|阶段切换")


class ChapterNamingPolicy:
    stable_titles = _STABLE

    def inspect(self, title: str, chapter_type: str) -> tuple[str, ...]:
        issues = []
        if len(title) > 12:
            issues.append("too_long")
        if title not in _WHITELIST and ("、" in title or "与" in title or "及" in title):
            issues.append("parallel_connectors")
        if title not in _WHITELIST and len(_ACTIONS.findall(title)) >= 2:
            issues.append("multiple_actions")
        if re.search(r"当|如果|若|则|后|时|，|。", title):
            issues.append("sentence_like")
        if _RESULTS.search(title) and title not in _WHITELIST:
            issues.append("contains_result")
        expected = _STABLE.get(chapter_type)
        if expected and title != expected and title not in _WHITELIST:
            issues.append("chapter_type_mismatch")
        return tuple(dict.fromkeys(issues))

    def name(self, value: ChapterNamingInput) -> ChapterNamingResult:
        if value.level == 1:
            title, source = value.system_name, "system"
        elif value.level == 2 and value.user_visible_variant_name:
            title, source = value.user_visible_variant_name, "user_visible_variant"
        elif value.level == 2 and value.object_name:
            title, source = value.object_name, "object"
        else:
            title, source = _STABLE.get(value.chapter_type, "待分类"), "stable_rule_category"
        old = value.legacy_title or ""
        reason = {
            "system": "一级节点使用已确认系统名",
            "object": "父节点使用素材中的稳定对象名",
            "stable_rule_category": f"{value.chapter_type} 使用跨项目稳定规则类别名",
            "user_visible_variant": "素材明确出现用户可识别的玩法名称",
        }[source]
        return ChapterNamingResult(title, reason, source, bool(old and old != title), self.inspect(title, value.chapter_type) if source == "stable_rule_category" else ())


chapter_naming_policy = ChapterNamingPolicy()
