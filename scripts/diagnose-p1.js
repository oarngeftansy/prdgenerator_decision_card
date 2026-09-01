const { chromium } = require("playwright");

(async () => {
  const browser = await chromium.launch({
    headless: true,
    executablePath: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  });
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
  const messages = [];
  page.on("console", (message) => messages.push(`console:${message.type()}:${message.text()}`));
  page.on("pageerror", (error) => messages.push(`pageerror:${error.message}`));
  await page.goto("http://127.0.0.1:8000/?job=4180cd72eeaa4819be41db50bb4c5011&ui=p1-diagnosis", { waitUntil: "networkidle" });
  await page.locator("#reviewWorkspace").waitFor({ state: "visible", timeout: 15000 });
  const button = page.locator('[data-workbench-step="p1"]');
  await button.click();
  await page.waitForTimeout(1500);
  const result = await page.evaluate(() => ({
    currentView: window.state?.reviewWorkspace?.view,
    directoryHidden: document.querySelector("#gameplayDirectoryView")?.hidden,
    directoryHtml: document.querySelector("#gameplayDirectoryView")?.innerHTML,
    status: document.querySelector("#status")?.textContent,
  }));
  process.stdout.write(`${JSON.stringify({ result, messages }, null, 2)}\n`);
  await browser.close();
})().catch((error) => {
  console.error(error.stack || error);
  process.exitCode = 1;
});
