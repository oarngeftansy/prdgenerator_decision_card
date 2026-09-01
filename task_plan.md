# Current task: standardize the approved GVE16 Feishu whiteboard

## Active phase (2026-08-03): compact interaction review

- [x] Recover the authoritative Git HEAD, omitted tests, and project tools from the archive.
- [x] Remove the hard-coded visual API key from the working copy and clear the calibration secret.
- [x] Reconcile the unknown-trigger confirmation contract with the latest compact-review specification.
- [x] Verify the recovered baseline: Python 490 passed; Node 182 passed.
- [x] Write the executable TDD implementation plan for the compact interaction review.
- [x] Implement backend stage grouping and representative-frame limits.
- [x] Implement the Chinese summary and on-demand component editor.
- [x] Run desktop/mobile browser QA with Feishu publication intercepted.

`CURRENT_STATE.md` is the authoritative handoff. The 2026-07-22 runtime task is historical only.

## Active phase (2026-07-22)
- [ ] Run `D:\20260722-171746.mp4` through interaction analysis.
- [ ] Inspect large-loop, stage, and small-loop hierarchy as lead planner.
- [ ] Repair the interaction plan until it meets the GVE16 content contract.
- [ ] Publish the interaction document and native UE board to Feishu.
- [ ] Compare the final document/board with the sample and report residual gaps.

## Active phase (2026-07-24)
- [ ] Align the mobile interaction planning output more strictly to the GVE16 interaction-planning form.
- [ ] Keep evidence/frame references as internal validation and traceability only.
- [ ] Remove user-facing "evidence chain/evidence frame" framing from Markdown and Feishu renderers unless the GVE16 form explicitly requires it.
- [ ] Reuse PRD-to-Figma only as schema/validation discipline, not as a visible output structure.

## Completed whiteboard foundation
- [x] Validate a minimal board slice against the GVE16 sample.
- [x] Add a failing contract for the approved native-board structure.
- [x] Deploy the project Skill and reference schema.
- [x] Add a reusable native-board compiler without new dependencies.
- [x] Run focused regression and Skill validation.

## Active acceptance contract
- Real `section` nodes, not section-shaped rectangles.
- Screenshot-first evidence with red numbered annotations and adjacent readable rules.
- Yellow notes for cross-state constraints and exceptions.
- Native `straight` horizontal/vertical connectors; no diagonal/freeform paths.
- Structure can be emitted independently from image-token overlays.

## Goal
Publish the validated gameplay or interaction plan into the fixed Feishu folder “视频策划案生成中心” as a native document with an embedded UE flow whiteboard.

## Phases
- [x] Task 1: safe lark-cli execution boundary.
- [x] Task 2: native Feishu XML and Mermaid renderers.
- [x] Task 3: idempotent publication service and conflict protection.
- [x] Task 4: FastAPI publication endpoints.
- [x] Task 5: website publication interaction.
- [x] Task 6: authentication guidance and end-to-end verification.

## Constraints
- Explicit publish click only; never auto-publish.
- Use Feishu user identity and the exact fixed folder name.
- Never persist or expose credentials.
- Never overwrite externally edited Feishu documents.
- Preserve separate gameplay and interaction structures.
- Add no dependency; use Python stdlib and the installed lark-cli.

## Baseline
- Branch: `codex/gve16-calibration`.
- Existing checkout is not a linked worktree; most application files are untracked, so a new worktree would omit the working application. User selected inline execution in the current task.
- Backend focused baseline: 14 passed.
- Frontend focused baseline: 21 passed.

## Errors
| Error | Attempt | Resolution |
|---|---|---|
| `lark-cli` PowerShell shim blocked by execution policy. | CLI capability check | Use the installed `lark-cli.cmd` executable with argv and `shell=False`. |

## Acceptance
- Real gameplay job published to a native Feishu document with 138 evidence images.
- Embedded UE whiteboard queried successfully and returned non-empty Mermaid code.
- Repeating the same request reused the same document URL.
- Focused verification: 34 Python tests and 6 JavaScript tests passed.
| Feishu user identity `岛岛` has no usable token. | Auth status check | Implement offline with fake CLI; real acceptance waits for a fresh user authorization. |
# 2026-07-24 成功飞书交付 Skill 固化

- [x] 停止本地服务和后续飞书写入。
- [x] 提交当前版本：`fe6c4e6 飞书逻辑修复`。
- [x] 只读获取成功文档 `TVnddRv6FoGFE0xTSMkcKNSunpc` 与画板 `XTlEwvcxohLp9QbnpR3c9SpOnhf`。
- [x] 基于成功链路与失败残留编写飞书文档+GVE16画板交付 Skill。
- [x] 验证 Skill 结构、触发条件和验收门槛。
- [x] Skill 完成后读取 `C:/Users/ASUS/Desktop/flowdoc-core-skill.md`，提取可复用项。

### 三层标准

- GVE16：总体颗粒度与策划表达。
- `TVnd...`：正文标题、章节顺序与对应内容。
- `ZNWk...`：UE 流转图 Section、代表截图、标记和往返连线。

### FlowDoc 审核交互补充

- [x] 固化全流程、环节、组件和导出预览四类视图。
- [x] 固化截图框选、跳转增删、字段编辑、去重和撤销/重做。
- [x] 固化 `AI 草稿 → 用户审核 → 流程确认 → 环节确认 → 导出飞书` 状态门槛。

## Active phase (2026-07-27): 截图优先输入

- [x] 确认截图文件夹为主输入，辅助视频为可选补充。
- [x] 确认只读取当前目录、文件名自然排序并允许手动调整。
- [x] 确认每个任务接收 2–30 张截图。
- [x] 完成入口、数据链路、错误处理与验收设计。
- [x] 提交并由用户复核设计规格。
- [x] 编写 TDD 实施计划。
- [x] 实现并验证截图优先任务链路。

## Screenshot-first planning checkpoint (2026-07-27)

- [x] User approved the written screenshot-first design specification.
- [x] Saved the TDD implementation plan at `docs/superpowers/plans/2026-07-27-screenshot-first-input-plan.md`.
- [x] Execute the approved plan inline after user approval.

## Active phase (2026-07-27): GVE16 审核工作台

- [x] 确认一期采用全宽分阶段工作台。
- [x] 确认全流程使用横向环节泳道，分支按环节折叠。
- [x] 确认环节审核采用截图与规则并排，移动端切换画面/规则。
- [x] 确认候选转换筛选、点击锚点、自动转换和可拖拽组件框。
- [x] 确认核心未知项阻断导出、非核心未知项保留并提示。
- [x] 完成正式设计规格。
- [x] 用户复核书面规格。
- [x] 编写 TDD 实施计划。
- [x] 选择 Subagent-Driven 执行并完成产品改造。
# 2026-07-28 最新版 GVE16 基准校准

- [x] 只读获取文档 `THLgdhhtIomhh4x2osacalc8nAf` 的目录和目标章节。
- [x] 导出并检查 `UX设计`、`策划草图`、`竞品参考` 三个 UE 画板。
- [x] 先补充失败的合同测试，锁定最新版文档 token、三画板职责及叙事/引导/红点规则域。
- [x] 更新双份 GVE16 Skill/交付合同，并保持内容一致。
- [x] 运行 Skill、渲染与相关回归测试，检查 git diff。

目标：把最新版 GVE16 作为后续交互策划审核与飞书导出的正式基准；不修改用户提供的飞书原文。

RED 已确认：新增合同因缺少 `THLg...` 失败；GREEN 后 Skill/部署合同 12 项通过。默认 Python 无 pytest，已改用 `calibration_packages;runtime_packages` 测试环境。

最终验证：全量 Python 测试 262 项通过（3 个既有弃用警告）；4 份 Skill 校验均通过；双份部署由字节一致性测试保护；`git diff --check` 无错误。Ponytail 复核未发现可删除的抽象或依赖。

# 2026-07-28 三画板与规则域扩展设计

- [x] 核对现有审核模型、阶段视图、导出渲染和飞书画板边界。
- [x] 用户确认独立规则域审核步骤。
- [x] 用户确认空域始终输出“本次素材未展示，待确认”，且不阻止导出。
- [x] 用户确认策划草图自动生成，UX/竞品采用可选素材槽。
- [x] 写入正式设计规格。
- [x] 自检规格并提交设计文档。
- [x] 等待用户复核书面规格后编写实施计划。

# 2026-07-28 三画板与规则域实施计划

- [x] 用户确认书面规格。
- [x] 映射审核模型、操作服务、前端工作台、正文渲染和飞书发布边界。
- [x] 写入 TDD 实施计划 `docs/superpowers/plans/2026-07-28-latest-gve16-rule-domains-plan.md`。
- [x] 自检计划的规格覆盖、占位符和接口一致性。
- [ ] 用户选择 Subagent-Driven 或 Inline Execution。

## Task 7 completion — two-board migration and browser QA (2026-07-28)

- [completed] Superseded the obsolete three-board/rule-domain execution plan with the active `planning → competitor` contract; legacy `ruleDomains` and `referenceBoards.ux` are read-only compatibility data.
- [completed] Added the legacy-three-board HTTP migration regression and migrated stale asset API/asset tests to competitor-only operations while retaining explicit legacy preservation coverage.
- [completed] Reworked real Edge QA for flow → component/stage confirmation → preview, competitor empty/upload/reorder/delete/retry, revision-safe export, mobile accessibility, and no rules/UX upload surface.
- [completed] No Feishu publication endpoint or document was invoked; artifacts remain ignored and unstaged.

## Active phase (2026-07-28): gameplay-planning research

- [completed] Inspect primary-source repositories `donchitos/claude-code-game-studios` and `bkingfilm/lapian-notes`, focusing on reusable game-planning, adjacent-video evidence, chapter decomposition, and diagram-revision patterns.
- [completed] Read the gameplay portions of the Maze Development Story execution document and the latest GVE16 execution document; exclude the UE-flow section from the gameplay contract.
- [completed] Reconfirm the completed interaction-review journey and define the handoff from interaction approval into gameplay review.
- [completed] Define screenshot-anchor + adjacent-video sampling: screenshots identify key mechanics; the analyzer opens only the nearby video interval needed to recover triggers, transitions, timing, and results.
- [completed] Define chapter-level gameplay checkpoints from the two execution documents, with mechanism-specific fields and parameters rather than a universal form.
- [completed] Define optional generated diagrams and a per-diagram feedback/revision loop; ordinary gameplay review does not display source screenshots.
- [completed] Do not sample `C:/Users/ASUS/Downloads/主线1.mp4`: the document reads were sufficient for the workflow contract and no screenshot-to-video anchor was supplied; preserve the video for later targeted adjacency checks.
- [completed] User confirmed one complete Feishu document: approved UE planning/competitor boards first, then reviewed gameplay chapters.

## Active phase (2026-07-29): gameplay-review implementation planning

- [completed] Map current interaction model, mutation service, browser workspace, preview, publication, auxiliary-video, and test boundaries.
- [completed] Apply the approved screenshot-first gameplay workflow and single-document export decision.
- [completed] Write the TDD implementation plan at `docs/superpowers/plans/2026-07-29-gameplay-review-implementation.md`.
- [completed] User chose Subagent-Driven execution; gameplay workflow Tasks 1-9 implemented and independently reviewed.
