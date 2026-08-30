// ux-polish-02 探针：工单 06 冒烟——doing 卡阶段槽、全部完成「去交付」、
// details 展开态重建保留。（无 LLM；每次重写临时任务清单）
import { writeFileSync } from "node:fs";
const CDP = 9251;
const pageUrl = "http://127.0.0.1:8000/";
const FAKE_DIR = "C:/Users/luoji/AppData/Local/Temp/dsh-ux-t04-proj";
const PLAN_PATH = FAKE_DIR.replace(/\//g, "\\") + "\\.contest_tasks.json";
const plan = (tasks) => writeFileSync(PLAN_PATH, JSON.stringify({ version: 1, generated_at: "2026-08-30T00:00:00", tasks, score_points: [] }), "utf8");

let targets = null;
for (let i = 0; i < 50 && !targets; i++) {
  try { targets = await (await fetch(`http://127.0.0.1:${CDP}/json/list`)).json(); } catch {}
  if (!targets || !targets.length) await new Promise((r) => setTimeout(r, 300));
}
if (!targets) { console.error("CDP 不可达"); process.exit(1); }
const page = targets.find((t) => t.type === "page");
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws error")); });

let seq = 0;
const pending = new Map();
const jsErrors = [];
ws.onmessage = (ev) => {
  const msg = JSON.parse(ev.data);
  if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
  if (msg.method === "Runtime.exceptionThrown") {
    jsErrors.push(msg.params.exceptionDetails?.exception?.description || "exception");
  }
};
const cdp = (method, params = {}) =>
  new Promise((resolve) => { const id = ++seq; pending.set(id, resolve); ws.send(JSON.stringify({ id, method, params })); });
const Eval = async (expr) => {
  const r = await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) throw new Error("eval 失败: " + (r.result.exceptionDetails.exception?.description || JSON.stringify(r.result.exceptionDetails)));
  return r.result?.result?.value;
};

await cdp("Runtime.enable");
await cdp("Page.enable");
await cdp("Network.setCacheDisabled", { cacheDisabled: true });
await cdp("Network.clearBrowserCache");

let failed = 0;
const check = (name, ok, extra) => {
  console.log((ok ? "PASS" : "FAIL") + " " + name + (extra !== undefined ? " [" + extra + "]" : ""));
  if (!ok) failed++;
};
const load = async () => {
  const token = "np=" + Date.now();
  await cdp("Page.navigate", { url: pageUrl + "?" + token });
  for (let i = 0; i < 120; i++) {
    try {
      const st = await Eval(`({ href: location.href, rs: document.readyState, ov: !!document.getElementById('gen-overview') })`);
      if (st.href.includes(token) && st.rs === "complete" && st.ov) break;
    } catch {}
    await new Promise((r) => setTimeout(r, 250));
  }
  await Eval(`document.getElementById('res-dir').textContent = ${JSON.stringify(FAKE_DIR)}`);
  await Eval(`(async () => { const m = await import('/js/ui/goto-tasks.js'); await m.goTaskProgress(); return true; })()`);
  await new Promise((r) => setTimeout(r, 900));
};

// ---- 阶段 A：全部完成 → 去交付 ----
plan([
  { id: "t1", title: "已完成卡", description: "编译绿", status: "verified", verify: "compile" },
  { id: "t2", title: "已跳过卡", description: "用户放弃", status: "skipped", verify: "compile" },
]);
await load();
const doneLine = await Eval(`({
  hasDone: document.getElementById('tasks-overview').textContent.includes('全部完成'),
  hasBtn: !!document.querySelector('.btn-task-goto-delivery'),
})`);
check("全部完成显示「去交付」按钮", doneLine.hasDone && doneLine.hasBtn, JSON.stringify(doneLine));
await Eval(`document.querySelector('.btn-task-goto-delivery').click()`);
await new Promise((r) => setTimeout(r, 250));
const deliveryActive = await Eval(`document.querySelector('#revise-tabs .revise-tab[data-tab="delivery"]').classList.contains('active')`);
check("点「去交付」→ 交付页签激活", deliveryActive === true);

// ---- 阶段 B：doing 阶段槽 + details 展开态保留 ----
plan([
  { id: "t1", title: "已完成卡", description: "编译绿", status: "verified", verify: "compile",
    iterations: [{ seq: 1, kind: "execute", status: "verified", compile_summary: "0 错误", checklist: ["灯亮", "轮转"], what_changed: "实现了", user_action: "观察", at: "2026-08-30T00:00:00" }] },
  { id: "t2", title: "待做卡", description: "待跳过", status: "pending", verify: "compile" },
  { id: "t3", title: "执行中卡", description: "进行中", status: "doing", verify: "compile" },
  { id: "t4", title: "待做卡2", description: "排队", status: "pending", verify: "compile" },
]);
await load();
const phase = await Eval(`(() => {
  const c = document.querySelector('.task-card[data-task-id="t3"]');
  return {
    hasPhase: !!c.querySelector('.task-phase'),
    hasSpinner: !!c.querySelector('.task-spinner'),
    text: c.querySelector('.task-phase-text') ? c.querySelector('.task-phase-text').textContent : '',
  };
})()`);
check("doing 卡渲染阶段槽（spinner + 执行中…）", phase.hasPhase && phase.hasSpinner && phase.text.includes("执行中"), JSON.stringify(phase));

// 打开 t1 自检清单 details → 跳过 t2（触发网格重建）→ 清单应保持展开
//（更多菜单会被「点外部关闭」委托收起——那是既有预期行为；清单/本轮变化
// 不在该委托内，恢复才有价值）
const checklistOpen = await Eval(`(() => {
  const d = document.querySelector('.task-card[data-task-id="t1"] .task-check-details');
  if (!d) return false;
  d.open = true;
  return true;
})()`);
check("前置：t1 有自检清单 details 并已展开", checklistOpen === true);
await Eval(`document.querySelector('.task-card[data-task-id="t2"] .btn-task-skip').click()`);
await new Promise((r) => setTimeout(r, 200));
await Eval(`document.querySelector('.ref-files-overlay [data-confirm-ok]').click()`);
await new Promise((r) => setTimeout(r, 800));
const after = await Eval(`(() => {
  const c = document.querySelector('.task-card[data-task-id="t1"]');
  const d = c.querySelector('.task-check-details');
  const t2 = document.querySelector('.task-card[data-task-id="t2"]');
  return {
    checklistOpen: d && d.open,
    t2Badge: t2 ? t2.querySelector('.badge').textContent : '',
  };
})()`);
check("渲染重建后 t1 自检清单展开态保留", after.checklistOpen === true, JSON.stringify(after));
check("t2 跳过生效（已跳过）", after.t2Badge.includes("已跳过"), after.t2Badge);

check("无未捕获 JS 异常", jsErrors.length === 0, jsErrors.join(" | ").slice(0, 300));
console.log((failed ? "FAILED " : "OK ") + "failed=" + failed);
process.exit(failed ? 1 : 0);
