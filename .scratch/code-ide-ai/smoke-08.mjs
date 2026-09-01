// 冒烟（工单 code-ide-ai/07）：内容快照泛化——真实页面 + 真实后端（无桩）。
// 覆盖：打开文件建快照（mtime==基线）/ 外部改 → 变更集 content 供面板行级
// diff / 未打开文件无 content / mtime 不等不动旧快照 / 清空确认 re-fetch /
// 保存推进 = 用户确认版 / 旧 maincContent 格式迁移兼容 / 超限文件 null。
// 零依赖，CDP 9231。样本目录每次重置。
import { mkdirSync, rmSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9231;
const pageUrl = "http://127.0.0.1:8000/";
const SAMPLE = join(ROOT, ".scratch", "code-ide-ai", "sample-proj");

const OLD_MAIN = "int main(void) {\n  // TODO: init sensor\n  init();\n  return 0;\n}\n";
const EXT_MAIN = "int main(void) {\n  // fixed by AI\n  init();\n  return 0;\n}\n";
const USER_MAIN = "int main(void) {\n  // user edited\n  init();\n  return 0;\n}\n";

const resetSample = () => {
  rmSync(SAMPLE, { recursive: true, force: true });
  mkdirSync(join(SAMPLE, "src"), { recursive: true });
  writeFileSync(join(SAMPLE, "main.c"), OLD_MAIN, "utf8");
  writeFileSync(join(SAMPLE, "src", "app.c"), "#include <stdint.h>\n", "utf8");
  writeFileSync(join(SAMPLE, "readme.md"), "# 样本\n", "utf8");
};

let targets = null;
for (let i = 0; i < 50 && !targets; i++) {
  try { targets = await (await fetch(`http://127.0.0.1:${CDP}/json/list`)).json(); } catch {}
  if (!targets || !targets.length) await new Promise((r) => setTimeout(r, 300));
}
if (!targets) { console.error("CDP 不可达"); process.exit(1); }
const page = targets.find((t) => t.type === "page" && t.url.includes("127.0.0.1:8000"))
  || targets.find((t) => t.type === "page");
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
await cdp("Network.enable");
await cdp("Network.setCacheDisabled", { cacheDisabled: true });
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

resetSample();
let failed = 0;
const check = (name, ok, extra) => {
  console.log((ok ? "PASS" : "FAIL") + " " + name + (extra !== undefined ? "  [" + extra + "]" : ""));
  if (!ok) failed++;
};

await cdp("Page.navigate", { url: pageUrl });
let ready = false;
for (let i = 0; i < 100 && !ready; i++) {
  try { ready = await Eval(`document.readyState === 'complete' && !!document.getElementById('tab-code')`); } catch {}
  if (!ready) await new Promise((r) => setTimeout(r, 300));
}
if (!ready) { console.error("页面未就绪"); process.exit(1); }
await Eval(`localStorage.clear()`);
await cdp("Page.reload", { ignoreCache: true });
await new Promise((r) => setTimeout(r, 1200));

// 基线读取 helper（浏览器端表达式片段）
const DIRQ = JSON.stringify(SAMPLE);
const blobOf = (path) => `(() => { const s = JSON.parse(localStorage.getItem('firstep.codeBaseline') || '{}'); const e = s[${DIRQ}]; const f = e && e.files && e.files[${JSON.stringify(path)}]; return f ? (f.content === undefined ? null : f.content) : 'noentry'; })()`;

// S1：打开目录 + 打开 main.c → 基线建内容快照（mtime==基线 → 快照=读盘内容）；
// app.c 未打开 → 无 content
await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${DIRQ}))`);
await waitFor(`!!document.querySelector('#code-tree [data-code-file="main.c"]')`);
await Eval(`import('/js/ui/codeeditor.js').then((m) => m.openEditorFile('main.c'))`);
await waitFor(`!!document.querySelector('.code-ta')`);
check("S1 打开 main.c：基线快照 = 读盘内容", await Eval(blobOf("main.c")) === OLD_MAIN);
check("S1 未打开 src/app.c：无快照（null）", await Eval(blobOf("src/app.c")) === null);

// S1b：同 mtime 重开（已有标签激活路径——不走读盘）→ 快照不变、无误报
await Eval(`import('/js/ui/codeeditor.js').then((m) => m.openEditorFile('main.c'))`);
check("S1b 同 mtime 重开：快照不变无误报", await Eval(blobOf("main.c")) === OLD_MAIN);

// S2：外部改 main.c → 感知 → 变更集 + 面板 main.c 行级 diff（旧快照 vs 磁盘）
writeFileSync(join(SAMPLE, "main.c"), EXT_MAIN, "utf8");
await Eval(`import('/js/ui/codeview.js').then((m) => m.checkCodeDiskChanges())`);
await waitFor(`!document.getElementById('code-change-panel').classList.contains('hidden')`);
check("S2 外部改 main.c：面板出现 + 行级 diff 区（快照数据源可用）", await Eval(`
  !document.getElementById('code-change-panel').classList.contains('hidden')
  && !!document.querySelector('#code-change-list details.code-change-diff')`));

// S3：外部改从未打开的 app.c → 文件级条目照常 + 基线 app.c 无 content
writeFileSync(join(SAMPLE, "src", "app.c"), "#include <stdint.h>\nint app(void){return 1;}\n", "utf8");
await Eval(`import('/js/ui/codeview.js').then((m) => m.checkCodeDiskChanges())`);
await waitFor(`!!document.querySelector('#code-change-list [data-change-path="src/app.c"]')`);
check("S3 未打开文件外部改：无 content（无行级区）", await Eval(blobOf("src/app.c")) === null);
check("S3 未打开文件外部改：面板文件级条目（无 diff 区）", await Eval(`
  !!document.querySelector('#code-change-list [data-change-path="src/app.c"]')
  && !document.querySelector('#code-change-list [data-change-path="src/app.c"] details')`));

// S4：打开已被外部改的 app.c → mtime != 基线 → 不动旧快照（仍无 content）；
// await openEditorFile = 读盘完成（onFileLoaded 同步回调已在返回前执行）
await Eval(`import('/js/ui/codeeditor.js').then((m) => m.openEditorFile('src/app.c'))`);
await waitFor(`!!document.querySelector('.code-ta')`);
check("S4 mtime 不等不建快照（无 content）", await Eval(blobOf("src/app.c")) === null);

// S5：清空确认 → 推进 re-fetch → main.c 快照 = 当前磁盘（EXT_MAIN）
await Eval(`document.getElementById('btn-code-change-clear').click()`);
await waitFor(`document.getElementById('code-change-panel').classList.contains('hidden')`);
check("S5 清空后 main.c 快照 = 磁盘当前内容（re-fetch）", await Eval(blobOf("main.c")) === EXT_MAIN);

// S6：编辑 main.c 保存 → 基线快照 = 用户确认版 + 变更集收敛
await Eval(`import('/js/ui/codeeditor.js').then((m) => m.openEditorFile('main.c'))`);
await waitFor(`!!document.querySelector('.code-ta')`);
await Eval(`(() => {
  const ta = document.querySelector('.code-ta');
  ta.value = ${JSON.stringify(USER_MAIN)};
  ta.dispatchEvent(new Event('input', { bubbles: true }));
  document.getElementById('btn-code-save').click();
})()`);
await waitFor(`JSON.parse(localStorage.getItem('firstep.codeBaseline') || '{}')[${DIRQ}]?.files?.['main.c']?.content === ${JSON.stringify(USER_MAIN)}`);
check("S6 保存后快照 = 用户确认版", await Eval(blobOf("main.c")) === USER_MAIN);

// S7：旧格式兼容——手写 old-format 基线（maincContent 每目录特例，mtime 用
// 磁盘真实值保证「无变更」）→ reload → 打开目录 → 打开 main.c（mtime==基线
// → 建快照落盘 = 迁移后的新格式）→ 不崩 + 特例键消失（迁移正确性由单测
// 覆盖；冒烟验证「旧格式可读、落盘为统一字段结构」）
const realMtime = await Eval(`fetch('/api/code/file?dir=' + encodeURIComponent(${DIRQ}) + '&path=main.c').then((r) => r.json()).then((d) => d.mtime_ns)`);
await Eval(`(() => {
  const store = {};
  store[${DIRQ}] = { ts: Date.now(), files: { 'main.c': { mtime_ns: ${JSON.stringify(realMtime)}, size_bytes: 1 } }, maincContent: 'OLD-FMT' };
  localStorage.setItem('firstep.codeBaseline', JSON.stringify(store));
})()`);
await cdp("Page.reload", { ignoreCache: true });
await new Promise((r) => setTimeout(r, 1200));
await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${DIRQ}))`);
await waitFor(`!!document.querySelector('#code-tree [data-code-file="main.c"]')`);
await Eval(`import('/js/ui/codeeditor.js').then((m) => m.openEditorFile('main.c'))`);
await waitFor(`!!document.querySelector('.code-ta')`);
check("S7 旧格式迁移：打开建档落盘（content = 读盘内容）", await Eval(blobOf("main.c")) === USER_MAIN);
check("S7 旧格式迁移：maincContent 特例键已删", await Eval(`
  JSON.parse(localStorage.getItem('firstep.codeBaseline') || '{}')[${DIRQ}]?.maincContent === undefined`));

// S8：超限文件（>256KB）→ 快照 null（无行级）+ 清单剔除
const BIG = "x".repeat(260 * 1024);
writeFileSync(join(SAMPLE, "big.c"), BIG, "utf8");
await Eval(`import('/js/ui/codeview.js').then((m) => m.refreshCodeTreeOnly())`);
await waitFor(`!!document.querySelector('#code-tree [data-code-file="big.c"]')`);
await Eval(`import('/js/ui/codeeditor.js').then((m) => m.openEditorFile('big.c'))`);
await waitFor(`!!document.querySelector('.code-ta')`);
check("S8 超限文件快照 null（无行级）", await Eval(blobOf("big.c")) === null);

// S9：已打开（持快照）文件被外部删除 → 感知 removed → 清空推进不崩溃
// （评审 Spec 轴：删除/改名文件在推进时被枚举 → snap[p] undefined 崩溃风险；
// 派生清单 + Object.keys(snap) 守卫后应安全）
await Eval(`import('/js/ui/codeeditor.js').then((m) => m.openEditorFile('readme.md'))`);
await waitFor(`!!document.querySelector('.code-ta')`);
rmSync(join(SAMPLE, "readme.md"));
await Eval(`import('/js/ui/codeview.js').then((m) => m.checkCodeDiskChanges())`);
await waitFor(`!!document.querySelector('#code-change-list [data-change-path="readme.md"][data-change-status="removed"]')`);
const clearOk = await Eval(`(async () => {
  try {
    document.getElementById('btn-code-change-clear').click();
    await new Promise((r) => setTimeout(r, 400));
    return document.getElementById('code-change-panel').classList.contains('hidden');
  } catch (e) { return 'ERR: ' + e.message; }
})()`);
check("S9 删除文件推进：无崩溃 + 面板收敛", clearOk === true, String(clearOk));

console.log(failed === 0 ? "全部通过" : failed + " 项失败");
process.exit(failed === 0 ? 0 : 1);
