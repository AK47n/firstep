// 推荐流程 llm_telemetry 展示结构钉（工单 recommend-telemetry/01）：
// 推荐 SSE 流绑定 telemetry 后，每次 LLM 调用完成前端显示观测快照
// （调用数 / provider 分流 / 最新 operation / 耗时）——"AI 正在干什么"。
// 运行：node --test tests/js/
import { readFileSync } from "node:fs";
import test from "node:test";
import assert from "node:assert/strict";

const html = readFileSync(
  new URL("../../src/contest_generator/static/index.html", import.meta.url),
  "utf8"
);

test("推荐进度面板有 telemetry 展示位", () => {
  assert.match(html, /id="rec-llm-telemetry"/);
  assert.match(html, /class="llm-telemetry hidden"/);
});

test("recPanel 事件表含 llm_telemetry handler（复用 formatLLMTelemetry）", () => {
  const match = html.match(/const recPanel = makeProgressPanel\([\s\S]*?\n\}\);/);
  assert.ok(match, "未找到 recPanel 定义（改名了？）");
  const body = match[0];
  assert.match(body, /llm_telemetry:\s*\(ev\)\s*=>/);
  assert.match(body, /formatLLMTelemetry\(ev\)/);
});

test("新推荐生命周期清掉旧 telemetry", () => {
  const match = html.match(/function startRecProgress\(\)[\s\S]*?\n\}/);
  assert.ok(match, "未找到 startRecProgress（改名了？）");
  const body = match[0];
  assert.match(body, /rec-llm-telemetry/);
  assert.match(body, /classList\.add\("hidden"\)/);
});

test("蒸馏进度面板有 telemetry 展示位与 handler（照推荐先例）", () => {
  assert.match(html, /id="prog-llm-telemetry"/);
  const dist = html.match(/const distPanel = makeProgressPanel\([\s\S]*?\n\}\);/);
  assert.ok(dist, "未找到 distPanel 定义（改名了？）");
  assert.match(dist[0], /llm_telemetry:\s*\(data\)\s*=>/);
  assert.match(dist[0], /formatLLMTelemetry\(data\)/);
  const start = html.match(/function startProgress\(\)[\s\S]*?\n\}/);
  assert.ok(start, "未找到 startProgress（改名了？）");
  assert.match(start[0], /prog-llm-telemetry/);
});

test("第 7 步引脚配置有自动配置按钮与端点接线", () => {
  assert.match(html, /id="btn-pin-auto"/);
  assert.match(html, /\/api\/bindings\/auto/);
  const handler = html.match(/\$\("btn-pin-auto"\)\.addEventListener\([\s\S]*?\n\}\);/);
  assert.ok(handler, "未找到 btn-pin-auto 事件监听（改名了？）");
  assert.match(handler[0], /collectBindings/);
  assert.match(handler[0], /renderPinCard\(\)/);
});
