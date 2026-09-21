// wrap-wiring.mjs — 把模块的**求值期接线语句**搬进导出的 init*()（工单 frontend-boot-module/04）。
//
// 为什么要脚本：这 6 个模块的接线是**散落**的（master 6 处、generate-core 12 处），手抄
// 156 行语句必出错。脚本做三件事，且自带自校验：
//   1. 用判据单源（tests/js/boot-contract.mjs 的 `wiringEffects` + 掩码器）找出"列 0 的
//      非声明副作用语句"，再把每条语句的**完整范围**算出来（按括号配平扫到平衡为止，
//      字符串/注释先掩掉，所以 `$("x").on("...")` 里的括号不会算错）；
//   2. 每条语句连同**紧邻其上的注释行**（中间不隔空行）一起搬走——注释是它的解释，留下会错位；
//   3. 按文件顺序拼进 `export function <init>() { … }`，插在文件末尾（函数声明提升，
//      引用不受位置影响；调用时机由装载根决定）。
//
// 自校验（任一不成立就不写盘）：搬走的块"去掉缩进"后与原文件逐字相同；搬完 `wiringEffects`
// 必须为 0；文件里不得已经存在同名 init。
//
// 用法：
//   node .scratch/frontend-boot-module/wrap-wiring.mjs <模块相对路径> <init 名> --dry-run
//   node .scratch/frontend-boot-module/wrap-wiring.mjs <模块相对路径> <init 名> --write
//   加 --doc "一句话" 覆盖默认 doc 注释。
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { maskCommentsAndStrings, topLevelEffects, wiringEffects } from "../../tests/js/boot-contract.mjs";

const REPO = fileURLToPath(new URL("../../", import.meta.url));
const [rel, initName, ...rest] = process.argv.slice(2);
const write = rest.includes("--write");
const doc = rest.includes("--doc") ? rest[rest.indexOf("--doc") + 1] : "接线：由装载根 boot.js 显式调用（工单 frontend-boot-module/04）";
if (!rel || !initName || (!write && !rest.includes("--dry-run"))) {
  console.error("用法：wrap-wiring.mjs <模块相对路径> <init 名> --dry-run|--write [--doc …]");
  process.exit(2);
}

const PATH = REPO + rel;
const src = readFileSync(PATH, "utf8");
if (src.includes(`export function ${initName}(`)) { console.error(`✗ ${rel} 里已经有 ${initName}()`); process.exit(1); }
const lines = src.split("\n");
const masked = maskCommentsAndStrings(src).split("\n");

/** 从第 i 行（0 基）起，按括号配平找这条语句的结束行（含）。 */
function statementEnd(i) {
  let depth = 0;
  let started = false;
  for (let j = i; j < masked.length; j++) {
    for (const ch of masked[j]) {
      if (ch === "(" || ch === "{" || ch === "[") { depth++; started = true; }
      else if (ch === ")" || ch === "}" || ch === "]") depth--;
    }
    if (started && depth <= 0) return j;
  }
  return i;
}

// ---- 1. 找出全部接线语句（按行号升序）----
// 判据单源：`wiringEffects` 就是"真接线"（已排除探针桥）——这里不再自己 .filter(!bridge)。
const effects = wiringEffects(src);
const blocks = [];
for (const eff of effects) {
  const startLine = eff.line - 1;
  const endLine = statementEnd(startLine);
  // 紧邻其上的注释行（中间不隔空行）一起搬
  let head = startLine;
  while (head - 1 >= 0 && lines[head - 1].trim().startsWith("//")
    && (blocks.length === 0 || head - 1 > blocks[blocks.length - 1].end)) head--;
  blocks.push({ start: head, end: endLine, first: lines[startLine].trim().slice(0, 70) });
}
// 合并重叠块（同一区域的相邻语句）
const merged = [];
for (const b of blocks) {
  const last = merged[merged.length - 1];
  if (last && b.start <= last.end + 1) last.end = Math.max(last.end, b.end);
  else merged.push({ ...b });
}

// ---- 2. 生成新文件 ----
const removed = new Set();
for (const b of merged) for (let i = b.start; i <= b.end; i++) removed.add(i);
const kept = lines.filter((_, i) => !removed.has(i));
// 去掉被搬走区域留下的连续空行（最多留一个）
const compact = [];
for (const line of kept) {
  if (!line.trim() && !compact[compact.length - 1]?.trim()) continue;
  compact.push(line);
}
const bodyBlocks = merged.map((b) => lines.slice(b.start, b.end + 1));
const indentedBlocks = bodyBlocks.map((blk) => blk.map((l) => (l.trim() ? "  " + l : l)));
const body = [];
indentedBlocks.forEach((blk, n) => {
  if (n) body.push("");                               // 块之间留一个空行
  body.push(...blk);
});
const block = [
  "",
  "/**",
  ` * ${doc}`,
  " * 语句顺序 = 原文件里的先后顺序；绑定的 target 与事件类型一字未改。",
  " */",
  `export function ${initName}() {`,
  ...body,
  "}",
  "",
];
const outLines = [...compact, ...block];
const outText = outLines.join("\n");

// ---- 3. 自校验（**查产物**，不是自证）----
//
// 先前一版把 `movedOriginal`（块数组）与"块数组加两格缩进再减两格"比较——那是恒等式，
// 永远为真（工单 04 评审抓出来的）。现在改成**从生成的文本里重新抠出函数体**再比：
// 装配环节一旦粘错块 / 丢行 / 插错空行，这里立刻红。
const problems = [];
const sigIdx = outLines.findIndex((l) => l === `export function ${initName}() {`);
let closeIdx = -1;
for (let i = outLines.length - 1; i > sigIdx; i--) if (outLines[i] === "}") { closeIdx = i; break; }
if (sigIdx < 0 || closeIdx < 0) {
  problems.push("产物里找不到 init 函数体（签名或收尾 } 丢了）");
} else {
  const bodyFromText = outLines.slice(sigIdx + 1, closeIdx)
    .filter((l) => l.trim())                       // 去掉块之间插入的空行
    .map((l) => (l.startsWith("  ") ? l.slice(2) : l));
  const originalBlocks = bodyBlocks.flat().filter((l) => l.trim());   // 同样忽略块内空行
  if (bodyFromText.join("\n") !== originalBlocks.join("\n")) {
    problems.push(`产物里的函数体与原文块不一致（产物 ${bodyFromText.length} 行 vs 原文 ${originalBlocks.length} 行）`);
  }
}
const left = wiringEffects(outText);
if (left.length) problems.push(`搬完仍有 ${left.length} 条求值期接线（第 ${left[0].line} 行起）`);

console.log(`${rel} → ${initName}()`);
console.log(`  接线语句 ${effects.length} 条，合并成 ${merged.length} 块：`);
for (const b of merged) console.log(`    ${String(b.start + 1).padStart(4)}–${String(b.end + 1).padStart(4)} 行  ${b.first}`);
console.log(`  文件：${lines.length} → ${outLines.length} 行`);
if (problems.length) {
  console.error("✗ 自校验不通过，拒绝写盘：");
  for (const p of problems) console.error("  · " + p);
  process.exit(1);
}
console.log("  ✓ 自校验通过");
if (!write) { console.log("（--dry-run：没有写盘）"); process.exit(0); }
writeFileSync(PATH, outText, "utf8");
console.log("  已写入");
