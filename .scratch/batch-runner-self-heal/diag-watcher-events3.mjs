// 诊断（工单 batch-runner-self-heal/01 排查用之三）：把批跑器建立监听的那几行**逐字复刻**，
// 再看它到底收不收得到事件，从而区分「批跑器的接线姿势错了」与「环境/时序问题」。
// 用法：node .scratch/batch-runner-self-heal/diag-watcher-events3.mjs
import { rebuildTab, connect } from "../cdp-harness.mjs";

const PORT = 9251;
const PAGE_URL = "http://127.0.0.1:8000/";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let currentTargetId = null;

// ① 批跑器开头的建立姿势
let watcher = await connect({
  port: PORT, pageUrl: PAGE_URL, timeoutMs: 20000, watchTargets: true,
  onTargetChange: (nt) => { if (nt) currentTargetId = nt.id; },
});
console.log(`建立：watcher.target=${String(watcher.target?.id).slice(0, 8)} events=${watcher.events.length}`);

// ② 批跑器每支前的重建 + 重挂
const t = await rebuildTab({ port: PORT, pageUrl: PAGE_URL });
currentTargetId = t.id;
console.log(`重建得到 ${t.id.slice(0, 8)}；重挂前 watcher.target=${String(watcher.target?.id).slice(0, 8)}`);
const old = watcher;
watcher = await connect({
  port: PORT, pageUrl: PAGE_URL, timeoutMs: 20000, targetId: t.id, watchTargets: true,
  onTargetChange: (nt) => { if (nt) currentTargetId = nt.id; },
});
old.close();
console.log(`重挂后 watcher.target=${String(watcher.target?.id).slice(0, 8)}（期望 ${t.id.slice(0, 8)}）currentTargetId=${String(currentTargetId).slice(0, 8)}`);

// ③ 清空缓冲（批跑器会做），然后按批跑器的方式跑一支会弹框+抛异常的脚本
watcher.events.splice(0, watcher.events.length);
console.log(`清空后 events=${watcher.events.length}`);

const { spawnSync } = await import("node:child_process");
const r = spawnSync(process.execPath, [".scratch/batch-runner-self-heal/probe-red-events.mjs"], {
  encoding: "utf8", cwd: process.cwd(),
  env: { ...process.env, PYTHONIOENCODING: "utf8", CDP_BATCH_TARGET: currentTargetId },
});
console.log(`探针 exit=${r.status}；首行：${(r.stdout || "").trim().split("\n")[0]}`);
await sleep(800);

const methods = {};
for (const e of watcher.events) methods[e.method] = (methods[e.method] || 0) + 1;
console.log(`\n旁听收到 ${watcher.events.length} 个事件：${JSON.stringify(methods)}`);
console.log(`当前 watcher.target=${String(watcher.target?.id).slice(0, 8)}`);
watcher.close();
