// 冒烟（mainc-codeview-bridge/04）：骨架引用模块锚定——编辑框写入含模块调用的
// 骨架 → 步骤 8 下方出现「骨架引用的模块」chips（去重保序）→ 点击 chip 打开
// 模块详情弹窗（与推荐卡同款 overlay）→ 改为仅注释内容 + input 防抖 → 整区
// 隐藏。零写库；webapp 8000 + CDP 9251。
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9251;

const fetchT = async (url, ms = 5000) => {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), ms);
  try { return await fetch(url, { signal: ctl.signal }); } finally { clearTimeout(t); }
};
let targets = null;
for (let i = 0; i < 50 && !targets; i++) {
  try { targets = await (await fetchT(`http://127.0.0.1:${CDP}/json/list`)).json(); } catch {}
  if (!targets || !targets.length) await new Promise((r) => setTimeout(r, 300));
}
if (!targets) { console.error("CDP 不可达"); process.exit(1); }
const page = targets.find((t) => t.type === "page" && t.url.startsWith("http://127.0.0.1:8000"));
if (!page) { console.error("未找到 webapp 页面 target"); process.exit(1); }
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws error")); });
let seq = 0;
const pending = new Map();
ws.onmessage = (ev) => {
  const msg = JSON.parse(ev.data);
  if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
};
const cdp = (method, params = {}) =>
  new Promise((resolve) => { const id = ++seq; pending.set(id, resolve); ws.send(JSON.stringify({ id, method, params })); });
const Eval = async (expr) => {
  const r = await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) throw new Error("eval 失败: " + (r.result.exceptionDetails.exception?.description || JSON.stringify(r.result.exceptionDetails)));
  return r.result?.result?.value;
};
const waitFor = async (expr, ms = 8000) => {
  for (let i = 0; i < ms / 200; i++) {
    try { if (await Eval(expr)) return true; } catch {}
    await new Promise((r) => setTimeout(r, 200));
  }
  return false;
};
const assert = (cond, label) => {
  if (!cond) { console.error("FAIL: " + label); process.exitCode = 1; }
  else console.log("ok: " + label);
};

assert(await waitFor(`typeof window.draftState === "function"`), "页面模块图加载");
// 1. 无命中：初始（空编辑框）整区隐藏
assert(await Eval(`document.querySelector("#skeleton-module-refs").classList.contains("hidden")`), "空骨架 → 锚定区隐藏");
// 2. 写入骨架（含模块调用）+ 已选模块 → chips 出现（去重保序：led 只一次）
await Eval(`(async () => {
  const r = await import("/js/ui/generate-recommend.js");
  r.setSelectedSlugs(["led", "adc"]);
  const ta = document.querySelector("#main-c");
  ta.value = "int main(void) {\\n  led_init(LED_RED);\\n  adc_init();\\n  led_write(LED_RED, 1);\\n  return 0;\\n}";
  const m = await import("/js/ui/skeleton-refs.js");
  m.renderSkeletonRefs();
})()`);
assert(await waitFor(`!document.querySelector("#skeleton-module-refs").classList.contains("hidden")`), "骨架含调用 → 锚定区可见");
assert(await Eval(`document.querySelectorAll("#skeleton-module-refs [data-skeleton-ref]").length === 2`), "chips = 2（去重）");
assert(await Eval(`document.querySelector("#skeleton-module-refs [data-skeleton-ref='led'] .reason").textContent === "led_init"`), "led chip 首次命中调用");
// 3. 点击 chip → 模块详情弹窗（与推荐卡同款 overlay）
await Eval(`document.querySelector("#skeleton-module-refs [data-skeleton-ref='led']").click(); true`);
assert(await waitFor(`!!document.querySelector(".module-info-overlay .module-info-modal")`), "点击 chip → 模块详情弹窗");
assert(await Eval(`document.querySelector(".module-info-modal").textContent.includes("led")`), "弹窗内容为对应模块");
// 关弹窗（overlay 点击关闭惯例：点遮罩）
await Eval(`document.querySelector(".module-info-overlay").click(); true`);
// 4. 内容改为仅注释 → input 事件防抖后整区隐藏
await Eval(`(() => {
  const ta = document.querySelector("#main-c");
  ta.value = "// led_init(); 注释不算\\n/* adc_init(); */";
  ta.dispatchEvent(new Event("input", { bubbles: true }));
})()`);
assert(await waitFor(`document.querySelector("#skeleton-module-refs").classList.contains("hidden")`, 5000), "仅注释 → 锚定区隐藏（防抖后）");
ws.close();
console.log(process.exitCode ? "\nSMOKE FAILED" : "\nSMOKE PASS");
