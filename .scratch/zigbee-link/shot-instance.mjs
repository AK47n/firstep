// 多实例配置卡截屏（工单 zigbee-link 之后的 UI 排查）：打开生成页 → 选平台 →
// 模块池点 led/key → 添加若干实例 → 多视口截图 #card-instance-config。
// 前置：webapp 起在 http://127.0.0.1:8814。用法：node .scratch/zigbee-link/shot-instance.mjs
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";
const require = createRequire(import.meta.url);
const { chromium } = require("C:/Users/luoji/AppData/Local/npm-cache/_npx/e41f203b7505f1fb/node_modules/playwright");

const BASE = "http://127.0.0.1:8814";
const OUT_DIR = ".scratch/zigbee-link";
mkdirSync(OUT_DIR, { recursive: true });

const browser = await chromium.launch({
  headless: true,
  executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe",
});
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
page.setDefaultTimeout(30000);

await page.goto(BASE + "/", { waitUntil: "domcontentloaded" });
await page.waitForSelector("#platforms .platform-card:not(.disabled)");
await page.click("#platforms .platform-card:not(.disabled)");
await page.waitForSelector("#module-grid .module-card[data-add='led']");

// led：加满到 4 个实例（含 name/variant 编辑态）
await page.click("#module-grid .module-card[data-add='led']");
await page.waitForSelector("#card-instance-config:not(.hidden)");
for (let i = 0; i < 4; i++) {
  const btn = await page.$("#instance-config [data-add='led']");
  if (!btn || await btn.isDisabled()) break;
  await btn.click();
}
await page.fill('#instance-config input[data-field="name"][data-index="0"]', "左前红灯 超长显示名测试");
await page.screenshot({ path: OUT_DIR + "/shot-instance-led-1440.png", fullPage: false });
await page.locator("#card-instance-config").screenshot({ path: OUT_DIR + "/shot-instance-led-card-1440.png" });

// 变体下拉实际交互态：点开 select 看选项
const variantSel = await page.$('#instance-config select[data-field="variant"][data-index="0"]');
let variantInfo = "no-select";
if (variantSel) {
  variantInfo = await page.evaluate(() => {
    const sel = document.querySelector('#instance-config select[data-field="variant"][data-index="0"]');
    return {
      html: sel ? sel.outerHTML.slice(0, 400) : null,
      options: sel ? [...sel.options].map((o) => o.value + "=" + o.text) : null,
    };
  });
}
console.log("variant select info:", JSON.stringify(variantInfo, null, 2));

// key 模块：多实例 + 变体 start/stop/mode/set
await page.click("#module-grid .module-card[data-add='key']");
await page.waitForSelector("#instance-config .instance-mod:nth-child(2)");
for (let i = 0; i < 3; i++) {
  const btn = await page.$("#instance-config [data-add='key']");
  if (!btn || await btn.isDisabled()) break;
  await btn.click();
}
await page.screenshot({ path: OUT_DIR + "/shot-instance-key-1440.png", fullPage: false });
await page.locator("#card-instance-config").screenshot({ path: OUT_DIR + "/shot-instance-key-card-1440.png" });

// 窄视口复现「框被挤没」
await page.setViewportSize({ width: 1100, height: 800 });
await page.waitForTimeout(300);
await page.locator("#card-instance-config").screenshot({ path: OUT_DIR + "/shot-instance-card-1100.png" });
await page.screenshot({ path: OUT_DIR + "/shot-instance-page-1100.png", fullPage: false });

await browser.close();
console.log("done:", OUT_DIR);
