// 工单 code-ide-ai/03：IDE AI 对话面板消息流渲染（fx 纯件单测）
import test from "node:test";
import assert from "node:assert/strict";
import { aiChatMessagesHTML, quoteRefParts } from "../../src/contest_generator/static/js/fx/ai-chat.js";

test("aiChatMessagesHTML：空消息 + 无 pending → 引导文案", () => {
  const html = aiChatMessagesHTML([], "");
  assert.ok(html.includes("引导"), "应有引导文案");
  assert.ok(html.includes("选中"), "引导应提及选中代码");
});

test("aiChatMessagesHTML：user 消息 → 气泡 + 角色「我」+ 内容", () => {
  const html = aiChatMessagesHTML([{ role: "user", content: "这里为什么用定时器？" }], "");
  assert.ok(html.includes('class="sugg-msg user"'), "user 气泡类");
  assert.ok(html.includes("我"), "角色标签");
  assert.ok(html.includes("这里为什么用定时器？"), "内容渲染");
});

test("aiChatMessagesHTML：assistant 消息 → ai 气泡 + at 时间", () => {
  const html = aiChatMessagesHTML([{ role: "assistant", content: "因为…", at: "14:02" }], "");
  assert.ok(html.includes('class="sugg-msg ai"'), "ai 气泡类");
  assert.ok(html.includes("AI"), "角色标签");
  assert.ok(html.includes("14:02"), "时间渲染");
});

test("aiChatMessagesHTML：内容 HTML 转义防注入", () => {
  const html = aiChatMessagesHTML([{ role: "user", content: "<script>alert(1)</script>" }], "");
  assert.ok(html.includes("&lt;script&gt;"), "脚本标签被转义");
  assert.ok(!html.includes("<script>"), "无裸脚本标签");
});

test("aiChatMessagesHTML：pending 乐观气泡置尾", () => {
  const html = aiChatMessagesHTML(
    [{ role: "user", content: "第一问" }, { role: "assistant", content: "第一答" }],
    "第二问",
  );
  const iUser = html.indexOf("第一问");
  const iAi = html.indexOf("第一答");
  const iPending = html.indexOf("第二问");
  assert.ok(iUser >= 0 && iAi > iUser && iPending > iAi, "顺序：user → ai → pending");
  assert.ok(html.includes('class="sugg-msg user"'), "pending 也走 user 气泡");
});

test("quoteRefParts：识别引用消息（路径/行区间/lang/代码/剩余问题）", () => {
  const text = "【代码引用 · src/app.c · 第 3-5 行】\n```c\nint x = 1;\n```\n这个写法对吗？";
  const r = quoteRefParts(text);
  assert.ok(r, "应识别引用");
  assert.equal(r.path, "src/app.c");
  assert.equal(r.startLine, 3);
  assert.equal(r.endLine, 5);
  assert.equal(r.lang, "c");
  assert.equal(r.code, "int x = 1;");
  assert.equal(r.rest, "这个写法对吗？");
});

test("quoteRefParts：lang 空兜底 c；无围栏 → null", () => {
  assert.equal(quoteRefParts("【代码引用 · a.c · 第 1-2 行】\n```\nx\n```").lang, "c");
  assert.equal(quoteRefParts("【代码引用 · a.c · 第 1-2 行】\n没有围栏的文本"), null);
  assert.equal(quoteRefParts("普通问题"), null);
  assert.equal(quoteRefParts(null), null);
});

test("aiChatMessagesHTML：引用 user 消息 → details 卡片 + 问题文本", () => {
  const text = "【代码引用 · main.c · 第 1-2 行】\n```c\nint x < 3;\n```\n这里对吗？";
  const html = aiChatMessagesHTML([{ role: "user", content: text }], "");
  assert.ok(html.includes("code-ai-ref"), "卡片类");
  assert.ok(html.includes("<summary>代码引用 · main.c · 第 1-2 行</summary>"), "summary 路径与行区间");
  assert.ok(html.includes("code-ai-ref-code"), "代码片段 pre");
  assert.ok(html.includes("&lt;"), "代码转义");
  assert.ok(html.includes("code-ai-ref-rest"), "问题文本分离");
  assert.ok(!html.includes("<script>"), "无裸标签");
});

test("aiChatMessagesHTML：pending 引用消息同样卡片化", () => {
  const text = "【代码引用 · main.c · 第 1-2 行】\n```c\nx\n```\n";
  const html = aiChatMessagesHTML([], text);
  assert.ok(html.includes("code-ai-ref"), "pending 也渲染卡片");
  assert.ok(html.includes('class="sugg-msg user"'), "pending user 气泡");
});

test("aiChatMessagesHTML：assistant 含 DIFF 块 → 剥离为占位提示（无块原样）", () => {
  const withDiff = "改好了：\n<DIFF>{\"path\":\"main.c\",\"hunks\":[]}</DIFF>";
  const html = aiChatMessagesHTML([{ role: "assistant", content: withDiff }], "");
  assert.ok(!html.includes("<DIFF>"), "DIFF 块剥离");
  assert.ok(html.includes("预览改动"), "占位提示含按钮指引");
  const plain = aiChatMessagesHTML([{ role: "assistant", content: "正常回答" }], "");
  assert.ok(plain.includes("正常回答"), "无块原样");
  assert.ok(!plain.includes("预览改动"), "无块无提示");
});

test("aiChatMessagesHTML：多消息与 pending 分页顺序稳定", () => {
  const msgs = [
    { role: "user", content: "a" },
    { role: "assistant", content: "b" },
    { role: "user", content: "c" },
  ];
  const html = aiChatMessagesHTML(msgs, "");
  const ia = html.indexOf("：a<");
  const ib = html.indexOf("：b<");
  const ic = html.indexOf("：c<");
  assert.ok(ia >= 0 && ib > ia && ic > ib, "消息顺序渲染");
});
