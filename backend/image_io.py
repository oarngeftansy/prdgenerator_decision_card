from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


def read_image(path: Path, flags: int = cv2.IMREAD_COLOR) -> np.ndarray | None:
    try:
        payload = path.read_bytes()
    except OSError:
        return None
    return cv2.imdecode(np.frombuffer(payload, dtype=np.uint8), flags)


def write_jpeg(path: Path, image: np.ndarray, quality: int) -> bool:
    encoded, payload = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not encoded:
        return False
    try:
        path.write_bytes(payload.tobytes())
    except OSError:
        return False
    return True
