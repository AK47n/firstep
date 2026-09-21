// probe-03-diff-proof.mjs — 独立机械证据：`git diff` 逐行**归因** ＋ 行尾/尾换行**逐字节**（工单 02）。
//
// 与 apply-removal 的自述**独立**：本件只看 `git diff --unified=0` 的 hunk 形状与 base/工作树的字节，
// 不读任何执行器的中间数据。
//
// 判据（全部硬判，任一不成立即非零退出）：
//   ① 每个 hunk 必须归得了因：
//      **摘名** —— 一个 `-` 行与一个 `+` 行只差一段连续文本，且**存在**一种切法让那段 = 分隔符+标识符；
//      **级联** —— 同上，而那段恰好是 `export `；
//      **整条删** —— 只有 `-` 行、没有 `+` 行，且被删的行**落在 base 某条 import 语句的区间里**；
//   ② 行尾与尾部换行逐字节不变：
//      **EOF 末尾字节序列**必须逐字节相同；LF/CRLF 的**计数差**必须正好等于被整行删掉的行数
//      （改写的行不增减换行）—— 口径与工单 02 §③ 的教训一致：不许用归一化把差异抹掉。
import { execFileSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { parseModuleImports } from "../../tests/js/boot-contract.mjs";

const BASE = "f1c9e1c7";
const REPO = fileURLToPath(new URL("../../", import.meta.url));
const lines = [];
const say = (s = "") => { lines.push(s); console.log(s); };

const changed = execFileSync("git", ["diff", "--name-only", BASE], { cwd: REPO, encoding: "utf8" })
  .split("\n").map((s) => s.trim()).filter(Boolean)
  // 只看**产品面**（static/js）：base 上还没有 .scratch/module-import-usage/ 与 01 的判据改动
  .filter((p) => p.startsWith("src/contest_generator/static/js/"));

const hunksOf = (path) => {
  const out = execFileSync("git", ["diff", "--unified=0", "--no-color", BASE, "--", path], { cwd: REPO, encoding: "utf8" });
  const hunks = [];
  let cur = null;
  for (const line of out.split("\n")) {
    if (line.startsWith("@@")) { cur = { minus: [], plus: [] }; hunks.push(cur); continue; }
    if (!cur || line.startsWith("---") || line.startsWith("+++")) continue;
    if (line.startsWith("-")) cur.minus.push(line.slice(1));
    else if (line.startsWith("+")) cur.plus.push(line.slice(1));
  }
  return hunks;
};

/**
 * 从 `a` 删掉一段连续文本得到 `b` 的**所有**切法 → [被删的那段…]。
 *
 * 为什么不能只取"最长公共前缀/后缀"那一种切法：删掉的名字常与**后一个名字共享前缀**
 *（`pdfDupRemainText, pdfTrashBodyHTML`、`resourcesToolbarHTML, resourceTaskColorMap`），
 * 那种切法会给出 `DupRemainText, pdf` 这种跨过名字边界的假切口 → 分类器认不出。
 * 这里对每个起点 `i` 直接解出唯一的终点（`j = a.length - b.slice(i).length`），
 * 于是"真切口"一定在候选里，由分类器按形状挑。
 */
function removedSpans(a, b) {
  const out = [];
  for (let i = 0; i <= Math.min(a.length, b.length); i++) {
    if (a.slice(0, i) !== b.slice(0, i)) break;      // 前缀一旦不匹配，再往后的 i 都不可能
    const rem = b.slice(i);
    const j = a.length - rem.length;
    if (j > i && a.slice(j) === rem) out.push(a.slice(i, j));
  }
  return out;
}

const counts = { "未改动老行": 0, "摘名": 0, "整行摘名": 0, "整条删": 0, "级联": 0 };
const unattributed = [];
say(`=== git diff 逐行归因（base ${BASE} → 工作树）===`);
say(`改动文件：${changed.length} 个（只看产品面 src/contest_generator/static/js/）`);
say("");
for (const path of changed) {
  const baseText = execFileSync("git", ["show", `${BASE}:${path}`], { cwd: REPO, encoding: "utf8" });
  const newText = readFileSync(`${REPO}${path}`, "utf8");
  // **口径：看语句，不看 hunk 形状**——`-` 行没有 `+` 行不等于"整条语句没了"：
  // 多行具名清单里"名字独占一行"被删掉时，也是只有 `-` 行，但语句还活着（= 整行摘名）。
  const baseStmts = parseModuleImports(baseText).length;
  const newStmts = parseModuleImports(newText).length;
  const droppedStatements = baseStmts - newStmts;
  if (droppedStatements < 0) unattributed.push(`${path}: 语句数变多了（${baseStmts} → ${newStmts}）`);
  const importSpans = parseModuleImports(baseText).map((e) => {
    const at = baseText.indexOf(e.raw);
    return [at, at + e.raw.length];
  });
  const hunks = hunksOf(path);
  const kinds = [];
  let removedLines = 0;
  for (const h of hunks) {
    if (h.minus.length && !h.plus.length) {
      removedLines += h.minus.length;
      // 被删的行必须落在 base 某条 import 语句的区间里（否则整条删吃掉了别的东西）
      let cursor = 0;
      let ok = true;
      for (const l of h.minus) {
        const at = baseText.indexOf(l, cursor);
        if (at < 0 || !importSpans.some(([s, e]) => at >= s && at < e)) { ok = false; break; }
        cursor = at + l.length;
      }
      if (!ok) { unattributed.push(`${path}: 只有 - 的 hunk 不落在任何 import 语句里：${JSON.stringify(h.minus[0])}`); continue; }
      // 语句数少了 → 整条语句没删；否则是"名字独占一行"的整行摘名
      const kind = droppedStatements > 0 ? "整条删" : "整行摘名";
      counts[kind]++; kinds.push(kind);
      continue;
    }
    if (h.minus.length === h.plus.length) {
      for (let i = 0; i < h.minus.length; i++) {
        const spans = removedSpans(h.minus[i], h.plus[i]);
        if (!spans.length) { unattributed.push(`${path}: 这两行不是"只删一段连续文本"：\n    - ${h.minus[i]}\n    + ${h.plus[i]}`); continue; }
        const cascade = spans.some((s) => s.trim() === "export") && h.minus[i].includes("function downloadedPercent(");
        const named = spans.some((s) => /^[,\s]*[\w$]+[,\s]*$/.test(s));
        if (cascade) { counts["级联"]++; kinds.push("级联"); }
        else if (named) { counts["摘名"]++; kinds.push("摘名"); }
        else { unattributed.push(`${path}: 删掉的那段既不是分隔符+标识符、也不是 export：${JSON.stringify(spans)}`); }
      }
      continue;
    }
    unattributed.push(`${path}: 这 hunk 归不了因（-${h.minus.length} / +${h.plus.length}）`);
  }
  const baseLines = baseText.split("\n");
  counts["未改动老行"] += baseLines.length - hunks.reduce((n, h) => n + h.minus.length, 0);
  say(`  ${path.replace("src/contest_generator/static/js/", "")}  语句 ${baseStmts} → ${newStmts}`
    + ` / 老行 ${baseLines.length - hunks.reduce((n, h) => n + h.minus.length, 0)}`
    + ` / 只有 - 的行 ${removedLines} / ${kinds.join(" + ") || "（无改写）"}`);
}
say("");
say("归因：");
for (const [k, v] of Object.entries(counts)) say(`  ${k} ${v}`);
/** 与 spec「处置规则」逐条对齐（11 摘名 ＋ 1 整条删 ＋ 1 级联）——**钉死**，不是只打印。 */
const PINNED = { "摘名": 11, "整条删": 1, "级联": 1 };
const nameTotal = counts["摘名"] + counts["整行摘名"];
for (const [k, v] of Object.entries(PINNED)) {
  const got = k === "摘名" ? nameTotal : counts[k];
  if (got !== v) unattributed.push(`分类计数与 spec 处置表不一致：${k} 实得 ${got}，应得 ${v}`);
}
say(`  （口径：**摘名 = ${nameTotal}**，其中 ${counts["摘名"]} 处摘同行的名字、${counts["整行摘名"]} 处删"名字独占的一行"；`
  + `整条删 = ${counts["整条删"]}；级联 = ${counts["级联"]}）`);
say(`**归不了因的差异：${unattributed.length} 处**`);
for (const u of unattributed) say(`  ✗ ${u}`);
say("");

// ── 行尾与尾部换行：逐字节（EOF 字节序列必须相同；换行计数差必须正好等于整行删掉的行数）
say("=== 行尾写法与尾部换行（逐文件逐字节）===");
let tailBad = 0;
for (const path of changed) {
  const baseBytes = execFileSync("git", ["cat-file", "blob", `${BASE}:${path}`], { cwd: REPO, encoding: "buffer" });
  const newBytes = readFileSync(`${REPO}${path}`);
  const tail = (b) => b.subarray(-6).toString("hex");
  const count = (b, re) => (b.toString("utf8").match(re) || []).length;
  const baseCrlf = count(baseBytes, /\r\n/g);
  const baseLf = count(baseBytes, /(?<!\r)\n/g);
  const newCrlf = count(newBytes, /\r\n/g);
  const newLf = count(newBytes, /(?<!\r)\n/g);
  const droppedLines = hunksOf(path).reduce((n, h) => (h.plus.length ? n : n + h.minus.length), 0);
  const eolOk = baseCrlf === newCrlf && baseLf - newLf === droppedLines;
  const tailOk = tail(baseBytes) === tail(newBytes);
  if (!eolOk || !tailOk) tailBad++;
  say(`  ${eolOk && tailOk ? "PASS" : "FAIL"}  ${path.replace("src/contest_generator/static/js/", "")}`
    + `  末 6 字节 ${tail(baseBytes)} → ${tail(newBytes)}`
    + `  换行 ${baseCrlf} CRLF + ${baseLf} LF → ${newCrlf} CRLF + ${newLf} LF（整行删 ${droppedLines} 行）`);
}
say(`**尾部换行/行尾不一致的文件：${tailBad} 个**`);
say("");
const pass = unattributed.length === 0 && tailBad === 0;
say(pass ? "**diff 归因：PASS**" : "**diff 归因：FAIL**");
writeFileSync(fileURLToPath(new URL("./diff-proof.txt", import.meta.url)), lines.join("\n") + "\n", "utf8");
process.exit(pass ? 0 : 1);
