from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("video", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--start", type=float, required=True)
    parser.add_argument("--end", type=float, required=True)
    parser.add_argument("--step", type=float, default=0.5)
    args = parser.parse_args()
    if args.end <= args.start or args.step <= 0:
        raise ValueError("invalid window")
    args.output.mkdir(parents=True, exist_ok=True)
    capture = cv2.VideoCapture(str(args.video))
    tiles = []
    timestamp = args.start
    while timestamp <= args.end + 1e-6:
        capture.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
        ok, raw = capture.read()
        if ok:
            frame_path = args.output / f"frame-{int(timestamp * 1000):010d}.jpg"
            cv2.imwrite(str(frame_path), raw)
            tile = cv2.resize(raw, (160, 300))
            cv2.rectangle(tile, (0, 0), (160, 24), (0, 0, 0), -1)
            cv2.putText(tile, f"{timestamp:07.3f}s", (6, 17), cv2.FONT_HERSHEY_SIMPLEX,
                        0.5, (255, 255, 255), 1, cv2.LINE_AA)
            tiles.append(tile)
        timestamp = round(timestamp + args.step, 3)
    capture.release()
    if not tiles:
        raise ValueError("no frames decoded")
    per_sheet = 20
    blank = np.zeros_like(tiles[0])
    for start in range(0, len(tiles), per_sheet):
        batch = tiles[start:start + per_sheet]
        batch += [blank] * (per_sheet - len(batch))
        rows = [np.hstack(batch[row:row + 5]) for row in range(0, per_sheet, 5)]
        cv2.imwrite(str(args.output / f"sheet-{start // per_sheet + 1:02d}.jpg"), np.vstack(rows))


if __name__ == "__main__":
    main()
