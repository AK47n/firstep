// 冒烟（工单 generate-overwrite/01）：同名工程 400 → 确认框（.bak 提示）→
// 确认自动重发 overwrite=true → 成功渲染；取消 = 原 400 文案不重发。
// 零后端依赖：mock window.apiPost / window.confirm（webapp 静态文件实时读）。
const CDP = 9231;

let targets = null;
for (let i = 0; i < 50 && !targets; i++) {
  try {
    targets = await (await fetch(`http://127.0.0.1:${CDP}/json/list`)).json();
  } catch {}
  if (!targets || !targets.length) await new Promise((r) => setTimeout(r, 300));
}
if (!targets) { console.error("CDP 不可达"); process.exit(1); }
const page = targets.find((t) => t.type === "page");
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
  const r = await cdp("Runtime.evaluate", { expression: expr, returnByValue: true });
  if (r.result?.exceptionDetails) throw new Error("eval 失败: " + (r.result.exceptionDetails.exception?.description || JSON.stringify(r.result.exceptionDetails)));
  return r.result?.result?.value;
};

let ready = false;
await Eval(`window.__smokeMarker = 1`);
await cdp("Page.reload", { ignoreCache: true });
for (let i = 0; i < 100 && !ready; i++) {
  try {
    ready = await Eval(`document.readyState === 'complete' && !window.__smokeMarker
      && !!document.getElementById('btn-generate') && typeof state !== 'undefined' && state`);
  } catch {}
  if (!ready) await new Promise((r) => setTimeout(r, 300));
}
if (!ready) { console.error("页面未就绪（btn-generate 不存在）"); process.exit(1); }

let failed = 0;
const check = (name, ok, extra) => {
  console.log((ok ? "PASS" : "FAIL") + " " + name + (extra !== undefined ? " [" + extra + "]" : ""));
  if (!ok) failed++;
};
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// ---- 装置：准备生成状态 + mock 双通道 ----
await Eval(`(() => {
  document.querySelector('[data-tab="generate"]').click();
  chosenPlatform = "stm32";
  selectedSlugs = ["dht11"];
  document.getElementById("problem").value = "赛题：覆盖冒烟";
  document.getElementById("output-dir").value = "C:\\\\tmp\\\\out";
  toolchains = {};  // 防真实自动编译修复
  window.__calls = [];
  window.__confirmCalled = false;
  window.__errLog = [];
  window.addEventListener("error", (ev) => window.__errLog.push("error: " + String(ev.error || ev.message)));
  window.addEventListener("unhandledrejection", (ev) => window.__errLog.push("unhandled: " + String(ev.reason)));
  window.apiPost = async (url, body) => {
    try {
      window.__calls.push({ url, body: body ? JSON.parse(JSON.stringify(body)) : null });
      if (url === "/api/bindings/validate") return { ok: true };
      if (url === "/api/generate" && body && body.overwrite !== true) {
        throw new Error("桌面上已有同名工程「Auto_Car_STM32」：为避免覆盖你的已有工程，请先删除该目录或修改题名后再生成（不会自动改名或覆盖）。同一赛题换平台再生成时，会自动使用带平台后缀的新目录（如 Auto_Car_MSPM0），不会误删旧工程");
      }
      if (url === "/api/generate" && body && body.overwrite === true) {
        return {
          output_dir: "C:\\\\tmp\\\\out\\\\Auto_Car_STM32",
          include_dirs: ["src", "include"],
          modules: [{ slug: "dht11", files: ["src/dht.c", "include/dht.h"] }],
          python_artifacts: [],
          score_points: [],
          build_hint: "",
          structure: ["main.c", "src/dht.c", "include/dht.h"],
        };
      }
      return { ok: true };
    } catch (err) {
      window.__errLog.push("apiPost err at " + url + ": " + String(err));
      throw err;
    }
  };
  window.confirm = (text) => { window.__confirmCalled = true; window.__confirmText = text; return true; };
  return true;
})()`);
await sleep(200);

// ---- 场景 1：确认覆盖 → 自动重发 overwrite=true → 成功渲染 ----
await Eval(`document.getElementById('btn-generate').click()`);
let calls = [];
for (let i = 0; i < 40; i++) {
  calls = await Eval(`window.__calls`);
  if (calls.length >= 3) break;
  await sleep(200);
}
check("请求序列 ≥3（validate + 冲突 generate + 覆盖 generate）", calls.length >= 3, "calls=" + calls.length);
check("第一发为 bindings/validate", calls[0] && calls[0].url === "/api/bindings/validate");
check("第二发 generate 不带 overwrite", calls[1] && calls[1].url === "/api/generate"
  && !("overwrite" in (calls[1].body || {})));
check("确认框被调用且含 .bak 提示", await Eval(`window.__confirmCalled === true && (window.__confirmText || "").includes("Auto_Car_STM32.bak")`),
  await Eval(`(window.__confirmText || "").slice(0, 60)`));
check("第三发覆盖 generate 带 overwrite:true", calls[2] && calls[2].url === "/api/generate"
  && calls[2].body && calls[2].body.overwrite === true);
check("覆盖重发沿用原 payload（平台/题面/模块原样）", calls[2] && calls[2].body
  && calls[2].body.platform === "stm32" && calls[2].body.slugs[0] === "dht11"
  && calls[2].body.problem_text === "赛题：覆盖冒烟");
check("成功渲染：结果面板可见 + 目录回显", await Eval(`(() => {
  const r = document.getElementById('generate-result');
  return !r.classList.contains('hidden') && document.getElementById('res-dir').textContent.includes('Auto_Car_STM32');
})()`));
check("成功文案就位", await Eval(`document.getElementById('generate-msg').classList.contains('ok')
  && document.getElementById('generate-msg').textContent.includes('生成完成')`));

// ---- 场景 2：取消 → 原 400 文案，不重发 ----
await Eval(`(() => {
  window.__calls = [];
  window.__confirmCalled = false;
  window.confirm = () => { window.__confirmCalled = true; return false; };
  return true;
})()`);
await sleep(100);
await Eval(`document.getElementById('btn-generate').click()`);
await sleep(1500);
const after = await Eval(`(() => ({
  calls: window.__calls.length,
  confirmCalled: window.__confirmCalled,
  msg: document.getElementById('generate-msg').textContent,
  hidden: document.getElementById('generate-result').classList.contains('hidden'),
}))()`);
check("取消分支：只有 validate + generate 两发（无覆盖重发）", after.calls === 2, "calls=" + after.calls);
check("取消分支：确认框被调用", after.confirmCalled === true);
check("取消分支：显示原 400 文案", after.msg.includes("已有同名工程") && !after.msg.includes("覆盖并重新生成"),
  "msg=" + after.msg.slice(0, 40));
check("取消分支：结果面板保持隐藏", after.hidden === true);

console.log(failed === 0 ? "SMOKE ALL PASS" : "SMOKE FAILED: " + failed);
process.exit(failed === 0 ? 0 : 1);
