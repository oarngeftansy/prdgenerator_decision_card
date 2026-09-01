from pathlib import Path

import cv2
import numpy as np

from backend.local_evidence import (
    extract_supplemental,
    merge_local_analysis,
    normalize_attention_signals,
    sample_times,
)


def _video(path: Path, seconds: float = 2.0, fps: int = 10) -> None:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (64, 48))
    for index in range(round(seconds * fps)):
        writer.write(np.full((48, 64, 3), index * 8 % 255, dtype=np.uint8))
    writer.release()


def test_sample_times_are_clipped_deduplicated_and_sorted():
    assert sample_times(5.0, 10.0) == [4.0, 4.5, 5.0, 5.5, 6.0]
    assert sample_times(0.2, 10.0) == [0.0, 0.2, 0.7, 1.2]
    assert sample_times(9.8, 10.0) == [8.8, 9.3, 9.8, 10.0]
    assert sample_times(0.0, 0.1) == [0.0, 0.1]


def test_attention_signals_accept_only_supported_unique_values():
    assert normalize_attention_signals([
        "visual_occlusion", "bad-signal", "visual_occlusion", "text_unreadable"
    ]) == ["visual_occlusion", "text_unreadable"]
    assert normalize_attention_signals("result_not_shown") == ["result_not_shown"]


def test_extract_supplemental_reuses_stable_files(tmp_path):
    video = tmp_path / "source.mp4"
    output = tmp_path / "supplemental"
    _video(video)

    first = extract_supplemental(video, output, "F0002", 1.0, 2.0)
    mtimes = {item["timestamp"]: (output / Path(item["imageUrl"]).name).stat().st_mtime_ns for item in first}
    second = extract_supplemental(video, output, "F0002", 1.0, 2.0)

    assert [item["timestamp"] for item in first] == [0.0, 0.5, 1.0, 1.5, 2.0]
    assert first == second
    assert mtimes == {item["timestamp"]: (output / Path(item["imageUrl"]).name).stat().st_mtime_ns for item in second}


def test_merge_updates_model_fields_but_protects_human_edits():
    frame = {
        "analysis": {"what": "旧场景", "userAction": "策划填写的点击", "confidence": "低"},
        "humanEditedFields": ["userAction"],
    }
    candidate = {
        "what": "战斗场景",
        "userAction": "点击升级卡",
        "confidence": "高",
        "attentionSignals": ["result_not_shown", "invalid"],
    }

    result = merge_local_analysis(frame, candidate)

    assert result["analysis"]["what"] == "战斗场景"
    assert result["analysis"]["userAction"] == "策划填写的点击"
    assert result["analysis"]["confidence"] == "高"
    assert result["analysisSuggestion"] == {"userAction": "点击升级卡"}
    assert result["attentionSignals"] == ["result_not_shown"]
    assert result["lastModelAnalysis"]["userAction"] == "点击升级卡"
