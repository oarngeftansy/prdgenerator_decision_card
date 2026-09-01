from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from html import escape
from pathlib import Path

from backend.planning_gameplay_sync import sync_planning_gameplay_insights


ROOT = Path(__file__).resolve().parents[1]
JOB_ID = "8312a91c89e144e6a59f81b982f14c06"
JOB_DIR = ROOT / "data" / "jobs" / JOB_ID
JOB_PATH = JOB_DIR / "job.json"


def p(value: str, *, value_type="文本", unit="无", source="素材截图", meaning="", value_range="—") -> dict:
    return {
        "value": value, "type": value_type, "unit": unit,
        "range": value_range, "source": source, "plannerMeaning": meaning,
    }


def evidence(axis: str, source_ids: list[str], facts: list[str], *, source_type="screenshot_fact", ordered=False) -> dict:
    item = {"applicable": True, "sourceType": source_type, "sourceIds": source_ids, "requiredFacts": facts}
    if ordered:
        item["ordered"] = True
    return item


def card(card_id: str, question: str, options: list[tuple[str, str, bool, str]], evidence_ids: list[str], impacts: list[str]) -> dict:
    return {
        "id": card_id, "question": question, "status": "pending", "selectionMode": "single", "allowCustom": True,
        "options": [{"id": option_id, "label": label, "recommended": recommended, "reason": reason}
                    for option_id, label, recommended, reason in options],
        "evidence": [{"frameId": frame_id, "label": f"截图 {frame_id}"} for frame_id in evidence_ids],
        "impacts": impacts,
    }


def diagram_svg(title: str, nodes: list[dict], edges: list[dict], width=1180, height=520) -> str:
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{escape(title)}" viewBox="0 0 {width} {height}">',
             f'<text x="28" y="38" font-size="22" font-weight="700" fill="#17233f">{escape(title)}</text>']
    for edge in edges:
        x1, y1, x2, y2 = edge["x1"], edge["y1"], edge["x2"], edge["y2"]
        parts.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#8b98aa" stroke-width="2"/>')
        # Explicit arrow head; marker elements are intentionally avoided for Feishu SVG safety.
        if abs(x2 - x1) >= abs(y2 - y1):
            pts = f'{x2},{y2} {x2-10},{y2-6} {x2-10},{y2+6}' if x2 >= x1 else f'{x2},{y2} {x2+10},{y2-6} {x2+10},{y2+6}'
        else:
            pts = f'{x2},{y2} {x2-6},{y2-10} {x2+6},{y2-10}' if y2 >= y1 else f'{x2},{y2} {x2-6},{y2+10} {x2+6},{y2+10}'
        parts.append(f'<polygon points="{pts}" fill="#8b98aa"/>')
        if edge.get("label"):
            parts.append(f'<text x="{edge.get("lx", (x1+x2)//2)}" y="{edge.get("ly", (y1+y2)//2-8)}" font-size="13" fill="#56657a">{escape(edge["label"])}</text>')
    for node in nodes:
        x, y, w, h = node["x"], node["y"], node.get("w", 150), node.get("h", 64)
        decision = node.get("kind") == "decision"
        fill = "#fff3d6" if decision else ("#e7f0ff" if node.get("kind") != "result" else "#e4f7ec")
        stroke = "#f4a340" if decision else ("#4f83ff" if node.get("kind") != "result" else "#35a36f")
        if decision:
            cx, cy = x+w/2, y+h/2
            parts.append(f'<polygon points="{cx},{y} {x+w},{cy} {cx},{y+h} {x},{cy}" fill="{fill}" stroke="{stroke}" stroke-width="2"/>')
        else:
            parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{fill}" stroke="{stroke}" stroke-width="2"/>')
        lines = node["label"].split("\n")
        start_y = y + h/2 - (len(lines)-1)*9 + 5
        for index, line in enumerate(lines):
            parts.append(f'<text x="{x+w/2}" y="{start_y+index*19}" font-size="14" font-weight="600" text-anchor="middle" fill="#17233f">{escape(line)}</text>')
    parts.append('</svg>')
    return "".join(parts)


def diagram(diagram_id: str, title: str, diagram_type: str, chapter_ids: list[str], nodes: list[dict], edges: list[dict], width=1180, height=520) -> dict:
    return {
        "id": diagram_id, "title": title, "type": diagram_type, "chapterIds": chapter_ids,
        "nodes": [{"id": f"{diagram_id}-N{index+1}", "label": node["label"], "sourceIds": chapter_ids} for index, node in enumerate(nodes)],
        "edges": [{"id": f"{diagram_id}-E{index+1}", "from": "", "to": "", "label": edge.get("label", ""), "sourceIds": chapter_ids} for index, edge in enumerate(edges)],
        "svg": diagram_svg(title, nodes, edges, width, height), "status": "reviewed", "freshness": "current",
        "optional": False, "revision": 1,
    }


CHAPTERS = {
    "GCH-001": {
        "flowHeading": "战斗推进、升级与栏位使用",
        "scope": "战场推进与载具生存",
        "section": "核心战斗",
        "subsection": "战场与载具",
        "summary": "载具在纵向战场中持续推进，玩家通过横向移动调整站位；武器负责清理沿途敌人，载具生命值归零时本局失败。",
        "flow": [
            "进入战斗后，界面同时显示关卡计时、局内等级进度、小地图、武器与资源状态、载具生命值。",
            "载具沿道路向前推进；玩家通过横向操作避开密集敌人或调整武器覆盖位置，松开操作后保留新的横向位置。",
            "敌人或首领攻击命中载具后扣除生命值，界面显示本次伤害并刷新生命条。",
            "载具生命值仍大于 0 时继续推进；生命值归零时停止战斗并进入失败分支。",
            "载具初始等级为 1 级。玩家在活动外消耗指定道具升级载具；各级使用同一种道具，但消耗数量按目标等级分别配置。",
            "载具升级后读取目标等级的攻击力、生命值和固定减伤，使后续进入关卡时使用新的基础属性；升级不可逆，活动结束后等级重置。",
            "进入关卡时载具承载 1 个默认武器栏和 4 个自选武器栏。默认栏已填充默认武器，自选栏初始为空。",
            "玩家在局内获得新武器类型时，将其写入一个空自选栏；每栏只能容纳一种武器，四个自选栏填满后不再获得新的武器类型。",
            "已填充栏位显示武器图标、当前累计词条数和冷却进度；点击空栏提示“当前武器栏为空”，点击已填充栏打开该武器的词条说明。",
            "购买指定礼包后解锁特权载具并自动替换默认载具。特权载具提供形象变化、固定减伤加成和独立特权技能；该技能不占武器栏，并按配置间隔释放全屏伤害。",
        ],
        "rules": [
            "横向操作与向前推进可以同时发生；横向移动不能在操作结束后自动复位。",
            "左侧小地图用于显示道路形态和当前推进位置；顶部计时与等级进度分别承担时间和局内成长反馈。",
            "载具受击后扣减当前生命值，生命条同步更新，并在命中位置显示本次伤害。",
            "所有武器栏中的武器类型一旦选定，本关卡内不可更换或卸除。",
            "特权载具解锁后不可在默认载具与特权载具之间切换；解锁状态随活动结束重置。",
        ],
        "special": [],
        "inventory": ["关卡计时", "局内等级进度", "小地图", "倍速", "伤害统计入口", "武器与资源状态", "载具生命值", "伤害反馈"],
        "parameters": {
            "载具攻击力": p("由配置表填写", value_type="数值", unit="点", source="策划明确要求（2026-08-11）", meaning="载具提供给武器伤害换算的基础攻击属性", value_range="大于等于0；上限待数值确认"),
            "载具当前生命值": p("战斗中实时变化", value_type="整数", unit="点", meaning="载具当前可承受伤害"),
            "载具生命值上限": p("由生命条上限表示", value_type="整数", unit="点", meaning="生命条满值"),
            "载具固定减伤": p("由配置表填写", value_type="数值", unit="点或比例待确认", source="策划明确要求（2026-08-11）", meaning="载具承伤计算中的固定减伤属性；计算位置需与伤害公式共同确认", value_range="允许范围与正负语义待数值确认"),
            "载具初始等级": p("1", value_type="整数", unit="级", source="策划提供的系统样例", meaning="进入活动时载具的起始等级", value_range="固定为1；活动结束后重置"),
            "载具升级道具ID": p("待项目配置确认", value_type="资源引用", unit="ID", source="策划提供的系统样例", meaning="载具升级消耗的指定道具；各级道具种类一致"),
            "载具升级消耗数量": p("按目标等级配置", value_type="整数", unit="个", source="策划提供的系统样例", meaning="本次升级需要扣除的道具数量", value_range="大于0；不同等级可不同"),
            "默认武器栏数量": p("1", value_type="整数", unit="栏", source="策划提供的系统样例", meaning="进入关卡时已经填充默认武器的固定栏位"),
            "自选武器栏数量": p("4", value_type="整数", unit="栏", source="策划提供的系统样例", meaning="进入关卡时为空、由玩家在局内填充的武器栏"),
            "武器栏累计词条数": p("获得武器时初始为1", value_type="整数", unit="条", source="策划提供的系统样例", meaning="该武器类型在本关卡累计获得的词条数量", value_range="大于等于1"),
            "武器栏冷却进度": p("以扇形角度显示", value_type="百分比", unit="%", source="策划提供的系统样例", meaning="该武器距离下一次可释放的可视化进度", value_range="0至100%"),
            "特权载具礼包ID": p("待项目配置确认", value_type="资源引用", unit="ID", source="策划提供的系统样例", meaning="购买后解锁特权载具的礼包配置引用"),
            "特权固定减伤加成": p("{x}", value_type="数值", unit="点或比例待确认", source="策划提供的系统样例", meaning="解锁特权载具后附加的固定减伤"),
            "特权技能释放间隔": p("{x}", value_type="时间", unit="s", source="策划提供的系统样例", meaning="独立于武器栏的特权技能两次全屏伤害之间的间隔", value_range="大于0"),
            "局内等级": p("画面显示 10、12、15、16、20 级", value_type="整数", unit="级", meaning="本局成长进度；示例值不是默认值"),
            "关卡进行时间": p("画面持续递增", value_type="时间", unit="分:秒", meaning="本次战斗已进行时间"),
        },
        "sources": ["F0001", "F0003", "F0007", "F0010", "F0012", "F0013", "F0014"],
    },
    "GCH-003": {
        "flowHeading": "武器解锁、攻击与词条成长",
        "scope": "武器槽位与自动攻击",
        "section": "核心战斗",
        "subsection": "武器与命中",
        "summary": "载具通过多个武器槽持续攻击敌人；各武器拥有独立图标、等级或累计状态，并以伤害数字和特效反馈命中结果。",
        "flow": [
            "战斗 HUD 右侧展示已获得武器/能力图标及对应数量，底部展示 1—6 号槽位。",
            "敌人进入对应武器可作用区域后，武器按自身攻击方式产生喷射、爆炸、毒液或雷暴等效果。",
            "命中后在目标附近显示伤害数字，并播放该武器对应的范围或持续效果。",
            "结算时按武器归集本局伤害，用于总伤害与秒伤展示。",
            "武器按物理、火、毒、雷、光或能量、冰、风分类；每个类型独立配置基础伤害比例、元素伤害、释放节奏、目标数量、索敌范围和伤害形状。",
            "武器需先在关卡外解锁，才能进行养成或进入关卡内获取范围。默认解锁型初始可用，通关解锁型在完成指定关卡后开放；解锁后默认等级为 1 级。",
            "玩家在关卡外消耗该武器对应道具进行升级。不同武器独立养成，升级提高元素伤害，并在达到配置等级时解锁指定词条。",
            "每个词条只属于一种武器类型，并配置词条组、前置词条、最大等级、随机权重、名称、描述及作用技能。",
            "关卡内只有已经局外解锁、且满足全部前置词条的词条可以进入随机池；同一词条重复获得时提升等级，达到最大等级后移出随机池。",
            "词条确认后修改指定武器技能或其附带效果，可改变伤害、范围、冷却、攻击结构、附加状态或状态持续时间。",
        ],
        "rules": [
            "本次战斗中可见火焰喷射、雷暴、毒液和机枪等不同攻击表现，各武器独立结算自身效果。",
            "强化卡中的伤害、范围、冷却和爆炸次数变化只作用于卡片指向的武器或技能。",
            "同屏多个攻击效果可以并行发生，伤害数字仍按实际命中分别出现。",
            "右上角武器卡显示当前等级与累计进度；累计进度的业务含义由对应决策项确定后写入。",
            "基础伤害比例是各武器类型的恒定换算比例，不随局外养成提升；元素伤害由对应武器的局外等级成长。",
            "索敌范围以载具为中心形成圆形搜索区域；目标进入该武器索敌范围后，武器才可开始释放。伤害范围再按圆形、扇形或单体分别读取所需参数。",
            "词条描述支持引用效果参数，使卡片展示值与实际生效值来自同一配置。",
        ],
        "special": [],
        "inventory": ["武器槽位", "火焰喷射", "雷暴枪", "剧毒炮", "机枪", "伤害数字", "范围特效", "结算归集"],
        "parameters": {
            "武器等级": p("界面示例 Lv.1", value_type="整数", unit="级", meaning="当前武器等级"),
            "武器累计状态": p("右侧图标旁显示数量", value_type="整数", unit="个", meaning="具体含义需由策划决策"),
            "单次伤害反馈": p("命中位置显示整数", value_type="整数", unit="点", meaning="本次命中的可见伤害"),
            "基础伤害比例": p("按武器类型配置", value_type="比例", unit="%或万分比待确认", source="策划明确要求（2026-08-11）", meaning="将载具攻击力换算为该武器基础伤害的恒定比例", value_range="各武器独立配置；不可通过局外养成提升"),
            "元素伤害": p("按武器类型与养成配置", value_type="数值", unit="点", source="策划明确要求（2026-08-11）", meaning="由武器养成提升的元素伤害值", value_range="各武器独立配置"),
            "伤害触发间隔": p("由配置表填写", value_type="时间", unit="s", source="策划明确要求（2026-08-11）", meaning="同一武器效果连续触发伤害的时间间隔", value_range="大于0"),
            "技能持续时间": p("由配置表填写", value_type="时间", unit="s", source="策划明确要求（2026-08-11）", meaning="持续型武器技能从开始到结束的时间", value_range="大于等于0；瞬时技能可不适用"),
            "直接伤害目标数": p("由配置表填写", value_type="整数", unit="个", source="策划明确要求（2026-08-11）", meaning="一次攻击可直接命中的最大目标数", value_range="大于等于1"),
            "间接伤害目标数": p("由配置表填写", value_type="整数", unit="个", source="策划明确要求（2026-08-11）", meaning="主目标受击后可继续影响的次级目标数", value_range="大于等于0"),
            "间接伤害衰减比例": p("由配置表填写", value_type="比例", unit="%或万分比待确认", source="策划明确要求（2026-08-11）", meaning="次级目标伤害相对主目标的保留比例", value_range="0至100%（若允许增幅需另行确认）"),
            "冷却时间": p("由配置表填写", value_type="时间", unit="s", source="策划明确要求（2026-08-11）", meaning="武器完成一次释放后到再次可释放的间隔", value_range="大于等于0"),
            "索敌范围": p("由配置表填写", value_type="距离", unit="场景单位", source="策划明确要求（2026-08-11）", meaning="以载具为中心、允许武器开始释放的圆形搜索区域半径", value_range="大于0"),
            "伤害范围": p("按圆形、扇形或单体配置", value_type="复合范围", unit="场景单位/角度", source="策划明确要求（2026-08-11）", meaning="武器实际造成伤害的空间范围；圆形读半径，扇形读半径与角度，单体不读范围", value_range="形状与对应参数必须匹配"),
            "武器类型": p("物理/火/毒/雷/光或能量/冰/风", value_type="枚举", unit="无", source="策划提供的系统样例", meaning="决定伤害表现、词条归属和显示区分的武器分类"),
            "武器解锁方式": p("默认解锁或通关解锁", value_type="枚举", unit="无", source="策划提供的系统样例", meaning="该武器在关卡外进入可养成、局内可获取状态的条件"),
            "武器解锁关卡": p("第{x}关", value_type="整数", unit="关", source="策划提供的系统样例", meaning="通关解锁型武器要求完成的关卡", value_range="默认解锁型不适用"),
            "武器升级道具ID": p("按武器类型配置", value_type="资源引用", unit="ID", source="策划提供的系统样例", meaning="该类武器在关卡外升级所消耗的道具"),
            "武器升级消耗数量": p("按武器与目标等级配置", value_type="整数", unit="个", source="策划提供的系统样例", meaning="本次武器升级扣除的道具数量", value_range="大于0"),
            "词条ID": p("待项目配置确认", value_type="唯一标识", unit="ID", source="策划提供的系统样例", meaning="局内随机、升级和效果引用使用的词条标识"),
            "词条组": p("同效果词条并入同组", value_type="分组标识", unit="ID", source="策划提供的系统样例", meaning="用于同效果词条的显示区分与互斥处理"),
            "前置词条ID": p("可配置多个", value_type="ID集合", unit="ID", source="策划提供的系统样例", meaning="全部获得后该词条才进入本局随机池"),
            "词条最大等级": p("按词条配置", value_type="整数", unit="级", source="策划提供的系统样例", meaning="同一词条在单局内可重复获取并提升的上限", value_range="达到后移出随机池"),
            "词条权重加成": p("按词条配置", value_type="权重", unit="权重值", source="策划提供的系统样例", meaning="参与词条三选一随机计算的相对权重", value_range="大于等于0"),
            "词条名称": p("每个词条独立配置", value_type="文本", unit="无", source="策划提供的系统样例", meaning="卡片和提示中展示的业务名称"),
            "词条描述": p("支持读取效果参数", value_type="富文本", unit="无", source="策划提供的系统样例", meaning="说明词条效果，并将效果字段参数写入展示文本"),
            "词条解锁武器等级": p("按词条配置", value_type="整数", unit="级", source="策划提供的系统样例", meaning="关卡外武器达到该等级后解锁此词条", value_range="1表示默认解锁"),
            "词条作用技能ID": p("指定唯一或明确的技能目标", value_type="资源引用", unit="ID", source="策划提供的系统样例", meaning="词条修改的武器技能或其附带BUFF"),
            "词条效果参数": p("按效果类型配置", value_type="参数集合", unit="随参数定义", source="策划提供的系统样例", meaning="伤害、范围、冷却、附加效果或BUFF持续时间等实际修改值"),
        },
        "sources": ["F0001", "F0003", "F0007", "F0010", "F0012", "F0013", "F0014", "F0015"],
    },
    "GCH-012": {
        "flowHeading": "升级触发与候选确认",
        "scope": "局内升级与三选一强化",
        "section": "局内成长",
        "subsection": "普通强化",
        "summary": "局内等级提升后暂停战斗并展示三项候选；玩家选择一项立即应用，也可在剩余次数允许时刷新候选。",
        "flow": [
            "局内等级进度满足升级条件后，战斗画面变暗并暂停，系统打开“选择武器”界面。",
            "系统同时展示三张候选卡；每张卡写明名称、关联武器图标和本次效果。",
            "玩家选择一张候选，系统只应用该项并关闭弹窗；未选候选不生效。",
            "玩家也可使用刷新替换本组三张候选；刷新次数显示在按钮上，刷新不等于确认强化。",
            "弹窗关闭后恢复战斗，新增或增强的武器效果立即参与后续攻击。",
        ],
        "rules": [
            "当前可见候选包括学习剧毒炮、火焰喷射伤害提高 20%、火焰喷射范围扩大 30%、火焰爆炸范围扩大 100%、雷暴枪伤害增加 100%。",
            "候选既可能解锁新武器，也可能增强已有武器；正文按卡片实际语义区分“获得”和“强化”。",
            "刷新按钮显示本次可用次数；当前界面为 1/1，执行刷新后应同步更新剩余次数。",
            "卡片值作为本次选择结果直接表达，不把这些值扩写为未经证实的全局公式。",
        ],
        "special": [],
        "inventory": ["升级触发", "战斗暂停", "三项候选", "获得新武器", "强化已有武器", "刷新候选", "选择确认", "恢复战斗"],
        "parameters": {
            "候选数量": p("3", value_type="整数", unit="项", meaning="单次界面同时显示的候选数"),
            "本次剩余刷新次数": p("截图示例 1/1", value_type="计数", unit="次", meaning="当前弹窗可用刷新次数"),
            "火焰喷射范围提升": p("30%", value_type="百分比", unit="%", meaning="对应候选的范围变化"),
            "雷暴枪伤害提升": p("100%", value_type="百分比", unit="%", meaning="对应候选的伤害变化"),
        },
        "sources": ["F0002", "F0004", "F0006", "F0009"],
    },
    "GCH-016": {
        "flowHeading": "终极词条进入与生效",
        "scope": "终极词条与攻击形态变化",
        "section": "局内成长",
        "subsection": "终极强化",
        "summary": "终极词条以金色样式进入词条库，并在后续候选中出现；确认后改变对应武器的攻击形态，同时可能附带数值代价。",
        "flow": [
            "升级过程中满足终极词条进入条件时，系统展示“终极词条进入词条库”提示和金色卡片。",
            "终极词条加入后续候选范围，并以金色边框与普通强化区分。",
            "玩家在三选一界面确认终极词条后，系统同时应用卡片中的收益和代价。",
            "后续战斗使用新的攻击形态，例如火焰喷射由单方向改为同时向四个方向喷射。",
        ],
        "rules": [
            "“广域喷射”明确写明同时向 4 面喷射火焰、伤害 -20%；两部分属于同一个不可拆分的选择结果。",
            "“多点爆炸”同时应用火焰爆炸次数增加 100% 与伤害 -20%；该伤害修正只属于这张词条卡。",
            "终极词条改变攻击结构，不应只写成普通属性加成。",
            "提示文字说明终极词条有概率在升级时出现；具体概率、前置等级和同局出现次数仍需权威配置。",
        ],
        "special": ["进入词条库不等于自动获得；仍需在后续候选中出现并由玩家确认。"],
        "inventory": ["进入词条库", "金色区分", "后续候选", "收益", "代价", "攻击形态变化"],
        "parameters": {
            "广域喷射方向数": p("4", value_type="整数", unit="方向", meaning="火焰同时喷射方向数"),
            "广域喷射伤害修正": p("-20%", value_type="百分比", unit="%", meaning="选择该词条后的伤害代价"),
            "多点爆炸次数修正": p("+100%", value_type="百分比", unit="%", meaning="选择该词条后的爆炸次数变化"),
        },
        "sources": ["F0005", "F0006", "F0009", "F0010"],
    },
    "GCH-018": {
        "flowHeading": "抽取开始、跳过与结果写入",
        "scope": "武器抽取界面与结果确认",
        "section": "局内成长",
        "subsection": "独立抽取",
        "summary": "局内还存在独立于三选一的武器抽取界面：图标按格滚动并在中间结果区停止，玩家可以等待动画或点击空白跳过。",
        "flow": [
            "触发武器抽取后暂停背景战斗并打开抽取装置。",
            "三列图标开始滚动，中间横向框作为最终结果区域。",
            "玩家等待滚动结束，或点击空白区域跳过动画。",
            "系统停止滚动并形成结果，随后关闭抽取界面并返回战斗。",
        ],
        "rules": [
            "滚动区域同时展示武器与技能图标，停止后只读取中间结果框中的最终结果。",
            "该界面与普通三选一的版式、结果区域和操作方式不同，应作为独立机制描述。",
        ],
        "special": [],
        "inventory": ["抽取入口", "滚动动画", "三列候选", "结果框", "跳过动画", "结果确认", "返回战斗"],
        "parameters": {
            "可见滚动列数": p("3", value_type="整数", unit="列", meaning="抽取装置可见的纵向滚动列"),
            "可见候选行数": p("3", value_type="整数", unit="行", meaning="画面同时可见的候选行"),
            "底部可见数值": p("100、300", value_type="整数", unit="未确认", meaning="只记录画面值，不定义其用途"),
        },
        "sources": ["F0008"],
    },
    "GCH-006": {
        "flowHeading": "波次刷新、怪物作战与首领切换",
        "scope": "关卡阶段与首领战",
        "section": "关卡推进",
        "subsection": "普通阶段与首领阶段",
        "summary": "关卡从普通敌人推进至首领阶段；首领登场前播放全屏警告，进入战斗后使用独立生命条，并在生命下降过程中切换可见战斗表现。",
        "flow": [
            "普通阶段中，敌人持续进入战场，载具沿路线推进并通过武器清理敌人。",
            "每个波次开始时刷新怪物。一个波次可以包含多组怪物，各组按照配置顺序生成，相邻组之间使用统一的毫秒间隔。",
            "每个波次配置多个相对载具的刷怪点，点位通过 x、y 偏移确定位置，并区分普通、精英、BOSS 和空点；空点不生成怪物。",
            "同类刷怪点读取同一个怪物组。例如十个普通点与一个 BOSS 点可以使用不同怪物 ID，但十个普通点之间保持一致。",
            "怪物生成后沿直线匀速向载具移动。移动速度读取怪物基础属性；进入攻击距离后停止前进并保持当前位置。",
            "怪物满足攻击距离后按攻击间隔执行攻击动作；远程怪同时读取子弹 ID 生成攻击子弹。载具离开攻击距离后，怪物停止攻击并恢复追踪移动。",
            "怪物受到武器攻击时先处理闪避与格挡，再按战斗计算结果扣除生命值；生命值小于等于 0 时播放死亡动作，动作完成后从场景移除。",
            "达到首领阶段条件后，系统覆盖红色警示效果并显示“首领来袭”，背景战斗信息降为次要层级。",
            "警告结束后进入首领战，顶部显示首领名称、生命百分比和附加计数。",
            "玩家继续移动并输出伤害；首领生命条从高百分比下降，并出现不同攻击表现。",
            "首领生命归零时进入成功结算；载具生命先归零时进入失败结算。",
        ],
        "rules": [
            "首领来袭是自动阶段反馈，不要求玩家点击确认。",
            "首领 HUD 展示首领名称、剩余生命百分比和附加计数；附加计数的名称由对应决策项确定后写入。",
            "关卡时间和局内等级在进入首领战后继续显示，说明首领阶段仍属于同一局战斗。",
            "怪物本波次生命值等于基础生命值乘当前关卡当前波次生命倍率；攻击力按相同方式读取攻击倍率。",
            "受到攻击时优先判定闪避。闪避成功则免除本次伤害并累计一次；连续闪避达到配置上限后，下次攻击必定命中，被命中时清空累计。",
            "若怪物仍有格挡次数，受伤时优先消耗 1 次格挡并免除该次伤害；免疫配置则分别决定灼烧、中毒等异常效果能否附加。",
        ],
        "special": ["首领阶段中载具受到伤害后，只要生命值仍大于0便继续战斗。"],
        "inventory": ["普通敌人阶段", "阶段触发", "首领来袭警告", "首领 HUD", "生命百分比", "可见计数", "攻击表现", "胜负分流"],
        "parameters": {
            "首领名称": p("僵尸博士", value_type="文本", unit="无", meaning="当前截图中的首领显示名"),
            "首领生命百分比": p("战斗中从 90.65% 降至 10.80%", value_type="百分比", unit="%", meaning="首领剩余生命的可见反馈"),
            "首领附加计数": p("画面示例 x19、x3", value_type="整数", unit="未确认", meaning="具体业务含义需策划决定"),
            "怪物生命值": p("基础生命值 × 当前关卡当前波次生命值倍率", value_type="数值/公式", unit="点", source="策划明确要求（2026-08-11）", meaning="怪物本波次的最大生命值", value_range="基础值与倍率均大于等于0"),
            "怪物攻击力": p("基础攻击力 × 当前关卡当前波次攻击力倍率", value_type="数值/公式", unit="点", source="策划明确要求（2026-08-11）", meaning="怪物本波次参与伤害计算的攻击属性", value_range="基础值与倍率均大于等于0"),
            "怪物移动速度": p("由配置表填写", value_type="速度", unit="场景单位/s", source="策划明确要求（2026-08-11）", meaning="怪物每秒向载具移动的距离", value_range="大于等于0"),
            "怪物攻击距离": p("由配置表填写", value_type="距离", unit="场景单位", source="策划明确要求（2026-08-11）", meaning="怪物与载具直线距离不大于该值时满足攻击条件", value_range="大于等于0"),
            "怪物攻速": p("由配置表填写", value_type="时间间隔", unit="ms", source="策划明确要求（2026-08-11）", meaning="怪物连续两次造成伤害的时间间隔", value_range="大于0"),
            "怪物最终减伤": p("由配置表填写", value_type="比例", unit="%或万分比待确认", source="策划明确要求（2026-08-11）", meaning="正值增伤、负值减伤的最终伤害修正项", value_range="正负上限待数值确认"),
            "怪物最终元素减伤": p("按元素分别配置", value_type="比例集合", unit="%或万分比待确认", source="策划明确要求（2026-08-11）", meaning="针对指定元素伤害的增伤或减伤修正", value_range="元素枚举与正负上限待确认"),
            "怪物闪避": p("由配置表填写", value_type="万分比", unit="‱", source="策划明确要求（2026-08-11）", meaning="受击时先判定闪避；闪避免除本次伤害并累计次数，被命中后清空累计", value_range="0至10000；每只怪物最多连续闪避3次，达到上限后下次必定命中"),
            "怪物格挡次数": p("由配置表填写", value_type="整数", unit="次", source="策划明确要求（2026-08-11）", meaning="受伤时优先消耗；每次格挡免除本次伤害并扣除1次", value_range="大于等于0"),
            "怪物免疫效果": p("按异常类型配置", value_type="布尔集合", unit="无", source="策划明确要求（2026-08-11）", meaning="声明是否免疫灼烧、中毒等指定异常效果", value_range="异常类型枚举待配置确认"),
            "怪物类型": p("普通怪/精英怪/BOSS", value_type="枚举", unit="无", source="策划明确要求（2026-08-11）", meaning="决定刷怪点、怪物组和表现规则的对象分类", value_range="普通怪、精英怪、BOSS"),
            "怪物子弹ID": p("按怪物配置", value_type="资源引用", unit="ID", source="策划明确要求（2026-08-11）", meaning="远程怪攻击时发射的子弹配置引用", value_range="近战或无子弹怪物可不适用"),
            "怪物基础生命值": p("按怪物ID配置", value_type="数值", unit="点", source="策划提供的系统样例", meaning="未乘关卡波次倍率前的生命值", value_range="大于等于0"),
            "怪物基础攻击力": p("按怪物ID配置", value_type="数值", unit="点", source="策划提供的系统样例", meaning="未乘关卡波次倍率前的攻击力", value_range="大于等于0"),
            "波次生命值倍率": p("按关卡与波次配置", value_type="倍率", unit="倍", source="策划提供的系统样例", meaning="用于计算当前波次怪物最终生命值", value_range="大于等于0"),
            "波次攻击力倍率": p("按关卡与波次配置", value_type="倍率", unit="倍", source="策划提供的系统样例", meaning="用于计算当前波次怪物最终攻击力", value_range="大于等于0"),
            "怪物攻击动作ID": p("按怪物ID配置", value_type="资源引用", unit="ID", source="策划提供的系统样例", meaning="怪物满足攻击条件时播放的动作配置"),
            "刷怪组间隔": p("按波次配置", value_type="时间", unit="ms", source="策划提供的系统样例", meaning="同一波次相邻怪物组开始刷新之间的恒定间隔", value_range="大于等于0"),
            "刷怪点类型": p("普通/精英/BOSS/空", value_type="枚举", unit="无", source="策划提供的系统样例", meaning="决定该点使用的怪物组；为空时不刷怪"),
            "刷怪点XY偏移": p("相对主角载具配置", value_type="二维坐标", unit="场景单位", source="策划提供的系统样例", meaning="刷怪点相对载具位置的x、y偏移量"),
            "怪物组ID与数量": p("按刷怪点类型配置", value_type="ID与数量集合", unit="ID/只", source="策划提供的系统样例", meaning="该波次各类刷怪点按顺序生成的怪物组成"),
        },
        "sources": ["F0001", "F0003", "F0007", "F0010", "F0011", "F0012", "F0013", "F0014"],
    },
    "GCH-010": {
        "flowHeading": "胜利结算与离开",
        "scope": "挑战成功、奖励与伤害统计",
        "section": "关卡推进",
        "subsection": "结算与复盘",
        "summary": "击败首领后停止战斗并进入挑战成功结算；页面集中展示新纪录、通关时间、奖励、各武器伤害贡献、双倍奖励入口和返回操作。",
        "flow": [
            "首领被击败后结束局内战斗并打开挑战成功界面。",
            "系统判断本次通关时间是否形成新纪录，并在满足时显示“新纪录”。",
            "结算页展示本次通关时间和获得道具，奖励按图标与数量逐项列出。",
            "伤害统计按武器展示总伤占比和秒伤；同时显示本局战斗总伤害。",
            "玩家选择双倍奖励或返回；对应按钮执行后离开结算页面。",
        ],
        "rules": [
            "当前截图显示通关时间 05:14、战斗总伤害 88.9 万，以及火焰喷射器、毒液炮、雷暴枪、机枪四项贡献；这些是本局结果示例。",
            "总伤占比按武器分别展示并可突出 MVP；秒伤是另一统计维度，不能与总伤占比混用。",
            "奖励区同时包含经验、货币和道具等多种图标，当前项目应逐项保留而不是概括成“获得奖励”。",
            "双倍奖励按钮显示今日剩余次数；当前结算界面为 3/3，具体触发方式与扣次时点由对应决策项确定。",
        ],
        "special": ["载具生命值先归零时进入失败分支，不进入成功结算。"],
        "inventory": ["挑战成功", "新纪录", "通关时间", "奖励清单", "总伤占比", "秒伤", "MVP", "战斗总伤害", "双倍奖励", "返回"],
        "parameters": {
            "通关时间": p("本局示例 05:14", value_type="时间", unit="分:秒", meaning="从关卡开始到成功的总时间"),
            "战斗总伤害": p("本局示例 88.9万", value_type="数值", unit="伤害", meaning="本局全部武器累计伤害"),
            "武器总伤占比": p("按武器显示百分比", value_type="百分比", unit="%", meaning="单武器累计伤害/本局总伤害"),
            "今日双倍奖励剩余次数": p("本局界面示例 3/3", value_type="计数", unit="次", meaning="当前页面显示的剩余/上限"),
        },
        "sources": ["F0015"],
    },
}


ATTRIBUTE_SECTIONS = {
    "GCH-001": [
        {"heading": "承伤与武器换算", "items": [
            "攻击力：作为载具提供给各类武器的基础攻击属性；武器结算时再读取自身的伤害比例或元素伤害，不能把载具攻击力直接等同于最终伤害。",
            "生命值：进入关卡时读取生命值上限，战斗中以当前生命值记录承伤结果；当前生命值降至 0 时停止推进并进入失败结算。",
            "固定减伤：参与载具承伤计算，用于降低命中后的伤害。",
        ]},
        {"heading": "等级与栏位状态", "items": [
            "等级：初始为 1 级；升级时消耗同一种指定道具，各目标等级分别配置消耗数量。升级后读取该级攻击力、生命值和固定减伤，升级不可逆，活动结束后重置。",
            "武器栏：进入关卡时包含 1 个已填充默认武器栏和 4 个空自选武器栏；每栏只能记录一种武器类型，填满后停止投放新的武器类型，已选武器不能更换或卸除。",
            "冷却进度：以扇形角度显示武器距离下一次释放的进度，显示范围为 0—100%，实际冷却时长读取对应武器配置。",
        ]},
        {"heading": "特权载具", "items": [
            "礼包 ID：购买对应礼包后解锁特权载具并自动替换默认载具；活动期间不可来回切换，活动结束后清除解锁状态。",
            "特权效果：在载具原有属性上附加固定减伤，并解锁不占用武器栏的独立技能；技能按配置间隔释放全屏伤害。",
        ]},
    ],
    "GCH-003": [
        {"heading": "伤害与释放条件", "items": [
            "武器类型：分为物理、火、毒、雷、光或能量、冰、风；类型决定表现、元素归属、可用词条和配置分组。",
            "基础伤害比例：把载具攻击力换算为该武器基础伤害的恒定比例，不随局外养成提升；元素伤害由该类武器的局外等级独立成长。",
            "伤害触发间隔与技能持续时间：前者控制持续效果相邻两次伤害的间隔，后者控制持续型技能从开始到结束的时长；瞬时技能可不读取持续时间。",
            "直接与间接目标数：直接目标数限制一次攻击首先命中的目标数量；间接目标数限制从主目标继续扩散的次级目标数量，次级伤害再乘间接伤害衰减比例。",
            "冷却时间：一次释放完成后到再次可释放的间隔；索敌范围决定是否允许释放，伤害范围决定释放后实际影响的空间，两者不能混用。",
            "索敌与伤害范围：索敌范围以载具为圆心读取半径；伤害范围按圆形、扇形或单体分别读取半径、角度或目标引用。",
        ]},
        {"heading": "解锁、养成与词条进入随机池", "items": [
            "武器解锁：默认解锁型初始可用；通关解锁型在完成指定关卡后开放。未解锁武器不能局外养成，也不进入局内获取范围；解锁后等级为 1。",
            "武器升级：不同武器独立消耗各自道具，目标等级分别配置消耗数量；升级提高元素伤害，并在达到指定等级时解锁对应词条。",
            "词条归属与前置：每个词条拥有唯一 ID，只属于一种武器类型；同效果词条可归入同一词条组。只有局外已解锁且本局已获得全部前置词条的内容才进入随机池。",
            "等级上限与权重：同一词条可在单局重复获得并提升等级，达到最大等级后移出随机池；未达上限时按词条权重参与三选一抽取。",
            "显示与效果：词条名称、描述独立配置，描述可读取效果参数；作用技能 ID 指向被修改的武器技能或附带状态，效果参数承载伤害、范围、冷却、附加效果和持续时间等变化。",
        ]},
    ],
    "GCH-006": [
        {"heading": "战斗属性", "items": [
            "生命值：由怪物基础生命值乘以当前关卡当前波次的生命值倍率得到；当前生命值降至 0 后播放死亡动作，动作结束再移除实体。",
            "攻击力：由怪物基础攻击力乘以当前关卡当前波次的攻击力倍率得到，并在攻击命中载具时进入伤害公式。",
            "移动速度：表示怪物每秒移动距离；攻击距离用于判断能否发动攻击。进入攻击距离后怪物停止移动，载具离开范围后怪物恢复追赶。",
            "攻速：表示相邻两次造成伤害的时间间隔，单位为毫秒；远程怪同时读取攻击动作 ID 和子弹 ID 生成对应攻击。",
            "最终减伤与最终元素减伤：前者作用于通用伤害，后者只作用于指定元素；正负值对应增伤还是减伤必须在伤害公式中保持同一语义。",
            "闪避：受击时先按万分比判定；闪避成功免除本次伤害并累计次数，达到上限后下一次受击必定命中，被命中后清空累计次数。",
            "格挡次数：受击时优先消耗一次剩余格挡并免除本次伤害；次数归零后继续执行普通承伤。免疫效果则决定怪物是否接受灼烧、中毒等异常状态。",
            "怪物类型：区分普通怪、精英怪和 BOSS，用于选择刷怪点、怪物组、表现及对应阶段规则。",
        ]},
        {"heading": "波次、刷怪点与怪物组", "items": [
            "刷怪组间隔：每个波次可包含多组怪物，各组按顺序刷新，相邻两组之间按毫秒配置固定间隔。",
            "刷怪点类型：普通怪点、精英怪点和 BOSS 点分别读取对应怪物组；点位为空时不生成怪物，同类型点位使用同一怪物组。",
            "刷怪点坐标：以主角载具为参照配置 x、y 偏移量，载具推进时按相对位置确定生成点，不能把截图绝对坐标写成关卡配置。",
            "怪物组：记录本组怪物 ID 与数量；同一波次可分别配置普通、精英和 BOSS 组，并与波次生命值倍率、攻击力倍率共同决定该波次强度。",
        ]},
    ],
}


# Delivery copy is intentionally separated from audit findings.  These titles and
# figures are selected by the mechanism, not emitted from a universal template.
DELIVERY_REFINEMENTS = {
    "GCH-001": {
        "ruleHeading": "推进与战斗反馈",
        "attributeHeading": "载具",
        "rules": [
            "横向操作与向前推进可以同时发生；横向移动不能在操作结束后自动复位。",
            "左侧小地图显示道路形态和当前推进位置；顶部计时与等级进度分别反馈战斗时间和局内成长。",
            "敌人命中载具后立即扣除生命值，同时刷新生命条并显示本次伤害。",
        ],
        "special": ["暂停、倍速和伤害统计是战斗 HUD 的独立操作入口。"],
        "inlineFigures": [{"frameId": "F0007", "caption": "战斗主界面：载具推进、武器槽、生命值、局内等级与伤害反馈在同一战斗状态中持续更新。"}],
    },
    "GCH-003": {
        "ruleHeading": "攻击、养成与词条生效",
        "attributeHeading": "武器",
        "rules": [
            "当前战斗中已出现火焰喷射、雷暴、毒液和机枪等不同攻击表现，各武器独立产生伤害与特效。",
            "强化卡可修改伤害、范围、冷却或攻击次数；选定后只作用于卡片指向的武器或技能。",
            "同屏多个攻击效果可以并行发生，伤害数字按实际命中分别出现。",
        ],
        "special": ["目标未进入武器的有效作用范围时，该武器不对其造成伤害。"],
        "inlineFigures": [{"frameId": "F0010", "caption": "战斗中的武器表现：右侧能力状态、底部武器槽与场内攻击特效共同说明武器已进入持续作战状态。"}],
    },
    "GCH-012": {
        "ruleHeading": "候选、刷新与确认",
        "rules": [
            "候选既可以解锁新武器，也可以强化已有武器；卡片文案分别使用“获得”和具体属性变化表达结果。",
            "刷新会整体替换当前三项候选，但不会直接应用任何强化；玩家确认其中一项后，本轮选择结束。",
            "刷新按钮显示当前可用次数，执行刷新后同步扣减并更新按钮状态。",
        ],
        "special": ["可用刷新次数为 0 时禁用刷新操作，但玩家仍可从当前三项候选中完成选择。"],
        "inlineFigures": [{"frameId": "F0009", "caption": "三选一强化界面：三张候选卡同时展示，底部刷新入口与剩余次数属于本轮选择状态。"}],
    },
    "GCH-016": {
        "ruleHeading": "终极词条的进入与生效",
        "rules": [
            "“广域喷射”同时改变攻击方向和伤害修正，两项效果作为同一个选择结果生效。",
            "“多点爆炸”同时改变爆炸次数和伤害修正，两项效果作为同一个选择结果生效。",
            "终极词条改变攻击结构，不按普通数值强化处理。",
        ],
        "special": ["进入词条库不等于自动获得；词条进入后续候选并被玩家确认时才生效。"],
        "inlineFigures": [{"frameId": "F0005", "caption": "终极词条提示与金色卡片用于区分词条已进入候选范围，后续仍需玩家完成选择。"}],
    },
    "GCH-018": {
        "ruleHeading": "滚动、跳过与结果",
        "rules": [
            "抽取界面使用三列滚动区，中间横向框承担最终结果展示。",
            "点击空白区域只跳过滚动表现，系统仍需生成并写入本次抽取结果。",
            "该抽取界面的操作和结果区域与普通三选一不同，作为独立机制处理。",
        ],
        "special": ["跳过只结束滚动表现，不取消抽取，也不重新生成另一份结果。"],
        "inlineFigures": [{"frameId": "F0008", "caption": "武器抽取界面：三列图标围绕中间结果框滚动，底部资源区与跳过操作属于同一次抽取流程。"}],
    },
    "GCH-006": {
        "ruleHeading": "刷新、作战与首领阶段",
        "attributeHeading": "怪物",
        "rules": [
            "达到首领阶段条件后自动播放“首领来袭”警告，不要求玩家点击确认。",
            "警告结束后切入首领战并显示首领名称、生命百分比和附加计数。",
            "关卡时间和局内等级在首领战中继续累计，首领阶段仍属于同一局战斗。",
        ],
        "special": ["首领生命归零与载具生命归零分别进入成功和失败结算，两条结果互斥。"],
        "inlineFigures": [
            {"frameId": "F0011", "caption": "阶段切换：首领来袭警告覆盖普通战斗画面，明确提示关卡进入首领阶段。"},
            {"frameId": "F0012", "caption": "首领战状态：独立生命条、首领名称和关卡 HUD 同时保留。"},
        ],
    },
    "GCH-010": {
        "ruleHeading": "奖励与伤害复盘",
        "rules": [
            "结算页逐项展示通关时间、奖励、战斗总伤害以及各武器的总伤占比和秒伤。",
            "总伤占比与秒伤是两个统计维度；MVP 标记用于突出本局贡献最高的武器。",
            "双倍奖励和返回是结算后的两条离开路径，执行任一操作后结束当前结算状态。",
        ],
        "special": ["伤害统计只汇总本局已经生效的武器伤害，不把未选择的候选或界面预览计入结果。"],
        "inlineFigures": [{"frameId": "F0015", "caption": "挑战成功结算：通关时间、奖励清单、武器伤害统计和离开操作集中展示。"}],
    },
}


def main() -> None:
    job = json.loads(JOB_PATH.read_text(encoding="utf-8"))
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = JOB_DIR / f"job.before-stage5-v2-{stamp}.json"
    shutil.copy2(JOB_PATH, backup)
    model = job["gameplayReviewModel"]
    by_id = {item["id"]: item for item in model.get("chapters") or []}
    ordered_ids = ["GCH-001", "GCH-003", "GCH-012", "GCH-016", "GCH-018", "GCH-006", "GCH-010"]
    for chapter_id in ordered_ids:
        chapter = by_id[chapter_id]
        data = CHAPTERS[chapter_id]
        refinement = DELIVERY_REFINEMENTS[chapter_id]
        data["rules"] = list(dict.fromkeys([*data["rules"], *refinement["rules"]]))
        data["special"] = list(dict.fromkeys([*data["special"], *refinement["special"]]))
        if chapter_id == "GCH-001":
            # The detailed vehicle attributes below already carry slot and privilege
            # rules. Keep this overview to the four distinct runtime facts instead
            # of repeating evidence wording and audit-stage notes.
            data["rules"] = list(refinement["rules"])
            data["special"] = list(refinement["special"])
        parameters = data["parameters"]
        for metadata in parameters.values():
            if isinstance(metadata, dict):
                metadata["sourceFrameIds"] = list(data["sources"])
        parameter_schema = [{
            "name": name, "plannerMeaning": metadata.get("plannerMeaning", ""),
            "type": metadata["type"], "unit": metadata["unit"], "defaultValue": metadata["value"],
            "range": metadata["range"], "configurationSource": metadata["source"],
            "rounding": "不适用", "evidenceLevel": "material",
            "sourceFrameIds": list(data["sources"]), "status": "素材明确展示",
        } for name, metadata in parameters.items()]
        chapter.update({"scope": data["scope"], "systemName": data["section"], "subsystemName": data["subsection"],
                        "contentInventory": data["inventory"], "executionSequence": data["flow"],
                        "parameters": parameters, "parameterSchema": parameter_schema, "fieldDictionary": [],
                        "objectStates": data["rules"], "interactionFeedback": data["flow"],
                        "runtimeResponsibilities": data["rules"], "presentationRules": data["rules"],
                        "plannerSummary": data["summary"], "plannerSections": {"summary": data["summary"],
                            "normalFlow": data["flow"], "keyRules": data["rules"], "specialCases": data["special"],
                            "attributeHeading": refinement.get("attributeHeading", ""),
                            "attributeSections": ATTRIBUTE_SECTIONS.get(chapter_id, []), "acceptanceExamples": []}, "plannerSectionsSource": "stage5_v2_evidence_reconstruction",
                        "sourceFrameIds": data["sources"], "inlineFigures": refinement["inlineFigures"],
                        "flowHeading": data["flowHeading"], "ruleHeading": refinement["ruleHeading"], "status": "approved",
                        "confirmation": {"confirmed": True, "revision": int(model.get("revision") or 0) + 1}})
        chapter["granularityEvidence"] = {
            "overviewTraceability": evidence("overviewTraceability", data["sources"], [data["summary"].split("；")[0]]),
            "contentInventory": evidence("contentInventory", data["sources"], data["inventory"]),
            "objectState": evidence("objectState", data["sources"], data["rules"][:2]),
            "attributeNarrative": evidence("attributeNarrative", data["sources"], [
                name for group in ATTRIBUTE_SECTIONS.get(chapter_id, []) for name in [
                    str(item).split("：", 1)[0] for item in group.get("items", []) if "：" in str(item)
                ]
            ], source_type="reference_document"),
            "executionSequence": evidence("executionSequence", data["sources"], data["flow"], source_type="video_sequence", ordered=True),
            "boundary": evidence("boundary", data["sources"], data["special"], source_type="context_inference"),
            "interactionFeedback": evidence("interactionFeedback", data["sources"], [data["flow"][0], data["flow"][-1]]),
            "runtimeResponsibility": evidence("runtimeResponsibility", data["sources"], data["rules"][:1], source_type="context_inference"),
            "presentationContract": evidence("presentationContract", data["sources"], data["rules"][:1]),
        }
        if not ATTRIBUTE_SECTIONS.get(chapter_id):
            chapter["granularityEvidence"].pop("attributeNarrative", None)

    by_id["GCH-003"]["decisionCards"] = [card("GDC-101", "右上角武器卡中的进度数值表示什么？", [
        ("affix_count", "累计词条数", True, "该解释与强化持续积累的画面最一致，但仍需策划确认。"),
        ("upgrade_progress", "武器升级进度", False, "若数值表示经验或碎片，应同时定义满值后的行为。"),
        ("ammo", "弹药或充能", False, "若战斗中会消耗，还需定义恢复时机。"),
    ], ["F0001", "F0010"], ["武器正文", "HUD解读", "参数表", "最终文档"])]
    by_id["GCH-012"]["decisionCards"] = [card("GDC-102", "普通三选一的候选池和刷新规则采用哪套方案？", [
        ("unlocked_weighted", "已解锁内容按权重抽取", True, "能支持新武器与已有武器强化同时出现，并便于配置。"),
        ("level_preset", "每级使用固定候选组", False, "结果更可控，但随机性较弱。"),
        ("owned_only", "仅从已拥有武器中抽取", False, "需要另设新武器解锁入口。"),
    ], ["F0002", "F0004", "F0006", "F0009"], ["三选一算法", "刷新规则", "算法流程图", "配置表", "最终文档"])]
    by_id["GCH-018"]["decisionCards"] = [card("GDC-103", "武器抽取的结果与消耗如何结算？", [
        ("one_result_one_cost", "每次付费取得一个中线结果", True, "与中间结果框和底部数值的画面结构较一致。"),
        ("multi_result", "一次取得三个列结果", False, "需要定义重复结果和批量写入方式。"),
        ("free_event", "事件触发后免费抽取", False, "底部数值需另行解释。"),
    ], ["F0008"], ["武器抽取正文", "消耗参数", "结果写入", "流程图", "最终文档"])]
    by_id["GCH-006"]["decisionCards"] = [card("GDC-104", "首领生命条后的 x19、x3 表示什么？", [
        ("hp_layers", "剩余生命层数", True, "计数随生命百分比下降而降低，最符合多管生命结构。"),
        ("phase_count", "当前阶段计数", False, "需要补充阶段切换阈值。"),
        ("other", "其他战斗计数", False, "需要策划给出业务名称与变化规则。"),
    ], ["F0012", "F0013"], ["首领HUD", "阶段规则", "参数命名", "最终文档"])]
    by_id["GCH-010"]["decisionCards"] = [card("GDC-105", "双倍奖励按钮采用什么触发方式？", [
        ("rewarded_ad", "观看激励广告后领取", True, "按钮带视频图标，且显示今日剩余次数。"),
        ("direct_claim", "直接消耗每日次数领取", False, "无需广告，但要定义次数扣除时机。"),
        ("item_cost", "消耗道具领取", False, "需要补充道具来源和不足反馈。"),
    ], ["F0015"], ["结算按钮逻辑", "奖励发放", "次数重置", "最终文档"])]

    model["chapters"] = [by_id[item] for item in ordered_ids]
    model["systems"] = [
        {"id": "GSY-001", "name": "核心战斗", "subsystems": [
            {"id": "GSS-001", "name": "战场与载具", "chapterIds": ["GCH-001"]},
            {"id": "GSS-002", "name": "武器与命中", "chapterIds": ["GCH-003"]}]},
        {"id": "GSY-002", "name": "局内成长", "subsystems": [
            {"id": "GSS-003", "name": "普通强化", "chapterIds": ["GCH-012"]},
            {"id": "GSS-004", "name": "终极强化", "chapterIds": ["GCH-016"]},
            {"id": "GSS-005", "name": "独立抽取", "chapterIds": ["GCH-018"]}]},
        {"id": "GSY-003", "name": "关卡推进", "subsystems": [
            {"id": "GSS-006", "name": "阶段与首领", "chapterIds": ["GCH-006"]},
            {"id": "GSS-007", "name": "结算与复盘", "chapterIds": ["GCH-010"]}]},
    ]
    model["directory"] = {
        "status": "confirmed", "revision": int(model.get("revision") or 0) + 1,
        "understanding": {
            "summary": "玩家驾驶载具沿关卡道路推进，依靠自动武器清理普通敌人并在局内升级时选择强化；过程中还会获得终极词条或进入独立武器抽取，最终击败首领并通过奖励与伤害统计复盘本局。",
            "playerGoal": "在载具生命值归零前击败沿途敌人与关卡首领。",
            "basicControls": "战斗中横向调整载具位置；成长界面中选择、刷新或确认强化；结算时选择奖励操作并返回。",
            "coreLoop": "推进并攻击 → 局内升级选择 → 继续战斗/独立抽取 → 首领来袭 → 首领战 → 成功结算。",
            "progression": "局内等级触发普通强化；终极词条改变武器攻击形态；武器抽取提供另一条局内获取路径。",
            "completion": "击败首领后进入挑战成功结算。",
            "failure": "载具生命值归零时本局失败。",
        },
        "entries": [{"id": f"GDE-S5-{index+1:02d}", "chapterId": cid, "title": CHAPTERS[cid]["scope"], "sectionTitle": CHAPTERS[cid]["section"], "order": index+1}
                    for index, cid in enumerate(ordered_ids)],
    }

    diagrams = []
    nodes = [
        {"x": 30, "y": 130, "label": "进入关卡\n开始推进"}, {"x": 225, "y": 130, "label": "普通战斗\n移动与自动攻击"},
        {"x": 420, "y": 120, "label": "达到升级条件？", "kind": "decision", "w": 150, "h": 84},
        {"x": 420, "y": 270, "label": "三选一/终极词条\n或武器抽取"}, {"x": 635, "y": 120, "label": "进入首领阶段？", "kind": "decision", "w": 150, "h": 84},
        {"x": 835, "y": 130, "label": "首领来袭\n进入首领战"}, {"x": 1010, "y": 120, "label": "载具生命归零？", "kind": "decision", "w": 150, "h": 84},
        {"x": 1010, "y": 270, "label": "挑战成功结算", "kind": "result"}, {"x": 835, "y": 390, "label": "失败结算分支", "kind": "result"},
    ]
    edges = [
        {"x1": 180, "y1": 162, "x2": 225, "y2": 162}, {"x1": 375, "y1": 162, "x2": 420, "y2": 162},
        {"x1": 495, "y1": 204, "x2": 495, "y2": 270, "label": "是", "lx": 505, "ly": 242},
        {"x1": 570, "y1": 162, "x2": 635, "y2": 162, "label": "否", "lx": 595, "ly": 150},
        {"x1": 570, "y1": 302, "x2": 635, "y2": 180, "label": "确认后继续", "lx": 580, "ly": 242},
        {"x1": 785, "y1": 162, "x2": 835, "y2": 162, "label": "是"},
        {"x1": 710, "y1": 204, "x2": 300, "y2": 194, "label": "否：继续普通战斗", "lx": 470, "ly": 220},
        {"x1": 985, "y1": 162, "x2": 1010, "y2": 162}, {"x1": 1085, "y1": 204, "x2": 1085, "y2": 270, "label": "否：首领归零"},
        {"x1": 1010, "y1": 190, "x2": 910, "y2": 390, "label": "是", "lx": 950, "ly": 300},
    ]
    diagrams.append(diagram("GDI-101", "关卡完整主循环", "state_flow", ["GCH-006", "GCH-001", "GCH-012", "GCH-010"], nodes, edges, 1200, 500))

    nodes = [
        {"x": 40, "y": 120, "label": "等级进度满足条件"}, {"x": 235, "y": 120, "label": "暂停战斗\n生成三项候选"},
        {"x": 440, "y": 110, "label": "玩家选择操作", "kind": "decision", "w": 150, "h": 84},
        {"x": 665, "y": 70, "label": "确认一项候选"}, {"x": 665, "y": 190, "label": "刷新当前候选"},
        {"x": 870, "y": 70, "label": "应用获得/强化\n关闭弹窗", "kind": "result"},
        {"x": 870, "y": 190, "label": "扣除可用次数\n重新生成三项"},
        {"x": 1020, "y": 70, "label": "恢复战斗", "kind": "result"},
    ]
    edges = [
        {"x1": 190, "y1": 152, "x2": 235, "y2": 152}, {"x1": 385, "y1": 152, "x2": 440, "y2": 152},
        {"x1": 590, "y1": 140, "x2": 665, "y2": 102, "label": "选择卡片"}, {"x1": 590, "y1": 170, "x2": 665, "y2": 222, "label": "点击刷新"},
        {"x1": 815, "y1": 102, "x2": 870, "y2": 102}, {"x1": 1020, "y1": 102, "x2": 1040, "y2": 102},
        {"x1": 870, "y1": 222, "x2": 590, "y2": 190, "label": "返回候选判断", "lx": 710, "ly": 245},
    ]
    diagrams.append(diagram("GDI-102", "三选一玩家操作与系统处理", "state_flow", ["GCH-012"], nodes, edges, 1210, 330))

    nodes = [
        {"x": 40, "y": 120, "label": "升级事件"}, {"x": 235, "y": 110, "label": "终极词条进入条件？", "kind": "decision", "w": 160, "h": 84},
        {"x": 465, "y": 70, "label": "加入终极词条库\n显示金色提示"}, {"x": 465, "y": 210, "label": "维持普通候选池"},
        {"x": 690, "y": 70, "label": "后续候选中出现"}, {"x": 895, "y": 60, "label": "玩家确认？", "kind": "decision", "w": 145, "h": 84},
        {"x": 895, "y": 190, "label": "收益与代价同时生效\n改变攻击形态", "kind": "result"},
    ]
    edges = [
        {"x1": 190, "y1": 152, "x2": 235, "y2": 152}, {"x1": 395, "y1": 140, "x2": 465, "y2": 102, "label": "是"},
        {"x1": 315, "y1": 194, "x2": 465, "y2": 242, "label": "否"}, {"x1": 615, "y1": 102, "x2": 690, "y2": 102},
        {"x1": 840, "y1": 102, "x2": 895, "y2": 102}, {"x1": 968, "y1": 144, "x2": 968, "y2": 190, "label": "是"},
        {"x1": 895, "y1": 115, "x2": 760, "y2": 135, "label": "否：等待后续选择", "lx": 770, "ly": 160},
    ]
    diagrams.append(diagram("GDI-103", "终极词条进入、候选与生效状态", "effect_chain", ["GCH-016"], nodes, edges, 1100, 350))

    nodes = [
        {"x": 40, "y": 120, "label": "打开武器抽取"}, {"x": 235, "y": 120, "label": "三列图标开始滚动"},
        {"x": 445, "y": 110, "label": "玩家跳过动画？", "kind": "decision", "w": 160, "h": 84},
        {"x": 680, "y": 70, "label": "立即停止滚动"}, {"x": 680, "y": 210, "label": "播放至自然停止"},
        {"x": 885, "y": 120, "label": "中间结果框形成结果"}, {"x": 1055, "y": 120, "label": "写入结果并返回战斗", "kind": "result"},
    ]
    edges = [
        {"x1": 190, "y1": 152, "x2": 235, "y2": 152}, {"x1": 385, "y1": 152, "x2": 445, "y2": 152},
        {"x1": 605, "y1": 140, "x2": 680, "y2": 102, "label": "是"}, {"x1": 525, "y1": 194, "x2": 680, "y2": 242, "label": "否"},
        {"x1": 830, "y1": 102, "x2": 885, "y2": 145}, {"x1": 830, "y1": 242, "x2": 885, "y2": 175},
        {"x1": 1035, "y1": 152, "x2": 1055, "y2": 152},
    ]
    diagrams.append(diagram("GDI-104", "武器抽取可见操作流程", "state_flow", ["GCH-018"], nodes, edges, 1240, 350))

    nodes = [
        {"x": 40, "y": 120, "label": "普通战斗推进"}, {"x": 235, "y": 110, "label": "达到首领条件？", "kind": "decision", "w": 160, "h": 84},
        {"x": 465, "y": 70, "label": "播放首领来袭警告"}, {"x": 465, "y": 210, "label": "继续普通战斗"},
        {"x": 680, "y": 70, "label": "进入首领战\n显示独立生命条"}, {"x": 895, "y": 60, "label": "谁先归零？", "kind": "decision", "w": 150, "h": 84},
        {"x": 895, "y": 190, "label": "首领归零：成功结算", "kind": "result"}, {"x": 1065, "y": 190, "label": "载具归零：失败结算", "kind": "result"},
    ]
    edges = [
        {"x1": 190, "y1": 152, "x2": 235, "y2": 152}, {"x1": 395, "y1": 140, "x2": 465, "y2": 102, "label": "是"},
        {"x1": 315, "y1": 194, "x2": 465, "y2": 242, "label": "否"}, {"x1": 615, "y1": 102, "x2": 680, "y2": 102},
        {"x1": 830, "y1": 102, "x2": 895, "y2": 102}, {"x1": 970, "y1": 144, "x2": 970, "y2": 190, "label": "首领"},
        {"x1": 1045, "y1": 120, "x2": 1140, "y2": 190, "label": "载具"}, {"x1": 465, "y1": 242, "x2": 190, "y2": 180, "label": "循环"},
    ]
    diagrams.append(diagram("GDI-105", "首领阶段切换与胜负分流", "state_flow", ["GCH-006", "GCH-010"], nodes, edges, 1240, 350))

    nodes = [
        {"x": 40, "y": 120, "label": "武器产生攻击"}, {"x": 235, "y": 110, "label": "命中有效目标？", "kind": "decision", "w": 160, "h": 84},
        {"x": 465, "y": 70, "label": "显示伤害数字\n播放对应特效"}, {"x": 465, "y": 210, "label": "不产生伤害反馈"},
        {"x": 690, "y": 70, "label": "累计到对应武器伤害"}, {"x": 895, "y": 70, "label": "结算汇总总伤占比与秒伤", "kind": "result", "w": 190},
    ]
    edges = [
        {"x1": 190, "y1": 152, "x2": 235, "y2": 152}, {"x1": 395, "y1": 140, "x2": 465, "y2": 102, "label": "是"},
        {"x1": 315, "y1": 194, "x2": 465, "y2": 242, "label": "否"}, {"x1": 615, "y1": 102, "x2": 690, "y2": 102},
        {"x1": 840, "y1": 102, "x2": 895, "y2": 102},
    ]
    diagrams.append(diagram("GDI-106", "武器命中、反馈与伤害归集", "effect_chain", ["GCH-003", "GCH-010"], nodes, edges, 1140, 340))

    model["diagrams"] = diagrams
    placements = {
        "GDI-101": ("GCH-001", 0, "图中的升级、首领和胜负节点由后续章节分别展开；本节继续说明载具推进与生存边界。"),
        "GDI-102": ("GCH-012", 0, "刷新只替换本轮三项候选，不视为完成选择；玩家确认一项后关闭选择界面并恢复战斗。"),
        "GDI-103": ("GCH-016", 1, "进入词条库不等于已经获得；只有候选出现并被玩家确认后，收益、代价和攻击形态才同时生效。"),
        "GDI-104": ("GCH-018", 0, "跳过只结束表现过程，不改变最终结果生成；消耗、奖池和结果写入规则仍需策划确认。"),
        "GDI-105": ("GCH-006", 1, "首领生命值归零时进入胜利结算；载具生命值归零时进入失败结算。"),
        "GDI-106": ("GCH-003", 2, "命中反馈与伤害归集属于同一数据链路：战斗中产生单次反馈，结算时再按武器汇总总伤占比和秒伤。"),
    }
    for item in model["diagrams"]:
        item["interactionRevision"] = job["reviewModel"]["revision"]
        chapter_id, after_index, follow_up = placements[item["id"]]
        item["placement"] = {"chapterId": chapter_id, "afterFlowIndex": after_index, "followUp": follow_up}
    model["diagramReview"] = {"status": "ready", "noDiagramChapterIds": [], "exceptions": [], "sourceRevision": int(model.get("revision") or 0) + 1}
    # 策划表按实际查配动作拆分。禁止把正文属性塞进统一的“字段审计表”。
    # 无权威数值的单元格留空，避免“待确认/配置值”等流程话术污染交付正文。
    weapon_types = [[name, "", "", "", "", "", "", "", "", "", ""]
                    for name in ["物理", "火", "毒", "雷", "光/能量", "冰", "风"]]
    model["tables"] = [
        {
            "id": "GTB-102", "title": "载具等级", "status": "reviewed", "chapterIds": ["GCH-001"],
            "columns": ["等级", "升级道具ID", "消耗数量", "攻击力", "生命值", "固定减伤"],
            "rows": [["1", "—", "—", "", "", ""], ["2～上限", "", "", "", "", ""]],
        },
        {
            "id": "GTB-102B", "title": "载具栏位与特权", "status": "reviewed", "chapterIds": ["GCH-001"],
            "columns": ["默认武器栏", "自选武器栏", "特权礼包ID", "固定减伤加成", "特权技能ID", "释放间隔(s)"],
            "rows": [["1", "4", "", "", "", ""]],
        },
        {
            "id": "GTB-103", "title": "武器基础属性", "status": "reviewed", "chapterIds": ["GCH-003"],
            "columns": ["武器类型", "基础伤害比例", "元素伤害", "触发间隔(s)", "持续时间(s)", "直接目标数", "间接目标数", "间接伤害比例", "冷却(s)", "索敌范围", "伤害范围"],
            "rows": weapon_types,
        },
        {
            "id": "GTB-103B", "title": "武器解锁与养成", "status": "reviewed", "chapterIds": ["GCH-003"],
            "columns": ["武器类型", "初始解锁", "通关解锁关卡", "升级道具ID", "目标等级", "消耗数量", "元素伤害"],
            "rows": [[name, "", "", "", "", "", ""] for name in ["物理", "火", "毒", "雷", "光/能量", "冰", "风"]],
        },
        {
            "id": "GTB-103C", "title": "武器词条", "status": "reviewed", "chapterIds": ["GCH-003"],
            "columns": ["词条ID", "武器类型", "词条组", "前置词条ID", "最大等级", "权重", "解锁等级", "作用技能ID", "效果参数", "名称", "描述"],
            "rows": [["", "", "", "", "", "", "", "", "", "广域喷射", ""],
                     ["", "", "", "", "", "", "", "", "", "多点爆炸", ""]],
        },
        {
            "id": "GTB-104", "title": "怪物战斗属性", "status": "reviewed", "chapterIds": ["GCH-006"],
            "columns": ["怪物ID", "类型", "基础生命值", "基础攻击力", "移动速度", "攻击距离", "攻速(ms)", "最终减伤", "元素减伤", "闪避(万分比)", "格挡次数", "免疫效果", "攻击动作ID", "子弹ID"],
            "rows": [["", kind, "", "", "", "", "", "", "", "", "", "", "", ""]
                     for kind in ["普通怪", "精英怪", "BOSS"]],
        },
    ]
    model["tables"].append({
        "id": "GTB-105", "title": "关卡波次与刷怪配置结构", "status": "reviewed", "chapterIds": ["GCH-006"],
        "columns": ["关卡", "波次", "怪物组顺序", "组间隔(ms)", "刷怪点类型", "xy偏移", "怪物/首领ID与数量", "生命倍率", "攻击倍率", "切换条件"],
        "rows": [["", "", "1", "", "普通怪点", "", "", "", "", ""],
                 ["", "", "2", "", "精英怪点", "", "", "", "", ""],
                 ["", "", "3", "", "BOSS点", "", "", "", "", ""]],
    })
    coverage_items = []
    for chapter_id in ordered_ids:
        data = CHAPTERS[chapter_id]
        for index, label in enumerate(data["inventory"], 1):
            coverage_items.append({"id": f"CC-{chapter_id}-{index:02d}", "label": label, "sourceIds": data["sources"],
                                   "carrierType": "chapter", "carrierIds": [chapter_id], "status": "covered"})
    for content_id, label, sources, carrier in [
        ("CC-DEC-01", "武器卡累计数值语义", ["F0001", "F0010"], "GDC-101"),
        ("CC-DEC-02", "三选一候选池、权重与刷新重置", ["F0002", "F0004", "F0006", "F0009"], "GDC-102"),
        ("CC-DEC-03", "武器抽取消耗、结果数与随机算法", ["F0008"], "GDC-103"),
        ("CC-DEC-04", "首领附加计数语义", ["F0012", "F0013"], "GDC-104"),
        ("CC-DEC-05", "双倍奖励触发与次数重置", ["F0015"], "GDC-105"),
    ]:
        coverage_items.append({"id": content_id, "label": label, "sourceIds": sources, "carrierType": "decision_card",
                               "carrierIds": [carrier], "status": "decision_required"})
    for index, (label, carrier) in enumerate([
        ("载具等级配置", "GTB-102"), ("载具栏位与特权配置", "GTB-102B"),
        ("武器基础属性配置", "GTB-103"), ("武器解锁与养成配置", "GTB-103B"),
        ("武器词条配置", "GTB-103C"), ("怪物战斗属性配置", "GTB-104"),
        ("关卡波次与刷怪配置结构", "GTB-105"),
    ], 1):
        coverage_items.append({"id": f"CC-REQ-ATTR-{index:02d}", "label": label,
                               "sourceIds": ["USR-20260811-ATTR"], "carrierType": "reviewed_table",
                               "carrierIds": [carrier], "status": "covered"})
    model["contentCoverage"] = {"version": 1, "items": coverage_items,
                                "summary": "当前 15 张竞品截图中的可见玩法内容已逐项映射；无法唯一判断的算法、字段语义和奖励逻辑进入决策卡。"}
    for stage in job.get("reviewModel", {}).get("stages", []):
        for insight in stage.get("gameplayInsights", []):
            if insight.get("id") == "PGI-003":
                insight["text"] = "抽取滚动区域会同时展示武器与技能图标，停止后读取中间结果框中的最终结果。"
    synced = sync_planning_gameplay_insights(job, model)
    model["chapters"] = synced["chapters"]
    model["planningGameplayTrace"] = synced["planningGameplayTrace"]
    model["granularityAuditVersion"] = 4
    model["revision"] = int(model.get("revision") or 0) + 1
    model.setdefault("reviewState", {}).update({"status": "chapter_review", "structurePhase": "detailed", "previewRevision": None})
    job["gameplayFinalPreview"] = None
    job["updatedAt"] = datetime.now(timezone.utc).isoformat()
    temporary = JOB_PATH.with_suffix(".stage5-v2.tmp")
    temporary.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(JOB_PATH)
    print(json.dumps({"jobId": JOB_ID, "backup": str(backup), "chapters": len(model["chapters"]),
                      "coverageItems": len(coverage_items), "diagrams": len(diagrams), "revision": model["revision"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
