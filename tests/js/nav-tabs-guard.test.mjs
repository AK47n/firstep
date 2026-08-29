// 顶部导航 tab 分组守卫（工单 tab-grouping/01/02；工单 beginner-guide/01 增「指南」组）：
// 读 index.html 静态标记锁定——组容器（做题 / 资料管理 / 指南）各恰好一个、
// 9 个 tab 键无多余/缺失、组归属与组内顺序精确、组容器不可点击且无旧组标签
// （tab-group-label 随胶囊导航重构移除，防把分组拆掉或把标签升级成按钮）、
// 9 个按钮均带非空中文 title（防占位半句话）、每个 tab 键有对应 section 容器
// （防死按钮）。
// 仿 tab-nav-guard.test.mjs 先例：静态标记的守卫测试直接读 HTML 断言。
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const html = readFileSync(
  new URL("../../src/contest_generator/static/index.html", import.meta.url),
  "utf8",
);

// 分组定义（与 index.html 顶部导航的标记契约）：组内顺序 = 组内按钮出现顺序。
const GROUPS = [
  { label: "做题", keys: ["generate", "topic", "settings"] },
  { label: "资料管理", keys: ["library", "reference", "pdf", "master", "changelog"] },
  { label: "指南", keys: ["guide"] },
];
const ALL_KEYS = GROUPS.flatMap((g) => g.keys);

function countOccurrences(text, needle) {
  return text.split(needle).length - 1;
}

/** 顶部导航块：锚定 <header> 内的 <nav>（避免误配 #step-nav /
 * #revise-tabs 等其他 nav；评审整改：原裸 <nav> 正则一旦头 nav 加属性
 * 会静默改指别的 nav）。非贪婪匹配到第一个 </nav> 即其自有的闭合。 */
function headerNavHTML() {
  const m = html.match(/<header[\s\S]*?<nav>([\s\S]*?)<\/nav>/);
  assert.ok(m, "index.html 应含 header 内的顶部 <nav>");
  return m[1];
}

/** 取一个分组块的内部 HTML（<div class="tab-group"...> 到第一个 </div>）。 */
function groupInnerHTML(label) {
  const re = new RegExp(
    '<div class="tab-group" role="group" aria-label="' + label + '"[^>]*>([\\s\\S]*?)</div>');
  const m = html.match(re);
  assert.ok(m, "分组容器 '" + label + "' 应存在");
  return m[1];
}

test("组容器：做题 / 资料管理 / 指南 各恰好一个，且无旧组标签残留", () => {
  for (const g of GROUPS) {
    const container = 'class="tab-group" role="group" aria-label="' + g.label + '"';
    assert.equal(countOccurrences(html, container), 1,
      "分组容器 '" + g.label + "' 应恰好出现一次");
  }
  assert.equal(countOccurrences(html, "tab-group-label"), 0,
    "旧组标签（tab-group-label）应已移除——胶囊导航重构后分组由 aria-label + 细分隔线表达");
});

test("9 个 tab 键在顶部导航内各恰好一次，无多余/缺失", () => {
  const nav = headerNavHTML();
  for (const key of ALL_KEYS) {
    assert.equal(countOccurrences(nav, 'data-tab="' + key + '"'), 1,
      "tab '" + key + "' 应恰好出现一次");
  }
  const total = countOccurrences(nav, "data-tab=");
  assert.equal(total, ALL_KEYS.length,
    "顶部导航应恰好 " + ALL_KEYS.length + " 个 tab 按钮（实际 " + total + "）");
});

test("组归属与组内顺序：做题 3 个、资料管理 5 个、指南 1 个，无串组", () => {
  for (const g of GROUPS) {
    const inner = groupInnerHTML(g.label);
    const keys = [...inner.matchAll(/data-tab="([^"]+)"/g)].map((m) => m[1]);
    assert.deepEqual(keys, g.keys,
      "组 '" + g.label + "' 应恰好含 " + g.keys.join(",") + " 且保持该顺序");
  }
});

test("组容器不可点击且无标签按钮：容器无 data-tab，组内无 tab-group-label", () => {
  for (const g of GROUPS) {
    const containerMatch = html.match(new RegExp(
      '<div class="tab-group" role="group" aria-label="' + g.label + '"[^>]*>'));
    assert.ok(containerMatch, "分组容器 '" + g.label + "' 应存在");
    assert.ok(!/data-tab/.test(containerMatch[0]),
      "组容器 '" + g.label + "' 不得携带 data-tab（容器进 [data-tab] 绑定会打断切换）");
    const inner = groupInnerHTML(g.label);
    assert.ok(!/<button[^>]*class="tab-group-label"/.test(inner),
      "组 '" + g.label + "' 不得含有标签按钮（组内应只剩 tab 按钮）");
  }
});

test("组先后顺序：做题组在资料管理组之前，指南组在最后（主流程入口在左半区）", () => {
  const gen = html.indexOf('aria-label="做题"');
  const lib = html.indexOf('aria-label="资料管理"');
  const guide = html.indexOf('aria-label="指南"');
  assert.ok(gen >= 0 && lib >= 0 && guide >= 0, "三组容器都应存在");
  assert.ok(gen < lib, "组顺序应为「做题」在「资料管理」之前（评审整改：补组序断言）");
  assert.ok(lib < guide, "组顺序应为「指南」在「资料管理」之后（工单 beginner-guide/01 契约）");
});

test("tab 按钮 title 覆盖：9 个均有非空中文 title（长度 ≥8）", () => {
  const nav = headerNavHTML();
  const CJK = /[\u4e00-\u9fff]/;
  for (const key of ALL_KEYS) {
    // 先取按钮元素再抽 title——属性序无关（评审整改：原正则要求 data-tab 在
    // title 之前，属性重排会大声失败；改为按钮级匹配后仅要求同按钮内存在）
    const btn = nav.match(new RegExp('<button[^>]*data-tab="' + key + '"[^>]*>'));
    assert.ok(btn, "tab '" + key + "' 按钮应存在");
    const titleMatch = btn[0].match(/title="([^"]*)"/);
    assert.ok(titleMatch, "tab '" + key + "' 应带 title 属性");
    const title = titleMatch[1];
    assert.ok(title.length >= 8,
      "tab '" + key + "' 的 title 长度应 ≥8（防占位半句话，实际 " + title.length + "）");
    assert.ok(CJK.test(title), "tab '" + key + "' 的 title 应为中文说明");
  }
});

test("每个 tab 键有对应 section 容器（防死按钮，工单 beginner-guide/01 强化）", () => {
  for (const key of ALL_KEYS) {
    assert.equal(countOccurrences(html, '<section id="tab-' + key + '"'), 1,
      "tab '" + key + "' 应有恰好一个 section 容器（无异步加载的 tab 由通用切换器驱动）");
  }
});
