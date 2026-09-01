const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(process.argv[2] || "artifacts/qa-web-navigation-2026-08-20/current");
const mainlineDir = path.join(root, "mainline-run8");
const finalDir = path.join(root, "accepted-preview");
const mainline = JSON.parse(fs.readFileSync(path.join(mainlineDir, "acceptance.json"), "utf8"));
const finalPreview = JSON.parse(fs.readFileSync(path.join(finalDir, "acceptance.json"), "utf8"));
const escapeCell = (value) => String(value ?? "").replace(/\|/g, "\\|").replace(/\r?\n/g, " ");
const link = (dir, file) => `[查看截图](${path.relative(root, path.join(dir, file)).replace(/\\/g, "/")})`;
const lines = [
  "# 网页功能与跳转验收",
  "",
  "验收数据全部来自隔离任务副本；不会修改正式项目。每个用例均保留独立截图。",
  "",
  "## 本轮修复的真实问题",
  "",
  "- 目录确认按钮因历史章节字段和决策卡 ID 不兼容返回 400：增加非破坏式历史模型升级。",
  "- 交互审核的“下一环节”回到原环节：改为明确选择目标 Stage；末环节文案和跳转改为 UE 流转图。",
  "- UE 流转图把已绑定代表截图因旧 OCR 标题缺失误判为素材缺口：允许使用同 Stage 的显式 representativeFrame 绑定，仍禁止借用其他 Stage 截图。",
  "- 交付物预览忽略已加载的规则模型并要求重复生成：优先消费当前 gameplayReviewWorkspace model。",
  "- 旧验收脚本用重复的 p2 步骤号定位页面：改用唯一 data-review-view 定位交互审核和 UE 流转图。",
  "",
  "## 主应用验收用例",
  "",
  "| 用例 | 操作 | 预期 | 实际页面 | 截图 |",
  "|---|---|---|---|---|",
  ...mainline.cases.map((item) => `| ${escapeCell(item.id)} | ${escapeCell(item.title)} | ${escapeCell(item.expected)} | ${escapeCell(item.actual)} | ${link(mainlineDir, item.screenshot)} |`),
  "",
  "## 最终 Canonical Publication 网页验收用例",
  "",
  "| 用例 | 标签 | 目标区域 | 截图 |",
  "|---|---|---|---|",
  ...finalPreview.cases.map((item) => `| ${escapeCell(item.id)} | ${escapeCell(item.title)} | ${escapeCell(item.target)} | ${link(finalDir, item.screenshot)} |`),
  "",
  "## 验收范围说明",
  "",
  "- 已覆盖玩法目录、交互审核、UE 流转图、交付物预览、规则审核、图解审核、参数审核、完整策划案预览，以及上一节/下一节和返回修改。",
  "- 已覆盖 Canonical Publication 的正文、UE 流转图、策划草图、竞品参考、必要图解、参数配置表与 GVE16 逐章核对标签，并验证深链接刷新后保持目标标签。",
  "- 发布到飞书属于外部写操作，不在隔离网页按钮点击中重复执行；飞书最终稿已在正文与画板验收阶段单独核验。",
  "",
];
fs.writeFileSync(path.join(root, "WEB_ACCEPTANCE.md"), lines.join("\n"), "utf8");
