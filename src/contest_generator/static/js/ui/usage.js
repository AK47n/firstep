// ui/usage.js — LLM 用量记录服务（阶段 2 工单 04 前置拆分）
//
// llm_telemetry 快照 → 会话差分 → 跨会话累计持久化 + 费用估算（设置页单价
// 优先，空则官方默认价）的跨簇共享胶水：recordLLMUsage 被推荐 / 修复 / 修订 /
// 提炼四个 SSE 流调用（先于各自 tab 迁出，故本模块在工单 04 独立成文）。
// 纯计算（usageDelta / usageAccumulate / llmCostEstimate / usageDisplay）在
// fx/llm.js；本模块只做状态持有与 DOM 显示。
// 单价表 llmPricesDefaults 本模块持有：设置页 loadSettings（设置簇）经
// setLlmPricesDefaults 写入；collectLlmPrices（设置簇）经 import 只读
// （ESM 活绑定，只读合法）。
import { $ } from "/js/app.js";
import { usageDelta, usageAccumulate, llmCostEstimate, usageDisplay } from "/js/fx/llm.js";

const USAGE_STORE_KEY = "firstep.usage.v1";
let usageBase = null;
let usageSessionAcc = { calls: 0, prompt: 0, completion: 0, cacheHit: 0, durationMs: 0, requestBytes: 0 };
export let llmPricesDefaults = {};       // 当前生效 LLM 单价表（工单 llm-cost-control/01）
export function setLlmPricesDefaults(v) { llmPricesDefaults = v; }

function loadUsageAcc() {
  try {
    const raw = localStorage.getItem(USAGE_STORE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (parsed && typeof parsed === "object") return parsed;
    }
  } catch (e) { /* 忽略 */ }
  return { calls: 0, prompt: 0, completion: 0, cacheHit: 0, durationMs: 0, requestBytes: 0 };
}

function currentLlmPrices() {
  const defs = llmPricesDefaults.deepseek || {};
  const hit = $("set-ds-in-hit").value.trim();
  const miss = $("set-ds-in").value.trim();
  const out = $("set-ds-out").value.trim();
  return {
    input_cache_hit_per_million: hit ? parseFloat(hit) : (defs.input_cache_hit_per_million || 0),
    input_cache_miss_per_million: miss ? parseFloat(miss) : (defs.input_cache_miss_per_million || 0),
    output_per_million: out ? parseFloat(out) : (defs.output_per_million || 0),
  };
}

export function recordLLMUsage(snapshot) {
  const delta = usageDelta(snapshot, usageBase);
  usageBase = usageDelta(snapshot, null);   // 新基线 = 当前快照（重复快照差分 0）
  if (!delta.calls && !delta.prompt && !delta.completion) return;
  usageSessionAcc = usageAccumulate(usageSessionAcc, delta);
  const acc = usageAccumulate(loadUsageAcc(), delta);
  try { localStorage.setItem(USAGE_STORE_KEY, JSON.stringify(acc)); } catch (e) { /* 忽略 */ }
  renderUsageStats();
}

export function renderUsageStats() {
  if (!$("usage-total")) return;
  const prices = currentLlmPrices();
  const acc = loadUsageAcc();
  const fmt = (d) => d.calls + " 次调用 · " + d.prompt.toLocaleString("en-US") + " prompt · "
    + d.completion.toLocaleString("en-US") + " completion"
    + (d.cacheHit ? "（缓存 " + d.cacheHit.toLocaleString("en-US") + "）" : "")
    + " · 耗时 " + d.durationMs.toLocaleString("en-US") + "ms"
    + " · 请求 " + d.requestBytes.toLocaleString("en-US") + "B"
    + " · 估算 " + d.costText;
  $("usage-session").textContent = fmt(usageDisplay(usageSessionAcc, llmCostEstimate(usageSessionAcc, prices)));
  $("usage-total").textContent = fmt(usageDisplay(acc, llmCostEstimate(acc, prices)));
}

$("btn-usage-reset").addEventListener("click", () => {
  try { localStorage.removeItem(USAGE_STORE_KEY); } catch (e) { /* 忽略 */ }
  usageSessionAcc = { calls: 0, prompt: 0, completion: 0, cacheHit: 0, durationMs: 0, requestBytes: 0 };
  renderUsageStats();
  $("usage-reset-msg").textContent = "已重置";
  setTimeout(() => { $("usage-reset-msg").textContent = ""; }, 1500);
});
