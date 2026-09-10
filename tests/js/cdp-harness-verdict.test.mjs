// cdp-harness.mjs 自助复判纯函数单测（工单 batch-runner-self-heal/01）：
// 判定口径（什么算绿 / 偶发 / 真红 / 挂死）、复跑决策、事件序列归拢、落盘命名与文本呈现。
// 全部是纯函数，不需要 Chrome：运行 `node --test tests/js/*.test.mjs`。
import test from "node:test";
import assert from "node:assert/strict";
import {
  classifyAttempt,
  runVerdict,
  retryDecision,
  digestEvents,
  diagFileName,
  renderDiagText,
  TRANSPORT_SIGNAL_RE,
} from "../../.scratch/cdp-harness.mjs";

test("classifyAttempt：exit=0 且无信号 = 绿", () => {
  const a = classifyAttempt({ exit: 0, out: "21 PASS / 0 FAIL | ALL PASS" });
  assert.equal(a.pass, true);
  assert.equal(a.hung, false);
  assert.deepEqual(a.reasons, []);
});

test("classifyAttempt：exit=1 有 FAIL 行 = 断言红（不是挂死）", () => {
  const a = classifyAttempt({ exit: 1, out: "18 PASS / 3 FAIL\n FAIL foo" });
  assert.equal(a.pass, false);
  assert.equal(a.hung, false);
  assert.ok(a.reasons.some((r) => r.includes("退出码 1")));
  assert.ok(!a.reasons.some((r) => r.includes("挂死")));
});

test("classifyAttempt：exit=2 + TRANSPORT 但页面仍可应答 = 传输层红，不判挂死", () => {
  const a = classifyAttempt({ exit: 2, out: "TRANSPORT(uncaughtException): CDP 无响应（20000ms）: Runtime.evaluate", pageUnresponsive: false });
  assert.equal(a.pass, false);
  assert.equal(a.hung, false, "页面能应答就不算挂死");
  assert.ok(a.reasons.some((r) => r.includes("传输层/挂死信号") && r.includes("未定性为挂死")));
});

test("classifyAttempt：传输层信号 + 页面确无响应 = 挂死；或脚本超时被杀 = 挂死", () => {
  const hung = classifyAttempt({ exit: null, out: "页面可能已挂死", pageUnresponsive: true });
  assert.equal(hung.hung, true);
  assert.equal(hung.pass, false);
  const killed = classifyAttempt({ exit: null, timedOut: true, out: "" });
  assert.equal(killed.hung, true);
  assert.ok(killed.reasons.includes("脚本超时被杀"));
});

test("classifyAttempt：exit=0 不足以判绿——带挂死信号仍算红（第十一轮 exit=1 无 FAIL 行的同族形态）", () => {
  const a = classifyAttempt({ exit: 0, out: "CDP 不可达（端口 9251）", pageUnresponsive: true });
  assert.equal(a.pass, false);
  assert.equal(a.hung, true);
});

test("TRANSPORT_SIGNAL_RE：认出脚本与批跑器的全部既有措辞", () => {
  for (const s of ["TRANSPORT(", "CDP 无响应（20000ms）", "页面可能已挂死", "页面未就绪", "CDP 不可达"]) {
    assert.ok(TRANSPORT_SIGNAL_RE.test(s), s);
  }
  assert.ok(!TRANSPORT_SIGNAL_RE.test("21 PASS / 0 FAIL"));
});

test("runVerdict：两次都绿 = pass；首红复绿 = flake（不算失败）；两次都红 = fail", () => {
  const ok = classifyAttempt({ exit: 0, out: "ALL PASS" });
  const bad = classifyAttempt({ exit: 1, out: "1 FAIL" });

  const pass = runVerdict(ok, ok);
  assert.equal(pass.verdict, "pass");
  assert.equal(pass.flake, false);
  assert.equal(pass.retried, true);

  const flake = runVerdict(bad, ok);
  assert.equal(flake.verdict, "flake");
  assert.equal(flake.flake, true);
  assert.equal(flake.attempts.length, 2, "两次记录都留痕");

  const fail = runVerdict(bad, bad);
  assert.equal(fail.verdict, "fail");
  assert.equal(fail.flake, false);

  const single = runVerdict(ok, null);
  assert.equal(single.verdict, "pass");
  assert.equal(single.retried, false);
  const singleRed = runVerdict(bad, null);
  assert.equal(singleRed.verdict, "fail");
});

test("runVerdict：挂死优先于 fail/flake 报告（任一次挂死即 hang）", () => {
  const ok = classifyAttempt({ exit: 0, out: "ALL PASS" });
  const bad = classifyAttempt({ exit: 1, out: "1 FAIL" });
  const hung = classifyAttempt({ exit: null, timedOut: true, out: "" });

  assert.equal(runVerdict(hung, ok).verdict, "hang");
  assert.equal(runVerdict(bad, hung).verdict, "hang");
  assert.deepEqual(runVerdict(hung, hung).attempts.length, 2);
});

test("retryDecision：只有非绿才复跑，且最多一次；--retry=0 永不复跑", () => {
  const ok = classifyAttempt({ exit: 0, out: "ALL PASS" });
  const bad = classifyAttempt({ exit: 1, out: "1 FAIL" });
  const hung = classifyAttempt({ exit: null, timedOut: true, out: "" });

  assert.equal(retryDecision(ok, { retry: 1 }).retry, false);
  assert.ok(retryDecision(ok, { retry: 1 }).reason.includes("首跑已绿"));

  assert.equal(retryDecision(bad, { retry: 1, attemptIndex: 1 }).retry, true);
  assert.ok(retryDecision(bad, { retry: 1, attemptIndex: 1 }).reason.includes("复跑一次定性"));
  assert.equal(retryDecision(hung, { retry: 1, attemptIndex: 1 }).retry, true);
  assert.ok(retryDecision(hung, { retry: 1, attemptIndex: 1 }).reason.includes("首跑挂死"));

  assert.equal(retryDecision(bad, { retry: 0, attemptIndex: 1 }).retry, false);
  assert.ok(retryDecision(bad, { retry: 0, attemptIndex: 1 }).reason.includes("--retry=0"));
  assert.equal(retryDecision(bad, { retry: 1, attemptIndex: 2 }).retry, false, "复跑后不再复跑");
  assert.ok(retryDecision(bad, { retry: 1, attemptIndex: 2 }).reason.includes("用尽"));
});

// 一段真实取材的事件序列（第十二轮 smoke-01 输出里的那段 + 一个异常与对话框）
const EVENTS = [
  { t: 1000, method: "Runtime.executionContextCreated", params: {} },
  { t: 1010, method: "Page.frameStartedNavigating", params: {} },
  { t: 1020, method: "Runtime.executionContextsCleared", params: {} },
  { t: 1100, method: "Page.javascriptDialogOpening", params: { type: "beforeunload" } },
  { t: 1102, method: "Page.javascriptDialogClosed", params: {} },
  { t: 1120, method: "Runtime.exceptionThrown", params: { exceptionDetails: { exception: { description: "TypeError: x is not a function\n    at foo (app.js:1:1)" } } } },
  { t: 1200, method: "Page.frameNavigated", params: {} },
  { t: 1210, method: "Page.loadEventFired", params: {} },
  { t: 1220, method: "Log.entryAdded", params: { entry: { text: "console 警告" } } },
  { t: 1240, method: "Network.requestWillBeSent", params: {} },
  { t: 1250, method: "SomeFuture.domainEvent", params: {} },
];

test("digestEvents：关键事件逐条留（带相对时刻）、噪声折叠计数、未知事件点名", () => {
  const d = digestEvents(EVENTS, { t0Ms: 1000 });
  assert.equal(d.total, EVENTS.length);

  const methods = d.kept.map((k) => k.method);
  assert.deepEqual(methods, [
    "Page.frameStartedNavigating", "Page.javascriptDialogOpening", "Page.javascriptDialogClosed",
    "Runtime.exceptionThrown", "Page.frameNavigated", "Page.loadEventFired", "Log.entryAdded",
  ]);
  assert.equal(d.kept[0].dtMs, 10);
  assert.equal(d.kept.find((k) => k.method === "Page.javascriptDialogOpening").dialogType, "beforeunload");
  const ex = d.kept.find((k) => k.method === "Runtime.exceptionThrown");
  assert.ok(ex.text.includes("TypeError: x is not a function"));
  assert.ok(!ex.text.includes("\n"), "异常文本压成一行");

  assert.deepEqual(d.folded, ["上下文噪声 ×2", "网络噪声 ×1"]);
  assert.deepEqual(d.unknown, ["SomeFuture.domainEvent ×1"]);
  assert.ok(d.summary.includes("Page.javascriptDialogOpening"));
  assert.ok(d.summary.includes("+100ms"));
});

test("digestEvents：空序列不炸（脚本没连 CDP 或挂在传输层）", () => {
  const d = digestEvents([], { t0Ms: 0 });
  assert.equal(d.total, 0);
  assert.deepEqual(d.kept, []);
  assert.equal(d.summary, "（无关键事件）");
});

test("diagFileName：脚本短名可 locate，去掉 .scratch/ 与 .mjs，非法字符归一", () => {
  const n = diagFileName(".scratch/code-editor-refine/smoke-01.mjs", 2, { stamp: 1789000000000 });
  assert.equal(n, "1789000000000-r2-code-editor-refine-smoke-01.json");
  const weird = diagFileName(".scratch/a b/c+d.mjs", 1, { stamp: 1, ext: "txt" });
  assert.equal(weird, "1-r1-a-b-c-d.txt");
  assert.equal(diagFileName("", 1, { stamp: 1 }).startsWith("1-r1-script"), true, "空名兜底");
});

test("renderDiagText：非绿现场文本含支次、判定、关键事件与折叠计数", () => {
  const digest = digestEvents(EVENTS, { t0Ms: 1000 });
  const txt = renderDiagText({
    script: "code-editor-refine/smoke-01.mjs", round: 2, attempt: 1, ts: 1789000000000, digest,
    attemptRecord: { verdict: "fail", exit: 1, timedOut: false, hung: false, reasons: ["退出码 1"], tail: "18 PASS / 3 FAIL" },
  });
  assert.ok(txt.includes("code-editor-refine/smoke-01.mjs"));
  assert.ok(txt.includes("轮次 r2"));
  assert.ok(txt.includes("attempt=1"));
  assert.ok(txt.includes("verdict=fail"));
  assert.ok(txt.includes("Runtime.exceptionThrown"));
  assert.ok(txt.includes("折叠计数：上下文噪声 ×2 / 网络噪声 ×1"));
  assert.ok(txt.includes("一行摘要："));
  assert.ok(txt.endsWith("\n"));
});
