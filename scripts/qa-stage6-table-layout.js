const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require("playwright");
const output = path.resolve(__dirname, "..", "artifacts", "stage6-table-layout");
fs.mkdirSync(output, { recursive: true });

(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe" });
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
  await page.goto("http://127.0.0.1:8000/?job=8312a91c89e144e6a59f81b982f14c06&ui=final_preview", { waitUntil: "networkidle", timeout: 40000 });
  const title = page.getByText("载具等级", { exact: true }).last();
  await title.scrollIntoViewIfNeeded();
  const table = title.locator("xpath=following::div[contains(@class,'final-document-table-scroll')][1]");
  await table.waitFor({ state: "visible", timeout: 10000 });
  const metrics = await table.evaluate((node) => {
    const tableNode = node.querySelector("table");
    const header = [...tableNode.querySelectorAll("thead th")].map((cell) => cell.innerText.trim());
    const rows = [...tableNode.querySelectorAll("tbody tr")].map((row) => [...row.children].map((cell) => cell.innerText.trim()));
    const styles = getComputedStyle(tableNode.querySelector("th"));
    return {
      header, rows, columnCount: header.length,
      rowColumnCounts: rows.map((row) => row.length),
      wrapperOverflowX: getComputedStyle(node).overflowX,
      headerPadding: styles.padding, borderBottom: styles.borderBottomStyle,
    };
  });
  await table.screenshot({ path: path.join(output, "S6R-TC4-vehicle-level-table.png") });

  const secondTitle = page.getByText("载具栏位与特权", { exact: true }).last();
  await secondTitle.scrollIntoViewIfNeeded();
  const secondTable = secondTitle.locator("xpath=following::div[contains(@class,'final-document-table-scroll')][1]");
  await secondTable.screenshot({ path: path.join(output, "S6R-TC4-vehicle-slot-privilege-table.png") });
  fs.writeFileSync(path.join(output, "result.json"), JSON.stringify(metrics, null, 2));
  console.log(JSON.stringify(metrics, null, 2));
  await browser.close();
})().catch((error) => { console.error(error); process.exitCode = 1; });
