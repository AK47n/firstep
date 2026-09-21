// probe-00-order.mjs — 现场测量（工单 launcher-exit-race，spec 前的取证）：
// **F5 重载时，旧页面的告别与浏览器为新页面发出的请求，谁先到服务器？**
//
// 为什么要量这一条（而不是靠推理）：修法的骨架取决于它。
//   · 若"新页面的请求（GET / 或 register）总是先到" ⇒ 只要把 register 提前到模块图之前就够了；
//   · 若"可能反过来（旧页面的 bye 后到）" ⇒ 那个迟到的 bye 会把**刚登记的新页面**注销掉
//     —— 退出判据又回到"新页面必须再登记一次"，秒级竞态原样复现。必须给告别配一个
//     "我是哪一次加载"的令牌（旧文档的告别不许注销新文档的登记）。
//
// 两个取数面同时记（互相对照，避免只看一侧就下结论）：
//   · **浏览器侧**（playwright `page.on("request")`）：请求**发出**的顺序与相对时刻；
//   · **服务端侧**（uvicorn access log，夹具已捕获）：请求**被处理**的顺序（这才是竞态的真身）。
//
// 夹具沿用 tests/browser/server.mjs（真后端、内核分配端口、自带起停）。
// 本探针**开启动器模式**（`FIRSTEP_LAUNCHER=1`，就是用户双击 start-app.bat 的那条路）——
// 所以它测完自己收服务，且**收之前先确认服务还活着**（它可能就是被这条竞态关掉的）。
//
// 用法：node .scratch/launcher-exit-race/probe-00-order.mjs [--rounds 8]
import { chromium } from "playwright";
import { tee } from "./tee.mjs";
import { startServer } from "../../tests/browser/server.mjs";

tee(process.argv[1], process.argv.slice(2));

const args = process.argv.slice(2);
const ROUNDS = args.includes("--rounds") ? Number(args[args.indexOf("--rounds") + 1]) : 8;
// 夹具把 `...process.env` 透给子进程 —— 这里设一次，服务就以启动器模式起来
process.env.FIRSTEP_LAUNCHER = "1";

// 服务端日志里的请求行 → 只看这条竞态相关的三条（access log 的顺序 = 处理顺序）
const WATCH = [
  ["GET /", /"GET \/ HTTP\/1\.1" 200/],
  ["POST /api/tabs/bye", /"POST \/api\/tabs\/bye HTTP\/1\.1" 200/],
  ["POST /api/tabs/register", /"POST \/api\/tabs\/register HTTP\/1\.1" 200/],
];

function serverEvents(log) {
  const out = [];
  for (const line of log.split(/\r?\n/)) {
    for (const [name, re] of WATCH) if (re.test(line)) out.push(name);
  }
  return out;
}

async function alive(url) {
  try {
    const resp = await fetch(`${url}/api/health`);
    return resp.ok;
  } catch (e) {
    return false;
  }
}

const server = await startServer();
const browser = await chromium.launch();
const page = await browser.newPage();

let clientEvents = [];
let t0 = 0;
let round = 0;
page.on("request", (req) => {
  const path = new URL(req.url()).pathname;
  if (path !== "/" && path !== "/api/tabs/bye" && path !== "/api/tabs/register") return;
  clientEvents.push(`第 ${round} 轮：${req.method()} ${path} @+${Date.now() - t0}ms`);
});

console.log(`== 现场测量：F5 重载时「旧页面的 bye」与「新页面的请求」谁先到 ==`);
console.log(`   服务：${server.url}（FIRSTEP_LAUNCHER=1）；轮数 ${ROUNDS}\n`);

t0 = Date.now();
await page.goto(server.url + "/", { waitUntil: "domcontentloaded" });
await page.waitForFunction(
  () => document.querySelectorAll("#platforms .platform-card").length > 0,
  undefined, { timeout: 30000 });

// 首屏那一轮也记（它没有"旧页面"），从第二轮起才是重载
let before = server.log().length;
clientEvents = [];
const rounds = [];
for (let i = 1; i <= ROUNDS; i++) {
  round = i;
  t0 = Date.now();
  let ready = true;
  try {
    await page.reload({ waitUntil: "domcontentloaded" });
    await page.waitForFunction(
      () => document.querySelectorAll("#platforms .platform-card").length > 0,
      undefined, { timeout: 15000 });
  } catch (e) {
    // 服务被这条竞态关掉时，page.reload / waitForFunction 抛的就是 ERR_CONNECTION_REFUSED
    ready = false;
  }
  const logChunk = server.log().slice(before);
  before = server.log().length;
  const eventsServer = serverEvents(logChunk);
  const ok = await alive(server.url);
  if (!ok || !ready) {
    console.log(`✗ 第 ${i} 轮：服务/页面已经没了（ready=${ready} / health=${ok}）——**竞态命中**`);
    console.log(`   这一轮服务端处理顺序：${eventsServer.join(" → ") || "（没记到受关注的请求）"}`);
    rounds.push({ i, eventsServer, ms: Date.now() - t0, ok, ready });
    break;                                   // 服务没了，后面的轮次没有意义
  }
  rounds.push({ i, eventsServer, ms: Date.now() - t0, ok, ready });
}
console.log(`浏览器侧事件（请求**发出**的顺序；时间是相对各轮起点的近似）——共 ${clientEvents.length} 条：`);
for (const e of clientEvents) console.log(`   ${e}`);
console.log("");
for (const r of rounds) {
  console.log(`第 ${r.i} 轮（reload → 页面可用 ${r.ms}ms；服务活着 ${r.ok}）：服务端处理顺序 = `
    + (r.eventsServer.join(" → ") || "（这一轮没记到受关注的请求）"));
}
console.log("");
console.log(`服务端进程还活着吗：${server.proc.exitCode === null ? "活着" : "已退出（exit " + server.proc.exitCode + "）"}`);
console.log(`跑完的轮数：${rounds.length} / ${ROUNDS}`
  + (rounds.some((r) => !r.ok) ? "（**中途命中竞态**）" : "（全程活着）"));

await browser.close();
await server.stop();
console.log("（服务已由本探针收掉）");
