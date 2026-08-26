// fx/workflow.js — 最近 LLM 工作流仪表盘纯函数（阶段 2 工单 01，迁自
// index.html「最近 LLM 工作流」域纯函数组：wfNum / usage/cost/summary/call
// 四段格式化）。阶段 1 规划漏项：该组原经 recent-workflows-format.test.mjs
// 正则抽取（非贪婪 \n\} 脆变体）复用，本次随迁为直接 import。域内常量无；
// 无共享件依赖。模块约定见 fx/core.js 头部。
export function wfNum(value) {
  return Number.isFinite(Number(value)) ? Number(value).toLocaleString("en-US") : "0";
}

export function formatWorkflowUsage(usage) {
  if (!usage || typeof usage !== "object") return "";
  const text = Object.keys(usage)
    .map((k) => k + "=" + usage[k])
    .join(", ");
  return text ? "usage(服务商上报) " + text : "";
}

export function formatWorkflowCost(est) {
  // 费用段（工单 llm-cost-control/01）：估算参考值；actual / 对照全 DeepSeek
  // 都为零（无 usage）不显示；节省 > 0.005 元才显示「省」段
  if (!est || typeof est !== "object") return "";
  const fmt = (v) => "¥" + Number(v || 0).toFixed(2);
  const actual = Number(est.est_cost_actual || 0);
  const counter = Number(est.est_cost_deepseek || 0);
  if (actual <= 0 && counter <= 0) return "";
  let text = "cost " + fmt(actual) + "（全 DeepSeek " + fmt(counter) + "）";
  const savings = Number(est.est_savings || 0);
  if (savings > 0.005) text = text.slice(0, -1) + "，省 " + fmt(savings) + "）";
  return text;
}

export function formatWorkflowSummary(w) {
  const parts = [
    (w.workflow_name || "unknown") + (w.status === "error" ? " ✗" : " ✓"),
    wfNum(w.call_count) + " calls",
    "local " + wfNum(w.local_calls) + " / DeepSeek " + wfNum(w.deepseek_calls),
    "request " + wfNum(w.request_bytes) + "B",
    "duration " + wfNum(w.duration_ms) + "ms",
  ];
  const usageText = formatWorkflowUsage(w.usage);
  if (usageText) parts.push(usageText);
  const costText = formatWorkflowCost(w.est);
  if (costText) parts.push(costText);
  return parts.join(" · ");
}

export function formatWorkflowCall(call) {
  const parts = [
    "#" + call.sequence,
    call.operation || "unknown",
    call.provider || "?",
    call.status || "?",
  ];
  if (call.error_kind) parts.push("error " + call.error_kind);
  if (call.parse_status && call.parse_status !== "success") parts.push("parse " + call.parse_status);
  if (call.http_status) parts.push("http " + call.http_status);
  if (call.attempts > 1) parts.push("attempts " + call.attempts);
  if (call.budget_attempt) parts.push("budget_attempt " + call.budget_attempt);
  parts.push("request " + wfNum(call.request_bytes) + "B");
  parts.push("duration " + wfNum(call.duration_ms) + "ms");
  const usageText = formatWorkflowUsage(call.usage);
  if (usageText) parts.push(usageText);
  return parts.join(" · ");
}

if (typeof window !== "undefined") {
  Object.assign(window, { wfNum, formatWorkflowUsage, formatWorkflowCost, formatWorkflowSummary, formatWorkflowCall });
}
