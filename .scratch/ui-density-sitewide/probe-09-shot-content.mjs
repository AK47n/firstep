// .scratch/ui-density-sitewide/probe-09-shot-content.mjs
// 工单 09 / 10：「任何时候都看不见」的那几块，用夹具驱动拍出来（浅色 + 暗色各一张）。
//
// 为什么单独立一支：08 单的 24 张整页图（含浅色）**拍不到**这几块——
//   · `.distill-progress`（提炼进度区，母版库 `#distill-progress`）：默认 `hidden`；
//   · `.distill-progress` 同族的 `#rec-progress`（生成页推荐进度）：默认 `hidden`；
//   · `.ref-files-*`（跨页弹层壳）：参考库 / 赛题库 / md / pdf / 代码页共用，**只在弹层里**。
//
// **每张图走的是哪条路径，如实写在这里**（照 05 单 probe-05c 的规矩）：
//   · 参考条目详情弹层：**全真**——点真表格行的「详情」，走 `ui/reference.js` 的
//     `viewReferenceDetail()`，文件清单来自本机 API，**零外网**。
//   · 提炼进度区 / 推荐进度区：**走产品自己的渲染路径**（工单 10 开的测试钩子）——
//     `window.masterProgressHooks`（`start` / `setStep` / `updateBatch` / `addLogLine` / `state`）
//     与 `window.recProgressHooks`（`start` / `handleEvent` / `state`）：探针往里塞**夹具数据**
//     （阶段 / 批次 / 计数）与**合成的 SSE 事件**，DOM 由产品自己写。
//     **数据是夹具、路径是产品的**；它证明"这一块的样式与档位在两种主题下长什么样"，
//     **不证明**"提炼 / 推荐流程真能跑通"（那要真调模型，见 spec 的零网络纪律）。
//     ⚠ 09 单时还没有钩子，那一版是"照产品写下的 DOM 形态复现"；10 单换成钩子。
//
// ⚠ 纪律：不要与全量 pytest 并发跑（本支要起真后端 + 浏览器）。主题参数**用逗号**
//   （代码是 `split(",")`；写 `light|dark` 不会报错、只会拍出主题没生效的图——
//   09 单评审 Standards 抓到头里那句写成 `light|dark` 的坑）。
//
//     node .scratch/ui-density-sitewide/probe-09-shot-content.mjs 10 light,dark
import { mkdirSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";
import { startServer } from "../../tests/browser/server.mjs";

const HERE = fileURLToPath(new URL("./", import.meta.url));
const OUT = join(HERE, "shots");
const TAG = process.argv[2] || "10";
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
  await page.locator("#ref-rows [data-ref-view]").first().click();
  await page.waitForSelector(".ref-files-modal", { state: "visible", timeout: 10000 });
  await page.waitForTimeout(600);
  const modal = await page.evaluate(() => ({
    files: document.querySelectorAll(".ref-files-list li").length,
    modalBorder: getComputedStyle(document.querySelector(".ref-files-modal")).borderTopWidth,
    filterBorder: getComputedStyle(document.querySelector(".ref-files-filter")).borderTopWidth,
  }));
  console.log("参考条目详情：", JSON.stringify(modal));
  if (!modal.files) throw new Error("文件清单是空的——这一张证明不了 .ref-files-list 的样子，停手");
  if (modal.modalBorder !== "1px") throw new Error(`弹层外壳那一层没了（${modal.modalBorder}）`);
  if (modal.filterBorder !== "1px") throw new Error(`过滤输入框的框没了（${modal.filterBorder}）`);
  await shootBoth(page, "reference-detail-modal");
  await page.evaluate(() => document.querySelector(".ref-files-overlay")?.remove());

  // ---- ② 提炼进度区（.distill-progress，母版库；走 10 单的钩子 = 产品渲染路径）----
  await page.click('nav button[data-tab="master"]');
  await page.waitForTimeout(400);
  const prog = await page.evaluate(() => {
    const h = window.masterProgressHooks;
    if (!h) return { ok: false, why: "masterProgressHooks 没挂上（钩子要在 initMasterWorkflow 里）" };
    h.start();                       // 产品入口：显示 + 复位 + setStep(0) + updateBatch()
    const p = h.state;               // ——以下全是夹具数据
    p.phase = "summary"; p.phaseTotal = { summary: 120, decide: 0 };
    p.batchIndex = 3; p.batchCount = 8; p.processed = 42;
    h.updateBatch();                 // 产品自己写 DOM
    h.setStep(2, "active");
    document.getElementById("prog-badge").classList.remove("hidden");
    document.getElementById("prog-badge").textContent = "有 2 处需要补问";
    [
      ["", "扫描完成：12 个工程 · 判定 Keil 9 / CCS 3"],
      ["batch", "摘要 第 1/8 批 · 已读 15/120"],
      ["batch", "摘要 第 2/8 批 · 已读 28/120"],
      ["error", "第 4 批有一次请求超时，已自动重试成功"],
      ["batch", "判定 第 3/8 批 · 已读 42/120"],
      ["", "正在补问：platform 字段有 2 处不一致"],
    ].forEach(([cls, text]) => h.addLogLine(cls, text));
    const box = document.getElementById("distill-progress");
    return { ok: true, visible: !box.classList.contains("hidden"),
             boxBorder: getComputedStyle(box).borderTopWidth,
             steps: box.querySelectorAll(".step").length,
             logs: box.querySelectorAll("#prog-log .line").length,
             stepFont: getComputedStyle(box.querySelector(".step")).fontSize,
             logFont: getComputedStyle(box.querySelector("#prog-log")).fontSize };
  });
  console.log("提炼进度区（走钩子）：", JSON.stringify(prog));
  if (!prog.ok) throw new Error(prog.why);
  if (!prog.visible || prog.steps !== 4) throw new Error("进度区没显示出来 / 步骤数不对，停手");
  if (prog.boxBorder !== "0px") throw new Error(`进度区的整圈框还在（${prog.boxBorder}）——07 单的去框没生效`);
  if (prog.stepFont !== "14px") throw new Error(`步骤名字号不是 14px（${prog.stepFont}）——07 单的档位没生效`);
  if (prog.logFont !== "13px") throw new Error(`日志字号不是 13px（${prog.logFont}）——07 单的档位没生效`);
  await shootBoth(page, "distill-progress");

  // ---- ③ 推荐进度区（#rec-progress，生成页；喂合成 SSE 事件，产品事件表自己写 DOM）----
  await page.click('nav button[data-tab="generate"]');
  await page.waitForTimeout(400);
  const rec = await page.evaluate(() => {
    const h = window.recProgressHooks;
    if (!h) return { ok: false, why: "recProgressHooks 没挂上（钩子要在 renderModulePool 里）" };
    h.start();
    h.handleEvent("start", JSON.stringify({ stage: "正在读题面并归纳功能需求…" }));
    h.handleEvent("round", JSON.stringify({ round: 3, round_total: 8 }));
    const box = document.getElementById("rec-progress");
    return { ok: true, visible: !box.classList.contains("hidden"),
             boxBorder: getComputedStyle(box).borderTopWidth,
             text: document.getElementById("rec-prog-text").textContent,
             barShown: !document.getElementById("rec-bar").classList.contains("hidden"),
             textFont: getComputedStyle(document.getElementById("rec-prog-text")).fontSize };
  });
  console.log("推荐进度区（喂合成事件）：", JSON.stringify(rec));
  if (!rec.ok) throw new Error(rec.why);
  if (!rec.visible || !rec.barShown || !rec.text.includes("第 3/8 轮")) {
    throw new Error("事件没走到 DOM 上（面板没显示 / 进度条没出 / 文案不对），停手");
  }
  if (rec.boxBorder !== "0px") throw new Error(`推荐进度区的整圈框还在（${rec.boxBorder}）`);
  await shootBoth(page, "rec-progress");
  await page.close();
} finally {
  await browser.close();
  await server.stop();
}
