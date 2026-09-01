// fix-center-core.test.mjs —— ui/fix-center-core.js 流程测试（工单 code-ide-ai/05）
// 核心 = 无 DOM 流程：mock globalThis.fetch 提供 SSE 流，断言回调序列 + 状态机。
import test from "node:test";
import assert from "node:assert/strict";
import {
  startFixCenterCore,
  continueFixCenterCore,
  runFixOnceCore,
  subscribeFixCenter,
  isFixRunning,
  fixLoopSnapshot,
  FIX_MAX_ROUNDS,
} from "../../src/contest_generator/static/js/ui/fix-center-core.js";

// ---- SSE 响应构造（与 fx/llm.js parseSSE 契约一致：event: <type>\n data: ...\n\n）----
function sseResponse(events) {
  // events = [[type, payload], ...]
  const enc = new TextEncoder();
  const stream = new ReadableStream({
    start(c) {
      for (const [type, payload] of events) {
        c.enqueue(enc.encode("event: " + type + "\n"
          + "data: " + JSON.stringify(payload) + "\n\n"));
      }
      c.close();
    },
  });
  return new Response(stream, { status: 200, headers: { "Content-Type": "text/event-stream" } });
}

/** fetch 桩：按 URL 分支返回预置 SSE 响应序列；记录调用参数。 */
function mockFetch(routes) {
  const calls = [];
  const orig = globalThis.fetch;
  globalThis.fetch = async (url, opts) => {
    const u = String(url);
    calls.push({ url: u, opts });
    const route = routes[u];
    if (typeof route === "function") return route(u, opts);
    if (route) return sseResponse(route);
    throw new Error("未预置路由：" + u);
  };
  return () => { globalThis.fetch = orig; return calls; };
}

// 编译 SSE 事件（compile_start → done）
const COMPILE_OK = [["compile_start", {}], ["done", {
  passed: true, timed_out: false, error_text: "", duration: 1.2,
  summary: { errors: 0, warnings: 0 }, parsed_errors: [],
}]];
const COMPILE_ERR_ROUND1 = [["compile_start", {}], ["done", {
  passed: false, timed_out: false, duration: 0.8, error_text: "a.c:3: error: bad",
  summary: { errors: 1, warnings: 0 },
  parsed_errors: [{ path: "a.c", line: 3, message: "bad" }],
}]];
const COMPILE_OK_WARN = [["compile_start", {}], ["done", {
  passed: true, timed_out: false, duration: 1.0, error_text: "",
  summary: { errors: 0, warnings: 2 }, parsed_errors: [],
}]];
const COMPILE_TIMEOUT = [["compile_start", {}], ["done", {
  passed: false, timed_out: true, duration: 181, error_text: "", summary: null, parsed_errors: [],
}]];

// 修复 SSE（fix-errors）：parse_done → fix_start → apply_result → done
function fixEvents(donePayload) {
  return [["parse_done", { error_count: 1, file_count: 1 }],
    ["fix_start", {}],
    ["apply_result", { file: "a.c", line: 3, reason: "ok", status: "applied" }],
    ["done", donePayload]];
}
const FIX_DONE_APPLIED = {
  parsed: [{ path: "a.c", line: 3, message: "bad" }],
  fixes: [{ file: "a.c", line: 3, status: "applied", reason: "ok" }],
  backup_id: "b1",
};
const FIX_DONE_SKIPPED = {
  parsed: [{ path: "a.c", line: 3, message: "bad" }],
  fixes: [{ file: "a.c", line: 3, status: "skipped", reason: "无上下文" }],
  backup_id: null,
};

const BASE = {
  outputDir: "/proj",
  platform: "stm32",
  problemText: "题面",
  mainC: "int main(void){}{}",
  slugs: [],
};

function collectCbs() {
  const events = [];
  return {
    events,
    cbs: {
      onState: (t) => events.push(["state", t]),
      onError: (t) => events.push(["error", t]),
      onRound: (t) => events.push(["round", t]),
      onApply: (item) => events.push(["apply", item]),
      onLog: (t) => events.push(["log", t]),
      onBanner: (k, t) => events.push(["banner", k, t]),
      onList: (parsed, fixes, round) => events.push(["list", parsed.length, fixes.length, round]),
      onTelemetry: (d) => events.push(["telemetry", d && d.calls]),
      onDone: (d) => events.push(["done", d && d.fixes ? d.fixes.length : 0]),
      onBusy: (b) => events.push(["busy", b]),
    },
  };
}

// ---------------------------------------------------------------------------
test("首编通过 0 警：banner success + 状态文案，不进修复轮", async () => {
  const restore = mockFetch({ "/api/compile": COMPILE_OK });
  const { cbs, events } = collectCbs();
  await startFixCenterCore({ ...BASE, callbacks: cbs });
  const calls = restore();
  assert.equal(calls.length, 1);
  assert.ok(events.some((e) => e[0] === "banner" && e[1] === "success"));
  assert.ok(events.some((e) => e[0] === "state" && e[1] === "编译通过 ✅ 0 错 0 警"));
  assert.equal(events.filter((e) => e[0] === "round").length, 0);
  assert.equal(isFixRunning(), false);
});

test("首编有错：进修复轮——round 文案 → fix 应用 → 重编译 → 通过终态", async () => {
  const orig = globalThis.fetch;
  const calls = [];
  // 队列化 fetch：首次 compile 错、fix、二次 compile 过
  let compileIdx = 0;
  globalThis.fetch = async (url, opts) => {
    const u = String(url);
    calls.push(u);
    if (u.includes("/api/compile")) {
      compileIdx += 1;
      if (compileIdx === 1) return sseResponse(COMPILE_ERR_ROUND1);
      return sseResponse(COMPILE_OK);
    }
    if (u.includes("/api/fix-errors")) return sseResponse(fixEvents(FIX_DONE_APPLIED));
    throw new Error("未预置：" + u);
  };
  const { cbs, events } = collectCbs();
  await startFixCenterCore({ ...BASE, callbacks: cbs });
  globalThis.fetch = orig;
  assert.equal(calls.filter((u) => u.includes("/api/compile")).length, 2);
  assert.equal(calls.filter((u) => u.includes("/api/fix-errors")).length, 1);
  // 轮次条：第 1/3 轮：编译有错 → AI 修复…；重编译验证中…；耗时
  assert.ok(events.some((e) => e[0] === "round"
    && typeof e[1] === "string" && e[1].includes("第 1/3 轮") && e[1].includes("编译有错")));
  assert.ok(events.some((e) => e[0] === "round" && e[1].includes("重编译验证中")));
  // apply 条目广播
  assert.ok(events.some((e) => e[0] === "apply" && e[1].file === "a.c" && e[1].status === "applied"));
  // done → onDone + 最终列表重建
  assert.ok(events.some((e) => e[0] === "done" && e[1] === 1));
  assert.ok(events.some((e) => e[0] === "list" && e[2] === 1));
  // 圆括号关闭：编译通过
  assert.ok(events.some((e) => e[0] === "state" && e[1] === "第 1 轮重编译通过 ✅ 0 错 0 警"));
  assert.equal(isFixRunning(), false);
  assert.deepEqual(fixLoopSnapshot(), { running: false, round: 0, batch: 1, resume: null });
});

test("0 applied（全 skipped）→ 立即停循环：状态文案 + 不再重编译", async () => {
  const restore = mockFetch({
    "/api/compile": COMPILE_ERR_ROUND1,
    "/api/fix-errors": () => sseResponse(fixEvents(FIX_DONE_SKIPPED)),
  });
  const { cbs, events } = collectCbs();
  await startFixCenterCore({ ...BASE, callbacks: cbs });
  restore();
  assert.ok(events.some((e) => e[0] === "state" && e[1].includes("未应用任何修复")));
  // 首编失败横幅（无重编译）：running（预发 + compile_start 事件）+ 终态 fail
  assert.ok(events.some((e) => e[0] === "banner" && e[1] === "fail"));
  assert.ok(!events.some((e) => e[0] === "banner" && e[1] === "success"));
  assert.equal(isFixRunning(), false);
});

test("轮上限终态：resume 快照 + 继续修复消费（不重跑初始编译）", async () => {
  // 首编错 → fix applied → 重编译仍错（第 1 轮）；然后 fix → 仍错（第 2、3 轮）
  const COMPILE_STILL_ERR = [["compile_start", {}], ["done", {
    passed: false, timed_out: false, duration: 0.6, error_text: "b.c:1: error: still",
    summary: { errors: 1, warnings: 0 }, parsed_errors: [{ path: "b.c", line: 1, message: "still" }],
  }]];
  const origFetch = globalThis.fetch;
  const calls = [];
  let fixCount = 0;
  globalThis.fetch = async (url, opts) => {
    const u = String(url);
    calls.push(u);
    if (u.includes("/api/compile")) return sseResponse(COMPILE_STILL_ERR);
    if (u.includes("/api/fix-errors")) {
      fixCount += 1;
      return sseResponse(fixEvents({ ...FIX_DONE_APPLIED, backup_id: "b" + fixCount }));
    }
    throw new Error("未预置：" + u);
  };
  const { cbs, events } = collectCbs();
  await startFixCenterCore({ ...BASE, callbacks: cbs });
  // 轮上限终态：fix 3 次（3 轮）+ 首编 + 3 次重编
  assert.equal(fixCount, 3);
  assert.ok(events.some((e) => e[0] === "state" && e[1].includes("3 轮上限")));
  // continue：用一个新回调组，验证「继续修复」不再跑初始编译（只有 fix + 重编）
  const callsBefore = calls.length;
  const cbs2 = collectCbs();
  await continueFixCenterCore({ ...BASE, callbacks: cbs2.cbs });
  globalThis.fetch = origFetch;
  const after = calls.length - callsBefore;
  // 继续批 = 3 轮 × (fix + compile)；不含初始 compile 之外的额外首编
  assert.equal(after, 6);
  assert.ok(cbs2.events.some((e) => e[0] === "round" && e[1].includes("继续批次")));
  assert.equal(isFixRunning(), false);
});

test("error 事件 → onError 文案（lastFixDone 清空）", async () => {
  const restore = mockFetch({
    "/api/compile": COMPILE_ERR_ROUND1,
    "/api/fix-errors": () => sseResponse([["parse_done", { error_count: 0, file_count: 0 }],
      ["error", { message: "LLM 调用失败" }]]),
  });
  const { cbs, events } = collectCbs();
  await startFixCenterCore({ ...BASE, callbacks: cbs });
  restore();
  assert.ok(events.some((e) => e[0] === "error" && e[1] === "修复失败（见上方提示）"));
  assert.equal(isFixRunning(), false);
});

test("单实例：running 中第二次触发被忽略（不重复请求）", async () => {
  const origFetch = globalThis.fetch;
  let fetchCount = 0;
  let gateResolve;
  const gate = new Promise((r) => { gateResolve = r; });
  globalThis.fetch = async () => {
    fetchCount += 1;
    await gate;   // 第一次调用挂起在等待中（模拟长编译）
    return sseResponse(COMPILE_OK);
  };
  const { cbs } = collectCbs();
  const p1 = startFixCenterCore({ ...BASE, callbacks: cbs });
  await new Promise((r) => setTimeout(r, 50));   // 让第一次进入 running
  await startFixCenterCore({ ...BASE, callbacks: cbs });   // 第二次：忽略
  assert.equal(fetchCount, 1);
  gateResolve();   // 放行第一次
  await p1;
  globalThis.fetch = origFetch;
  assert.equal(fetchCount, 1);
});

test("FIX_MAX_ROUNDS = 3（契约导出）", () => {
  assert.equal(FIX_MAX_ROUNDS, 3);
});

// ---------------------------------------------------------------------------
// 评审补测（Spec 轴 a3）：告警轮（0 错 N 警进轮，重编译 0 错 0 警停）与
// 降级模式（parse_done 无 file_count 的状态文案）。
// ---------------------------------------------------------------------------
test("告警轮：首编 0 错 N 警 → 进修复轮 → 重编译 0 错 0 警通过", async () => {
  const orig = globalThis.fetch;
  let compileIdx = 0;
  globalThis.fetch = async (url) => {
    const u = String(url);
    if (u.includes("/api/compile")) {
      compileIdx += 1;
      if (compileIdx === 1) return sseResponse(COMPILE_OK_WARN);
      return sseResponse(COMPILE_OK);   // 修复后 0 错 0 警
    }
    if (u.includes("/api/fix-errors")) return sseResponse(fixEvents(FIX_DONE_APPLIED));
    throw new Error("未预置：" + u);
  };
  const { cbs, events } = collectCbs();
  await startFixCenterCore({ ...BASE, callbacks: cbs });
  globalThis.fetch = orig;
  // 首编 0 错 2 警 → 进轮（「编译有警」头部）
  assert.ok(events.some((e) => e[0] === "round" && e[1].includes("编译有警")));
  assert.ok(events.some((e) => e[0] === "round" && e[1].includes("2 条 Warning")));
  // 重编译通过（0 错 0 警）：第 1 轮重编译通过
  assert.ok(events.some((e) => e[0] === "state" && e[1] === "第 1 轮重编译通过 ✅ 0 错 0 警"));
});

test("降级模式：parse_done 无 file_count → 状态文案含「降级模式」", async () => {
  const orig = globalThis.fetch;
  globalThis.fetch = async (url) => {
    const u = String(url);
    if (u.includes("/api/compile")) return sseResponse(COMPILE_ERR_ROUND1);
    if (u.includes("/api/fix-errors")) return sseResponse([
      ["parse_done", { error_count: 2, file_count: 0 }],   // 降级：未定位到源码文件
      ["fix_start", {}],
      ["done", { parsed: [], fixes: [], backup_id: null }],
    ]);
    throw new Error("未预置：" + u);
  };
  const { cbs, events } = collectCbs();
  await startFixCenterCore({ ...BASE, callbacks: cbs });
  globalThis.fetch = orig;
  assert.ok(events.some((e) => e[0] === "state" && e[1].includes("未定位到可读取的源码文件（降级模式")));
});

// ---------------------------------------------------------------------------
// 订阅制广播（工单 code-ide-ai/06 铺垫）：长驻订阅（IDE 面板/生成页壳层
// subscribe 一次）即使不作为 input.callbacks 也收到事件；同一回调组同时为
// 触发方临时订阅与长驻订阅 → Set 去重只收一次（H1 整改回归钉：触发组 cbs
// 与长驻同对象时 onState 只收 2 次——原 withCbs 包装新对象导致双发）。
// ---------------------------------------------------------------------------
test("订阅制广播：长驻订阅收到事件（双面板同步）+ 同组去重", async () => {
  const orig = globalThis.fetch;
  globalThis.fetch = async (url) => {
    const u = String(url);
    if (u.includes("/api/compile")) return sseResponse([
      ["done", { passed: true, error_text: "", summary: { errors: 0, warnings: 0 }, parsed_errors: [] }],
    ]);
    throw new Error("未预置：" + u);
  };
  const { cbs, events } = collectCbs();
  const panel = { events: [] };
  for (const k of ["onState", "onRound", "onApply", "onList", "onDone", "onReset", "onBusy", "onResume", "onCompiled", "onError", "onLog", "onBanner", "onTelemetry"]) {
    panel[k] = (...a) => panel.events.push([k, ...a]);
  }
  const unsubPanel = subscribeFixCenter(panel);
  const unsubCbs = subscribeFixCenter(cbs);   // 模拟壳层「既长驻订阅又当触发方」
  try {
    await startFixCenterCore({ ...BASE, callbacks: cbs });
    assert.ok(panel.events.some((e) => e[0] === "onState" && e[1].includes("编译通过 ✅ 0 错 0 警")),
      "长驻订阅应收到终态：" + JSON.stringify(panel.events));
    const stateCount = panel.events.filter((e) => e[0] === "onState").length;
    assert.equal(stateCount, 2, "同组只收一次（自动编译中… + 终态）实际 " + stateCount);
    // H1 回归钉：触发方自身也单发（修复前 4 次）；banner 不双发（running + success）
    const triggerState = events.filter((e) => e[0] === "state").length;
    assert.equal(triggerState, 2, "触发方同组只收一次，实际 " + triggerState);
    const triggerBanner = events.filter((e) => e[0] === "banner").length;
    assert.equal(triggerBanner, 2, "触发方 onBanner 不双发（running + success）实际 " + triggerBanner);
  } finally {
    unsubPanel();
    unsubCbs();
    globalThis.fetch = orig;
  }
});

// ---------------------------------------------------------------------------
// 评审整改（Standards 轴）：手动模式（runFixOnceCore）也占单实例——运行中
// 再触发抛错（防手动/自动并发互相清空共享态）。
// ---------------------------------------------------------------------------
test("手动模式单实例：运行中再触发抛错（防并发写盘）", async () => {
  const orig = globalThis.fetch;
  let gateResolve;
  const gate = new Promise((r) => { gateResolve = r; });
  globalThis.fetch = async (url) => {
    if (String(url).includes("/api/fix-errors")) {
      await gate;
      return sseResponse([["parse_done", { error_count: 1, file_count: 1 }],
        ["done", { parsed: [], fixes: [], backup_id: null }]]);
    }
    throw new Error("未预置：" + url);
  };
  const { cbs } = collectCbs();
  const p = runFixOnceCore({ ...BASE, callbacks: cbs }, "err");
  await new Promise((r) => setTimeout(r, 30));
  await assert.rejects(() => runFixOnceCore({ ...BASE, callbacks: cbs }, "err"),
    /修复循环进行中/);
  gateResolve();
  await p;
  globalThis.fetch = orig;
  assert.equal(isFixRunning(), false);
});
