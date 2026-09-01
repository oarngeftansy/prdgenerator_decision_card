const { chromium } = require("playwright");

const jobId = process.env.STAGE6_JOB_ID || "8312a91c89e144e6a59f81b982f14c06";
const origin = process.env.STAGE6_ORIGIN || "http://127.0.0.1:8000";

(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" });
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
  await page.goto(`${origin}/?job=${jobId}&ui=gameplay_directory`, { waitUntil: "networkidle" });
  await page.locator("#reviewWorkspace").waitFor({ state: "visible" });
  const rows = [];
  for (let index = 1; index <= 7; index += 1) {
    await page.locator(`[data-workbench-step="p${index}"]`).click();
    await page.waitForTimeout(index === 3 || index === 7 ? 700 : 250);
    rows.push(await page.evaluate(index => {
      const visible = node => {
        const style = getComputedStyle(node); const rect = node.getBoundingClientRect();
        return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
      };
      const controls = [...document.querySelectorAll("#reviewWorkspace button,#reviewWorkspace input,#reviewWorkspace textarea,#reviewWorkspace select")]
        .filter(visible).map(node => ({
          tag: node.tagName.toLowerCase(), type: node.type || "", text: (node.innerText || node.value || "").trim(),
          aria: node.getAttribute("aria-label") || "", disabled: Boolean(node.disabled),
          cls: node.className, name: node.name || "",
        }));
      return { page: `P${index}`, view: document.querySelector("#reviewWorkspace")?.dataset.activeView, controls };
    }, index));
  }
  console.log(JSON.stringify(rows, null, 2));
  await browser.close();
})().catch(error => { console.error(error); process.exitCode = 1; });
