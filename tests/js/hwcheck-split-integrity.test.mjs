// hwcheck-split-integrity.test.mjs — **搬迁完整性自检**（工单 hwcheck-hygiene/09）。
//
// ## 这条判据要挡的是什么
//
// 09 号单把 1380 行的 `fx/hwcheck.js`（78 个导出 ＋ 4 个未导出的私有件 ＋ 1 条 window 桥）
// 按职责整段搬进六件。这类改动的失败方式不是"报错"，
// 而是**静默少东西**：漏搬一个导出、搬的时候手抖改了一个字、某件少 import 了一个兄弟函数、
// 桥条目落了一件没发。四种都不会让整页崩（前三种在真浏览器里照样跑，因为 window 桥兜住了），
// 所以"门禁全绿"证明不了搬全了——它只能证明**没搬坏**。
//
// 于是这里按**搬前快照**逐名逐字对账。快照是搬那一刻的逐字节副本
// （`.scratch/hwcheck-hygiene/fx-hwcheck-before-split.js`，由 `apply-09-split.py` 在
// 第一次 `--write` 时落盘、之后不再覆盖）。
//
// ## 为什么另一侧不是"旧文件"
//
// 10 号单会把旧文件与 barrel 一起删掉，而这条自检**必须在那之后仍然可跑**
// （09 的验收标准明写）。所以两侧都是磁盘上的**文件**、与旧路径存不存在无关：
//   搬前 = 快照；搬后 = 六件。
//
// ## 四条断言
//
//   ① **导出名集合相等**：快照的导出清单 ＝ 六件并集（逐名，多一个少一个都报）；
//   ② **声明单元逐字**：每个导出的「紧邻上方注释块 ＋ 声明本体」规范化空白后逐字相同
//      ——搬迁允许的变化只有 import/export 语句与文件头说明，函数体与它自己的注释
//      一个字都不许动；
//   ③ **window 桥并集相等**，且 **barrel 自己一个都不发布**（桥按声明的归属拆到六件里，
//      页面内联脚本与浏览器探针仍取到同样的全局名）；
//   ④ **跨件调用必须有 import**：某件正文里调用了**兄弟件声明的名字**，它就必须在本件
//      import 或声明过。判据本体（`boot-contract.mjs` 判据 ⑧）只覆盖"挂在 window 桥上的
//      名字"，而桥只发 77 个名字、导出有 78 个（`hwcheckPinFixHTML` /
//      `hwcheckPinCapacityNoteHTML` 不在桥上）——这条把同一件事扩到**全部声明**。
//      实测价值：09 第一次落盘时正是它（与判据 ⑧ 一起）抓出 project 少 import
//      `hwcheckDeviceSlugs`——漏掉它的后果是"点了生成就 ReferenceError"。
//
// ## 抽取器不静默失效（"那种绿比红更坏"）
//
// 断言为空的判据必须能报：文件头几条自检往真源码里注入四种破坏（摘一个导出 / 改一个字 /
// 摘一条桥 / 摘一条 import），每条都必须被**对号**报出来；另有一条下限体检
// （快照的导出数、六件的声明数），目录搬走或抽取器失效时当场红。
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import {
  maskCommentsAndStrings, maskNonCode, parseModuleExports, windowBridgeNames, callPositionNames,
} from "./boot-contract.mjs";

const FX_DIR = fileURLToPath(new URL("../../src/contest_generator/static/js/fx/", import.meta.url));
const SNAPSHOT = fileURLToPath(
  new URL("../../.scratch/hwcheck-hygiene/fx-hwcheck-before-split.js", import.meta.url));

/** 六件（**不含** barrel）：搬迁的产物面。顺序 = 职责顺序（快照里的声明顺序）。 */
const MODULES = [
  "hwcheck-state.js", "hwcheck-project.js", "hwcheck-wiring.js",
  "hwcheck-plan.js", "hwcheck-triage.js", "hwcheck-handoff.js",
];
const BARREL = "hwcheck.js";
const BEFORE = "（搬前快照）";

// ---------------------------------------------------------------------------
// 抽取器：声明单元 / 桥 / 声明名 / 调用位
// ---------------------------------------------------------------------------

// 顶层声明（**含未导出的私有件**）：票面说的是"函数体逐字"，而文件里除了 78 个导出，
// 还有 4 个私有件住在段落之间的"间隙"里（`hwcheckSameExclusiveGroup` / `hwcheckRoleLabeler` /
// `HWCHECK_ORDER_DESC_CHARS` / `HWCHECK_VERDICT_FALLBACK`）——它们同样必须逐字搬走
//（Spec 轴评审实测：只判导出的话，这四件没有任何判据看着）。所以判据面 = **全部顶层声明**，
// 表头的"导出名集合"那一半仍只认导出。
const DECL_RE = /^(?:export )?(function|const) ([A-Za-z_$][\w$]*)/gm;

/** 顶层声明名（含未导出的私有件）：跨件调用判据要看到它们。 */
function declaredNames(text) {
  const masked = maskCommentsAndStrings(text);
  const out = new Set();
  for (const m of masked.matchAll(
    /(?:^|\n)[ \t]*(?:export\s+)?(?:async\s+)?(?:function|const|let|var|class)\s+([A-Za-z_$][\w$]*)/g)) {
    out.add(m[1]);
  }
  return out;
}

/**
 * 声明名 → 声明单元原文（**紧邻上方**的连续 `//` 注释块 ＋ 声明本体）。
 * 中间隔空行的注释不算（那是"间隙"里的段落表头，如 `// ==== 工单 … ====`）。
 */
function unitsOf(text) {
  const masked = maskCommentsAndStrings(text);
  const out = new Map();
  const re = new RegExp(DECL_RE.source, "gm");
  let m;
  while ((m = re.exec(masked)) !== null) {
    const name = m[2];
    let end;
    if (m[1] === "function") {
      // 函数体的 `{` = 圆括号深度 0 处的第一个 `{`（缺省参数里的对象字面量不算）
      let depth = 0;
      let open = -1;
      for (let i = m.index + m[0].length; i < masked.length; i++) {
        if (masked[i] === "(") depth++;
        else if (masked[i] === ")") depth--;
        else if (masked[i] === "{" && depth === 0) { open = i; break; }
      }
      assert.ok(open >= 0, `${name}：找不到函数体`);
      depth = 0;
      for (let i = open; i < masked.length; i++) {
        if (masked[i] === "{") depth++;
        else if (masked[i] === "}" && --depth === 0) { end = i + 1; break; }
      }
    } else {
      end = masked.indexOf(";", m.index + m[0].length) + 1;
    }
    assert.ok(end > 0, `${name}：找不到声明收尾`);
    // 紧邻上方的连续 `//` 注释行（中间隔空行的不算——那是"间隙"里的段落表头）
    const headLines = text.slice(0, m.index).split("\n");
    let i = headLines.length - 2;
    while (i >= 0 && headLines[i].trimStart().startsWith("//")) i--;
    const start = headLines.slice(0, i + 1).reduce((n, line) => n + line.length + 1, 0);
    out.set(name, text.slice(start, end));
  }
  return out;
}

const norm = (text) => text.replace(/\s+/g, " ").trim();

// ---------------------------------------------------------------------------
// 判据本体：文件表进，问题清单出
// ---------------------------------------------------------------------------

/** files = Map<名字, 源码>（含 `BEFORE` 那一份快照）。→ [{ code, detail }]；空 = 搬迁完整。 */
function auditProblems(files) {
  const problems = [];
  const before = files.get(BEFORE);
  const after = MODULES.map((key) => ({ key, text: files.get(key) }));

  // ① 导出名集合
  const beforeNames = [...parseModuleExports(before)].sort();
  const afterNames = [...new Set(after.flatMap((m) => [...parseModuleExports(m.text)]))].sort();
  const lost = beforeNames.filter((n) => !afterNames.includes(n));
  const added = afterNames.filter((n) => !beforeNames.includes(n));
  if (lost.length) problems.push({ code: "①", detail: `搬前有、六件里没有：${lost.join(", ")}` });
  if (added.length) problems.push({ code: "①", detail: `六件里有、搬前没有：${added.join(", ")}` });

  // ② 声明单元逐字（含紧邻上方的注释块）——**导出与私有件一起判**（私有件住在段落间隙里，
  //    没有导出名，① 看不见它们）
  const beforeUnits = unitsOf(before);
  const afterUnits = new Map();
  for (const m of after) {
    for (const [name, body] of unitsOf(m.text)) {
      if (afterUnits.has(name)) {
        problems.push({ code: "②", detail: `${name} 在六件里出现了两次` });
      }
      afterUnits.set(name, { key: m.key, body });
    }
  }
  for (const [name, want] of beforeUnits) {
    const got = afterUnits.get(name);
    if (!got) {
      // 导出缺失由 ① 报出（口径是"导出名集合"）；这里只说私有件
      if (!beforeNames.includes(name)) {
        problems.push({ code: "②", detail: `私有件 ${name} 没有搬进六件` });
      }
      continue;
    }
    if (norm(want) !== norm(got.body)) {
      problems.push({
        code: "②",
        detail: `${name}（${got.key}）的声明单元与搬前不是逐字相同`,
      });
    }
  }

  // ③ window 桥：并集相等，且 barrel 一个都不发布
  const bridgeBefore = [...windowBridgeNames(before)].sort();
  const bridgeAfter = [...new Set(after.flatMap((m) => [...windowBridgeNames(m.text)]))].sort();
  const bridgeBarrel = [...windowBridgeNames(files.get(BARREL))];
  const bridgeLost = bridgeBefore.filter((n) => !bridgeAfter.includes(n));
  const bridgeAdded = bridgeAfter.filter((n) => !bridgeBefore.includes(n));
  if (bridgeLost.length) problems.push({ code: "③", detail: `桥丢了这些名字：${bridgeLost.join(", ")}` });
  if (bridgeAdded.length) problems.push({ code: "③", detail: `桥多出这些名字：${bridgeAdded.join(", ")}` });
  if (bridgeBarrel.length) {
    problems.push({ code: "③", detail: `barrel 自己发布了桥条目（应归六件）：${bridgeBarrel.join(", ")}` });
  }

  // ④ 跨件调用必须有 import / 本件声明
  const owner = new Map();                               // 声明名 → 它所在的件
  for (const m of after) for (const name of declaredNames(m.text)) owner.set(name, m.key);
  for (const m of after) {
    const locals = new Set(
      [...maskedImportLocals(m.text)].concat([...declaredNames(m.text)]));
    for (const { name } of callPositionNames(maskNonCode(m.text))) {
      const home = owner.get(name);
      if (home === undefined || home === m.key || locals.has(name)) continue;
      problems.push({
        code: "④",
        detail: `${m.key} 调用了 ${name}（声明在 ${home}）却没 import`,
      });
    }
  }
  return problems;
}

/** 模块 import 的本地名（`import { a as b }` 收 b）。 */
function maskedImportLocals(text) {
  const out = [];
  const masked = maskCommentsAndStrings(text);
  for (const m of masked.matchAll(/(?:^|\n)[ \t]*import\s*\{([^}]*)\}/g)) {
    for (const part of m[1].split(",")) {
      const clean = part.trim();
      if (!clean) continue;
      out.push(clean.split(/\s+as\s+/).pop().trim());
    }
  }
  return out;
}

// ---------------------------------------------------------------------------
// 取数面
// ---------------------------------------------------------------------------

function readAll() {
  const files = new Map();
  files.set(BEFORE, readFileSync(SNAPSHOT, "utf8"));
  for (const name of [BARREL, ...MODULES]) {
    files.set(name, readFileSync(FX_DIR + name, "utf8"));
  }
  return files;
}

const withPatch = (files, key, fn) =>
  new Map([...files].map(([k, text]) => [k, k === key ? fn(text) : text]));

const FILES = readAll();
const REPORT = (files) => auditProblems(files).map((p) => `${p.code} ${p.detail}`);

// ---------------------------------------------------------------------------
// 用例
// ---------------------------------------------------------------------------

test("取数面体检：快照与六件都读到了，且判据面够大（那种绿比红更坏）", () => {
  const names = [...parseModuleExports(FILES.get(BEFORE))];
  assert.ok(names.length >= 70, `快照的导出只抽到 ${names.length} 个（下限 70）——抽取器失效？`);
  const units = unitsOf(FILES.get(BEFORE));
  assert.ok(units.size > names.length,
    `快照的声明单元只抽到 ${units.size} 个、导出 ${names.length} 个 —— `
    + "私有件（未导出的顶层声明）没被判据面覆盖，② 会漏一整类");
  for (const key of [BARREL, ...MODULES]) {
    assert.ok(FILES.get(key).length > 200, `${key} 读出来只有 ${FILES.get(key).length} 字节`);
  }
  const bridge = [...windowBridgeNames(FILES.get(BEFORE))];
  assert.ok(bridge.length >= 60, `快照的桥只抽到 ${bridge.length} 个名字（下限 60）`);
});

test("搬迁完整：① 导出名集合 ② 声明单元逐字 ③ 桥并集 ④ 跨件 import —— 零问题", () => {
  const report = REPORT(FILES);
  assert.deepEqual(report, [],
    "搬迁与搬前快照对不上（每一条都是「搬的时候丢了东西」的形态）：\n  " + report.join("\n  "));
});

test("① 正向对照：摘掉一个导出必须报出（判据不是靠「两边都空」绿的）", () => {
  const patched = withPatch(FILES, "hwcheck-triage.js",
    (t) => t.replace("export function hwcheckAdviceHTML(", "function hwcheckAdviceHTML("));
  assert.ok(patched.get("hwcheck-triage.js").includes("\nfunction hwcheckAdviceHTML("),
    "注入没落上（锚点变了？）—— 这条自检会静默空转");
  const hits = REPORT(patched).filter((line) => line.startsWith("①") && line.includes("hwcheckAdviceHTML"));
  assert.equal(hits.length, 1, `摘掉导出没被报出：${JSON.stringify(REPORT(patched))}`);
});

test("② 正向对照：函数体里改一个字必须报出", () => {
  const anchor = "return { ...state, platform: target.id };";
  const patched = withPatch(FILES, "hwcheck-state.js", (t) => {
    assert.ok(t.includes(anchor), `锚点变了（${anchor}）—— 这条自检会静默空转`);
    return t.replace(anchor, "return { ...state, platform: target.id + 1 };");
  });
  const hits = REPORT(patched).filter((line) => line.startsWith("②") && line.includes("hwcheckSelectPlatform"));
  assert.equal(hits.length, 1, `改了函数体没被报出：${JSON.stringify(REPORT(patched))}`);
});

test("② 正向对照：改**私有件**一个字必须报出（只判导出的话这一整类没人看着）", () => {
  const anchor = "const HWCHECK_ORDER_DESC_CHARS = 60;";
  const patched = withPatch(FILES, "hwcheck-wiring.js", (t) => {
    assert.ok(t.includes(anchor), `锚点变了（${anchor}）—— 这条自检会静默空转`);
    return t.replace(anchor, "const HWCHECK_ORDER_DESC_CHARS = 61;");
  });
  const hits = REPORT(patched).filter((line) => line.startsWith("②") && line.includes("HWCHECK_ORDER_DESC_CHARS"));
  assert.equal(hits.length, 1, `改了私有件没被报出：${JSON.stringify(REPORT(patched))}`);
});

test("③ 正向对照：摘掉一条桥必须报出；barrel 自己发布桥也要报出", () => {
  const drop = withPatch(FILES, "hwcheck-plan.js",
    (t) => t.replace("hwcheckConsoleState, hwcheckConsoleHTML, hwcheckConsoleNoteHTML,",
      "hwcheckConsoleState, hwcheckConsoleNoteHTML,"));
  assert.ok(!drop.get("hwcheck-plan.js").includes("hwcheckConsoleHTML,"),
    "注入没落上（锚点变了？）—— 这条自检会静默空转");
  assert.ok(REPORT(drop).some((line) => line.startsWith("③") && line.includes("hwcheckConsoleHTML")),
    `摘掉桥条目没被报出：${JSON.stringify(REPORT(drop))}`);
  const barrelBridge = withPatch(FILES, BARREL,
    (t) => t + '\nif (typeof window !== "undefined") { Object.assign(window, { hwcheckHintHTML }); }\n');
  assert.ok(REPORT(barrelBridge).some((line) => line.startsWith("③") && line.includes("barrel")),
    `barrel 发布桥条目没被报出：${JSON.stringify(REPORT(barrelBridge))}`);
});

test("④ 正向对照：摘掉一条跨件 import 必须报出（09 实测抓到过的那个形态）", () => {
  const anchor = "import { hwcheckHintHTML, hwcheckDeviceSlugs } from \"./hwcheck-state.js\";";
  const patched = withPatch(FILES, "hwcheck-project.js", (t) => {
    assert.ok(t.includes(anchor), `锚点变了（${anchor}）—— 这条自检会静默空转`);
    return t.replace(anchor, "import { hwcheckHintHTML } from \"./hwcheck-state.js\";");
  });
  const hits = REPORT(patched).filter((line) => line.startsWith("④") && line.includes("hwcheckDeviceSlugs"));
  assert.equal(hits.length, 1, `摘掉跨件 import 没被报出：${JSON.stringify(REPORT(patched))}`);
});
