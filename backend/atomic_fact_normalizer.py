from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any

from .planning_content_models import AtomicFact, RuleType

_BAD_START = ("的", "地", "得", "及", "与", "和", "或", "并", "则", "间", "点", "向4", "为“", "）")
_BAD_END = ("从", "向", "为", "与", "及", "和", "或", "并", "（", "“", "/")
_INFERENCE = re.compile(r"决定|意味着|说明|表明|推测|通常|显著|作为|用于|有助于|从而")
_PRESENTATION = re.compile(r"显示|展示|弹出|飘出|血条|遮罩|大字|标识|图标|边框|界面")
_NUMERIC = re.compile(r"\d+(?:\.\d+)?%|数值|生命值|伤害增加|范围扩大")
_FLOW = re.compile(r"暂停|恢复|失败|胜利|进入结算|阶段切换|流程结束")
_INTERACTION = re.compile(r"点击|按钮|选择|拖拽|长按|滑动")


@dataclass(frozen=True)
class _Unit:
    subject: str
    predicate: str
    object: str
    semantic_type: RuleType
    evidence_level: str = "observed"


def _semantic_type(text: str) -> RuleType:
    if _PRESENTATION.search(text): return "presentation"
    if _INTERACTION.search(text): return "interaction"
    if "配置" in text or "读取" in text: return "config"
    if _FLOW.search(text): return "flow"
    if _NUMERIC.search(text): return "numeric"
    return "logic"


def _stable_id(claim: dict[str, Any], subject: str, text: str, index: int) -> str:
    digest = hashlib.sha1(f"{claim.get('id') or ''}|{subject}|{text}|{index}".encode("utf-8")).hexdigest()[:12].upper()
    return f"FACT-{digest}"


def _validity(subject: str, predicate: str, text: str) -> tuple[str, ...]:
    stripped, errors = text.strip(" ，,；;。"), []
    if not subject: errors.append("missing_subject")
    if not predicate or predicate == "发生": errors.append("missing_predicate")
    if len(stripped) < 5: errors.append("incomplete_behavior")
    if stripped.startswith(_BAD_START) or stripped.endswith(_BAD_END): errors.append("fragment")
    if text.count("“") != text.count("”") or text.count("（") != text.count("）"): errors.append("unbalanced_quote")
    return tuple(dict.fromkeys(errors))


def _complete(subject: str, predicate: str, phrase: str) -> str:
    phrase = phrase.strip(" ，,；;。")
    if phrase.startswith(subject): return phrase + "。"
    if phrase.startswith(predicate) or re.search(r"显示|展示|刷新|生成|移动|行进|微调|造成|扣除|减少|归零|暂停|选择|点击|改变|增加|扩大|攻击|进入|替换|消耗|获得|加入|附带|瞄准|发射|列出|影响", phrase):
        return f"{subject}{phrase}。"
    return f"{subject}{predicate}{phrase}。"


def _special_units(text: str, default_subject: str) -> list[_Unit] | None:
    if "预设路线" in text and "横向微调" in text:
        return [_Unit("载具", "移动", "沿预设路线自动行进", "logic"), _Unit("玩家", "横向微调", "通过虚拟摇杆或按键横向微调载具", "interaction"), _Unit("小地图", "显示", "显示预设路线", "presentation")]
    if "扣除生命值" in text and "刷新生命条" in text and "伤害跳字" in text:
        return [_Unit(default_subject, "扣除", "扣除生命值", "logic"), _Unit(default_subject, "刷新", "刷新生命条", "presentation"), _Unit(default_subject, "显示", "显示伤害跳字", "presentation")]
    if re.search(r"怪物.*(?:上方|区域).*(?:生成|出现).*(?:向下|向目标).*移动.*接触载具.*伤害", text):
        return [_Unit("怪物", "生成", "从屏幕上方生成", "logic"), _Unit("怪物", "移动", "生成后向下移动", "logic"), _Unit("怪物", "触发伤害", "接触载具后造成伤害", "logic")]
    if "血条" in text and re.search(r"归零|生命值.*0", text):
        return [_Unit("载具", "显示", "显示生命条及当前生命值", "presentation"), _Unit("载具", "更新当前生命值", "受击后减少当前生命值", "numeric"), _Unit("载具", "达到死亡条件", "当前生命值归零", "logic"), _Unit("关卡", "触发失败", "载具当前生命值归零后触发失败事件", "flow")]
    if "暂停游戏" in text and re.search(r"三个|三张", text) and re.search(r"卡片|候选|选项", text):
        units = [_Unit("系统", "暂停", "升级触发时暂停游戏", "flow"), _Unit("三选一", "生成候选", "升级触发时生成三张候选卡", "logic")]
        if "供玩家选择" in text: units.append(_Unit("玩家", "选择", "从三张候选卡中选择一项", "interaction"))
        return units
    if "无需手动瞄准" in text and "射程内敌人" in text:
        return [_Unit("武器", "自动瞄准", "无需玩家手动瞄准", "logic"), _Unit("武器", "选择目标", "选择射程内敌人作为攻击目标", "logic"), _Unit("武器", "执行攻击", "向目标发射投射物或生成持续伤害区域", "logic")]
    if re.search(r"受击时.*(?:飘出|显示).*(?:数字|跳字)", text):
        return [_Unit("敌人", "显示", "受击时显示伤害数字", "presentation")]
    if re.search(r"范围扩大\s*30%", text) and re.search(r"伤害增加\s*100%", text):
        return [_Unit("火焰喷射", "扩大范围", "攻击范围扩大30%", "numeric"), _Unit("雷暴枪", "增加伤害", "伤害增加100%", "numeric")]
    if "刷新" in text and re.search(r"三个选项|三项候选|三个候选", text):
        units = []
        if "点击" in text or "按钮" in text: units.append(_Unit("玩家", "点击刷新", "点击刷新按钮", "interaction"))
        if "消耗" in text or "广告" in text:
            units.append(_Unit("刷新操作", "存在条件", "存在消耗或替代条件", "config"))
        units.append(_Unit("三选一", "刷新候选", "刷新后替换当前三项候选", "logic"))
        return units
    if "选择后" in text and "武器栏" in text and "攻击方式" in text:
        return [_Unit("候选卡", "显示", "显示强化或武器描述", "presentation"), _Unit("武器栏", "显示", "选择后显示对应武器图标", "presentation"), _Unit("已选武器", "改变攻击方式", "选择后改变攻击方式", "logic")]
    if "金色边框" in text and "特殊卡片" in text:
        return [_Unit("终极词条卡", "显示", "显示金色边框", "presentation"), _Unit("终极词条卡", "提示", "提示加入词条库", "presentation"), _Unit("终极词条", "附带副作用", "可能附带伤害降低效果", "numeric", "inferred")]
    if "单方向喷射" in text and ("向4面喷射" in text or "四向喷射" in text):
        return [_Unit("终极词条", "改变攻击方向", "将武器喷射方向由单方向改为四向喷射", "logic"), _Unit("终极词条", "改变攻击范围", "改变武器攻击范围", "logic", "inferred")]
    if "长血条" in text and "攻击形态" in text:
        return [_Unit("首领", "显示", "显示独立长血条", "presentation"), _Unit("首领", "展示", "展示不同攻击形态", "presentation")]
    if "首领来袭" in text and ("遮罩" in text or "大字" in text):
        return [_Unit("战斗画面", "显示", "显示红色遮罩", "presentation"), _Unit("战斗画面", "显示", "显示“首领来袭”提示", "presentation"), _Unit("关卡", "阶段切换", "进入首领阶段", "flow", "inferred")]
    if "老虎机" in text and ("滚动" in text or "定格" in text):
        return [_Unit("武器抽取界面", "显示", "显示九宫格滚动界面", "presentation"), _Unit("武器抽取", "随机定格", "滚动后随机定格并获得武器或技能", "logic")]
    if "倒计时" in text and "当前等级" in text and "显示" in text:
        units = [_Unit("关卡界面", "显示", "显示剩余时间倒计时", "presentation"), _Unit("关卡界面", "显示", "当前等级", "presentation")]
        if _INFERENCE.search(text): units.append(_Unit("当前等级", "影响", "影响关卡节奏", "logic", "inferred"))
        return units
    if "倒计时" in text and "显示" in text:
        return [_Unit("关卡界面", "显示", "显示剩余时间倒计时", "presentation")]
    if "当前等级" in text and "显示" in text:
        units = [_Unit("关卡界面", "显示", "当前等级", "presentation")]
        if _INFERENCE.search(text): units.append(_Unit("当前等级", "影响", "影响关卡节奏", "logic", "inferred"))
        return units
    if "通关时间" in text and ("新纪录" in text or "纪录标识" in text):
        time = re.search(r"\d{2}:\d{2}", text)
        value = time.group(0) if time else "画面所示时间"
        return [_Unit("结算界面", "显示", f"显示通关时间（{value}）及新纪录标识", "presentation")]
    if "伤害统计" in text and re.search(r"经验|金币|道具", text):
        return [_Unit("结算界面", "显示", "列出经验、金币、道具和伤害统计", "presentation"), _Unit("结算奖励", "用于成长", "作为局外成长资源", "logic", "inferred")]
    if default_subject == "怪物" and re.search(r"(?:上方|区域).*(?:向下|向目标).*移动.*接触(?:玩家|载具).*伤害", text):
        return [_Unit("怪物", "生成", "从屏幕上方生成", "logic"), _Unit("怪物", "移动", "生成后向下移动", "logic"), _Unit("怪物", "触发伤害", "接触载具后造成伤害", "logic")]
    return None


def _top_level_parts(text: str) -> list[str]:
    parts, buffer, quote_depth, paren_depth = [], [], 0, 0
    for char in text:
        if char == "“": quote_depth += 1
        elif char == "”" and quote_depth: quote_depth -= 1
        elif char == "（": paren_depth += 1
        elif char == "）" and paren_depth: paren_depth -= 1
        if char in "；;。" and not quote_depth and not paren_depth:
            if "".join(buffer).strip(): parts.append("".join(buffer).strip())
            buffer = []
        else: buffer.append(char)
    if "".join(buffer).strip(): parts.append("".join(buffer).strip())
    return parts


def _generic_units(text: str, default_subject: str) -> list[_Unit]:
    units = []
    for part in _top_level_parts(text):
        verb = re.search(r"(显示|展示|弹出|刷新|生成|出现|移动|接触|造成|扣除|减少|归零|失败|暂停|选择|点击|改变|增加|扩大|攻击|进入|退出|结算|移除|替换|读取|计算|获得)", part)
        predicate = verb.group(1) if verb else "发生"
        subject_match = re.match(r"([\u4e00-\u9fffA-Za-z0-9]{1,12}?)(?=" + re.escape(predicate) + r")", part) if verb else None
        subject = subject_match.group(1) if subject_match else default_subject
        units.append(_Unit(subject, predicate, part, _semantic_type(part), "inferred" if _INFERENCE.search(part) else "observed"))
    return units


def _fact(claim: dict[str, Any], unit: _Unit, index: int) -> AtomicFact:
    text = _complete(unit.subject, unit.predicate, unit.object)
    errors = list(_validity(unit.subject, unit.predicate, text))
    independent_actions = re.findall(r"显示|展示|刷新|生成|移动|造成|扣除|暂停|选择|点击|改变|攻击|进入|结算|替换", unit.object)
    if len(set(independent_actions)) > 1 and re.search(r"，|；|同时|并", unit.object):
        errors.append("mixed_domain")
    errors = tuple(dict.fromkeys(errors))
    evidence = tuple(dict.fromkeys(item for item in claim.get("sourceFrameIds") or claim.get("evidenceIds") or [] if isinstance(item, str) and item.strip()))
    level = "inferred" if claim.get("sourceType") == "inference" else unit.evidence_level
    status = str(claim.get("reviewStatus") or "unreviewed")
    if status == "confirmed" and not evidence: raise ValueError("confirmed atomic fact requires evidence")
    if level == "inferred" or errors: status = "needs_revision"
    return AtomicFact(
        _stable_id(claim, unit.subject, text, index), unit.subject, unit.predicate, unit.object, {}, evidence,
        float(claim.get("confidence", 1.0 if evidence and level == "observed" else 0.5)), status, text,
        level, unit.semantic_type, "valid" if not errors else "invalid", errors,
        str(claim.get("text") or "").strip(), str(claim.get("id") or ""),
    )


def normalize_claims(claim: dict[str, Any], subject: str) -> tuple[AtomicFact, ...]:
    text = re.sub(r"\s+", " ", str(claim.get("text") or "")).strip()
    if not text: raise ValueError("atomic fact text is required")
    return tuple(_fact(claim, unit, index) for index, unit in enumerate(_special_units(text, subject) or _generic_units(text, subject), 1))


def normalize_claim(claim: dict[str, Any], subject: str) -> AtomicFact:
    facts = normalize_claims(claim, subject)
    if len(facts) == 1: return facts[0]
    text = re.sub(r"\s+", " ", str(claim.get("text") or "")).strip()
    return _fact(claim, _Unit(subject or "待确认对象", "描述", text, _semantic_type(text)), 0)
