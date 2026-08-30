// tests/js/library-polish.test.mjs — 库页面小修（工单 ux-walkthrough-02/22）：
// ①参考/PDF 默认「最近更新」降序（ui 状态 + HTML select selected + 方向钮文案）；
// ②赛题/PDF 读取失败清加载占位、同位置错误空态；③赛题库加载占位延迟 150ms；
// ④设置页库目录卡：5 目录（模块/母版可编辑 + 赛题/参考/PDF 只读派生 span +
// 联动说明）、settings.js 保存前确认联动。静态/源码守卫式断言。
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const indexHtml = readFileSync(
  new URL("../../src/contest_generator/static/index.html", import.meta.url),
  "utf8",
);
const referenceUi = readFileSync(
  new URL("../../src/contest_generator/static/js/ui/reference.js", import.meta.url),
  "utf8",
);
const pdfUi = readFileSync(
  new URL("../../src/contest_generator/static/js/ui/pdf.js", import.meta.url),
  "utf8",
);
const topicUi = readFileSync(
  new URL("../../src/contest_generator/static/js/ui/topic.js", import.meta.url),
  "utf8",
);
const settingsUi = readFileSync(
  new URL("../../src/contest_generator/static/js/ui/settings.js", import.meta.url),
  "utf8",
);

test("① 参考/PDF 默认排序 = 最近更新降序（ui 状态 + select selected + 方向钮文案）", () => {
  assert.match(referenceUi, /sortBy: "mtime", sortDir: "desc"/, "参考库默认 mtime desc");
  assert.match(pdfUi, /sortBy: "mtime", sortDir: "desc"/, "PDF 库默认 mtime desc");
  assert.match(indexHtml, /<option value="mtime" selected>按最近更新（默认）<\/option>/,
    "参考库排序下拉默认选中最近更新");
  assert.match(indexHtml, /<option value="mtime" selected>按修改时间（默认）<\/option>/,
    "PDF 库排序下拉默认选中修改时间");
  assert.match(indexHtml, /id="ref-sort-dir">↓ 降序（默认）<\/button>/);
  assert.match(indexHtml, /id="pdf-sort-dir">↓ 降序（默认）<\/button>/);
});

test("② 赛题/PDF 读取失败：清空加载占位并同位置显示错误空态", () => {
  assert.match(topicUi, /赛题库读取失败/, "loadTopics catch 应写错误空态");
  assert.match(topicUi, /重新点击「赛题库」页签重试/, "应给重试指引");
  assert.match(pdfUi, /PDF 资料库读取失败/, "loadPdfs catch 应写错误空态");
  assert.match(pdfUi, /点「刷新」重试/, "PDF 有刷新按钮可重试");
  // 失败路径不再依赖 topic-browse-msg 裸抛（旧实现）——错误就地显示
  assert.match(topicUi, /\$\("topic-browse-msg"\)\.textContent = "";/, "错误路径清空旧 msg");
});

test("③ 赛题库加载占位延迟 150ms（本地快响应不闪加载态）", () => {
  assert.match(topicUi, /setTimeout\(\(\) => \{ if \(topicLoading\) renderTopics\(\); \}, 150\)/,
    "占位应在 150ms 后才渲染");
  assert.match(topicUi, /clearTimeout\(topicLoadTimer\)/, "完成/失败都应清定时器");
});

test("④ 设置页库目录卡：5 目录（2 可编辑 + 3 只读派生 span + 联动说明）", () => {
  assert.match(indexHtml, /模块库 \/ 母版库（可编辑）/, "库目录卡分区标题");
  assert.match(indexHtml, /派生目录（只读，跟随模块库目录）/, "派生分区标题");
  for (const id of ["set-lib-dir-topic", "set-lib-dir-reference", "set-lib-dir-pdf"]) {
    assert.ok(indexHtml.includes('id="' + id + '"'), "应含只读 span #" + id);
  }
  assert.match(indexHtml, /改模块库目录会连带改变它们/, "联动说明文案");
  assert.match(settingsUi, /修改模块库目录？/, "settings.js 应弹确认");
  assert.match(settingsUi, /赛题库 \/ 参考文件库 \/ PDF 资料库目录随模块库目录联动/,
    "确认文案应点明联动");
  assert.match(settingsUi, /set-lib-dir-topic/, "探测回显应写三个派生 span");
});
