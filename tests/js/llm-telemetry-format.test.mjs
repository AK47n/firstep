// LLM telemetry 状态行格式化测试（llm-observability-dashboard/02）：
// 从 index.html 抽取纯函数，锁定第 10 栏紧凑展示文案，不碰 DOM / fetch。
// 运行：node --test tests/js/
import { readFileSync } from "node:fs";
import test from "node:test";
import assert from "node:assert/strict";

const html = readFileSync(
  new URL("../../src/contest_generator/static/index.html", import.meta.url),
  "utf8"
);
const match = html.match(/function formatLLMTelemetry[\s\S]*?\n\}/);
assert.ok(match, "index.html 中未找到 formatLLMTelemetry 函数体（改名了？）");
const formatLLMTelemetry = new Function("return (" + match[0] + ")")();

test("LLM telemetry 行显示 calls / provider split / latest / error / bytes / duration / usage", () => {
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
    "LLM：3 calls · local 1 / DeepSeek 2 · latest fix_compile_errors · error network / parse parse_error · http 502 · attempts 4, retries 2, errors 2, parse_errors 1, 429 1, network 1, 5xx 1 · request 12,345B · duration 678ms · usage prompt_tokens=10, completion_tokens=2, total_tokens=12"
  );
});

test("无 usage / 无错误时省略对应段", () => {
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
    "LLM：1 calls · local 0 / DeepSeek 1 · latest select_modules · parse success · request 90B · duration 12ms"
  );
});
