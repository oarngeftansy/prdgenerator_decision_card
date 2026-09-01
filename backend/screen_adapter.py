from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import cv2

from .image_io import read_image, write_jpeg

ROOT = Path(__file__).resolve().parents[1]
UIED_ROOT = ROOT / "ScreenCoder" / "UIED"


class ScreenCoderAdapter:
    """调用 ScreenCoder/UIED；旧依赖异常时用兼容轮廓检测保证任务可完成。"""

    def __init__(self) -> None:
        self._uied = None
        self.import_error = ""
        try:
            sys.path.insert(0, str(UIED_ROOT))
            from detect_compo import ip_region_proposal
            self._uied = ip_region_proposal
        except Exception as exc:  # optional legacy engine
            self.import_error = str(exc)

    def analyze(self, image_path: Path, output_dir: Path) -> dict[str, Any]:
        output_dir.mkdir(parents=True, exist_ok=True)
        if self._uied is not None:
            try:
                return self._analyze_uied(image_path, output_dir)
            except Exception as exc:
                result = self._analyze_compatible(image_path, output_dir)
                result["warning"] = f"ScreenCoder UIED fallback: {exc}"
                return result
        result = self._analyze_compatible(image_path, output_dir)
        result["warning"] = f"ScreenCoder UIED unavailable: {self.import_error}"
        return result

    def _analyze_uied(self, image_path: Path, output_dir: Path) -> dict[str, Any]:
        params = {
            "min-grad": 8,
            "ffl-block": 5,
            "min-ele-area": 50,
            "merge-contained-ele": True,
        }
        image = read_image(image_path)
        height, width = image.shape[:2]
        resize_height = 800 if height >= width else max(320, int(800 * height / width))
        compos = self._uied.compo_detection(
            str(image_path), str(output_dir), params,
            resize_by_height=resize_height, classifier=None, show=False,
        )
        elements = []
        scale = resize_height / max(1, height)
        for index, compo in enumerate(compos):
            box = compo.bbox
            coords = [round(box.col_min / scale), round(box.row_min / scale), round(box.col_max / scale), round(box.row_max / scale)]
            elements.append({
                "id": f"E{index + 1:03d}",
                "class": getattr(compo, "category", "Compo"),
                "bbox": coords,
                "area": int(max(0, coords[2] - coords[0]) * max(0, coords[3] - coords[1])),
            })
        return self._finalize("ScreenCoder-UIED", image_path, width, height, elements, output_dir)

    def _analyze_compatible(self, image_path: Path, output_dir: Path) -> dict[str, Any]:
        image = read_image(image_path)
        if image is None:
            raise ValueError(f"cannot read image: {image_path}")
        height, width = image.shape[:2]
        scale = min(1.0, 900 / max(height, width))
        work = cv2.resize(image, None, fx=scale, fy=scale) if scale < 1 else image.copy()
        gray = cv2.cvtColor(work, cv2.COLOR_BGR2GRAY)
        grad = cv2.morphologyEx(gray, cv2.MORPH_GRADIENT, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)))
        _, binary = cv2.threshold(grad, 18, 255, cv2.THRESH_BINARY)
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (5, 3)))
        contours, _ = cv2.findContours(binary, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        elements = []
        min_area = max(80, work.shape[0] * work.shape[1] * 0.00012)
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            area = w * h
            if area < min_area or area > work.shape[0] * work.shape[1] * 0.92:
                continue
            inv = 1 / scale
            elements.append({
                "id": "",
                "class": self._region_class(x, y, w, h, work.shape[1], work.shape[0]),
                "bbox": [round(x * inv), round(y * inv), round((x + w) * inv), round((y + h) * inv)],
                "area": round(area * inv * inv),
            })
        elements = self._dedupe(elements)[:120]
        for index, element in enumerate(elements):
            element["id"] = f"E{index + 1:03d}"
        return self._finalize("ScreenCoder-compatible-CV", image_path, width, height, elements, output_dir)

    @staticmethod
    def _region_class(x: int, y: int, w: int, h: int, width: int, height: int) -> str:
        if y < height * 0.14 and w > width * 0.35:
            return "header-or-hud"
        if x < width * 0.18 and h > height * 0.35:
            return "sidebar"
        if y > height * 0.82 and w > width * 0.3:
            return "bottom-controls"
        if w > width * 0.45 and h > height * 0.35:
            return "main-content-or-playfield"
        return "component"

    @staticmethod
    def _dedupe(elements: list[dict[str, Any]]) -> list[dict[str, Any]]:
        ordered = sorted(elements, key=lambda item: item["area"], reverse=True)
        kept = []
        for item in ordered:
            x1, y1, x2, y2 = item["bbox"]
            contained = False
            for other in kept:
                a1, b1, a2, b2 = other["bbox"]
                if a1 <= x1 and b1 <= y1 and a2 >= x2 and b2 >= y2 and item["area"] / max(other["area"], 1) > 0.82:
                    contained = True
                    break
            if not contained:
                kept.append(item)
        return kept

    @staticmethod
    def _finalize(engine: str, image_path: Path, width: int, height: int, elements: list[dict[str, Any]], output_dir: Path) -> dict[str, Any]:
        counts: dict[str, int] = {}
        for element in elements:
            counts[element["class"]] = counts.get(element["class"], 0) + 1
        region_tree = {"id": "ROOT", "class": "screen", "bbox": [0, 0, width, height], "children": []}
        preferred = ["header-or-hud", "sidebar", "main-content-or-playfield", "bottom-controls", "component"]
        region_names = preferred + [name for name in sorted(counts) if name not in preferred]
        for region_name in region_names:
            members = [element for element in elements if element["class"] == region_name]
            if members:
                region_tree["children"].append({"id": f"REGION-{len(region_tree['children']) + 1}", "class": region_name, "children": [element["id"] for element in members]})
        asset_candidates = ScreenCoderAdapter._crop_assets(image_path, elements, output_dir.parent / "assets", width, height)
        result = {
            "engine": engine,
            "source": image_path.name,
            "width": width,
            "height": height,
            "elementCount": len(elements),
            "regionCounts": counts,
            "elements": elements,
            "regionTree": region_tree,
            "assetCandidates": asset_candidates,
        }
        (output_dir / f"{image_path.stem}.structure.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return result

    @staticmethod
    def _crop_assets(image_path: Path, elements: list[dict[str, Any]], assets_dir: Path, width: int, height: int) -> list[dict[str, Any]]:
        image = read_image(image_path)
        if image is None:
            return []
        assets_dir.mkdir(parents=True, exist_ok=True)
        candidates = []
        screen_area = max(1, width * height)
        for element in sorted(elements, key=lambda item: item["area"], reverse=True):
            ratio = element["area"] / screen_area
            if not 0.015 <= ratio <= 0.55:
                continue
            x1, y1, x2, y2 = element["bbox"]
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(width, x2), min(height, y2)
            if x2 <= x1 or y2 <= y1:
                continue
            filename = f"{image_path.stem}_{element['id']}.jpg"
            if write_jpeg(assets_dir / filename, image[y1:y2, x1:x2], 86):
                candidates.append({"elementId": element["id"], "trackId": element.get("trackId"), "bbox": element["bbox"], "path": f"assets/{filename}"})
            if len(candidates) >= 12:
                break
        return candidates
