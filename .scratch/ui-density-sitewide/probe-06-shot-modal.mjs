// .scratch/ui-density-sitewide/probe-06-shot-modal.mjs —— 五页**详情弹层**那一张（工单 06）。
//
// 票面：「五页各一张暗色整页图入库（**详情弹层另出一张**）」。这一支拍**模块详情弹窗**——
// 它是五页里最厚的一个弹层（四问分段 / 推荐理由块 / 键值行 / 平台分段 / 引脚表 / 源码区），
// 06 单改它改得最多（`.mi-*` 一族 + 弹层标题那一档 + 三处去框）。
//
// 用的是同一套真后端夹具（`tests/browser/server.mjs`）：真库真母版、端口内核分配、跑完自收。
// ⚠ 纪律同其它探针：不要与全量 pytest 同时跑。
//
//     node .scratch/ui-density-sitewide/probe-06-shot-modal.mjs 06-after dark
import { mkdirSync } from "node:fs";
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
const server = await startServer();
const browser = await chromium.launch();
try {
  const page = await browser.newPage({ viewport: VIEWPORT });
  page.on("dialog", (d) => d.dismiss());
  await page.goto(server.url + "/", { waitUntil: "domcontentloaded" });
  if (THEME === "light") {
    await page.evaluate(() => { document.documentElement.dataset.theme = "light"; });
  }
  await page.click('nav button[data-tab="library"]');
  await page.waitForSelector("#lib-rows [data-info]", { timeout: 20000 });
  const rows = await page.locator("#lib-rows tr").count();
  console.log(`模块库行数 = ${rows}`);
  await page.locator("#lib-rows [data-info]").first().click();
  await page.waitForSelector(".module-info-modal", { state: "visible", timeout: 10000 });
  await page.waitForTimeout(600);
  const probe = await page.evaluate(() => {
    const m = document.querySelector(".module-info-modal");
    const cs = getComputedStyle(m);
    const reason = document.querySelector(".mi-reason");
    return { title: (document.querySelector(".module-info-title .slug") || {}).textContent,
             introSecs: document.querySelectorAll(".mi-intro-sec").length,
             plats: document.querySelectorAll(".mi-plat").length,
             modalBorder: cs.borderTopWidth,
             reasonBorder: reason ? getComputedStyle(reason).borderTopWidth : "-",
             platBorder: (document.querySelector(".mi-plat") ? getComputedStyle(document.querySelector(".mi-plat")).borderTopWidth : "-") };
  });
  console.log("弹层读数：", JSON.stringify(probe));
  if (!probe.introSecs) throw new Error("四问分段没渲染出来——拍到的不是有内容那一态，停手");
  // **弹层自己那一层要在**（06c 的 KEEP 第一项；评审 Standards 抓到这条原先只打印不断言）
  if (probe.modalBorder !== "1px") {
    throw new Error(`弹层外壳的框没了（${probe.modalBorder}）——一屏一层里的那一层不该被去掉`);
  }
  // 去框的两处（这一张图里够得着的两个）——**`.mi-reason` 只在"被推荐过"的模块上渲染**，
  // 打开的这一件没有就跳过（不当成失败：那不是"框还在"，是"这块没渲染"）
  for (const [what, v] of [["平台小卡", probe.platBorder], ["推荐理由块", probe.reasonBorder]]) {
    if (v === "-") { console.log(`  （${what}在这一次打开的模块上没有渲染，跳过）`); continue; }
    if (v !== "0px") throw new Error(`${what}还带着框（${v}）——06 的去框没生效`);
  }

  await page.screenshot({ path: join(OUT, `${TAG}-${THEME}-library-modal.png`) });
  console.log("shot:", join(OUT, `${TAG}-${THEME}-library-modal.png`));
  await page.close();
} finally {
  await browser.close();
  await server.stop();
}
