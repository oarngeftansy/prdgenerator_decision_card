---
name: video-evidence-extractor
description: Extract an auditable evidence set from long gameplay or product interaction videos. Use when Codex must scan the full timeline, detect scenes, deduplicate similar frames, densify around transitions, run ScreenCoder/UIED structure detection, track components, crop asset candidates, and package timestamped facts for downstream planning.
---

# Video Evidence Extractor

## Workflow

1. Read video metadata and verify duration, FPS, dimensions, and decodability.
2. Sample the full duration at low frequency; do not cap scanning by truncating the tail.
3. Detect scene changes using visual signatures and adaptive thresholds.
4. Add samples before and after scene boundaries to retain transition evidence.
5. Deduplicate perceptually similar frames while preserving time coverage and boundary frames.
6. Run ScreenCoder/UIED on retained frames; record the engine and fallback warnings.
7. Assign cross-frame component tracks using class and IoU.
8. Save asset crops, region trees, scene groups, and evidence metadata using [references/evidence-schema.md](references/evidence-schema.md).

## Quality Gates

- First and last video segments must be represented.
- Every scene must have beginning, middle, and ending evidence when available.
- Temporal claims require multiple frames or explicit model evidence.
- Failed OCR, structure, or semantic analysis must remain visible as warnings.
