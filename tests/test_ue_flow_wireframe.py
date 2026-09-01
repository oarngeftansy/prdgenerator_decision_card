import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts" / "ue-flow-review-wireframe-2026-08-19"


def test_shell_contract_matches_confirmed_p1_p7_workspace():
    contract = json.loads((ARTIFACT / "shell-contract.json").read_text(encoding="utf-8"))
    assert contract == {
        "stageLabels": [
            "P1 玩法目录",
            "P2-1 交互流程审核",
            "P2-2 UE 流转图审核",
            "P3 交互交付物预览",
            "P4 玩法规则审核",
            "P5 必要图解审核",
            "P6 表格与参数审核",
            "P7 最终文档",
        ],
        "leftPanel": "流程目录",
        "canvasControls": ["缩小", "放大", "适应画布", "定位当前节点"],
        "detailFields": [
            "来源页面",
            "目标页面",
            "触发方式",
            "成立条件",
            "系统反馈",
            "操作结果",
            "证据来源",
        ],
        "footerActions": ["返回 P2 修改", "重新生成", "确认 UE 流转图并进入 P4"],
    }


def test_wireframe_is_read_only_and_embedded_in_original_workspace_shell():
    html = (ARTIFACT / "线框图.html").read_text(encoding="utf-8")
    for marker in (
        'data-browser-contract="ue-flow-review-v1"',
        'id="ue-flow-canvas"',
        'class="ue-flow-node',
        'class="ue-flow-edge',
        'id="ue-detail"',
        'id="back-to-p2"',
        'id="regenerate-flow"',
        'id="confirm-flow"',
        "言灵镜瞳",
        "飞书原生画板",
    ):
        assert marker in html
    assert html.count('class="ue-flow-node') == 5
    assert html.count('class="screen-marker') == 20
    assert html.count('class="screen-shot"') == 5
    assert "P5 必要图解审核" in html
    assert "P6 表格与参数审核" in html
    assert 'draggable="true"' not in html
    assert "新增页面" not in html
    assert "修改连线" not in html
