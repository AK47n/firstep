// LLM 用量统计纯函数单测（工单 frontend-es-modules/09）：
// usageDelta（telemetry 快照差分）/ llmCostEstimate（费用分档估算）/
// usageAccumulate（累计合并）/ usageDisplay（统计展示格式化）。
// 直接 import fx/llm.js（不再字符串提取）。
import test from "node:test";
import assert from "node:assert/strict";
import {
  usageDelta, usageAccumulate, llmCostEstimate, usageDisplay,
} from "../../src/contest_generator/static/js/fx/llm.js";

const SNAP = {
  llm_total_calls: 3,
  llm_usage: {
    prompt_tokens: 1200,
    completion_tokens: 400,
    prompt_cache_hit_tokens: 200,
  },
  llm_duration_ms: 5432,
  llm_request_bytes: 88000,
};

test("usageDelta：首快照（base 为空）返回快照全量", () => {
  const d = usageDelta(SNAP, null);
  assert.equal(d.calls, 3);
  assert.equal(d.prompt, 1200);
  assert.equal(d.completion, 400);
  assert.equal(d.cacheHit, 200);
  assert.equal(d.durationMs, 5432);
  assert.equal(d.requestBytes, 88000);
});

test("usageDelta：相同快照重复到达 → 差分全 0（防重复累计）", () => {
  const base = usageDelta(SNAP, null);   // recordLLMUsage 存的就是规范化结构
  const d = usageDelta(SNAP, base);
  assert.deepEqual(d, { calls: 0, prompt: 0, completion: 0, cacheHit: 0, durationMs: 0, requestBytes: 0 });
});

test("usageDelta：增量快照 → 只计增量；字段缺失兜 0", () => {
  const next = {
    llm_total_calls: 7,
    llm_usage: { prompt_tokens: 3200, completion_tokens: 900, prompt_cache_hit_tokens: 500 },
    llm_duration_ms: 8123,
    llm_request_bytes: 150000,
  };
  const d = usageDelta(next, usageDelta(SNAP, null));
  assert.deepEqual(d, { calls: 4, prompt: 2000, completion: 500, cacheHit: 300, durationMs: 2691, requestBytes: 62000 });
  const bare = usageDelta({ llm_total_calls: 1 }, null);
  assert.equal(bare.prompt, 0);
  assert.equal(bare.cacheHit, 0);
});

test("usageDelta：llm_usage 缺失 / 非对象 → 不抛错且 token 为 0", () => {
  assert.equal(usageDelta({ llm_total_calls: 1 }, null).prompt, 0);
  assert.equal(usageDelta({ llm_total_calls: 1, llm_usage: "x" }, null).completion, 0);
});

test("llmCostEstimate：命中/未命中分档 + 输出计费", () => {
  const prices = {
    input_cache_hit_per_million: 1,   // ¥1 / 百万
    input_cache_miss_per_million: 2,
    output_per_million: 8,
  };
  // 1200 prompt 中 200 命中 → 1000 未命中；400 completion
  const c = llmCostEstimate({ prompt: 1200, completion: 400, cacheHit: 200 }, prices);
  assert.equal(c.hitCost, 200 / 1e6 * 1);
  assert.equal(c.missCost, 1000 / 1e6 * 2);
  assert.equal(c.outCost, 400 / 1e6 * 8);
});

test("llmCostEstimate：cacheHit 缺失 → 全部按未命中；价格全空 → 0（未配置）", () => {
  const c = llmCostEstimate({ prompt: 100, completion: 50 }, { input_cache_hit_per_million: 1, input_cache_miss_per_million: 2, output_per_million: 8 });
  assert.equal(c.hitCost, 0);
  assert.equal(c.missCost, 100 / 1e6 * 2);
  assert.equal(llmCostEstimate({ prompt: 1, completion: 1 }, {}).outCost, 0);
  assert.equal(llmCostEstimate({ prompt: 1, completion: 1 }, null).missCost, 0);
});

test("usageAccumulate：空累计 + 空 delta 都不炸；数字累加", () => {
  const a = usageAccumulate(null, { calls: 1, prompt: 10, completion: 2, cacheHit: 1, durationMs: 100, requestBytes: 5 });
  assert.deepEqual(a, { calls: 1, prompt: 10, completion: 2, cacheHit: 1, durationMs: 100, requestBytes: 5 });
  const b = usageAccumulate(a, { calls: 2, prompt: 5, completion: 0, cacheHit: 3, durationMs: 50, requestBytes: 2 });
  assert.deepEqual(b, { calls: 3, prompt: 15, completion: 2, cacheHit: 4, durationMs: 150, requestBytes: 7 });
  // 原对象不被修改
  assert.equal(a.calls, 1);
  // delta 缺字段 → 该字段保持
  assert.deepEqual(usageAccumulate(a, { calls: 1 }), { calls: 2, prompt: 10, completion: 2, cacheHit: 1, durationMs: 100, requestBytes: 5 });
});

test("usageDisplay：有费用 → ¥ 四位小数；无费用 → 破折号；字段兜 0", () => {
  const d = usageDisplay(
    { calls: 3, prompt: 1200, completion: 400, cacheHit: 200, durationMs: 5432, requestBytes: 88000 },
    { hitCost: 0.0002, missCost: 0.002, outCost: 0.0032 }
  );
  assert.equal(d.calls, 3);
  assert.equal(d.cost, 0.0054);
  assert.equal(d.costText, "¥0.0054");
  assert.equal(usageDisplay(null, null).costText, "—");
  assert.equal(usageDisplay({}, {}).prompt, 0);
});
