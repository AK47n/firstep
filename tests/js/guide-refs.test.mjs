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

const flashPy = readFileSync(
  new URL("../../src/contest_generator/flash.py", import.meta.url),
  "utf8",
);

/** 从板卡 JSON 取出「SWD 调试」条目占用的引脚（守卫与 boards/*.json 同源，
 * 教程正文与板定义漂移即失败——评审整改：由字面自检改为单源派生）。 */
function swdPins(boardPath) {
  const board = JSON.parse(readFileSync(new URL(boardPath, import.meta.url), "utf8"));
  const pool = [...(board.fixed || []), ...(board.features || [])];
  const swd = pool.find((f) => f.name === "SWD 调试");
  assert.ok(swd, "板卡定义应含「SWD 调试」条目：" + boardPath);
  return swd.occupies;
}

const NAV_TAB_KEYS = ["generate", "topic", "code", "settings", "library", "reference", "pdf", "master", "changelog", "guide"];

function sectionByTitle(chapter, titlePrefix) {
  return chapter.sections.find((s) => s.title.indexOf(titlePrefix) === 0);
}

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
  const platTable = sectionByTitle(GUIDE_CHAPTERS.prepare, "开始前，四样东西")
    .blocks.find((b) => b.type === "table");
  assert.ok(platTable && platTable.rows.length === 2, "平台表应有 2 行（stm32 / mspm0）");
});

test("准备章：库目录自动指向 / 下载入口 / 浏览器 / 一键补齐口径", () => {
  const t = allText(GUIDE_CHAPTERS.prepare);
  for (const w of ["库目录自动指向", "设置 → 库目录", "library\\modules", "library\\masters", "只带路", "32KB", "Edge", "stsw-link009.html", "MSPM0-SDK"]) {
    assert.ok(t.includes(w), "准备章应提到「" + w + "」");
  }
  // 一键补齐：只带路、不承诺下载（事实口径，偏差即失败）
  const ovNote = GUIDE_CHAPTERS.prepare.sections
    .flatMap((s) => s.blocks)
    .find((b) => b.type === "note" && (b.label || "").includes("一键补齐"));
  assert.ok(ovNote, "准备章应有「就绪总览与一键补齐」提醒");
  assert.ok(
    !ovNote.text.includes("下载参考文件与模块库"),
    "一键补齐提醒不应声称能下载参考文件与模块库（实际：" + ovNote.text + "）",
  );
  // 下载表：4 行官方入口
  const dlTable = sectionByTitle(GUIDE_CHAPTERS.prepare, "什么是 IDE")
    .blocks.find((b) => b.type === "table");
  assert.ok(dlTable && dlTable.rows.length === 4, "下载表应有 4 行（MDK / CCS / MSPM0 SDK / ST-Link 驱动）");
  const joined = dlTable.rows.flat().join(" ");
  for (const d of ["keil.com/download/product/", "keil.com/limits", "ti.com/tool/CCSTUDIO", "ti.com/tool/MSPM0-SDK", "https://www.st.com/en/development-tools/stsw-link009.html"]) {
    assert.ok(joined.includes(d), "下载表应含官方入口「" + d + "」");
  }
});

test("做题主线章：关键入口词在场（任务推进 / 和 AI 商量 / 新手词表 / 交接提示词 / 赛题库）", () => {
  const t = allText(GUIDE_CHAPTERS.build);
  for (const word of ["任务推进", "和 AI 商量", "新手词表", "交接提示词", "赛题库", "设置"]) {
    assert.ok(t.includes(word), "做题主线章应提到「" + word + "」");
  }
});

test("做题主线章：评分点与参数速调讲解在场", () => {
  const t = allText(GUIDE_CHAPTERS.build);
  for (const word of ["评分点覆盖总览", "评分点核对", "参数速调", "问 AI：我该调哪个参数", "恢复旧值"]) {
    assert.ok(t.includes(word), "做题主线章应提到「" + word + "」");
  }
});

test("AI 边界口径：本地 Ollama 可离线 / 要 AI 标签 / 无 key 行为", () => {
  const t = allText(GUIDE_CHAPTERS.build);
  assert.ok(t.includes("本地 Ollama"), "应说明可配本地模型离线（llm.py LOCAL_LLM_METHODS 口径）");
  assert.ok(t.includes("没有 key"), "应说明无 key 时 AI 步骤会提示先配置");
});

test("编译与上板章：接线 / 烧录事实齐全且与单源一致（boards/*.json、flash.py）", () => {
  const t = allText(GUIDE_CHAPTERS.compile);
  for (const w of ["ST-Link", "SWDIO", "SWCLK", "3V3", "DSLite", "XDS110", "烧录到板子", "一键体检"]) {
    assert.ok(t.includes(w), "编译与上板章应提到「" + w + "」");
  }
  // 烧录产物：教程与 flash.py 的 artifact 赋值行同源
  const stm32Hex = "user/Objects/*.hex";
  const mspm0Out = "Debug/*.out";
  assert.ok(flashPy.includes('"' + stm32Hex + '" if platform == PLATFORM_STM32 else "' + mspm0Out + '"'),
    "flash.py 的 artifact 赋值行应与教程一致（源已漂移？）");
  assert.ok(t.includes(stm32Hex) && t.includes(mspm0Out), "教程应含双方产物路径（" + stm32Hex + " / " + mspm0Out + "）");
  // 接线：SWD 引脚从板卡 JSON 派生（stm32 与 mspm0 两行）
  const wireTable = sectionByTitle(GUIDE_CHAPTERS.compile, "第一次接线").blocks.find((b) => b.type === "table");
  assert.ok(wireTable && wireTable.rows.length === 2, "接线表应有 2 行（stm32 / mspm0）");
  const swdStm32 = swdPins("../../src/contest_generator/boards/stm32-min-system.json");
  const swdMspm0 = swdPins("../../src/contest_generator/boards/mspm0-dimx.json");
  const rowStm32 = wireTable.rows[0].join(" ");
  const rowMspm0 = wireTable.rows[1].join(" ");
  assert.ok(rowStm32.includes(swdStm32[0]) && rowStm32.includes(swdStm32[1]),
    "stm32 行应含板卡 SWD 占用 " + swdStm32.join("/") + "（实际：" + rowStm32 + "）");
  assert.ok(rowMspm0.includes(swdMspm0[0]) && rowMspm0.includes(swdMspm0[1]),
    "mspm0 行应含板卡 SWD 占用 " + swdMspm0.join("/") + "（实际：" + rowMspm0 + "）");
});

test("编译与上板章：常见报错速查表在场且行目齐全", () => {
  const sec = GUIDE_CHAPTERS.compile.sections.find((s) => s.title.indexOf("常见报错速查") === 0);
  assert.ok(sec, "编译章应有「常见报错速查」小节");
  const table = sec.blocks.find((b) => b.type === "table");
  assert.ok(table && table.rows.length >= 5,
    "速查表应至少 5 行（实际 " + (table ? table.rows.length : 0) + "）");
  const joined = table.rows.flat().join(" ");
  for (const w of ["180s", "DSLite", "OpenOCD", "st-flash", "母版未导入", "端口 8000", "未找到固件产物"]) {
    assert.ok(joined.includes(w), "速查表应含「" + w + "」");
  }
});

test("交付与收尾章：交付物 / 交接提示词 / 收尾事实齐全", () => {
  const t = allText(GUIDE_CHAPTERS.deliver);
  for (const w of ["设计报告草稿", "演示脚本", "交付检查", "一键打包", "打开工程", "交接提示词", "stop-firstep.bat", "赛题库", "最近生成", "评分点核对"]) {
    assert.ok(t.includes(w), "交付与收尾章应提到「" + w + "」");
  }
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
