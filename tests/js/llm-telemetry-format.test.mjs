// LLM telemetry 状态行格式化测试（工单 frontend-es-modules/09）：
// 直接 import fx/llm.js，锁定第 10 栏紧凑展示文案，不碰 DOM / fetch。
// 运行：node --test tests/js/
import test from "node:test";
import assert from "node:assert/strict";
import { formatLLMTelemetry } from "../../src/contest_generator/static/js/fx/llm.js";

test("LLM telemetry 行显示调用数 / provider 分流 / 最新操作 / 错误 / 字节 / 耗时 / 用量（中文）", () => {
  assert.equal(
    formatLLMTelemetry({
      llm_total_calls: 3,
      llm_local_calls: 1,
      llm_deepseek_calls: 2,
      llm_latest_operation: "fix_compile_errors",
      llm_error_kind: "network",
      llm_parse_status: "parse_error",
      llm_latest_http_status: 502,
      llm_attempts: 4,
      llm_retry_calls: 2,
      llm_error_calls: 2,
      llm_parse_error_calls: 1,
      llm_rate_limit_calls: 1,
      llm_network_error_calls: 1,
      llm_5xx_calls: 1,
      llm_budget_blocked_calls: 0,
      llm_request_bytes: 12345,
      llm_duration_ms: 678,
      llm_usage: { prompt_tokens: 10, completion_tokens: 2, total_tokens: 12 },
    }),
    "LLM：3 次调用 · 本地 1 / DeepSeek 2 · 最新 编译修复 · 错误 网络 / 解析 解析失败 · HTTP 502 · 尝试 4, 重试 2, 错误 2, 解析错误 1, 限流 1, 网络错误 1, 5xx 1 · 请求 12,345B · 耗时 678ms · 用量 prompt=10, completion=2, total=12"
  );
});

test("无 usage / 无错误时省略对应段；未知 operation 回退原文", () => {
  assert.equal(
    formatLLMTelemetry({
      llm_total_calls: 1,
      llm_local_calls: 0,
      llm_deepseek_calls: 1,
      llm_latest_operation: "select_modules",
      llm_parse_status: "success",
      llm_request_bytes: 90,
      llm_duration_ms: 12,
    }),
    "LLM：1 次调用 · 本地 0 / DeepSeek 1 · 最新 选模块 · 解析 成功 · 请求 90B · 耗时 12ms"
  );
  assert.equal(
    formatLLMTelemetry({
      llm_total_calls: 1,
      llm_local_calls: 1,
      llm_deepseek_calls: 0,
      llm_latest_operation: "future_op_unknown",
    }),
    "LLM：1 次调用 · 本地 1 / DeepSeek 0 · 最新 future_op_unknown · 请求 0B · 耗时 0ms"
  );
});

test("域拒绝（domain）有中文标签——不再在设置页显示原始英文 kind", () => {
  // 工单 real-acceptance/03：错误类别词表新增 domain（本地域判决，与上游 4xx
  // 的 client 区分）；词表缺项时前端会回退显示原文「错误 domain」。
  assert.match(
    formatLLMTelemetry({
      llm_total_calls: 2,
      llm_local_calls: 0,
      llm_deepseek_calls: 2,
      llm_latest_operation: "select_modules",
      llm_error_kind: "domain",
      llm_parse_status: "parse_error",
      llm_attempts: 2,
    }),
    /错误 域拒绝 \/ 解析 解析失败/
  );
});
