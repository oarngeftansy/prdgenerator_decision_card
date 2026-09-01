from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AUDIT = ROOT / "artifacts/gve16-complete-delivery-gap-audit-2026-08-19/一路狂飙-GVE16-最完整差异审计.md"
DEFAULT_OUTPUT = DEFAULT_AUDIT.parent / "alignment-closure-matrix.json"
ATOM_ID = re.compile(r"^(H|UE|W|C|D|M|L|S|P5|P6|PR)-\d+$")


DELIVERY_ROUTES = {
    "H": ["Planning Hierarchy", "Final", "P5", "P6"],
    "UE": ["UE", "策划草图"],
    "W": ["Approved Rule", "RuleChain", "Final", "P6"],
    "C": ["Approved Rule", "RuleChain", "Final", "P5", "P6"],
    "D": ["Approved Rule", "RuleChain", "Final", "UE", "策划草图"],
    "M": ["Approved Rule", "RuleChain", "Final", "P5", "P6"],
    "L": ["Approved Rule", "RuleChain", "Final", "UE", "P5", "P6"],
    "S": ["Approved Rule", "RuleChain", "Final", "P5", "策划草图"],
    "P5": ["P5", "Final"],
    "P6": ["P6", "Final"],
    "PR": ["策划草图", "Final"],
    "X": ["Final Crosswalk", "UE", "P5", "P6", "策划草图"],
}

# These closures are backed by regenerated canonical delivery files, not by the
# matrix itself. Keep the evidence path precise so a stale/missing artifact fails review.
DELIVERY_CLOSURES = {
    "UE-01": ("data/jobs/4180cd72eeaa4819be41db50bb4c5011/structures/ue-flow-annotations.json#loops", "UE Board 先展示覆盖全部已核验页面的“局内挑战循环”总容器。"),
    "UE-02": ("js/ue-flow-review.js#annotationLoops", "stageId 已映射为成长选择、首领战斗、结算返回三个用户可读阶段分组，并通过完整覆盖校验。"),
    "UE-03": ("ue-flow-review-acceptance.json", "三个小循环均绑定进入页与退出 transition。"),
    "UE-09": ("ue-flow-review-acceptance.json", "所有交互按钮均绑定目标页面/状态，自动流转使用具名系统触发。"),
    "UE-10": ("ue-flow-review-acceptance.json", "正向流程线已绑定选择、展示完成、结果结算、首领生成和成功条件，不再用截图顺序替代触发关系。"),
    "UE-12": ("ue-flow-review-acceptance.json", "刷新、跳过、选择、首领生成和成功结算条件均投影到对应边。"),
    "UE-13": ("ue-flow-review-acceptance.json", "页面功能说明已由 Review 接收，并与 Final/P5 的 Approved Rule 一致。"),
    "UE-15": ("feishu-native-whiteboards/remote-publication-acceptance.json", "远端飞书文档与 planning/competitor 两块原生画板已发布，并通过预览与 raw 双重验收。"),
    "H-02": ("human-planning-preview.md#自然-Owner", "Final 已使用载具、武器、怪物、战斗规则和关卡规则作为稳定 Owner。"),
    "H-08": ("cross-delivery-references.json", "独立抽取以结构化关系消费武器获取/升级/替换的 Primary Owner 定义，未复制具体规则块。"),
    "H-10": ("human-planning-preview.md#关卡规则/内部逻辑", "战斗等级、三选一和独立抽取已回归关卡内部逻辑。"),
    "H-11": ("human-planning-preview.md#载具", "载具已作为攻击目标、失败条件和武器栏持有者的独立 Owner。"),
    "H-12": ("human-planning-preview.md#交付索引", "Final 以自然业务名建立正文、P5 图解与 P6 配置表定位，不暴露工程 ID。"),
    "UE-11": ("data/jobs/4180cd72eeaa4819be41db50bb4c5011/structures/ue-flow-annotations.json#UET-F0015-RETURN", "UE 已以 return 方向和独立符号投影结算返回线，与 forward/branch 明确区分。"),
    "UE-16": ("feishu-native-whiteboards/acceptance.json", "交互交付已固定为策划草图与竞品参考两个独立原生板；竞品素材为空时只显示待补充，不混入策划或 UX 内容。"),
    "UE-17": ("js/ue-flow-review.js#annotationPages", "UE 审核允许每页 1—4 个真实功能标记；当前注释已删除为凑数产生的战斗背景区和重复武器栏标记。"),
    "P5-04": ("necessary-diagrams.json#P5-CHOICE-FLOW", "Pool 不足已作为显式分支投影到 P5。"),
    "P5-05": ("necessary-diagrams.json#P5-CHOICE-FLOW", "三选一已基于获批的触发、资格、去重、Pool不足、刷新、选择与恢复规则生成完整条件图。"),
    "P5-08": ("necessary-diagrams.md#关卡阶段与结算流程", "成功/失败按 edge 分支渲染，不再线性串联。"),
    "P5-11": ("necessary-diagrams.json#P5-DAMAGE-DATA", "已批准的按武器累计、总伤害求和、占比计算、冻结与结算读取已进入统计数据流图。"),
    "P5-12": ("data/jobs/4180cd72eeaa4819be41db50bb4c5011/structures/p5-review-diagrams.json", "5 张必要图解已通过只读 sidecar 进入当前任务 P5 审核模型，且未修改 job.json。"),
    "P6-05": ("human-planning-preview.md#武器词条配置", "组合词条按参数职责拆行，值与单位分列。"),
    "P6-09": ("publication-tables.json#tables.rows", "P6 已按每个参数行投影 reviewStatus 与 sourceStatus，不再只有整体 source。"),
    "P6-17": ("data/jobs/4180cd72eeaa4819be41db50bb4c5011/structures/p6-review-tables.json", "新 P6 产物已通过通用 sidecar 读取链进入历史任务审核模型，且未修改 job.json。"),
    "M-14": ("necessary-diagrams.json#P5-MONSTER-STATE", "怪物暂停与恢复已在怪物正文和 P5 状态图中形成显式跨机制关系。"),
    "S-08": ("human-planning-preview.md#战斗规则/伤害统计", "F0015 已观察的秒伤维度已作为展示事实进入 Final，未推导公式。"),
    "X-01": ("necessary-diagrams.json#P5-CHOICE-FLOW", "P5 显式投影3项候选与 Pool 不足分支。"),
    "X-02": ("planning-sketch.md#三选一/界面信息", "草图已投影刷新次数和刷新入口。"),
    "X-03": ("planning-sketch.md#独立抽取/结果展示", "草图已投影滚动网格和结果行。"),
    "X-07": ("planning-sketch.md#结算/结果信息", "草图已投影武器占比、秒伤和总伤展示。"),
    "X-08": ("human-planning-preview.md#战斗规则/伤害统计", "秒伤展示事实已同步至 Final 与策划草图；未批准公式仍不进入任何交付。"),
    "X-09": ("data/jobs/4180cd72eeaa4819be41db50bb4c5011/structures/ue-flow-annotations.json#UET-F0015-RETURN", "结算返回控件已绑定至“当前挑战的关卡入口页”外部目标，与 Final 一致。"),
}
PROGRESS_EVIDENCE = {
    "UE-09": ("data/jobs/4180cd72eeaa4819be41db50bb4c5011/structures/ue-flow-annotations.json#transitions", "已建立刷新和跳过动画的控件→目标状态绑定；其余页面跳转继续保持开放。"),
    "UE-12": ("js/ue-flow-review.js#annotationTransitions", "已在 UE 边上投影刷新/跳过的成立条件；其余分支尚未全部绑定。"),
}
BLOCKED_CLOSURES = {
    "W-18": "当前项目正式武器词条配置导出（稳定表名、字段名与版本）尚未提供；取得后逐行绑定7个已观察词条参数并重新生成 P6。",
    "P6-06": "当前项目正式武器词条配置导出（稳定表名、字段名与版本）尚未提供；取得后逐行绑定7个已观察词条参数并重新生成 P6。",
    "L-13": "当前项目商业化策略尚未确认入口承载、奖励范围、次数、失败降级与地区合规；取得决策后生成 Approved Rule 并同步 Final/P5/P6/策划草图。",
}
BLOCKED_EVIDENCE = {
    "W-18": "artifacts/full-mechanic-accepted-publication-2026-08-19/p6-source-contract.json",
    "P6-06": "artifacts/full-mechanic-accepted-publication-2026-08-19/p6-source-contract.json",
    "L-13": "artifacts/full-mechanic-accepted-publication-2026-08-19/commercial-decision-contract.json",
}
BLOCKED_ACTIONS = {
    "W-18": "取得正式配置导出后逐行绑定真实表名、字段名和版本，并重新生成 P6 来源投影。",
    "P6-06": "取得正式配置导出后逐行绑定真实表名、字段名和版本，并重新生成 P6 来源投影。",
    "L-13": "商业负责人确认入口承载、奖励范围、次数、失败降级和地区合规后，生成 Approved Rule 并同步 Final/P5/P6/策划草图。",
}
EVIDENCE_CLOSURES = {
    "L-06": "击败 Boss 后继续清理场上剩余怪物；剩余怪物清空后结束战斗并进入成功结算。",
    "P5-09": "Boss 死亡到关卡完成的分支已按连续视频证据补为“清理剩余怪物→剩余怪物清空”。",
}
DESIGN_CLOSURES = {
    "C-01": ("approved_design", "新挑战的战斗等级固定从1级初始化。"),
    "C-02": ("approved_design", "击败怪物获得该怪物配置的经验值。"),
    "C-03": ("parameter_resolved", "升级阈值采用10+5×(当前等级-1)的项目自有参数公式。"),
    "C-05": ("approved_design", "三选一和独立抽取统一暂停战斗模拟与计时，仅保留界面动画。"),
    "C-06": ("approved_design", "候选资格由解锁、前置、上限和构筑兼容性共同决定。"),
    "C-10": ("approved_design", "候选从合格内容中等概率无放回生成，最多3项。"),
    "C-11": ("scope_confirmed_not_applicable", "范围核验并批准当前项目使用单级内容池，不采用先类型后内容的两级抽取。"),
    "C-20": ("approved_design", "多级连续升级进入待处理队列，逐级完成选择和抽取后再恢复战斗。"),
    "C-21": ("parameter_resolved", "刷新次数每局初始化为1次。"),
    "C-22": ("approved_design", "刷新次数在新挑战开始时重置为1次，本局内不自然恢复。"),
    "C-23": ("approved_design", "新挑战将战斗等级和经验重置为1级、0经验。"),
    "D-06": ("approved_design", "独立抽取展示的3项结果全部获得。"),
    "D-09": ("approved_design", "结果在动画前确定；跳过只缩短展示时间，不改变结果。"),
    "D-10": ("parameter_resolved", "独立抽取由等级奖励触发，额外消耗为0。"),
    "D-11": ("approved_design", "抽取池复用当前可生效的武器与技能内容，并过滤已达上限或不兼容项。"),
    "D-12": ("parameter_resolved", "合格抽取项采用等概率口径。"),
    "D-13": ("scope_confirmed_not_applicable", "范围核验并批准当前项目不设置独立抽取保底。"),
    "D-14": ("approved_design", "独立抽取不可放弃；满栏新武器必须完成替换。"),
    "P6-13": ("parameter_resolved", "三选一候选与独立抽取均建立等概率参数口径。"),
    "P6-14": ("parameter_resolved", "刷新次数总量配置为1次/局，新挑战重置。"),
    "P6-15": ("parameter_resolved", "独立抽取额外消耗配置为0。"),
    "W-07": ("approved_design", "武器选择射程内距离载具最近的敌人，目标失效后重新选择。"),
    "W-11": ("parameter_resolved", "非持续武器基础攻击间隔配置为1.0秒。"),
    "W-12": ("parameter_resolved", "持续武器基础结算间隔配置为0.2秒。"),
    "W-13": ("parameter_resolved", "非持续/持续武器基础射程分别配置为8/6世界单位。"),
    "W-14": ("approved_design", "伤害按基础伤害、同武器伤害修正之和、命中次数的顺序结算。"),
    "W-20": ("approved_design", "武器、局内等级和词条在新挑战开始时重置。"),
    "M-04": ("parameter_resolved", "怪物接触阈值配置为碰撞边缘距离≤0.5世界单位。"),
    "M-05": ("approved_design", "怪物接触载具后停止移动；脱离后恢复靠近。"),
    "M-06": ("approved_design", "接触成立时立即造成首次伤害。"),
    "M-08": ("parameter_resolved", "怪物保持接触时每1.0秒重复造成伤害。"),
    "M-09": ("parameter_resolved", "怪物脱离阈值配置为碰撞边缘距离>0.75世界单位。"),
    "M-16": ("scope_confirmed_not_applicable", "范围核验并批准普通怪物唯一合法攻击目标为载具，不存在多目标切换分支。"),
    "S-05": ("approved_design", "直接、持续、爆炸和词条附加伤害均归属触发它们的武器。"),
    "S-09": ("parameter_resolved", "秒伤分母采用武器有效战斗秒数，并排除选择、抽取和结算暂停时间。"),
    "S-10": ("scope_confirmed_not_applicable", "范围核验确认伤害统计只在结算页展示冻结结果，不存在战斗中实时刷新。"),
    "S-11": ("approved_design", "结算按累计伤害降序排列，同值按武器栏位顺序。"),
    "S-12": ("approved_design", "条长以本局最高武器累计伤害为100%归一化。"),
    "S-16": ("fixed", "离开结算后清除统计累计、有效战斗时长和冻结快照。"),
    "P6-10": ("parameter_resolved", "P6 已承载非持续武器1.0秒攻击间隔与持续武器0.2秒结算间隔。"),
    "P6-11": ("parameter_resolved", "P6 已承载0.5接触阈值、0.75脱离阈值、首次0延迟与1.0秒Repeat。"),
    "P6-12": ("parameter_resolved", "P6 与 Final 已承载基础伤害、伤害修正和命中次数的计算顺序。"),
    "X-04": ("fixed", "怪物接触攻击的阈值、停移、首次伤害、Repeat和脱离已同步 Final/P5/P6。"),
    "L-01": ("approved_design", "击败普通怪物累计配置进度，达到100点时停止普通刷怪并进入首领来袭。"),
    "L-09": ("scope_confirmed_not_applicable", "范围核验确认计时器只记录经过时间，不参与失败判定。"),
    "L-11": ("approved_design", "成功结算100基础货币并结算道具；失败结算50基础货币且不结算道具。"),
    "L-12": ("parameter_resolved", "成功/失败奖励在胜负冻结后按100/50基础货币一次计算。"),
    "L-15": ("approved_design", "失败页显示挑战失败、存活时间、失败奖励、武器统计、再次挑战与返回。"),
    "L-16": ("approved_design", "首次成功额外发放200货币且每关一次；不设置进度里程碑奖励。"),
    "L-17": ("parameter_resolved", "进入战斗消耗5体力，战斗开始后失败不返还，进入前取消不扣除。"),
    "P6-16": ("parameter_resolved", "P6 已承载阶段目标、成功/失败/首通奖励和体力消耗返还参数。"),
    "PR-19": ("fixed", "策划草图已补齐失败页标题、存活时间、奖励、伤害统计、重试与返回。"),
    "X-06": ("fixed", "载具生命归零失败已同步 Final、P5、P6 与失败策划草图。"),
}
for _audit_id in ("PR-02", "PR-03", "PR-05", "PR-06", "PR-09", "PR-10", "PR-11", "PR-12", "PR-13", "PR-14", "PR-15", "PR-16", "PR-17"):
    DELIVERY_CLOSURES[_audit_id] = ("planning-sketch.md", "已观察表现已投影到策划草图，不反向定义玩法逻辑。")


def split_row(line: str) -> list[str]:
    return [part.strip() for part in line.strip().strip("|").split("|")]


def route(root_cause: str, judgement: str) -> tuple[str, str]:
    reason = root_cause.lower()
    if judgement == "=":
        return "verification_only", "fixed"
    if judgement == "S":
        return "suppression_guardrail", "fixed"
    if "delivery_pending" in reason or "implementation" in reason or "publication" in reason:
        return "implementation_depth", "fixed"
    if "parameter" in reason or "algorithm" in reason or "公式" in root_cause or "字段" in root_cause:
        return "parameter_review", "parameter_resolved"
    if "material_insufficient" in reason or "截图" in root_cause or "素材" in root_cause:
        return "evidence_probe_then_review", "evidence_resolved"
    if judgement == "U" or "范围" in root_cause or "存在信号" in root_cause:
        return "scope_verification", "approved_design"
    if "review" in reason or "approval" in reason or judgement in {"△", "×", "S/△"}:
        return "design_review", "approved_design"
    return "delivery_reconciliation", "fixed"


def make_entry(audit_id: str, feature: str, carrier: str, judgement: str, cause: str) -> dict:
    prefix = audit_id.split("-", 1)[0]
    remediation, target = route(cause, judgement)
    already_closed = judgement in {"=", "S"}
    routes = DELIVERY_ROUTES[prefix]
    action = (
        f"回归验证「{feature}」在{'、'.join(routes)}的承载与门禁。"
        if already_closed
        else f"按 {remediation} 路由关闭「{feature}」，并重建{'、'.join(routes)}的真实交付面。"
    )
    return {
        "auditId": audit_id,
        "feature": feature,
        "originalCarrier": carrier,
        "originalJudgement": judgement,
        "currentJudgement": judgement,
        "currentState": "closed_verified" if already_closed else "open",
        "targetState": target,
        "rootCause": cause or "—",
        "remediationType": remediation,
        "actions": [action],
        "affectedFiles": [],
        "affectedArtifacts": routes,
        "acceptanceCriteria": [
            f"「{feature}」的交付结论可从权威来源追溯到{'、'.join(routes)}。",
            "不引入 GVE16 项目答案，不把 Proposal/Requirement/审核语言写入 Final。",
        ],
        "closureState": "fixed" if already_closed else "in_progress",
        "beforeEvidence": [carrier] if carrier and carrier != "—" else [],
        "afterEvidence": [],
        "verification": ["pending_real_delivery_verification"] if not already_closed else ["audit_baseline_verified"],
        "remainingRisk": [] if already_closed else [cause or "requires_real_delivery_change"],
    }


def parse_audit(text: str) -> list[dict]:
    entries: list[dict] = []
    in_cross_delivery = False
    cross_index = 0
    for line in text.splitlines():
        if line.startswith("## 12. "):
            in_cross_delivery = True
            continue
        if not line.startswith("|") or line.startswith("|---"):
            continue
        cells = split_row(line)
        if cells and ATOM_ID.fullmatch(cells[0]):
            if len(cells) == 5:
                audit_id, feature, carrier, judgement, cause = cells
            elif len(cells) == 6 and cells[0].startswith("P5-"):
                audit_id, diagram, check, carrier, judgement, cause = cells
                feature = f"{diagram}：{check}"
            else:
                raise ValueError(f"unexpected atomic row: {line}")
            entries.append(make_entry(audit_id, feature, carrier, judgement, cause))
        elif in_cross_delivery and len(cells) == 7 and cells[0] not in {"规则/信息", "---"}:
            cross_index += 1
            audit_id = f"X-{cross_index:02d}"
            carrier = f"正文={cells[1]}; UE={cells[2]}; P5={cells[3]}; P6={cells[4]}; 草图={cells[5]}"
            conclusion = cells[6]
            judgement = "=" if conclusion.startswith("=") else "×" if conclusion.startswith("×") else "△"
            entries.append(make_entry(audit_id, cells[0], carrier, judgement, conclusion))
    ids = [entry["auditId"] for entry in entries]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate audit IDs")
    for entry in entries:
        closure = DELIVERY_CLOSURES.get(entry["auditId"])
        if not closure:
            continue
        evidence, result = closure
        entry.update({
            "currentJudgement": "=",
            "currentState": "closed_verified",
            "targetState": "fixed",
            "closureState": "fixed",
            "afterEvidence": [evidence if evidence.startswith(("data/", "artifacts/")) else f"artifacts/full-mechanic-accepted-publication-2026-08-19/{evidence}"],
            "verification": [result],
            "remainingRisk": [],
        })
    for entry in entries:
        progress = PROGRESS_EVIDENCE.get(entry["auditId"])
        if not progress or entry["closureState"] == "fixed":
            continue
        evidence, result = progress
        entry.update({
            "currentJudgement": "△",
            "currentState": "partially_remediated",
            "afterEvidence": [evidence],
            "verification": [result],
        })
    for entry in entries:
        missing_source = BLOCKED_CLOSURES.get(entry["auditId"])
        if not missing_source:
            continue
        entry.update({
            "currentJudgement": "△",
            "currentState": "terminal_blocked",
            "targetState": "blocked_by_missing_source",
            "closureState": "blocked_by_missing_source",
            "actions": [BLOCKED_ACTIONS[entry["auditId"]]],
            "affectedFiles": [BLOCKED_EVIDENCE[entry["auditId"]]],
            "afterEvidence": [BLOCKED_EVIDENCE[entry["auditId"]]],
            "verification": ["缺失 source 与取得后的关闭动作均已进入 P6 Review 交付。"],
            "remainingRisk": [missing_source],
        })
    for entry in entries:
        resolved = EVIDENCE_CLOSURES.get(entry["auditId"])
        if not resolved:
            continue
        entry.update({
            "currentJudgement": "=",
            "currentState": "closed_verified",
            "targetState": "evidence_resolved",
            "closureState": "evidence_resolved",
            "actions": ["复核 185–202 秒连续视频，并将 Boss 死亡后的剩余怪物清理条件同步至 Final 与 P5。"],
            "affectedFiles": [
                "artifacts/full-mechanic-accepted-publication-2026-08-19/human-planning-preview.md",
                "artifacts/full-mechanic-accepted-publication-2026-08-19/necessary-diagrams.json",
            ],
            "afterEvidence": [
                "artifacts/gve16-complete-delivery-gap-audit-2026-08-19/probes/boss-death-to-settlement/probe-report.json",
                "artifacts/full-mechanic-accepted-publication-2026-08-19/necessary-diagrams.json#P5-LEVEL-OUTCOME",
            ],
            "verification": [resolved],
            "remainingRisk": [],
        })
    for entry in entries:
        closure = DESIGN_CLOSURES.get(entry["auditId"])
        if not closure:
            continue
        closure_state, resolved = closure
        entry.update({
            "currentJudgement": "=",
            "currentState": "closed_verified",
            "targetState": closure_state,
            "closureState": closure_state,
            "actions": ["将 Review 接收的项目自有方案投影至 Final、P5、P6 与策划草图，并执行跨交付一致性校验。"],
            "affectedFiles": [
                "artifacts/full-mechanic-accepted-publication-2026-08-19/human-planning-preview.md",
                "artifacts/full-mechanic-accepted-publication-2026-08-19/necessary-diagrams.json",
                "artifacts/full-mechanic-accepted-publication-2026-08-19/publication-tables.json",
                "artifacts/full-mechanic-accepted-publication-2026-08-19/planning-sketch.md",
            ],
            "afterEvidence": [
                "artifacts/full-mechanic-accepted-publication-2026-08-19/alignment-closure-review.json",
                "artifacts/full-mechanic-accepted-publication-2026-08-19/human-planning-preview.md",
                "artifacts/full-mechanic-accepted-publication-2026-08-19/p6-review-tables.json",
            ],
            "verification": [resolved],
            "remainingRisk": [],
        })
    return entries


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    entries = parse_audit(args.audit.read_text(encoding="utf-8"))
    document = {
        "schemaVersion": "alignment-closure-matrix/v1",
        "benchmark": "一路狂飙-GVE16",
        "sourceAudit": str(args.audit.relative_to(ROOT)).replace("\\", "/"),
        "allowedTerminalStates": [
            "fixed", "approved_design", "evidence_resolved", "parameter_resolved",
            "scope_confirmed_not_applicable", "blocked_by_missing_source",
        ],
        "summary": {
            "total": len(entries),
            "atomic": sum(not e["auditId"].startswith("X-") for e in entries),
            "crossDelivery": sum(e["auditId"].startswith("X-") for e in entries),
            "closedBaseline": sum(e["closureState"] == "fixed" for e in entries),
            "evidenceResolved": sum(e["closureState"] == "evidence_resolved" for e in entries),
            "approvedDesign": sum(e["closureState"] == "approved_design" for e in entries),
            "parameterResolved": sum(e["closureState"] == "parameter_resolved" for e in entries),
            "scopeConfirmedNotApplicable": sum(e["closureState"] == "scope_confirmed_not_applicable" for e in entries),
            "blocked": sum(e["closureState"] == "blocked_by_missing_source" for e in entries),
            "closed": sum(e["closureState"] != "in_progress" for e in entries),
            "open": sum(e["closureState"] == "in_progress" for e in entries),
        },
        "items": entries,
    }
    rendered = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
    if args.check:
        if not args.output.exists() or args.output.read_text(encoding="utf-8") != rendered:
            raise SystemExit("alignment closure matrix is missing or stale")
        return
    args.output.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()
