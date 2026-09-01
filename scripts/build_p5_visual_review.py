from __future__ import annotations

import json
from html import escape
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "artifacts/full-mechanic-accepted-publication-2026-08-19/p5-review-diagrams.json"
OUT = ROOT / "artifacts/full-mechanic-accepted-publication-2026-08-19/p5-visual-review.html"


def main() -> None:
    diagrams = json.loads(SOURCE.read_text(encoding="utf-8"))["diagrams"]
    cards = []
    for diagram in diagrams:
        cards.append(
            '<section><h2>{}</h2><div class="flow">{}</div></section>'.format(
                escape(str(diagram["title"])), diagram["svg"]
            )
        )
    OUT.write_text(
        """<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>P5 图解视觉验收</title>
<style>
body{{margin:0;padding:28px;background:#eceaf3;color:#211a31;font-family:"Microsoft YaHei",sans-serif}}
h1{{margin:0 0 24px}}section{{background:white;border:1px solid #d8d2e7;border-radius:18px;padding:20px;margin:0 0 24px;box-shadow:0 8px 24px #39285f18}}
h2{{margin:0 0 12px;font-size:22px}}.flow{{overflow:auto;border-radius:12px;background:#fbfaff;padding:12px}}.flow svg{{display:block;width:100%;height:auto;min-width:980px}}
</style><body><h1>P5 必要图解 · 视觉验收</h1>{}</body></html>""".format("".join(cards)),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
