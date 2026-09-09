// 收口自测（工单 code-editor-cdp-hang/01）：证明「每支前重建标签页」约定真的挡住挂死。
//
// 三组：
//   ① 对照组（不重建）：smoke-04 → smoke-05 背靠背 → 预期第 2 支挂死（复现第七轮现象）
//   ② 约定组（重建）：同一序列，每支前重建标签页 → 预期两支都绿
//   ③ harness 组：直接用 cdp-harness.mjs 连页面 + 造脏 + reload → 对话框被自动应答、不挂
//
// 用法：node .scratch/code-editor-cdp-hang/self-test.mjs
import { spawnSync } from "node:child_process";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { writeSync, mkdirSync, writeFileSync } from "node:fs";
import { rebuildTab, connect, pageTarget } from "../cdp-harness.mjs";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));   // 仓库根（本文件在 .scratch/<批次>/ 下）
const PORT = 9251, PAGE_URL = "http://127.0.0.1:8000/";
const SAMPLE = join(ROOT, ".scratch", "code-editor-cdp-hang", "sample-proj");
mkdirSync(SAMPLE, { recursive: true });
writeFileSync(join(SAMPLE, "guard.c"), "int main(void) { return 0; }\n");
const log = (s) => writeSync(2, s + "\n");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const A = ".scratch/code-page-vscode-overhaul/smoke-04.mjs";
const B = ".scratch/code-page-vscode-overhaul/smoke-05.mjs";

function run(script) {
  const t0 = Date.now();
  const r = spawnSync(process.execPath, [join(ROOT, script)], { encoding: "utf8", timeout: 60000, cwd: ROOT });
  const timedOut = !!(r.error && r.error.code === "ETIMEDOUT");
  return { exit: r.status, ms: Date.now() - t0, timedOut, tail: (r.stdout || "").trim().split("\n").slice(-1)[0] };
}

let pass = 0, fail = 0;
const check = (name, ok, extra) => { log(`${ok ? "PASS" : "FAIL"} ${name}${extra !== undefined ? " [" + extra + "]" : ""}`); ok ? pass++ : fail++; };

// ---------- ① 对照组：不重建 ----------
log("=== ① 对照组（不重建标签页）===");
await rebuildTab({ port: PORT, pageUrl: PAGE_URL });
const a1 = run(A);
log(`  ${A}: exit=${a1.exit} ${a1.ms}ms | ${a1.tail}`);
const b1 = run(B);
log(`  ${B}: exit=${b1.exit} ${b1.ms}ms timedOut=${b1.timedOut} | ${b1.tail}`);
const t1 = await pageTarget({ port: PORT, pageUrl: PAGE_URL, anyPage: true });
let probe1 = null;
try { const c = await connect({ port: PORT, pageUrl: PAGE_URL, timeoutMs: 6000 }); probe1 = await c.Eval("1+1", 6000); c.close(); }
catch (e) { probe1 = "HANG: " + e.message; }
check("对照组：第 2 支挂死（复现现象）", b1.timedOut === true, `timedOut=${b1.timedOut}`);
check("对照组：挂死现场命令不返回", typeof probe1 === "string" && probe1.startsWith("HANG"), String(probe1));
check("对照组：第 1 支本身全绿（证明挂死是残留脏缓冲导致）", a1.exit === 0 && /ALL PASS/.test(a1.tail), a1.tail);

// ---------- ② 约定组：每支前重建 ----------
log("\n=== ② 约定组（每支前重建标签页）===");
await rebuildTab({ port: PORT, pageUrl: PAGE_URL });
const a2 = run(A);
log(`  ${A}: exit=${a2.exit} ${a2.ms}ms | ${a2.tail}`);
await rebuildTab({ port: PORT, pageUrl: PAGE_URL });
const b2 = run(B);
log(`  ${B}: exit=${b2.exit} ${b2.ms}ms timedOut=${b2.timedOut} | ${b2.tail}`);
check("约定组：第 1 支全绿", a2.exit === 0 && /ALL PASS/.test(a2.tail), a2.tail);
check("约定组：第 2 支全绿（挂死消失）", b2.exit === 0 && /ALL PASS/.test(b2.tail), b2.tail);
check("约定组：第 2 支未超时", b2.timedOut === false, `timedOut=${b2.timedOut}`);

// ---------- ③ harness 组：脏缓冲 + reload 自动应答 ----------
log("\n=== ③ harness 组（connect 自动应答对话框）===");
const t3 = await rebuildTab({ port: PORT, pageUrl: PAGE_URL });
check("harness：重建标签页可用", !!t3, t3 && t3.id.slice(0, 8));
const c = await connect({ port: PORT, pageUrl: PAGE_URL, timeoutMs: 8000 });
await c.cdp("Page.enable"); await c.cdp("Runtime.enable");
await c.Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`);
await c.waitFor(`!!document.querySelector('#code-tree [data-code-file="guard.c"]')`, 8000);
await c.Eval(`document.querySelector('#code-tree [data-code-file="guard.c"]')?.click()`);
await c.waitFor(`!!document.querySelector('#code-viewer .code-ta')`, 8000);
await c.Eval(`(() => { const ta = document.querySelector('#code-viewer .code-ta'); ta.focus(); ta.setSelectionRange(0,0); return true; })()`);
for (const ch of "//x") {
  await c.cdp("Input.dispatchKeyEvent", { type: "keyDown", key: ch, text: ch, windowsVirtualKeyCode: ch.charCodeAt(0), nativeVirtualKeyCode: ch.charCodeAt(0) });
  await c.cdp("Input.dispatchKeyEvent", { type: "keyUp", key: ch, windowsVirtualKeyCode: ch.charCodeAt(0), nativeVirtualKeyCode: ch.charCodeAt(0) });
}
await sleep(400);
const dirty = await c.Eval(`import('/js/ui/codeeditor.js').then((m) => m.dirtyTabPaths())`);
check("harness：前置脏缓冲已建立", Array.isArray(dirty) && dirty.includes("guard.c"), JSON.stringify(dirty));
await c.cdp("Page.reload", { ignoreCache: true }, 8000);
await sleep(2000);
const ready = await c.Eval("document.readyState", 8000).catch((e) => "HANG: " + e.message);
check("harness：reload 后命令返回（不挂死）", ready === "complete", String(ready));
check("harness：beforeunload 对话框被自动应答", c.dialogsAccepted >= 1, `dialogsAccepted=${c.dialogsAccepted}`);
c.close();

log(`\nPASS ${pass} / FAIL ${fail}`);
process.exit(fail ? 1 : 0);
