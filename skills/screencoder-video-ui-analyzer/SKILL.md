---
name: screencoder-video-ui-analyzer
description: Extract UI regions, component hierarchy, persistent tracks, state changes, and reusable visual assets from gameplay or interaction-video keyframes with ScreenCoder/UIED and the project fallback detector. Use for video UI understanding, HUD reconstruction, component tracking, visual evidence extraction, or ScreenCoder analysis.
---

# ScreenCoder Video UI Analyzer

Turn retained video frames into timestamped structural evidence for planning. This package exposes the production-relevant ScreenCoder capability already connected through `backend/screen_adapter.py`; it does not invoke ScreenCoder training or post-training code.

## Workflow

1. Consume deduplicated keyframes from `$video-evidence-extractor`.
2. Run UIED through `ScreenCoderAdapter`; record `engine` and any fallback warning.
3. Preserve `bbox`, class, parent/child region placement, region counts, track IDs, and crop candidates.
4. Compare adjacent observations to identify appeared, disappeared, moved, selected, enabled, disabled, or unknown component states.
5. Attach `frameId`, `sceneId`, timestamp, confidence, and source path to every conclusion.
6. Send structural evidence—not raw guesses—to gameplay or interaction planning.

## Rules

- A detected rectangle is not automatically a button; semantic type remains unknown without visual or behavioral evidence.
- Keep HUD/game-world elements separate in gameplay mode and page/modal/navigation layers separate in interaction mode.
- Treat fallback CV output as lower-confidence geometry evidence.
- Never discard the original frame reference when merging component tracks.

## Output

Return region trees, component observations, persistent tracks, state deltas, asset candidates, engine diagnostics, and evidence references. Use deterministic source IDs already emitted by the backend.
