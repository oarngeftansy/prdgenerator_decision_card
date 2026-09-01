from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "feishu-gameplay-prd-reconstruction"


def test_skill_requires_sample_depth_without_fixed_gameplay_directory():
    text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    for required in (
        "内容清单",
        "配置字段",
        "执行顺序",
        "公式",
        "异常边界",
        "生命周期",
        "不得固定套用",
    ):
        assert required in text


def test_granularity_contract_covers_visible_and_hidden_evidence_roles():
    text = (SKILL_ROOT / "references" / "granularity-contract.md").read_text(encoding="utf-8")
    for required in (
        "玩法概述",
        "玩家目标",
        "基础操作",
        "核心循环",
        "胜败条件",
        "配置表名",
        "字段名",
        "取整",
        "退出重进",
    ):
        assert required in text


def test_quality_gate_rejects_shallow_catalog_and_unsupported_precision():
    text = (SKILL_ROOT / "references" / "quality-gates.md").read_text(encoding="utf-8")
    for required in (
        "存在多种",
        "逐项内容清单",
        "无依据的精确数值",
        "配置表名",
        "字段名",
        "同一机制的规则、参数、公式和验收彼此矛盾",
    ):
        assert required in text


def test_competitor_reference_has_explicit_optional_states():
    text = (ROOT / "skills" / "gve16-feishu-whiteboard" / "SKILL.md").read_text(encoding="utf-8")
    assert "本次未提供" in text
    assert "不影响导出" in text
    assert "待补充" not in text


def test_skill_teaches_sample_aligned_parameter_carrier_selection():
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    contract = (SKILL_ROOT / "references" / "granularity-contract.md").read_text(encoding="utf-8")
    knowledge = (ROOT / "docs" / "research" / "feishu-sample-language-and-content-grammar-2026-08-11.md").read_text(encoding="utf-8")
    combined = "\n".join((skill, contract, knowledge))
    for required in (
        "行为正文",
        "就近命名映射",
        "业务名 → 配置表/字段名",
        "建议程序字段名（待程序/配置表确认）",
        "配置表集中承载值、单位、范围",
        "生命周期紧跟机制结尾",
        "不得用集中字段字典总表替代",
    ):
        assert required in combined


def test_skill_preserves_stage5_incident_boundaries():
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    for required in (
        "Attribute completeness must be visible in the gameplay prose",
        "review-process language out of the formal PRD",
        "radio/checkbox beside the option text",
        "not explicitly marked accepted/验收无误",
        "unique matching screenshot",
    ):
        assert required in skill


def test_skill_locks_diagram_review_incident_guardrails():
    gameplay_skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    acceptance_skill = (ROOT / "skills" / "executing-staged-acceptance" / "SKILL.md").read_text(encoding="utf-8")
    combined = "\n".join((gameplay_skill, acceptance_skill))
    for required in (
        "策划语义图",
        "不得被通用生成器",
        "左侧章节、中间图解、右侧审核对象",
        "同一图解 ID",
        "用户判退",
        "出现箭头",
        "后端真实状态",
        "过期图解",
        "重复图解",
    ):
        assert required in combined


def test_skill_persists_cross_project_prd_depth_runtime_contract():
    files = [
        SKILL_ROOT / "SKILL.md",
        SKILL_ROOT / "references" / "granularity-contract.md",
        SKILL_ROOT / "references" / "evidence-to-output.md",
        SKILL_ROOT / "references" / "quality-gates.md",
        ROOT / "docs" / "research" / "gve16-production-depth-addendum-2026-08-11.md",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in files)

    for required in (
        "单一事实主载体",
        "carrierRefs",
        "applicable / decision_required / not_applicable",
        "sample_reserve",
        "对象归属的属性正文",
        "禁止固定标题",
        "局部截图与流程图就近放置",
        "禁止审核报告口吻",
        "跨项目盲测",
        "分阶段验收",
        "每个用例使用唯一匹配截图",
    ):
        assert required in combined


def test_skill_requires_line_traced_handwritten_delta_matrix_across_nine_dimensions():
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    matrix = (ROOT / "docs" / "qa" / "handwritten-vs-current-prd-gap-matrix.md").read_text(encoding="utf-8")

    for required in (
        "机制拆分",
        "规则深度",
        "属性解释",
        "配置映射",
        "执行顺序",
        "异常边界",
        "生命周期",
        "图文关系",
        "语言与排布",
        "章节或行号",
        "逐章",
        "项目专属事实",
    ):
        assert required in skill

    for required in (
        "手写文档有",
        "当前输出有",
        "缺失",
        "多余或错误",
        "改善方式",
    ):
        assert required in matrix
