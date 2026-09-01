const path = require("node:path");
const fs = require("node:fs");
const { chromium } = require("playwright");

(async () => {
  const root = path.resolve(__dirname, "..");
  const artifactName = process.env.P4_ARTIFACT_DIR || "planning-content-phase2-2026-08-17";
  const output = path.join(root, "artifacts", artifactName, "p4-structured-review.png");
  const approvedData = JSON.parse(fs.readFileSync(path.join(root, "artifacts", artifactName, "p4-structured-result.json"), "utf8"));
  const browser = await chromium.launch({ headless: true, executablePath: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" });
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 }, deviceScaleFactor: 1 });
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.setContent('<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>Phase 2 P4</title></head><body><div id="root"></div></body></html>');
  await page.addStyleTag({ path: path.join(root, "css", "style.css") });
  await page.addStyleTag({ path: path.join(root, "css", "gameplay-review.css") });
  await page.addScriptTag({ path: path.join(root, "js", "gameplay-mechanism-forms.js") });
  await page.addScriptTag({ path: path.join(root, "js", "planner-decision-cards.js") });
  await page.addScriptTag({ path: path.join(root, "js", "gameplay-review.js") });
  await page.evaluate(data => {
    window.GameplayReview.render({
      root: document.getElementById("root"),
      model: { contentModelVersion: 2, approvedData: data, chapters: [], evidenceAnchors: [], reviewState: { findings: [] } },
      state: { selectedChapterId: data.chapters.find(chapter => chapter.ruleCount !== 0)?.chapterId || data.chapters[0]?.chapterId },
    });
  }, approvedData);
  await page.locator(".gameplay-rule-audit-v2").waitFor();
  const checks = await page.evaluate(() => ({
    cards: document.querySelectorAll("[data-rule-id]").length,
    slots: document.querySelectorAll("[data-schema-slot]").length,
    hasPlannerProse: document.body.textContent.includes("一句话玩法"),
    overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
  }));
  if (!checks.cards || !checks.slots || checks.hasPlannerProse || checks.overflow || errors.length) throw new Error(JSON.stringify({ checks, errors }));
  await page.screenshot({ path: output, fullPage: true });
  fs.writeFileSync(path.join(path.dirname(output), "p4-screenshot-check.json"), JSON.stringify({ viewport: "1600x1000", ...checks, pageErrors: errors }, null, 2));
  await browser.close();
  console.log(JSON.stringify({ output, ...checks }));
})().catch(error => { console.error(error); process.exit(1); });
