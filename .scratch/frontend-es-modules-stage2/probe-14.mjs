// 工单 14 实况探针：main.c 预览工具小簇迁 ui/generate-mainc.js 后行为完好性。
// 验证：动态 import 无错 → 高亮同步（行号列 + 语法着色 token）→ 字号缩放
// （in/out/clamp/label/font-size + 持久化）→ 复制（真实鼠标点击 → toast）→
// 下载（toast）→ 全屏（class + body lock + 按钮文案 + Esc 退出）→ 全程零 EXC。
// 识别不到跨模块 window 桥（ui 模块不挂桥），一律 DOM 实况驱动。
// CDP 直连（9251），webapp 8000。
const CDP = 9251;
const targets = await (await fetch(`http://127.0.0.1:${CDP}/json/list`)).json();
const page = targets.find((t) => t.type === "page" && t.url.startsWith("http://127.0.0.1:8000"));
if (!page) { console.error("no 8000 page"); process.exit(1); }
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws")); });
let seq = 0;
const pending = new Map();
const events = [];
ws.onmessage = (ev) => {
  const m = JSON.parse(ev.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); return; }
  if (m.method === "Runtime.exceptionThrown") {
    const d = m.params.exceptionDetails;
    events.push("EXC@L" + d.lineNumber + "C" + d.columnNumber + ": " + (d.exception?.description || d.text).slice(0, 200));
  }
  if (m.method === "Log.entryAdded" && m.params.entry.level === "error") {
    const t = (m.params.entry.text || "") + " " + (m.params.entry.url || "");
    if (t.includes("favicon")) return;   // 既有 favicon 404 噪声，不计
    events.push("LOG: " + (m.params.entry.text || "").slice(0, 250));
  }
  if (m.method === "Network.loadingFailed") {
    events.push("NETFAIL: " + m.params.errorText + " " + (m.params.blockedReason || ""));
  }
  if (m.method === "Network.responseReceived" && m.params.response.status >= 400 && !m.params.response.url.includes("favicon")) {
    events.push("HTTP" + m.params.response.status + ": " + m.params.response.url);
  }
};
const cdp = (method, params = {}) => new Promise((resolve) => { const id = ++seq; pending.set(id, resolve); ws.send(JSON.stringify({ id, method, params })); });
const Eval = async (expr) => {
  const r = await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) throw new Error("eval 失败: " + (r.result.exceptionDetails.exception?.description || JSON.stringify(r.result.exceptionDetails)));
  return r.result?.result?.value;
};
const waitFor = async (expr, ms = 12000) => {
  for (let i = 0; i < ms / 200; i++) {
    try { if (await Eval(expr)) return true; } catch {}
    await new Promise((r) => setTimeout(r, 200));
  }
  return false;
};
const check = (name, ok, extra = "") => {
  console.log((ok ? "PASS " : "FAIL ") + name + (extra ? " [" + extra + "]" : ""));
  if (!ok) process.exitCode = 1;
};
// 真实鼠标点击（复制需要用户手势走 navigator.clipboard）
const realClick = async (id) => {
  const r = await Eval(`(() => { const el = document.getElementById("${id}"); if (!el) return null; el.scrollIntoView({ block: "center" }); const b = el.getBoundingClientRect(); return { x: b.left + b.width / 2, y: b.top + b.height / 2 }; })()`);
  if (!r) return false;
  await cdp("Input.dispatchMouseEvent", { type: "mouseMoved", x: r.x, y: r.y });
  await cdp("Input.dispatchMouseEvent", { type: "mousePressed", x: r.x, y: r.y, button: "left", clickCount: 1 });
  await cdp("Input.dispatchMouseEvent", { type: "mouseReleased", x: r.x, y: r.y, button: "left", clickCount: 1 });
  return true;
};

await cdp("Runtime.enable");
await cdp("Log.enable");
await cdp("Network.enable");

// P0 模块静态 import 可执行性直探（语法错误会在此炸出异常）
const impOk = await Eval(`import("/js/ui/generate-mainc.js").then(() => "ok", (e) => "FAIL: " + e.message)`);
check("generate-mainc.js 可动态 import（无语法/引用错误）", impOk === "ok", impOk);

// 清草稿 + 缩放记忆，保证确定性起点
await Eval(`try { localStorage.removeItem("firstep.draft.v1"); } catch (e) {}`);
await Eval(`try { localStorage.removeItem("firstep.mainc.zoom"); } catch (e) {}`);
await cdp("Page.reload", { ignoreCache: true });
await waitFor(`document.readyState === "complete" && !!document.getElementById("main-c") && !!document.querySelector("#platforms .platform-card")`);
await new Promise((r) => setTimeout(r, 800));

// P1 高亮同步：填充样例 C 代码 → input 事件 → 行号列 + 语法着色 token
const p1 = await Eval(`(() => {
  const ta = document.getElementById("main-c");
  const src = "#include <stdio.h>\\n\\nint main(void) {\\n  // 注释\\n  return 0;\\n}";
  ta.value = src;
  ta.dispatchEvent(new Event("input", { bubbles: true }));
  const nums = document.getElementById("main-c-nums").textContent;
  const hl = document.getElementById("main-c-hl").innerHTML;
  return {
    numsLines: nums ? nums.split("\\n").length : 0,
    numsTail: nums ? nums.trimEnd().split("\\n").pop() : "",
    tokPre: (hl.match(/tok-pre/g) || []).length,
    tokKw: (hl.match(/tok-kw/g) || []).length,
    tokCom: (hl.match(/tok-com/g) || []).length,
  };
})()`);
check("高亮同步：行号列 6 行 + 末行 6", p1.numsLines === 6 && p1.numsTail === "6", JSON.stringify(p1));
check("高亮同步：预处理/关键字/注释 token 着色", p1.tokPre >= 1 && p1.tokKw >= 2 && p1.tokCom >= 1, JSON.stringify(p1));

// P2 字号缩放：初始 100% → in 110 → out 100 → out 90 → out 80（下限 clamp 封顶）
const zoom0 = await Eval(`({ label: document.getElementById("code-zoom-label").textContent, fs: getComputedStyle(document.querySelector("#main-c").closest(".code-wrap")).fontSize })`);
check("缩放：初始 100%", zoom0.label === "100%", JSON.stringify(zoom0));
await Eval(`document.getElementById("btn-code-zoom-in").click()`);
const z1 = await Eval(`({ label: document.getElementById("code-zoom-label").textContent, fs: document.querySelector("#main-c").closest(".code-wrap").style.fontSize })`);
check("缩放：in → 110% / 14.3px", z1.label === "110%" && z1.fs === "14.3px", JSON.stringify(z1));
await Eval(`document.getElementById("btn-code-zoom-out").click()`);
const z2 = await Eval(`({ label: document.getElementById("code-zoom-label").textContent, fs: document.querySelector("#main-c").closest(".code-wrap").style.fontSize })`);
check("缩放：out → 100% / 13px", z2.label === "100%" && z2.fs === "13px", JSON.stringify(z2));
await Eval(`document.getElementById("btn-code-zoom-out").click()`);
const z3 = await Eval(`({ label: document.getElementById("code-zoom-label").textContent, fs: document.querySelector("#main-c").closest(".code-wrap").style.fontSize })`);
check("缩放：out → 90% / 11.7px", z3.label === "90%" && z3.fs === "11.7px", JSON.stringify(z3));
await Eval(`document.getElementById("btn-code-zoom-out").click()`);   // 90 → 80
await Eval(`document.getElementById("btn-code-zoom-out").click()`);   // 80 → clamp 80
const z4 = await Eval(`({ label: document.getElementById("code-zoom-label").textContent, fs: document.querySelector("#main-c").closest(".code-wrap").style.fontSize, stored: localStorage.getItem("firstep.mainc.zoom") })`);
check("缩放：下限 clamp 80%（再点 out 不降）", z4.label === "80%" && z4.fs === "10.4px" && z4.stored === "80", JSON.stringify(z4));
await Eval(`document.getElementById("btn-code-zoom-in").click()`);    // 回到 90，供 P6 持久化验证
check("缩放：in 回 90%（持久化起点）", (await Eval(`document.getElementById("code-zoom-label").textContent`)) === "90%");

// P3 复制：真实鼠标点击（用户手势 → navigator.clipboard）→ toast「main.c 已复制」
const copyHit = await realClick("btn-main-c-copy");
const p3 = await waitFor(`[...document.querySelectorAll("#toast-root .toast-text")].some((t) => t.textContent.includes("已复制"))`, 6000);
check("复制：真实点击 → 「main.c 已复制」toast", copyHit && p3);

// P4 下载：点击 → toast「main.c 已下载」
await Eval(`document.getElementById("btn-main-c-download").scrollIntoView({ block: "center" }); document.getElementById("btn-main-c-download").click()`);
const p4 = await waitFor(`[...document.querySelectorAll("#toast-root .toast-text")].some((t) => t.textContent.includes("已下载"))`, 6000);
check("下载：点击 → toast「main.c 已下载」", p4 === true);

// P5 全屏：点击 → wrap.fullscreen + body lock + 按钮文案；Esc → 退出
await Eval(`document.getElementById("btn-main-c-fullscreen").click()`);
const p5a = await Eval(`({
  full: document.querySelector("#main-c").closest(".code-wrap").classList.contains("fullscreen"),
  bodyLock: document.body.classList.contains("code-full-body-lock"),
  label: document.getElementById("btn-main-c-fullscreen").textContent,
})`);
check("全屏：进入（wrap.fullscreen + body lock + 「退出全屏」）", p5a.full && p5a.bodyLock && p5a.label === "退出全屏", JSON.stringify(p5a));
await Eval(`document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }))`);
const p5b = await Eval(`({
  full: document.querySelector("#main-c").closest(".code-wrap").classList.contains("fullscreen"),
  bodyLock: document.body.classList.contains("code-full-body-lock"),
  label: document.getElementById("btn-main-c-fullscreen").textContent,
})`);
check("全屏：Esc 退出（类全清 + 「全屏」）", !p5b.full && !p5b.bodyLock && p5b.label === "全屏", JSON.stringify(p5b));

// P6 缩放持久化：重载后从 localStorage 恢复 90%
await cdp("Page.reload", { ignoreCache: true });
await waitFor(`document.readyState === "complete" && !!document.getElementById("code-zoom-label")`);
await new Promise((r) => setTimeout(r, 800));
const p6 = await Eval(`({ label: document.getElementById("code-zoom-label").textContent, fs: document.querySelector("#main-c").closest(".code-wrap").style.fontSize })`);
check("缩放持久化：重载恢复 90% / 11.7px", p6.label === "90%" && p6.fs === "11.7px", JSON.stringify(p6));

// 全程零 EXC / 零 HTTP 错误
check("全程零 EXC / 零 4xx / 零加载失败", events.length === 0, events.slice(0, 5).join(" | "));
console.log("done");
process.exit(process.exitCode || 0);
