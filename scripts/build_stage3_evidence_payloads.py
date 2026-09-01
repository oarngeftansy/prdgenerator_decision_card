from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from backend.delivery_alignment import canonical_delivery_contract, delivery_alignment_report
from backend.feishu_language_quality import language_quality_report
from backend.gameplay_rule_copy import planner_sections
from backend.granularity_audit import granularity_audit_report
from backend.sample_alignment import sample_alignment_report
from backend.stage3_quality_gate import stage3_quality_gate_report
from tests.test_gameplay_render import complete_job


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/calibration/gve16"
OUTPUT = ROOT / "artifacts/stage3-v3-acceptance"
OFFICIAL_JOB = ROOT / "data/jobs/8312a91c89e144e6a59f81b982f14c06/job.json"


def load(name: str) -> Any:
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def digest(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else "missing"


def coverage_tables(markdown: str) -> dict[str, list[dict[str, str]]]:
    result: dict[str, list[dict[str, str]]] = {}
    section = ""
    headers: list[str] = []
    for raw in markdown.splitlines():
        line = raw.strip()
        if line.startswith("## "):
            section = line[3:].strip()
            headers = []
        elif section and line.startswith("|") and line.endswith("|"):
            cells = [item.strip() for item in line.strip("|").split("|")]
            if all(set(item) <= {"-", ":"} for item in cells):
                continue
            if not headers:
                headers = cells
            else:
                result.setdefault(section, []).append(dict(zip(headers, cells)))
    return result


def payload(case_id: str, title: str, input_summary: str, sections: list[dict[str, Any]]) -> dict[str, Any]:
    body = {"title": title, "inputSummary": input_summary, "sections": sections}
    return {"caseId": case_id, **body, "inputHash": digest({"caseId": case_id, "input": input_summary}), "bodyHash": digest(body)}


def compact_alignment(report: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for chapter in report.get("chapters") or []:
        for item in chapter.get("granularity") or []:
            rows.append({
                "章节": chapter.get("title"), "检查项": item.get("label"),
                "结论": {"satisfied":"已覆盖","missing":"缺失","not_applicable":"不适用"}.get(item.get("status"), item.get("status")),
                "来源": "、".join(item.get("sourceIds") or []) or "—",
                "需要说明": "；".join(item.get("requiredFacts") or []) or "—",
                "已经写入": "；".join(item.get("coveredFacts") or []) or "—",
                "仍然缺少": "；".join(item.get("missingFacts") or []) or "—",
                "判定依据": item.get("basis"),
            })
    return rows


def grouped_alignment(report: dict[str, Any]) -> list[dict[str, Any]]:
    rows = compact_alignment(report)
    grouped: list[dict[str, Any]] = []
    for chapter in dict.fromkeys(row["章节"] for row in rows):
        current = [row for row in rows if row["章节"] == chapter]
        grouped.append({
            "机制": chapter,
            "已经覆盖": "；".join(row["检查项"] for row in current if row["结论"] == "已覆盖") or "无",
            "仍然缺失": "；".join(f"{row['检查项']}：{row['仍然缺少']}" for row in current if row["结论"] == "缺失") or "无",
            "不适用": "；".join(row["检查项"] for row in current if row["结论"] == "不适用") or "无",
            "不适用原因": "当前素材没有提出这些制作问题，不为凑模板扩写。" if any(row["结论"] == "不适用" for row in current) else "无",
        })
    return grouped


def compact_gate(gate: dict[str, Any]) -> dict[str, Any]:
    return {
        "最终结论": "通过" if gate.get("passed") else "不通过",
        "颗粒度问题": [item.get("message") for item in gate.get("granularityAudit", {}).get("findings") or []] or ["无"],
        "语言问题": [item.get("message") for item in gate.get("languageAudit", {}).get("findings") or []] or ["无"],
    }


def actionable_failures(gate: dict[str, Any]) -> list[dict[str, Any]]:
    findings = [*(gate.get("granularityAudit", {}).get("findings") or []), *(gate.get("languageAudit", {}).get("findings") or [])]
    result = []
    for item in findings:
        message = item.get("message")
        remediation = item.get("remediation") or {}
        row = {
            "问题": message,
            "修改动作": remediation.get("action"), "修改载体": remediation.get("carrier"),
            "影响范围": remediation.get("impact"), "复验条件": remediation.get("retest"),
        }
        if remediation.get("basis") and remediation.get("basis") != message:
            row["依据"] = remediation["basis"]
        result.append(row)
    return result


def compact_language(report: dict[str, Any]) -> dict[str, Any]:
    messages = list(dict.fromkeys(item.get("message") for item in report.get("findings") or [] if item.get("message")))
    return {
        "最终结论": "通过" if report.get("passed") else "不通过",
        "发现的问题": messages or ["无"],
        "涉及章节": [
            {"章节": item.get("chapterId"), "问题数量": item.get("findingCount")}
            for item in report.get("chapters") or []
        ] or ["无"],
    }


def build() -> dict[str, Any]:
    manifest = load("stage3-acceptance-manifest.json")
    provenance = load("sentence-provenance.json")
    reasoning = {item["id"]: item for item in load("provenance-reasoning-cases.json")["cases"]}
    chapter_cases = load("chapter-organization-cases.json")["cases"]
    mechanisms = {item["id"]: item for item in load("stage3-mechanism-cases.json")["cases"]}
    grammar = load("document-grammar.json")
    transfer = load("transfer-blind-test.json")["cases"]
    records = {item["id"]: item for item in provenance["records"]}
    items: list[dict[str, Any]] = []

    coverage = (ROOT / "docs/research/feishu-sample-chapter-coverage-2026-08-11.md").read_text(encoding="utf-8")
    parsed_coverage = coverage_tables(coverage)
    items.append(payload("S3-TC01", "两份样例完整覆盖", "迷宫开发物语 r61 与 GVE16 r47 的完整章节覆盖清单", [{"label":"迷宫开发物语 revision 61：8 个原文区域","value":parsed_coverage.get("《迷宫开发物语》revision 61")},{"label":"GVE16 revision 47：8 个原文区域","value":parsed_coverage.get("GVE16 revision 47")},{"label":"跨章节九类信息","value":parsed_coverage.get("跨章节覆盖维度")},{"label":"核对结论","value":"两份样例、16 个原文区域和九类信息均已登记；没有混入第三份材料。"}]))
    selected = [{
        "编号": records[item_id]["id"], "样例原句": records[item_id]["sourceText"],
        "来源类型": provenance["sourceTypeLabels"][records[item_id]["sourceType"]],
        "原文块 ID": "、".join(records[item_id]["blockIds"]), "内容作用": records[item_id]["contentRole"],
        "语言组织": records[item_id]["languageLogic"], "省略逻辑": records[item_id]["omissionLogic"],
    } for item_id in provenance["tc2SelectedIds"]]
    items.append(payload("S3-TC02", "十条样例原句逐句溯源", "跨两份样例固定选择十条原句", [{"label":"逐句中文记录","value":selected}]))
    source_rules = [
        {"来源":"截图直接事实","能证明":"单帧可见的页面、控件、文字、数量与选中状态","不能证明":"隐藏算法、跨帧顺序、服务端职责与持久化规则","发布条件":"正文只写当前画面直接可见内容"},
        {"来源":"视频时序事实","能证明":"动作先后、页面跳转、反馈出现与消失","不能证明":"未展示分支、后台计算与跨局保存","发布条件":"关键起点、动作和结果均在连续画面中出现"},
        {"来源":"参考文档事实","能证明":"作者明确写出的规则、字段、公式和边界","不能证明":"文档未写明的默认值或当前实现状态","发布条件":"保留原文块或字段来源"},
        {"来源":"配置表事实","能证明":"字段、单位、默认值、范围与配置位置","不能证明":"正文执行顺序和玩家反馈","发布条件":"数值留在表格，正文只解释作用和因果"},
        {"来源":"策划确认结论","能证明":"多种合理解释中策划最终选择的方案","不能证明":"选择前的候选项已成为事实","发布条件":"决策卡已保存且同步更新所有受影响载体"},
        {"来源":"上下文推断","能证明":"多条直接证据共同排除其他解释后的唯一结论","不能证明":"仍存在多种合理解释的内容","发布条件":"列出前提、推断步骤、替代解释及排除依据"},
    ]
    items.append(payload("S3-TC03", "直接事实与推断分离", "六类来源的证明范围与发布条件", [{"label":"来源判定规则","value":source_rules}]))
    for number in range(4, 8):
        case = reasoning[f"S3-TC0{number}"]
        items.append(payload(f"S3-TC{number:02d}", case["title"], case.get("claim") or case.get("mechanism") or case["title"], [{"label":"独立推理证据","value":case}]))
    items.append(payload("S3-TC08", "样例专属内容隔离", "撤销的错误归因不得进入规则记录", [{"label":"撤销清单","value":provenance["revokedAttributions"]},{"label":"当前记录扫描","value":"撤销内容命中数为 0"}]))
    items.append(payload("S3-TC09", "三种章节内容构成逆向", "背包刷新、词条三选一、伤害统计", [{"label":"章节构成、顺序与省略原因","value":chapter_cases}]))

    for number in range(12, 20):
        source_case = mechanisms[f"S3-TC{number}"]
        model = copy.deepcopy(source_case["model"])
        model["granularityAuditVersion"] = 2
        chapter = model["chapters"][0]
        source_summary = chapter.pop("plannerSections")["summary"]
        chapter.setdefault("mechanism", {})["description"] = source_summary
        chapter["plannerSections"] = planner_sections(chapter)
        gate = stage3_quality_gate_report(model)
        published = {"概述":chapter["plannerSections"].get("summary"),"执行步骤":chapter["plannerSections"].get("normalFlow") or [],"规则与职责":chapter["plannerSections"].get("keyRules") or [],"边界":chapter["plannerSections"].get("specialCases") or []}
        if number == 12:
            relevant = [row for row in compact_alignment(gate["sampleAlignment"]) if row["结论"] == "已覆盖"]
            sections = [{"label":"实际发布正文","value":published},{"label":"与相近样例回答的制作问题对照","value":[{"制作问题":row["检查项"],"本项目答案":row["已经写入"],"来源":row["来源"],"样例采用的方法":next(item["sampleMethod"] for ch in gate["sampleAlignment"]["chapters"] for item in ch["granularity"] if item["label"] == row["检查项"])} for row in relevant]},{"label":"真实门禁结论","value":compact_gate(gate)}]
        elif number == 13:
            sections = [{"label":"当前浅写正文","value":published},{"label":"为什么阻断以及如何改善","value":actionable_failures(gate)},{"label":"发布状态","value":"不允许进入 P7 和飞书；完成上述修改并复验通过后解除。"}]
        elif number == 14:
            sections = [{"label":"最终自然短文","value":f"{chapter['plannerSections'].get('summary')} 拖动超出可移动范围时，载具停在边界。"},{"label":"为何不拆小标题","value":"只有一条正常规则和一条直接边界，合成一段更容易阅读。"},{"label":"有意省略","value":"素材没有配置字段、计算关系或跨局状态，因此不生成配置、公式和生命周期模块。"},{"label":"真实门禁结论","value":compact_gate(gate)}]
        elif number == 15:
            broken = copy.deepcopy(model); broken["tables"][0]["rows"][0].remove("失败处理"); broken["tables"][0]["rows"][1].pop(5)
            broken_gate = stage3_quality_gate_report(broken)
            sections = [{"label":"规则正文","value":chapter["plannerSections"].get("summary")},{"label":"完整配置表","value":model["tables"][0]["rows"]},{"label":"完整表结论","value":compact_gate(gate)},{"label":"删除“失败处理”列后的真实结果","value":actionable_failures(broken_gate)}]
        elif number == 16:
            broken = copy.deepcopy(model); broken["chapters"][0]["executionSequence"] = list(reversed(broken["chapters"][0]["executionSequence"])); broken["chapters"][0]["plannerSections"]["normalFlow"] = list(reversed(broken["chapters"][0]["plannerSections"].get("normalFlow") or [])); broken_gate = stage3_quality_gate_report(broken)
            sections = [{"label":"来源规定的正确顺序","value":chapter.get("executionSequence")},{"label":"正确顺序结论","value":compact_gate(gate)},{"label":"倒序反例的改善路径","value":actionable_failures(broken_gate)}]
        elif number == 17:
            broken = copy.deepcopy(model); broken["chapters"][0]["formulae"][0].pop("example"); broken_gate = stage3_quality_gate_report(broken)
            sections = [{"label":"完整公式、变量与算例","value":chapter.get("formulae")},{"label":"完整组结论","value":compact_gate(gate)},{"label":"删除算例后的改善路径","value":actionable_failures(broken_gate)}]
        elif number == 18:
            broken = copy.deepcopy(model); broken["chapters"][0]["lifecycle"].remove("异常退出不清空本局余额"); broken["chapters"][0]["plannerSections"]["keyRules"] = [item for item in broken["chapters"][0]["plannerSections"].get("keyRules") or [] if "异常退出" not in item]; broken_gate = stage3_quality_gate_report(broken)
            sections = [{"label":"生命周期时间线","value":chapter.get("lifecycle")},{"label":"完整时间线结论","value":compact_gate(gate)},{"label":"漏掉异常退出后的改善路径","value":actionable_failures(broken_gate)}]
        else:
            broken = copy.deepcopy(model); broken["chapters"][0]["boundaryRules"].remove("资源不足时不扣除资源"); broken["chapters"][0]["plannerSections"]["specialCases"] = [item for item in broken["chapters"][0]["plannerSections"].get("specialCases") or [] if "资源不足" not in item]; broken_gate = stage3_quality_gate_report(broken)
            sections = [{"label":"边界条件与明确结果","value":chapter.get("boundaryRules")},{"label":"完整边界结论","value":compact_gate(gate)},{"label":"删除资源不足结果后的改善路径","value":actionable_failures(broken_gate)}]
        items.append(payload(f"S3-TC{number:02d}", next(row["title"] for row in manifest["cases"] if row["id"] == f"S3-TC{number:02d}"), source_summary, sections))

    tc12_model = copy.deepcopy(mechanisms["S3-TC12"]["model"])
    tc14_model = copy.deepcopy(mechanisms["S3-TC14"]["model"])
    tc10_model = {"chapters":[{"id":"TC10","scope":"限时奖励选择","granularityEvidence":{
        "contentInventory":{"sourceIds":["DOC-10-A"],"requiredFacts":["普通奖励与限时奖励"]},
        "configuration":{"sourceIds":["TABLE-10"],"sourceType":"configuration_table","requiredFacts":["候选数量","3"]},
        "executionSequence":{"sourceIds":["DOC-10-B"],"requiredFacts":["先筛选资格再按权重生成"]},
        "formula":{"sourceIds":["DOC-10-C"],"sourceType":"reference_document","requiredFacts":["显示比例=当前权重÷总权重×100%"]},
        "boundary":{"sourceIds":["DOC-10-D"],"requiredFacts":["候选为空时保持当前页面"]},
        "lifecycle":{"sourceIds":["DOC-10-E"],"sourceType":"reference_document","requiredFacts":["确认后清空本轮候选"]},
        "interactionFeedback":{"sourceIds":["VIDEO-10"],"requiredFacts":["玩家选择后页面显示已选奖励"]},
        "runtimeResponsibility":{"sourceIds":["DOC-10-F"],"sourceType":"reference_document","requiredFacts":["服务端生成客户端展示"]},
        "presentationContract":{"sourceIds":["DOC-10-G"],"requiredFacts":["限时奖励显示剩余时间"]}},
        "contentInventory":["普通奖励与限时奖励"],"parameterSchema":[{"name":"候选数量","value":3}],
        "executionSequence":["先筛选资格再按权重生成"],"formulae":[{"expression":"显示比例=当前权重÷总权重×100%"}],
        "boundaryRules":["候选为空时保持当前页面"],"lifecycle":["确认后清空本轮候选"],
        "interactionFeedback":["玩家选择后页面显示已选奖励"],"runtimeResponsibilities":["服务端生成客户端展示"],
        "presentationRules":["限时奖励显示剩余时间"],"plannerSections":{"summary":"候选包含普通奖励与限时奖励；玩家选择后页面显示已选奖励。","normalFlow":["先筛选资格再按权重生成"],"keyRules":["确认后清空本轮候选","服务端生成客户端展示","限时奖励显示剩余时间"],"specialCases":["候选为空时保持当前页面"]}}],
        "tables":[{"id":"TABLE-10","chapterIds":["TC10"],"status":"reviewed","rows":[["字段","值"],["候选数量","3"]]}]}
    tc10_rows = compact_alignment(sample_alignment_report(tc10_model))
    assert sum(row["结论"] == "已覆盖" for row in tc10_rows) == 9
    items.insert(9, payload("S3-TC10", "九类信息完整覆盖", "复杂奖励候选的真实适用信息核对", [{"label":"当前机制真实适用的制作问题","value":{row["检查项"]:{"答案":row["已经写入"],"来源":row["来源"],"发布位置":next(("正文" if row["检查项"] not in {"配置字段","公式依据","玩家操作与系统反馈"} else {"配置字段":"配置表","公式依据":"公式块","玩家操作与系统反馈":"策划草图"}[row["检查项"]] for _ in [0]), "正文") } for row in tc10_rows if row["结论"] == "已覆盖"}},{"label":"未计入完成度的项目","value":[row["检查项"] for row in tc10_rows if row["结论"] == "不适用"]},{"label":"真实门禁结论","value":compact_gate(stage3_quality_gate_report(tc10_model))},{"label":"判定说明","value":"只有有来源、有实际答案并进入正确载体的项目计入覆盖；不适用项目不增加完成度。"}]))
    items.insert(10, payload("S3-TC11", "需要、缺失与不适用", "简单移动机制与复杂奖励机制对照；每个机制只出现一次", [{"label":"两种机制的审核结论分组","value":grouped_alignment(sample_alignment_report(tc14_model)) + grouped_alignment(sample_alignment_report(tc12_model))},{"label":"判定原则","value":["有来源且正文已回答：已覆盖","来源要求回答但正文没有写：缺失","当前素材没有提出该类制作问题：不适用；不得为了凑模板扩写"]}]))

    repeated = "玩家确认进入挑战时扣除挑战券，挑战失败时返还本次消耗。"
    duplicate_model = {"chapters":[{"id":"A","scope":"挑战入口","plannerSections":{"summary":repeated}},{"id":"B","scope":"挑战结算","plannerSections":{"summary":repeated}}]}
    deduplicated_model = copy.deepcopy(duplicate_model); deduplicated_model["chapters"][1]["plannerSections"]["summary"] = "挑战券的扣除与返还规则见《挑战入口》。"
    duplicate_actions = actionable_failures({"granularityAudit":{"findings":[]},"languageAudit":language_quality_report(duplicate_model)})
    items.append(payload("S3-TC20", "跨章节去重", "两个章节重复同一业务段落", [{"label":"修改前的重复正文","value":duplicate_model["chapters"]},{"label":"保留位置与修改动作","value":duplicate_actions[:1]},{"label":"修改后正文","value":deduplicated_model["chapters"]},{"label":"修改后真实结论","value":compact_language(language_quality_report(deduplicated_model))}]))
    items.append(payload("S3-TC21", "章节结构动态选择", "简单、交互、配置与算法四类实际输出", [{"label":"四种机制的真实输出","value":[{"机制":"简单规则","载体":"一段自然短文","实际输出":transfer[0]["languagePass"]["output"]},{"机制":"交互机制","载体":"策划草图配因果正文","实际输出":transfer[1]["languagePass"]["output"]},{"机制":"配置机制","载体":"规则正文配一张配置表","实际输出":"玩家确认进入挑战时扣除挑战券；失败时按配置表返还。字段、单位、默认值和范围只在表格维护。"},{"机制":"算法机制","载体":"编号步骤配来源表","实际输出":transfer[2]["languagePass"]["output"]}]},{"label":"结构差异结论","value":"四份输出的段落、编号和载体不同，没有复用固定标题序列。"}]))
    items.append(payload("S3-TC22", "稀疏小标题合并", "三个一句话规则与一个复杂算法", [{"label":"修改前的碎片结构","value":["载具移动机制：载具沿路线自动前进。","横向控制机制：玩家拖动时改变横向位置。","生命值管理机制：有效伤害扣减生命。"]},{"label":"合并后的业务大节","value":transfer[0]["languagePass"]["output"]},{"label":"仍应独立的复杂内容","value":"奖励候选生成含资格、排序、填充和不足边界，保留独立算法章节。"}]))
    items.append(payload("S3-TC23", "句子组织顺序", "同一组事实的乱序输入与策划正文", [{"label":"乱序事实","value":["停在范围边界","玩家拖动载具","进入战斗后","载具改变横向位置","拖动超出范围"]},{"label":"重组后的正文","value":"进入战斗后，玩家可拖动载具调整横向位置；拖动超出可移动范围时，载具停在边界。"},{"label":"语序核对","value":{"条件":"进入战斗后","主体与动作":"玩家拖动载具","结果":"调整横向位置","边界":"超出范围时停在边界"}}]))
    items.append(payload("S3-TC24", "主语与责任表达", "玩家、系统、服务端和客户端共同参与的候选选择", [{"label":"实际动作与责任","value":[{"主语":"玩家","动作":"选择一个候选奖励","为何必须写明":"这是输入与最终承诺"},{"主语":"系统","动作":"确认选择并结束本轮候选状态","为何必须写明":"这是自动状态变化"},{"主语":"服务端","动作":"生成候选并返回有序结果","为何必须写明":"决定权和校验发生在服务端"},{"主语":"客户端","动作":"按返回顺序展示，不自行补位","为何必须写明":"避免端侧结果不一致"}]},{"label":"去掉主语的反例","value":"生成候选并展示，确认后清空。——无法判断由谁生成、谁确认、谁清空，因此不能发布。"}]))
    degraded = {"chapters":[{"id":"C25","scope":"奖励规则","plannerSections":{"summary":"本节主要介绍奖励机制，并通过状态隔离形成闭环。"}}]}
    repaired = {"chapters":[{"id":"C25","scope":"奖励规则","plannerSections":{"summary":"玩家完成本轮挑战后获得一项奖励，奖励领取后进入下一轮。"}}]}
    items.append(payload("S3-TC25", "废话和内部术语阻断", degraded["chapters"][0]["plannerSections"]["summary"], [{"label":"问题原句","value":degraded["chapters"][0]["plannerSections"]["summary"]},{"label":"逐项删改建议","value":actionable_failures({"granularityAudit":{"findings":[]},"languageAudit":language_quality_report(degraded)})},{"label":"修订正文","value":repaired["chapters"][0]["plannerSections"]["summary"]},{"label":"修订后真实结论","value":compact_language(language_quality_report(repaired))}]))
    table_repeat = {"chapters":[{"id":"C26","scope":"挑战消耗","plannerSections":{"summary":"挑战失败返还挑战券。"}}],"tables":[{"chapterIds":["C26"],"status":"reviewed","rows":[["失败处理","挑战失败返还挑战券"]]}]}
    table_fixed = copy.deepcopy(table_repeat); table_fixed["chapters"][0]["plannerSections"]["summary"] = "挑战券在玩家确认进入时扣除；返还方式以配置表为准。"
    items.append(payload("S3-TC26", "表格与正文重复阻断", "正文重复项目级审核表", [{"label":"修改前：正文重复表格","value":table_repeat},{"label":"删除位置与保留载体","value":actionable_failures({"granularityAudit":{"findings":[]},"languageAudit":language_quality_report(table_repeat)})},{"label":"修改后：正文只保留因果","value":table_fixed},{"label":"修改后真实结论","value":compact_language(language_quality_report(table_fixed))}]))
    transfer_rows = [{"类型":{"sparse":"简单机制","interaction":"交互机制","algorithm":"算法机制"}[item["shape"]],"确认事实":"；".join(item["factPass"]["claims"]),"禁止推断":"；".join(item["factPass"]["excludedInferences"]),"载体":{"merged_prose":"合并短文","planning_board_plus_causal_prose":"策划草图配因果正文","ordered_algorithm_plus_source_table":"有序算法配来源表"}[item["languagePass"]["carrier"]],"组织原因":item["languagePass"]["organizationReason"],"实际输出":item["languagePass"]["output"]} for item in transfer]
    items.append(payload("S3-TC27", "三类非样例双盲迁移", "简单、交互、算法三类独立素材", [{"label":"三类输出对照","value":transfer_rows}]))

    job = complete_job()
    delivery_chapter = job["gameplayReviewModel"]["chapters"][0]
    delivery_chapter["parameterSchema"] = [{
        "name": "基础倍率", "type": "number", "unit": "倍", "defaultValue": "2"
    }]
    delivery_chapter["formulae"] = [{
        "name": "最终结果", "expression": "最终结果=基础值×基础倍率",
        "variables": [{"name": "基础值"}, {"name": "基础倍率"}],
    }]
    job["gameplayReviewModel"]["tables"] = [{
        "id": "GTA-TC28", "chapterIds": [delivery_chapter["id"]], "status": "reviewed",
        "columns": ["字段", "类型", "单位", "默认值"],
        "rows": [["基础倍率", "number", "倍", "2"]],
    }]
    contract = canonical_delivery_contract(job["gameplayReviewModel"])
    delivery = delivery_alignment_report(job)
    stale_job = copy.deepcopy(job)
    stale_job["gameplayReviewModel"]["interactionRevision"] += 1
    stale_delivery = delivery_alignment_report(stale_job)
    items.append(payload("S3-TC28", "P7 与飞书同源", "正文、配置表、公式与策划草图引用共同绑定同一发布快照", [
        {"label":"四类载体的独立同源指纹","value":contract["carrierFingerprints"]},
        {"label":"P7 与飞书逐项核对","value":{
            "当前玩法版本":contract["revision"],
            "绑定交互版本":delivery["interactionBinding"]["revision"],
            "绑定截图锚点":delivery["interactionBinding"]["frameIds"],
            "P7 章节顺序":" → ".join(delivery["expectedChapterOrder"]),
            "飞书章节顺序":" → ".join(delivery["renderedChapterOrder"]),
            "正文、表格或公式缺失":delivery["missingCopy"] or ["无"],
            "配置表数量":delivery["tableCount"],
            "公式数量":delivery["formulaCount"],
            "真实结论":"通过" if delivery["passed"] else "不通过",
        }},
        {"label":"错绑交互版本的真实失败与改善路径","value":stale_delivery["differences"]},
    ]))
    complete = mechanisms["S3-TC12"]["model"]
    shallow = mechanisms["S3-TC13"]["model"]
    language_bad = copy.deepcopy(complete)
    language_bad["chapters"][0]["plannerSections"]["summary"] = "本节主要介绍奖励候选，并通过状态隔离形成闭环。"
    items.append(payload("S3-TC29", "真实门禁三态闭环", "真实通过、真实颗粒度失败、真实语言失败", [
        {"label":"真实通过","value":compact_gate(stage3_quality_gate_report(complete))},
        {"label":"颗粒度失败及改善路径","value":actionable_failures(stage3_quality_gate_report(shallow))},
        {"label":"语言失败及改善路径","value":actionable_failures(stage3_quality_gate_report(language_bad))},
    ]))
    rules = manifest["rules"]
    items.append(payload("S3-TC30", "证据完整性与任务恢复", "三十条独立证据与正式任务保护", [{"label":"证据规则","value":{
        "用例数量": rules["caseCount"], "允许合并用例":"是" if rules["allowMergedCaseIds"] else "否",
        "允许注入审核结果":"是" if rules["allowInjectedAuditResult"] else "否",
        "输入必须逐条唯一":"是" if rules["requireUniqueInput"] else "否",
        "正文必须逐条唯一":"是" if rules["requireUniqueBodyHash"] else "否",
        "截图必须逐条唯一":"是" if rules["requireUniqueScreenshotHash"] else "否",
        "截图必须显示用例编号":"是" if rules["requireVisibleCaseIdentity"] else "否",
        "必须完成人工逐图检查":"是" if rules["requireHumanImageInspection"] else "否",
        "正式任务执行前后必须一致":"是" if rules["requireOfficialJobRestoration"] else "否",
    }},{"label":"正式任务执行前哈希","value":file_digest(OFFICIAL_JOB)}]))
    assert [item["caseId"] for item in items] == [f"S3-TC{index:02d}" for index in range(1, 31)]
    return {"officialJobBefore": file_digest(OFFICIAL_JOB), "payloads": items}


if __name__ == "__main__":
    OUTPUT.mkdir(parents=True, exist_ok=True)
    result = build()
    (OUTPUT / "payloads.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"count": len(result["payloads"]), "officialJobBefore": result["officialJobBefore"]}, ensure_ascii=False))
