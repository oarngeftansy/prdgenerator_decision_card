from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
JOB_PATH = ROOT / "data" / "jobs" / "8312a91c89e144e6a59f81b982f14c06" / "job.json"

INSIGHTS = {
    "F0001": ("常规战斗画面可见载具、武器栏、敌人和生命信息。", "保留战斗主界面层级，并将生命信息同步到生存规则。"),
    "F0002": ("强化界面同时展示三个候选、武器名称和属性变化。", "采用三选一比较结构；可见属性进入强化规则和字段表。"),
    "F0003": ("强化结果与后续武器选择连续出现。", "用于说明强化确认后继续选择或返回战斗的页面关系。"),
    "F0004": ("候选卡片展示不同武器及其属性收益。", "将武器名称、属性类型和变化值作为候选比较信息。"),
    "F0005": ("终极强化使用区别于普通候选的视觉标识。", "终极词条作为独立状态处理，不与普通数值强化混同。"),
    "F0006": ("终极强化结果后仍存在后续武器选择。", "保留终极词条确认后的页面去向和攻击逻辑变化。"),
    "F0007": ("战斗中可见自动攻击、伤害数字和敌人受击反馈。", "同步到武器自动攻击与命中反馈规则。"),
    "F0008": ("抽取界面以滚动格子展示武器或技能结果。", "单独建立随机武器抽取机制；不套用普通三选一规则。"),
    "F0009": ("技能候选展示名称、说明、数值与刷新入口。", "采用候选比较和刷新入口；刷新消耗缺证据时不写死。"),
    "F0010": ("强化后的攻击表现可在战斗中观察。", "用于核对强化结果确实改变战斗表现，不反推隐藏公式。"),
    "F0011": ("首领来袭警告覆盖当前战斗画面。", "在策划草图中作为阶段切换反馈，并连接到首领战。"),
    "F0012": ("首领战可见独立生命值、载具生命值和密集伤害反馈。", "首领生命值、载具生存和武器输出分别进入对应玩法章节。"),
    "F0013": ("首领剩余生命与另一种攻击表现同时可见。", "说明首领战持续阶段与多种攻击表现；不编造轮换顺序。"),
    "F0014": ("首领战后续状态继续展示生命变化和攻击表现。", "用于核对首领战状态连续性和结算前条件。"),
    "F0015": ("结算页展示结果、奖励和按武器统计的伤害占比。", "奖励清单和伤害统计进入结算规则与字段词典。"),
}

FIELDS = {
    "GCH-001": [
        ("载具当前生命值", "vehicleCurrentHp", "整数", "点", "4434", "竞品战斗截图"),
        ("载具生命值上限", "vehicleMaxHp", "整数", "点", "画面未提供默认值", "生命条结构"),
        ("横向移动边界", "vehicleMoveBounds", "区间", "场景坐标", "画面可见道路范围", "竞品战斗截图"),
    ],
    "GCH-003": [
        ("武器名称", "weaponName", "文本", "—", "火焰喷射器、雷暴枪", "强化卡片"),
        ("武器等级", "weaponLevel", "整数", "级", "卡片可见等级", "强化卡片"),
        ("武器基础伤害", "weaponBaseDamage", "整数", "点", "待配置资料确认", "伤害数字只能证明结果"),
        ("武器攻击范围", "weaponAttackRange", "数值", "场景距离", "待配置资料确认", "强化说明可证明存在范围属性"),
    ],
    "GCH-006": [
        ("首领当前生命比例", "bossHpRate", "百分比", "%", "90.65%、10.80%", "首领战截图"),
        ("关卡计时", "stageElapsedTime", "时间", "分:秒", "04:37", "战斗截图"),
        ("战斗倍率", "battleSpeedRate", "倍率", "倍", "画面可见倍率", "首领战截图"),
    ],
    "GCH-010": [
        ("通关时间", "clearTime", "时间", "分:秒", "结算页展示", "竞品结算截图"),
        ("武器伤害占比", "weaponDamageShare", "百分比", "%", "按武器统计", "竞品结算截图"),
        ("结算奖励", "settlementRewards", "列表", "—", "经验、金币、道具", "竞品结算截图"),
    ],
    "GCH-012": [
        ("候选数量", "upgradeOptionCount", "整数", "项", "3", "强化选择截图"),
        ("刷新剩余次数", "refreshRemainingCount", "整数", "次", "界面可见次数", "强化选择截图"),
        ("火焰喷射范围增幅", "flameRangeBonusRate", "百分比", "%", "+30%", "强化卡片文字"),
        ("雷暴枪伤害增幅", "thunderDamageBonusRate", "百分比", "%", "+100%", "强化卡片文字"),
    ],
    "GCH-016": [
        ("终极喷射方向数", "ultimateDirectionCount", "整数", "个方向", "4", "终极词条说明"),
        ("终极词条伤害修正", "ultimateDamageModifier", "百分比", "%", "-20%", "终极词条说明"),
    ],
    "GCH-018": [
        ("抽取候选格", "drawCandidateSlots", "列表", "格", "以实际界面为准", "竞品抽取截图"),
        ("抽取结果", "drawResult", "对象", "—", "武器或技能", "竞品抽取截图"),
    ],
}

GRANULARITY = {
    "GCH-001": {
        "contentInventory": ("screenshot_fact", ["自动前进", "横向移动", "生命值"]),
        "boundary": ("screenshot_fact", ["移动区域限制", "无效攻击不扣除"]),
        "lifecycle": ("context_inference", ["生命值归零后结束本局"]),
        "interactionFeedback": ("screenshot_fact", ["生命值"]),
        "configuration": ("context_inference", ["载具当前生命值", "载具生命值上限", "横向移动边界"]),
    },
    "GCH-003": {
        "contentInventory": ("screenshot_fact", ["武器名称", "武器等级", "伤害", "攻击范围"]),
        "executionSequence": ("video_sequence", ["寻找攻击范围内的敌人", "自动攻击", "显示伤害数字"]),
        "boundary": ("screenshot_fact", ["目标不在武器有效范围内"]),
        "configuration": ("context_inference", ["武器名称", "武器等级", "武器基础伤害", "武器攻击范围"]),
    },
    "GCH-006": {
        "executionSequence": ("video_sequence", ["首领来袭警告", "进入首领战", "首领生命值归零", "进入关卡结算"]),
        "boundary": ("context_inference", ["载具生命值先归零", "失败结束"]),
        "configuration": ("context_inference", ["首领当前生命比例", "关卡计时", "战斗倍率"]),
        "presentationContract": ("screenshot_fact", ["首领警告", "独立生命值"]),
    },
    "GCH-010": {
        "contentInventory": ("screenshot_fact", ["通关时间", "经验", "金币", "道具", "伤害统计"]),
        "boundary": ("context_inference", ["成功结果互斥"]),
        "configuration": ("context_inference", ["通关时间", "武器伤害占比", "结算奖励"]),
    },
    "GCH-012": {
        "contentInventory": ("screenshot_fact", ["三个候选强化", "强化名称", "关联武器", "属性"]),
        "executionSequence": ("video_sequence", ["暂停战斗", "展示三个候选", "选择其中一项", "继续战斗"]),
        "boundary": ("context_inference", ["一次选择只应用一个候选", "刷新不等同于确认强化"]),
        "configuration": ("context_inference", ["候选数量", "刷新剩余次数", "火焰喷射范围增幅", "雷暴枪伤害增幅"]),
    },
    "GCH-016": {
        "contentInventory": ("screenshot_fact", ["收益", "代价", "攻击方式"]),
        "executionSequence": ("video_sequence", ["满足终极强化条件", "确认终极词条", "攻击方式发生结构性变化"]),
        "boundary": ("context_inference", ["不能推广为所有终极强化"]),
        "configuration": ("context_inference", ["终极喷射方向数", "终极词条伤害修正"]),
    },
    "GCH-018": {
        "contentInventory": ("screenshot_fact", ["武器", "技能", "抽取结果"]),
        "executionSequence": ("video_sequence", ["格子内容开始滚动", "停止", "形成抽取结果"]),
        "boundary": ("context_inference", ["不能证明奖池权重", "保底", "合成公式"]),
        "configuration": ("context_inference", ["抽取候选格", "抽取结果"]),
    },
}


def main() -> None:
    job = json.loads(JOB_PATH.read_text(encoding="utf-8"))
    competitor = job["reviewModel"].setdefault("referenceBoards", {}).setdefault("competitor", {})
    competitor["insights"] = {
        frame_id: {
            "observed": observed,
            "adopted": adopted,
            "excluded": "截图只证明可见状态，不据此推导隐藏概率、公式、默认值或服务端职责。",
        }
        for frame_id, (observed, adopted) in INSIGHTS.items()
    }
    gameplay = job["gameplayReviewModel"]
    for chapter in gameplay.get("chapters") or []:
        rows = FIELDS.get(str(chapter.get("id") or ""), [])
        chapter["fieldDictionary"] = [
            {
                "plannerName": planner_name,
                "suggestedCodeName": suggested,
                "type": field_type,
                "unit": unit,
                "visibleExample": example,
                "source": source,
                "status": "建议命名，待程序或配置表确认",
            }
            for planner_name, suggested, field_type, unit, example, source in rows
        ]
        chapter["granularityEvidence"] = {
            axis: {
                "applicable": True,
                "sourceType": source_type,
                "sourceIds": list(chapter.get("sourceFrameIds") or []),
                "requiredFacts": facts,
                **({"ordered": True} if axis == "executionSequence" else {}),
            }
            for axis, (source_type, facts) in GRANULARITY.get(str(chapter.get("id") or ""), {}).items()
        }
    gameplay["granularityAuditVersion"] = 2
    acceptance_index = 1
    for chapter in gameplay.get("chapters") or []:
        for item in chapter.get("acceptanceCases") or []:
            item["id"] = f"GAC-{acceptance_index:03d}"
            acceptance_index += 1
    replacements = {
        "GCH-001": {
            "keyRules": {2: "载具生命值随有效受击持续变化；生命值归零后结束本局。"},
            "specialCases": {0: "拖动超出移动区域限制时停在边界；无效攻击不扣除载具生命值。"},
        },
        "GCH-003": {
            "normalFlow": {0: "武器先寻找攻击范围内的敌人；目标有效时自动攻击，并按照自身方式产生投射物、范围伤害或持续伤害。"},
            "keyRules": {0: "武器属性包含武器名称、武器等级和本次强化涉及的属性，用于强化比较与战斗结果判断。"},
        },
        "GCH-006": {"keyRules": {1: "首领警告只负责提示阶段切换；进入首领战后使用独立生命值表示首领剩余状态。"}},
        "GCH-010": {
            "keyRules": {0: "结算内容包括通关时间、经验、金币、道具和按武器汇总的伤害统计，不再参与当局伤害计算。", 1: "载具生命值归零的失败结果与击败首领后的成功结果互斥。"},
            "specialCases": {0: "双倍奖励和返回操作的消耗及发放规则需要补充资料；失败结果与成功结果互斥。"},
        },
        "GCH-012": {
            "normalFlow": {0: "触发升级后暂停战斗，并展示三个候选强化。", 2: "玩家选择其中一项后，该强化立即加入本局，随后继续战斗。"},
            "keyRules": {0: "三个候选强化分别列出强化名称、关联武器和属性，一次选择只应用一个候选。", 1: "属性变化按照对应强化卡片应用，具体数值统一由配置表承载。", 2: "刷新只替换候选，刷新不等同于确认强化。"},
            "specialCases": {0: "一次选择只应用一个候选；刷新不等同于确认强化。升级触发条件和刷新消耗仍需补充依据。"},
        },
        "GCH-016": {
            "summary": "满足终极强化条件后，玩家可选择改变武器攻击逻辑的终极词条；部分词条同时附带属性代价。",
            "keyRules": {0: "终极词条同时说明攻击方式、收益与代价，不应只作为普通数值提升处理。"},
            "specialCases": {0: "伤害降低 20% 只属于对应词条，不能推广为所有终极强化；解锁条件仍需补充依据。"},
        },
        "GCH-018": {
            "normalFlow": {0: "进入抽取阶段后，格子内容开始滚动，并在停止后形成抽取结果。"},
            "keyRules": {0: "抽取结果可以是武器或技能，且与普通三选一强化分开处理。", 1: "当前素材只能证明可见候选，不能据此推导完整奖池。"},
            "specialCases": {0: "当前素材不能证明奖池权重、保底或合成公式；抽取消耗与重复结果处理也需补充依据。"},
        },
    }
    entries = {item.get("chapterId"): item for item in (gameplay.get("directory") or {}).get("entries") or []}
    for chapter in gameplay.get("chapters") or []:
        change = replacements.get(str(chapter.get("id") or ""), {})
        sections = chapter.get("plannerSections") or {}
        if change.get("summary"):
            sections["summary"] = chapter["plannerSummary"] = change["summary"]
            if chapter.get("id") in entries:
                entries[chapter["id"]]["summary"] = change["summary"]
        for section_name in ("normalFlow", "keyRules", "specialCases"):
            for index, value in change.get(section_name, {}).items():
                sections[section_name][index] = value
    for chapter in gameplay.get("chapters") or []:
        for row in chapter.get("parameterSchema") or []:
            if isinstance(row, dict) and row.get("sourceFrameIds"):
                row["evidenceLevel"] = "material"
    gameplay["revision"] = int(gameplay.get("revision") or 0) + 1
    gameplay.setdefault("reviewState", {})["previewRevision"] = None
    job["updatedAt"] = datetime.now(timezone.utc).isoformat()
    temp = JOB_PATH.with_suffix(".stage5-insights.tmp")
    temp.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(JOB_PATH)
    print(json.dumps({"insights": len(INSIGHTS), "fieldRows": sum(map(len, FIELDS.values())), "gameplayRevision": gameplay["revision"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
