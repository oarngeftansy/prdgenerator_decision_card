from backend.feishu_prd_depth_contract import PROMPT_CONTRACT
from backend.gameplay_analysis import _prompt, _structure_prompt


def test_generation_prompts_embed_evidence_conditioned_depth_contract():
    for prompt in (_prompt(["F0001"]), _structure_prompt(["F0001"])):
        assert "内容清单" in prompt
        assert "配置字段" in prompt
        assert "执行顺序" in prompt
        assert "公式依据" in prompt
        assert "异常边界" in prompt
        assert "生命周期" in prompt
        assert "玩家操作与系统反馈" in prompt
        assert "制作职责与同步时机" in prompt
        assert "表现与载体要求" in prompt
        assert "有证据却遗漏时阻断" in prompt
        assert "没有证据时不得强行生成模块" in prompt


def test_contract_forbids_fixed_templates_caption_prose_and_pending_pollution():
    assert "不得套用固定游戏目录" in PROMPT_CONTRACT
    assert "页面操作不能冒充玩法概述" in PROMPT_CONTRACT
    assert "看图说话" in PROMPT_CONTRACT
    assert "纯文字和公式不生成图解" in PROMPT_CONTRACT
    assert "不得以大量“待确认”污染正文" in PROMPT_CONTRACT
    assert "正常怎么玩、关键规则、特殊情况" in PROMPT_CONTRACT
def test_runtime_contract_requires_attribute_prose_and_forbids_review_meta_in_delivery():
    prompt = _prompt(["F0001"])

    assert "attributeSections" in prompt
    assert "A complete parameterSchema never substitutes for attributeSections" in prompt
    assert "attributes present only in tables" in prompt
    assert "审核过程" in PROMPT_CONTRACT
    assert "正式正文和图解说明只写业务规则" in PROMPT_CONTRACT
