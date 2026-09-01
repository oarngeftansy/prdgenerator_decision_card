---
name: gve16-feishu-whiteboard
description: Use when generating or reviewing a Feishu UE flow whiteboard from confirmed gameplay or interaction video evidence under the GVE16 standard.
---

# GVE16 Feishu Whiteboard

## Contract

Build screenshot-first planning boards, not abstract flowcharts.

## Interaction Delivery Boundary

交互阶段只生成两个原生 UE 画板，严格按 `planning → competitor` 排列：

1. `策划草图`：使用确认后的代表截图、组件编号、规则说明、straight 跳转/返回线和黄色待确认注记。
2. `竞品参考`：仅使用用户上传的竞品截图和文件名；素材为空时明确显示“本次未提供竞品参考（可选，不影响导出）”，不得使用含义不清的临时占位状态。

交互阶段不生成 UX设计，也不输出叙事、引导、红点提示章节。未来玩法策划使用单独的、证据特定的合同，不得从这份仅限交互的规则中推断。

1. Present the complete large loop, then its stages, then each stage's small loop.
2. Use a real Feishu `section` for every functional module. Sections are unlocked and titled in plain planning language.
3. Use actual screenshots as the primary evidence. Add red numbered markers on the screenshot and matching numbered rule text beside it.
4. Put cross-state constraints, exceptions, and unresolved conclusions in a pale-yellow `#fff3bf` note.
5. Connect modules with native `straight` connectors. Keep lines horizontal or vertical. Use a solid line for forward/open and a dashed line for return/close. Do not add turning points unless a simple right angle is unavoidable.
6. Name actions and states as a planner would say them; never expose implementation labels such as `default-loading`.
7. Overwrite structure before uploading images. Then upload board media and incrementally add token-backed image nodes; an overwrite can invalidate earlier media tokens.
8. Export a preview and query raw nodes after writing.

## Acceptance

- Actual Section nodes exist and are movable with their child content.
- Screenshots, annotations, rule text, and yellow notes remain readable at the default overview.
- Connector endpoints and direction match the described interaction.
- Raw nodes contain only `straight` connectors with no accidental turning points.
- Compare the prototype slice against the GVE16 sample before scaling. Require at least 90% visual-structure fidelity.
- If the slice fails, do not generate the complete video board.

## Output Boundary

Use `backend.feishu_native_board.compile_gve16_whiteboard` for the native structure contract. Keep structure and media overlays separate because Feishu may reject adding a new image directly under an existing Section.

## Gameplay structural diagrams

Gameplay structural diagrams are not interaction planning boards. Generate them in addition to the two interaction boards when prose alone cannot clearly express ordered stages, branch/merge, loop, pause/resume, multi-entity coordination, spatial wave layout, or multi-stage randomization.

- Use native sections, concise rectangular nodes, and straight directional connectors.
- Show the complete loop first, then split complex stages into local diagrams.
- Label conditions on the branch or node; visibly merge paths that return to the same state.
- Show repeated scene/wave reuse as a loop and show pause/resume as explicit state transitions.
- Keep parameter values in nearby prose/tables unless the value changes routing.
- Do not require screenshots for a purely structural gameplay diagram; use screenshots beside it when they prove a visible state or spatial layout.
- A chapter that meets a diagram trigger cannot pass with `no diagram needed` unless the audit records a specific evidence-based exception.
- In the final PRD, anchor each gameplay diagram inside the relevant chapter rather than publishing a separate diagram gallery. The prose before it establishes the trigger/current state; the prose after it explains branch results, configuration, edge cases, and reset behavior.
- When a screenshot explains a node, state, or spatial layout, place the approved screenshot or crop next to that local explanation. The planning-board overview may remain a board, but it does not replace readable inline illustrations in the gameplay body.
- The final preview must render the approved P3 planning-board model at a readable scale. A full board squeezed into a thumbnail strip is not an acceptable “策划草图” delivery even if the underlying SVG exists.
