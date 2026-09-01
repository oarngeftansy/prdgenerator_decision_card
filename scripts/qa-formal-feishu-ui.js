const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
function option(name, fallback = "") { const index = process.argv.indexOf(name); return index >= 0 ? process.argv[index + 1] || "" : fallback; }
const { chromium } = require(path.resolve(option("--playwright")));
const base = option("--base", "http://127.0.0.1:8014").replace(/\/$/, "");
const job = option("--job");
const output = path.resolve(option("--output"));

(async () => {
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ headless: true, executablePath: "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe" });
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  page.setDefaultTimeout(30000);
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => { if (message.type() === "error") errors.push(message.text()); });
  try {
    await page.route("**/api/feishu/folders**", (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ folders: [{ token: "folder-qa", name: "策划组共享" }] }) }));
    await page.goto(`${base}/?job=${job}&ui=final_preview`, { waitUntil: "domcontentloaded" });
    await page.waitForFunction(() => document.querySelector("#reviewWorkspace")?.dataset.activeView === "final_preview");
    const pickerPromise = page.evaluate(() => chooseFeishuFolder());
    await page.getByRole("heading", { name: "选择飞书保存位置", exact: true }).waitFor();
    await page.getByRole("button", { name: /策划组共享/ }).click();
    await page.screenshot({ path: path.join(output, "UX-TC19-feishu-folder-picker.png"), fullPage: false, animations: "disabled" });
    await page.getByRole("button", { name: "取消", exact: true }).click();
    assert.equal(await pickerPromise, null);
    assert.equal(await page.locator(".feishu-folder-picker").count(), 0);

    await page.evaluate(() => {
      const target = document.createElement("section");
      target.id = "qaFeishuPublished";
      target.className = "feishu-publication";
      target.innerHTML = FeishuPublish.renderFeishuPublication({
        status: "published",
        documentUrl: "https://example.feishu.cn/docx/qa",
        folderName: "策划组共享",
      }, true);
      document.body.append(target);
      target.scrollIntoView({ block: "center" });
    });
    const publication = page.locator("#qaFeishuPublished");
    await publication.getByRole("link", { name: "打开飞书文档", exact: true }).waitFor();
    assert.equal(await publication.getByRole("button", { name: "重新导出", exact: true }).count(), 1);
    assert.equal(await publication.getByRole("button", { name: "另存为新版本", exact: true }).count(), 1);
    await page.screenshot({ path: path.join(output, "UX-TC20-feishu-published-actions.png"), fullPage: false, animations: "disabled" });
    assert.deepEqual(errors, []);
    fs.writeFileSync(path.join(output, "feishu-ui.json"), JSON.stringify({ passed: true, folderCancelCreatedNothing: true, publishedActions: ["打开飞书文档", "重新导出", "另存为新版本"], errors }, null, 2));
    console.log(JSON.stringify({ passed: true }, null, 2));
  } finally { await browser.close(); }
})().catch((error) => { console.error(error.stack || error); process.exitCode = 1; });
