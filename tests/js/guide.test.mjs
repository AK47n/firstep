// guide.test.mjs — 新手指引教程页纯函数与静态标记契约（工单 beginner-guide/01
// 骨架 + 02 内容）：GUIDE_TABS / guidePanelFor / guideTabNext 单测，教程章节
// 数据结构与渲染（GUIDE_CHAPTERS / guideBlockHTML / guideChapterHTML）单测，
// 并读 index.html 钉住契约四联：按钮 data-guide-tab、面板 id guide-panel-*、
// 出现顺序、与 GUIDE_TABS 一一对应（防键四处漂移）。仿 fx/revise-tabs.test.mjs
// 与 nav-tabs-guard.test.mjs 先例。
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  GUIDE_TABS, GUIDE_CHAPTERS, guidePanelFor, guideTabNext,
  guideBlockHTML, guideChapterHTML, guideBlocksOf,
} from "../../src/contest_generator/static/js/fx/guide.js";

const html = readFileSync(
  new URL("../../src/contest_generator/static/index.html", import.meta.url),
  "utf8",
);

const NAV_TAB_KEYS = ["generate", "topic", "settings", "library", "reference", "pdf", "master", "changelog", "guide"];

function countOccurrences(text, needle) {
  return text.split(needle).length - 1;
}

test("GUIDE_TABS：恰为 4 个子页签，key 唯一、文案非空", () => {
  assert.equal(GUIDE_TABS.length, 4, "教程应为 4 个子页签（准备/做题主线/编译与上板/交付与收尾）");
  const keys = GUIDE_TABS.map((t) => t.key);
  assert.equal(new Set(keys).size, keys.length, "子页签 key 不得重复");
  for (const t of GUIDE_TABS) {
    assert.ok(t.key && t.label, "子页签应同时有 key 与 label：" + JSON.stringify(t));
  }
});

test("guidePanelFor：面板 id 契约（guide-panel-<key>）", () => {
  for (const t of GUIDE_TABS) {
    assert.equal(guidePanelFor(t.key), "guide-panel-" + t.key);
  }
});

test("guideTabNext：方向键循环（回绕）", () => {
  assert.equal(guideTabNext(0, 1, 4), 1);
  assert.equal(guideTabNext(3, 1, 4), 0, "末位 +1 应回绕到首位");
  assert.equal(guideTabNext(0, -1, 4), 3, "首位 -1 应回绕到末位");
  assert.equal(guideTabNext(1, -1, 4), 0);
  assert.equal(guideTabNext(0, 1, 0), -1, "count=0 应返回 -1");
  assert.equal(guideTabNext(2, 1, 4), 3);
});

test("HTML 契约：每个子页签恰有一个按钮与一个面板，顺序与 GUIDE_TABS 一致", () => {
  for (const t of GUIDE_TABS) {
    assert.equal(countOccurrences(html, 'data-guide-tab="' + t.key + '"'), 1,
      "子页签 '" + t.key + "' 的按钮应恰好出现一次");
    assert.equal(countOccurrences(html, 'id="' + guidePanelFor(t.key) + '"'), 1,
      "面板 '" + guidePanelFor(t.key) + "' 应恰好出现一次");
  }
  const order = GUIDE_TABS.map((t) => html.indexOf('data-guide-tab="' + t.key + '"'));
  assert.deepEqual([...order].sort((a, b) => a - b), order,
    "子页签按钮在 index.html 中的顺序应与 GUIDE_TABS 一致");
});

test("GUIDE_CHAPTERS：四章（准备 / 做题主线 / 编译与上板 / 交付与收尾）结构完备（title / intro / sections），键与 GUIDE_TABS 一一对应", () => {
  for (const t of GUIDE_TABS) {
    const ch = GUIDE_CHAPTERS[t.key];
    assert.ok(ch, "缺章 '" + t.key + "'");
    assert.ok(ch.title && ch.intro, "章 '" + t.key + "' 应有 title 与 intro");
    assert.ok(Array.isArray(ch.sections) && ch.sections.length >= 2,
      "章 '" + t.key + "' 应有至少 2 个小节");
    for (const s of ch.sections) {
      assert.ok(s.title, "小节缺标题：" + JSON.stringify(s));
      assert.ok(Array.isArray(s.blocks) && s.blocks.length >= 1, "小节缺块：" + s.title);
    }
  }
});

test("教程块：类型与字段合法（p/note/ul/ol/table/jump），jump tab ∈ 导航键", () => {
  for (const ch of Object.values(GUIDE_CHAPTERS)) {
    for (const b of guideBlocksOf(ch)) {
        switch (b.type) {
          case "p": assert.ok(typeof b.text === "string" && b.text.length > 0, "p 块缺 text：" + JSON.stringify(b)); break;
          case "note": assert.ok(typeof b.text === "string" && b.text.length > 0, "note 块缺 text"); break;
          case "ul": case "ol":
            assert.ok(Array.isArray(b.items) && b.items.length >= 1 && b.items.every((i) => typeof i === "string"), b.type + " 块 items 非法");
            break;
          case "table":
            assert.ok(Array.isArray(b.head) && b.head.length >= 1, "table 块缺 head");
            assert.ok(Array.isArray(b.rows) && b.rows.length >= 1, "table 块缺 rows");
            for (const r of b.rows) assert.equal(r.length, b.head.length, "table 行列宽度不一致");
            break;
          case "jump":
            assert.ok(typeof b.label === "string" && b.label.length > 0, "jump 块缺 label");
            assert.ok(NAV_TAB_KEYS.includes(b.tab), "jump tab 非法：" + JSON.stringify(b));
            break;
          default: assert.fail("未知块类型：" + b.type);
      }
    }
  }
});

test("guideBlocksOf：章内块扁平序列（空章/缺 sections 返回空数组）", () => {
  assert.equal(guideBlocksOf(GUIDE_CHAPTERS.prepare).length > 0, true, "prepare 应有块");
  assert.deepEqual(guideBlocksOf(undefined), [], "缺章应返回空数组");
  assert.deepEqual(guideBlocksOf({ title: "x" }), [], "无 sections 应返回空数组");
});

test("guideChapterHTML：渲染标题 / 表格头与行 / 跳转按钮 / 转义", () => {
  const htmlOut = guideChapterHTML(GUIDE_CHAPTERS.prepare);
  assert.ok(htmlOut.includes('<h3 class="guide-chapter-title">准备：装好工具、配好 key、挑块板子</h3>'),
    "应渲染章标题");
  assert.ok(htmlOut.includes("guide-table"), "应渲染表格");
  assert.ok(htmlOut.includes('data-jump-tab="settings"') && htmlOut.includes('data-jump-focus="set-api-key"'),
    "应渲染跳转按钮（data-jump-tab/focus）");
  assert.equal(guideChapterHTML(undefined), "", "缺章应返回空串（面板保留占位）");
  assert.equal(guideChapterHTML({ title: "x", sections: [] }).includes("<h3"), true, "最小章也应渲染标题");
});

test("guideBlockHTML：转义与未知类型兜底", () => {
  assert.equal(
    guideBlockHTML({ type: "p", text: '<b onclick="x">y</b>' }),
    "<p>&lt;b onclick=&quot;x&quot;&gt;y&lt;/b&gt;</p>",
  );
  assert.equal(guideBlockHTML({ type: "unknown" }), "", "未知块类型应渲染为空串");
  assert.ok(guideBlockHTML({ type: "jump", label: '去 "设置"', tab: "settings", focus: "set-api-key" })
    .includes('data-jump-tab="settings"'), "jump 块应带 data-jump-tab");
});
