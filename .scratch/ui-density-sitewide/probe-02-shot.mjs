// .scratch/ui-density-sitewide/probe-02-shot.mjs — 全站逐页截图（每单的证据件）。
//
// 为什么要有它：这一轮改的是"看起来挤不挤 / 层级清不清楚"，门禁只能证明没改坏，
// **证明不了好不好看**。所以每单留一张该页的暗色整页图（用户拍板的口径），收尾再出一次
// 浅色全站巡检。
//
// 用的是与浏览器门禁**同一个真后端夹具**（`tests/browser/server.mjs`）：真库真母版、
// 端口由内核分配、跑完自己收——不碰用户默认的 8000，也不留孤儿进程。
//
// ⚠ 纪律（`docs/agents/local-environment.md` 第 2 节）：浏览器门禁 / 本脚本**不要与
// 全量 pytest 同时跑**（本机负载下会抖，读数不可信）。
//
// 用法（在仓库根）：
//     node .scratch/ui-density-sitewide/probe-02-shot.mjs 01-after            # 暗色，全部页签
//     node .scratch/ui-density-sitewide/probe-02-shot.mjs 09-light light      # 浅色，全部页签
//     node .scratch/ui-density-sitewide/probe-02-shot.mjs 03-dark dark generate,topic
//     $env:SHOT_WIDTH=1024; node .scratch/ui-density-sitewide/probe-02-shot.mjs 01-narrow dark generate,settings
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
const ALL_TABS = [
  "generate", "hwcheck", "topic", "code", "settings",
  "library", "reference", "pdf", "md", "master", "guide", "changelog",
];
const TABS = process.argv[4] ? process.argv[4].split(",") : ALL_TABS;

mkdirSync(OUT, { recursive: true });

const server = await startServer();
const browser = await chromium.launch();
try {
  for (const tab of TABS) {
    const page = await browser.newPage({ viewport: VIEWPORT });
    await page.goto(server.url + "/", { waitUntil: "domcontentloaded" });
    if (THEME === "light") {
      await page.evaluate(() => { document.documentElement.dataset.theme = "light"; });
    }
    await page.click(`nav button[data-tab="${tab}"]`);
    // 各页的数据是异步拉的；给足时间把首屏渲染完（截图是给人看的，宁可多等一拍）
    await page.waitForTimeout(1200);
    // 点页签会把页面滚下去；截图前回到顶部，几张对照图才对得齐
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.waitForTimeout(200);
    const base = join(OUT, `${TAG}-${THEME}-${tab}`);
    await page.screenshot({ path: `${base}-top.png` });
    await page.screenshot({ path: `${base}-full.png`, fullPage: true });
    console.log("shot:", base);
    await page.close();
  }
} finally {
  await browser.close();
  await server.stop();
}
