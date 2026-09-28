// .scratch/ui-density-sitewide/probe-09-shot-content.mjs
// 工单 09：「任何时候都看不见」的那两块，用夹具驱动拍出来（浅色 + 暗色各一张）。
//
// 为什么单独立一支：08 单的 24 张整页图（含浅色）**拍不到**这两块——
//   · `.distill-progress`（提炼进度区）：母版库 `#distill-progress` 与生成页 `#rec-progress`
//     两个实例**都默认 `hidden`**，只有真跑一次提炼才出现；
//   · `.ref-files-*`（跨页弹层壳）：参考库 / 赛题库 / md / pdf / 代码页共用，**只在弹层里**。
// 07 账第 2 条点名"浅色巡检要看这两处"，08 账第 7 条承认落空 —— 这一支把洞补上。
//
// **每张图的"产品渲染路径"各占多少，如实写在这里**（照 05 单 probe-05c 的规矩）：
//   · 参考条目详情弹层：**整段都是产品渲染路径**——点真表格行的「详情」，走
//     `ui/reference.js` 的 `viewReferenceDetail()`，文件清单来自本机 API（`/api/references/:id/files`），
//     **零外网**。
//   · 提炼进度区：**结构是产品的**（`index.html` 里的 `#distill-progress` 原样 DOM），
//     **文字是夹具**——更新它的那几个函数（`setStep` / `updateBatch` / `addLogLine`）是
//     `ui/master.js` 的模块私有件、没有导出，探针照它们写下的 DOM 形态复现一遍。
//     所以这张图能证明的是"**这一块的样式在浅色下长什么样**"，**不能**证明"提炼流程跑通了"。
//
// ⚠ 纪律：不要与全量 pytest 并发跑（本支要起真后端 + 浏览器）。主题参数**用逗号**
//   （代码是 `split(",")`；写 `light|dark` 不会报错、只会拍出主题没生效的图——
//   09 单评审 Standards 抓到头里那句写成 `light|dark` 的坑）。
//
//     node .scratch/ui-density-sitewide/probe-09-shot-content.mjs 09 light,dark
import { mkdirSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";
import { startServer } from "../../tests/browser/server.mjs";

const HERE = fileURLToPath(new URL("./", import.meta.url));
const OUT = join(HERE, "shots");
const TAG = process.argv[2] || "09";
const THEMES = (process.argv[3] || "light,dark").split(",");
const VIEWPORT = { width: Number(process.env.SHOT_WIDTH || 1600), height: 1000 };

mkdirSync(OUT, { recursive: true });
const server = await startServer();
const browser = await chromium.launch();

async function shootBoth(page, name) {
  for (const theme of THEMES) {
    await page.evaluate((t) => { document.documentElement.dataset.theme = t; }, theme);
    await page.waitForTimeout(350);
    const path = join(OUT, `${TAG}-${theme}-${theme}-${name}.png`);
    await page.screenshot({ path });
    console.log("shot:", path);
  }
}

try {
  const page = await browser.newPage({ viewport: VIEWPORT });
  page.on("dialog", (d) => d.dismiss());
  await page.goto(server.url + "/", { waitUntil: "domcontentloaded" });

  // ---- ① 参考条目详情弹层（.ref-files-*，全真：真行 + 真端点 + 真渲染）----
  await page.click('nav button[data-tab="reference"]');
  await page.waitForSelector("#ref-rows [data-ref-view]", { timeout: 20000 });
  const rows = await page.locator("#ref-rows tr").count();
  await page.locator("#ref-rows [data-ref-view]").first().click();
  await page.waitForSelector(".ref-files-modal", { state: "visible", timeout: 10000 });
  await page.waitForTimeout(600);
  const modal = await page.evaluate(() => {
    const m = document.querySelector(".ref-files-modal");
    const cs = getComputedStyle(m);
    return { rows: document.querySelectorAll("#ref-rows tr").length,
             files: document.querySelectorAll(".ref-files-list li").length,
             filter: !!document.querySelector(".ref-files-filter"),
             modalBorder: cs.borderTopWidth,
             filterBorder: (document.querySelector(".ref-files-filter")
               ? getComputedStyle(document.querySelector(".ref-files-filter")).borderTopWidth : "-") };
  });
  console.log("参考条目详情：", JSON.stringify(modal));
  if (!modal.files) throw new Error("文件清单是空的——这一张证明不了 .ref-files-list 的样子，停手");
  if (modal.modalBorder !== "1px") throw new Error(`弹层外壳那一层没了（${modal.modalBorder}）`);
  if (modal.filterBorder !== "1px") throw new Error(`过滤输入框的框没了（${modal.filterBorder}）`);
  await shootBoth(page, "reference-detail-modal");
  await page.keyboard.press("Escape");
  await page.evaluate(() => document.querySelector(".ref-files-overlay")?.remove());

  // ---- ② 提炼进度区（.distill-progress，结构真 / 文字夹具）----
  await page.click('nav button[data-tab="master"]');
  await page.waitForTimeout(500);
  const prog = await page.evaluate(() => {
    const box = document.getElementById("distill-progress");
    if (!box) return { ok: false };
    box.classList.remove("hidden");
    // 以下 DOM 写法逐条对应 ui/master.js 的 setStep / updateBatch / addLogLine
    const steps = box.querySelectorAll("#prog-stepper .step");
    const conns = box.querySelectorAll("#prog-stepper .connector");
    steps.forEach((el, i) => {
      el.classList.remove("done", "active");
      el.querySelector(".dot").textContent = i < 2 ? "✓" : String(i + 1);
      if (i < 2) el.classList.add("done");
      else if (i === 2) el.classList.add("active");
    });
    conns.forEach((el, i) => el.classList.toggle("done", i < 2));
    document.getElementById("prog-batch-text").textContent = "摘要 第 3/8 批 · 已读 42/120";
    document.getElementById("prog-bar").classList.remove("hidden");
    document.getElementById("prog-bar-fill").style.width = "35%";
    const badge = document.getElementById("prog-badge");
    badge.classList.remove("hidden");
    badge.textContent = "有 2 处需要补问";
    document.getElementById("prog-timer-total").textContent = "总用时 03:12";
    document.getElementById("prog-timer-call").textContent = "当前调用已等待 00:07";
    document.getElementById("prog-log-count").textContent = "（6 条）";
    const log = document.getElementById("prog-log");
    log.innerHTML = [
      ["", "扫描完成：12 个工程 · 判定 Keil 9 / CCS 3"],
      ["batch", "摘要 第 1/8 批 · 已读 15/120"],
      ["batch", "摘要 第 2/8 批 · 已读 28/120"],
      ["error", "第 4 批有一次请求超时，已自动重试成功"],
      ["batch", "判定 第 3/8 批 · 已读 42/120"],
      ["", "正在补问：platform 字段有 2 处不一致"],
    ].map(([cls, text]) => `<div class="line${cls ? " " + cls : ""}">`
      + `<span class="t">23:0${Math.floor(Math.random() * 9)}:12</span>${text}</div>`).join("");
    const cs = getComputedStyle(box);
    return { ok: true, visible: !box.classList.contains("hidden"),
             boxBorder: cs.borderTopWidth,
             steps: box.querySelectorAll(".step").length,
             logs: box.querySelectorAll("#prog-log .line").length,
             stepFont: getComputedStyle(box.querySelector(".step")).fontSize,
             logFont: getComputedStyle(box.querySelector("#prog-log")).fontSize };
  });
  console.log("提炼进度区：", JSON.stringify(prog));
  if (!prog.ok || !prog.visible) throw new Error("进度区没显示出来，停手");
  if (prog.boxBorder !== "0px") throw new Error(`进度区的整圈框还在（${prog.boxBorder}）——07 单的去框没生效`);
  if (prog.stepFont !== "14px") throw new Error(`步骤名字号不是 14px（${prog.stepFont}）——07 单的档位没生效`);
  if (prog.logFont !== "13px") throw new Error(`日志字号不是 13px（${prog.logFont}）——07 单的档位没生效`);
  await shootBoth(page, "distill-progress");
  await page.close();
} finally {
  await browser.close();
  await server.stop();
}
