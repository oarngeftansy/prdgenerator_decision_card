from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "skills" / "gve16-feishu-delivery"
MIRROR = ROOT / ".codex" / "skills" / "gve16-feishu-delivery"
SKILL = PACKAGE / "SKILL.md"
REFERENCE = (
    PACKAGE
    / "references"
    / "delivery-contract.md"
)
FLOWDOC_REFERENCE = (
    PACKAGE
    / "references"
    / "flowdoc-review-contract.md"
)
def test_skill_preserves_separate_interaction_document_and_whiteboard_references():
    text = SKILL.read_text(encoding="utf-8")

    assert "ZsTVw7lTEi9rErknL9bcRfFunei" in text
    assert "TVnddRv6FoGFE0xTSMkcKNSunpc" in text
    assert "ZNWkd0Ke3oZCtAxDQA5ckxonnJS" in text
    assert "交互交付标准" in text
    assert "正文格式基准" in text
    assert "原生 UE 画板的技术实现基准" in text


def test_skill_requires_representative_only_token_backed_board_images():
    text = (SKILL.read_text(encoding="utf-8") + REFERENCE.read_text(encoding="utf-8"))

    required = [
        "--parent-type whiteboard",
        "代表帧",
        "禁止上传全部证据帧",
        "image.token",
        "width > 0",
        "height > 0",
        "真实 Section",
        "实线",
        "虚线",
        "零尺寸",
        "重复坐标",
    ]
    for phrase in required:
        assert phrase in text


def test_skill_requires_ordered_publish_and_readback_gates():
    text = (SKILL.read_text(encoding="utf-8") + REFERENCE.read_text(encoding="utf-8"))

    ordered_steps = [
        "创建正文",
        "读取画板 token",
        "写入结构",
        "上传代表帧",
        "写入图片节点",
        "预览验收",
        "raw 验收",
    ]
    positions = [text.index(step) for step in ordered_steps]
    assert positions == sorted(positions)
    assert "结构写入完成后不得再次 overwrite" in text
    assert "正文不建立重复的“证据帧图库”" in text
    assert "就近放在对应正文之后" in text
    assert "不得新建另一份文档" in text


def test_runtime_and_codex_skill_copies_are_identical():
    for relative in [
        "SKILL.md",
        "agents/openai.yaml",
        "references/delivery-contract.md",
        "references/flowdoc-review-contract.md",
    ]:
        assert (PACKAGE / relative).read_bytes() == (MIRROR / relative).read_bytes()


def test_flowdoc_review_contract_defines_views_and_editable_fields():
    text = FLOWDOC_REFERENCE.read_text(encoding="utf-8")

    required = [
        "全流程视图",
        "环节视图",
        "组件视图",
        "导出预览视图",
        "截图框选",
        "拖拽移动",
        "8 点缩放",
        "来源页面",
        "目标页面",
        "交互类型",
        "触发条件",
        "成立分支",
        "不成立分支",
        "新增跳转",
        "删除跳转",
        "跨页面去重",
        "撤销/重做",
    ]
    for phrase in required:
        assert phrase in text


def test_flowdoc_review_contract_requires_user_confirmation_before_publish():
    text = FLOWDOC_REFERENCE.read_text(encoding="utf-8")

    states = ["AI 草稿", "用户审核", "流程确认", "环节确认", "导出飞书"]
    positions = [text.index(state) for state in states]
    assert positions == sorted(positions)
    assert "未确认的数据不得进入最终飞书文档" in text
    assert "FlowDoc 决定如何审核，GVE16 决定最终写什么" in text


def test_latest_gve16_reference_preserves_two_board_interaction_contract():
    delivery = SKILL.read_text(encoding="utf-8") + REFERENCE.read_text(encoding="utf-8")

    assert "ZsTVw7lTEi9rErknL9bcRfFunei" in delivery
    for requirement in (
        "planning → competitor",
        "策划草图",
        "竞品参考",
        "交互阶段不生成 UX设计",
        "交互阶段不输出叙事、引导、红点提示章节",
        "确认后的代表截图",
        "仅使用用户上传的竞品截图和文件名",
        "黄色“待补充”",
        "单独的、证据特定的合同",
        "不得从这份仅限交互的规则中推断",
    ):
        assert requirement in delivery
