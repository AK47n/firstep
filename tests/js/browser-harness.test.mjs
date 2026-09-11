// tests/js/browser-harness.test.mjs —— 浏览器姿势助手的纯件测试（工单 real-acceptance/07）。
//
// 助手不 import playwright（page 由调用方传进来），所以这里用**假 page** 就能把「姿势」
// 本身钉住：调用顺序、可见性判据、超时与 evaluate 抛错的语义。真机面仍由 B24 脚本
// （.scratch/revise-deepen/verify-16-revise-render.mjs）复跑覆盖。
import test from "node:test";
import assert from "node:assert/strict";

import {
  cardSelector, observationDone, asObservation, pollUntil, expandCard,
} from "../../.scratch/browser-harness.mjs";

// --- 假 page（轮询面）：evaluate 依次吐脚本化的观测 ---
function pollingPage(observations) {
  const calls = [];
  let i = 0;
  return {
    calls,
    async evaluate() {
      calls.push({ op: "evaluate" });
      return observations[Math.min(i++, observations.length - 1)];
    },
    async waitForTimeout(ms) { calls.push({ op: "waitForTimeout", ms }); },
  };
}

// --- 假 document + 页面（展开 / 页签面）：evaluate 真跑页面回调（document 用桩）---
function fakeDom() {
  const clicked = [];
  const make = (sel, { collapsed = false } = {}) => {
    const classes = new Set(collapsed ? ["card", "collapsed"] : ["card"]);
    return {
      sel,
      classList: {
        contains: (c) => classes.has(c),
        remove: (c) => { classes.delete(c); },
        has: (c) => classes.has(c),
      },
      click: () => clicked.push(sel),
    };
  };
  return { clicked, make };
}

// nodes：选择器 → 元素（未登记的返回 null）。page.evaluate 在 node 侧执行回调。
function domPage(nodes, { attachedThrow = false, visibleThrow = false, visibleSelectors = null } = {}) {
  const calls = [];
  globalThis.document = { querySelector: (sel) => nodes[sel] || null };
  return {
    calls,
    async evaluate(fn, arg) { calls.push({ op: "evaluate" }); return fn(arg); },
    async waitForSelector(sel, opts = {}) {
      calls.push({ op: "waitForSelector", sel, state: opts.state, timeout: opts.timeout });
      if (opts.state === "attached" && attachedThrow) throw new Error("attached timeout");
      if (opts.state === "visible" && visibleThrow) throw new Error("visible timeout");
      if (opts.state === "visible" && visibleSelectors && !visibleSelectors.includes(sel)) {
        throw new Error("visible timeout");
      }
      return {};
    },
    async waitForTimeout(ms) { calls.push({ op: "waitForTimeout", ms }); },
  };
}

test("cardSelector：id / #id / 复合选择器都归一", () => {
  assert.equal(cardSelector("card-revise"), "#card-revise");
  assert.equal(cardSelector("#card-fix-center"), "#card-fix-center");
  assert.equal(cardSelector('  #revise-tabs .revise-tab[data-tab="revise"]  '),
    '#revise-tabs .revise-tab[data-tab="revise"]');
  assert.throws(() => cardSelector(""), /cardId 不能为空/);
});

test("observationDone / asObservation：{done} 判据与非对象包装", () => {
  assert.equal(observationDone({ done: true, st: "x" }), true);
  assert.equal(observationDone({ done: false, st: "x" }), false);
  assert.equal(observationDone(null), false);
  assert.equal(observationDone(true), true);          // 布尔真值也认
  assert.equal(observationDone(0), false);
  assert.deepEqual(asObservation(true), { value: true });
  assert.deepEqual(asObservation({ done: true }), { done: true });
});

test("pollUntil：轮询到 done，返回最后一次观测 + 元信息（不自己再存一份）", async () => {
  const page = pollingPage([
    { done: false, st: "轮次 1" },
    { done: false, st: "轮次 2" },
    { done: true, st: "分析完成", msg: "" },
  ]);
  const out = await pollUntil(page, () => ({}), { timeoutMs: 5000, every: 1, label: "分析" });
  assert.equal(out.done, true);
  assert.equal(out.st, "分析完成");          // 终态快照与判定同源
  assert.equal(out.msg, "");
  assert.equal(out.timeout, undefined);
  assert.equal(out.observations, 3);
  assert.equal(page.calls.filter((c) => c.op === "evaluate").length, 3);
  // 间隔用本地 sleep（不是 page.waitForTimeout）：页面关了也照样能等到超时，
  // 助手不绑 playwright 生命周期
  assert.equal(page.calls.filter((c) => c.op === "waitForTimeout").length, 0);
});

test("pollUntil：超时如实返回（timeout:true + 最后观测），并往 stderr 打一行", async () => {
  const page = pollingPage([{ done: false, st: "一直没动" }]);
  const errs = [];
  const orig = console.error;
  console.error = (...a) => errs.push(a.join(" "));
  let out;
  try {
    out = await pollUntil(page, () => ({}), { timeoutMs: 20, every: 5, label: "执行" });
  } finally { console.error = orig; }
  assert.equal(out.done, false);
  assert.equal(out.timeout, true);
  assert.equal(out.st, "一直没动");
  assert.equal(out.label, "执行");
  assert.ok(out.observations >= 2, `至少轮询两次（实测 ${out.observations}）`);
  assert.match(errs.join("\n"), /轮询超时（执行，20ms）/);
});

test("pollUntil：evaluate 抛错按「未就绪」处理，不炸；之后转绿仍算 done", async () => {
  let n = 0;
  const page = {
    async evaluate() {
      n++;
      if (n === 1) throw new Error("Execution context was destroyed");
      return { done: n >= 2 };
    },
    async waitForTimeout() {},
  };
  const out = await pollUntil(page, () => ({}), { timeoutMs: 5000, every: 1 });
  assert.equal(out.done, true);
  assert.equal(out.observations, 2);
});

test("expandCard：顺序 = attached → 页面内展开+点页签 → visible 见证", async () => {
  const dom = fakeDom();
  const tabSel = '#revise-tabs .revise-tab[data-tab="revise"]';
  const nodes = {
    "#card-revise": dom.make("#card-revise", { collapsed: true }),
    [tabSel]: dom.make(tabSel),
  };
  const page = domPage(nodes, { visibleSelectors: [tabSel] });
  try {
    const out = await expandCard(page, "card-revise", tabSel);
    // 见证 = 页签条：折叠态 `.card.collapsed > *:not(h2)` 整块 display:none，
    // 页签条可见 ⇔ 卡真的展开了
    assert.deepEqual(page.calls.map((c) => c.op + (c.state ? ":" + c.state : "")),
      ["waitForSelector:attached", "evaluate", "waitForSelector:visible"]);
    assert.equal(page.calls[2].sel, tabSel);
    assert.equal(nodes["#card-revise"].classList.has("collapsed"), false, "折叠类已摘掉");
    assert.deepEqual(dom.clicked, [tabSel], "页签被点了一次");
    assert.equal(out.wasCollapsed, true);
    assert.equal(out.tabFound, true);
    assert.equal(out.witness, tabSel);
  } finally { delete globalThis.document; }
});

test("expandCard：无页签时见证 = 卡本身；已展开的卡不会重复点页签", async () => {
  const dom = fakeDom();
  const nodes = { "#card-fix-center": dom.make("#card-fix-center", { collapsed: false }) };
  const page = domPage(nodes);
  try {
    const out = await expandCard(page, "#card-fix-center");
    assert.equal(page.calls[2].sel, "#card-fix-center");
    assert.deepEqual(dom.clicked, []);
    assert.equal(out.wasCollapsed, false);
    assert.equal(out.tabFound, false);
  } finally { delete globalThis.document; }
});

test("expandCard：见证一直不可见 → 抛错带上下文（卡所在步骤没显示 / 页签选择器不对）", async () => {
  const dom = fakeDom();
  const tabSel = '#revise-tabs .revise-tab[data-tab="revise"]';
  const nodes = { "#card-revise": dom.make("#card-revise", { collapsed: true }) };
  const page = domPage(nodes, { visibleThrow: true });
  try {
    await assert.rejects(
      () => expandCard(page, "card-revise", tabSel, { visibleMs: 10 }),
      /仍不可见（10ms）[\s\S]*结果区要走过一次生成/);
  } finally { delete globalThis.document; }
});

test("expandCard：卡不在 DOM（attached 也等不到）→ 原样抛 waitForSelector 的错", async () => {
  const page = domPage({}, { attachedThrow: true });
  try {
    await assert.rejects(() => expandCard(page, "card-nope", "", { attachMs: 10 }), /attached timeout/);
  } finally { delete globalThis.document; }
});
