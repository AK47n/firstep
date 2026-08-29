// probe-04-entry.mjs — beginner-guide/04 实机探针（验收聚合）：
// 模拟全新手（route 改写 /api/state api_configured=false）→ 欢迎卡 full 态
// 含「先看新手指引」→ 点击进入教程页 → 四章/子页签/跳转动作核对 →
// 导航三组 9 键回归 → 亮暗主题截图 → 零 JS 错误。
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

// 模拟全新手：/api/state 的 api_configured 改 false（真实 fetch 后就地改 JSON）
await page.route("**/api/state", async (route) => {
  const resp = await route.fetch();
  const body = await resp.json();
  body.api_configured = false;
  await route.fulfill({ response: resp, json: body });
});

await page.goto("http://127.0.0.1:8000/", { waitUntil: "networkidle" });
await page.reload({ waitUntil: "networkidle" });

// 1. 欢迎卡 full 态：包含「先看新手指引」按钮
const welcomeVisible = await page.$eval("#welcome-card", (el) => !el.classList.contains("hidden"));
const guideBtn = await page.$("#welcome-card #btn-welcome-guide");
const guideBtnText = guideBtn ? await guideBtn.textContent() : null;
check("欢迎卡 full 态显示", welcomeVisible);
check("full 态含「先看新手指引」按钮", !!guideBtn && guideBtnText === "先看新手指引", String(guideBtnText));
const fullHasKey = await page.$("#welcome-card #btn-welcome-goto-key");
check("full 态仍含去配置 key 按钮", !!fullHasKey);

// 2. 点「先看新手指引」→ 教程页
await page.click("#welcome-card #btn-welcome-guide");
const guideActive = await page.$eval("#tab-guide", (s) => s.classList.contains("active"));
const genHidden = await page.$eval("#tab-generate", (s) => !s.classList.contains("active"));
check("点击后教程页激活、生成页收起", guideActive && genHidden);

// 3. 四章内容齐（切换四个子页签核对标题）
const titles = {};
for (const key of ["prepare", "build", "compile", "deliver"]) {
  await page.click('#guide-tabs .guide-tab[data-guide-tab="' + key + '"]');
  titles[key] = await page.$eval("#guide-panel-" + key + " h3.guide-chapter-title", (e) => e.textContent);
}
check("四章标题齐", !!titles.prepare && !!titles.build && !!titles.compile && !!titles.deliver,
  Object.values(titles).map((t) => t.slice(0, 6)).join(" / "));

// 4. 跳转按钮抽样：去设置配 key（回归 gotoNavTab）
await page.click('#guide-tabs .guide-tab[data-guide-tab="prepare"]');
await page.click('#guide-panel-prepare .guide-jump[data-jump-tab="settings"]');
const settingsActive = await page.$eval("#tab-settings", (s) => s.classList.contains("active"));
check("教程「去设置」跳转生效", settingsActive);

// 5. 导航三组 9 键回归
const keys = await page.$$eval("header nav button[data-tab]", (els) => els.map((e) => e.dataset.tab));
check("导航含 guide 共 9 键", keys.length === 9 && keys.includes("guide"), "n=" + keys.length);
const groups = await page.$$eval("header nav .tab-group", (els) => els.map((e) => e.getAttribute("aria-label")));
check("导航三组", groups.join(",") === "做题,资料管理,指南", groups.join(","));

// 6. 截图（暗）+ 亮主题截图
await page.click('header nav button[data-tab="guide"]');
await page.screenshot({ path: ".scratch/beginner-guide/shot-04-welcome-dark.png", fullPage: true });
const themeBtn = await page.$("#btn-theme");
if (themeBtn) {
  await page.click("#btn-theme");
  await page.waitForTimeout(400);
  await page.screenshot({ path: ".scratch/beginner-guide/shot-04-guide-light.png", fullPage: true });
  check("亮暗主题截图完成", true);
} else {
  check("主题按钮缺失", false);
}
check("零页面 JS 错误", errors.length === 0, errors.slice(0, 3).join(" | "));

await browser.close();
const fail = results.filter((r) => !r.ok).length;
console.log((fail === 0 ? "ALL PASS" : "FAILURES: " + fail) + " / " + results.length);
