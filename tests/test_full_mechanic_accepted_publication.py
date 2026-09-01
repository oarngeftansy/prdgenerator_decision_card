from __future__ import annotations

import json
import re
from pathlib import Path

from scripts.generate_full_mechanic_accepted_publication import main


def test_accepted_review_rules_close_requirements_and_enter_real_chains(tmp_path: Path):
    main(output_dir=tmp_path)
    closure = json.loads((tmp_path / "requirement-closure.json").read_text(encoding="utf-8"))
    chains = json.loads((tmp_path / "gameplay-rule-chains.json").read_text(encoding="utf-8"))
    integrity = json.loads((tmp_path / "publication-integrity.json").read_text(encoding="utf-8"))
    assert closure["resolvedRequirementCount"] == 20
    assert closure["manualStatusMutationCount"] == 0
    assert integrity["acceptedRuleCount"] == 14
    assert integrity["publishedNewRuleCount"] == 10
    assert integrity["reusedExistingRuleCount"] == 4
    assert integrity["unpublishedAcceptedRuleIds"] == []
    chain_rule_ids = {rule_id for chain in chains for rule_id in chain.get("supportingRuleIds", [])}
    assert set(integrity["effectiveAcceptedRuleIds"]) <= chain_rule_ids


def test_final_publication_contains_only_approved_logic_and_sketch_owns_presentation(tmp_path: Path):
    main(output_dir=tmp_path)
    markdown = (tmp_path / "human-planning-preview.md").read_text(encoding="utf-8")
    sketch = (tmp_path / "planning-sketch.md").read_text(encoding="utf-8")
    integrity = json.loads((tmp_path / "publication-integrity.json").read_text(encoding="utf-8"))
    assert markdown.startswith("# 一路狂飙·执行策划案\n\n## 玩法概述")
    assert "| 概述项 | 内容 |" in markdown
    assert "| 玩家目标 | 在载具生命值归零前击败首领，并清空场上剩余普通怪物。 |" in markdown
    assert "| 基础操作 | 战斗阶段无需手动瞄准；成长阶段选择强化" in markdown
    assert "| 核心循环 | 进入战斗 → 自动攻击与击败怪物 → 关卡内成长" in markdown
    assert "| 成长与资源 | 击败怪物获得战斗经验" in markdown
    assert "| 怎样获胜 | 击败首领，并在随后清空场上剩余普通怪物。 |" in markdown
    assert "| 怎样失败 | 任一战斗阶段中载具生命值归零。 |" in markdown
    assert "### 核心循环与页面流转" not in markdown
    assert "### 成长与构筑" not in markdown
    assert "### 胜负与结算\n\n首领生命归零" not in markdown
    assert markdown.index("## 玩法概述") < markdown.index("## 载具")
    assert markdown.count("<!-- EMBED:BOARD:planning -->") == 1
    assert "<!-- EMBED:BOARD:ue -->" not in markdown
    assert "<!-- EMBED:BOARD:competitor -->" not in markdown
    assert "筛选当前可生效内容。" in markdown
    assert "从筛选结果中生成3项互不重复的候选。" in markdown
    assert "多个怪物接触载具时，分别计算攻击间隔和伤害。" in markdown
    assert "碰撞边缘距离不大于0.5世界单位时成立接触" in markdown
    assert "碰撞边缘距离大于0.75世界单位时成立脱离" in markdown
    assert "怪物停止移动并立即造成首次伤害" in markdown
    assert markdown.count("\n#### 战斗等级\n") == 1
    assert markdown.count("\n#### 三选一\n") == 1
    assert markdown.count("\n### 获取\n") == 1
    assert markdown.count("\n### 武器栏\n") == 1
    assert markdown.count("### 普通怪物") == 1
    assert "### 怪物行为" not in markdown
    assert "点击空白处可跳过抽取动画。" not in markdown
    assert "点击空白处可跳过抽取动画。" in sketch
    assert "敌人受击时显示伤害数字。" in sketch
    assert "界面显示本局剩余刷新次数和刷新入口。" in sketch
    assert "滚动区域停止后，高亮显示本次抽取的结果行。" in sketch
    assert "首领来袭提示使用警示图标和红色遮罩。" in sketch
    assert "结算页显示挑战结果、通关时间、获得道具和武器伤害统计。" in sketch
    assert "伤害统计包含各武器伤害占比、秒伤和本局总伤害。" in sketch
    assert sketch.count("\n## 三选一\n") == 1
    assert sketch.count("\n## 怪物\n") == 1
    assert sketch.count("\n## 结算\n") == 1
    assert integrity["reviewLanguageTerms"] == []
    assert integrity["internalIdTerms"] == []
    assert integrity["duplicatePublishedRuleCount"] == 0
    assert integrity["logicPresentationPollutionCount"] == 0


def test_necessary_diagram_markdown_preserves_real_branches(tmp_path: Path):
    main(output_dir=tmp_path)
    diagrams = (tmp_path / "necessary-diagrams.md").read_text(encoding="utf-8")
    assert "普通战斗 → 首领来袭 → 首领战斗 → 关卡完成 → 成功结算 → 载具生命归零" not in diagrams
    assert "首领战斗 --Boss生命归零--> 清理场上剩余怪物" in diagrams
    assert "清理场上剩余怪物 --剩余怪物清空--> 关卡完成" in diagrams
    assert "首领战斗 → 载具生命归零" in diagrams
    assert "清理场上剩余怪物 → 载具生命归零" in diagrams
    assert "载具生命归零 → 失败结算" in diagrams


def test_publication_integrity_hashes_written_file_bytes(tmp_path: Path):
    import hashlib

    main(output_dir=tmp_path)
    integrity = json.loads((tmp_path / "publication-integrity.json").read_text(encoding="utf-8"))
    expected = hashlib.sha256((tmp_path / "human-planning-preview.md").read_bytes()).hexdigest().upper()
    assert integrity["sha256"] == expected
    score = json.loads((tmp_path / "gve16-alignment-score.json").read_text(encoding="utf-8"))
    assert score["markdownSha256"] == expected


def test_publication_changes_the_formal_markdown_and_emits_gve16_score(tmp_path: Path):
    main(output_dir=tmp_path)
    integrity = json.loads((tmp_path / "publication-integrity.json").read_text(encoding="utf-8"))
    benchmark = json.loads((tmp_path / "gve16-alignment-score.json").read_text(encoding="utf-8"))
    assert integrity["sha256"] != integrity["baselineSha256"]
    assert set(benchmark["scores"]) == set("ABCDEFGHIJ")
    assert benchmark["coreAH"] >= 64.5
    assert benchmark["scores"]["I"] >= 90
    assert benchmark["scores"]["J"] >= 95


def test_alignment_crosswalk_uses_the_same_linear_chapter_owners_as_final(tmp_path: Path):
    main(output_dir=tmp_path)
    benchmark = json.loads((tmp_path / "gve16-alignment-score.json").read_text(encoding="utf-8"))
    report = (tmp_path / "gve16-alignment-report.md").read_text(encoding="utf-8")
    chapters = [item["chapter"] for item in benchmark["chapterAlignment"]]
    assert chapters == [
        "单局流程",
        "武器",
        "怪物 / 普通怪物",
        "怪物 / 首领",
        "战斗规则 / 战斗计算",
        "关卡规则 / 内部逻辑",
        "关卡规则 / 战斗统计",
        "关卡规则 / 关卡结算",
    ]
    assert "核心战斗 / 武器" not in chapters
    assert "局内成长 / 三选一" not in chapters
    assert "关卡推进与关卡结束" not in chapters
    assert report.count("仍有差距：") == 2


def test_final_editorial_pass_unifies_level_lifecycle_and_exposes_real_calculations(tmp_path: Path):
    main(output_dir=tmp_path)
    markdown = (tmp_path / "human-planning-preview.md").read_text(encoding="utf-8")
    for heading in ("单局流程", "关卡规则", "战斗规则"):
        assert markdown.count(f"\n## {heading}\n") == 1
    assert "\n### 内部逻辑\n" in markdown
    assert "\n### 外部逻辑\n" in markdown
    assert "\n## 关卡推进\n" not in markdown
    assert "\n## 关卡结束\n" not in markdown
    assert "候选生成按以下顺序执行" in markdown
    assert "筛选当前可生效内容" in markdown
    assert "本局总伤害 = Σ 各武器累计伤害" in markdown
    assert "武器伤害占比 = 该武器累计伤害 ÷ 本局总伤害" in markdown
    assert "场上剩余怪物清空后结束战斗，并进入成功结算。" in markdown
    assert "关卡进入首领战斗阶段。" not in markdown
    assert "关卡内使用独立的战斗等级和升级进度。" not in markdown


def test_final_heading_tree_matches_gve16_atomic_owner_grammar(tmp_path: Path):
    main(output_dir=tmp_path)
    markdown = (tmp_path / "human-planning-preview.md").read_text(encoding="utf-8")
    h2 = re.findall(r"^## (.+)$", markdown, flags=re.M)
    assert h2 == ["玩法概述", "策划草图", "单局流程", "载具", "武器", "怪物", "战斗规则", "关卡规则", "附录"]
    forbidden = {
        "战斗定位与失败职责", "获取与栏位处理", "目标筛选与重选", "攻击方式与周期",
        "词条与解锁", "目标与接近", "接触、伤害与脱离", "死亡、暂停与恢复",
        "进入条件与初始化", "击败与残敌清理", "战斗等级与三选一",
        "统计窗口与归属", "聚合、占比与秒伤", "排序与展示尺度",
        "冻结、读取与重置", "挑战消耗与奖励", "胜负与结算",
    }
    headings = set(re.findall(r"^#{2,5} (.+)$", markdown, flags=re.M))
    assert headings.isdisjoint(forbidden)
    assert markdown.index("### 普通怪物") < markdown.index("### 首领")
    assert markdown.index("### 内部逻辑") < markdown.index("### 外部逻辑")
    assert markdown.index("#### 关卡流程") < markdown.index("#### 战斗等级")
    assert markdown.index("#### 战斗等级") < markdown.index("#### 三选一") < markdown.index("#### 独立抽取")
    assert markdown.index("#### 独立抽取") < markdown.index("#### 战斗统计") < markdown.index("#### 胜负判定") < markdown.index("#### 关卡结算")


def test_final_body_crosswalk_prints_every_actual_body_line_with_first_party_owner(tmp_path: Path):
    main(output_dir=tmp_path)
    crosswalk = json.loads((tmp_path / "final-body-gve16-line-crosswalk.json").read_text(encoding="utf-8"))
    report = (tmp_path / "final-body-gve16-line-crosswalk.md").read_text(encoding="utf-8")
    assert crosswalk["lines"]
    assert all(item["renderedFinalText"] and item["ownerPath"] for item in crosswalk["lines"])
    assert all(item["gve16ResponsibilityReference"] != "未映射" for item in crosswalk["lines"])
    assert any(item["renderedFinalText"].startswith("- 武器自动攻击射程内") for item in crosswalk["lines"])
    assert "最终实际文字" in report


def test_final_editorial_pass_does_not_invent_unapproved_boss_or_parameter_answers(tmp_path: Path):
    main(output_dir=tmp_path)
    markdown = (tmp_path / "human-planning-preview.md").read_text(encoding="utf-8")
    assert "Boss死亡后立即结算" not in markdown
    assert "清理全部残敌后判定成功" not in markdown
    assert "攻击间隔：" not in markdown


def test_approved_dps_contract_reaches_final(tmp_path: Path):
    main(output_dir=tmp_path)
    markdown = (tmp_path / "human-planning-preview.md").read_text(encoding="utf-8")
    assert "武器秒伤 = 该武器累计伤害 ÷ 该武器有效战斗秒数" in markdown
    assert "排除选择、抽取和结算暂停时间" in markdown


def test_monster_pause_and_resume_relation_is_projected_in_final_and_p5(tmp_path: Path):
    main(output_dir=tmp_path)

    markdown = (tmp_path / "human-planning-preview.md").read_text(encoding="utf-8")
    diagrams = json.loads((tmp_path / "necessary-diagrams.json").read_text(encoding="utf-8"))

    assert "选择或抽取结束并恢复战斗后，仍存活的怪物恢复移动和攻击。" in markdown
    monster = next(item for item in diagrams["diagrams"] if item["diagramId"] == "P5-MONSTER-STATE")
    assert "选择或抽取：暂停移动和攻击" in monster["nodes"]
    assert "恢复战斗：仍存活怪物恢复移动和攻击" in monster["nodes"]
    assert "武器秒伤 = 该武器累计伤害 ÷ 该武器有效战斗秒数" in markdown
    assert "实时刷新秒伤" not in markdown
    assert "{x}" not in markdown


def test_algorithm_and_parameter_contracts_use_only_approved_values(tmp_path: Path):
    main(output_dir=tmp_path)
    markdown = (tmp_path / "human-planning-preview.md").read_text(encoding="utf-8")
    p6 = json.loads((tmp_path / "p6-review-tables.json").read_text(encoding="utf-8"))
    benchmark = json.loads((tmp_path / "gve16-alignment-score.json").read_text(encoding="utf-8"))
    rows_by_table = {table["id"]: table["publicationRows"] for table in p6["tables"]}
    assert "武器结果按以下分支处理：" in markdown
    assert "| 新武器 | 栏位已满 | 由玩家选择要替换的武器 |" in markdown
    assert ["候选数量", "每轮三选一可生成的候选上限", "3", "项/轮", "单次候选生成", "筛选后等概率无放回抽取", "当前执行规则"] in rows_by_table["P6-CHOICE"]
    assert ["刷新消耗", "每次重新生成全部候选的次数消耗", "1", "次/次", "单次刷新", "刷新操作成功时扣除", "当前执行规则"] in rows_by_table["P6-CHOICE"]
    assert ["抽取结果数量", "每次独立抽取预先确定的结果数", "3", "项/次", "单次抽取", "结果生成与展示", "抽取画面与当前规则"] in rows_by_table["P6-DRAW"]
    assert ["火焰扩张·范围修正", "扩大火焰喷射覆盖范围", "+30", "%", "本局对应武器", "生成攻击范围时叠加", "局内词条画面"] in rows_by_table["P6-WEAPON-TRAITS"]
    assert ["多点爆炸·次数修正", "增加火焰爆炸的触发次数", "+100", "%", "本局对应武器", "生成爆炸次数时叠加", "局内词条画面"] in rows_by_table["P6-WEAPON-TRAITS"]
    assert ["多点爆炸·伤害修正", "调整多次爆炸的单次伤害", "-20", "%", "本局对应武器", "伤害结算时叠加", "局内词条画面"] in rows_by_table["P6-WEAPON-TRAITS"]
    assert ["抽取权重", "合格内容在当前项目中的抽取机会", "等概率", "—", "单次抽取", "过滤后结果生成", "当前执行规则"] in rows_by_table["P6-DRAW"]
    assert "候选权重待确认" not in markdown
    assert "攻击间隔数值" not in markdown
    assert benchmark["scores"]["F"] >= 74
    assert benchmark["scores"]["G"] >= 76


def test_final_and_delivery_carriers_use_natural_project_owners(tmp_path: Path):
    main(output_dir=tmp_path)
    markdown = (tmp_path / "human-planning-preview.md").read_text(encoding="utf-8")
    diagrams = json.loads((tmp_path / "necessary-diagrams.json").read_text(encoding="utf-8"))["diagrams"]
    tables = json.loads((tmp_path / "publication-tables.json").read_text(encoding="utf-8"))["tables"]
    for heading in (
        "## 单局流程", "## 载具", "## 武器", "## 怪物",
        "## 关卡规则", "## 战斗规则",
    ):
        assert heading in markdown
    assert markdown.index("## 单局流程") < markdown.index("## 载具")
    assert markdown.index("## 载具") < markdown.index("## 武器") < markdown.index("## 怪物")
    assert markdown.index("## 怪物") < markdown.index("## 战斗规则") < markdown.index("## 关卡规则")
    assert "### 普通怪物" in markdown and "### 首领" in markdown
    assert "### 内部逻辑" in markdown
    assert markdown.index("### 普通怪物") < markdown.index("### 首领")
    assert "首领被击败不等于关卡立即完成" in markdown
    assert "转场结束后生成首领" in markdown
    assert "生命值初始化为该首领的生命上限" in markdown
    assert "首领以载具为唯一攻击目标" in markdown
    assert "首领与尚未死亡的普通怪物共同进入武器的合法目标集合" in markdown
    assert "接近、接触成立、首次伤害、周期攻击与脱离重追" in markdown
    assert "首领受到武器伤害时，沿用战斗规则中的统一伤害公式" in markdown
    assert "首领生命值归零与载具生命值归零在同一结算步成立时，失败判定优先" in markdown
    assert "重新挑战会清除上一局首领实例、生命值、目标引用和阶段状态" in markdown
    assert "## 核心战斗" not in markdown
    assert "## 局内成长" not in markdown
    assert diagrams[0]["ownerPath"] == ["武器", "获取"]
    assert all(path[0] != "局内成长" for path in [item["ownerPath"] for item in diagrams + tables])


def test_delivery_index_and_primary_owner_references_are_stable_and_human_readable(tmp_path: Path):
    main(output_dir=tmp_path)
    markdown = (tmp_path / "human-planning-preview.md").read_text(encoding="utf-8")
    references = json.loads((tmp_path / "cross-delivery-references.json").read_text(encoding="utf-8"))
    assert "### 交付索引" in markdown
    assert "| 武器 | 武器获取、选敌与伤害流程 | 武器词条配置、武器与接触战斗配置 |" in markdown
    assert "| 关卡规则 | 升级选择、独立抽取、阶段胜负与奖励流程 | 三选一配置、独立抽取配置、关卡与奖励配置 |" in markdown
    assert "| 战斗规则 | 伤害统计数据流 | 伤害统计配置 |" in markdown
    draw_reference = next(item for item in references["references"] if item["consumer"] == "关卡规则/内部逻辑/独立抽取")
    assert draw_reference == {
        "consumer": "关卡规则/内部逻辑/独立抽取",
        "primaryOwner": "武器/获取",
        "relation": "抽取结果按武器获取、升级或替换规则处理",
    }
    assert "RULE-" not in markdown


def test_final_body_anchors_every_reviewed_diagram_and_parameter_table_once(tmp_path: Path):
    main(output_dir=tmp_path)
    markdown = (tmp_path / "human-planning-preview.md").read_text(encoding="utf-8")
    p5 = json.loads((tmp_path / "p5-review-diagrams.json").read_text(encoding="utf-8"))["diagrams"]
    p6 = json.loads((tmp_path / "p6-review-tables.json").read_text(encoding="utf-8"))["tables"]

    for diagram in p5:
        assert markdown.count(f"<!-- EMBED:P5:{diagram['id']} -->") == 1
    for table in p6:
        assert markdown.count(f"<!-- EMBED:P6:{table['id']} -->") == 1
    assert "#### 获取来源" not in markdown
    assert "#### 参数配置" not in markdown


def test_p6_projects_review_and_source_state_per_parameter_row(tmp_path: Path):
    main(output_dir=tmp_path)
    tables = json.loads((tmp_path / "publication-tables.json").read_text(encoding="utf-8"))["tables"]
    assert sum(len(table["rows"]) for table in tables) == 43
    for table in tables:
        assert table["reviewStatus"] == "approved"
        assert len(table["rows"]) == table["rowCount"]
        for row in table["rows"]:
            assert row["reviewStatus"] == "approved"
            assert row["sourceStatus"] == "approved_observed_or_design_value"
            assert row["parameter"]


def test_generator_emits_review_ui_compatible_p6_sidecar(tmp_path: Path):
    main(output_dir=tmp_path)
    payload = json.loads((tmp_path / "p6-review-tables.json").read_text(encoding="utf-8"))
    assert payload["schemaVersion"] == "p6-review-tables-v1"
    assert [table["id"] for table in payload["tables"]] == ["P6-WEAPON-TRAITS", "P6-COMBAT", "P6-DAMAGE-STATS", "P6-LEVEL-REWARD", "P6-CHOICE", "P6-DRAW"]
    for table in payload["tables"]:
        assert table["status"] == "reviewed"
        assert table["chapterIds"]
        assert table["columns"][4] == "状态"
        assert all(row[4] == "已确认" for row in table["rows"])
        assert table["publicationColumns"] == ["参数", "含义", "当前值", "单位", "作用域", "消费规则", "来源"]
        assert len(table["publicationRows"]) == len(table["rows"])
        assert all(len(row) == 7 and all(str(cell).strip() for cell in row) for row in table["publicationRows"])
        assert all(row[1] != "已批准参数职责" for row in table["rows"])


def test_p6_source_contract_names_the_external_source_needed_to_bind_fields(tmp_path: Path):
    main(output_dir=tmp_path)
    payload = json.loads((tmp_path / "p6-source-contract.json").read_text(encoding="utf-8"))
    assert payload["schemaVersion"] == "p6-source-contract-v1"
    assert {item["auditId"] for item in payload["blockedItems"]} == {"W-18", "P6-06"}
    for item in payload["blockedItems"]:
        assert item["missingSource"]
        assert item["resolutionAction"]
        assert item["sourceTable"] is None
        assert item["sourceField"] is None


def test_commercial_decision_contract_contains_a_mature_double_reward_recommendation(tmp_path: Path):
    main(output_dir=tmp_path)
    payload = json.loads((tmp_path / "commercial-decision-contract.json").read_text(encoding="utf-8"))
    item = payload["blockedItems"][0]
    assert item["auditId"] == "L-13"
    assert item["observedSignal"]
    assert item["recommendedDesign"]
    assert item["missingSource"]
    assert item["resolutionAction"]


def test_alignment_closure_review_accepts_choice_and_draw_designs_and_projects_them(tmp_path: Path):
    main(output_dir=tmp_path)
    review = json.loads((tmp_path / "alignment-closure-review.json").read_text(encoding="utf-8"))
    markdown = (tmp_path / "human-planning-preview.md").read_text(encoding="utf-8")
    sketch = (tmp_path / "planning-sketch.md").read_text(encoding="utf-8")
    diagrams = json.loads((tmp_path / "necessary-diagrams.json").read_text(encoding="utf-8"))["diagrams"]

    assert review["reviewAction"] == "accept_recommended_designs"
    closed_ids = {audit_id for item in review["decisions"] for audit_id in item["auditIds"]}
    assert {"C-01", "C-20", "D-06", "D-14", "W-07", "M-04", "S-09", "S-16", "L-01", "L-17", "PR-19"} <= closed_ids
    assert "每局从战斗等级1级、0经验开始" in markdown
    assert "3项结果全部获得" in markdown
    assert "基础伤害 ×（1 + 同武器伤害修正之和）" in markdown
    assert "伤害条长度以本局最高武器累计伤害为100%归一化" in markdown
    assert "成功结算发放100基础货币" in markdown
    assert "失败页使用“挑战失败”标题" in sketch
    assert "跳过动画不会改变结果" in sketch
    choice = next(item for item in diagrams if item["diagramId"] == "P5-CHOICE-FLOW")
    assert "还有待处理等级" in choice["nodes"]
    assert "独立抽取：预先确定3项且全部获得" in choice["nodes"]


def test_alignment_review_produces_stable_approved_rules_consumed_by_chains_and_assembly(tmp_path: Path):
    main(output_dir=tmp_path)
    approved = json.loads((tmp_path / "approved-alignment-rules.json").read_text(encoding="utf-8"))
    chains = json.loads((tmp_path / "gameplay-rule-chains.json").read_text(encoding="utf-8"))
    assembly = json.loads((tmp_path / "chapter-assembly-result.json").read_text(encoding="utf-8"))

    assert approved["ruleCount"] == 29
    assert approved["allFinalProjectionsSatisfied"] is True
    approved_ids = {rule["approvedRuleId"] for rule in approved["rules"]}
    assert all(rule["decisionId"].startswith("DEC-ALIGN-") for rule in approved["rules"])
    assert all(rule["renderedFinalText"] and rule["semanticSatisfaction"] for rule in approved["rules"])
    assert all(rule["chapterOwner"] and rule["ruleGroup"] and rule["assemblyInput"] for rule in approved["rules"])
    boss_rule = next(rule for rule in approved["rules"] if "L-02" in rule["auditIds"])
    assert boss_rule["auditIds"] == ["L-02", "L-03", "L-04", "L-05", "L-06", "L-07", "L-08"]
    assert boss_rule["chapterOwner"] == "怪物"
    assert boss_rule["ruleGroup"] == "首领"
    assert boss_rule["chainType"] == "boss_encounter_lifecycle"
    assert boss_rule["requiredCarriers"] == ["Final", "P5", "UE", "PlanningSketch"]
    boss_rendered = "\n".join(boss_rule["renderedFinalText"])
    assert "首领以载具为唯一攻击目标" in boss_rendered
    assert "失败判定优先" in boss_rendered
    chain_ids = {rule_id for chain in chains for rule_id in chain.get("approvedAlignmentRuleIds", [])}
    assert chain_ids == approved_ids
    assert set(assembly["approvedAlignmentRuleIds"]) == approved_ids
    assert assembly["sourceOfTruth"] == "approved_structured_rules"
    assert assembly["fallbackSectionCount"] == 0
    assert assembly["llmRegeneratedSectionCount"] == 0


def test_generator_emits_review_ui_compatible_p5_sidecar(tmp_path: Path):
    main(output_dir=tmp_path)
    payload = json.loads((tmp_path / "p5-review-diagrams.json").read_text(encoding="utf-8"))
    assert payload["schemaVersion"] == "p5-review-diagrams-v1"
    assert len(payload["diagrams"]) == 5
    for diagram in payload["diagrams"]:
        svg = diagram["svg"]
        assert diagram["status"] == "reviewed"
        assert len(re.findall(r'<path id="edge-', svg)) == len(diagram["edges"])
        assert len(re.findall(r'<polygon id="arrow-', svg)) == len(diagram["edges"])
        assert svg.count('class="edge-label"') == sum(bool(edge["label"]) for edge in diagram["edges"])
        x_values = set(re.findall(r'<rect x="([\d.]+)" y="[\d.]+" width="190"', svg))
        y_values = set(re.findall(r'<rect x="[\d.]+" y="([\d.]+)" width="190"', svg))
        assert len(x_values) > 1, f"{diagram['id']} collapsed into a vertical explanation stack"
        assert len(y_values) > 1, f"{diagram['id']} lost branch/return lanes"
        branching_nodes = {
            edge["from"] for edge in diagram["edges"]
            if sum(candidate["from"] == edge["from"] for candidate in diagram["edges"]) > 1
        }
        if branching_nodes:
            assert '>分支</text>' in svg
