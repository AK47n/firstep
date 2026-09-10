// 取证探针（工单 batch-runner-self-heal/01）：**真红 + 事件序列**——连上真实 Chrome 制造两类
// 可观测事件，然后以断言失败退出（exit 1）。目的：让批跑器的常驻监听收到**真实 CDP 事件**
// 并落盘，从而验证「非绿支次自动落盘事件序列」这一段是实录，而不是事后推断。
//
// 两个事件源（第十三轮实测校准 —— 详见 diag-watcher-events.mjs）：
//   ① `Page.javascriptDialogOpening`：`Runtime.evaluate{userGesture:true}` 里调 `confirm()`，
//      真会弹原生对话框（第二版曾用「脏缓冲 + Input 按键 + location.reload()」复刻 beforeunload 框，
//      但按键没真正弄脏编辑器模型 ⇒ 不弹框 ⇒ 事件为零；这里改用可控事件源）。
//   ② `Runtime.exceptionThrown`：页面内 `setTimeout(() => { throw … })` 的**未捕获异步异常**
//      （用 `Runtime.evaluate` 直接 throw 不行：那是 eval 自身的异常，不算未捕获）。
//
// 用法：node .scratch/batch-runner-self-heal/probe-red-events.mjs [--port=9251] [--page=…] [--target=<批跑器的标签页 id>]
// 复用批跑器标签页的约定：环境变量 `CDP_BATCH_TARGET`（批跑器每支次按此变量把标签页交给脚本）。
// 支持它的脚本**不再自己 rebuildTab()** —— 这样脚本与批跑器的旁听连接在同一个 target 上，
// 事件才收得到；否则脚本换标签页，换页瞬间的事件会漏（见 cdp-harness.mjs 的 watchTargets 注释）。
import { connect, rebuildTab } from "../cdp-harness.mjs";

const argv = process.argv.slice(2);
const argOf = (n, d) => { const h = argv.find((a) => a.startsWith(`--${n}=`)); return h ? h.split("=")[1] : d; };
const PORT = Number(argOf("port", "9251"));
const PAGE_URL = argOf("page", "http://127.0.0.1:8000/");
const TARGET_HINT = argOf("target", process.env.CDP_BATCH_TARGET || "");

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

try {
  if (TARGET_HINT) {
    console.log(`（复用批跑器标签页 ${TARGET_HINT.slice(0, 8)}：不自己重建）`);
  } else {
    await rebuildTab({ port: PORT, pageUrl: PAGE_URL });
    // 停顿：本探针自己换标签页，而批跑器的常驻监听要 300ms 轮询才发现目标变了并改挂过来。
    // 若一上来就弹对话框，那个事件会落在「改挂之前」而被漏掉（旁听连接的固有限制，
    // 见 cdp-harness.mjs watchTargets 注释）—— 停顿 1.2s 让旁听先挂稳，再造事件。
    await sleep(1200);
  }
  const c = await connect({ port: PORT, pageUrl: PAGE_URL, timeoutMs: 20000, targetId: TARGET_HINT || null });
  await c.ready();

  // ① 未捕获异步异常 → Runtime.exceptionThrown
  await c.Eval("setTimeout(() => { throw new Error('probe-red-events: 未捕获异步异常'); }, 0); true");

  // ② 原生对话框 → Page.javascriptDialogOpening（被 harness 自动应答）
  await c.cdp("Runtime.evaluate", { expression: "confirm('probe-red-events 对话框')", userGesture: true, returnByValue: true }, 8000)
    .catch((e) => console.log(`TRANSPORT(probe-dialog): ${String(e.message || e)}`));

  // ③ 再补一个未捕获异常：与 ② 一起保证「异常 + 对话框」两类事件都在监听就位后产生
  await c.Eval("setTimeout(() => { throw new Error('probe-red-events: 第二个未捕获异常'); }, 0); true");

  await sleep(900);          // 给旁听连接时间收事件
  c.close();
} catch (e) {
  console.log(`TRANSPORT(probe): ${String(e && e.message || e)}`);
}

console.log("PASS 12 / FAIL 1 | 真红探针：断言失败（exit 1），事件序列应由批跑器落盘");
process.exit(1);
