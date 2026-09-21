// apply-sweep.mjs — 工单 export-surface-guard/02 的清点执行器
//
// 要做什么：让**判据 D（零消费者导出）从 111 处变成 0 处**，且页面行为零变化。
// 处置形态照实测（`.scratch/export-surface-guard/survey-06-sweep-inventory.txt`）：
//
//   ① 73 处 inline（`export const/let/function/async function NAME`）→ 删 `export ` 前缀
//   ② 30 处从**留下**的 8 条 `export {…}` 清单里摘名字
//   ③  7 处所在的 4 条清单**整行删**（`ui/full-update.js:150` / `ui/generate-fix.js:47` /
//      `ui/params-chat.js:225` / `ui/params.js:366`）
//   ④  1 处整条删：`ui/generate-recommend.js::groupChoiceGap()`（零引用；上方无专属注释块）
//   ⑤  1 处**级联**：`ui/fix-center-core.js::fixLoop` —— 原消费者正是 ③ 里
//      `ui/generate-fix.js:47` 那条转手再导出（`export { … } from "…"` 本身就是一条 import 边）。
//      摘掉它，`fixLoop` 就成零消费者了；判据 D 要 0，这一处必须一起摘。
//      **它不是"顺手做"**：在摘之前算不出它（当时它还有消费者）——这是清点暴露出来的必然结果。
//   ⑥  1 处**孤儿 import**：`ui/full-update.js` 的 `fullStateText` 只为那条再导出而存在，
//      摘完 export 它就成了未使用具名（`import-usage.mjs` 那条不变量）→ 连它一起摘。
//
// **自带校验**（工单 02 验收标准第一条）：
//   · 清点前先复算判据 D；形态分布与实测基线对不上就整体不写盘；
//   · 每处都**内容锚定**（存死锚点的形态要求原文里恰好命中一次；清单/import 形态按当前文本现算）；
//   · 逐处断言"改完这一处，其文本刚好是删掉那个 `export` / `import` 的样子"；
//   · 全量归一化比对：把改动前后各自的 `import`/`export` 边语句都抹掉，两份正文必须
//     **逐字节相同**（唯一例外是 ④ 那一个被明令整条删的函数，单独记账单独核验）；
//   · 行尾：`static/js` 下混着 LF 与 CRLF，落盘前按清点前那个文件**逐字节还原**行尾写法与尾部换行数；
//   · 收尾复跑判据 D / 判据 T / 星号体检 / 取数面体检 / `graphBreaks` / `reachable` /
//     `wiringViolations` / `registryProblems`，并跑既有 `unusedImports` 判据。
//
// 用法（在仓库根）：
//     node .scratch/export-surface-guard/apply-sweep.mjs            # 执行清点 + 写 verify-sweep.txt
//     node .scratch/export-surface-guard/apply-sweep.mjs --dry-run  # 只出报告，不写盘
import { writeFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import {
  readJsModules, readLoadRoot, readConsumerModules, maskCommentsAndStrings, parseModuleExports,
  parseModuleImports, unconsumedExports, nonFunctionCallees, starImports, exportFaceProblems,
  graphBreaks, wiringViolations, reachable, registryProblems,
} from "../../tests/js/boot-contract.mjs";
import { unusedImports, identRe } from "../../tests/js/import-usage.mjs";

const ROOT = fileURLToPath(new URL("../../", import.meta.url));
const STATIC = `${ROOT}src/contest_generator/static`;
const JS_DIR = `${STATIC}/js`;
const OUT = fileURLToPath(new URL("./verify-sweep.txt", import.meta.url));
const DRY = process.argv.includes("--dry-run");
const esc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const abs = (key) => `${JS_DIR}/${key}`;

// 实测形态基线（probe-06 / survey-06）：对不上就是现场被人动过，整体拒绝
const EXPECT = { inlinePrefix: 73, listName: 30, listWhole: 7, wholeDelete: 1, total: 111, exports: 995 };

const lines = [];
const say = (s = "") => { lines.push(s); console.log(s); };
const die = (msg) => {
  say(`\n✗ 拒绝写盘：${msg}`);
  writeFileSync(OUT, lines.join("\n") + "\n", "utf8");       // 读数照落档：失败现场比成功后更值得留
  console.error(`\n✗ 拒绝写盘：${msg}\n（读数已落 ${OUT}）`);
  process.exit(2);
};

// ---------------------------------------------------------------------------
// 通用小件
// ---------------------------------------------------------------------------

const lf = (s) => s.split("\r\n").join("\n");

/** 尾部换行数（CRLF 归一再数）。 */
const trailingEol = (s) => {
  const n = lf(s);
  return n.length - n.replace(/\n+$/, "").length;
};

/**
 * 清点用的行尾判法（**必须在 `lf()` 之前调**——一旦归一成 LF，`\r` 就没了，判出来永远是 LF；
 * 第一版就是先 `lf()` 再判，于是"49 个 CRLF 文件"被读成"0 个 CRLF / 49 个 LF"，
 * 还原函数也跟着按 LF 写回去，差点把 49 个文件的行尾整体改掉——被下面那条断言拦下）。
 */
const eolOf = (sample) => (sample.includes("\r\n") ? "\r\n" : "\n");

/**
 * 收尾：把行尾**写法**还原成清点前那个文件的样子。
 *
 * 关键点：清点是在**原文**上做的，插进去的换行是 LF，而仓库里 51 个文件是 CRLF。
 * 第一版写成"整篇 `\n` → `\r\n`"（按文档语义没错），但那会把文件里**原本就是 LF 的换行**
 * 一并改掉——`ui/generate-recommend.js` 正是"整体 CRLF、个别行 LF"的混合体，
 * 于是三条按**字面 LF** 断言源码形态的用例当场变红（实测：前端门禁 1679 → 1677）。
 *
 * 正确的做法：按 `\n` 切行、再按原文件的写法**逐行**接回去 —— 只统一"写法"，
 * 不制造"原本没有的差异"；行首缩进与行尾空白一律不动。
 */
function restoreLineEndings(text, sample) {
  const eol = eolOf(sample);
  const body = lf(text).replace(/\n+$/, "");              // 先归一，免得把 `\r\n` 数成两行
  return body.split("\n").join(eol) + eol.repeat(trailingEol(sample));
}

/** 第 `line` 行（1 基）在 `text` 里的字符下标；越界返回 -1。 */
function lineStart(text, line) {
  if (line < 1) return -1;
  let at = 0;
  for (let i = 1; i < line; i++) {
    at = text.indexOf("\n", at);
    if (at < 0) return -1;
    at += 1;
  }
  return at;
}

/**
 * **只替换第一次出现**（并显式断言锚点还在——不在就当场失败，不静默跳过）。
 * 同一模块里多处改动按顺序串行施加：前一处改完的文本是后一处的输入。
 */
function replaceOnce(text, anchor, to) {
  const at = text.indexOf(anchor);
  if (at < 0) return null;
  return text.slice(0, at) + to + text.slice(at + anchor.length);
}

/** 清空第 `line`..`endLine` 行（1 基，含端点；保留换行，行结构不动）。 */
function clearLines(text, line, endLine) {
  const raw = text.split("\n");
  if (line < 1 || endLine > raw.length) return null;
  for (let i = line; i <= endLine; i++) raw[i - 1] = "";
  return raw.join("\n");
}

/** 把 `export {…}` 清单里**顶层**的一项 `name` 摘掉（嵌套对象里的逗号不算分隔符）。 */
function dropListItem(text, name) {
  for (const m of text.matchAll(/(?:^|\n)[ \t]*export\s*\{/g)) {
    const open = text.indexOf("{", m.index);
    let depth = 0;
    let close = -1;
    for (let i = open; i >= 0 && i < text.length; i++) {
      if (text[i] === "{") depth++;
      else if (text[i] === "}" && --depth === 0) { close = i; break; }
    }
    if (close < 0) continue;
    const body = text.slice(open + 1, close);
    let hit = false;
    const kept = body.split(/\s*,\s*/)
      .map((p) => p.trim())
      .filter((p) => {
        if (p.split(/\s+as\s+/)[0].trim() !== name) return true;
        hit = true;
        return false;
      });
    if (!hit) continue;
    // 重排成单行 `{ a, b }`：摘掉一项后原多行布局会留下整行空白与孤儿缩进，收成一行最干净。
    // **紧随其后的空行不动**——原来 `}` 与下一段之间隔几个空行就还隔几个（少删一个空行，
    // diff 里就少一条与本轮无关的差异）。
    return text.slice(0, open + 1) + ` ${kept.join(", ")} ` + text.slice(close);
  }
  return null;
}

/** 把一条 import 边里的 `name` 摘掉（剩 0 个名字就整行清空，保留换行）。 */
function dropImportName(text, edge, name) {
  const at = lineStart(text, edge.line);
  if (at < 0 || text.slice(at, at + edge.raw.length) !== edge.raw) return null;
  const keep = edge.names.filter((n) => n !== name);
  if (keep.length) {
    const open = text.indexOf("{", at);
    const close = text.indexOf("}", open);
    if (open < 0 || close < 0) return null;
    return text.slice(0, open + 1) + ` ${keep.join(", ")} ` + text.slice(close);
  }
  const nl = text.indexOf("\n", at);
  return text.slice(0, at) + (nl < 0 ? "" : text.slice(nl));
}

/** 模块里所有 `export {…}` 清单 → [{ start, end, names }]（行列 1 基；含注释、多行都认）。 */
function exportLists(text) {
  const masked = maskCommentsAndStrings(text);
  const out = [];
  for (const m of masked.matchAll(/(?:^|\n)([ \t]*)export\s*\{/g)) {
    // 前导 `\n` 也算在 `m[0]` 里，起算必须带上它——漏了它就整体前移一格，
    // "清单整行删"会从上一条语句的 `{` 起切（实测把 `} from "…";` 一起吃掉了）
    const begin = m.index + (m[0].startsWith("\n") ? 1 : 0) + m[1].length;
    const open = masked.indexOf("{", begin);
    const close = masked.indexOf("}", open);
    if (open < 0 || close < 0) continue;
    out.push({
      start: masked.slice(0, begin).split("\n").length,
      end: masked.slice(0, close).split("\n").length,
      names: masked.slice(open + 1, close).split(",")
        .map((p) => p.trim().split(/\s+as\s+/)[0].trim()).filter(Boolean),
    });
  }
  return out;
}

/** 从锚行起按花括号配平找函数体结束行（1 基）。 */
function functionEndLine(text, startLine) {
  const body = text.split("\n").slice(startLine - 1).join("\n");
  const open = body.indexOf("{");
  if (open < 0) return startLine;
  let depth = 0;
  for (let i = open; i < body.length; i++) {
    if (body[i] === "{") depth++;
    else if (body[i] === "}" && --depth === 0) {
      return startLine + body.slice(0, i).split("\n").length - 1;
    }
  }
  return startLine;
}

/**
 * 归一化：把所有 import / export **边语句**与 inline `export ` 前缀抹掉，再统一收敛空行。
 * 剩下的是同一份正文 ⇔ 动过的只有导出面与导入面。
 *
 * 三条纪律（都是被误报/假绿逼出来的）：
 *   · **先统一行尾**：`static/js` 下混着 LF 与 CRLF，不统一的话"行尾多个 `\r`"与"少一行"分不清；
 *   · **边语句只清空、不删行**：否则"删掉一条语句"与"删掉一个空行"无法区分；
 *   · **收尾不折叠**：尾随空行/换行的差异必须照样现形（折叠会把真差异抹掉 = 假绿）。
 *
 * 边语句行区间取两处并集：`parseModuleImports` 的 `{line, raw}`（管 import 与带 `from` 的再导出），
 * 以及本文件自己扫的 `^export {`——**纯本文件导出面（无 `from`）不是 import 边**，
 * 解析器按设计不收，但它当然也是导出面。
 */
function normalizeBody(text) {
  const body = lf(text);
  const drop = new Set();
  const mark = (startLine, span) => { for (let i = 0; i < span; i++) drop.add(startLine + i); };
  for (const e of parseModuleImports(body)) mark(e.line, Math.max(1, e.raw.split("\n").length));
  const masked = maskCommentsAndStrings(body);
  for (const m of masked.matchAll(/(?:^|\n)[ \t]*export\s*\{/g)) {
    const start = m.index + (m[0].startsWith("\n") ? 1 : 0);
    const first = masked.slice(0, start).split("\n").length;
    let depth = 0;
    let close = -1;
    for (let i = masked.indexOf("{", start); i >= 0 && i < masked.length; i++) {
      if (masked[i] === "{") depth++;
      else if (masked[i] === "}" && --depth === 0) { close = i; break; }
    }
    mark(first, masked.slice(start, close < 0 ? masked.length : close).split("\n").length);
  }
  const out = body.split("\n").map((line, i) => (drop.has(i + 1) ? "" : line)).join("\n");
  return out.replace(/^([ \t]*)export\s+(?=(?:async\s+)?(?:function|class|const|let|var)\b)/gm, "$1")
    .replace(/\n{2,}/g, "\n\n").split("\n").map((l) => l.replace(/[ \t]+$/, "")).join("\n");
}

/** 行级 LCS 差异 → [{ a: 下标或 -1, b: 下标或 -1 }]（用于归因"正文为什么变了"）。 */
function diffLines(a, b) {
  const n = a.length;
  const m = b.length;
  const dp = Array.from({ length: n + 1 }, () => new Uint32Array(m + 1));
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
    }
  }
  const ops = [];
  let i = 0;
  let j = 0;
  while (i < n && j < m) {
    if (a[i] === b[j]) { i++; j++; continue; }
    if (dp[i + 1][j] >= dp[i][j + 1]) ops.push({ a: i++, b: -1 });
    else ops.push({ a: -1, b: j++ });
  }
  while (i < n) ops.push({ a: i++, b: -1 });
  while (j < m) ops.push({ a: -1, b: j++ });
  return ops;
}

/** 把差异归因成人话：多删了几行 / 多插了几行，带样例。 */
function explainDiff(a, b) {
  const ops = diffLines(a, b);
  const notes = [];
  let k = 0;
  let changed = 0;
  while (k < ops.length) {
    if (ops[k].a >= 0 && ops[k].b >= 0) { changed++; k++; continue; }
    const del = [];
    const ins = [];
    let lastA = -1;
    while (k < ops.length && !(ops[k].a >= 0 && ops[k].b >= 0)) {
      if (ops[k].a >= 0) { del.push(a[ops[k].a]); lastA = ops[k].a; } else ins.push(b[ops[k].b]);
      k++;
    }
    if (del.length && ins.length) {
      notes.push(`整块替换：第 ${lastA + 1} 行附近删 ${del.length} 行 / 插 ${ins.length} 行`
        + `（前「${del[0].trim().slice(0, 40)}」→ 后「${ins[0].trim().slice(0, 40)}」）`);
    } else if (del.length) {
      notes.push(`多删了 ${del.length} 行（第 ${lastA + 1} 行附近，样例「${del[0].trim().slice(0, 40)}」）`);
    } else {
      notes.push(`多插了 ${ins.length} 行（样例「${ins[0].trim().slice(0, 40)}」）`);
    }
  }
  if (changed) notes.unshift(`有 ${changed} 行只能靠"同一行被改过"对齐`);
  return notes;
}

// ---------------------------------------------------------------------------
// ① 清点前状态：复算判据 D，做形态归类，与实测基线对表
// ---------------------------------------------------------------------------

// 现场只**如实打印**，不拿它当闸门：本机 `core.autocrlf=true` 会把检出物物化成 CRLF，
// 而清点是按工作树原文读的——于是"git 认为干净 / 我读到的是 CRLF 版"可以同时成立，
// 用 git status 当闸门会误杀（实测踩过）。
// 真正的闸门在下面：清点前判据 D **必须恰好 111 处**（清点过一遍之后再跑就是 0 处 → 直接拒绝），
// 加上逐处锚定 + 逐处自校验 + 全量归一化比对 + 行尾还原，任何一条不过都整体不写盘。
const gitStatus = execFileSync("git", ["status", "--porcelain", "--", "src/contest_generator/static/js"],
  { cwd: ROOT, encoding: "utf8" }).trim();
say("== ⓪ 现场 ==");
say(`  git 对 src/contest_generator/static/js 的未提交改动：${gitStatus ? `\n${gitStatus}` : "无（干净）"}`);
say(`  行尾（工作树原文，CRLF 检出下与 git 对象不同）：${eolOf(readLoadRoot(STATIC)) === "\r\n" ? "CRLF" : "LF"}`);

const before = new Map(readJsModules(STATIC).map((m) => [m.key, m.text]));
before.set("boot.js", readLoadRoot(STATIC));
const consumers = readConsumerModules(ROOT);
const pageEntries = [...before.entries()].map(([key, text]) => ({ key, text }));

const violations = unconsumedExports(pageEntries, consumers);
const exportsBefore = pageEntries.reduce((n, e) => n + parseModuleExports(e.text).size, 0);
say("\n== ① 清点前判据 D ==");
say(`  页面模块 ${pageEntries.length} 个；消费侧 ${consumers.length} 个 .mjs`);
say(`  零消费者导出：${violations.length} 处（实测基线 ${EXPECT.total}）`);
say(`  导出条目总数：${exportsBefore}（实测基线 ${EXPECT.exports}）`);
if (violations.length !== EXPECT.total) die(`判据 D 报出 ${violations.length} 处，实测基线是 ${EXPECT.total} 处`);
if (exportsBefore !== EXPECT.exports) die(`导出条目总数 ${exportsBefore}，实测基线是 ${EXPECT.exports}`);

// 形态归类：inline 前缀 / 清单整行删 / 清单摘名字 / 整条删
const catalog = [];
for (const v of violations) {
  const text = before.get(v.key);
  const maskedLines = maskCommentsAndStrings(text).split("\n");
  const inlineRe = new RegExp(`^[ \\t]*export\\s+(?:async\\s+)?(?:function|class|const|let|var)\\s+${esc(v.name)}(?![\\w$])`);
  const inlineLine = maskedLines.findIndex((l) => inlineRe.test(l));
  if (inlineLine >= 0) {
    catalog.push({ ...v, shape: "inline", line: inlineLine + 1 });
    continue;
  }
  const list = exportLists(text).find((l) => l.names.includes(v.name));
  if (list) {
    catalog.push({ ...v, shape: "list", line: list.start, end: list.end, list: list.names });
    continue;
  }
  die(`${v.key}::${v.name} 既不是 inline 声明也不在任何 \`export {…}\` 清单里 —— 形态认不出，拒绝猜`);
}
const whole = catalog.filter((c) => c.key === "ui/generate-recommend.js" && c.name === "groupChoiceGap");
const inline = catalog.filter((c) => c.shape === "inline" && !whole.includes(c));
if (whole.length !== 1) die(`inline 形态里 groupChoiceGap 找到 ${whole.length} 个（应为 1 个）`);

const sites = new Map();
for (const c of catalog.filter((x) => x.shape === "list")) {
  const tag = `${c.key}:${c.line}-${c.end}`;
  if (!sites.has(tag)) sites.set(tag, { tag, key: c.key, line: c.line, end: c.end, list: c.list, doomed: [] });
  sites.get(tag).doomed.push(c.name);
}
const listWhole = [...sites.values()].filter((s) => s.doomed.length === s.list.length);
const listKept = [...sites.values()].filter((s) => s.doomed.length !== s.list.length);
const shape = {
  inlinePrefix: inline.length,
  listName: catalog.filter((c) => c.shape === "list"
    && listKept.some((s) => s.tag === `${c.key}:${c.line}-${c.end}`)).length,
  listWhole: listWhole.reduce((n, s) => n + s.doomed.length, 0),
  wholeDelete: whole.length,
};
say("\n  形态分布（实测 → 基线）：");
for (const [label, key] of [["摘 export 前缀", "inlinePrefix"], ["清单摘名字", "listName"],
  ["清单整行删", "listWhole"], ["整条删", "wholeDelete"]]) {
  say(`    ${label}：${shape[key]} → ${EXPECT[key]}${shape[key] === EXPECT[key] ? " ✓" : " ✗"}`);
  if (shape[key] !== EXPECT[key]) die(`形态「${label}」是 ${shape[key]} 处，实测基线是 ${EXPECT[key]} 处`);
}
say(`  整行删的清单（${listWhole.length} 条）：${listWhole.map((s) => `${s.tag}（${s.doomed.join("/")}）`).join("；")}`);
say(`  摘名字的清单（${listKept.length} 条）：${listKept.map((s) => `${s.tag} 摘 ${s.doomed.length}/${s.list.length}`).join("；")}`);

// ---------------------------------------------------------------------------
// ② 生成改动（每处内容锚定）
// ---------------------------------------------------------------------------

const pending = new Map();
const plan = [];
const note = (key, edit) => pending.set(key, [...(pending.get(key) || []), edit]);
/** 在**当前**文本上施加一处改动 → 新文本；定位不到返回 null（调用方当场失败）。 */
const applyEdit = (text, e) => (e.apply ? e.apply(text) : replaceOnce(text, e.anchor, e.to));
const add = (kind, where, what, b, a, edit) => {
  note(edit.key, edit);
  plan.push({ kind, where, what, before: b, after: a });
};

// ① inline：删 `export ` 前缀（保留缩进与行内注释，一字不动）
for (const c of inline) {
  const anchor = before.get(c.key).split("\n")[c.line - 1];
  add("① 摘 export 前缀", `${c.key}:${c.line}`, c.name, anchor.trim(),
    anchor.replace(/^([ \t]*)export\s+/, "$1").trim(),
    { kind: "摘 export 前缀", key: c.key, names: [c.name], entry: `${c.key}::${c.name}`,
      anchor, to: anchor.replace(/^([ \t]*)export\s+/, "$1"), apply: null });
}

// ③ 清单整行删（清空整条 `export {…}` 语句 + 其下紧跟的那一个空行）
//    上方整行注释**留下**——它们是本模块的说明，不是这一条清单的注脚。
for (const s of listWhole) {
  const raw = before.get(s.key).split("\n");
  const end = raw[s.end] !== undefined && raw[s.end].trim() === "" ? s.end + 1 : s.end;
  const text = before.get(s.key);
  const from = lineStart(text, s.line);
  const stop = lineStart(text, end + 1);
  add("③ 清单整行删", `${s.key}:${s.line}-${end}`, s.doomed.join(", "),
    `${end - s.line + 1} 行（第 ${s.line}-${end} 行）`, "（清空该 export 语句与该空行）",
    { kind: "清单整行删", key: s.key, names: s.doomed, entry: `${s.key}（${s.doomed.join(", ")}）`,
      anchor: text.slice(from, stop < 0 ? text.length : stop), to: "",
      apply: (t) => clearLines(t, s.line, end) });
}

// ② 清单摘名字（多行清单的逗号与缩进原样保留，只把那一项摘掉；同一清单的多个名字逐次现算）
for (const c of catalog.filter((x) => x.shape === "list" && listKept.some((s) => s.tag === `${x.key}:${x.line}-${x.end}`))) {
  const s = sites.get(`${c.key}:${c.line}-${c.end}`);
  add("② 清单摘名字", `${c.key}:${s.line}-${s.end}`, c.name, c.name, "（从清单里摘掉）",
    { kind: "清单摘名字", key: c.key, names: [c.name], entry: `${c.key}::${c.name}`,
      anchor: null, to: null, apply: (t) => dropListItem(t, c.name) });
}

// ④ 整条删 groupChoiceGap()（**不带注释块**——实测它上方没有属于自己的注释块：
//    紧邻上方是 `export let groupChoices` 那几行的行尾注释续行，属别的声明）
{
  const c = whole[0];
  const text = before.get(c.key);
  const raw = text.split("\n");
  const bodyEnd = functionEndLine(text, c.line);
  const end = raw[bodyEnd] !== undefined && raw[bodyEnd].trim() === "" ? bodyEnd + 1 : bodyEnd;
  const from = lineStart(text, c.line);
  const stop = lineStart(text, end + 1);
  add("④ 整条删函数", `${c.key}:${c.line}-${end}`, `${c.name}()`,
    `${end - c.line + 1} 行（第 ${c.line}-${end} 行）`,
    "（删掉；零引用，语义由同文件 groupChoiceGapMessage 覆盖；上方无专属注释块）",
    { kind: "整条删函数", key: c.key, names: [c.name], entry: `${c.key}::${c.name}`,
      anchor: text.slice(from, stop < 0 ? text.length : stop), to: "", apply: null });
}

/** 施加当前全部改动 → **整张**模块表（没改过的模块原样带过来，判据要的是完整页面图）。 */
function stage(edits) {
  const out = new Map(before);
  for (const [key, list] of edits) {
    let text = before.get(key);
    for (const e of list) {
      const next = applyEdit(text, e);
      if (next === null) die(`${e.entry} 在 ${key} 的当前文本里定位不到`);
      text = next;
    }
    out.set(key, text);
  }
  return out;
}

// ⑤ / ⑤-b **不动点**扫描：一轮一轮地找"本轮改动**连带**出来的"两类东西，直到不再新增：
//
//   A. **孤儿 import**：改动前有人用、改动后没人用的具名 import。
//      判据用仓库自己的 `unusedImports` 本体（`tests/js/import-usage.mjs`），
//      **不是"只扫我摘过的那些名字"**——整条删（④）也会把别人带死：
//      实测 `ui/generate-recommend.js` 的 `pendingGroupChoices` 唯一调用者就是被④删掉的
//      `groupChoiceGap()`，它压根不在"被摘的导出名"名单里（双轴评审抓出的硬违规：
//      第一版按 `swept.has(name)` 过滤 → 漏检 → 清点自造出一条死 import）。
//   B. **级联的零消费者导出**：摘掉一条转手再导出之后，被再导出的那个名字可能就没人用了。
//      实测只有 `ui/fix-center-core.js::fixLoop`（原消费者 = `ui/generate-fix.js:47`）。
//
//   "改动前就没人用"的 import（实测 10 处，`WRITE_GUARD_ACTIONS` ×4 等）**不碰**——
//   它们不在判据 D 的 111 处清单里、也不由本轮造成，如实记进 `staleImports`。
//
//   为什么要不动点而不是两趟：④ 删的是正文，它能带死的 import 与"被摘的导出名"没有交集，
//   单趟扫描天然覆盖不到；改成循环后，新加进来的编辑会再被扫一遍，直到稳定。
const followUps = [];
const cascades = [];
const staleImports = [];
const MAX_ROUNDS = 8;
for (let round = 1; round <= MAX_ROUNDS; round++) {
  const staged = stage(pending);
  const entries = [...staged.entries()].map(([key, text]) => ({ key, text }));
  let added = 0;

  // A. 改动前有人用、改动后没人用的具名 import
  for (const key of [...pending.keys()].sort()) {
    const deadBefore = new Set(unusedImports(before.get(key)).flatMap((p) => p.unused));
    const deadAfter = unusedImports(staged.get(key)).flatMap((p) => p.unused);
    for (const name of deadAfter) {
      if (deadBefore.has(name)) {
        if (!staleImports.some((s) => s.key === key && s.name === name)) staleImports.push({ key, name });
        continue;
      }
      const edge = parseModuleImports(before.get(key))
        .find((e) => e.names.includes(name) && !/^export/.test(e.raw.trimStart()));
      if (!edge) die(`${key} 的 ${name} 被判未使用，但找不到它来自哪条 import`);
      const local = edge.locals[edge.names.indexOf(name)];
      const rest = (maskCommentsAndStrings(staged.get(key))
        .match(new RegExp(`(?<![\\w$.])${esc(local)}(?![\\w$])`, "g")) || []).length;
      if (rest !== 1) die(`${key} 的 ${name}（本地名 ${local}）在改动后的正文里还出现 ${rest} 次`);
      add("⑤ 摘孤儿 import", `${key}:${edge.line}`, name,
        edge.raw.replace(/\s+/g, " ").trim(),
        `{ ${edge.names.filter((n) => n !== name).join(", ")} } from "${edge.spec}"`,
        { kind: "摘孤儿 import", key, names: [name], entry: `${key} 的 import "${edge.spec}" 里的 ${name}`,
          anchor: null, to: null, apply: (t) => dropImportName(t, edge, name) });
      followUps.push({ key, spec: edge.spec, name });
      added++;
    }
  }

  // B. 新暴露出来的零消费者导出（判据必须喂**整张**页面模块表——少喂一个模块会整片假红）
  for (const v of unconsumedExports(entries, consumers)) {
    if (violations.some((o) => o.key === v.key && o.name === v.name)) continue;   // 原有 111 处，不管
    if (!(v.key === "ui/fix-center-core.js" && v.name === "fixLoop")) {
      die(`级联超出实测范围：${v.key}::${v.name} 也是新暴露的零消费者导出 —— 需要人工定夺`);
    }
    const text = staged.get(v.key);
    const line = maskCommentsAndStrings(text).split("\n")
      .findIndex((l) => new RegExp(`^[ \\t]*export\\s+(?:async\\s+)?(?:function|class|const|let|var)\\s+${esc(v.name)}(?![\\w$])`).test(l));
    if (line < 0) die(`${v.key}::${v.name} 是级联出来的零消费者导出，但不是 inline 声明形态`);
    const anchor = text.split("\n")[line];
    add("⑤-b 级联摘 export", `${v.key}:${line + 1}`, v.name, anchor.trim(),
      anchor.replace(/^([ \t]*)export\s+/, "$1").trim(),
      { kind: "摘 export 前缀", key: v.key, names: [v.name], entry: `${v.key}::${v.name}（级联）`,
        anchor, to: anchor.replace(/^([ \t]*)export\s+/, "$1"), apply: null });
    cascades.push({ key: v.key, name: v.name, line: line + 1 });
    added++;
  }

  say(`  · 不动点第 ${round} 轮：连带改动 +${added}`);
  if (added === 0) break;
  if (round === MAX_ROUNDS) die(`不动点扫描 ${MAX_ROUNDS} 轮还没稳定 —— 停下来人工看`);
}

say("\n== ② 预期副作用 ==");
say(`  孤儿 import（改动前有人用、改动后没人用）：${followUps.length} 处`);
for (const f of followUps) say(`    · ${f.key}：从 "${f.spec}" 只取了 ${f.name} → 连 import 一起摘`);
say(`  级联（摘再导出后新暴露的零消费者导出）：${cascades.length} 处`);
for (const c of cascades) say(`    · ${c.key}:${c.line} 的 ${c.name} —— 原消费者是 ui/generate-fix.js:47 那条转手再导出`);
if (staleImports.length) {
  say(`  如实记账（**本轮不动**）：另有 ${staleImports.length} 处 import 在本轮之前就已经是死的`
    + "（不在判据 D 的 111 处清单里，也不由本轮造成；`import-usage-guard` 的取数面只有 boot.js，故至今无人报）");
  for (const s of staleImports) say(`    · ${s.key} → ${s.name}`);
}

// ---------------------------------------------------------------------------
// ③ 锚定校验 → 应用 → 逐处自校验（全部在内存；任何一条不过就整体不写盘）
// ---------------------------------------------------------------------------

say("\n== ③ 逐处锚定 ==");
for (const [key, edits] of [...pending.entries()].sort()) {
  for (const e of edits) {
    if (e.anchor === null) continue;                         // 清单/import 形态按当前文本现算
    const hits = before.get(key).split(e.anchor).length - 1;
    if (hits !== 1) die(`${e.entry} 的锚文本在 ${key} 原文里出现 ${hits} 次（必须恰好 1 次）`);
    if (e.anchor === e.to) die(`${e.entry} 的锚点没带来任何变化`);
  }
}
const after = stage(pending);
say(`  ✓ ${plan.length} 处改动全部唯一命中（${pending.size} 个模块；存死锚点的形态按原文一次命中，`
  + "清单/import 形态按当前文本现算）");
for (const [key, edits] of pending) {
  for (const e of edits) {
    if (e.kind !== "摘 export 前缀") continue;
    if (e.to !== e.anchor.replace(/^([ \t]*)export\s+/, "$1")) die(`${e.entry}：替换结果与预期不符`);
  }
}
say(`  ✓ ${plan.length} 处改动逐处自校验通过（每一处都恰好是"删掉那个 export / import"的样子）`);

// ④ 归一化比对：唯一例外是工单明令整条删的那个函数，单独记账单独核验
say("\n== ④ 行为零变化：正文比对 ==");
const EXCEPT = new Set(whole.map((c) => c.key));
say(`  例外（工单明令整条删，正文确有删除）：${[...EXCEPT].map((k) => `${k}::${whole[0].name}()`).join("；")}`);
const bodyDiffs = [...before.keys()].filter((k) => !EXCEPT.has(k))
  .filter((k) => normalizeBody(before.get(k)) !== normalizeBody(after.get(k)));
for (const k of bodyDiffs) {
  say(`  ✗ ${k} 的正文也变了 —— ${explainDiff(normalizeBody(before.get(k)).split("\n"),
    normalizeBody(after.get(k)).split("\n")).join("；")}`);
}
if (bodyDiffs.length) die("正文变化 = 不止动了导出面/导入面，拒绝写盘");
for (const key of EXCEPT) {
  const residue = identRe(whole[0].name).test(maskCommentsAndStrings(after.get(key)));
  say(`  例外核验：${key} 里 \`${whole[0].name}\` ${residue ? "仍有残迹（✗）" : "已整条删干净（✓）"}`);
  if (residue) die(`${key} 里还留着 ${whole[0].name} 的残迹`);
}
say(`  ✓ 其余 ${before.size - EXCEPT.size} 个模块剥掉 import/export 边语句后**逐字节相同**（正文零变化、零丢失）`);

// ⑤ 落盘（行尾与尾部换行按清点前逐字节还原）
say("\n== ⑤ 落盘 ==");
const final = new Map([...after].map(([k, t]) => [k, restoreLineEndings(t, before.get(k))]));
const touched = [...pending.keys()].sort();
let lineDelta = 0;
for (const key of touched) {
  const bodyOf = (s) => lf(s).replace(/\n+$/, "").split("\n").length;
  const b = bodyOf(before.get(key));
  const a = bodyOf(final.get(key));
  lineDelta += a - b;
  say(`  ${key}：${b} → ${a} 行（${a - b >= 0 ? "+" : ""}${a - b}）`);
  if (a > b) die(`${key} 行数增加了（只许减）`);
  if (trailingEol(final.get(key)) !== trailingEol(before.get(key))) {
    die(`${key} 的尾部换行数变了（前 ${trailingEol(before.get(key))} / 后 ${trailingEol(final.get(key))}）`);
  }
  // 行尾还原的**幂等性**：`final` 已经过 `restoreLineEndings`，再还原一次不该有任何变化
  // （第一版拿 `lf(final)` 去比，等于拿 LF 版比 CRLF 版，永远不相等——是断言写错，不是还原写错）
  if (restoreLineEndings(final.get(key), before.get(key)) !== final.get(key)) {
    const a = final.get(key);
    const b = restoreLineEndings(a, before.get(key));
    let i = 0;
    while (i < Math.min(a.length, b.length) && a[i] === b[i]) i++;
    die(`${key} 的行尾还原不是幂等的（首个不同处：下标 ${i}`
      + `｜现「${JSON.stringify(a.slice(Math.max(0, i - 20), i + 20))}」`
      + `｜再还原「${JSON.stringify(b.slice(Math.max(0, i - 20), i + 20))}」）`);
  }
}
say(`  合计行数变化：${lineDelta}（只减不增）；行尾写法与尾部换行数逐文件还原 ✓`);
// 行尾判法见 `eolOf`（**必须在 `lf()` 之前调**）。这里也顺手把全仓分布打出来，
// 好让"为什么必须逐文件还原"这件事在读数里看得见。
const eolStyle = eolOf;
const styleDrift = touched.filter((k) => eolStyle(final.get(k)) !== eolStyle(before.get(k)));
say(`  本批改动文件里：${touched.filter((k) => eolStyle(before.get(k)) === "\r\n").length} 个 CRLF / `
  + `${touched.filter((k) => eolStyle(before.get(k)) === "\n").length} 个 LF；`
  + `还原后不一致：${styleDrift.length ? styleDrift.join(", ") : "0 个"}`);
if (styleDrift.length) die(`这些文件的行尾写法变了：${styleDrift.join(", ")}`);
// 仓库确实混着两种行尾（实测：CRLF 检出下 51 个 CRLF、LF 归一后 0 个），所以"逐字节还原"
// 必须**逐文件**按工作树原文判，别按全仓统一处理。（另外工作树是 CRLF 的那批在 git 对象里存的是
// LF——`core.autocrlf=true`——所以比对得按工作树那一份。）
const lfOnes = [...before.entries()].filter(([, t]) => eolStyle(t) === "\n").map(([k]) => k);
say(`  全仓 ${before.size} 个模块的行尾：LF ${lfOnes.length} 个 / CRLF ${before.size - lfOnes.length} 个`);
const bridgeTouched = [...pending.entries()]
  .filter(([, edits]) => edits.some((e) => /Object\.assign\(window/.test(e.anchor || "")))
  .map(([key]) => key);
say(`  window 探针桥（\`Object.assign(window, {…})\`）改动：${bridgeTouched.length ? bridgeTouched.join(", ") : "零改动"}`);
say("  index.html / 555 个 id：零改动（本轮只碰 static/js）");
if (DRY) say("  （--dry-run：不写盘）");
else {
  // 行尾归一：仓库存储是 LF，但本机 `core.autocrlf=true` 把检出物变成 CRLF，而**两条前端
  // "源码形态"用例按字面 LF 断言源码**（`ai-action-refs.test.mjs:138` /
  // `module-intro-detail.test.mjs:166`）→ CRLF 检出下必红（纯净克隆实测：CRLF 1677/2、LF 1679/0，
  // 见工单 Comments ⑥）。清点本身已按原文逐文件还原行尾，这里**额外**把改动涉及的文件归一成 LF，
  // 使落盘形态与 `git show` 本来一致，本地门禁不再受检出副作用影响（git 归一化后内容不变）。
  let normalized = 0;
  for (const key of touched) {
    const eol = eolOf(final.get(key));
    const text = eol === "\r\n" ? final.get(key).split("\r\n").join("\n") : final.get(key);
    if (eol === "\r\n") {
      final.set(key, text);
      normalized++;
    }
    writeFileSync(abs(key), text, "utf8");
  }
  say(`  已写 ${touched.length} 个文件：${touched.join(", ")}`);
  say(`  行尾归一（CRLF → LF，对齐仓库存储形态与那两条字面 LF 用例）：${normalized} 个文件`);
}

// ---------------------------------------------------------------------------
// ⑥ 复跑判据
// ---------------------------------------------------------------------------

const finalEntries = [...final.entries()].map(([key, text]) => ({ key, text }));
const modules = finalEntries.filter((e) => e.key !== "boot.js");
const rootText = final.get("boot.js");
const nowD = unconsumedExports(finalEntries, consumers);
const nowT = nonFunctionCallees(finalEntries);
const nowStars = starImports(finalEntries, consumers);
const nowFace = exportFaceProblems(finalEntries, consumers);
const breaks = graphBreaks(finalEntries);
const wiring = wiringViolations(rootText, modules);
const { orphans } = reachable(rootText, modules);
const registry = registryProblems(rootText, modules);
const unused = unusedImports(rootText).length;
// 模块级未使用具名：`import-usage-guard` 的取数面**只有 boot.js**，所以"装载根 0 处"对模块级
// 没有证明力（双轴评审点出的口径错配）。清点自己必须把口径补全：改动前的模块级死 import
// 不计（不由本轮造成），但**改动后不许比改动前多**——这一条兜住"清点自造死 import"。
const moduleDead = (texts) => [...texts.entries()]
  .filter(([key]) => key !== "boot.js")
  .flatMap(([key, text]) => unusedImports(text).flatMap((p) => p.unused.map((n) => `${key}::${n}`)));
const deadBeforeList = moduleDead(before);
const deadAfterList = moduleDead(final);
const newDeadImports = deadAfterList.filter((x) => !deadBeforeList.includes(x));
const exportsAfter = finalEntries.reduce((n, e) => n + parseModuleExports(e.text).size, 0);
const stillRed = violations.filter((v) => nowD.some((n) => n.key === v.key && n.name === v.name));

say(`\n== ⑥ 复跑判据（${DRY ? "dry-run 内存结果" : "已落盘的工作树"}）==`);
say(`  判据 D 零消费者导出：${nowD.length} 处${nowD.length ? " —— " + nowD.slice(0, 10).map((v) => `${v.key}::${v.name}`).join(", ") : "（0 = 目标达成）"}`);
say(`  逐处销账：清点前 ${violations.length} 处 → 仍红 ${stillRed.length} 处${stillRed.length ? " —— " + stillRed.map((v) => `${v.key}::${v.name}`).join(", ") : ""}`);
say(`  判据 T 形态违规：${nowT.length} 处`);
say(`  星号导入体检：${nowStars.length} 处`);
say(`  取数面体检：${nowFace.length ? nowFace.join("；") : "无问题"}`);
say(`  graphBreaks（全图 import↔export 对账）：${breaks.length} 处${breaks.length ? " —— " + JSON.stringify(breaks.slice(0, 5)) : "（绿）"}`);
say(`  wiringViolations：${wiring.length} 处${wiring.length ? " —— " + JSON.stringify(wiring.slice(0, 3)) : "（绿）"}`);
say(`  registryProblems：${registry.length} 处${registry.length ? " —— " + JSON.stringify(registry.slice(0, 3)) : "（登记体检绿）"}`);
say(`  reachable 掉队模块：${orphans.length} 个${orphans.length ? " —— " + orphans.join(", ") : "（绿）"}`);
say(`  import-usage（装载根 boot.js）：${unused} 处未使用具名`);
say(`  模块级未使用具名（全 132 个模块，清点前 ${deadBeforeList.length} 处 → 清点后 ${deadAfterList.length} 处）：`
  + `${newDeadImports.length ? "清点自造了 " + newDeadImports.join(", ") + "（✗）" : "本轮未新增"}`);
say(`  导出条目总数：${exportsBefore} → ${exportsAfter}（减少 ${exportsBefore - exportsAfter}）`);

const ok = nowD.length === 0 && nowT.length === 0 && nowStars.length === 0 && nowFace.length === 0
  && breaks.length === 0 && wiring.length === 0 && registry.length === 0
  && stillRed.length === 0 && orphans.length === 0 && unused === 0 && bodyDiffs.length === 0
  && newDeadImports.length === 0;

say(`\n== ⑦ 逐处改动清单（${plan.length} 处）==`);
for (const p of plan) say(`  ${p.kind}  ${p.where}  ${p.what}\n      前：${p.before}\n      后：${p.after}`);

say("\n== 结论 ==");
say(`  判据 D：${violations.length} → ${nowD.length}${nowD.length === 0 ? "（0 = 清点完成）" : "（未达成）"}`);
say(`  其余判据（T / 星号 / 取数面 / graphBreaks / wiring / registry / reachable / import-usage）：`
  + `${[nowT, nowStars, nowFace, breaks, wiring, registry, orphans, unused]
    .every((x) => (Array.isArray(x) ? x.length : x) === 0) ? "全绿" : "有红（见上）"}`);
say(`  改动分类（按**名字**数）：摘 export ${shape.inlinePrefix + shape.listName + shape.listWhole + cascades.length} 个`
  + `（前缀 ${shape.inlinePrefix} + 清单摘名字 ${shape.listName} + 清单整行删 ${shape.listWhole}`
  + ` + 级联 ${cascades.length}）、整条删 ${shape.wholeDelete} 个、孤儿 import ${followUps.length} 个`);
say(ok ? "\nPASS" : "\nFAIL");

writeFileSync(OUT, lines.join("\n") + "\n", "utf8");
console.log(`\n读数落档：${OUT}`);
process.exitCode = ok ? 0 : 1;
