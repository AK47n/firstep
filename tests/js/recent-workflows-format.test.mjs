// 最近 LLM 工作流仪表盘格式化单测（llm-observability-dashboard/03）：
// 从 index.html 抽取纯函数，锁定 summary / detail 行文案，不碰 DOM / fetch。
// 运行：node --test tests/js/
import { readFileSync } from "node:fs";
import test from "node:test";
import assert from "node:assert/strict";

const html = readFileSync(
  new URL("../../src/contest_generator/static/index.html", import.meta.url),
  "utf8"
);

function extract(name) {
  const match = html.match(new RegExp("function " + name + "[\\s\\S]*?\\n\\}"));
  assert.ok(match, "index.html 中未找到 " + name + " 函数体（改名了？）");
  return match[0];
}

const ns = new Function(
  "return (() => {"
    + ["wfNum", "formatWorkflowUsage", "formatWorkflowSummary", "formatWorkflowCall"]
      .map(extract)
      .join("\n")
    + "\nreturn { formatWorkflowUsage, formatWorkflowSummary, formatWorkflowCall };"
    + "})()"
)();
const { formatWorkflowUsage, formatWorkflowSummary, formatWorkflowCall } = ns;

test("summary 行：provider 拆分 / call 数 / 耗时 / 请求字节 / 状态 / usage", () => {
  assert.equal(
    formatWorkflowSummary({
      workflow_name: "fix-errors",
      status: "error",
      call_count: 3,
      local_calls: 1,
      deepseek_calls: 2,
      request_bytes: 12345,
      duration_ms: 678,
      usage: { prompt_tokens: 10, completion_tokens: 2, total_tokens: 12 },
    }),
    "fix-errors ✗ · 3 calls · local 1 / DeepSeek 2 · request 12,345B · duration 678ms · usage(服务商上报) prompt_tokens=10, completion_tokens=2, total_tokens=12"
  );
});

test("summary 行：成功且无 usage 时省略 usage 段", () => {
  assert.equal(
    formatWorkflowSummary({
      workflow_name: "skeleton",
      status: "success",
      call_count: 1,
      local_calls: 0,
      deepseek_calls: 1,
      request_bytes: 90,
      duration_ms: 12,
    }),
    "skeleton ✓ · 1 calls · local 0 / DeepSeek 1 · request 90B · duration 12ms"
  );
});

test("detail 行：错误 / parse / http / attempts / budget_attempt / usage 全展开", () => {
  assert.equal(
    formatWorkflowCall({
      sequence: 2,
      operation: "summarize_topic",
      provider: "local",
      status: "error",
      error_kind: "network",
      parse_status: "parse_error",
      http_status: 502,
      attempts: 3,
      budget_attempt: 2,
      request_bytes: 25,
      duration_ms: 12,
      usage: { prompt_tokens: 1 },
    }),
    "#2 · summarize_topic · local · error · error network · parse parse_error · http 502 · attempts 3 · budget_attempt 2 · request 25B · duration 12ms · usage(服务商上报) prompt_tokens=1"
  );
});

test("detail 行：普通成功调用省略可选段", () => {
  assert.equal(
    formatWorkflowCall({
      sequence: 1,
      operation: "select_modules",
      provider: "deepseek",
      status: "success",
      request_bytes: 100,
      duration_ms: 12,
    }),
    "#1 · select_modules · deepseek · success · request 100B · duration 12ms"
  );
});

test("detail 行：字段缺失不炸，缺省兜底", () => {
  assert.equal(formatWorkflowCall({ sequence: 1 }), "#1 · unknown · ? · ? · request 0B · duration 0ms");
});

test("usage 标注为服务商上报；空 usage 返回空串", () => {
  assert.equal(formatWorkflowUsage({ prompt_tokens: 10 }), "usage(服务商上报) prompt_tokens=10");
  assert.equal(formatWorkflowUsage(null), "");
  assert.equal(formatWorkflowUsage({}), "");
  assert.equal(formatWorkflowUsage("x"), "");
});

test("仪表盘文案：token 标注服务商上报、不估算费用、仅内存不落盘", () => {
  assert.ok(html.includes("服务商上报"), "卡片脚注应标注 provider-reported");
  assert.ok(html.includes("不估算费用"), "卡片脚注应声明不估算费用");
  assert.ok(html.includes("仅保存在内存"), "卡片脚注应声明仅内存、重启清空");
  assert.ok(html.includes("/api/llm-workflows/recent"), "应调用只读 recent 端点");
});
