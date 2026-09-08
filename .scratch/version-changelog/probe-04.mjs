// version-changelog/04 探针：验证「版本更新记录」前端（CDP 直连 Chrome 9251，
// 依赖 8123 端口的新代码 webapp）。
// 场景 A：Fetch 拦截 /api/changelog 返回样例版本数据 → 卡片渲染 / 默认折叠 /
// 点击展开（aria-expanded）+ 截图。
// 场景 B：放行真实 API（VERSIONS.md 空态）→ 空态文案 + 截图。
import { writeFileSync } from "node:fs";

const CDP = 9251;
const pageUrl = "http://127.0.0.1:8123/";

const SAMPLE = {
  releases: [
    { version: "v1.1.0", date: "2026-09-04",
      summary: "一个月打磨，从能生成工程到像 IDE 一样改",
      items: [
        { kind: "新增", text: "代码栏：IDE 式编辑器（文件树 / 多标签 / 搜索 / Ctrl+P 快速打开）" },
        { kind: "新增", text: "编译错误行内标记，点击直达出错行" },
        { kind: "改进", text: "生成主流程自动编译 + AI 修复" },
        { kind: "修复", text: "一批现场问题" },
        { kind: "性能", text: "编辑器大文件惰性高亮" },
        { kind: "其他", text: "无标签兜底条目" },
      ] },
    { version: "v1.0.0", date: "2026-08-05", summary: "",
      items: [{ kind: "新增", text: "赛题 → 完整工程生成" }] },
  ],
};

let targets = null;
for (let i = 0; i < 60 && !targets; i++) {
  try { targets = await (await fetch(`http://127.0.0.1:${CDP}/json/list`)).json(); } catch {}
  if (!targets || !targets.length) await new Promise((r) => setTimeout(r, 300));
}
if (!targets) { console.error("CDP 不可达"); process.exit(1); }
const page = targets.find((t) => t.type === "page");
console.log("target page:", page.url);
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws error")); });
console.log("ws open");

let seq = 0;
const pending = new Map();
const jsErrors = [];
let intercept = false;
const cdp = (method, params = {}) =>
  new Promise((resolve) => { const id = ++seq; pending.set(id, resolve); ws.send(JSON.stringify({ id, method, params })); });
ws.onmessage = (ev) => {
  const msg = JSON.parse(ev.data);
  if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
  if (msg.method === "Runtime.exceptionThrown") {
    jsErrors.push(msg.params.exceptionDetails?.exception?.description || "exception");
  }
  if (msg.method === "Fetch.requestPaused") {
    const { requestId, request } = msg.params;
    if (intercept && request.url.includes("/api/changelog")) {
      cdp("Fetch.fulfillRequest", {
        requestId,
        responseCode: 200,
        responseHeaders: [{ name: "Content-Type", value: "application/json" }],
        body: Buffer.from(JSON.stringify(SAMPLE)).toString("base64"),
      });
    } else {
      cdp("Fetch.continueRequest", { requestId });
    }
  }
};
const Eval = async (expr) => {
  const r = await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) throw new Error("eval 失败: " + (r.result.exceptionDetails.exception?.description || JSON.stringify(r.result.exceptionDetails)));
  return r.result?.result?.value;
};
const shot = async (name) => {
  const s = await cdp("Page.captureScreenshot", { format: "png" });
  writeFileSync(new URL(name, import.meta.url), Buffer.from(s.result.data, "base64"));
  console.log("saved", name);
};
const openChangelog = async () => {
  await Eval(`(() => { const b = [...document.querySelectorAll('nav button[data-tab]')].find(x => x.dataset.tab === 'changelog'); if (!b) return 'no-tab'; b.click(); return b.textContent; })()`);
  await new Promise((r) => setTimeout(r, 700));
};

console.log("stage: enable");
await cdp("Runtime.enable");
await cdp("Page.enable");
await cdp("Network.setCacheDisabled", { cacheDisabled: true });
await cdp("Emulation.setDeviceMetricsOverride", { width: 1280, height: 900, deviceScaleFactor: 1, mobile: false });

// ---- 场景 A：拦截 API，样例版本卡片 ----
console.log("stage: fetch enable + navigate A");
intercept = true;
await cdp("Fetch.enable", { patterns: [{ urlPattern: "*api/changelog*", requestStage: "Request" }] });
await cdp("Page.navigate", { url: pageUrl + "?a=" + Date.now() });
let ready = false;
for (let i = 0; i < 120 && !ready; i++) {
  try { ready = await Eval(`document.readyState === 'complete' && !!document.getElementById('changelog-list')`); } catch {}
  if (!ready) await new Promise((r) => setTimeout(r, 300));
}
if (!ready) { console.error("页面未就绪"); process.exit(1); }
console.log("stage: open changelog A");
await openChangelog();

const cardsA = await Eval(`document.querySelectorAll('.release-card').length`);
const verA = await Eval(`document.querySelector('.release-ver')?.textContent`);
const openA = await Eval(`document.querySelector('.release-card')?.classList.contains('collapsed')`);
const closedA2 = await Eval(`document.querySelectorAll('.release-card')[1]?.classList.contains('collapsed')`);
const tagsA = await Eval(`[...document.querySelectorAll('.rel-tag')].map(t => t.textContent).join(',')`);
const boxA = await Eval(`document.getElementById('changelog-list').innerHTML.slice(0, 160)`);
console.log("A cards:", cardsA, "first:", verA, "firstCollapsed:", openA, "secondCollapsed:", closedA2, "tags:", tagsA);
console.log("A box:", boxA);
if (cardsA !== 2) { console.error("A FAIL: 卡片数不符"); process.exit(1); }
await shot("shot-04-cards.png");

// 点击第二个卡片头 → 展开（aria-expanded 翻转）
await Eval(`document.querySelectorAll('.release-head')[1].click()`);
await new Promise((r) => setTimeout(r, 300));
const aria2 = await Eval(`document.querySelectorAll('.release-head')[1].getAttribute('aria-expanded')`);
const closed2 = await Eval(`document.querySelectorAll('.release-card')[1].classList.contains('collapsed')`);
console.log("A toggle → aria-expanded:", aria2, "collapsed:", closed2);
await shot("shot-04-cards-expanded.png");

// 再点一下 → 收回
await Eval(`document.querySelectorAll('.release-head')[1].click()`);
await new Promise((r) => setTimeout(r, 300));
const closed2b = await Eval(`document.querySelectorAll('.release-card')[1].classList.contains('collapsed')`);
console.log("A toggle back → collapsed:", closed2b);

// ---- 场景 B：真实 API（已发布 v1.0.0 → 卡片实况） ----
console.log("stage: navigate B");
await cdp("Fetch.disable");
intercept = false;
await cdp("Page.navigate", { url: pageUrl + "?b=" + Date.now() });
ready = false;
for (let i = 0; i < 120 && !ready; i++) {
  try { ready = await Eval(`document.readyState === 'complete' && !!document.getElementById('changelog-list')`); } catch {}
  if (!ready) await new Promise((r) => setTimeout(r, 300));
}
console.log("stage: open changelog B");
await openChangelog();
const verB = await Eval(`document.querySelector('#changelog-list .release-ver')?.textContent`);
const dateB = await Eval(`document.querySelector('#changelog-list .release-date')?.textContent`);
const summaryB = await Eval(`document.querySelector('#changelog-list .release-summary')?.textContent`);
const tagsB = await Eval(`document.querySelectorAll('#changelog-list .rel-tag').length`);
const tabLabel = await Eval(`[...document.querySelectorAll('nav button[data-tab]')].find(x => x.dataset.tab === 'changelog')?.textContent`);
const tabGroup = await Eval(`(() => { const b = [...document.querySelectorAll('nav button[data-tab]')].find(x => x.dataset.tab === 'changelog'); return b ? b.closest('.tab-group')?.getAttribute('aria-label') : null; })()`);
console.log("B real:", verB, dateB, "|", summaryB, "| tags:", tagsB, "| tab:", tabLabel, "| group:", tabGroup);
if (verB !== "v1.0.0") { console.error("B FAIL: 实况应为 v1.0.0 卡片"); process.exit(1); }
await shot("shot-04-release.png");

console.log("jsErrors:", jsErrors.length ? jsErrors : "无");
console.log(jsErrors.length ? "FAIL" : "PASS");
process.exit(jsErrors.length ? 1 : 0);
