// hwcheck-split-integrity.test.mjs — 本批**两次拆分的搬迁完整性自检**
// （工单 hwcheck-hygiene/09-10 拆 fx、11 拆 ui；这是本批唯一为拆分新造的判据）。
//
// 第一部分：`fx/hwcheck.js`（1380 行）按职责拆成六件（09 搬、10 迁消费者并删 barrel）。
// 第二部分：`ui/hwcheck.js`（1401 行）按职责拆成四件（11）。两半各读**自己那份搬前快照**，
// 判据面互相独立（见文件尾那一段的分工说明）。
//
// ## 这条判据要挡的是什么
//
// 09 号单把 1380 行的 `fx/hwcheck.js`（78 个导出 ＋ 4 个未导出的私有件 ＋ 1 条 window 桥）
// 按职责整段搬进六件；10 号单把消费者改指六件、删掉那个过渡态 barrel。这类改动的失败方式
// 不是"报错"，而是**静默少东西**：漏搬一个导出、搬的时候手抖改了一个字、某件少 import 了
// 一个兄弟函数、桥条目落了一件没发。四种都不会让整页崩（前三种在真浏览器里照样跑，因为
// window 桥兜住了），所以"门禁全绿"证明不了搬全了——它只能证明**没搬坏**。
//
// 于是这里按**搬前快照**逐名逐字对账。快照是搬那一刻的逐字节副本
// （`.scratch/hwcheck-hygiene/fx-hwcheck-before-split.js`，由 `apply-09-split.py` 在
// 第一次 `--write` 时落盘、之后不再覆盖；与当时 HEAD 那一份逐字节相同）。
//
// ## 为什么另一侧不是"旧文件"
//
// 10 号单已经把旧文件与 barrel 一起删了，而这条自检**必须在那之后仍然可跑**（09 的验收标准
// 明写）。所以两侧都是磁盘上的**文件**、与旧路径存不存在无关：搬前 = 快照；搬后 = 六件。
//
// ## 四条断言
//
//   ① **导出名集合相等**：快照的导出清单 ＝ 六件并集（逐名，多一个少一个都报）；
//   ② **声明单元逐字**：**每个顶层声明**（导出 ＋ 4 个未导出的私有件）的「紧邻上方注释块 ＋
//      声明本体」规范化空白后逐字相同——搬迁允许的变化只有 import/export 语句与文件头说明，
//      函数体与它自己的注释一个字都不许动；
//   ③ **window 桥并集相等**（桥按声明的归属拆到六件里，页面内联脚本与浏览器探针仍取到同样的
//      全局名）；另：**过渡态 barrel 不许回来**（`fx/hwcheck.js` 必须已不存在）；
//   ④ **跨件调用必须有 import**：某件正文里调用了**兄弟件声明的名字**，它就必须在本件
//      import 或声明过。判据本体（`boot-contract.mjs` 判据 ⑧）只覆盖"挂在 window 桥上的
//      名字"，而桥只发 77 个名字、导出有 78 个（`hwcheckPinFixHTML` /
//      `hwcheckPinCapacityNoteHTML` 不在桥上）——这条把同一件事扩到**全部声明**。
//      实测价值：09 第一次落盘时正是它（与判据 ⑧ 一起）抓出 project 少 import
//      `hwcheckDeviceSlugs`——漏掉它的后果是"点了生成就 ReferenceError"。
//
// ## 抽取器不静默失效（"那种绿比红更坏"）
//
// 断言为空的判据必须能报：几条自检往真源码里注入五种破坏（摘一个导出 / 改函数体一个字 /
// 改**私有件**一个字 / 摘一条桥 / 摘一条 import），每条都必须被**对号**报出来；另有一条
// 下限体检（快照的导出数与声明单元数、六件的字节数），目录搬走或抽取器失效时当场红。
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, existsSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import {
  maskCommentsAndStrings, maskNonCode, parseModuleExports, parseModuleImports,
  windowBridgeNames, callPositionNames,
} from "./boot-contract.mjs";

const FX_DIR = fileURLToPath(new URL("../../src/contest_generator/static/js/fx/", import.meta.url));
const SNAPSHOT = fileURLToPath(
  new URL("../../.scratch/hwcheck-hygiene/fx-hwcheck-before-split.js", import.meta.url));
/** 过渡态 barrel 的路径（09 留、10 删）：它出现在磁盘上就是"过渡态没收拾干净"。 */
const BARREL = FX_DIR + "hwcheck.js";

/** 六件：搬迁的产物面。顺序 = 职责顺序（快照里的声明顺序）。 */
const MODULES = [
  "hwcheck-state.js", "hwcheck-project.js", "hwcheck-wiring.js",
  "hwcheck-plan.js", "hwcheck-triage.js", "hwcheck-handoff.js",
];
const BEFORE = "（搬前快照）";

/**
 * **搬迁之后被别的工单合法改过的声明**（名字 → 改它的工单）。
 *
 * 为什么需要这张表：② 判的是"与搬前快照逐字相同"，而搬迁完成不等于代码从此不许动——
 * 后续工单动了这些函数就会被它判红（工单 hwcheck-hygiene/14 首例：`**粗**` 的渲染）。
 * 口径是**逐条记账**，不是放行：没登记进这张表的改动照旧报（下面的正向对照钉着这一点），
 * 且每条登记都要能在四件/六件里找到同名声明（防表腐烂）。
 */
const LATER_EDITS = new Map([
  ["hwcheckSectionNoteHTML", "hwcheck-hygiene/14"],   // 配方说明行改用 escRich
  ["hwcheckOrderHTML", "hwcheck-hygiene/14"],         // 建议顺序那一行改用 escRich
]);

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
 *
 * `declRe` 可换（工单 hwcheck-hygiene/11）：fx 那一半只认 `function|const`；
 * DOM 层那一半还要认 `async function` 与 `let`（模块级 `let` 是它的状态）。
 */
function unitsOf(text, declRe = DECL_RE) {
  const masked = maskCommentsAndStrings(text);
  const out = new Map();
  const re = new RegExp(declRe.source, "gm");
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
    if (LATER_EDITS.has(name)) continue;      // 搬迁后依法改过的：见 LATER_EDITS 的说明
    if (norm(want) !== norm(got.body)) {
      problems.push({
        code: "②",
        detail: `${name}（${got.key}）的声明单元与搬前不是逐字相同`,
      });
    }
  }

  // ③ window 桥：并集相等（且过渡态 barrel 不许回来——见下面那条用例）
  const bridgeBefore = [...windowBridgeNames(before)].sort();
  const bridgeAfter = [...new Set(after.flatMap((m) => [...windowBridgeNames(m.text)]))].sort();
  const bridgeLost = bridgeBefore.filter((n) => !bridgeAfter.includes(n));
  const bridgeAdded = bridgeAfter.filter((n) => !bridgeBefore.includes(n));
  if (bridgeLost.length) problems.push({ code: "③", detail: `桥丢了这些名字：${bridgeLost.join(", ")}` });
  if (bridgeAdded.length) problems.push({ code: "③", detail: `桥多出这些名字：${bridgeAdded.join(", ")}` });

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
  for (const name of MODULES) {
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
  for (const key of MODULES) {
    assert.ok(FILES.get(key).length > 200, `${key} 读出来只有 ${FILES.get(key).length} 字节`);
  }
  const bridge = [...windowBridgeNames(FILES.get(BEFORE))];
  assert.ok(bridge.length >= 60, `快照的桥只抽到 ${bridge.length} 个名字（下限 60）`);
  assert.ok(!existsSync(BARREL),
    "过渡态 barrel（fx/hwcheck.js）还在 —— 10 号单已经把消费者改指六件，它不该留在这棵树上");
});

test("搬迁完整：① 导出名集合 ② 声明单元逐字 ③ 桥并集 ④ 跨件 import —— 零问题", () => {
  const report = REPORT(FILES);
  assert.deepEqual(report, [],
    "搬迁与搬前快照对不上（每一条都是「搬的时候丢了东西」的形态）：\n  " + report.join("\n  "));
});

test("LATER_EDITS 体检：登记的名字真的在六件/四件里，且**没登记的改动照旧报**", () => {
  // 反方向的牙齿：这张表只能逐条豁免，不能变成"谁都别判我"的挡箭牌
  const names = new Set([...FILES.get(BEFORE).matchAll(DECL_RE)].map((m) => m[2]));
  const seen = new Set([...uiUnits(UI_FILES.get(UI_BEFORE)).keys(),
    ...[...FILES.values()].flatMap((t) => [...declaredNames(t)])]);
  for (const [name, why] of LATER_EDITS) {
    assert.ok(names.has(name), `LATER_EDITS 里的 ${name} 不在搬前快照里（表腐烂了，${why}）`);
    assert.ok(seen.has(name), `LATER_EDITS 里的 ${name} 在六件/四件里找不到（表腐烂了，${why}）`);
  }
  // 正向对照：改一个**没登记**的声明的函数体（不改名——改名归 ①），② 必须报
  const anchor = "这个输出位置下还没有检测工程。";
  const patched = withPatch(FILES, "hwcheck-project.js", (t) => {
    assert.ok(t.includes(anchor), "锚点变了 —— 这条自检会静默空转");
    return t.replace(anchor, "这个输出位置下还没有检测工程哦。");
  });
  const hits = REPORT(patched).filter((l) => l.startsWith("②") && l.includes("hwcheckRecentEmptyHTML"));
  assert.equal(hits.length, 1, `未登记的改动没被报出：${JSON.stringify(REPORT(patched))}`);
});

test("① 正向对照：摘掉一个导出必须报出（判据不是靠「两边都空」绿的）", () => {  const patched = withPatch(FILES, "hwcheck-triage.js",
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

test("③ 正向对照：摘掉一条桥必须报出", () => {
  const drop = withPatch(FILES, "hwcheck-plan.js",
    (t) => t.replace("hwcheckConsoleState, hwcheckConsoleHTML, hwcheckConsoleNoteHTML,",
      "hwcheckConsoleState, hwcheckConsoleNoteHTML,"));
  assert.ok(!drop.get("hwcheck-plan.js").includes("hwcheckConsoleHTML,"),
    "注入没落上（锚点变了？）—— 这条自检会静默空转");
  assert.ok(REPORT(drop).some((line) => line.startsWith("③") && line.includes("hwcheckConsoleHTML")),
    `摘掉桥条目没被报出：${JSON.stringify(REPORT(drop))}`);
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

test("过渡态不留痕：barrel 已删，且没有任何 import 边再指向旧路径", () => {
  // 10 号单的验收线。**口径**（与票面的 `grep 零命中` 差一点，理由在票尾）：
  // 判的是**有没有边指向它**——`from "…/fx/hwcheck.js"` 这类 import 一旦留在树上，
  // 浏览器解析时整页 SyntaxError；而**墓碑注释**（"由 fx/hwcheck.js 搬来"）是本仓既有体裁
  //（`boot.js` 里满是这样的话，守卫也按"注释不是消费者"处理），留着才解释得清这批文件的来历。
  assert.ok(!existsSync(BARREL), "fx/hwcheck.js 还在（它是 09 的过渡态 barrel）");
  const roots = ["../../src/contest_generator/", "../../tests/"]
    .map((rel) => fileURLToPath(new URL(rel, import.meta.url)));
  const hits = [];
  const walk = (dir) => {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const full = dir + entry.name;
      if (entry.isDirectory()) { walk(full + "/"); continue; }
      if (!/\.(js|mjs|py|html)$/.test(entry.name)) continue;
      // 本文件自己豁免：它的判据正则是**字面写着那个路径**的（不自指就没法判"别人有没有用"）。
      if (entry.name === "hwcheck-split-integrity.test.mjs") continue;
      const text = readFileSync(full, "utf8");
      // 边：`from "…/fx/hwcheck.js"` / 裸装载 `import "…/fx/hwcheck.js"` / `…src="…/fx/hwcheck.js"`
      for (const re of [/from\s+["'][^"']*fx\/hwcheck\.js["']/g,
        /import\s+["'][^"']*fx\/hwcheck\.js["']/g,
        /(?:src|href)\s*=\s*["'][^"']*fx\/hwcheck\.js["']/g]) {
        for (const m of text.matchAll(re)) {
          hits.push(`${full.slice(full.indexOf("firstep") + 8)}: ${m[0].slice(0, 60)}`);
        }
      }
    }
  };
  for (const root of roots) walk(root);
  assert.deepEqual(hits, [],
    "还有 import 边指向已删除的旧路径 `fx/hwcheck.js`（那会让整页脚本解析失败）：\n  "
    + hits.join("\n  "));
});

// ===========================================================================
// 第二部分：DOM 层那次拆分（工单 hwcheck-hygiene/11）
//
// `ui/hwcheck.js`（1401 行 / **59 个顶层声明**）按职责拆成四件——入口（接线 + 两个导出）／
// 核心渲染／「我的器件」／动作与请求。失败方式与 fx 那次同型：**静默少东西**（漏搬一个
// 函数、搬的时候手抖改一个字、某件少 import 一个兄弟函数、一段委托分支两边都不在）。
// 四种都不会让整页崩，所以"门禁全绿"只能证明**没搬坏**，证明不了搬全了。
//
// 与第一部分的两点不同（列得出，不许模糊）：
//   · 搬迁顺带做了三张**可数**的改造——15 段事件委托的匿名回调整段下沉成具名函数
//     （`UI_HANDLERS`：11 段进动作件、4 段进器件件），6 处跨件写入口
//     `pendingFocusSelector = X` → `setPendingFocus(X)`（ESM 的导入绑定只读，跨件写不了
//     `let`，所以核心件开了一个写入口），以及那个网格助手改名后**调用位**跟着改的 2 处
//     （`activate(e.target)` → `activateHwcheckDeviceCard(e.target)`）。故 ② 的"逐字"面
//     排除 `initHwcheck`，它由 ③ 按**代码行多重集**单独对账；三张表各有条数断言。
//     这就是工单 11 允许的"只搬不改 + 跨件调用方向在实施时定死"的全部形变，**没有第四张**：
//     谁能多改一处，这条自检就当场报（实测过：第一版漏改那两个调用位，③ 立刻点名）。
//   · 快照 `ui-hwcheck-before-split.js` 由 `apply-11-split.py` 第一次 `--write` 时落盘
//     （与该次 HEAD 那一份逐字节相同，指纹写死在脚本里）。
//
// ## 这**不是**工单 11 禁的那种"源码串断言"
//
// 工单 11 的验收写着"不新增源码串断言——新增的 ui 行为断言一律进真浏览器门禁"。它禁的是
// `readFileSync` + `includes("源码里有这行")` 那一类：那种断言看见 `**` 也照样绿（评审
// 三、工程卫生那一节的盲区）。本文件判的是**结构不变量**（名字集合 / 声明单元逐字 / 行级
// 分解 / 导出契约 / 调用位在场），**没有任何一条**是"某行源码在不在"；而且
// spec「测试决策」明写"这条自检是本轮唯一为拆分新造的判据"——09 为 fx 那一半造了它，
// 11 把同一件判据扩到 ui 那一半（同一个文件、同一套取数面），不是第二件新判据。
// 它挡的坏法**真浏览器用例看不见**：漏搬一段分支 / 搬的时候改一个字 / 少一条跨件 import，
// 三种都不会让整页崩，跑起来照样"能用"（第一版那段 `activate` 就是被真浏览器用例抓到的，
// 而这三类里没有一类能靠浏览器门禁用例穷举）。
// ===========================================================================

const UI_DIR = fileURLToPath(new URL("../../src/contest_generator/static/js/ui/", import.meta.url));
const UI_SNAPSHOT = fileURLToPath(
  new URL("../../.scratch/hwcheck-hygiene/ui-hwcheck-before-split.js", import.meta.url));
const UI_MODULES = ["hwcheck-core.js", "hwcheck-devices.js", "hwcheck-actions.js", "hwcheck.js"];
const UI_ENTRY = "hwcheck.js";
const UI_BEFORE = "（ui 搬前快照）";
/** 被改造过的声明：只有 `initHwcheck`（委托分支下沉 + 跨件写入口改写都发生在它内部）。 */
const UI_REWRITTEN = "initHwcheck";
/** 对外契约（票面：入口仍只有这两个导出）。 */
const UI_ENTRY_EXPORTS = ["initHwcheck", "renderHwcheckPanel"];
/** 下沉成具名函数的 15 段事件委托（名字 → 它现在住的那一件）。 */
const UI_HANDLERS = {
  "hwcheck-actions.js": [
    "handlePlatformClick", "handleChannelChange", "activateHwcheckDeviceCard",
    "handleDeviceGridClick", "handleDeviceGridKeydown", "handleDeviceChipsClick",
    "handleDeviceChipsKeydown", "handleParentChange", "pickHwcheckParent",
    "handleProjectClick", "handleChecklistChange",
  ],
  "hwcheck-devices.js": [
    "handleMyDeviceClick", "handleMyDeviceInput", "handleMyDeviceChange", "suggestMyDeviceId",
  ],
};
/** 拆分**新加**的名字（15 个处理分支 + 一个焦点写入口）——四件里多出来的只能是这些。 */
const UI_NEW_NAMES = ["setPendingFocus", ...Object.values(UI_HANDLERS).flat()];
/** 声明行（DOM 层还要认 `async function` 与 `let`）。 */
const UI_DECL_RE = /^(?:export )?(?:async )?(function|const|let|var) ([A-Za-z_$][\w$]*)/gm;
/** 被下沉的回调头（应恰好消失 14 行）：`x.addEventListener("evt", (e) => {`。 */
const UI_CALLBACK_HEAD_RE = /addEventListener\("[^"]+", (?:async )?\([^)]*\) => \{$/;
/**
 * **搬移的包装行**——两边一起丢掉，它们不承载信息，留着只会淹没差异：
 *   · 纯括号行（`}` / `});`）；
 *   · 捕获阶段回调的尾巴（`}, true);`）；
 *   · 下沉的具名助手头（`const activate = (target) => {` —— 它变成 `function …(target) {`，
 *     而函数签名行在 `uiBodyLines` 里本来就被丢掉）。
 */
const UI_WRAPPER_LINE = [/^[)}\];,]+$/, /^\}, true\);$/, /^const \w+ = \([^)]*\) => \{$/];
/** 三段**不是**事件委托的下沉（`activate` 是网格里的具名助手，入口没有它的接线）。 */
const UI_NO_WIRING = new Set(["activateHwcheckDeviceCard"]);
const UI_WIRING_COUNT = 15 - UI_NO_WIRING.size;
/** 跨件写入口（`pendingFocusSelector = X` → `setPendingFocus(X)`）——ESM 导入绑定只读。 */
const UI_FOCUS_REWRITES = 6;

const uiUnits = (text) => unitsOf(text, UI_DECL_RE);
const unitsIn = (text, name) => uiUnits(text).get(name);

/**
 * 代码行（去空行 / 去注释 / 归一空白 / 丢掉包装行）——多重集对账的取数面。
 */
function uiCodeLines(text) {
  return text
    .replace(/\/\*[\s\S]*?\*\//g, " ")
    .split("\n")
    .map((line) => line.replace(/\s+/g, " ").trim())
    .filter((line) => line && !line.startsWith("//")
      && !UI_WRAPPER_LINE.some((re) => re.test(line)));
}

/** 声明单元的**正文行**（丢掉签名行——`function x(...) {` 是包装，注释与空行已在上一步滤掉）。 */
function uiBodyLines(unit) {
  return uiCodeLines(unit)
    .filter((line) => !/^(?:export )?(?:async )?(?:function|const|let|var) [A-Za-z_$][\w$]*/.test(line));
}

/** 逐字面比较前的归一：拆分的唯一允许增量是声明行前面的 `export `（跨件要用它）。 */
const stripExport = (text) =>
  text.replace(/(^|\n)[ \t]*export[ \t]+(?=(?:async )?(?:function|const|let|var) )/g, "$1");

/**
 * 判据 ⑥ 的豁免面：**语言内置 + 浏览器平台对象**（清单里不许出现本栏目自己的名字——
 * 那会把"搬丢一个函数"喂成绿；由下面的自检钉住）。
 */
const UI_GLOBALS = new Set([
  "Object", "Array", "String", "Number", "Boolean", "JSON", "Math", "Date", "RegExp",
  "Set", "Map", "Promise", "Error", "parseInt", "parseFloat", "isNaN",
  "encodeURIComponent", "decodeURIComponent", "setTimeout", "clearTimeout",
  "document", "window", "localStorage", "fetch", "FormData", "console",
]);

/**
 * 判据 ⑥：**每个调用位的自由标识符都必须在场**（本件声明 ∪ 本件 import ∪ 上面那几个全局）。
 *
 * 这一条是为一类真实事故立的：网格助手 `activate` 下沉成 `activateHwcheckDeviceCard` 时，
 * 两个处理分支里的**调用位**没跟着改（第一版实测）。`activate` 既不在本件声明、也不在任何
 * import 里、更不在 `window` 桥上——前端门禁与结构守卫**全绿**，只有"点器件卡片"那几条
 * 真浏览器用例红（9 条 30s 超时）。守卫 ⑧（桥依赖）只看桥上的名字，管不到这种"谁都没有的名字"。
 */
function uiDanglingCalls(files) {
  const problems = [];
  for (const key of UI_MODULES) {
    const text = files.get(key);
    const declared = new Set(uiUnits(text).keys());
    const imported = new Set(parseModuleImports(text).flatMap((edge) => edge.locals));
    for (const { name, line } of callPositionNames(maskNonCode(text))) {
      if (declared.has(name) || imported.has(name) || UI_GLOBALS.has(name)) continue;
      problems.push({ code: "⑥", detail: `${key}:${line} 调用了 ${name}（本件没声明、也没 import）` });
    }
  }
  return problems;
}

const uiAllFiles = () => {
  const files = new Map();
  files.set(UI_BEFORE, readFileSync(UI_SNAPSHOT, "utf8"));
  for (const name of UI_MODULES) files.set(name, readFileSync(UI_DIR + name, "utf8"));
  return files;
};

/** 多重集（Map<行, 条数>）——行级对账要走它，"集合"会把重复行吃掉。 */
function multiset(lines) {
  const out = new Map();
  for (const line of lines) out.set(line, (out.get(line) || 0) + 1);
  return out;
}

const multisetDiff = (a, b) => {
  const out = [];
  for (const [line, count] of a) {
    const rest = count - (b.get(line) || 0);
    for (let i = 0; i < rest; i++) out.push(line);
  }
  return out;
};

/** files = Map<名字, 源码>（含 UI_BEFORE 那一份快照）。→ [{ code, detail }]；空 = 搬迁完整。 */
function uiAuditProblems(files) {
  const problems = [];
  const before = files.get(UI_BEFORE);
  const beforeUnits = uiUnits(before);
  const afterUnits = new Map();
  for (const key of UI_MODULES) {
    for (const [name, body] of uiUnits(files.get(key))) {
      if (afterUnits.has(name)) problems.push({ code: "①", detail: `${name} 在四件里出现了两次` });
      afterUnits.set(name, { key, body });
    }
  }

  // ① 声明名集合（快照有 59 个：导出 ＋ 私有件 ＋ 模块级 `let`）
  for (const name of beforeUnits.keys()) {
    if (!afterUnits.has(name)) problems.push({ code: "①", detail: `搬前有、四件里没有：${name}` });
  }
  const extra = [...afterUnits.keys()].filter((n) => !beforeUnits.has(n));
  const unexpected = extra.filter((n) => !UI_NEW_NAMES.includes(n));
  if (unexpected.length) {
    problems.push({ code: "①", detail: `四件多出未登记的名字：${unexpected.join(", ")}` });
  }
  const lostNew = UI_NEW_NAMES.filter((n) => !afterUnits.has(n));
  if (lostNew.length) problems.push({ code: "①", detail: `登记过的新名字不见了：${lostNew.join(", ")}` });

  // ② 声明单元逐字（含紧邻上方的注释块）——`initHwcheck` 除外（它被改造，由 ③ 对）。
  //    唯一允许的增量是声明行前面的 `export `（跨件要用它；09 那半同理）。
  for (const [name, want] of beforeUnits) {
    if (name === UI_REWRITTEN) continue;
    const got = afterUnits.get(name);
    if (!got) continue;                                  // ① 已报
    if (LATER_EDITS.has(name)) continue;                 // 搬迁后依法改过的
    if (norm(stripExport(want)) !== norm(stripExport(got.body))) {
      problems.push({ code: "②", detail: `${name}（${got.key}）的声明单元与搬前不是逐字相同` });
    }
  }

  // ③ `initHwcheck` 的行级分解：搬前 = 入口 ＋ 15 段下沉分支 − 三张改造表
  const rawBefore = uiBodyLines(unitsIn(before, UI_REWRITTEN));
  let beforeLines = rawBefore;
  const lineRewrites = [
    { re: /^pendingFocusSelector = (.+);$/, to: "setPendingFocus($1);",
      count: UI_FOCUS_REWRITES, what: "跨件写入口（`pendingFocusSelector = …`）" },
    { re: /(?<![\w$.])activate\(e\.target\)/, to: "activateHwcheckDeviceCard(e.target)",
      count: 2, what: "下沉助手的**调用位**改名（`activate(e.target)`）" },
  ];
  for (const rw of lineRewrites) {
    const hit = beforeLines.filter((line) => rw.re.test(line)).length;
    if (hit !== rw.count) {
      problems.push({ code: "③", detail: `${rw.what} 应恰为 ${rw.count} 处，实测 ${hit}` });
    }
    beforeLines = beforeLines.map((line) => line.replace(rw.re, rw.to));
  }
  const entryLines = uiBodyLines(unitsIn(files.get(UI_ENTRY), UI_REWRITTEN));
  const handlerLines = Object.entries(UI_HANDLERS).flatMap(([key, names]) =>
    names.flatMap((name) => {
      const unit = unitsIn(files.get(key), name);
      return unit === undefined ? [] : uiBodyLines(unit);
    }));
  const right = multiset([...entryLines, ...handlerLines]);
  const missing = multisetDiff(multiset(beforeLines), right);
  const added = multisetDiff(right, multiset(beforeLines));
  const badMissing = missing.filter((line) => !UI_CALLBACK_HEAD_RE.test(line));
  if (missing.length !== UI_WIRING_COUNT || badMissing.length) {
    problems.push({
      code: "③",
      detail: `入口 + 15 段分支对不上搬前的 initHwcheck：少 ${missing.length} 行`
        + `（应恰为 ${UI_WIRING_COUNT} 条回调头）、其中不像是回调头的 ${badMissing.length} 行`
        + `${badMissing.length ? "：" + badMissing.slice(0, 3).join(" ｜ ") : ""}`,
    });
  }
  const wiringLines = added.filter((line) => line.includes("addEventListener("));
  const badAdded = added.filter((line) => !wiringLines.includes(line));
  if (wiringLines.length !== UI_WIRING_COUNT || badAdded.length) {
    problems.push({
      code: "③",
      detail: `多出来的行只该是那 ${UI_WIRING_COUNT} 条接线：实测接线 ${wiringLines.length}、`
        + `其它 ${badAdded.length} 行${badAdded.length ? "：" + badAdded.slice(0, 3).join(" ｜ ") : ""}`,
    });
  }

  // ④ 对外契约：入口的导出仍只有那两个
  const entryExports = [...parseModuleExports(files.get(UI_ENTRY))].sort();
  if (JSON.stringify(entryExports) !== JSON.stringify(UI_ENTRY_EXPORTS)) {
    problems.push({
      code: "④",
      detail: `入口的导出面变了：${entryExports.join(", ")}（应 ${UI_ENTRY_EXPORTS.join(", ")}）`,
    });
  }

  // ⑤ 15 段分支**两头都在**：本件声明了它，入口有一条接线调它（`activate` 那段不是委托，
  //    它是网格里的具名助手，入口没有它的接线——那一条按名单豁免）。
  const entryText = files.get(UI_ENTRY);
  for (const [key, names] of Object.entries(UI_HANDLERS)) {
    for (const name of names) {
      if (!afterUnits.has(name) || afterUnits.get(name).key !== key) {
        problems.push({ code: "⑤", detail: `${name} 不在 ${key} 里` });
        continue;
      }
      if (UI_NO_WIRING.has(name)) continue;
      const wired = new RegExp(`addEventListener\\("[^"]+", (?:\\([^)]*\\) => )?${name}\\b`)
        .test(entryText);
      if (!wired) problems.push({ code: "⑤", detail: `入口没有指向 ${name} 的接线` });
    }
  }

  // ⑥ 调用位的自由标识符必须在场（上面那段说明：这是第一版真踩到的那一类）
  problems.push(...uiDanglingCalls(files));
  return problems;
}

const UI_FILES = uiAllFiles();
const uiReport = (files) => uiAuditProblems(files).map((p) => `${p.code} ${p.detail}`);
const uiPatch = (files, key, fn) =>
  new Map([...files].map(([k, text]) => [k, k === key ? fn(text) : text]));
const UI_HANDLER_COUNT = Object.keys(UI_HANDLERS).flatMap((k) => UI_HANDLERS[k]).length;

test("ui 拆分体检：快照与四件都读到了，且判据面够大（那种绿比红更坏）", () => {
  const names = [...uiUnits(UI_FILES.get(UI_BEFORE)).keys()];
  assert.ok(names.length >= 55, `快照的声明只抽到 ${names.length} 个（下限 55）——抽取器失效？`);
  assert.equal(UI_HANDLER_COUNT, 15, "下沉的处理分支应恰为 15 段");
  assert.equal(UI_NEW_NAMES.length, 16, "新名字应是 15 段分支 + setPendingFocus");
  for (const key of UI_MODULES) {
    assert.ok(UI_FILES.get(key).length > 200, `${key} 读出来只有 ${UI_FILES.get(key).length} 字节`);
  }
  const lines = uiBodyLines(unitsIn(UI_FILES.get(UI_BEFORE), UI_REWRITTEN));
  assert.ok(lines.length >= 150, `搬前的 initHwcheck 只抽到 ${lines.length} 行代码`);
  // ⑥ 的豁免面不许掺进本栏目自己的名字（否则"搬丢一个函数"会被它喂绿）
  const own = new Set(UI_MODULES.flatMap((key) => [...uiUnits(UI_FILES.get(key)).keys()]));
  const overlap = [...UI_GLOBALS].filter((n) => own.has(n));
  assert.deepEqual(overlap, [], `判据 ⑥ 的豁免面里有本栏目自己的名字：${overlap.join(", ")}`);
  // ⑥ 的判据面非空自检：四件里至少扫得出一批调用位
  const calls = UI_MODULES.flatMap((key) => callPositionNames(maskNonCode(UI_FILES.get(key))));
  assert.ok(calls.length >= 150, `四件只扫出 ${calls.length} 个调用位（取数面失效？）`);
});

test("ui 搬迁完整：① 声明名 ② 声明单元逐字 ③ initHwcheck 行级分解 ④ 契约 ⑤ 两头都在 ⑥ 调用位在场", () => {
  const report = uiReport(UI_FILES);
  assert.deepEqual(report, [],
    "DOM 层搬迁与搬前快照对不上（每条都是「搬的时候丢了东西」的形态）：\n  " + report.join("\n  "));
});

test("ui ⑥ 正向对照：调用位冒出一个谁都没有的名字必须报出（第一版真踩到的形态）", () => {
  const anchor = "  addHwcheckDevice(card.dataset.add);";
  const patched = uiPatch(UI_FILES, "hwcheck-actions.js", (t) => {
    assert.ok(t.includes(anchor), `锚点变了（${anchor}）—— 这条自检会静默空转`);
    return t.replace(anchor, "  activateProbeGhost(card.dataset.add);");
  });
  const hits = uiReport(patched).filter((l) => l.startsWith("⑥"));
  assert.ok(hits.some((l) => l.includes("activateProbeGhost")),
    `调用位冒出幽灵名字没被报出：${JSON.stringify(uiReport(patched))}`);
});

test("ui ② 正向对照：改一个未改造声明的一个字必须报出", () => {
  const anchor = "return hwcheckPlatformLabel(hwcheckPlatforms(), id);";
  const patched = uiPatch(UI_FILES, "hwcheck-core.js", (t) => {
    assert.ok(t.includes(anchor), `锚点变了（${anchor}）—— 这条自检会静默空转`);
    return t.replace(anchor, "return hwcheckPlatformLabel(hwcheckPlatforms(), id + \"\");");
  });
  assert.ok(uiReport(patched).some((l) => l.startsWith("②") && l.includes("platformLabel")),
    `改了函数体没被报出：${JSON.stringify(uiReport(patched))}`);
});

test("ui ③ 正向对照：入口把一条接线改回匿名回调（分支就没人管了）必须报出", () => {
  const anchor = 'platforms.addEventListener("click", handlePlatformClick);';
  const patched = uiPatch(UI_FILES, UI_ENTRY, (t) => {
    assert.ok(t.includes(anchor), `锚点变了（${anchor}）—— 这条自检会静默空转`);
    // 注入成**多行**的匿名回调：单行写法既不改行多重集、也摸不到"回调头"那条判据
    return t.replace(anchor,
      'platforms.addEventListener("click", (e) => {\r\n      handlePlatformClick(e);\r\n    });');
  });
  const hits = uiReport(patched);
  assert.ok(hits.some((l) => l.startsWith("③")), `行级分解没报出：${JSON.stringify(hits)}`);
  assert.ok(hits.some((l) => l.startsWith("⑤") && l.includes("handlePlatformClick")),
    `"入口没有指向它的接线"没报出：${JSON.stringify(hits)}`);
});

test("ui ① 正向对照：删掉一段下沉分支必须报出（两个方向各报一次）", () => {
  const patched = uiPatch(UI_FILES, "hwcheck-devices.js",
    (t) => t.replace(/\/\/ suggestMyDeviceId[\s\S]*?\r?\n\}\r?\n/, "\r\n"));
  assert.ok(!patched.get("hwcheck-devices.js").includes("function suggestMyDeviceId"),
    "注入没落上（锚点变了？）—— 这条自检会静默空转");
  const hits = uiReport(patched);
  assert.ok(hits.some((l) => l.startsWith("①") && l.includes("suggestMyDeviceId")),
    `新名字丢了没被报出：${JSON.stringify(hits)}`);
  assert.ok(hits.some((l) => l.startsWith("③") || l.startsWith("⑤")),
    `分支两头缺一头没被报出：${JSON.stringify(hits)}`);
});

test("ui ④ 正向对照：入口多一个导出必须报出（对外契约就这两个）", () => {
  const patched = uiPatch(UI_FILES, UI_ENTRY, (t) => `${t}\nexport function probeExtraExport() {}\n`);
  const hits = uiReport(patched);
  assert.ok(hits.some((l) => l.startsWith("④")), `导出面变了没被报出：${JSON.stringify(hits)}`);
  assert.ok(hits.some((l) => l.startsWith("①") && l.includes("probeExtraExport")),
    `未登记的声明没被报出：${JSON.stringify(hits)}`);
});
