// .scratch/ui-density/probe-02-shot.mjs — 检测页整页截图（工单 ui-density/01/03 的证据件）。
//
// 为什么要有它：这一轮改的是"看起来挤不挤"，门禁只能证明没改坏，**证明不了好不好看**。
// 所以留两份人眼可查的对照：`before`（改前）与 `after`（改后），各拍
// 暗/亮 × 空态/选了器件 四张，每张再附一张"只看首屏"的（整页很高，缩略后看不清字号）。
//
// 用的是与浏览器门禁**同一个真后端夹具**（`tests/browser/server.mjs`）：真库真母版、
// 端口由内核分配、跑完自己收——不碰用户默认的 8000，也不留孤儿进程。
//
// 用法（在仓库根）：
//     node .scratch/ui-density/probe-02-shot.mjs after
//     node .scratch/ui-density/probe-02-shot.mjs before      # 配 git stash 用，见本目录 README
import { mkdirSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";
import { startServer } from "../../tests/browser/server.mjs";

const HERE = fileURLToPath(new URL("./", import.meta.url));
const OUT = join(HERE, "shots");
const TAG = process.argv[2] || "shot";
const VIEWPORT = { width: 1600, height: 1000 };

mkdirSync(OUT, { recursive: true });

const server = await startServer();
const browser = await chromium.launch();
try {
  for (const theme of ["dark", "light"]) {
    for (const state of ["empty", "picked"]) {
      const page = await browser.newPage({ viewport: VIEWPORT });
      await page.goto(server.url + "/", { waitUntil: "domcontentloaded" });
      if (theme === "light") {
        await page.evaluate(() => { document.documentElement.dataset.theme = "light"; });
      }
      await page.click('nav button[data-tab="hwcheck"]');
      await page.waitForSelector("#hwcheck-device-grid .module-card");
      if (state === "picked") {
        await page.click('[data-hwcheck-platform="mspm0"]');
        await page.waitForSelector('#hwcheck-device-grid [data-add="ml_mpu6050"]');
        await page.click('#hwcheck-device-grid [data-add="ml_mpu6050"]');
        // 等板侧视图（接线 / 冲突 / 顺序 / 检测计划）投影回来
        await page.waitForSelector("#hwcheck-sections .hwcheck-section", { timeout: 15000 })
          .catch(() => console.log("（提示：这一版没等到检测计划小节，可能投影慢或为空）"));
        await page.waitForTimeout(800);
      }
      await page.waitForTimeout(300);
      // 点器件/平台会把页面滚下去（click 自带 scrollIntoView）——截图前回到顶部，
      // 否则"首屏"拍到的是半路，两张对照图对不齐。
      await page.evaluate(() => window.scrollTo(0, 0));
      await page.waitForTimeout(200);
      const base = join(OUT, `${TAG}-${theme}-${state}`);
      await page.screenshot({ path: `${base}-top.png` });                 // 首屏
      await page.screenshot({ path: `${base}-full.png`, fullPage: true }); // 整页
      console.log("shot:", base);
      await page.close();
    }
  }
} finally {
  await browser.close();
  await server.stop();
}
