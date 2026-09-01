from pathlib import Path
import json

from scripts.generate_full_mechanic_accepted_publication import main


def test_final_delivery_separates_review_language_and_emits_p5_p6_contracts(tmp_path: Path):
    main(output_dir=tmp_path)
    markdown = (tmp_path / "human-planning-preview.md").read_text(encoding="utf-8")
    diagrams = json.loads((tmp_path / "necessary-diagrams.json").read_text(encoding="utf-8"))["diagrams"]
    tables = json.loads((tmp_path / "publication-tables.json").read_text(encoding="utf-8"))["tables"]

    assert markdown.startswith("# 一路狂飙·执行策划案\n\n## 玩法概述")
    assert "<!-- EMBED:BOARD:planning -->" in markdown
    assert "<!-- EMBED:BOARD:ue -->" not in markdown
    assert "<!-- EMBED:BOARD:competitor -->" not in markdown
    assert "已批准值" not in markdown
    assert "已确认配置" not in markdown
    assert "| 获得结果 | 栏位状态 | 处理结果 |" in markdown
    assert markdown.count("<!-- EMBED:P6:") == len(tables)
    assert {item["type"] for item in diagrams} >= {"condition_branch", "state_flow", "data_flow"}
    assert all(item["nodes"] and item["edges"] for item in diagrams)
    assert {item["tableId"] for item in tables} == {
        "P6-WEAPON-TRAITS",
        "P6-COMBAT",
        "P6-DAMAGE-STATS",
        "P6-LEVEL-REWARD",
        "P6-CHOICE",
        "P6-DRAW",
    }
    assert all("消费规则" in item["columns"] for item in tables)
