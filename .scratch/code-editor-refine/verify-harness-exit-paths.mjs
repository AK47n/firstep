// 退出路径自检（第十二轮，工单 code-editor-refine/14-harness-transport-migration.md）
//
// 对照的是「冒烟脚本自带迷你 CDP 客户端」的两种致命形态：
//   ① 命令不返回（`beforeunload` 原生对话框挂死）→ 渲染进程侧命令永不返回 →
//      脚本停在**未落定的 top-level await** → Node 事件循环一空即 **exit 13**，且**没有 FAIL 行**；
//   ② 命令只是慢/不返回时，自建 `cdp()` 既无超时也无 reject → 同样的静默挂住。
// 本脚本两项都验，且要求退出码是**显式的 2**（= 传输层异常，与断言失败的 1 分开）。
//
// 用法：node .scratch/code-editor-refine/verify-harness-exit-paths.mjs [--case=timeout|dialog|both]
import { connect } from "../cdp-harness.mjs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const DIR_A = join(ROOT, ".scratch", "code-editor-refine", "sample-proj", "a");

const argv = process.argv.slice(2);
const argOf = (n, d) => { const h = argv.find((a) => a.startsWith(`--${n}=`)); return h ? h.split("=")[1] : d; };
const CASES = String(argOf("case", "both")).split(",");
const want = (name) => CASES.includes("both") || CASES.includes(name);
const EXIT_TRANSPORT = 2;

const bail = (kind) => (e) => {
  console.error(`TRANSPORT(${kind}) ${String((e && e.message) || e).split("\n")[0]}`);
  process.exit(EXIT_TRANSPORT);
};
process.on("unhandledRejection", bail("unhandledRejection"));
process.on("uncaughtException", bail("uncaughtException"));

let failed = 0;
const check = (name, ok, extra) => {
  console.log((ok ? "PASS" : "FAIL") + " " + name + (extra !== undefined ? " [" + extra + "]" : ""));
  if (!ok) failed++;
};

// 用例 1：把命令级超时压到 1ms = 人为造「命令不返回」的等价形态。
// 期望：超时**显式 reject**（不是静默挂住），错误带 `hung:true` 与命令名。
// 放子进程跑：`connect()` 自己也要开 Page/Runtime 域（走同一条超时通道），
// 在同一进程里压 1ms 会把连接建立本身也压掉，测不到「被测命令超时」这件事。
async function caseTimeout() {
  const { spawnSync } = await import("node:child_process");
  const child = join(ROOT, ".scratch", "code-editor-refine", "child-timeout-caught.mjs");
  const r = spawnSync(process.execPath, [child], { encoding: "utf8", cwd: ROOT, timeout: 30000 });
  const out = ((r.stdout || "") + (r.stderr || "")).trim();
  let got = null;
  try { got = JSON.parse(out.split("\n").pop()); } catch {}
  check("命令超时显式报错（不静默挂住）", !!got && got.hung === true, got ? `${got.ms}ms` : out.slice(0, 120));
  check("超时错误点名了命令", !!got && got.method === "Runtime.evaluate");
  check("超时错误带「挂死」提示", !!got && /无响应|挂死/.test(String(got.message)));
  console.log(`   退出路径：这类未落定 await 现在走 unhandledRejection 兜底 → exit ${EXIT_TRANSPORT}（原先 = exit 13 且无 FAIL 行）`);
  console.log(`   现场：${got ? got.message : out.slice(0, 120)}`);
}

// 用例 2：真造一次 `beforeunload` 原生对话框（脏缓冲 + 真实用户手势），再页面内导航。
// 期望：harness 自动应答 → 导航照常完成、后续命令照常返回；无人应答（旧版 mini 客户端，
// 或没开 Page 域导致收不到框）→ 渲染进程停在等应答态、后续命令全超时。
async function caseDialog() {
  const c = await connect({ port: 9251, timeoutMs: 20000 });
  const { cdp, Eval } = c;
  // 本脚本**刻意不**自己 `Page.enable`：`connect()` 现在无条件开 Page 域（第十二轮修），
  // 这一条同时是那条修复的回归断言 —— 不自己 enable 也应当能收到框并自动应答。
  await cdp("Page.reload", { ignoreCache: true });
  const ok = await c.waitFor(`document.readyState === 'complete' && !!document.getElementById('tab-code')`, 20000);
  check("重载后就绪（前置）", ok);
  const dialogsBefore = c.dialogsAccepted;
  // 造脏：打开样例目录 → 点 main.c 成为活动标签 → **真实输入路径**（trusted 按键）
  // 直写 textarea 只改模型，拿不到用户手势；`beforeunload` 对话框需要「脏 + 用户手势」两者
  // （第八轮 `probe-dialog-type.mjs` 已确证），故这里照它的姿势走 trusted 按键。
  await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(DIR_A)}))`);
  await c.waitFor(`document.querySelector('#code-tree [data-code-file="main.c"]')`, 15000);
  await Eval(`document.querySelector('#code-tree [data-code-file="main.c"]')?.click()`);
  await c.waitFor(`document.querySelector('#code-viewer .code-ta')`, 15000);
  await Eval(`(() => { const ta = document.querySelector('#code-viewer .code-ta'); ta.focus(); ta.setSelectionRange(0, 0); return true; })()`);
  for (const ch of "//x") {
    const vk = ch.charCodeAt(0);
    await cdp("Input.dispatchKeyEvent", { type: "keyDown", key: ch, text: ch, windowsVirtualKeyCode: vk, nativeVirtualKeyCode: vk });
    await cdp("Input.dispatchKeyEvent", { type: "keyUp", key: ch, windowsVirtualKeyCode: vk, nativeVirtualKeyCode: vk });
  }
  await c.waitFor(`(async () => (await import('/js/ui/codeeditor.js')).dirtyTabPaths().length > 0)()`, 3000);
  const dirty = await Eval(`(async () => {
    const ed = await import('/js/ui/codeeditor.js');
    return { tabs: ed.openTabPaths(), dirty: ed.dirtyTabPaths() };
  })()`);
  check("已造出脏标签（前置）", !!dirty && (dirty.dirty || []).length > 0, JSON.stringify(dirty));
  // 触发导航：这里用**页面内发起**的 `location.reload()`（第八轮 `probe-dialog-type.mjs`
  // 确证该形态出 `dialogOpening type=beforeunload`，且导航会真的走完 —— 好判定）。
  // 补充实测（第十二轮，`tmp-reload-dialog-probe.mjs` 的取证，见工单 Comments）：
  // **`Page.reload` 在脏页上同样会弹框**，但被应答（accept）时**导航被取消**、页面不重载
  // （`frameNavigated` 0 次、`window` 标记不变）。所以「用 Page.reload 复位脏页」这条路
  // 不成立 —— 复位的正确手段是 `rebuildTab()` 换标签页。
  // 这里的对比点：对话框弹出后渲染进程停在等应答态 —— harness 自动 accept ⇒ 命令照常返回、
  // 导航照常完成；没有自动应答（旧版 mini 客户端，或没开 Page 域）⇒ 卡在等应答、
  // 后续渲染进程侧命令全超时（脚本就以**未落定 top-level await → exit 13** 收场）。
  const navBefore = c.events.filter((e) => e.method === "Page.frameNavigated").length;
  const t0 = Date.now();
  await Eval("location.reload(); 'ok'");                      // 旧版：这一句之后全线挂住
  let navigated = false;
  for (let i = 0; i < 100 && !navigated; i++) {
    navigated = c.events.filter((e) => e.method === "Page.frameNavigated").length > navBefore;
    if (!navigated) await new Promise((r) => setTimeout(r, 200));
  }
  const ms = Date.now() - t0;
  check("脏页导航在守卫内完成（未被对话框卡住）", navigated && ms < 20000, `${ms}ms`);
  const dialogEvents = c.events.filter((e) => e.method === "Page.javascriptDialogOpening");
  console.log(`   [原始事件] dialogOpening=${JSON.stringify(dialogEvents.map((e) => e.params && e.params.type))}`);
  check("出现 beforeunload 对话框", dialogEvents.length > 0 && dialogEvents.some((e) => e.params && e.params.type === "beforeunload"));
  check("对话框被自动应答（accept）", c.dialogsAccepted > dialogsBefore,
    `应答 ${c.dialogsAccepted - dialogsBefore} 次`);
  const alive = await c.waitFor("document.readyState === 'complete'", 20000)
    ? "complete" : await Eval("document.readyState").catch((e) => "err:" + e.message);
  check("应答后页面恢复正常（可继续求值）", alive === "complete", String(alive));
  c.close();
}

// 用例 3（关键一条）：把「命令超时且**没有 try/catch**」放进子进程跑，验退出码。
// 这正是「旧脚本 await openFile 挂住 → exit 13」的同形场景：期望 **exit 2 + TRANSPORT 行**，
// 而不是 exit 13 且无任何 FAIL/诊断行。
async function caseExitPath() {
  const { spawnSync } = await import("node:child_process");
  const child = join(ROOT, ".scratch", "code-editor-refine", "child-timeout-no-catch.mjs");
  const r = spawnSync(process.execPath, [child], { encoding: "utf8", cwd: ROOT, timeout: 30000 });
  const out = (r.stdout || "") + (r.stderr || "");
  check("超时未被捕获时退出码 = 2（传输层），不是 13", r.status === 2, `exit=${r.status}`);
  check("退出前打出 TRANSPORT 诊断行", /TRANSPORT\(/.test(out));
  check("退出前点名了超时命令", /无响应|挂死/.test(out));
  console.log("   " + out.trim().split("\n").slice(0, 2).join("\n   "));
}

if (want("timeout")) await caseTimeout();
if (want("dialog")) await caseDialog();
if (want("exit-path")) await caseExitPath();
console.log(`\n${failed ? "FAIL" : "OK"}（断言失败 ${failed} 项）`);
process.exit(failed ? 1 : 0);
