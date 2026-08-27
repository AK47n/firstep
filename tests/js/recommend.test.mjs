// 买件指引选型参考纯函数单测（工单 buy-guide/02）：库外建议 chip 展开/
// 收起 + 方案行 + 徽标（推荐 / AI 建议 / 共存 / 都无）+ solutions 空回退旧样。
// 运行：node --test tests/js/
import { readFileSync } from "node:fs";
import test from "node:test";
import assert from "node:assert/strict";
import {
  suggestionSolutionBadges, suggestionOptionRowHTML,
  suggestionOptionsHTML, suggestionChipHTML,
  decisionBadgeHTML, reviewBadgeHTML, decisionPayload,
  suggestionKey, loadBuyDecisions, saveBuyDecisions, matchBuyDecision,
  discussionAreaHTML,
} from "../../src/contest_generator/static/js/fx/recommend.js";

// 结构护栏：纯函数单源在 fx/recommend.js，index.html / ui 层不得再定义
const html = readFileSync(
  new URL("../../src/contest_generator/static/index.html", import.meta.url),
  "utf8"
);
for (const name of ["suggestionSolutionBadges", "suggestionOptionRowHTML",
  "suggestionOptionsHTML", "suggestionChipHTML"]) {
  test(`纯函数单源：${name} 不在 index.html 内联定义`, () => {
    assert.ok(!new RegExp("function\\s+" + name + "\\s*\\(").test(html));
  });
}

const SOL = (over = {}) => ({
  name: "K230 CanMV", interface: "SPI/串口", price: "￥60-90/套",
  note: "内置视觉AI，跑色块/矩形识别", suitable: "识别类赛题", recommended: true, ...over,
});

test("徽标：仅推荐 → 只出「推荐」", () => {
  const out = suggestionSolutionBadges(SOL(), "");
  assert.match(out, /sugg-rec/);
  assert.ok(!out.includes("sugg-ai"));
});

test("徽标：selected 命中 → 只出「AI 建议」", () => {
  const out = suggestionSolutionBadges(SOL({ recommended: false }), "K230 CanMV");
  assert.match(out, /sugg-ai/);
  assert.ok(!out.includes("sugg-rec"));
});

test("徽标：推荐 + AI 建议可共存", () => {
  const out = suggestionSolutionBadges(SOL(), "K230 CanMV");
  assert.match(out, /sugg-rec/);
  assert.match(out, /sugg-ai/);
});

test("徽标：均无 → 空串；selected 词表外 / 空串不高亮", () => {
  assert.equal(suggestionSolutionBadges(SOL({ recommended: false }), ""), "");
  assert.equal(suggestionSolutionBadges(SOL({ recommended: false }), "别的方案"), "");
});

test("方案行：名称/接口/价格/徽标/备注/适用齐全且转义", () => {
  const out = suggestionOptionRowHTML(SOL({ note: "注意 <坑>", suitable: "识别" }), "K230 CanMV");
  assert.match(out, /sugg-name/);
  assert.match(out, /SPI\/串口/);
  assert.match(out, /￥60-90\/套/);
  assert.match(out, /sugg-rec/);
  assert.match(out, /sugg-ai/);
  assert.match(out, /注意 &lt;坑&gt;/);   // esc 转义
  assert.match(out, /适用：识别/);
});

test("方案行：可空字段缺失不渲染对应段", () => {
  const out = suggestionOptionRowHTML(
    { name: "卫星模块", interface: "", price: "", note: "", suitable: "", recommended: false }, "");
  assert.ok(!out.includes("sugg-meta"));
  assert.ok(!out.includes("sugg-note"));
  assert.ok(!out.includes("适用："));
  assert.ok(!out.includes("sugg-rec") && !out.includes("sugg-ai"));
});

test("面板：solutions 空 → 空串（不渲染）", () => {
  assert.equal(suggestionOptionsHTML({ solutions: [], selected: "" }), "");
  assert.equal(suggestionOptionsHTML({ selected: "" }), "");
});

test("面板：多方案逐行渲染 + 标题", () => {
  const out = suggestionOptionsHTML({
    solutions: [SOL(), SOL({ name: "OpenMV H7", recommended: false })],
    selected: "K230 CanMV",
  });
  assert.match(out, /选型参考/);
  assert.equal((out.match(/sugg-row/g) || []).length, 2);
  assert.match(out, /K230 CanMV/);
  assert.match(out, /OpenMV H7/);
});

test("chip：solutions 空 → 旧行为（无 wrapper / 无计数 / 无面板）", () => {
  const out = suggestionChipHTML({ name: "某型号", examples: ["A", "B"], degraded: true });
  assert.ok(!out.includes("sugg-wrap"));
  assert.ok(!out.includes("sugg-count"));
  assert.ok(!out.includes("sugg-panel"));
  assert.match(out, /chip out/);
  assert.match(out, /需自备（型号不在词表，按类别展示）：A \/ B/);
});

test("chip：有方案 → wrapper + 「⤵ N 方案」计数 + 面板 + 名称转义", () => {
  const out = suggestionChipHTML({
    name: "视觉模块 <v>", examples: [], degraded: false,
    solutions: [SOL({ name: "A" }), SOL({ name: "B", recommended: false })],
    selected: "A",
  });
  assert.match(out, /sugg-wrap/);
  assert.match(out, /⤵ 2 方案/);
  assert.match(out, /sugg-panel/);
  assert.match(out, /sugg-chip/);
  assert.match(out, /视觉模块 &lt;v&gt;/);
  assert.equal((out.match(/sugg-row/g) || []).length, 2);
});

// ===== 已定方案与商量（工单 buy-discuss/04）=====

test("已定徽标：wordlist / custom 两形态 + 缺省空", () => {
  const w = decisionBadgeHTML({ source: "wordlist", name: "NRF24L01 遥控" });
  assert.match(w, /sugg-decided/);
  assert.match(w, /✓ 已定：NRF24L01 遥控/);
  const c = decisionBadgeHTML({ source: "custom", name: "我的旧 HC-SR04", verdict: "risky" });
  assert.match(c, /✓ 已定·自定：我的旧 HC-SR04/);
  assert.equal(decisionBadgeHTML(null), "");
  assert.equal(decisionBadgeHTML({ source: "wordlist", name: "" }), "");
});

test("审核徽标：三态 + reason + 缺省空（词表外 verdict 无标签回退）", () => {
  assert.match(reviewBadgeHTML({ verdict: "feasible", reason: "接口简单" }), /sugg-review-feasible/);
  assert.match(reviewBadgeHTML({ verdict: "risky", reason: "阳光强" }), /sugg-review-risky/);
  assert.match(reviewBadgeHTML({ verdict: "infeasible", reason: "无此驱动" }), /sugg-review-infeasible/);
  assert.match(reviewBadgeHTML({ verdict: "risky", reason: "阳光强" }), /AI 审核：有风险：阳光强/);
  assert.equal(reviewBadgeHTML(null), "");
  assert.equal(reviewBadgeHTML({ verdict: "" }), "");
});

test("decisionPayload：上行形状（wordlist / custom + note + verdict）", () => {
  assert.deepEqual(
    decisionPayload({ source: "wordlist", name: "NRF24L01 遥控", note: "", verdict: "" }),
    { source: "wordlist", name: "NRF24L01 遥控", note: "", verdict: "" }
  );
  assert.deepEqual(
    decisionPayload({ source: "custom", name: "旧 HC-SR04", note: "仓库翻出", verdict: "risky" }),
    { source: "custom", name: "旧 HC-SR04", note: "仓库翻出", verdict: "risky" }
  );
  assert.equal(decisionPayload(null), null);
});

test("记忆读写：load 损坏 JSON → 空对象；save 写回；match 按建议名命中", () => {
  const store = new Map();
  const storage = {
    getItem: (k) => (store.has(k) ? store.get(k) : null),
    setItem: (k, v) => store.set(k, String(v)),
  };
  assert.deepEqual(loadBuyDecisions(storage), {});              // 无键
  assert.equal(saveBuyDecisions(storage, { 遥控接收: { source: "wordlist", name: "NRF" } }), true);
  assert.deepEqual(loadBuyDecisions(storage), { 遥控接收: { source: "wordlist", name: "NRF" } });
  assert.deepEqual(matchBuyDecision(loadBuyDecisions(storage), "遥控接收"),
    { source: "wordlist", name: "NRF" });
  assert.equal(matchBuyDecision(loadBuyDecisions(storage), "别的建议"), null);

  // 损坏 JSON → 空对象（不炸）
  const bad = { getItem: () => "{损坏", setItem: () => {} };
  assert.deepEqual(loadBuyDecisions(bad), {});
  // save 抛错（隐私模式）→ false
  const fail = { setItem: () => { throw new Error("denied"); } };
  assert.equal(saveBuyDecisions(fail, {}), false);
});

test("suggestionKey：建议名（词表外降级名即类别名，重推后仍可匹配恢复）", () => {
  assert.equal(suggestionKey({ name: "遥控接收" }), "遥控接收");
  assert.equal(suggestionKey(null), "");
});

test("讨论区：有方案渲染（toggle + 输入 + 历史消息 + AI 审核徽标）；无方案 = 空串", () => {
  const out = discussionAreaHTML({
    name: "遥控接收", solutions: [SOL()],
  }, {
    open: true, busy: false,
    history: [{ role: "user", content: "我想用红外" }, { role: "assistant", content: "红外怕强光" }],
    review: { verdict: "risky", reason: "阳光强" },
  });
  assert.match(out, /和 AI 商量/);
  assert.match(out, /sugg-discuss-box open/);
  assert.match(out, /我想用红外/);
  assert.match(out, /红外怕强光/);
  assert.match(out, /sugg-review-risky/);
  assert.match(out, /sugg-discuss-input/);
  assert.match(out, /发送/);
  assert.equal(discussionAreaHTML({ name: "无方案", solutions: [] }, {}), "");
  assert.equal(discussionAreaHTML({ name: "无方案", solutions: [], }, { open: true }), "");
});

test("面板尾部含讨论区（有方案时）", () => {
  const out = suggestionOptionsHTML({
    solutions: [SOL()], selected: "",
  });
  assert.match(out, /sugg-discuss/);
});
