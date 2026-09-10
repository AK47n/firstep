// 诊断探针（第十六轮 B24 段二卡住时用）：页面点分析 → 每 4s 轮询 DOM（不 await
// 被卡的 evaluate）→ 同时用 route.fetch 抓服务端真实 SSE 体，判断「服务端好 / 前端卡」。
// 用后即清（一次性诊断，不入正式验收链路）。
import { createRequire } from "node:module";
import { readFileSync, writeFileSync } from "node:fs";

const require = createRequire(import.meta.url);
const { chromium } = require("C:/Users/luoji/AppData/Local/npm-cache/_npx/e41f203b7505f1fb/node_modules/playwright");

const REPO = "C:/Users/luoji/Desktop/firstep";
const DIR = `${REPO}/.scratch/real-run/out_2026C_stm32`;
const out = [];
const say = (s) => { console.log(s); out.push(s); };

const browser = await chromium.launch({
  headless: true,
  executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe",
});
const page = await browser.newPage();
const logs = [];
page.on("console", (m) => logs.push(`${m.type()}: ${m.text().slice(0, 200)}`));
page.on("pageerror", (e) => logs.push(`pageerror: ${String(e).slice(0, 300)}`));
let served = null;
await page.route("**/api/revise/analyze", async (route) => {
  const resp = await route.fetch();
  const body = await resp.text();
  served = { status: resp.status(), len: body.length, head: body.slice(0, 160) };
  await route.fulfill({ response: resp, body });
});

await page.goto("http://127.0.0.1:8000", { waitUntil: "networkidle" });
await page.waitForSelector("#btn-revise-load-dir", { state: "attached" });
await page.evaluate(() => {
  document.getElementById("card-revise").classList.remove("collapsed");
  document.querySelector('#revise-tabs .revise-tab[data-tab="revise"]')?.click();
});
await page.fill("#revise-dir-input", DIR);
await page.click("#btn-revise-load-dir");
await page.waitForFunction(
  () => !document.getElementById("revise-context").classList.contains("hidden"),
  null, { timeout: 30000 });
const fillVisible = await page.evaluate(
  () => !document.getElementById("revise-problem-fill").classList.contains("hidden"));
say(`补题面区可见=${fillVisible}`);
if (fillVisible) {
  await page.fill("#revise-problem-text", readFileSync(`${REPO}/library/topics/2026C/topic.md`, "utf-8"));
  await page.evaluate(() => {
    const bs = [...document.querySelectorAll("#revise-problem-fill button")];
    (bs.find((x) => /保存|确认|填入|应用/.test(x.textContent)) || bs[0])?.click();
  });
  await page.waitForTimeout(1200);
}
await page.fill("#revise-qa-new", "问：无线通信是否限定 Zigbee？\n答：用现有 DL-20 透传。");
// 不 await：先 kick off，再轮询 DOM（被 evaluate 卡住也不影响我们看状态）
page.evaluate(async () => {
  const m = await import("/js/ui/generate-revise.js");
  m.reviseAnalyze();
}).catch((e) => logs.push("kick err: " + String(e).slice(0, 200)));

for (let i = 0; i < 15; i += 1) {
  await page.waitForTimeout(4000);
  const st = await page.evaluate(() => ({
    s: document.getElementById("revise-analyze-status").textContent,
    m: document.getElementById("revise-analyze-msg").textContent,
    hidden: document.getElementById("revise-analysis").classList.contains("hidden"),
    len: document.getElementById("revise-analysis").textContent.length,
  })).catch((e) => ({ err: String(e).slice(0, 120) }));
  say(`t+${(i + 1) * 4}s ${JSON.stringify(st)}`);
  if (st.hidden === false || (st.m && st.m.length)) break;
}
say("served(route.fetch 抓到的服务端 SSE): " + JSON.stringify(served));
say("页面 console/pageerror（前 10 条）: " + JSON.stringify(logs.slice(0, 10), null, 1));
writeFileSync(`${REPO}/.scratch/revise-deepen/verify-16-revise-hang-diag.txt`, out.join("\n") + "\n", "utf-8");
await browser.close();
