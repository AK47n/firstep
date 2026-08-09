// SSE 解析器单测（工单 A 深化）：parseSSE 是 index.html 里唯一的纯函数接缝
// （不碰 DOM，只依赖 Response 流 / TextDecoder / 回调），从 HTML 抽取函数体
// 直接喂浏览器同构的 Response + ReadableStream 测试——替代 devtools 手测。
// 运行：node --test tests/js/
import { readFileSync } from "node:fs";
import test from "node:test";
import assert from "node:assert/strict";

const html = readFileSync(
  new URL("../../src/contest_generator/static/index.html", import.meta.url),
  "utf8"
);
const match = html.match(/async function parseSSE[\s\S]*?\n\}/);
assert.ok(match, "index.html 中未找到 parseSSE 函数体（改名了？）");
const parseSSE = new Function("return (" + match[0] + ")")(); // 函数声明包成表达式取引用

/** 构造带流的 Response：按 chunk 依次推字节（测分片）。 */
function streamResponse(chunks, crlf = false) {
  const encoder = new TextEncoder();
  const body = new ReadableStream({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(encoder.encode(crlf ? chunk.replace(/\n/g, "\r\n") : chunk));
      }
      controller.close();
    },
  });
  return new Response(body);
}

test("单帧：event + data + 空行 → 一次回调", async () => {
  const events = [];
  await parseSSE(streamResponse(['event: round\ndata: {"round":1,"round_total":4}\n\n']), (t, d) => events.push([t, d]));
  assert.deepEqual(events, [["round", '{"round":1,"round_total":4}']]);
});

test("一帧里两事件 + data 前导空格剥离", async () => {
  const events = [];
  // 线格式契约（sse._sse_frame）："data: " + JSON——恰好一个前导空格，剥离后原样
  await parseSSE(
    streamResponse(['event: converged\ndata: {"round":2}\n\nevent: done\ndata: {"ok":true}\n\n']),
    (t, d) => events.push([t, d])
  );
  assert.deepEqual(events, [
    ["converged", '{"round":2}'],
    ["done", '{"ok":true}'],
  ]);
});

test("多行 data：连 data: 行以换行拼接", async () => {
  const events = [];
  await parseSSE(
    streamResponse(['event: error\ndata: {"message":\ndata: "多行信息"}\n\n']),
    (t, d) => events.push([t, d])
  );
  assert.deepEqual(events, [["error", '{"message":\n"多行信息"}']]);
});

test("帧跨 chunk 边界（半帧推进不丢事件）", async () => {
  const events = [];
  const frame = 'event: round\ndata: {"round":3,"round_total":4}\n\n';
  await parseSSE(streamResponse([frame.slice(0, 17), frame.slice(17)]), (t, d) => events.push([t, d]));
  assert.deepEqual(events, [["round", '{"round":3,"round_total":4}']]);
});

test("单 chunk 含两帧且第二帧被切半", async () => {
  const events = [];
  const frame = 'event: batch_start\ndata: {"batch_index":1}\n\n';
  const chunk1 = frame + 'event: batch_done\ndata: {"processed_count":';
  const chunk2 = '2}\n\n';
  await parseSSE(streamResponse([chunk1, chunk2]), (t, d) => events.push([t, d]));
  assert.deepEqual(events, [
    ["batch_start", '{"batch_index":1}'],
    ["batch_done", '{"processed_count":2}'],
  ]);
});

test("CRLF 行尾（Windows 代理）归一化", async () => {
  const events = [];
  await parseSSE(
    streamResponse(['event: round\ndata: {"round":1}\n\n'], true),
    (t, d) => events.push([t, d])
  );
  assert.deepEqual(events, [["round", '{"round":1}']]);
});

test("流末尾缺最后一个空行也认（flush 兜底）", async () => {
  const events = [];
  await parseSSE(streamResponse(['event: done\ndata: {"ok":true}\n']), (t, d) => events.push([t, d]));
  assert.deepEqual(events, [["done", '{"ok":true}']]);
});

test("无关行（id / 注释）忽略", async () => {
  const events = [];
  await parseSSE(
    streamResponse([': keep-alive 注释\nid: 42\nevent: round\ndata: {"round":1}\n\n']),
    (t, d) => events.push([t, d])
  );
  assert.deepEqual(events, [["round", '{"round":1}']]);
});

test("无 body → 抛错（断线 = 放弃本次）", async () => {
  await assert.rejects(parseSSE(new Response(null), () => {}));
});
