// probe-02-close-page.mjs — "关掉最后一个页面 → 服务自己停"这条路径，在真浏览器里**到底怎么走**
// （工单 launcher-exit-race/04 的取证：浏览器门禁里用例 C 第一版用 `page.close()` 没关掉服务，
// 先量清楚是"信标没发出去"还是"服务端没退"，别猜）。
//
// 三种收尾方式各量一次（都在启动器模式下、真后端）：
//   ① `page.close()`                     —— playwright 默认（不跑 beforeunload）
//   ② `page.close({runBeforeUnload:true})` —— 让它跑卸载流程
//   ③ `page.goto("about:blank")`          —— 真导航离开（pagehide 一定有真实网络请求可刷）
// 每一轮都看两件事：服务端日志里有没有 `POST /api/tabs/bye`，进程有没有自己退出。
//
// ⚠ **每一轮都换一个干净的服务**（第一版没换，"③ 进程没退"这条读数会被误读）：①② 的收尾
// 方式根本不发 bye ⇒ 它们开的页面**一直留在注册表里**，于是轮到 ③ 时"最后一个页面"这个前提
// 已经不成立（注册表里还挂着前两轮的标签），进程当然不会退——那不是 ③ 的问题，是探针自己的
// 状态没清（工单 launcher-exit-race/04 的评审抓出这条口径）。这里要量的是"**只剩这一个页面
// 时**它离开会发生什么"，所以每轮各起一个服务、各开一个页面。
//
// 用法：node .scratch/launcher-exit-race/probe-02-close-page.mjs
import { chromium } from "playwright";
import { tee } from "./tee.mjs";
import { startServer } from "../../tests/browser/server.mjs";

tee(process.argv[1], process.argv.slice(2));

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const BYE_RE = /"POST \/api\/tabs\/bye HTTP\/1\.1"/;

const browser = await chromium.launch();

/** 收尾一次（每轮自带服务与页面）并判读：信标到了吗 / 进程退了吗。 */
async function observe(label, teardown) {
  const server = await startServer({ launcher: true });
  const page = await browser.newPage();
  await page.goto(server.url + "/", { waitUntil: "domcontentloaded" });
  await page.waitForFunction(
    () => document.querySelectorAll("#platforms .platform-card").length > 0,
    undefined, { timeout: 30000 });
  await sleep(200);                       // 让登记确实到达
  const before = server.log().length;
  const t0 = Date.now();
  let threw = null;
  try {
    await teardown(page);
  } catch (e) {
    threw = e.message;                    // 收尾方式自己抛错也要如实记
  }
  let exitMs = null;
  const deadline = Date.now() + 6000;
  while (Date.now() < deadline) {
    if (server.proc.exitCode !== null) { exitMs = Date.now() - t0; break; }
    await sleep(100);
  }
  const chunk = server.log().slice(before);
  console.log(`\n== ${label} ==`);
  console.log(`  收尾动作抛错：${threw === null ? "无" : threw}`);
  console.log(`  服务端收到 /api/tabs/bye：${BYE_RE.test(chunk) ? "是" : "**否**"}`);
  console.log(`  进程自己退出：${exitMs === null ? "**否**（6 秒内没退）" : `是（${exitMs}ms）`}`);
  if (!BYE_RE.test(chunk)) {
    const tail = chunk.split("\n").filter((l) => l.includes("tabs") || l.includes("GET /"))
      .slice(-4).join("\n      ");
    console.log(`  该轮服务端日志里与标签/首页相关的行：\n      ${tail || "（没有）"}`);
  }
  await page.close().catch(() => {});
  await server.stop();
  return exitMs !== null;
}

console.log("== 关掉/离开最后一个页面的三条路径（启动器模式，**每轮各起一个干净服务**）==");

await observe("① page.close()（playwright 默认）", (p) => p.close());
await observe("② page.close({runBeforeUnload:true})", (p) => p.close({ runBeforeUnload: true }));
await observe('③ page.goto("about:blank")（真导航离开）', (p) => p.goto("about:blank"));

await browser.close();
console.log("\n（每个服务都已由本探针收掉）");
