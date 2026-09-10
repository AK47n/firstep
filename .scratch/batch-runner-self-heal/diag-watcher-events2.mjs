// 诊断（工单 batch-runner-self-heal/01 排查用）：为什么探针里造的对话框/异常事件
// 到不了「旁听连接」？本脚本把三方对齐打印：旁听连接的 target、探针（子进程）连上的 target、
// 以及**在旁听连接自己身上**做同样两步时事件是否产生。
// 用法：node .scratch/batch-runner-self-heal/diag-watcher-events2.mjs
import { spawnSync } from "node:child_process";
import { rebuildTab, connect, listTargets } from "../cdp-harness.mjs";

const PORT = 9251;
const PAGE_URL = "http://127.0.0.1:8000/";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const brief = async () => (await listTargets(PORT)).filter((t) => t.type === "page").map((t) => `${t.id.slice(0, 8)} ${t.url}`);

console.log("--- 重建前页面 target ---");
for (const l of await brief()) console.log(`   ${l}`);

const t = await rebuildTab({ port: PORT, pageUrl: PAGE_URL });
console.log(`\n重建得到 target = ${t && t.id.slice(0, 8)}`);
const watcher = await connect({
  port: PORT, pageUrl: PAGE_URL, targetId: t.id, watchTargets: true,
  onTargetChange: (nt) => console.log(`   [跟随] 监听改挂 target = ${nt ? nt.id.slice(0, 8) : "(丢失)"}`),
});
console.log(`旁听连接 target = ${String(watcher.target?.id).slice(0, 8)}（events=${watcher.events.length}）`);

// A：在旁听连接自己身上造事件（对照组）
await watcher.cdp("Runtime.evaluate", { expression: "confirm('diag2-self')", userGesture: true, returnByValue: true }, 8000).catch((e) => console.log(`   自我组失败: ${e.message}`));
await watcher.cdp("Runtime.evaluate", { expression: "setTimeout(() => { throw new Error('diag2-self-boom'); }, 0); true", userGesture: true, returnByValue: true }, 8000).catch(() => {});
await sleep(600);
console.log(`A 对照组（同在旁听连接上造事件）→ events=${watcher.events.length} ${JSON.stringify(watcher.events.map((e) => e.method))}`);

// B：探针子进程（它自己会 rebuildTab 换标签页）
const before = watcher.events.length;
console.log(`\n--- 启动探针子进程前：页面 target ---`);
for (const l of await brief()) console.log(`   ${l}`);
const r = spawnSync(process.execPath, [".scratch/batch-runner-self-heal/probe-red-events.mjs"], { encoding: "utf8", cwd: process.cwd() });
console.log(`探针 exit=${r.status}；输出：${(r.stdout || "").trim().split("\n")[0]}`);
console.log(`--- 探针结束后：页面 target ---`);
for (const l of await brief()) console.log(`   ${l}`);
await sleep(600);
const newEvents = watcher.events.slice(before);
console.log(`\nB 探针组 → 旁听新增事件 ${newEvents.length} 个 ${JSON.stringify(newEvents.map((e) => e.method))}`);
console.log(`旁听连接仍挂在 target ${String(watcher.target?.id).slice(0, 8)}；当前 URL 由 pageTarget 判定 = ${String((await brief()).length)} 个页面 target`);

watcher.close();
