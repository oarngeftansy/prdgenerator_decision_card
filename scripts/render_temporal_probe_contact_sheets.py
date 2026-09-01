from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("video", type=Path)
    parser.add_argument("index", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    index = json.loads(args.index.read_text(encoding="utf-8"))
    times = index["candidateSampleTimes"]
    args.output.mkdir(parents=True, exist_ok=True)
    frame_output = args.output / "frames"
    frame_output.mkdir(parents=True, exist_ok=True)
    capture = cv2.VideoCapture(str(args.video))
    tiles = []
    for timestamp in times:
        capture.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
        ok, frame = capture.read()
        if not ok:
            continue
        cv2.imwrite(str(frame_output / f"frame-{int(timestamp * 1000):010d}.jpg"), frame)
        frame = cv2.resize(frame, (160, 300))
        cv2.rectangle(frame, (0, 0), (160, 24), (0, 0, 0), -1)
        cv2.putText(frame, f"{timestamp:07.3f}s", (6, 17), cv2.FONT_HERSHEY_SIMPLEX,
                    0.5, (255, 255, 255), 1, cv2.LINE_AA)
        tiles.append(frame)
    capture.release()
    per_sheet = 20
    for start in range(0, len(tiles), per_sheet):
        batch = tiles[start:start + per_sheet]
        blank = np.zeros_like(tiles[0])
        batch += [blank] * (per_sheet - len(batch))
        rows = [np.hstack(batch[row:row + 5]) for row in range(0, per_sheet, 5)]
        cv2.imwrite(str(args.output / f"sheet-{start // per_sheet + 1:02d}.jpg"), np.vstack(rows))


if __name__ == "__main__":
    main()
