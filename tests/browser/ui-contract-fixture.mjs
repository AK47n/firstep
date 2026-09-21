// ui-contract-fixture.mjs — ui 行为契约的共用助手（工单 ui-dom-contract-gate/04）。
//
// 为什么单列一个文件：三个契约用例都要"开一张干净的页面 + 等启动完成 + 真点页签"，
// 而其中两处细节是**踩出来的**（不是从文档抄的）——
//   ① 要等装载根（static/js/boot.js，工单 frontend-boot-module/02 起）的启动区跑过
//      （平台卡渲染出来 = 所有 init 都已调用），不等就点会偶发"点了没反应"
//      （导航分发还没绑上）；
//   ② 点页签必须**真点**（`page.click`）而不是 `classList.add`——
//      契约的一多半正是"监听器真的绑上了"，自己改类名等于跳过被测对象。
//
// 夹具服务沿用 tests/browser/server.mjs（真后端；每个 spec 各向内核要一个空闲端口）。
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

/**
 * 打开真页面并等启动完成。返回 { page, problems }（problems = 页面级异常收集器）。
 *
 * `problems` 只收**页面级异常**（pageerror）与**非资源类**的 console 错误：
 * 真后端在"没配 AI key / 没填题面"的测试态下，若干端点会如实回 400（例如
 * `/api/generate/preview-dir` 缺必填字段），浏览器于是打一行
 * `Failed to load resource … 400` —— 那是**既有的产品行为**，不是本层要断的契约
 * （先例：`module-intro.spec.mjs` 的 KNOWN_NOISE 同样只过滤这一类）。
 * 真正的接线错误会以 pageerror 出现（模块求值炸了 / 事件处理里抛了），那一条照收。
 */
const RESOURCE_NOISE = "Failed to load resource";

export async function openApp(browser, server, { clearStorage = false } = {}) {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const problems = [];
  page.on("pageerror", (e) => problems.push("pageerror: " + e.message));
  page.on("console", (m) => {
    if (m.type() !== "error") return;
    const text = m.text();
    if (text.includes(RESOURCE_NOISE)) return;   // 见上：既有 400，不是接线问题
    problems.push("console: " + text);
  });
  await page.goto(server.url + "/", { waitUntil: "domcontentloaded" });
  if (clearStorage) {
    await page.evaluate(() => localStorage.clear());
    await page.reload({ waitUntil: "domcontentloaded" });
  }
  await ready(page);
  return { page, problems };
}

/** 等"启动完成"：平台卡渲染出来 ⟺ index.html 启动区跑过（所有 init 已调用）。 */
export async function ready(page) {
  await page.waitForFunction(
    () => document.querySelectorAll("#platforms .platform-card").length > 0,
    undefined, { timeout: 30000 });
}

/** 点顶部页签（真点击：契约有一半是"监听器绑上了"）。 */
export async function gotoNavTab(page, tab) {
  await page.click(`nav button[data-tab="${tab}"]`);
  await page.waitForSelector(`#tab-${tab}`, { state: "visible" });
}

/**
 * 从**产品源码**里抠出某个 id 的**静态容器**（判据锚点取自产品标记，不手抄）。
 * 用途：某条契约要断言"这个容器里的东西"时，别在用例里再写一遍选择器字面量。
 *
 * 取数面 = index.html（标记）∪ boot.js（装载根正文；工单 frontend-boot-module/02 把宿主
 * 脚本块搬去了那里）。
 */
export function staticAnchor(needle) {
  const html = readFileSync(fileURLToPath(
    new URL("../../src/contest_generator/static/index.html", import.meta.url)), "utf8");
  const boot = readFileSync(fileURLToPath(
    new URL("../../src/contest_generator/static/js/boot.js", import.meta.url)), "utf8");
  return html.includes(needle) || boot.includes(needle);
}
