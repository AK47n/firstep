// .scratch/ui-density-sitewide/probe-02c-shot-code-open.mjs —— 代码页「**打开了一个工程**」态整页图。
//
// 为什么还要一支：票面要求本页的暗色整页图**含"打开了一个工程"那一态**，而
// `probe-02-shot.mjs` 只点页签、不打开任何目录（拍到的永远是空态"点左侧文件在编辑器中打开"）。
// 这一支照 `tests/browser/code-tree-click.spec.mjs` 的既有跑法：真生成一个最小 stm32 工程
// （**题面留空 = 零 LLM**，main_c 必填，输出目录手输进临时根），再用代码页自己导出的桥
// `openCodeViewer(dir)`（`static/js/ui/codeview.js`，浏览器拿不到绝对路径的「选择文件夹」
// 走的就是它）打开那棵树，点开一个文件，让树 / 标签条 / 编辑器 / 状态条四处都**有内容**。
//
// 用的是同一套真后端夹具（`tests/browser/server.mjs`）：真库真母版、端口内核分配、跑完自收。
// ⚠ 纪律同 `probe-02-shot.mjs`：不要与全量 pytest 同时跑。
//
// 用法（在仓库根）：
//     node .scratch/ui-density-sitewide/probe-02c-shot-code-open.mjs 04-after dark
//
// 「改前」那一张怎么来的（可复现）：把 `src/contest_generator/static/index.html` 换回固定点
// （`git checkout 76daca48 -- src/contest_generator/static/index.html`）→ 跑同一支脚本
// tag 用 `04-before` → 再把工作树那版拷回来。**别在跑门禁/评审的同时做这个替换**。
import { existsSync, mkdirSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";
import { startServer } from "../../tests/browser/server.mjs";

const HERE = fileURLToPath(new URL("./", import.meta.url));
const OUT = join(HERE, "shots");
const TAG = process.argv[2] || "shot";
const THEME = process.argv[3] || "dark";
const VIEWPORT = { width: Number(process.env.SHOT_WIDTH || 1600), height: 1000 };

mkdirSync(OUT, { recursive: true });
const work = mkdtempSync(join(tmpdir(), "ui-density-code-shot-"));
const outDir = join(work, "proj");

const server = await startServer();
const browser = await chromium.launch();
try {
  const page = await browser.newPage({ viewport: VIEWPORT });
  page.on("dialog", (d) => d.dismiss());
  await page.goto(server.url + "/", { waitUntil: "domcontentloaded" });
  if (THEME === "light") {
    await page.evaluate(() => { document.documentElement.dataset.theme = "light"; });
  }

  // ---- 前置：真生成一个最小工程（与 tests/browser/code-tree-click.spec.mjs 同一跑法）----
  await page.locator("#platforms .platform-card", { hasText: "STM32" }).first().click();
  await page.waitForFunction(() => document.querySelectorAll("#module-grid .module-card").length > 0);
  await page.locator('#module-grid .module-card[data-add="motor"]').click();
  await page.waitForFunction(() => !document.getElementById("btn-expand").disabled,
    undefined, { timeout: 30000 });
  await page.uncheck("#desktop-topic-output").catch(() => {});
  await page.fill("#problem", "");                                // 题面留空 = 零 LLM
  await page.fill("#output-dir", outDir);
  await page.fill("#main-c", "int main(void) { return 0; }");
  await page.waitForTimeout(200);
  await page.click("#btn-generate");
  await page.waitForFunction(() => !document.getElementById("btn-generate").disabled,
    undefined, { timeout: 180000 });
  // **前置不成立就别按快门**（评审 Standards：原来只 console.log 一行，拍出一张空页也没人拦）
  if (!existsSync(join(outDir, "main.c"))) {
    throw new Error(`生成没落盘 main.c（${outDir}）——后面拍到的会是空树空编辑器，停手`);
  }
  console.log(`生成终态：main.c 落盘 = true`);

  // ---- 打开代码页并载入那棵真工程树 ----
  await page.click('nav button[data-tab="code"]');
  await page.evaluate(async (dir) => {
    const mod = await import("/js/ui/codeview.js");
    mod.openCodeViewer(dir);
  }, outDir);
  await page.waitForFunction(
    () => document.querySelectorAll("#code-tree .code-tree-file button").length > 0,
    undefined, { timeout: 30000 });
  // 点开一个 .c 文件（有 .c 就点 .c，没有就点第一个），让标签条 / 编辑器 / 状态条都有内容
  const pick = page.locator('#code-tree .code-tree-file button', { hasText: ".c" }).first();
  if (await pick.count()) await pick.click();
  else await page.locator("#code-tree .code-tree-file button").first().click();
  await page.waitForTimeout(1200);
  // 编辑器真的有内容才拍（评审 Standards：只验 DOM 存在性会拍出"空编辑器 + 满树"的假态）
  const lines = await page.locator(".code-gutter-line").count();
  const tabCount = await page.locator("#code-tabs .code-tab").count();
  console.log(`编辑器行数 = ${lines}；标签数 = ${tabCount}`);
  if (lines === 0 || tabCount === 0) {
    throw new Error("编辑器/标签条是空的——「打开了一个工程」那一态没成立，停手（别把空态图当证据）");
  }

  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(300);
  await page.screenshot({ path: join(OUT, `${TAG}-${THEME}-code-open-top.png`) });
  await page.screenshot({ path: join(OUT, `${TAG}-${THEME}-code-open-full.png`), fullPage: true });
  console.log("shot:", join(OUT, `${TAG}-${THEME}-code-open-full.png`));

  // 快捷键帮助浮层（`.code-shortcuts-group` 16 / `.code-kbd` 12 的落点）——弹层自己算一屏，
  // 票尾的逐层清单要能对着它说话；拍不到就如实记一笔，不假装看过
  const scBtn = page.locator("#btn-code-shortcuts");
  if (await scBtn.count()) {
    await scBtn.click();
    await page.waitForSelector(".code-shortcuts-overlay", { state: "visible", timeout: 5000 });
    await page.waitForTimeout(400);
    await page.screenshot({ path: join(OUT, `${TAG}-${THEME}-code-open-shortcuts.png`) });
    console.log("shot:", join(OUT, `${TAG}-${THEME}-code-open-shortcuts.png`));
    await page.keyboard.press("Escape");
    await page.waitForTimeout(300);
  } else {
    throw new Error("找不到 #btn-code-shortcuts——快捷键浮层拍不到（它是 16/12 两档的落点，别静默跳过）");
  }

  // 分段图（可选）：SHOT_AT="#code-bottom-panels,.code-layout"
  const ats = (process.env.SHOT_AT || "").split(",").map((s) => s.trim()).filter(Boolean);
  for (const [i, sel] of ats.entries()) {
    const el = page.locator(sel).first();
    if (!(await el.count())) { console.log(`  ⚠ 找不到 ${sel}`); continue; }
    await el.scrollIntoViewIfNeeded();
    await page.waitForTimeout(250);
    const p = join(OUT, `${TAG}-${THEME}-code-open-seg${i + 1}.png`);
    await page.screenshot({ path: p });
    console.log("seg:", p, `(${sel})`);
  }
  await page.close();
} finally {
  await browser.close();
  await server.stop();
  rmSync(work, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 });
}
