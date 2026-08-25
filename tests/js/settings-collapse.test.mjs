// settings-collapse.test.mjs — 设置页折叠纯函数单测（工单 settings-infoarch/01/02/03）：
// parseSettingsCollapse / settingsDefaultCollapsed / effectiveCollapsed /
// applySettingsCollapseState（卡片 + 计费小节两分支）+ settingsMasterLabel / sectionCollapseLabel。
// 抽取方式沿 card-collapse.test.mjs 先例：先抽既有核心块（提供 syncCollapseBtn），
// 再抽设置页折叠块，拼进同一 Function 作用域（新块函数体引用 syncCollapseBtn）。
import { readFileSync } from "node:fs";
import test from "node:test";
import assert from "node:assert/strict";

const html = readFileSync(
  new URL("../../src/contest_generator/static/index.html", import.meta.url),
  "utf8"
);

// 既有核心块（card-collapse.test.mjs 同款正则）：collapseBtnLabel/syncCollapseBtn/collapseToggleAll
const coreMatch = html.match(
  /function collapseBtnLabel[\s\S]*?function syncCollapseBtn[\s\S]*?function collapseToggleAll[\s\S]*?\n\}/
);
assert.ok(
  coreMatch,
  "index.html 中未找到既有 collapseBtnLabel/syncCollapseBtn/collapseToggleAll 块（改名了？）"
);

// 设置页折叠块：SETTINGS_COLLAPSE_KEY 常量起到 initSettingsCollapse 止
const match = html.match(
  /const SETTINGS_COLLAPSE_KEY[\s\S]*?function initSettingsCollapse[\s\S]*?\n\}/
);
assert.ok(match, "index.html 中未找到设置页折叠函数块（改名了？）");

const fns = new Function(
  coreMatch[0] + "\n" + match[0] + "\nreturn { parseSettingsCollapse, settingsDefaultCollapsed, effectiveCollapsed, applySettingsCollapseState, settingsMasterLabel, sectionCollapseLabel };"
)();
const { parseSettingsCollapse, settingsDefaultCollapsed, effectiveCollapsed, applySettingsCollapseState, settingsMasterLabel, sectionCollapseLabel } = fns;
for (const name of ["parseSettingsCollapse", "settingsDefaultCollapsed", "effectiveCollapsed", "applySettingsCollapseState", "settingsMasterLabel", "sectionCollapseLabel"]) {
  assert.equal(typeof fns[name], "function", `${name} 未从 index.html 抽取成功`);
}

// 存储键契约：firstep.settingsCollapse.v1 必须出现在 index.html（防漂移）
assert.match(html, /firstep\.settingsCollapse\.v1/, "设置页折叠存储键 firstep.settingsCollapse.v1 缺失");

// 假卡片：只实现 classList.toggle / querySelector(".card-collapse") / title/aria-label 回写
function fakeCardEl(collapsed, withBtn = true) {
  const state = { collapsed: !!collapsed, btnTitle: "", ariaLabel: "" };
  const btn = {
    set title(v) { state.btnTitle = v; },
    setAttribute(k, v) { if (k === "aria-label") state.ariaLabel = v; },
  };
  return {
    _state: state,
    _btn: btn,
    querySelector: (sel) => (sel === ".card-collapse" && withBtn ? btn : null),
    classList: { toggle: (k, v) => { if (k === "collapsed") state.collapsed = v; } },
  };
}

// 假计费小节：querySelector(".settings-collapse-head") 返回头按钮，无 .card-collapse
function fakeSectionEl(collapsed) {
  const state = { collapsed: !!collapsed, headTitle: "", ariaLabel: "" };
  const head = {
    set title(v) { state.headTitle = v; },
    setAttribute(k, v) { if (k === "aria-label") state.ariaLabel = v; },
  };
  return {
    _state: state,
    querySelector: (sel) =>
      sel === ".settings-collapse-head" ? head : sel === ".card-collapse" ? null : null,
    classList: { toggle: (k, v) => { if (k === "collapsed") state.collapsed = v; } },
  };
}

test("parseSettingsCollapse：空/垃圾输入回 { }", () => {
  assert.deepEqual(parseSettingsCollapse(""), {});
  assert.deepEqual(parseSettingsCollapse("null"), {});
  assert.deepEqual(parseSettingsCollapse("{bad json"), {});
  assert.deepEqual(parseSettingsCollapse("42"), {});
  assert.deepEqual(parseSettingsCollapse("[]"), {});
});

test("parseSettingsCollapse：合法 JSON 对象透传", () => {
  assert.deepEqual(parseSettingsCollapse('{"libs":true,"llm-api":false}'), { libs: true, "llm-api": false });
});

test("settingsDefaultCollapsed：默认集成员判定", () => {
  assert.equal(settingsDefaultCollapsed("libs"), true);
  assert.equal(settingsDefaultCollapsed("toolchain"), true);
  assert.equal(settingsDefaultCollapsed("local-llm"), true);
  assert.equal(settingsDefaultCollapsed("vision"), true);
  assert.equal(settingsDefaultCollapsed("ai-billing"), true);
  assert.equal(settingsDefaultCollapsed("llm-api"), false);
  assert.equal(settingsDefaultCollapsed("app"), false);
  assert.equal(settingsDefaultCollapsed("usage"), false);
  assert.equal(settingsDefaultCollapsed("recent-wf"), false);
  assert.equal(settingsDefaultCollapsed("no-such-id"), false);
});

test("effectiveCollapsed：stored 覆盖默认（含显式 false 展开）", () => {
  assert.equal(effectiveCollapsed("libs", {}), true);          // 默认收起
  assert.equal(effectiveCollapsed("libs", { libs: false }), false); // 用户展开
  assert.equal(effectiveCollapsed("llm-api", {}), false);      // 默认展开
  assert.equal(effectiveCollapsed("llm-api", { "llm-api": true }), true); // 用户收起
  assert.equal(effectiveCollapsed("app", { app: true }), true);
  assert.equal(effectiveCollapsed("unknown", {}), false);
});

test("applySettingsCollapseState：卡片分支 class + title/aria-label 同步", () => {
  const el = fakeCardEl(false);
  applySettingsCollapseState(el, true);
  assert.equal(el._state.collapsed, true);
  assert.equal(el._state.btnTitle, "展开");
  assert.equal(el._state.ariaLabel, "展开该卡片");
  applySettingsCollapseState(el, false);
  assert.equal(el._state.collapsed, false);
  assert.equal(el._state.btnTitle, "折叠");
  assert.equal(el._state.ariaLabel, "折叠该卡片");
});

test("applySettingsCollapseState：计费小节分支 class + 头按钮 aria-label", () => {
  const el = fakeSectionEl(false);
  applySettingsCollapseState(el, true);
  assert.equal(el._state.collapsed, true);
  assert.equal(el._state.headTitle, "展开");
  assert.equal(el._state.ariaLabel, "展开计费区");
  applySettingsCollapseState(el, false);
  assert.equal(el._state.collapsed, false);
  assert.equal(el._state.ariaLabel, "折叠计费区");
});

test("applySettingsCollapseState：无按钮元素只切 class 不崩", () => {
  const el = fakeCardEl(false, false);
  applySettingsCollapseState(el, true);
  assert.equal(el._state.collapsed, true);
});

test("settingsMasterLabel：全部折叠/非全折双向", () => {
  assert.equal(settingsMasterLabel(true), "全部展开");
  assert.equal(settingsMasterLabel(false), "全部收起");
});

test("sectionCollapseLabel：计费区折叠/展开双向", () => {
  assert.equal(sectionCollapseLabel(true), "展开计费区");
  assert.equal(sectionCollapseLabel(false), "折叠计费区");
});
