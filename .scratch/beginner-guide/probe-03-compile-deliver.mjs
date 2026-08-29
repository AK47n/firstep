// probe-03-compile-deliver.mjs — beginner-guide/03 实机探针：后两章正文渲染
// （编译与上板：接线表 2 行 / 烧录说明；交付与收尾：草稿/三动作/收尾）→
// 四面板占位全部被正文替换 → 跳转按钮（去任务推进 / 去赛题库）实际生效 →
// 亮暗主题各截一张 → 零 JS 错误。
import { chromium } from "file:///C:/Users/luoji/AppData/Local/npm-cache/_npx/e41f203b7505f1fb/node_modules/playwright/index.mjs";

const results = [];
function check(name, ok, extra = "") {
  results.push({ name, ok, extra });
  console.log((ok ? "PASS " : "FAIL ") + name + (extra ? " — " + extra : ""));
}

const browser = await chromium.launch({ executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe", headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 2600 } });
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));
page.on("console", (m) => {
  if (m.type() === "error" && !String(m.text()).includes("Failed to load resource")) {
    errors.push("console: " + m.text());
  }
});

await page.goto("http://127.0.0.1:8000/", { waitUntil: "networkidle" });
await page.reload({ waitUntil: "networkidle" });
await page.click('header nav button[data-tab="guide"]');

// 1. 编译与上板章
await page.click('#guide-tabs .guide-tab[data-guide-tab="compile"]');
const compileTitle = await page.$eval("#guide-panel-compile h3.guide-chapter-title", (e) => e.textContent);
check("编译与上板章标题", compileTitle.indexOf("编译与上板") === 0, compileTitle);
const compileTables = await page.$$eval("#guide-panel-compile .guide-table", (els) =>
  els.map((t) => t.querySelectorAll("tbody tr").length));
check("接线表 2 行", compileTables.includes(2), JSON.stringify(compileTables));
const compileText = await page.$eval("#guide-panel-compile", (e) => e.textContent);
check("接线/烧录事实", compileText.indexOf("SWDIO") >= 0 && compileText.indexOf("烧录到板子") >= 0 && compileText.indexOf("XDS110") >= 0);

// 2. 交付与收尾章
await page.click('#guide-tabs .guide-tab[data-guide-tab="deliver"]');
const deliverTitle = await page.$eval("#guide-panel-deliver h3.guide-chapter-title", (e) => e.textContent);
check("交付与收尾章标题", deliverTitle.indexOf("交付与收尾") === 0, deliverTitle);
const deliverText = await page.$eval("#guide-panel-deliver", (e) => e.textContent);
check("交付物/收尾事实", deliverText.indexOf("设计报告草稿") >= 0 && deliverText.indexOf("一键打包") >= 0 && deliverText.indexOf("stop-firstep.bat") >= 0);

// 3. 占位全被替换 + 四章齐
const placeholders = await page.$$eval("#tab-guide .guide-empty-hint", (els) => els.length);
check("占位提示全部消失", placeholders === 0, "剩余占位 " + placeholders);
const chapterTitles = await page.$$eval("#tab-guide .guide-chapter-title", (els) => els.map((e) => e.textContent));
check("四章标题齐", chapterTitles.length === 4, chapterTitles.length + " 章");

// 4. 跳转按钮：去任务推进 → 生成页；去赛题库 → 赛题库页
await page.click('#guide-tabs .guide-tab[data-guide-tab="compile"]');
await page.click('#guide-panel-compile .guide-jump[data-jump-tab="generate"][data-jump-focus="revise-panel-tasks"]');
const genActive = await page.$eval("#tab-generate", (s) => s.classList.contains("active"));
check("「去任务推进」→ 生成页激活", genActive);
await page.click('header nav button[data-tab="guide"]');
await page.click('#guide-tabs .guide-tab[data-guide-tab="deliver"]');
await page.click('#guide-panel-deliver .guide-jump[data-jump-tab="topic"]');
const topicActive = await page.$eval("#tab-topic", (s) => s.classList.contains("active"));
check("「去赛题库」→ 赛题库页激活", topicActive);

// 5. 截图（默认暗主题）→ 切亮主题 → 截图
await page.click('header nav button[data-tab="guide"]');
await page.click('#guide-tabs .guide-tab[data-guide-tab="compile"]');
await page.screenshot({ path: ".scratch/beginner-guide/shot-03-compile-dark.png", fullPage: true });
const themeBtn = await page.$("#btn-theme");
if (themeBtn) {
  await page.click("#btn-theme");
  await page.waitForTimeout(400);
  await page.screenshot({ path: ".scratch/beginner-guide/shot-03-compile-light.png", fullPage: true });
  check("亮暗主题截图完成", true);
} else {
  check("主题按钮缺失——跳过亮主题截图", false);
}
check("零页面 JS 错误", errors.length === 0, errors.slice(0, 3).join(" | "));

await browser.close();
const fail = results.filter((r) => !r.ok).length;
console.log((fail === 0 ? "ALL PASS" : "FAILURES: " + fail) + " / " + results.length);
