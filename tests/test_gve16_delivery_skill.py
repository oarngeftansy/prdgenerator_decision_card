from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / ".codex" / "skills" / "gve16-feishu-delivery"
RUNTIME = ROOT / "skills" / "gve16-feishu-delivery"
FINDINGS = ROOT / "findings.md"
PROGRESS = ROOT / "progress.md"


def _interaction_contract(root: Path) -> str:
    return "\n".join((
        (root / "SKILL.md").read_text(encoding="utf-8"),
        (root / "references" / "delivery-contract.md").read_text(encoding="utf-8"),
        (root / "references" / "flowdoc-review-contract.md").read_text(encoding="utf-8"),
    ))


def test_interaction_skill_names_only_two_active_ue_boards():
    skill_text = _interaction_contract(PROJECT)

    for requirement in (
        "策划草图",
        "竞品参考",
        "交互阶段不生成 UX设计",
        "交互阶段不输出叙事、引导、红点提示章节",
        "planning → competitor",
    ):
        assert requirement in skill_text

    assert "恰好两个有序的原生 whiteboard 块" in skill_text
    assert "嵌入一个真实 whiteboard 块" not in skill_text


def test_interaction_contract_keeps_only_evidence_backed_planning_and_competitor_assets():
    skill_text = _interaction_contract(PROJECT)

    for requirement in (
        "确认后的代表截图",
        "组件编号",
        "规则说明",
        "straight 跳转/返回线",
        "黄色待确认注记",
        "仅使用用户上传的竞品截图和文件名",
        "黄色“待补充”",
        "未来玩法策划",
        "单独的、证据特定的合同",
        "不得从这份仅限交互的规则中推断",
    ):
        assert requirement in skill_text


def test_project_and_runtime_delivery_skill_copies_match():
    for relative in (
        "SKILL.md",
        "references/delivery-contract.md",
        "references/flowdoc-review-contract.md",
    ):
        assert (PROJECT / relative).read_bytes() == (RUNTIME / relative).read_bytes()


def test_task6_records_preserve_base_history_and_add_two_board_facts():
    records = FINDINGS.read_text(encoding="utf-8") + PROGRESS.read_text(encoding="utf-8")

    for requirement in (
        "## Account-switch handoff",
        "2026-07-28 最新版 GVE16 文档发现",
        "ZsTVw7lTEi9rErknL9bcRfFunei",
        "revision 40",
        "planning 146 (58 image/54 composite/30 connector/4 sticky)",
        "competitor 26 image",
        "compatibility strategy A",
        "planning → competitor",
    ):
        assert requirement in records
