# 言灵·镜瞳

言灵·镜瞳是一个以有序截图为主、视频为辅，生成完整交互与玩法策划案的本地工具。

它的工作流是：

1. 上传 2–30 张带顺序文件名的截图；需要补充动态上下文时再上传辅助视频。
2. 调用视觉模型识别页面、组件、交互流转和玩法线索。
3. 先审核 UE 流程图与竞品参考，再按章节审核玩法规则、参数、待确认项和必要图示。
4. 将确认结果导出为一份包含交互与玩法内容的飞书文档。

网站提供视频时间轴、场景导航、Evidence 定位、优先审核队列、任务取消/重试、单场景重分析和自动质量评分。高活动区间会进行二次高频扫描；音轨会独立提取，后续可接入语音转写模型。

处理管线直接接入 `ScreenCoder/` 的 UIED 页面区域与组件层级扫描，并把 `ai-website-cloner-template/` 的完整状态、行为规格和证据化验收流程落地为视频场景分析与策划案生成模块。

## 本地使用

首次使用安装后端依赖到项目目录：

```powershell
python -m pip install --target .\runtime_packages -r .\requirements-backend.txt
```

启动完整网站：

```powershell
.\start.ps1
```

默认启动后，本机访问 `http://127.0.0.1:8000`；同一局域网设备使用 `http://<本机局域网IP>:8000`。分析必须通过服务地址访问；直接打开 `index.html` 不会降级到旧版浏览器内分析，而会明确提示连接统一分析服务。

如需仅允许本机访问，或修改端口：

```powershell
.\start.ps1 -HostAddress 127.0.0.1 -Port 8000
```

网站默认由 FastAPI 后端直连百炼兼容 API，不受浏览器 CORS 限制。本地代理仅作为可选开发方式：

```powershell
$env:QWEN_API_KEY="sk-your-key-here"
$env:QWEN_BASE_URL="https://ws-e1fznwamzppfboqx.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
node .\tools\qwen-local-proxy.example.js
```

然后在页面左侧把 API 地址设置为：

```text
http://127.0.0.1:8787/v1
```

## 仓库内容

## 已集成的生产工作流

- 视觉解读：支持 Qwen-VL 或任意 OpenAI-compatible 多模态接口。
- 语音证据：自动提取 16kHz 单声道 WAV；配置转写接口后生成带时间段的 transcript。
- 任务历史：网站可恢复、继续审核或归档既有任务。
- 复用证据重解读：从 `frames-complete` 检查点开始，不重复扫描视频和 UIED。
- 规范样例库：保存玩法/交互规范版本和理想策划案示例，并绑定到新任务。
- 审核持久化：保存逐帧确认和修订；未全部确认或仍有未知项时，下载文件自动标记为草稿。

视觉模型和语音转写可以共用 Base URL/API Key，也可在页面中单独配置。密钥不会写入任务 JSON。

- `index.html`: 言灵·镜瞳工具页面。
- `api_server.py` / `backend/`: 长视频任务 API、ScreenCoder 结构扫描、AI 分层解读和策划案生成。
- `start.ps1`: 完整网站启动脚本。
- `tools/qwen-local-proxy.example.js`: 本地 Qwen 代理示例，密钥从环境变量读取。
- `skills/visual-prd-reconstruction`: 视频/截图到 PRD 的 Codex skill。
- `skills/typography-formulas`: 从《排版的力量-54个排版公式》整理出的排版公式 skill。
- `ScreenCoder`: 截图结构检测、区域化代码生成和真实图像回填参考实现。
- `ai-website-cloner-template`: 网站交互取证、组件规格与视觉验收参考实现。

## 安全说明

不要提交真实 API Key。本仓库的 `.gitignore` 已排除 `.env`、`*.local.html` 和本地硬编码代理脚本。

API Key 仅随单次上传请求传给本机后端，不会写入任务 JSON。视频、关键帧和策划案保存在 `data/jobs/<任务ID>/`，该目录默认不提交 Git。

## 发布到飞书

## 玩法审核与恢复

交互预览确认后，可进入“玩法”阶段生成按机制拆分的章节。玩法任务会独立保存章节、图解、审核结论与最终预览版本；从本机任务历史重新打开时，会恢复上次选中的章节、生成状态、图解状态和导出资格。历史接口只返回继续审核所需的数据，不返回 API 配置、技术错误、绝对路径或辅助视频匹配细节。

浏览器回归测试（不会真实发布飞书，发布请求由脚本拦截）：

```powershell
node .\tools\run_gameplay_review_browser_qa.js --playwright "<playwright模块目录>" --base http://127.0.0.1:8000 --output .\artifacts\gameplay-review-qa
```

策划案审核完成后，可在输出区点击“发布到飞书”。工具会以当前飞书用户身份，在“我的空间”根目录查找固定文件夹“视频策划案生成中心”；不存在时创建一次，随后将玩法或交互策划案写成飞书原生文档，并把 UE 流转图写为文档内嵌画板。

Windows 首次使用先检查 CLI 与登录状态：

```powershell
lark-cli.cmd --version
lark-cli.cmd auth status --json --verify
```

若显示用户登录缺失或过期，执行：

```powershell
lark-cli.cmd auth login --domain docs --domain drive --no-wait --json
```

按返回的飞书授权地址完成用户授权后，再回到网站点击发布。登录 token 由 `lark-cli` 自身管理，不会进入网站任务数据。重复发布会更新同一文档；如果系统发现文档已在飞书内被人工修改，则不会覆盖，并提示另存为新版本。
