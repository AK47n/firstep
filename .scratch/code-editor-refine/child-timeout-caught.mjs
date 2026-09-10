// 子进程（可复用）：用 1ms 命令超时造一次「命令不返回」，**捕获**它并打印形态。
// 只由 `.scratch/code-editor-refine/verify-harness-exit-paths.mjs --case=timeout` 调用。
// `connect()` 现在会先开 Page/Runtime 域（命令走同一条超时通道），故超时被测命令要等
// **连接建立之后**再发 —— 断言的是「命令级超时显式报错」这件事本身，不是某个具体调用点的耗时。
import { connect } from "../cdp-harness.mjs";

const c = await connect({ port: 9251, timeoutMs: 1 });
const t0 = Date.now();
let hung = null;
try { await c.cdp("Runtime.evaluate", { expression: "1+1", returnByValue: true }); }
catch (e) { hung = e; }
c.close();
console.log(JSON.stringify({
  hung: !!(hung && hung.hung === true),
  method: hung && hung.method,
  message: hung && hung.message,
  ms: Date.now() - t0,
}));
process.exit(hung && hung.hung === true && /无响应|挂死/.test(String(hung.message)) ? 0 : 1);
