// guide-refs.test.mjs — 新手教程内容守护（工单 beginner-guide/02）：
// 教程正文与界面事实的一致性命中钉住——12 步表逐行对应生成页卡标题、
// AI 列口径（本地/要 AI/不用）、准备章安装/配 key/平台事实齐全、
// 关键入口词、跳转按钮目标（tab ∈ 导航键、focus id 存在）。
// 仿 glossary-refs.test.mjs 先例。
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { GUIDE_CHAPTERS, guideBlocksOf } from "../../src/contest_generator/static/js/fx/guide.js";

const html = readFileSync(
  new URL("../../src/contest_generator/static/index.html", import.meta.url),
  "utf8",
);

const NAV_TAB_KEYS = ["generate", "topic", "settings", "library", "reference", "pdf", "master", "changelog", "guide"];

function allText(chapter) {
  return guideBlocksOf(chapter).map((b) => {
    if (b.type === "table") return b.head.concat(b.rows.flat()).join(" ");
    if (b.type === "ul" || b.type === "ol") return b.items.join(" ");
    return (b.text || b.label || "") + " ";
  }).join(" ");
}

function stepTable() {
  const sec = GUIDE_CHAPTERS.build.sections.find((s) => s.title.indexOf("12 步向导") === 0);
  const table = sec && sec.blocks.find((b) => b.type === "table");
  assert.ok(table && table.rows.length === 12, "应存在 12 行 12 步表");
  return table;
}

test("做题主线章：12 步表逐行与生成页卡标题对应", () => {
  const table = stepTable();
  for (let n = 1; n <= 12; n++) {
    const m = html.match(new RegExp('<span class="step-no">' + n + '<\\/span>([^<]+)<\\/h2>'));
    assert.ok(m, "index.html 应含第 " + n + " 步卡标题");
    const stepName = m[1].split("：")[0].split("（")[0].trim();
    const rowBase = table.rows[n - 1][0].replace(/^\d+\s*/, "");
    assert.ok(stepName === rowBase || stepName.includes(rowBase),
      "12 步表第 " + n + " 行应含卡标题「" + stepName + "」（实际「" + table.rows[n - 1][0] + "」）");
  }
});

test("12 步表 AI 列口径：关键行钉住", () => {
  const table = stepTable();
  const ai = (n) => table.rows[n - 1][2];
  assert.ok(ai(2).includes("本地"), "第 2 步（赛题预读）应说明可本地离线，实际：" + ai(2));
  assert.ok(ai(4).includes("本地"), "第 4 步（参考资料）应说明摘要可本地，实际：" + ai(4));
  assert.ok(ai(5).includes("要 AI") && !ai(5).includes("不用"), "第 5 步（AI 推荐）应标要 AI，实际：" + ai(5));
  assert.ok(ai(8).includes("要 AI"), "第 8 步（骨架）应标要 AI，实际：" + ai(8));
  assert.ok(ai(9).includes("不用"), "第 9 步（生成）应标不用，实际：" + ai(9));
  assert.ok(ai(10).includes("要 AI") && ai(10).includes("不用"), "第 10 步（修复中心）应同时说明，实际：" + ai(10));
  assert.ok(ai(12).includes("不用"), "第 12 步（交接提示词）应标不用，实际：" + ai(12));
});

test("准备章：安装 / 配 key / 平台事实齐全", () => {
  const t = allText(GUIDE_CHAPTERS.prepare);
  for (const w of ["install.bat", "start-app.vbs", "127.0.0.1:8000", "Keil5", "CCS", "一键体检", "API key"]) {
    assert.ok(t.includes(w), "准备章应提到「" + w + "」");
  }
  const platTable = GUIDE_CHAPTERS.prepare.sections[0].blocks.find((b) => b.type === "table");
  assert.ok(platTable && platTable.rows.length === 2, "平台表应有 2 行（stm32 / mspm0）");
});

test("做题主线章：关键入口词在场（任务推进 / 和 AI 商量 / 新手词表 / 交接提示词 / 赛题库）", () => {
  const t = allText(GUIDE_CHAPTERS.build);
  for (const word of ["任务推进", "和 AI 商量", "新手词表", "交接提示词", "赛题库", "设置"]) {
    assert.ok(t.includes(word), "做题主线章应提到「" + word + "」");
  }
});

test("AI 边界口径：本地 Ollama 可离线 / 要 AI 标签 / 无 key 行为", () => {
  const t = allText(GUIDE_CHAPTERS.build);
  assert.ok(t.includes("本地 Ollama"), "应说明可配本地模型离线（llm.py LOCAL_LLM_METHODS 口径）");
  assert.ok(t.includes("没有 key"), "应说明无 key 时 AI 步骤会提示先配置");
});

test("跳转按钮目标合法：tab ∈ 导航键、focus id 在 index.html 存在", () => {
  const jumps = [];
  for (const ch of Object.values(GUIDE_CHAPTERS)) {
    jumps.push(...guideBlocksOf(ch).filter((b) => b.type === "jump"));
  }
  assert.ok(jumps.length >= 3, "应有至少 3 个跳转按钮（实际 " + jumps.length + "）");
  for (const j of jumps) {
    assert.ok(NAV_TAB_KEYS.includes(j.tab), "jump tab 非法：" + j.label + "→" + j.tab);
    if (j.focus) {
      assert.ok(html.includes('id="' + j.focus + '"'),
        "jump focus「" + j.focus + "」在 index.html 不存在（" + j.label + "）");
    }
  }
});
