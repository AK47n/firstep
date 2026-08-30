// ux-polish-02 探针：工单 05 冒烟——failed 卡无「确认通过」、跳过确认弹窗、
// 措辞（恢复此步/重做）与 title 统一。依赖临时工程 .contest_tasks.json（无 LLM）。
import { writeFileSync } from "node:fs";
const CDP = 9251;
const pageUrl = "http://127.0.0.1:8000/";
const FAKE_DIR = "C:/Users/luoji/AppData/Local/Temp/dsh-ux-t04-proj";

// 每次运行重置临时任务清单（上轮「确认跳过」会落盘改状态）
const PLAN = {
  version: 1, generated_at: "2026-08-30T00:00:00",
  tasks: [
    { id: "t1", title: "失败卡测试", description: "编译仍红", status: "failed", verify: "compile" },
    { id: "t2", title: "待做卡测试", description: "等跳过", status: "pending", verify: "compile" },
    { id: "t3", title: "待上板卡测试", description: "需人工确认", status: "unverified", verify: "manual" },
  ],
  score_points: [],
};
writeFileSync(FAKE_DIR.replace(/\//g, "\\") + "\\.contest_tasks.json", JSON.stringify(PLAN), "utf8");

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
const token = "np=" + Date.now();
await cdp("Page.navigate", { url: pageUrl + "?" + token });
for (let i = 0; i < 120; i++) {
  try {
    const st = await Eval(`({ href: location.href, rs: document.readyState, ov: !!document.getElementById('gen-overview') })`);
    if (st.href.includes(token) && st.rs === "complete" && st.ov) break;
  } catch {}
  await new Promise((r) => setTimeout(r, 250));
}

// 加载临时工程（结果目录 + 自动加载上下文 → 任务清单读盘）
await Eval(`document.getElementById('res-dir').textContent = ${JSON.stringify(FAKE_DIR)}`);
await Eval(`(async () => { const m = await import('/js/ui/goto-tasks.js'); await m.goTaskProgress(); return true; })()`);
await new Promise((r) => setTimeout(r, 900));
const cards = await Eval(`(() => {
  const out = {};
  document.querySelectorAll('.task-card').forEach((c) => {
    const id = c.dataset.taskId;
    if (!id) return;
    out[id] = {
      title: c.querySelector('.head .slug') ? c.querySelector('.head .slug').textContent : '',
      hasMark: !!c.querySelector('.btn-task-mark'),
      hasRun: !!c.querySelector('.btn-task-run'),
      hasRevert: !!c.querySelector('.btn-task-revert'),
      hasSkip: !!c.querySelector('.btn-task-skip'),
      revertLabel: c.querySelector('.btn-task-revert') ? c.querySelector('.btn-task-revert').textContent : '',
      revertTitle: c.querySelector('.btn-task-revert') ? c.querySelector('.btn-task-revert').title : '',
      skipTitle: c.querySelector('.btn-task-skip') ? c.querySelector('.btn-task-skip').title : '',
    };
  });
  return out;
})()`);
check("任务卡已渲染（t1/t2/t3）", !!(cards.t1 && cards.t2 && cards.t3), JSON.stringify(Object.keys(cards)));
check("failed 卡无「确认通过」，保留做/重做", cards.t1 && !cards.t1.hasMark && cards.t1.hasRun && cards.t1.hasRevert, JSON.stringify(cards.t1));
check("unverified 卡保留「确认通过」", cards.t3 && cards.t3.hasMark, JSON.stringify(cards.t3));
check("skip 带 title 提示", cards.t2 && cards.t2.skipTitle.includes("依赖"), cards.t2 && cards.t2.skipTitle);
check("revert 文案统一（failed 卡「重做」+ title 说明）", cards.t1 && cards.t1.revertLabel === "重做" && cards.t1.revertTitle.includes("恢复为待做"), JSON.stringify(cards.t1));

// 跳过确认：点 t2 的跳过 → 弹窗出现 → 取消（不落盘）
await Eval(`document.querySelector('.task-card[data-task-id="t2"] .btn-task-skip').click()`);
await new Promise((r) => setTimeout(r, 200));
const modal1 = await Eval(`({
  exists: !!document.querySelector('.ref-files-overlay'),
  text: document.querySelector('.ref-files-overlay') ? document.querySelector('.ref-files-overlay').textContent : '',
})`);
check("跳过弹确认（文案含连锁影响）", modal1.exists && modal1.text.includes("跳过") && modal1.text.includes("依赖"), modal1.text.slice(0, 120));
await Eval(`document.querySelector('.ref-files-overlay [data-confirm-cancel]').click()`);
await new Promise((r) => setTimeout(r, 200));
const skipState = await Eval(`(() => {
  const c = document.querySelector('.task-card[data-task-id="t2"]');
  return { badge: c ? c.querySelector('.badge').textContent : '', modalGone: !document.querySelector('.ref-files-overlay') };
})()`);
check("取消后不落盘（t2 仍待做）+ 弹窗关闭", skipState.badge.includes("待做") && skipState.modalGone, JSON.stringify(skipState));

// 重新点跳过并确认 → 置为已跳过 + 恢复此步
await Eval(`document.querySelector('.task-card[data-task-id="t2"] .btn-task-skip').click()`);
await new Promise((r) => setTimeout(r, 200));
await Eval(`document.querySelector('.ref-files-overlay [data-confirm-ok]').click()`);
await new Promise((r) => setTimeout(r, 700));
const afterSkip = await Eval(`(() => {
  const c = document.querySelector('.task-card[data-task-id="t2"]');
  return {
    badge: c ? c.querySelector('.badge').textContent : '',
    hasRevert: !!c.querySelector('.btn-task-revert'),
    revertLabel: c.querySelector('.btn-task-revert') ? c.querySelector('.btn-task-revert').textContent : '',
  };
})()`);
check("确认跳过 → 已跳过 + 「恢复此步」", afterSkip.badge.includes("已跳过") && afterSkip.hasRevert && afterSkip.revertLabel === "恢复此步", JSON.stringify(afterSkip));

check("无未捕获 JS 异常", jsErrors.length === 0, jsErrors.join(" | ").slice(0, 300));
console.log((failed ? "FAILED " : "OK ") + "failed=" + failed);
process.exit(failed ? 1 : 0);
