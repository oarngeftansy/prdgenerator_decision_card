const path = require("path");
const { pathToFileURL } = require("url");

function option(name) {
  const index = process.argv.indexOf(name);
  if (index < 0 || !process.argv[index + 1]) throw new Error(`missing ${name}`);
  return process.argv[index + 1];
}

const { chromium } = require(path.resolve(option("--playwright")));

(async () => {
  const inputDir = path.resolve(option("--input"));
  const outputDir = path.resolve(option("--output"));
  const browser = await chromium.launch({
    headless: true,
    executablePath: "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
  });
  try {
    const page = await browser.newPage({ viewport: { width: 1600, height: 1200 }, deviceScaleFactor: 1 });
    for (const key of ["ue", "planning", "competitor"]) {
      const input = path.join(inputDir, `${key}-preview.svg`);
      await page.goto(pathToFileURL(input).href, { waitUntil: "load" });
      const svg = page.locator("svg");
      await svg.screenshot({ path: path.join(outputDir, `${key}-diagram-design-review.png`) });
    }
  } finally {
    await browser.close();
  }
})();
