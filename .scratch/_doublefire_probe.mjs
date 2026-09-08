// Temp: prove whether the trigger's own callback group double-fires under the
// new subscription model (fixSubs add of withCbs wrapper + long-resident sub).
import { startFixCenterCore, subscribeFixCenter } from "../src/contest_generator/static/js/ui/fix-center-core.js";

function sseResponse(events) {
  const enc = new TextEncoder();
  const stream = new ReadableStream({
    start(c) { for (const [type, payload] of events) c.enqueue(enc.encode("event: " + type + "\n" + "data: " + JSON.stringify(payload) + "\n\n")); c.close(); },
  });
  return new Response(stream, { status: 200, headers: { "Content-Type": "text/event-stream" } });
}
function mockFetch(routes) {
  const orig = globalThis.fetch;
  globalThis.fetch = async (url, opts) => {
    const u = String(url);
    const r = routes[u];
    if (typeof r === "function") return r(u, opts);
    if (r) return sseResponse(r);
    throw new Error("未预置路由：" + u);
  };
  return () => { globalThis.fetch = orig; };
}

const COMPILE_ERR = [["compile_start", {}], ["done", { passed: false, timed_out: false, duration: 0.5, error_text: "a.c:3: error: bad", summary: { errors: 1, warnings: 0 }, parsed_errors: [{ path: "a.c", line: 3, message: "bad" }] }]];
const COMPILE_OK = [["compile_start", {}], ["done", { passed: true, timed_out: false, duration: 0.5, error_text: "", summary: { errors: 0, warnings: 0 }, parsed_errors: [] }]];
const FIX_DONE = { parsed: [{ path: "a.c", line: 3, message: "bad" }], fixes: [{ file: "a.c", line: 3, status: "applied", reason: "ok" }], backup_id: "b1" };
const FIX = [["parse_done", { error_count: 1, file_count: 1 }], ["fix_start", {}], ["apply_result", { file: "a.c", line: 3, reason: "ok", status: "applied" }], ["done", FIX_DONE]];

const BASE = { outputDir: "/proj", platform: "stm32", problemText: "题面", mainC: "m", slugs: [] };
let compileCount = 0;
const restore = mockFetch({
  "/api/compile": () => (compileCount++ === 0 ? sseResponse(COMPILE_ERR) : sseResponse(COMPILE_OK)),
  "/api/fix-errors": FIX,
});

// One callback group, both long-resident-subscribed AND passed as input.callbacks
// (this is exactly generate-fix.js's fixInput(): callbacks === fixCb).
let stateHits = 0, applyHits = 0, listHits = 0, doneHits = 0, busyOn = 0;
const cb = {
  onState: (t) => { stateHits++; },
  onApply: (item) => { applyHits++; },
  onList: (p, f, r) => { listHits++; },
  onDone: (d, o) => { doneHits++; },
  onBusy: (b) => { if (b) busyOn++; },
};
subscribeFixCenter(cb);   // 长驻订阅（与真实 generate-fix.js / code-fix-panel.js 相同）

await startFixCenterCore({ ...BASE, callbacks: cb });   // 触发方临时订阅（同 cb 对象）

console.log("Trigger group (== long-resident group) invocation counts over one cycle:");
console.log("  onState hits:", stateHits, "(expect 2 logical: 自动编译中… + 编译通过)");
console.log("  onApply hits:", applyHits, "(expect 1 logical: 1 apply_result)");
console.log("  onList hits:", listHits, "(expect 2 logical: 首编列表 + 最终列表)");
console.log("  onDone hits:", doneHits, "(expect 1 logical)");
console.log("  onBusy(true) hits:", busyOn, "(expect 1 logical)");
restore();
