# P1–P7 Workbench Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将现有审核页面改造成七个独立、可恢复、策划可直接使用的工作台，并保持当前任务数据和最终飞书交付链路不变。

**Architecture:** 保留现有后端审核模型和七个 `data-review-view` 路由，以 `review-workspace.js` 作为统一阶段控制器，各阶段渲染器只负责自身布局。P2–P6 共享已确认目录和证据模型，P7 聚合各阶段真实完成状态；样式按阶段拆分，统一设计令牌由 `review-workspace.css` 提供。

**Tech Stack:** 原生 HTML/CSS/JavaScript、Node `node:test`、Python `pytest`、FastAPI、现有本地浏览器回归脚本。

## Global Constraints

- P1–P7 是七个独立环节；P4、P5、P6 不能合并为同页标签。
- 策划可见文字使用简体中文，不暴露英文枚举、内部编号、状态码、`undefined` 或诊断堆栈。
- 当前任务 `4180cd72eeaa4819be41db50bb4c5011` 的已确认内容不得覆盖或丢失。
- P3 策划草图以 GVE16 页面关系结构为准；本轮不实现红色 UE 流转编号。
- P5 不生成纯文字、单公式和普通参数列表图解；P6 不编造无依据数值。
- P7 只有通过真实主策检查后才能导出飞书。
- 本轮不自动提交或推送 Git。

---

### Task 1: 统一七阶段路由与工作台外框

**Files:**
- Modify: `index.html`
- Modify: `js/review-workspace.js`
- Modify: `css/review-workspace.css`
- Test: `tests/js/review-workspace.test.js`
- Test: `tests/test_review_workspace_ui_contract.py`

**Interfaces:**
- Consumes: `data-review-view`、当前任务审核模型和浏览器 URL 中的 `job`。
- Produces: `WORKBENCH_STEPS` 七阶段定义、统一阶段导航、每个阶段独立 `data-active-view` 布局状态。

- [ ] 添加失败测试：七个阶段名称、顺序和活动状态来自同一公开导航；正式工作台不显示旧项目摘要宽栏。
- [ ] 运行 `node --test tests/js/review-workspace.test.js` 与 `python -m pytest tests/test_review_workspace_ui_contract.py -q`，确认新增断言失败。
- [ ] 在 `review-workspace.js` 建立七阶段元数据并驱动导航、标题和前后环节；在 HTML/CSS 中移除重复横排说明与无价值摘要占位。
- [ ] 重跑两组测试，预期通过；不创建提交。

### Task 2: 共享任务入口与恢复

**Files:**
- Modify: `index.html`
- Modify: `css/style.css`
- Modify: `js/app.js`
- Modify: `js/backend.js`
- Test: `tests/js/screenshot-input.test.js`
- Test: `tests/js/archive-history.test.js`
- Test: `tests/test_resume_jobs.py`

**Interfaces:**
- Consumes: 截图选择、可选视频、模型配置和 `?job=<id>`。
- Produces: 精简任务入口、真实分析进度、失败保留与任务直达恢复。

- [ ] 添加失败测试：无任务时不显示正式阶段导航；任务链接恢复工作台；上传页不存在黑色空预览和冗余欢迎说明。
- [ ] 运行对应 Node/Python 测试并确认失败。
- [ ] 重排上传、基本信息、模型配置和进度；恢复任务时隐藏上传区并进入保存的正式阶段。
- [ ] 重跑测试并通过；使用 HTTP 请求验证当前任务链接返回 200。

### Task 3: P1 动态玩法目录确认

**Files:**
- Modify: `js/gameplay-directory.js`
- Modify: `css/gameplay-review.css`
- Modify: `js/gameplay-workspace.js`
- Test: `tests/js/gameplay-directory.test.js`
- Test: `tests/test_gameplay_directory.py`

**Interfaces:**
- Consumes: `systems[].subsystems[].mechanisms[]` 和策划编辑操作。
- Produces: 动态二/三级目录、主辅玩法建议、原子保存与目录确认状态。

- [ ] 添加失败测试：目录可动态两级或三级渲染；编辑后直接确认仍保存；示例玩法名不被写死。
- [ ] 运行测试确认失败。
- [ ] 实现“理解 / 目录树 / 节点编辑”三栏布局和目录操作反馈。
- [ ] 重跑测试并通过，验证后续工作台读取确认目录。

### Task 4: P2 交互审核与 P3 GVE16 策划草图

**Files:**
- Modify: `js/stage-review.js`
- Modify: `js/export-preview.js`
- Modify: `css/review-workspace.css`
- Modify: `backend/planning_board_model.py`
- Test: `tests/js/stage-review.test.js`
- Test: `tests/js/export-preview.test.js`
- Test: `tests/test_planning_board_model.py`
- Test: `tests/test_gve16_native_whiteboard.py`

**Interfaces:**
- Consumes: 页面、原始截图、页面关系、操作类型和来源判断。
- Produces: 单步交互审核、全局页面关系画板、页面详情、局部截图和页面内小流程。

- [ ] 添加失败测试：主动操作、自动触发和信息页使用不同字段；确认后自动下一项；原图保持比例；同一页面关系不重复定义。
- [ ] 添加画板测试：实线前进、虚线返回、黄色仅用于异常或待决策；无真实去向不生成箭头。
- [ ] 运行测试确认失败。
- [ ] 实现交互审核版式和共享页面关系模型，网页与飞书白板共用同一结构。
- [ ] 重跑测试并通过，执行画板浏览器截图检查。

### Task 5: P4 独立玩法规则工作台

**Files:**
- Modify: `js/gameplay-review.js`
- Modify: `css/gameplay-review.css`
- Modify: `backend/gameplay_review_model.py`
- Test: `tests/js/gameplay-review.test.js`
- Test: `tests/test_gameplay_review_model.py`

**Interfaces:**
- Consumes: 确认目录、章节、证据、参数、公式、验收和来源。
- Produces: “目录 / 证据 / 正文”三栏独立工作台和逐章确认状态。

- [ ] 添加失败测试：按机制动态显示规则模块；参数包含单位、范围、来源、顺序、取整和算例；无证据公式不显示。
- [ ] 运行测试确认失败。
- [ ] 实现目标稿三栏和动态正文；来源标签全部改为策划表述。
- [ ] 重跑测试并通过，确认“确认并查看下一节”只在保存成功后前进。

### Task 6: P5 独立必要图解工作台

**Files:**
- Modify: `js/gameplay-diagrams.js`
- Modify: `css/gameplay-diagrams.css`
- Modify: `backend/gameplay_diagrams.py`
- Test: `tests/js/gameplay-diagrams.test.js`
- Test: `tests/test_gameplay_diagrams.py`

**Interfaces:**
- Consumes: 章节结构字段与跨章节关系。
- Produces: 图解列表、画布、单图通过/重修/删除和“无图解”状态。

- [ ] 添加失败测试：纯文字、单公式、普通列表返回“无图解”；有效状态、概率或结构关系进入审核。
- [ ] 运行测试确认失败。
- [ ] 实现独立三栏图解工作台，隐藏内部编号、置信度和技术统计。
- [ ] 重跑测试并通过，验证零图解可完成本环节。

### Task 7: P6 独立玩法表格工作台

**Files:**
- Modify: `js/gameplay-tables.js`
- Modify: `css/gameplay-tables.css`
- Modify: `backend/gameplay_tables.py`
- Test: `tests/js/gameplay-tables.test.js`
- Test: `tests/test_gameplay_tables.py`

**Interfaces:**
- Consumes: 动态表结构、字段来源、单位、范围和配置映射。
- Produces: 表格目录、动态列、字段详情、逐行与整表确认。

- [ ] 添加失败测试：属性、武器、概率池和配置字段使用不同列；无来源建议值为空；类型为中文策划表述。
- [ ] 运行测试确认失败。
- [ ] 实现独立动态表格工作台和来源详情；简单公式保留文本，不生成关系图。
- [ ] 重跑测试并通过，验证零表格可完成本环节。

### Task 8: P7 完整预览、自动补全与飞书导出

**Files:**
- Modify: `js/export-preview.js`
- Modify: `js/feishu-publish.js`
- Modify: `css/review-workspace.css`
- Modify: `backend/review_preview.py`
- Modify: `backend/lead_planner_gate.py`
- Test: `tests/js/export-preview.test.js`
- Test: `tests/js/feishu-publish.test.js`
- Test: `tests/test_review_preview.py`
- Test: `tests/test_lead_planner_gate.py`
- Test: `tests/test_feishu_publish_contract.py`

**Interfaces:**
- Consumes: P2–P6 真实审核状态及已确认内容。
- Produces: 四级目录预览、自动补全进度与日志、主策复检结果和飞书导出资格。

- [ ] 添加失败测试：部分审核不能显示已就绪；缺失内容自动补全且不覆盖确认内容；四级标题原样输出；失败保留预览和重试入口。
- [ ] 运行测试确认失败。
- [ ] 实现“目录 / 正文 / 状态日志”三栏，统一“返回修改 / 导出到飞书”操作。
- [ ] 重跑测试并通过，验证当前任务可生成可导出预览。

### Task 9: 全量回归与主策验收

**Files:**
- Modify: `tools/review-workspace-browser-qa.js`
- Modify: `.claude/memory/memory.md`
- Modify: `.claude/memory/wiki.md`
- Modify: `.claude/memory/learnings.md`（仅发现新陷阱时）
- Test: `tests/test_review_workspace_browser_qa_contract.py`

**Interfaces:**
- Consumes: 完成后的七阶段工作流。
- Produces: 自动化浏览器验收、测试报告和持久规则。

- [ ] 扩展浏览器回归，覆盖七阶段跳转、刷新恢复、确认后前进、无重叠、无正文省略号和飞书门禁。
- [ ] 运行全部 Python 与前端测试并记录精确结果。
- [ ] 使用当前任务进行真实浏览器验收，检查常用桌面宽度、原图比例、图文对应和中文文案。
- [ ] 以主策视角检查目录、证据、规则、图解、表格和最终文档；修复所有 P0/P1 问题。
- [ ] 更新项目记忆；不提交、不推送，等待用户验收与授权。
