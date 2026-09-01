# Evidence Schema

Video: filename, duration, FPS, width, height, scan count, scene threshold.

Scene: ID, start, end, representative frame IDs, type, summary, confidence.

Frame: ID, timestamp, scene ID, image path, perceptual hash, structure engine, region tree, elements, asset candidates, analysis, evidence level, confidence.

Component track: ID, class, observations containing frame ID, timestamp, and bounding box.

Allowed evidence levels: `明确展示`, `合理推断`, `未知待确认`.

Allowed confidence values: `高`, `中`, `低`.
