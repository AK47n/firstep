// 步骤 2「赛题预读」展示层纯函数单测（工单 topic-preread/02）：
// prereadReminderGroups（按步骤分组 / 多步同现 / 其他限定最后）/
// prereadGroupLabel（步骤名查表不硬编码）/ prereadHTML（总览 + 分组 + 引用
// 小字 + 转义）。
// 对偶 step-done-refs.test.mjs 范式：只测外部行为（分组结果 / 渲染子串）。
import test from "node:test";
import assert from "node:assert/strict";
import {
  prereadReminderGroups, prereadGroupLabel, prereadHTML, prereadSlotHTML, OTHER_GROUP_LABEL,
} from "../../src/contest_generator/static/js/fx/topic-preread.js";

const reminders = [
  { steps: [3], text: "题面限定采用 TI MSPM0 系列", quote: "采用 TI 公司 MSPM0 系列处理器" },
  { steps: [5, 7], text: "只允许使用组委会提供的传感器", quote: "只能使用" },
  { steps: [], text: "车体尺寸不超过 30cm", quote: "" },
];

// ================= 分组：prereadReminderGroups =================
test("分组按步骤升序；空 steps 归其他限定组放最后", () => {
  const groups = prereadReminderGroups(reminders);
  assert.deepEqual(groups.map((g) => g.step), [3, 5, 7, null]);
  assert.equal(groups[groups.length - 1].items.length, 1);
  assert.equal(groups[groups.length - 1].items[0].text, "车体尺寸不超过 30cm");
});

test("一条提醒影响多个步骤 → 每个相关组都出现（多卡同现语义）", () => {
  const groups = prereadReminderGroups(reminders);
  const s5 = groups.find((g) => g.step === 5);
  const s7 = groups.find((g) => g.step === 7);
  assert.ok(s5.items.some((i) => i.text === "只允许使用组委会提供的传感器"));
  assert.ok(s7.items.some((i) => i.text === "只允许使用组委会提供的传感器"));
});

test("步骤乱序输入 → 输出升序；无其他限定 → 无 null 组", () => {
  const groups = prereadReminderGroups([
    { steps: [11, 3], text: "a" },
    { steps: [6], text: "b" },
  ]);
  assert.deepEqual(groups.map((g) => g.step), [3, 6, 11]);
  assert.ok(!groups.some((g) => g.step === null));
});

test("非法输入防御：非数组 / 缺 steps / 非整数 steps / 缺 text", () => {
  assert.deepEqual(prereadReminderGroups(null), []);
  assert.deepEqual(prereadReminderGroups([{ text: "x", quote: "" }]), [
    { step: null, items: [{ text: "x", quote: "" }] },
  ]);
  // 非整数 steps 被丢弃；非字符串 text / quote 强转不炸
  const groups = prereadReminderGroups([{ steps: [3, NaN, "7"], text: 42, quote: 7 }]);
  assert.deepEqual(groups.map((g) => g.step), [3]);
});

// ================= 组标题：prereadGroupLabel =================
test("组标题：步骤名查表 + 无表回退 + 其他限定", () => {
  assert.equal(prereadGroupLabel({ step: 3, items: [] }, { 3: "目标平台" }), "步骤 3 · 目标平台");
  assert.equal(prereadGroupLabel({ step: 3, items: [] }, {}), "步骤 3");
  assert.equal(prereadGroupLabel({ step: null, items: [] }, {}), OTHER_GROUP_LABEL);
});

// ================= 渲染：prereadHTML =================
test("渲染：总览一行 + 组标题 + 提醒文本 + 引用小字（无引用不渲染）", () => {
  const html = prereadHTML({ overview: "做一个智能小车", reminders }, { 3: "目标平台" });
  assert.match(html, /preread-overview">做一个智能小车</);
  assert.match(html, /步骤 3 · 目标平台/);
  assert.match(html, /题面限定采用 TI MSPM0 系列/);
  assert.match(html, /preread-quote">题面原文：采用 TI 公司 MSPM0 系列处理器</);
  assert.doesNotMatch(html, /preread-quote">题面原文：<\/div>/);  // 空引用不出小字行
});

test("渲染：HTML 转义防注入（文本 / 引用 / 总览）", () => {
  const html = prereadHTML(
    { overview: "<b>总览</b>", reminders: [{ steps: [], text: "<script>x</script>", quote: "\"引号\"" }] },
    {}
  );
  assert.ok(!html.includes("<script>"));
  assert.match(html, /&lt;b&gt;总览&lt;\/b&gt;/);
  assert.match(html, /&lt;script&gt;x&lt;\/script&gt;/);
});

test("渲染：空 reminders 只有总览；空数据输出空串", () => {
  assert.equal(prereadHTML({ overview: "只有总览", reminders: [] }, {}).includes("preread-group"), false);
  assert.ok(prereadHTML({ overview: "只有总览", reminders: [] }, {}).includes("只有总览"));
  assert.equal(prereadHTML(null, {}), "");
  assert.equal(prereadHTML({ overview: "", reminders: null }, {}), "");
});

// ================= 钉卡横幅：prereadSlotHTML =================
test("钉卡横幅：每条提醒一行 + 引用小字（无引用省略）+ 转义", () => {
  const html = prereadSlotHTML([
    { text: "题面限定采用 TI MSPM0 系列", quote: "采用 TI 公司 MSPM0 系列处理器" },
    { text: "<script>渲染</script>", quote: "" },
  ]);
  assert.match(html, /题面限定采用 TI MSPM0 系列/);
  assert.match(html, /题面原文：采用 TI 公司 MSPM0 系列处理器/);
  assert.ok(!html.includes("<script>"));
  assert.match(html, /&lt;script&gt;渲染&lt;\/script&gt;/);
});

test("钉卡横幅：空条目输出空串；非数组防御", () => {
  assert.equal(prereadSlotHTML([]), "");
  assert.equal(prereadSlotHTML(null), "");
});
