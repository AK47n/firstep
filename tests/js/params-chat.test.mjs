// params-chat.test.mjs — fx/params-chat.js 参数速调 AI 咨询纯函数单测
// （工单 params-chat-ai/02）：AI 回复提及参数名 → 定位 chip（词边界 / 只包
// 真实参数名 / 用户消息不包 / esc 安全）、输入行（busy 禁用 / draft 回填）、
// 整区（open/close/空态引导/历史 + pending）。直接 import fx 模块。
import test from "node:test";
import assert from "node:assert/strict";
import {
  paramsChatMessageHTML, paramsChatInputHTML, paramsChatHTML,
} from "../../src/contest_generator/static/js/fx/params-chat.js";

test("paramsChatMessageHTML：AI 消息提及真实参数名 → 定位 chip（data-param-ref + title）", () => {
  const html = paramsChatMessageHTML(
    { role: "assistant", content: "先调 THRESHOLD，再看 SPEED。" },
    ["THRESHOLD", "SPEED"],
  );
  assert.ok(html.includes('<span class="sugg-msg-role">AI</span>'));
  assert.ok(html.includes(
    '<button class="btn-param-ref" data-param-ref="THRESHOLD" type="button" title="点击定位到参数卡">THRESHOLD</button>'
  ));
  assert.ok(html.includes(
    '<button class="btn-param-ref" data-param-ref="SPEED" type="button" title="点击定位到参数卡">SPEED</button>'
  ));
  // chip 前后的文本保留
  assert.ok(html.includes("先调"));
  assert.ok(html.includes("，再看"));
  assert.ok(html.includes("。"));
});

test("paramsChatMessageHTML：词边界——只包完整词，不误配前后缀", () => {
  const html = paramsChatMessageHTML(
    { role: "assistant", content: "THRESHOLDX 与 THRESHOLD 不同，MY_SPEED2 不匹配。" },
    ["THRESHOLD", "SPEED"],
  );
  // THRESHOLDX / MY_SPEED2 是完整词整体匹配（≠ 清单名）→ 不包；独立 THRESHOLD 包
  assert.equal((html.match(/data-param-ref="THRESHOLD"/g) || []).length, 1);
  assert.equal((html.match(/data-param-ref="SPEED"/g) || []).length, 0);
  assert.equal((html.match(/class="btn-param-ref"/g) || []).length, 1);
});

test("paramsChatMessageHTML：非真实参数名不包；用户消息恒不包", () => {
  const ai = paramsChatMessageHTML(
    { role: "assistant", content: "建议调 speed、spd（都是小写，不是清单里的原名）" },
    ["SPEED"],
  );
  assert.equal(ai.match(/class="btn-param-ref"/g), null);

  const user = paramsChatMessageHTML(
    { role: "user", content: "我觉得要调 THRESHOLD。" },
    ["THRESHOLD"],
  );
  assert.equal(user.match(/class="btn-param-ref"/g), null);
  assert.ok(user.includes('<span class="sugg-msg-role">我</span>'));
  // 用户消息原样转义
  const evil = paramsChatMessageHTML(
    { role: "user", content: '<img src=x onerror=alert(1)> "THRESHOLD"' },
    ["THRESHOLD"],
  );
  assert.ok(evil.includes("&lt;img"));
  assert.ok(!evil.includes("data-param-ref"));
});

test("paramsChatMessageHTML：AI 文本先转义再切词——标签不外泄、实体不误配", () => {
  const html = paramsChatMessageHTML(
    { role: "assistant", content: 'THRESHOLD <script>alert(1)</script> &amp;' },
    ["THRESHOLD"],
  );
  // 真实提及 THRESHOLD → 包 chip；script/amp 不在清单 → 不包
  assert.equal(html.match(/data-param-ref="THRESHOLD"/g).length, 1);
  assert.equal(html.match(/data-param-ref="script"/g), null);
  assert.equal(html.match(/data-param-ref="amp"/g), null);
  // HTML 标签与实体原样转义（无任何裸 <script>）
  assert.ok(html.includes("&lt;script&gt;alert(1)&lt;/script&gt;"));
  assert.ok(html.includes("&amp;amp;"));
  assert.ok(!html.includes("<script>"));
});

test("paramsChatMessageHTML：空 paramNames 不包任何 chip（未识别参数）", () => {
  const html = paramsChatMessageHTML(
    { role: "assistant", content: "先识别参数，比如 THRESHOLD。" },
    [],
  );
  assert.equal(html.match(/class="btn-param-ref"/g), null);
  assert.ok(html.includes("THRESHOLD"));
});

test("paramsChatMessageHTML：at 时间戳转义渲染", () => {
  const html = paramsChatMessageHTML({
    role: "assistant", content: "好", at: "2026-08-29T10:00:00+0800",
  }, []);
  assert.ok(html.includes('<span class="muted">2026-08-29T10:00:00+0800</span>'));
});

test("paramsChatInputHTML：输入框 + 发送按钮，busy 禁用 + 文案「回应中…」，draft 回填转义", () => {
  const idle = paramsChatInputHTML({ draft: "" });
  assert.ok(idle.includes('id="params-chat-input"'));
  assert.ok(idle.includes(">发送</button>"));
  assert.ok(!idle.includes("disabled"));

  const busy = paramsChatInputHTML({ busy: true, draft: '未发送"内容"' });
  assert.ok(busy.includes(" disabled"));
  assert.ok(busy.includes("回应中…"));
  assert.ok(busy.includes('value="未发送&quot;内容&quot;"'));
});

test("paramsChatHTML：close → 空串；open 空历史 → 引导文案；历史 + pending 渲染", () => {
  assert.equal(paramsChatHTML({ open: false }, []), "");
  assert.equal(paramsChatHTML({}, []), "");

  const empty = paramsChatHTML({ open: true, chat: { messages: [] } }, []);
  assert.ok(empty.includes("这是「该调哪个参数」的咨询区"));
  assert.ok(empty.includes('id="params-chat-input"'));

  const history = paramsChatHTML({
    open: true,
    chat: { messages: [
      { role: "user", content: "小车直行跑偏" },
      { role: "assistant", content: "先调 THRESHOLD。" },
    ] },
  }, ["THRESHOLD"]);
  assert.ok(history.includes("小车直行跑偏"));
  assert.ok(history.includes('data-param-ref="THRESHOLD"'));
  assert.ok(history.includes('<div class="sugg-discuss-msgs">'));

  const pending = paramsChatHTML({
    open: true, chat: { messages: [] }, pending: "还在问…", busy: true,
  }, []);
  assert.ok(pending.includes("还在问…"));
  assert.ok(pending.includes("AI 回应中…（分钟级调用，请等待）"));
});

test("paramsChatHTML：busy 时输入行按钮禁用", () => {
  const html = paramsChatHTML({ open: true, busy: true, chat: { messages: [] } }, []);
  assert.ok(html.includes(" disabled"));
  assert.ok(html.includes("回应中…"));
});
