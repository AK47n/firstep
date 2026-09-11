// fx/llm.js — LLM 用量与遥测纯函数（工单 frontend-es-modules/09，迁自
// index.html LLM 域纯函数组：telemetry 格式化 / SSE 流解析 / 用量差分累计 /
// 费用估算 / 展示格式化）。域内常量无（USAGE_STORE_KEY 等由胶水层使用，
// 留内联）；无共享件依赖。模块约定见 fx/core.js 头部。
export function formatLLMTelemetry(data) {
  const toNumber = (v) => Number.isFinite(Number(v)) ? Number(v) : 0;
  // 中文标签表（operation / 解析状态 / 错误类型 / usage 键；未知回退原文）
  const opLabels = {
    select_modules: "选模块", clarify: "澄清提问", preread_topic: "赛题预读",
    summarize_module: "模块简介", reference_summarize: "参考资料摘要",
    validate_module_description: "简介校验", reference_judge_archivable: "归档判定",
    generate_main_skeleton: "生成骨架", generate_smoke_main: "自检冒烟",
    fix_compile_errors: "编译修复", distill_master: "母版提炼",
    topic_split_topics: "拆条", topic_extract_number: "编号识别",
    vision_describe: "视觉识别",
  };
  const parseLabels = { success: "成功", parse_error: "解析失败", not_sent: "未发送" };
  // 错误类别标签（与 llm.ERROR_KIND_* 常量同词表，工单 real-acceptance/03 补
  // domain=域拒绝——本地域判决与上游 4xx 是两回事；real-acceptance/09 补
  // output=输出不可用——HTTP 200 拿到但输出不能用，同样不是上游拒绝；未知类别
  // 回退原文）
  const errLabels = { network: "网络", rate_limit: "限流", client: "客户端", domain: "域拒绝", output: "输出不可用", server: "服务端" };
  const usageLabels = { prompt_tokens: "prompt", completion_tokens: "completion", total_tokens: "total" };
  const op = data.llm_latest_operation || "";
  const parts = [
    "LLM：" + toNumber(data.llm_total_calls) + " 次调用",
    "本地 " + toNumber(data.llm_local_calls) + " / DeepSeek " + toNumber(data.llm_deepseek_calls),
  ];
  if (op) parts.push("最新 " + (opLabels[op] || op));
  if (data.llm_error_kind) {
    parts.push("错误 " + (errLabels[data.llm_error_kind] || data.llm_error_kind)
      + " / 解析 " + (parseLabels[data.llm_parse_status] || data.llm_parse_status || ""));
  } else if (data.llm_parse_status) {
    parts.push("解析 " + (parseLabels[data.llm_parse_status] || data.llm_parse_status));
  }
  if (data.llm_latest_http_status) parts.push("HTTP " + toNumber(data.llm_latest_http_status));
  const counters = [];
  if (data.llm_attempts) counters.push("尝试 " + toNumber(data.llm_attempts));
  if (data.llm_retry_calls) counters.push("重试 " + toNumber(data.llm_retry_calls));
  if (data.llm_error_calls) counters.push("错误 " + toNumber(data.llm_error_calls));
  if (data.llm_parse_error_calls) counters.push("解析错误 " + toNumber(data.llm_parse_error_calls));
  if (data.llm_rate_limit_calls) counters.push("限流 " + toNumber(data.llm_rate_limit_calls));
  if (data.llm_network_error_calls) counters.push("网络错误 " + toNumber(data.llm_network_error_calls));
  if (data.llm_5xx_calls) counters.push("5xx " + toNumber(data.llm_5xx_calls));
  if (data.llm_budget_blocked_calls) counters.push("预算拦截 " + toNumber(data.llm_budget_blocked_calls));
  if (counters.length) parts.push(counters.join(", "));
  parts.push("请求 " + toNumber(data.llm_request_bytes).toLocaleString("en-US") + "B");
  parts.push("耗时 " + toNumber(data.llm_duration_ms).toLocaleString("en-US") + "ms");
  const usage = data.llm_usage || null;
  if (usage && typeof usage === "object") {
    const usageText = Object.keys(usage)
      .map((k) => (usageLabels[k] || k) + "=" + usage[k]).join(", ");
    if (usageText) parts.push("用量 " + usageText);
  }
  return parts.join(" · ");
}

// ===== SSE 解析器（工单 03；纯函数：输入 Response → 逐事件回调，不碰 DOM）=====
// 工单 02 契约：HTTP 200、text/event-stream；每个事件 = "event: <type>\n" +
// "data: <JSON>\n" + "\n"（空行分隔）；断线 = 放弃本次（无自动重连）。
// 本地手测：浏览器 devtools 用 new Response(new ReadableStream(...)) 构造假流喂它。
export async function parseSSE(resp, onEvent) {
  if (!resp.body) throw new Error("服务响应无流");
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let type = "";
  let data = "";
  const feed = (block) => {
    for (const line of block.split("\n")) {
      if (!line) continue;
      if (line.startsWith("event:")) type = line.slice(6).trim();
      else if (line.startsWith("data:")) data += line.slice(5).replace(/^ /, "") + "\n";
      // 其他行（id / 注释等）本次契约不用，忽略
    }
  };
  const flush = () => {
    if (type || data) {
      onEvent(type || "message", data.replace(/\n$/, ""));
      type = "";
      data = "";
    }
  };
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n").replace(/\r/g, "\n");
    let idx;
    while ((idx = buffer.indexOf("\n\n")) !== -1) {
      feed(buffer.slice(0, idx));
      buffer = buffer.slice(idx + 2);
      flush();
    }
  }
  buffer += decoder.decode();
  if (buffer) { feed(buffer); flush(); }   // 流末尾缺最后一个空行也认
}

// ---------------------------------------------------------------------------
// LLM 用量统计（工单 ui-polish-5/02）：llm_telemetry 累计快照 → 会话差分 →
// 跨会话累计持久化 + 费用估算（设置页单价优先，空则官方默认价）
// （USAGE_STORE_KEY / usageBase / usageSessionAcc 等状态与持久化胶水留内联）
// ---------------------------------------------------------------------------
export function usageDelta(snapshot, base) {
  const num = (v) => Number.isFinite(Number(v)) ? Number(v) : 0;
  const usage = snapshot.llm_usage && typeof snapshot.llm_usage === "object" ? snapshot.llm_usage : {};
  const s = {
    calls: num(snapshot.llm_total_calls),
    prompt: num(usage.prompt_tokens),
    completion: num(usage.completion_tokens),
    cacheHit: num(usage.prompt_cache_hit_tokens),
    durationMs: num(snapshot.llm_duration_ms),
    requestBytes: num(snapshot.llm_request_bytes),
  };
  if (!base) return s;   // 首快照 = 从零到当前的增量
  const d = {};
  for (const k of Object.keys(s)) d[k] = Math.max(0, s[k] - (base[k] || 0));
  return d;
}

export function usageAccumulate(acc, delta) {
  const out = Object.assign({}, acc || {});
  for (const k of ["calls", "prompt", "completion", "cacheHit", "durationMs", "requestBytes"]) {
    out[k] = (out[k] || 0) + (delta[k] || 0);
  }
  return out;
}

export function llmCostEstimate(usage, prices) {
  const p = prices || {};
  const prompt = Number(usage.prompt) || 0;
  const cacheHit = Number(usage.cacheHit) || 0;
  const miss = Math.max(0, prompt - cacheHit);
  return {
    hitCost: (cacheHit / 1e6) * (Number(p.input_cache_hit_per_million) || 0),
    missCost: (miss / 1e6) * (Number(p.input_cache_miss_per_million) || 0),
    outCost: ((Number(usage.completion) || 0) / 1e6) * (Number(p.output_per_million) || 0),
  };
}

export function usageDisplay(acc, cost) {
  const a = acc || {};
  const c = cost || { hitCost: 0, missCost: 0, outCost: 0 };
  const total = c.hitCost + c.missCost + c.outCost;
  return {
    calls: a.calls || 0,
    prompt: a.prompt || 0,
    completion: a.completion || 0,
    cacheHit: a.cacheHit || 0,
    durationMs: a.durationMs || 0,
    requestBytes: a.requestBytes || 0,
    cost: total,
    costText: total > 0 ? "¥" + total.toFixed(4) : "—",
  };
}

if (typeof window !== "undefined") {
  Object.assign(window, { formatLLMTelemetry, parseSSE, usageDelta, usageAccumulate, llmCostEstimate, usageDisplay });
}
