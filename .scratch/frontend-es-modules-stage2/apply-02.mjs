// 阶段 2 工单 02：index.html 共享件搬 app.js——8 块替换 + 2 处 state 赋值改 setState + import 行插入
import { readFileSync, writeFileSync } from "node:fs";

const p = "src/contest_generator/static/index.html";
let txt = readFileSync(p, "utf8");
if (!txt.includes("\r\n")) throw new Error("not CRLF?");
const eol = "\r\n";
const lines = txt.split(eol);

if (lines.some((l) => l.includes('from "/js/app.js"'))) throw new Error("app.js import already present");
const moved = ["currentTheme", "applyTheme", "initTheme", "handle", "apiGet", "apiPost", "apiPut", "apiDelete", "KIND_TEXT", "initBtnIcons", "TOAST_ICON", "toast"];

const findNote = (frag) => lines.findIndex((l) => l.includes(frag));
const findStart = (frag) => { const i = findNote(frag); return i >= 0 ? i - 1 : -1; };  // 含前导 dashes
const must = (idx, what) => { if (idx < 0) throw new Error("anchor not found: " + what); return idx; };

// 校验各名定义存在（在待删块内逐块 check）
const checkIn = (removed, name) => {
  if (!new RegExp("(function|const)\\s+" + name + "\\b").test(removed)) throw new Error("missing " + name + " in removed span");
};

// ---- 1) host import 行：workflow.js import 之后
const wfIdx = must(lines.findIndex((l) => l.includes('from "/js/fx/workflow.js"')), "workflow import");
const hostImp = 'import { $, handle, apiGet, apiPost, apiPut, apiDelete, KIND_TEXT, state, setState, toast } from "/js/app.js";';
lines.splice(wfIdx + 1, 0, hostImp);

// ---- 2) 主题块（注释 + 3 函数 + initTheme() 调用）
{
  const a = must(findStart("// 主题切换（工单 ui-polish-5/01）：亮/暗两套变量"), "theme block start");
  if (!lines[a].startsWith("// ---")) throw new Error("theme prev not dashes");
  const b = must(lines.findIndex((l) => l.trim() === "initTheme();"), "initTheme() call");
  const removed = lines.slice(a, b + 1).join(eol);
  ["currentTheme", "applyTheme", "initTheme"].forEach((n) => checkIn(removed, n));
  const note = [
    "// 主题切换（工单 ui-polish-5/01）：currentTheme / applyTheme / initTheme 及",
    "// initTheme() 启动调用已迁至 static/js/app.js（阶段 2 工单 02）。",
  ];
  lines.splice(a, b - a + 1, ...note);
}

// ---- 3) API 辅助块（注释 + handle + apiGet/Post/Put/Delete）
{
  const a = must(findStart("// API 辅助：统一错误提取"), "api block start");
  const b = must(lines.findIndex((l) => l.startsWith("const KIND_TEXT =")), "KIND_TEXT");
  const removed = lines.slice(a, b).join(eol);  // KIND_TEXT 行自身后处理
  ["handle", "apiGet", "apiPost", "apiPut", "apiDelete"].forEach((n) => checkIn(removed, n));
  const note = [
    "// API 辅助（统一错误提取，detail 是后端的中文 message）：handle / apiGet /",
    "// apiPost / apiPut / apiDelete 已迁至 static/js/app.js（阶段 2 工单 02）。",
  ];
  lines.splice(a, b - a, ...note);
  // KIND_TEXT 行：删（前一空行留）
  const k = must(lines.findIndex((l) => l.startsWith("const KIND_TEXT =")), "KIND_TEXT line");
  if (!new RegExp("const KIND_TEXT\\b").test(lines[k])) throw new Error("KIND_TEXT not const");
  lines.splice(k, 1, "// KIND_TEXT（平台警告文案映射）已迁至 static/js/app.js（阶段 2 工单 02）。");
}

// ---- 4) 标签会话块（注释 + TAB_ID_KEY/tabId/register/pagehide）
{
  const a = must(findStart("// 标签会话（启动器模式）"), "tab session start");
  const b = must(lines.findIndex((l) => l.startsWith('window.addEventListener("pagehide"')), "pagehide");
  let end = b;
  for (; end < lines.length && !(lines[end] === "});"); end++) { /* scan */ }
  if (end >= lines.length + 0) end = b;  // 防御（不会走到）
  // 上面循环会多走一行：标准结构 = window.addEventListener(...){ 3 行 + });}——统一按「});」后重算
  let e2 = b;
  while (e2 < lines.length && lines[e2] !== "});") e2++;
  const removed = lines.slice(a, e2 + 1).join(eol);
  if (!/TAB_ID_KEY/.test(removed) && !/tabId/.test(removed)) throw new Error("tab session missing");
  const note = [
    "// 标签会话（启动器模式）：TAB_ID_KEY / tabId 登记与 pagehide sendBeacon 已迁至",
    "// static/js/app.js（阶段 2 工单 02）。",
  ];
  lines.splice(a, e2 - a + 1, ...note);
}

// ---- 5) state 声明行（let state = null; 删 + 注记）
{
  const s = must(lines.findIndex((l) => l.includes("let state = null;")), "state let");
  lines.splice(s, 1, "// state（GET /api/state）已迁至 static/js/app.js（阶段 2 工单 02）：");
  lines.splice(s + 1, 0, "// 本文件经 host import 的 setState 整换；ui 模块属性写（state.modules = ...）合法。");
}

// ---- 6) refreshState + init 两处 `state = await apiGet("/api/state")` → setState(...)
{
  const hits = [];
  for (let i = 0; i < lines.length; i++) {
    if (/^\s*state = await apiGet\("\/api\/state"\);/.test(lines[i])) hits.push(i);
  }
  if (hits.length !== 2) throw new Error("expected 2 state= assignment sites, got " + hits.length + ": " + hits.join(","));
  for (const i of hits) {
    lines[i] = lines[i].replace('state = await apiGet("/api/state");', 'setState(await apiGet("/api/state"));');
    if (!/setState\(await apiGet\("\/api\/state"\)\);/.test(lines[i])) throw new Error("setState rewrite failed at " + i + ": " + lines[i]);
  }
}

// ---- 7) initBtnIcons IIFE（6964 一带：注释 2 行 + IIFE 5 行）
{
  const a = must(lines.findIndex((l) => l.includes("// 按钮图标（工单 ui-polish-9/04）")), "btn icon comment");
  const b = must(lines.findIndex((l) => l.trim() === "})();" && true), "nearby IIFE");  // 占位，下面精确找 a 之后的第一个 "})();"
  let e = -1;
  for (let i = b; i < lines.length; i++) {
    if (i > a && lines[i].trim() === "})();") { e = i; break; }
  }
  if (e < 0) throw new Error("initBtnIcons IIFE end not found");
  const removed = lines.slice(a, e + 1).join(eol);
  if (!/initBtnIcons/.test(removed)) throw new Error("initBtnIcons missing");
  const note = [
    "// 按钮图标（工单 ui-polish-9/04）：btnIcon 纯件在 fx/btn-icon.js；注入 IIFE",
    "// initBtnIcons（data-ico → 内联 SVG）已迁至 static/js/app.js（阶段 2 工单 02）。",
  ];
  lines.splice(a, e - a + 1, ...note);
}

// ---- 8) Toast 块（注释 + TOAST_ICON + toast）
{
  const a = must(findStart("// Toast 轻通知（工单 ui-polish-3/03）"), "toast block start");
  const t0 = must(lines.findIndex((l) => l.startsWith("function toast(kind, text) {")), "toast fn");
  let to = t0;
  while (to < lines.length && !/^\}$/.test(lines[to])) to++;
  if (to >= lines.length) throw new Error("toast fn end not found");
  const removed = lines.slice(a, to + 1).join(eol);
  if (!/TOAST_ICON/.test(removed) || !/function toast/.test(removed)) throw new Error("toast block missing");
  const note = [
    "// ---------------------------------------------------------------------------",
    "// Toast 轻通知（工单 ui-polish-3/03）：toast / TOAST_ICON 已迁至",
    "// static/js/app.js（阶段 2 工单 02）；右上角堆叠 2.5s 自动消失，最多同屏 3 条。",
    "// ---------------------------------------------------------------------------",
  ];
  lines.splice(a, to - a + 1, ...note);
}

// ---- 校验：被搬名在 index.html 无定义残留
for (const n of moved) {
  if (new RegExp("(function|const)\\s+" + n + "\\b").test(lines.join(eol))) throw new Error("residual definition of " + n);
}

writeFileSync(p, lines.join(eol), "utf8");
console.log("OK: app.js import inserted; 8 blocks replaced; 2 state->setState rewritten; total lines now", lines.length);
