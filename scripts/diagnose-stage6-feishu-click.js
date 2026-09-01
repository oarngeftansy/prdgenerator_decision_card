const { chromium } = require("playwright");
const jobId = "8312a91c89e144e6a59f81b982f14c06";
const origin = process.env.STAGE6_ORIGIN || "http://127.0.0.1:8000";

(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" });
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
  const events = [];
  page.on("request", request => { if (request.url().includes("/feishu/")) events.push({ kind: "request", method: request.method(), url: request.url(), body: request.postData() }); });
  page.on("response", async response => { if (response.url().includes("/feishu/")) events.push({ kind: "response", status: response.status(), url: response.url(), body: await response.text().catch(() => "") }); });
  page.on("pageerror", error => events.push({ kind: "pageerror", message: error.message }));
  page.on("console", message => { if (message.type() === "error") events.push({ kind: "console", message: message.text() }); });
  await page.goto(`${origin}/?job=${jobId}&ui=final_preview`, { waitUntil: "networkidle" });
  await page.locator(".final-document-shell").waitFor({ state: "visible" });
  const button = page.locator(".final-document-feishu-action");
  const before = { count: await button.count(), enabled: await button.isEnabled().catch(() => false), text: await button.innerText().catch(() => ""), bodyHasStatus: (await page.locator("body").innerText()).includes("导出") };
  await button.click();
  await page.waitForTimeout(4000);
  const publication = await page.evaluate(async id => fetch(`/api/jobs/${id}/feishu/publication`, { cache: "no-store" }).then(response => response.json()), jobId);
  const after = { buttonText: await button.innerText().catch(() => "missing"), visibleP7Text: (await page.locator(".final-document-status").innerText()).slice(-500), globalStatus: await page.locator("#status").innerText().catch(() => "") };
  console.log(JSON.stringify({ before, after, publication, events }, null, 2));
  await browser.close();
})().catch(error => { console.error(error); process.exitCode = 1; });
