---
name: video-audio-evidence-aligner
description: Align speech transcripts, visible subtitles, interface text, sound cues, and visual events on one timestamped video timeline. Use when Codex must combine audio and visual evidence, resolve narration-versus-screen conflicts, detect feedback sounds, or enrich gameplay and interaction planning with spoken and written evidence.
---

# Video Audio Evidence Aligner

## Workflow

1. Extract a normalized mono audio track without modifying the source video.
2. Ingest timestamped speech transcription, subtitle OCR, visible UI text, and detected sound cues.
3. Align evidence to scenes and event windows with tolerance appropriate to the source latency.
4. Link spoken rules and labels to supporting or contradicting visual states.
5. Classify audio-only claims as externally narrated until confirmed by visuals.
6. Output aligned evidence using [references/alignment-schema.md](references/alignment-schema.md).

## Rules

- Keep narration, system audio, music, and uncertain sound effects distinct.
- Do not treat commentary as an implemented rule without corroboration.
- Preserve original timestamps and transcription confidence.
- Flag audio/visual contradictions for human review.
