const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require("playwright");

const output = path.resolve(__dirname, "..", "artifacts", "wireframe-comparison");
const url = "http://127.0.0.1:8000/?ui=p5-p7-fixture";
const viewport = { width: 1600, height: 1000 };
const chapters = [
  { id: "C1", scope: "三选一强化池", summary: "升级时提供三项强化，玩家选择一项后立即生效。", confirmation: { confirmed: true } },
  { id: "C2", scope: "武器升级流程", summary: "武器强化后更新对应能力。", confirmation: { confirmed: true } },
  { id: "C3", scope: "生命值状态管理", summary: "生命归零时本局失败。", confirmation: { confirmed: true } },
  { id: "C4", scope: "怪物刷新", summary: "", confirmation: { confirmed: false } },
];
const svg = '<svg viewBox="0 0 560 480" xmlns="http://www.w3.org/2000/svg"><g fill="none" stroke="#2f55c7"><rect x="190" y="20" width="180" height="54" rx="18" fill="#eef3ff"/><path d="M280 74v45M280 173v45M280 272v45"/></g><g font-family="Microsoft YaHei" font-size="16" text-anchor="middle" fill="#25324d"><text x="280" y="53">升级触发</text><rect x="190" y="119" width="180" height="54" rx="8" fill="#fff" stroke="#ccd2dc"/><text x="280" y="151">随机抽取三项强化</text><rect x="190" y="218" width="180" height="54" rx="8" fill="#fff8ef" stroke="#e8a23d"/><text x="280" y="250">玩家选择</text><rect x="190" y="317" width="180" height="54" rx="18" fill="#f1faf4" stroke="#56ad73"/><text x="280" y="349">强化生效并返回战斗</text></g></svg>';

(async () => {
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ headless: true, executablePath: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" });
  try {
    for (const pageName of ["p5", "p6", "p7"]) {
      const page = await browser.newPage({ viewport });
      await page.goto(url, { waitUntil: "networkidle" });
      await page.evaluate(({ pageName, chapters, svg }) => {
        document.documentElement.style.width = "100%"; document.documentElement.style.maxWidth = "none";
        document.body.style.width = "100%"; document.body.style.maxWidth = "none"; document.body.style.margin = "0"; document.body.style.padding = "0";
        document.body.innerHTML = '<div id="fixture" style="width:100vw;max-width:none;height:100vh;margin:0"></div>';
        const root = document.querySelector("#fixture");
        if (pageName === "p5") GameplayDiagrams.render({ root, model: { chapters, diagrams: [
          { id: "D1", type: "state_flow", chapterIds: ["C1"], status: "open", svg },
          { id: "D2", type: "effect_chain", chapterIds: ["C2"], status: "reviewed", svg },
        ], diagramReview: { status: "ready" } } });
        if (pageName === "p6") GameplayTables.render({ root, model: { systems: [{ name: "核心战斗系统", subsystems: [{ chapterIds: ["C3"] }] }, { name: "成长系统", subsystems: [{ chapterIds: ["C1"] }] }], chapters, tables: [
          { id: "T1", title: "生命值参数", chapterIds: ["C3"], columns: ["字段", "类型", "AI 建议值", "修改值", "状态", "操作"], rows: [["基础生命值", "整数", "500", "500", "已确认", "确认"], ["每秒恢复量", "小数", "20", "30", "待确认", "确认"], ["受击扣减值", "公式", "当前生命值－伤害值", "当前生命值－伤害值", "已确认", "确认"]], rowDetails: [{ field: "基础生命值", purpose: "确定初始生存能力", basis: "参考文档明确说明", source: "载具配置", formula: "" }, { field: "每秒恢复量", purpose: "控制生存节奏", basis: "参考文档明确说明", source: "成长配置", formula: "当前生命值＋每秒恢复量×时间" }, { field: "受击扣减值", purpose: "处理受击后的生命变化", basis: "素材明确展示", source: "战斗规则", formula: "当前生命值－本次伤害" }] },
          { id: "T2", title: "强化参数", chapterIds: ["C1"], columns: ["字段", "类型", "AI 建议值", "修改值", "状态", "操作"], rows: [["候选数量", "整数", "3", "3", "已确认", "确认"]] },
        ], tableReview: { status: "ready" } } });
        if (pageName === "p7") FinalDocumentPreview.render({ root, preview: { documentTitle: "自动战斗与局内成长完整策划案", analysisNote: "本文档根据已确认的交互流程、玩法规则、参数表格与有效图解生成。", interactionRevision: 2, gameplayRevision: 3 }, model: { systems: [{ name: "核心战斗系统", subsystems: [{ name: "角色与载具控制", chapterIds: ["C3", "C4"] }] }, { name: "成长系统", subsystems: [{ name: "升级选择", chapterIds: ["C1", "C2"] }] }], chapters, tables: [], diagrams: [{ id: "D1" }] }, interaction: { stages: [
          { id: "S1", title: "持续战斗", pagePurpose: "展示载具、敌人和当前战斗状态", operationBefore: "玩家已进入关卡，载具保持自动攻击", playerAction: "拖动载具调整横向位置", systemFeedback: "载具沿移动方向改变位置并继续攻击", operationResult: "战斗继续，击中敌人时显示伤害数字", confirmation: { confirmed: true } },
          { id: "S2", title: "选择强化", pagePurpose: "让玩家从三个候选强化中选择一项", operationBefore: "达到升级条件后战斗暂停", playerAction: "点击一张强化卡片", systemFeedback: "所选卡片高亮并展示强化结果", operationResult: "强化立即生效并返回战斗", confirmation: { confirmed: true } },
          { id: "S3", title: "首领登场", objective: "提示首领出现并进入首领战", entryCondition: "关卡推进到首领节点", exitCondition: "首领战正式开始", confirmation: { confirmed: true } }
        ], transitions: [{ sourceStageId: "S1", targetStageId: "S2", triggerLabel: "达到升级条件", response: "打开三选一强化界面", resultState: "等待玩家选择" }, { sourceStageId: "S2", targetStageId: "S1", triggerLabel: "确认强化", response: "关闭强化界面", resultState: "返回战斗" }, { sourceStageId: "S1", targetStageId: "S3", triggerLabel: "推进到首领节点", response: "显示首领预警", resultState: "进入首领战" }], sources: {} }, view: { exportDisabled: true }, completion: { progress: 88, missingChapters: [{ id: "C4", title: "怪物刷新" }], logs: [{ message: "玩法目录已确认" }, { message: "交互流程已生成" }, { message: "规则说明已生成" }] } });
      }, { pageName, chapters, svg });
      await page.screenshot({ path: path.join(output, `${pageName}-fixture-current.png`) });
      await page.close();
    }
  } finally { await browser.close(); }
})();
