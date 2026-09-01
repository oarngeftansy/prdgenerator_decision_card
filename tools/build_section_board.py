from __future__ import annotations

import json
import sys
from pathlib import Path


def main(source: str, target: str) -> None:
    payload = json.loads(Path(source).read_text(encoding="utf-8"))
    nodes = payload.get("data", {}).get("result", {}).get("nodes") or payload.get("result", {}).get("nodes") or payload["nodes"]
    sections = []
    for node in nodes:
        size = (node.get("width"), node.get("height"))
        if node.get("type") == "composite_shape" and size in {(1180, 1020), (430, 720)}:
            node["type"] = "section"
            node.pop("composite_shape", None)
            node["locked"] = False
            node["section"] = {"title": "功法选择" if size == (1180, 1020) else "功法详情弹窗"}
            node["children"] = []
            node["style"] = {
                "border_color_type": 0, "border_opacity": 100,
                "border_radius": {"bottom_left": 4, "bottom_right": 4, "top_left": 4, "top_right": 4},
                "border_style": "solid", "border_width": "extra_narrow",
                "fill_color": "#f5f6f7", "fill_color_type": 0, "fill_opacity": 100,
                "theme_border_color_code": -1, "theme_fill_color_code": -1,
            }
            sections.append(node)
    for node in nodes:
        if node in sections or node.get("type") == "connector":
            continue
        x, y = node.get("x", 0), node.get("y", 0)
        section = next((item for item in sections if item["x"] <= x <= item["x"] + item["width"] and item["y"] <= y <= item["y"] + item["height"]), None)
        if section:
            node["parent_id"] = section["id"]
            section["children"].append(node["id"])
            node["x"] = x - section["x"]
            node["y"] = y - section["y"]
    Path(target).write_text(json.dumps({"nodes": nodes}, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
