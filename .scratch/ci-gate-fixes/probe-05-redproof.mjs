// probe-05-redproof.mjs — 工单 ci-gate-fixes/05 的**确定性红证**（秒级回路）。
//
// ## 它证什么
//
// 红那一轮的机制（定性读数见工单 Comments：`probe-05-catch2-logs/suite-05-red.txt`）：
// 新文档 head 内联脚本那一发 `POST /api/tabs/register` **派发在一条不可用的连接上**
// （浏览器从池里取到旧文档留下的、已被服务端按 keep-alive 关掉的空闲连接），
// 于是它以 `net::ERR_CONNECTION_REFUSED` / `ERR_CONNECTION_RESET` 当场失败；
// 而那一发**没有重试**（`fetch(...).catch(() => {})`）⇒ 登记永远没发生 ⇒
// 旧文档的 `bye` 把注册表清空后，1.5 秒宽限到点 ⇒ 应用自杀 ⇒ 页面 30 秒超时。
//
// 本探针把**那一发的失败**确定性地造出来（`page.route` 拦 register 并 `abort("failed")`
// 一次 = 传输层失败，不是 HTTP 错误码），其余一律真跑（真后端 + 真 Chromium + 真启动器模式）。
//
// **判据（就是这一条）**：一次失败的登记**之后**，服务必须还活着、页面必须还能用。
//   · 修复前：红（服务自杀 / 页面永远等不到可用）。
//   · 修复后：绿（重试那一发落在新连接上，登记成立）。
// **它不碰"最后离开 → 自停"**：那条不变量由 `launcher-reload.spec.mjs` 用例 C 照旧验
// （本探针不改产品语义，只改登记的健壮性）。
//
// ## 「一次」是怎么算的
//
// 只让 `reload` **之后**的第一发 register 失败。reload 之前那一发（首次加载的登记）照常放行
// ——所以在旧文档 `pagehide` 之前，注册表里**有**它的登记，"服务自杀"只可能来自"新文档那发
// 丢 + 旧文档 bye"这一条链，而不是"从来没人登记过"。
//
// 跑法：node .scratch/ci-gate-fixes/probe-05-redproof.mjs
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";
import { serverAlive, startServer } from "../../tests/browser/server.mjs";

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const WEBAPP_PY = fileURLToPath(
  new URL("../../src/contest_generator/webapp.py", import.meta.url));
const GRACE_MS = Number(
  /^_EXIT_GRACE\s*=\s*([0-9.]+)/m.exec(readFileSync(WEBAPP_PY, "utf8"))[1]) * 1000;
// 观测窗口：宽限 + 余量（判决只需"宽限过去之后服务还在不在"）
const WATCH_MS = GRACE_MS + 4000;

const server = await startServer({ launcher: true });
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
const t = {};
let dropNext = false;
let dropped = 0;

page.on("requestfailed", (r) => {
  const p = new URL(r.url()).pathname;
  if (p.endsWith("/register") && t.reloadStart) {
    t.regFailedAt ??= Date.now() - t.reloadStart;
  }
});

try {
  await page.route("**/api/tabs/register", async (route) => {
    if (dropNext) {
      dropNext = false;
      dropped++;
      await route.abort("failed");        // 传输层失败：与现场那发同签名
      return;
    }
    await route.continue().catch(() => {});
  });

  await page.goto(server.url + "/", { waitUntil: "domcontentloaded" });
  await page.waitForFunction(
    () => document.querySelectorAll("#platforms .platform-card").length > 0,
    undefined, { timeout: 60000 });

  // ① 让新文档那一发登记失败（只一发）。
  dropNext = true;
  t.reloadStart = Date.now();
  await page.reload({ waitUntil: "domcontentloaded", timeout: 30000 })
    .then(() => { t.reloadOk = Date.now() - t.reloadStart; })
    .catch((e) => { t.reloadErr = e.message.split("\n")[0]; });

  // ② 宽限过去了：服务还在吗？（产品不变量：宽限窗口本身就是"给新页面的时间"）
  await sleep(WATCH_MS);
  const alive = await serverAlive(server.url);
  const exited = server.proc.exitCode;
  let pageUsable = false;
  try {
    pageUsable = await page.evaluate(
      () => document.querySelectorAll("#platforms .platform-card").length > 0);
  } catch (e) { pageUsable = false; }

  const registers = server.log().split("POST /api/tabs/register").length - 1;
  console.log(`宽限 ${GRACE_MS}ms / 观测窗口 ${WATCH_MS}ms`);
  console.log(`  造出来的失败：${dropped} 发（期望 1）${t.regFailedAt ? `，@+${t.regFailedAt}ms` : ""}`);
  console.log(`  reload：${t.reloadOk ? `OK ${t.reloadOk}ms` : `失败 ${t.reloadErr || "?"}`}`);
  console.log(`  后端：${exited === null ? "活着" : `已退出 code=${exited}`} / health=${alive}`);
  console.log(`  页面可用：${pageUsable} / 服务端收到的 register 次数：${registers}`);

  const ok = dropped === 1 && exited === null && alive && pageUsable;
  console.log(ok
    ? "\n[红证] 绿：一次失败的登记之后服务活着、页面可用 —— 重试起作用了"
    : "\n[红证] 红：一次失败的登记把应用自己关掉了（register 丢失 ⇒ 宽限到点 ⇒ 自杀）");
  process.exitCode = ok ? 0 : 1;
} finally {
  await browser.close().catch(() => {});
  await server.stop().catch(() => {});
}
