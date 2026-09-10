// 子进程：验证「命令超时」在**没有 try/catch**时的退出码。
// 这正是旧脚本「`await openFile` 挂住 → 未落定 top-level await → exit 13」的同形场景，
// 换成 harness 之后应当是**显式 exit 2**（传输层异常），且带 TRANSPORT 行。
// 只由 `.scratch/code-editor-refine/verify-harness-exit-paths.mjs --case=exit-path` 调用。
import { connect } from "../cdp-harness.mjs";

const bail = (kind) => (e) => {
  console.error(`TRANSPORT(${kind}) ${String((e && e.message) || e).split("\n")[0]}`);
  process.exit(2);
};
process.on("unhandledRejection", bail("unhandledRejection"));
process.on("uncaughtException", bail("uncaughtException"));

const c = await connect({ port: 9251, timeoutMs: 1 });
await c.cdp("Runtime.evaluate", { expression: "1+1", returnByValue: true });   // 故意不 catch
console.log("不应到达这里（命令本应超时）");
process.exit(0);
