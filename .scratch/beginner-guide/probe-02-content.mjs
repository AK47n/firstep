// probe-02-content.mjs — beginner-guide/02 实机探针：教程页两章正文渲染
// （准备/做题主线章标题、平台表 2 行、12 步表 12 行、跳转按钮）→
// 后两章仍为占位 → 跳转按钮实际跳转（去设置配 key / 打开新手词表 / 去设置体检）
// → 欢迎卡 gotoNavTab 回归（若在显示态）→ 零 JS 错误 + 截图。
import { chromium } from "file:///C:/Users/luoji/AppData/Local/npm-cache/_npx/e41f203b7505f1fb/node_modules/playwright/index.mjs";

const results = [];
function check(name, ok, extra = "") {
  results.push({ name, ok, extra });
  console.log((ok ? "PASS " : "FAIL ") + name + (extra ? " — " + extra : ""));
}

const browser = await chromium.launch({ executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe", headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 2400 } });
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

// 1. 准备章正文
const prepTitle = await page.$eval("#guide-panel-prepare h3.guide-chapter-title", (e) => e.textContent);
check("准备章标题渲染", prepTitle.indexOf("准备：装好工具") === 0, prepTitle);
const prepTables = await page.$$eval("#guide-panel-prepare .guide-table", (els) =>
  els.map((t) => t.querySelectorAll("tbody tr").length));
check("准备章表：平台表 2 行", prepTables.includes(2), JSON.stringify(prepTables));
const prepJumps = await page.$$eval('#guide-panel-prepare .guide-jump', (els) => els.map((e) => e.textContent));
check("准备章跳转按钮 ≥2", prepJumps.length >= 2, prepJumps.join(" / "));

// 2. 做题主线章：12 步表
await page.click('#guide-tabs .guide-tab[data-guide-tab="build"]');
const stepRows = await page.$$eval("#guide-panel-build .guide-table", (els) =>
  els.map((t) => t.querySelectorAll("tbody tr").length));
check("做题主线章 12 步表 12 行", stepRows.includes(12), JSON.stringify(stepRows));
const buildText = await page.$eval("#guide-panel-build", (e) => e.textContent);
check("任务推进 / 新手词表在正文", buildText.indexOf("任务推进") >= 0 && buildText.indexOf("新手词表") >= 0);

// 3. 后两章占位保留
await page.click('#guide-tabs .guide-tab[data-guide-tab="compile"]');
const compilePlaceholder = await page.$eval("#guide-panel-compile", (e) => e.textContent.indexOf("工单 03") >= 0);
check("编译与上板章暂为占位（03 填充）", compilePlaceholder);
await page.click('#guide-tabs .guide-tab[data-guide-tab="deliver"]');
const deliverPlaceholder = await page.$eval("#guide-panel-deliver", (e) => e.textContent.indexOf("工单 03") >= 0);
check("交付与收尾章暂为占位（03 填充）", deliverPlaceholder);

// 4. 跳转按钮：去设置配 key
await page.click('#guide-tabs .guide-tab[data-guide-tab="prepare"]');
await page.click('#guide-panel-prepare .guide-jump[data-jump-tab="settings"][data-jump-focus="set-api-key"]');
const settingsActive = await page.$eval("#tab-settings", (s) => s.classList.contains("active"));
const keyFocused = await page.evaluate(() => document.activeElement && document.activeElement.id);
check("「去设置配 API key」→ 设置页激活", settingsActive);
check("聚焦 #set-api-key", keyFocused === "set-api-key", "focus=" + keyFocused);

// 5. 跳转按钮：打开新手词表（回生成页）
await page.click('header nav button[data-tab="guide"]');
await page.click('#guide-tabs .guide-tab[data-guide-tab="build"]');
await page.click('#guide-panel-build .guide-jump[data-jump-tab="generate"][data-jump-focus="glossary-card"]');
const genActive = await page.$eval("#tab-generate", (s) => s.classList.contains("active"));
check("「打开新手词表」→ 生成页激活", genActive);

// 6. 欢迎卡回归（gotoNavTab 共用路径）：显示态则点击验证
const welcomeVisible = await page.$eval("#welcome-card", (el) => !el.classList.contains("hidden") && el.textContent.length > 0);
if (welcomeVisible) {
  await page.click("header nav button[data-tab=generate]");
  const hasBtn = await page.$("#btn-welcome-goto-key");
  if (hasBtn) {
    await page.click("#btn-welcome-goto-key");
    const settingsActive2 = await page.$eval("#tab-settings", (s) => s.classList.contains("active"));
    check("欢迎卡「去配置 API key」→ 设置页（gotoNavTab 回归）", settingsActive2);
  } else {
    check("欢迎卡在显示态但无 goto-key 按钮——跳过回归", true, "模式非 full");
  }
} else {
  check("欢迎卡当前隐藏（已有 key/已选不再显示）——跳过回归", true);
}

// 7. 截图 + 零错误
await page.click('header nav button[data-tab="guide"]');
await page.screenshot({ path: ".scratch/beginner-guide/shot-02-content.png", fullPage: true });
check("零页面 JS 错误", errors.length === 0, errors.slice(0, 3).join(" | "));

await browser.close();
const fail = results.filter((r) => !r.ok).length;
console.log((fail === 0 ? "ALL PASS" : "FAILURES: " + fail) + " / " + results.length);
