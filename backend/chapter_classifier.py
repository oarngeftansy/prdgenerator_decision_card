from __future__ import annotations

import re
from dataclasses import dataclass

from .chapter_schema_library import SCHEMA_VERSION, chapter_schema_library


@dataclass(frozen=True)
class ChapterClassification:
    chapter_type: str
    mechanic_variant: str | None
    matched_schema: str | None
    classification_evidence: tuple[str, ...]
    confidence: float


_RULES = (
    ("randomization", ((r"三选一|三张候选|候选卡|老虎机|轮盘|九宫格|随机池|候选池|随机抽取|权重|刷新候选|滚动.*定格", 6), (r"随机|抽取|候选", 3))),
    ("slot", ((r"武器栏|装备栏|自选栏|默认栏|空栏|满栏|栏位|槽位|手牌栏", 6),)),
    ("settlement", ((r"结算界面|进入结算|挑战成功|挑战失败|通关时间|奖励发放|结束回合.*结算|离开结算", 6),)),
    ("movement", ((r"预设路线|沿道路|横向移动|横向调整|自动行进|自动前进|移动路径|移动规则|跟随目标|直线移动|接近攻击目标", 6), (r"移动|行进|位移|路线", 3))),
    ("attack", ((r"自动索敌|进入射程|发射投射物|攻击方式|攻击目标|攻击间隔|近战攻击|远程攻击", 6), (r"攻击|命中|射程|喷射|爆炸|雷暴|伤害区域", 3))),
    ("damage_death", ((r"生命值归零|进入死亡|死亡处理|扣除生命|受击.*生命|实体移除|进入失败", 6), (r"受击|生命值|死亡|血条", 3))),
    ("unlock_progression", ((r"消耗.*升级|升级不可逆|解锁条件|最大等级|活动结束.*重置|局外解锁|养成|词条.*升级", 6), (r"升级|解锁|等级|成长", 3))),
    ("spawn", ((r"生成怪物|怪物生成|波次生成|出生点|刷新怪物|源源不断", 6),)),
    ("level_flow", ((r"关卡.*波次|波次.*阶段|首领阶段|整局时间|倒计时|结束回合|切换行动方|行动点.*耗尽", 6), (r"关卡|波次|阶段推进|回合", 3))),
    ("combat_calculation", ((r"伤害计算|计算公式|计算顺序|最终伤害|倍率.*计算|取整", 6),)),
    ("content_catalog", ((r"内容清单|武器清单|技能清单|多种武器|多个武器类型|武器分类|词条组", 6),)),
    ("attribute", ((r"基础属性|攻击力|固定减伤|属性上限|生命上限", 5),)),
    ("state_machine", ((r"进入.{0,8}状态|退出.{0,8}状态|状态切换|状态机", 4),)),
    ("interaction", ((r"点击|拖动|按钮|摇杆|操作", 2),)),
    ("presentation", ((r"动画|特效|红色遮罩|金色边框|显示.*图标|伤害数字|跳字|界面显示|画面变暗", 3),)),
)


def classify_text(title: str, evidence_texts: list[str]) -> ChapterClassification:
    combined = "\n".join([title, *evidence_texts])
    weighted = [("title", title, 1), *((f"evidence:{index}", text, 3) for index, text in enumerate(evidence_texts, 1))]
    scores = {kind: 0 for kind, _ in _RULES}
    evidence = {kind: [] for kind, _ in _RULES}
    for kind, patterns in _RULES:
        for source, text, source_weight in weighted:
            for pattern, weight in patterns:
                match = re.search(pattern, text or "", re.I)
                if match:
                    scores[kind] += weight * source_weight
                    marker = f"{source} 命中“{match.group(0)}”"
                    if marker not in evidence[kind]:
                        evidence[kind].append(marker)
    order = {kind: index for index, (kind, _) in enumerate(_RULES)}
    winner = min(scores, key=lambda kind: (-scores[kind], order[kind]))
    condition_only_death = (
        re.search(r"生命值归零", combined)
        and re.search(r"停止对局|判定胜负|移交结算|进入.{0,6}结算", combined)
        and not re.search(r"扣除生命|受击处理|死亡状态|死亡处理|实体移除|死亡动画", combined)
    )
    if condition_only_death:
        winner = "level_flow"
        evidence[winner].append("semantic 主行为命中“胜负判定/结束条件/结算触发”")
        scores[winner] = max(scores[winner], 18)
    hud_display_only = (
        re.search(r"显示.{0,12}(?:倒计时|当前等级)|(?:倒计时|当前等级).{0,12}显示", combined)
        and not re.search(r"推进波次|触发.{0,8}阶段|切换.{0,8}阶段|结束条件", combined)
    )
    if hud_display_only:
        winner = "presentation"
        evidence[winner].append("semantic 主行为命中“HUD 显示”")
        scores[winner] = max(scores[winner], 18)
    if scores[winner] < 6:
        return ChapterClassification("unknown", None, None, (), 0.0)
    variant = None
    variant_match = None
    variants = {
        "randomization": (("three_choice", r"三选一|三张候选|三个候选|选择一项"), ("roulette", r"老虎机|轮盘|九宫格|滚动.*定格|中线结果")),
        "attack": (("ranged", r"投射物|射程|远程|喷射|枪|炮"), ("melee", r"近战|挥砍|接触攻击")),
        "movement": (("follow", r"跟随|追踪目标"), ("straight_line", r"直线|预设路线|沿道路|向前推进|自动行进")),
    }
    for candidate, pattern in variants.get(winner, ()):
        match = re.search(pattern, combined, re.I)
        if match:
            variant, variant_match = candidate, match.group(0)
            break
    schema = chapter_schema_library.resolve(winner, variant, SCHEMA_VERSION)
    markers = list(evidence[winner][:6])
    if variant_match:
        markers.append(f"mechanicVariant 命中“{variant_match}”")
    return ChapterClassification(winner, variant, schema.schema_key, tuple(markers), round(min(0.99, 0.45 + scores[winner] / 100), 2))
