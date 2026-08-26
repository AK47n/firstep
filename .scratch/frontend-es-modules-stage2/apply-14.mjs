// 阶段 2 工单 14：main.c 预览工具小簇（高亮同步 / 字号缩放 / 工具栏）迁
// static/js/ui/generate-mainc.js。
// ① 提取 index.html 2325-2440 三节（main.c 行号 + 语法着色 / 代码字号缩放 /
//    main.c 工具栏：4 函数 + 2 IIFE + 3 常量）→ 逐字搬入新模块（头部注释 + import +
//    导出清单在脚本内拼装）；
// ② index.html：host 顶部 import 行 + 簇体→注记。
// 全程 CRLF 感知；模块文件 LF（与既有 ui/*.js 一致）。
import { readFileSync, writeFileSync } from "node:fs";

const p = "src/contest_generator/static/index.html";
const mod = "src/contest_generator/static/js/ui/generate-mainc.js";
let txt = readFileSync(p, "utf8");
if (!txt.includes("\r\n")) throw new Error("not CRLF?");
const eol = "\r\n";
const lines = txt.split(eol);
const must = (i, what) => { if (i < 0) throw new Error("anchor not found: " + what); return i; };
if (lines.some((l) => l.includes('from "/js/ui/generate-mainc.js"'))) throw new Error("import already present");

const FUNCS = ["syncMainCHighlight", "initMainCHighlight", "currentCodeZoomPct",
  "applyCodeZoom", "initCodeZoom", "initMainCTools"];
const CONSTS = ["CODE_ZOOM_STEP", "CODE_ZOOM_BASE", "CODE_ZOOM_KEY"];

// ---- 1) 定位并提取簇体（main.c 行号 双横线头 → 生成页：8 双横线头，不含后者） ----
const hmc = must(lines.findIndex((l) => l.startsWith("// main.c 行号 + 语法着色")), "main.c header");
const dashMc = hmc - 1;
if (!lines[dashMc].startsWith("// ------")) throw new Error("dash before main.c header not found");
const h8 = must(lines.findIndex((l) => l.startsWith("// 生成页：8. main.c 骨架")), "8 header");
const dash8 = h8 - 1;
if (!lines[dash8].startsWith("// ------")) throw new Error("dash before 8 header not found");
let body = lines.slice(dashMc, dash8);   // 2325..2441（含末尾空行）
const bodyTxt = body.join(eol);
for (const n of FUNCS) {
  if (!new RegExp("function\\s+\\w*\\s*" + n + "\\(").test(bodyTxt)) throw new Error("missing " + n);
}
for (const c of CONSTS) {
  if (c === "CODE_ZOOM_KEY") {
    if (!bodyTxt.includes('CODE_ZOOM_KEY = "firstep.mainc.zoom"')) throw new Error("missing const " + c);
  } else if (!new RegExp("const\\s+" + c + "\\b").test(bodyTxt)) {
    throw new Error("missing const " + c);
  }
}
for (const frag of ['const CODE_ZOOM_STEP = 10',
  'const CODE_ZOOM_BASE = 13, CODE_ZOOM_KEY = "firstep.mainc.zoom"',
  '$("btn-main-c-copy")', '$("btn-main-c-download")', '$("btn-main-c-fullscreen")',
  'maincFullscreenLabel(active)', 'maincContentEmpty(ta.value)', 'codeZoomClamp(pct)',
  'parseZoomStored(localStorage.getItem(CODE_ZOOM_KEY))']) {
  if (!bodyTxt.includes(frag)) throw new Error("body missing frag: " + frag.slice(0, 40));
}

// ---- 2) 拼装 ui/generate-mainc.js（LF；头部注释 + imports + 簇体 + 导出） ----
const header = [
  "// ui/generate-mainc.js — 生成页 · main.c 预览工具（阶段 2 工单 14，源自",
  "// index.html 2325-2440 三节：main.c 行号 + 语法着色 / 代码字号缩放 / main.c 工具栏）",
  "//",
  "// DOM 胶水全量迁入：高亮同步（syncMainCHighlight + initMainCHighlight IIFE）/",
  "// 字号缩放（currentCodeZoomPct / applyCodeZoom / initCodeZoom IIFE + 常量",
  "// CODE_ZOOM_STEP / CODE_ZOOM_BASE / CODE_ZOOM_KEY）/ 工具栏（initMainCTools：",
  "// 复制 / 下载 / 全屏）。纯件在 fx/code.js（cHighlight / cLineCount /",
  "// codeZoomClamp / parseZoomStored / maincContentEmpty / maincFullscreenLabel——",
  "// 本模块 import 调用；maincLineOffsetRange / isMainCPath 属行跳转簇，host 侧使用）。",
  "// 状态所有权：本模块无跨簇 mutable 状态（CODE_ZOOM_KEY 的 localStorage 键名与",
  "// .code-wrap font-size 为模块内私有；host 经顶部 import 活绑定调用",
  "// syncMainCHighlight（generateMain / restoreDraft 写入后重同步）与",
  "// initMainCTools（启动区初始化））。",
  "// IIFE（initMainCHighlight / initCodeZoom）在 import 时自执行（module 脚本延迟",
  "// 执行，DOM 已就绪）；顶层 addEventListener 随 IIFE 绑定。",
  'import { $, toast } from "/js/app.js";',
  'import { cHighlight, cLineCount, codeZoomClamp, parseZoomStored, maincContentEmpty, maincFullscreenLabel } from "/js/fx/code.js";',
  "",
];
const exportTail = [
  "",
  "// ---- 本簇导出面（host 顶部 import 活绑定调用点） ----",
  "export { initMainCTools, syncMainCHighlight, currentCodeZoomPct, applyCodeZoom };",
  "",
];
writeFileSync(mod, [...header, ...body, ...exportTail].join("\n"), "utf8");
console.log("module written:", mod);

// ---- 3) index.html：host import 行（generate-pins import 之后） ----
{
  const i = must(lines.findIndex((l) => l.includes('from "/js/ui/generate-pins.js"')), "generate-pins import");
  lines.splice(i + 1, 0,
    'import { initMainCTools, syncMainCHighlight, currentCodeZoomPct, applyCodeZoom } from "/js/ui/generate-mainc.js";');
}

// ---- 4) 簇体 → 注记（重新定位：3 步已移动数组下标） ----
{
  const a = must(lines.findIndex((l) => l.startsWith("// main.c 行号 + 语法着色")), "main.c header");
  const da = a - 1;
  if (!lines[da].startsWith("// ------")) throw new Error("dash before main.c not found (re)");
  const b = must(lines.findIndex((l) => l.startsWith("// 生成页：8. main.c 骨架")), "8 header");
  const db = b - 1;
  if (!lines[db].startsWith("// ------")) throw new Error("dash before 8 not found (re)");
  const gap = lines.slice(da, db).join(eol);
  if (!gap.includes("function initMainCTools(") || !gap.includes("const CODE_ZOOM_BASE")) throw new Error("re-anchored gap lost cluster?");
  const note = [
    "// ---------------------------------------------------------------------------",
    "// 生成页：main.c 预览工具（高亮同步 / 字号缩放 / 复制 / 下载 / 全屏）",
    "// ---------------------------------------------------------------------------",
    "// 已迁至 static/js/ui/generate-mainc.js（阶段 2 工单 14）：syncMainCHighlight /",
    "// initMainCHighlight / currentCodeZoomPct / applyCodeZoom / initCodeZoom /",
    "// initMainCTools（4 函数 + 2 IIFE）+ 常量 CODE_ZOOM_STEP / CODE_ZOOM_BASE /",
    "// CODE_ZOOM_KEY。host 经顶部 import 活绑定调用 syncMainCHighlight",
    "// （generateMain / restoreDraft 写入后重同步）与 initMainCTools（启动区初始化）。",
    "",
  ];
  lines.splice(da, db - da, ...note);
}

// ---- 5) 校验 ----
const out = lines.join(eol);
if ((out.match(/from "\/js\/ui\/generate-mainc\.js"/) || []).length !== 1) throw new Error("generate-mainc import count != 1");
for (const n of FUNCS) {
  if (new RegExp("function\\s+\\w*\\s*" + n + "\\(").test(out)) throw new Error("residual definition of " + n);
}
for (const c of CONSTS) {
  if (new RegExp("const\\s+" + c + "\\b").test(out)) throw new Error("residual const " + c);
}
if (!out.includes("initMainCTools();  // main.c 工具栏（复制/下载/全屏）：DOM 已就绪，纯本地交互")) throw new Error("startup initMainCTools call lost");
if (!out.includes("syncMainCHighlight();")) throw new Error("host syncMainCHighlight calls lost");
if (!out.includes('    $("main-c").value = data.main_c;\r\n    syncMainCHighlight();')) throw new Error("generateMain sync call lost");
if (!out.includes("$(\"main-c\").value = d.mainC; markStepDone(8); syncMainCHighlight();")) throw new Error("restoreDraft sync call lost");
if (out.includes("firstep.mainc.zoom")) throw new Error("residual zoom key ref");

writeFileSync(p, out, "utf8");
console.log("OK: main.c preview cluster moved to ui/generate-mainc.js; host rewired; lines now", lines.length);
