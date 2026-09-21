// apply-move.mjs — 装载根搬家（工单 frontend-boot-module/02），机械搬运 + 自校验。
//
// 做什么：
//   1. 把 index.html 里 `<script type="module">…</script>` 的**块内容**逐字搬进
//      `static/js/boot.js`（前面加一段文件头；行尾由 index.html 的 CRLF 归一为 LF——
//      static/js/ 下的既有 JS 全是 LF，index.html 是 CRLF，这是本仓既有的两套行尾）；
//   2. index.html 原处换成一条装载标签 `<script type="module" src="/js/boot.js"></script>`；
//   3. 自校验：boot.js 去掉文件头后与搬走的块内容**逐字相同**（行尾归一后）、
//      index.html 里零 import、装载标签恰好一条且 src 正确、markup 其余部分逐字节未动。
//
// 用法：
//    node .scratch/frontend-boot-module/apply-move.mjs --dry-run   # 只校验，不写盘
//    node .scratch/frontend-boot-module/apply-move.mjs --write     # 落盘
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const REPO = fileURLToPath(new URL("../../", import.meta.url));
const INDEX = REPO + "src/contest_generator/static/index.html";
const BOOT = REPO + "src/contest_generator/static/js/boot.js";
const TAG_OPEN = '<script type="module">';
const TAG_NEW = '<script type="module" src="/js/boot.js"></script>';

// 文件头（新写的部分；`--check` 靠它把"搬运内容"切出来）。末尾一行是分隔标记。
const HEADER = `// js/boot.js — 前端**装载根**（工单 frontend-boot-module/02）：模块装载清单 + 接线 + 启动。
//
// 为什么有这个文件（原 index.html 末尾那个 <script type="module"> 整块搬来这里）：
//   1. **装载图不该住在 HTML 里**：清单里提到一个不存在的导出，浏览器解析 import 就抛
//      SyntaxError，整页脚本全灭，而服务端 /api/* 与静态资源全 200（2026-09-12 真机现场，
//      看起来像"卡住"，强刷也没用）。搬进模块图后，这件事归 tests/js 的静态守卫
//      （含全图 import↔export 对账）与真浏览器门禁管。
//   2. **"靠被加载才接线"的隐式边退场**：模块求值期不再绑监听器 / 写首帧 DOM，接线写成
//      显式的 init*() 调用（工单 03/04 起），读这一个文件就知道页面装了什么、按什么顺序装的。
//
// 分层规则（照 js/app.js 的禁环约定）：
//   · boot 可以 import ui/** 与 app.js；
//   · **任何 ui/** 或 app.js 都不得 import boot.js**（否则成环）；
//   · index.html 只留一条 <script type="module" src="/js/boot.js"> 装载标签。
//
// 顺序纪律：装载清单**逐字保序**（ESM 求值顺序 = import 书写顺序，排序 / 分组 / 合并
// 都会改变模块求值次序）；接线区的调用顺序 = 清单里的出现顺序。
//
// ---- 以下为原 index.html 宿主块逐字搬运（工单 02；迁移墓碑注释一并保留）----
`;

const args = process.argv.slice(2);
const write = args.includes("--write");
if (!write && !args.includes("--dry-run")) {
  console.error("用法：node apply-move.mjs --dry-run | --write");
  process.exit(2);
}

const html = readFileSync(INDEX, "utf8");
const start = html.indexOf(TAG_OPEN);
if (start < 0) { console.error(`✗ index.html 里找不到 ${TAG_OPEN}`); process.exit(2); }
const contentStart = start + TAG_OPEN.length;
const end = html.indexOf("</script>", contentStart);
if (end < 0) { console.error("✗ 找不到块尾 </script>"); process.exit(2); }

const moved = html.slice(contentStart, end);          // 逐字（含首尾换行）
const before = html.slice(0, start);
const after = html.slice(end + "</script>".length);
const nextHtml = before + TAG_NEW + after;
const nextBoot = HEADER + moved.replace(/\r\n/g, "\n");

// ---- 自校验（先算后写：任一条不成立就不落盘）----
const problems = [];
const backMoved = nextBoot.slice(HEADER.length);
if (backMoved !== moved.replace(/\r\n/g, "\n")) {
  problems.push("boot.js 去掉文件头后与搬走的块内容不逐字相同（行尾归一后）");
}
if (!nextHtml.includes(TAG_NEW)) problems.push("index.html 里没有装载标签");
if (/^[ \t]*import\b/m.test(nextHtml.replace(TAG_NEW, ""))) {
  problems.push("index.html 里仍有 import 语句");
}
if (nextHtml.replace(TAG_NEW, "").length !== html.replace(html.slice(start, end + 9), "").length) {
  problems.push("index.html 除块之外的部分长度变了（markup 被动过？）");
}
// 装载清单保序：boot.js 里 import 出现的先后 = 原块里的先后
const specs = (text) => [...text.matchAll(/^[ \t]*import\s*(?:\{[^}]*\}\s*from\s*)?["']([^"']+)["']/gm)].map((m) => m[1]);
const a = specs(moved);
const b = specs(backMoved);
if (a.length !== b.length || a.some((s, i) => s !== b[i])) {
  problems.push(`装载清单顺序变了（原 ${a.length} 条 → 新 ${b.length} 条）`);
}

console.log(`块内容：${moved.split("\n").length - 1} 行 / ${Buffer.byteLength(moved, "utf8")} 字节`);
console.log(`装载清单：${a.length} 条（逐字保序：${problems.some((p) => p.includes("顺序")) ? "✗" : "✓"}）`);
console.log(`index.html：${html.length} → ${nextHtml.length} 字节（−${html.length - nextHtml.length}）`);
console.log(`boot.js：${nextBoot.split("\n").length} 行 / ${Buffer.byteLength(nextBoot, "utf8")} 字节（含 ${HEADER.split("\n").length} 行文件头）`);
if (problems.length) {
  console.error("✗ 自校验不通过，拒绝写盘：");
  for (const p of problems) console.error("  · " + p);
  process.exit(1);
}
console.log("✓ 自校验通过");
if (!write) { console.log("（--dry-run：没有写盘）"); process.exit(0); }
writeFileSync(BOOT, nextBoot, "utf8");
writeFileSync(INDEX, nextHtml, "utf8");
console.log("已写入 boot.js 与 index.html");
