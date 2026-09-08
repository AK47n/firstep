// 截图（工单 07 右侧栏收起）：深色主题 + 1440x900 + 样本工程 main.c 打开 +
// 侧栏收起（点活动页签「大纲」等价路径）→ shot-side-collapsed.png。
const CDP = 9251;
const targets = await (await fetch(`http://127.0.0.1:${CDP}/json/list`)).json();
const page = targets.find((t) => t.type === "page" && t.url.startsWith("http://127.0.0.1:8000"));
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws")); });
let seq = 0; const pending = new Map();
ws.onmessage = (ev) => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
const cdp = (method, params = {}) => new Promise((res) => { const id = ++seq; pending.set(id, res); ws.send(JSON.stringify({ id, method, params })); });
const Eval = async (expr) => { const r = await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true }); if (r.result?.exceptionDetails) throw new Error("eval: " + (r.result.exceptionDetails.exception?.description || "?")); return r.result?.result?.value; };
const SAMPLE = "C:\\Users\\luoji\\Desktop\\firstep\\.scratch\\code-viewer-editor\\sample-proj";
await cdp("Emulation.setDeviceMetricsOverride", { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });
await Eval(`localStorage.setItem('firstep.theme','dark'); localStorage.setItem('firstep.codeSideCollapsed','0'); location.reload()`);
await new Promise((r) => setTimeout(r, 1200));
await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`);
await new Promise((r) => setTimeout(r, 900));
await Eval(`document.querySelector('#code-tree [data-code-file="main.c"]')?.click()`);
await new Promise((r) => setTimeout(r, 600));
// 收起侧栏（等价于展开态点活动页签「大纲」）
await Eval(`document.querySelector('.code-side-tabs [data-code-side="outline"]')?.click()`);
await new Promise((r) => setTimeout(r, 500));
const collapsed = await Eval(`document.querySelector('.code-layout')?.classList.contains('side-collapsed')`);
console.log("collapsed =", collapsed);
const shot = await cdp("Page.captureScreenshot", { format: "png" });
const { writeFileSync } = await import("node:fs");
writeFileSync(".scratch/code-viewer-editor/shot-side-collapsed.png", Buffer.from(shot.result.data, "base64"));
console.log("shot saved");
ws.close();
