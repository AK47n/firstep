// probe-01-nav.mjs — beginner-guide/01 实机探针：导航三组 9 键在位 →
// 点「新手指引」进教程页 → 默认激活 prepare → 四子页签点击/方向键切换
// （panel 互斥 + aria-selected + roving tabindex）→ 切回生成页正常 →
// 零 JS 错误。截图存 .scratch/beginner-guide/shot-01-nav.png。
import { chromium } from "file:///C:/Users/luoji/AppData/Local/npm-cache/_npx/e41f203b7505f1fb/node_modules/playwright/index.mjs";

const results = [];
function check(name, ok, extra = "") {
  results.push({ name, ok, extra });
  console.log((ok ? "PASS " : "FAIL ") + name + (extra ? " — " + extra : ""));
}

const browser = await chromium.launch({ executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe", headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 2000 } });
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));
page.on("console", (m) => {
  if (m.type() === "error" && !String(m.text()).includes("Failed to load resource")) {
    errors.push("console: " + m.text());
  }
});

await page.goto("http://127.0.0.1:8000/", { waitUntil: "networkidle" });
await page.reload({ waitUntil: "networkidle" });

// 1. 导航三组 + 9 键 + 「指南」组在最后
const groups = await page.$$eval("header nav .tab-group", (els) =>
  els.map((e) => ({ label: e.getAttribute("aria-label"), keys: [...e.querySelectorAll("button[data-tab]")].map((b) => b.dataset.tab) })));
check("导航三组", JSON.stringify(groups.map((g) => g.label)) === JSON.stringify(["做题", "资料管理", "指南"]),
  groups.map((g) => g.label).join(">"));
check("指南组含 guide 键", groups[2] && groups[2].keys[0] === "guide", groups[2] && groups[2].keys.join(","));
const totalKeys = groups.reduce((n, g) => n + g.keys.length, 0);
check("共 9 个 tab 键", totalKeys === 9, "n=" + totalKeys);

// 2. 点「新手指引」→ 教程页激活
await page.click('header nav button[data-tab="guide"]');
const guideActive = await page.$eval("#tab-guide", (s) => s.classList.contains("active"));
const genHidden = await page.$eval("#tab-generate", (s) => !s.classList.contains("active"));
check("点「新手指引」→ #tab-guide 激活", guideActive);
check("生成页收起", genHidden);

// 3. 四子页签 + 默认 prepare 激活 + panel 互斥
const subKeys = await page.$$eval("#guide-tabs .guide-tab", (els) => els.map((e) => e.dataset.guideTab));
check("四个子页签按钮", JSON.stringify(subKeys) === JSON.stringify(["prepare", "build", "compile", "deliver"]), subKeys.join(","));
const activeInit = await page.$eval("#guide-tabs .guide-tab.active", (e) => e.dataset.guideTab);
check("默认激活 prepare", activeInit === "prepare", "active=" + activeInit);

// 4. 子页签点击切换：panel hidden 互斥 + aria-selected + roving tabindex
async function checkTab(key) {
  await page.click('#guide-tabs .guide-tab[data-guide-tab="' + key + '"]');
  const panels = await page.$$eval(".guide-panel", (els) =>
    els.map((e) => ({ id: e.id, hidden: e.hasAttribute("hidden") })));
  const visible = panels.filter((p) => !p.hidden).map((p) => p.id);
  const aria = await page.$eval('#guide-tabs .guide-tab[data-guide-tab="' + key + '"]', (e) => e.getAttribute("aria-selected"));
  const tabIdx = await page.$$eval("#guide-tabs .guide-tab", (els) =>
    els.map((e) => ({ k: e.dataset.guideTab, ti: e.tabIndex })));
  const rovingOk = tabIdx.filter((t) => t.ti === 0).map((t) => t.k).join(",") === key;
  check("点「" + key + "」→ 仅对应 panel 可见", visible.length === 1 && visible[0] === "guide-panel-" + key, visible.join(","));
  check("aria-selected 同步 " + key, aria === "true", "aria=" + aria);
  check("roving tabindex " + key, rovingOk, tabIdx.map((t) => t.k + ":" + t.ti).join(","));
}
// 初始 roving（评审整改：启动即应用）
const initTabIdx = await page.$$eval("#guide-tabs .guide-tab", (els) =>
  els.map((e) => ({ k: e.dataset.guideTab, ti: e.tabIndex })));
check("初始 roving 已应用", initTabIdx.filter((t) => t.ti === 0).map((t) => t.k).join(",") === "prepare",
  initTabIdx.map((t) => t.k + ":" + t.ti).join(","));
await checkTab("build");
await checkTab("compile");
await checkTab("deliver");
await checkTab("prepare");

// 5. 方向键循环：prepare → ArrowRight → build（焦点跟随）
await page.focus('#guide-tabs .guide-tab[data-guide-tab="prepare"]');
await page.keyboard.press("ArrowRight");
const afterArrow = await page.$eval("#guide-tabs .guide-tab.active", (e) => e.dataset.guideTab);
const focused = await page.evaluate(() => document.activeElement && document.activeElement.dataset ? document.activeElement.dataset.guideTab : null);
check("ArrowRight → 激活 build", afterArrow === "build", "active=" + afterArrow);
check("焦点跟随 build", focused === "build", "focus=" + focused);
await page.keyboard.press("ArrowLeft");
const afterLeft = await page.$eval("#guide-tabs .guide-tab.active", (e) => e.dataset.guideTab);
check("ArrowLeft → 回到 prepare", afterLeft === "prepare", "active=" + afterLeft);

// 6. 切回生成页 + 再切回教程页（页签切换器无状态残留）
await page.click('header nav button[data-tab="generate"]');
const genBack = await page.$eval("#tab-generate", (s) => s.classList.contains("active"));
const guideHidden = await page.$eval("#tab-guide", (s) => !s.classList.contains("active"));
check("切回生成页", genBack && guideHidden);
await page.click('header nav button[data-tab="guide"]');
const guideBack = await page.$eval("#tab-guide", (s) => s.classList.contains("active"));
check("再切回教程页", guideBack);

// 7. 截图 + 零错误
await page.screenshot({ path: ".scratch/beginner-guide/shot-01-nav.png", fullPage: true });
check("零页面 JS 错误", errors.length === 0, errors.slice(0, 3).join(" | "));

await browser.close();
const fail = results.filter((r) => !r.ok).length;
console.log((fail === 0 ? "ALL PASS" : "FAILURES: " + fail) + " / " + results.length);
