// 诊断（工单 batch-runner-self-heal/01 排查用）：常驻监听到底收不收得到事件？
// 已知：批跑器旁听连接（connect 挂 targetId）在探针跑完后 events.length 为 0。
// 本脚本直接验证两件事：① 旁听连接能否收到**另一条连接**造成的对话框/异常事件；
// ② `confirm()` 在 userGesture 下是否是可靠的事件源（比「脏缓冲 + reload」可控）。
// 用法：node .scratch/batch-runner-self-heal/diag-watcher-events.mjs
import { rebuildTab, connect } from "../cdp-harness.mjs";

const PORT = 9251;
const PAGE_URL = "http://127.0.0.1:8000/";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const t = await rebuildTab({ port: PORT, pageUrl: PAGE_URL });
console.log(`重建标签页：${t && t.id.slice(0, 8)}`);

// 旁听连接：与批跑器一致（按 targetId 挂上，只旁听）
const watcher = await connect({ port: PORT, pageUrl: PAGE_URL, targetId: t.id });
console.log(`旁听连接已建立（target ${String(watcher.target?.id).slice(0, 8)}）`);

// 演员连接：另一条连接，用 userGesture 触发 confirm() 对话框
const actor = await connect({ port: PORT, pageUrl: PAGE_URL, targetId: t.id });
console.log(`演员连接已建立（target ${String(actor.target?.id).slice(0, 8)}）`);

await actor.cdp("Runtime.evaluate", { expression: "true", returnByValue: true });
await sleep(300);
console.log(`[基线] 旁听收到事件 ${watcher.events.length} 个（重建后页面自身的加载事件）`);

// ① 对话框（userGesture + autoDialog 自动应答）
const dlg = await actor.cdp("Runtime.evaluate", { expression: "confirm('probe-dialog')", userGesture: true, returnByValue: true }, 8000)
  .catch((e) => ({ err: String(e.message || e) }));
await sleep(500);
console.log(`① 对话框后：旁听事件 ${watcher.events.length} 个；演员返回 ${JSON.stringify(dlg).slice(0, 120)}`);

// ② 页面内未捕获异常
await actor.cdp("Runtime.evaluate", { expression: "setTimeout(() => { throw new Error('probe-async-boom'); }, 0); true", userGesture: true, returnByValue: true }, 8000).catch(() => {});
await sleep(500);
console.log(`② 异步未捕获异常后：旁听事件 ${watcher.events.length} 个`);

const methods = {};
for (const e of watcher.events) methods[e.method] = (methods[e.method] || 0) + 1;
console.log(`旁听收到的全部事件类型：${JSON.stringify(methods)}`);

watcher.close();
actor.close();
console.log(`结论：${watcher.events.length ? "旁听连接能收到另一条连接造成的事件（批跑器侧机制成立）" : "旁听连接收不到 —— 批跑器侧机制有缺口"}`);
