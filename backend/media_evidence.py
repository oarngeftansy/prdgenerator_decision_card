from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import imageio_ffmpeg
from openai import OpenAI


def extract_audio_evidence(video_path: Path, job_dir: Path, config: dict[str, Any] | None = None) -> dict[str, Any]:
    audio_path = job_dir / "audio.wav"
    command = [
        imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-i", str(video_path),
        "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(audio_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=180)
    if result.returncode != 0 or not audio_path.exists():
        return {"hasAudio": False, "audioUrl": None, "transcript": [], "warning": "视频没有可提取音轨或音轨解码失败。"}
    evidence = {
        "hasAudio": True,
        "audioUrl": f"/artifacts/{job_dir.name}/audio.wav",
        "transcript": [],
        "transcriptionStatus": "awaiting-transcription-provider",
        "note": "音轨已按16kHz单声道提取；语音转写将在配置转写模型后写入同一时间轴。",
    }
    config = config or {}
    api_base = str(config.get("transcriptionApiBase") or config.get("apiBase") or "").rstrip("/")
    api_key = str(config.get("transcriptionApiKey") or config.get("apiKey") or "")
    model = str(config.get("transcriptionModel") or "whisper-1")
    if not api_base or not api_key:
        return evidence
    try:
        client = OpenAI(api_key=api_key, base_url=api_base, timeout=180, max_retries=2)
        with audio_path.open("rb") as audio:
            result = client.audio.transcriptions.create(
                model=model, file=audio, response_format="verbose_json", timestamp_granularities=["segment"]
            )
        segments = getattr(result, "segments", None) or []
        evidence.update(
            transcript=[{"start": float(getattr(s, "start", 0)), "end": float(getattr(s, "end", 0)), "text": str(getattr(s, "text", "")).strip()} for s in segments],
            transcriptionStatus="completed", transcriptionModel=model,
            note=f"音轨已由 {model} 转写并对齐到视频时间轴。",
        )
    except Exception as exc:
        evidence.update(transcriptionStatus="failed", transcriptionError=str(exc))
    return evidence
