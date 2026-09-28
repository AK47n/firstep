// .scratch/ui-density-sitewide/probe-04-measure-treepane.mjs —— 树面板标题行**装不装得下**的量具。
//
// 为什么要有它：04 单把字号抬到台阶之后，`#tab-code` 左栏标题行（「文件」+ 三个动作按钮）
// 在 240px 默认树宽下看着被裁了一角（"选择文"）。"看着像"不算证据，这里按 rect 量：
//   · `.code-pane-title` 的 scrollWidth vs clientWidth（行内溢出多少）
//   · 每个 `.code-pane-action` 的 right 边界 vs 面板 right 边界（按钮越界多少）
// 同一支脚本在改前 / 改后各跑一次，两个数一对比就知道是不是本单顶出来的。
//
// 用的是真后端夹具（tests/browser/server.mjs），只开页面不开工程（空树就够）。
// ⚠ 纪律同其它探针：不要与全量 pytest 同时跑。
//
//     node .scratch/ui-density-sitewide/probe-04-measure-treepane.mjs
import { chromium } from "playwright";
import { startServer } from "../../tests/browser/server.mjs";

const server = await startServer();
const browser = await chromium.launch();
try {
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
  await page.goto(server.url + "/", { waitUntil: "domcontentloaded" });
  await page.click('nav button[data-tab="code"]');
  await page.waitForTimeout(1200);

  const data = await page.evaluate(() => {
    const pane = document.querySelector(".code-pane-tree");
    const title = pane && pane.querySelector(".code-pane-title");
    if (!pane || !title) return { error: "找不到 .code-pane-tree / .code-pane-title" };
    const pr = pane.getBoundingClientRect();
    const btns = [...title.querySelectorAll(".code-pane-action")].map((b) => {
      const r = b.getBoundingClientRect();
      return {
        text: b.textContent.trim(),
        left: Math.round(r.left), right: Math.round(r.right), width: Math.round(r.width),
        overflowPx: Math.round(r.right - pr.right),
        fontSize: getComputedStyle(b).fontSize,
      };
    });
    const titleEl = title.querySelector("h2, h3, span, strong") || title;
    return {
      paneWidth: Math.round(pr.width),
      paneRight: Math.round(pr.right),
      titleScrollW: title.scrollWidth,
      titleClientW: title.clientWidth,
      rowOverflowPx: title.scrollWidth - title.clientWidth,
      titleFont: getComputedStyle(titleEl).fontSize,
      buttons: btns,
    };
  });
  console.log(JSON.stringify(data, null, 2));
  await page.close();
} finally {
  await browser.close();
  await server.stop();
}
