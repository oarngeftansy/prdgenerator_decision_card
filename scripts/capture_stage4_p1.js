const path = require("node:path");
const { chromium } = require("playwright");

const jobId = "8312a91c89e144e6a59f81b982f14c06";
const origin = process.env.STAGE4_ORIGIN || "http://127.0.0.1:8000";
const output = path.resolve(__dirname, "..", "artifacts", "stage4-browser-acceptance", "s4-tc07-p1-directory-full.png");

(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" });
  try {
    const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
    await page.goto(`${origin}/?job=${jobId}&ui=gameplay_directory`, { waitUntil: "networkidle" });
    await page.locator("#reviewWorkspace").waitFor({ state: "visible", timeout: 15000 });
    const model = await page.evaluate(async id => (await fetch(`/api/jobs/${id}/gameplay-review-model`)).json(), jobId);
    if (model.revision !== 139 || model.directory.entries.length !== 7) throw new Error("P1 model identity mismatch");
    const renderedEntries = await page.locator("#gameplayDirectoryView .gameplay-directory-tree-item").count();
    if (renderedEntries !== 7) throw new Error(`P1 expected 7 rendered entries, got ${renderedEntries}`);
    await page.evaluate(id => {
      const sourceTree = document.querySelector(".gameplay-directory-tree-column");
      const evidence = document.createElement("main");
      evidence.style.cssText = "display:block;width:1200px;margin:0 auto;padding-bottom:24px;background:#f5f6f8";
      const banner = document.createElement("div");
      banner.textContent = `S4-TC07-P1R｜目录按业务机制归并为七章｜正式任务 ${id}`;
      Object.assign(banner.style, { position: "relative", zIndex: "100000", padding: "10px 18px", background: "#17233f", color: "white", font: "600 16px Microsoft YaHei" });
      const tree = sourceTree.cloneNode(true);
      tree.style.cssText = "display:block;height:auto;max-height:none;overflow:visible;padding-bottom:24px;background:#f5f6f8";
      const scopedView = document.createElement("section");
      scopedView.id = "gameplayDirectoryView";
      scopedView.style.cssText = "display:block;height:auto;overflow:visible";
      scopedView.append(tree);
      evidence.append(banner, scopedView);
      document.body.replaceChildren(evidence);
      document.documentElement.style.height = "auto";
      document.body.style.cssText = "margin:0;height:auto;min-height:0;overflow:visible;background:#e9edf4";
    }, jobId);
    await page.screenshot({ path: output, fullPage: true });
    console.log(JSON.stringify({ passed: true, revision: model.revision, chapters: model.directory.entries.length, renderedEntries, output }, null, 2));
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
