# 长视频分析架构

## 可执行链路

1. 前端通过 `POST /api/jobs` 上传视频和玩法/交互方向。
2. 后端为任务建立独立目录并异步执行，前端轮询 `GET /api/jobs/<id>`。
3. OpenCV 读取完整时长，最多扫描 240 个全片样本。
4. 使用 HSV 直方图差异发现高变化场景，并在变化点前后补帧。
5. 关键帧最多 140 个，超出时按完整时间轴均匀收敛，不截断视频尾部。
6. 每个关键帧实际调用 `ScreenCoder/UIED/detect_compo/ip_region_proposal.py`。
7. ScreenCoder 旧算法异常时，兼容 OpenCV 引擎继续任务，并在结构结果中记录 warning 和 engine。
8. AI 首先分析场景代表帧，再对最多 60 个均匀分布的事件帧建立因果链；其他帧继承场景上下文并明确标记。
9. 策划案按玩法或交互分别生成，并包含场景时间线、事件链、证据索引、置信度和未知项。
10. 感知哈希删除短时间内重复帧，场景边界帧不参与删除。
11. 同类组件通过 IoU 建立跨帧轨迹，资产候选被裁剪到任务 `assets/` 目录。
12. 每个场景生成独立的 `scene-NNN.spec.md`，用于审核和单场景重分析。
13. 高活动区间按 5 FPS 二次扫描，再通过感知哈希收敛重复帧。
14. 音轨通过项目内 FFmpeg 提取为 16kHz 单声道 WAV，等待转写提供方接入。
15. 事实协调器生成全局事实表、审核队列和 0–100 质量分。
16. 前端时间轴支持场景、Evidence、视频时间点和帧卡片双向跳转。

## 任务产物

```text
data/jobs/<job-id>/
├─ source.<video-extension>
├─ job.json
├─ frames/
│  └─ F0001_<timestamp>.jpg
└─ structures/
   ├─ ip/                         # ScreenCoder UIED 原始输出
   └─ F0001_<timestamp>.structure.json
├─ assets/
│  └─ F0001_<timestamp>_E001.jpg
└─ specs/
   └─ scene-001.spec.md
```

## 降级边界

- 后端未启动：前端回退到浏览器内抽帧与 Qwen 调用。
- 未配置视觉模型：仍执行全片扫描和 ScreenCoder 结构检测；语义字段标为未知，不伪造结论。
- UIED 单帧失败：使用兼容轮廓检测，并记录具体 warning。
- 浏览器关闭：任务继续运行；再次打开网站会根据本地任务 ID 恢复轮询。
- 用户可取消或重试任务，也可只重新分析一个场景。

## 项目 Skills

- `long-video-gameplay-planner`：玩法规则、核心循环和状态机策划。
- `long-video-interaction-planner`：用户流程、组件状态和交互策划。
- `video-evidence-extractor`：场景、关键帧、组件轨迹和资产证据。
- `planning-sample-calibrator`：从标杆样例提炼规范并建立回归评分。
- `temporal-event-reconciler`：统一跨场景事实、状态和事件，发现冲突。
- `planning-quality-auditor`：审计覆盖率、因果链、证据和交付质量。
- `video-audio-evidence-aligner`：对齐语音、字幕、音效和画面事件。

## 样例规范接入点

后续提供“原视频 + 理想策划案”后，主要校准：

- `backend/analysis_service.py`：场景和事件帧提示词、字段映射、证据规则。
- `backend/planner.py`：玩法与交互策划案章节、术语和详略标准。

## 飞书原生发布层

飞书发布位于策划模型和 Markdown 输出之后，不参与视频分析。`backend/feishu_render.py` 将已验证的 GVE16 中间模型渲染为飞书 XML 与 Mermaid UE 流程；`backend/feishu_publish.py` 负责固定文件夹、文档、证据图片、画板验证、幂等重试和 revision 冲突保护；`backend/feishu_cli.py` 只允许执行明确白名单中的 `lark-cli.cmd` argv。

发布必须由用户在网站明确点击触发，并使用飞书用户身份。任务只保存公开文档链接、资源标识、revision、内容指纹和发布状态，不保存飞书或模型凭证。文档写入成功而图片或画板失败时，任务保留部分成功状态，后续从失败步骤继续。
- 可新增 `specs/gameplay/` 与 `specs/interaction/`，把规范从代码中外置。
