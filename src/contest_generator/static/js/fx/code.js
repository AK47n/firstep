// fx/code.js — main.c 工具模块（工单 frontend-es-modules/01，迁自 index.html 4315-4369 /
// 4394-4403 / 4434-4440 / 5222-5233）。原实现刻意自包含（不引用模块级常量、不调用
// 其它抽取函数）；模块化后 esc 单源化自 fx/core.js（cHighlight 原局部 esc 已移除，
// 行为零变化），其余函数保持逐字原样。
// 模块约定见 fx/core.js 头部：主体为纯函数（cHighlight / cLineCount / … /
// maincLineOffsetRange）；下述两个交互例外（error-jump-task/02 迁移说明）——
// maincScrollToRange / maincJumpToLine 是 DOM 交互件（硬编码 #main-c /
// #main-c-hl 全局查询 + 卡片展开 / 滚动 / 选区），fx/generate.js 的
// syncCollapseBtn 同款先例（节点参数式）；例外已如实声明，不再与「纯函数」
// 表述冲突。maincJumpToLine 返回错误码（null 成功 / "empty" / "out-of-range"
// / "no-textarea"），toast 由调用方做（fx 模块不 import app.js 的 toast）。
import { esc } from "./core.js";
import { syncCollapseBtn } from "./generate.js";

// 全大写宏常量判定（工单 code-viewer-ide-restyle/02）：含下划线的全大写
// 标识符（GPIO_PIN_0 / LED_GPIO）；无下划线全大写短词（如 A）不误染。
function isMacroConst(w) {
  return /^[A-Z0-9_]+$/.test(w) && /[A-Z]/.test(w) && w.includes("_");
}

export function cHighlight(code) {
  const src = String(code == null ? "" : code);
  const kw = {};
  "auto break case char const continue default do double else enum extern float for goto if inline int long register restrict return short signed sizeof static struct switch typedef union unsigned void volatile while".split(" ")
    .forEach((w) => { kw[w] = true; });
  let html = "";
  let i = 0;
  const n = src.length;
  while (i < n) {
    const ch = src[i];
    if (ch === "/" && src[i + 1] === "/") {           // 行注释
      let j = src.indexOf("\n", i); if (j < 0) j = n;
      html += '<span class="tok-com">' + esc(src.slice(i, j)) + "</span>";
      i = j;
    } else if (ch === "/" && src[i + 1] === "*") {    // 块注释
      let j = src.indexOf("*/", i + 2); j = j < 0 ? n : j + 2;
      html += '<span class="tok-com">' + esc(src.slice(i, j)) + "</span>";
      i = j;
    } else if (ch === '"' || ch === "'") {            // 字符串
      let j = i + 1;
      while (j < n && src[j] !== ch) { if (src[j] === "\\") j++; j++; }
      if (j < n) j++;
      html += '<span class="tok-str">' + esc(src.slice(i, j)) + "</span>";
      i = j;
    } else if (/[0-9]/.test(ch) || (ch === "." && /[0-9]/.test(src[i + 1] || ""))) {  // 数字
      let j = i;
      while (j < n && /[0-9a-fA-FxXbBoO._]/.test(src[j])) j++;
      html += '<span class="tok-num">' + esc(src.slice(i, j)) + "</span>";
      i = j;
    } else if (/[A-Za-z_]/.test(ch)) {                // 标识符 / 关键字
      let j = i;
      while (j < n && /[A-Za-z0-9_]/.test(src[j])) j++;
      const word = src.slice(i, j);
      if (kw[word]) {
        html += '<span class="tok-kw">' + word + "</span>";
      } else {
        let k = j;
        while (k < n && (src[k] === " " || src[k] === "\t")) k++;
        if (k < n && src[k] === "(") {              // 函数名/调用（Dark+ 式淡黄）
          html += '<span class="tok-fn">' + esc(word) + "</span>";
        } else if (isMacroConst(word)) {            // 宏常量（Dark+ 式紫）
          html += '<span class="tok-const">' + esc(word) + "</span>";
        } else {
          html += esc(word);
        }
      }
      i = j;
    } else if (ch === "#" && (i === 0 || src[i - 1] === "\n")) {  // 预处理行
      let j = src.indexOf("\n", i); if (j < 0) j = n;
      const line = src.slice(i, j);
      const m = line.match(/^#\s*define\s+([A-Za-z_][A-Za-z0-9_]*)/);
      if (m && isMacroConst(m[1])) {                  // #define NAME → NAME 拆出 tok-const
        const prefix = line.slice(0, m[0].length - m[1].length);
        const rest = line.slice(prefix.length + m[1].length);
        html += '<span class="tok-pre">' + esc(prefix) + "</span>"
              + '<span class="tok-const">' + esc(m[1]) + "</span>"
              + '<span class="tok-pre">' + esc(rest) + "</span>";
      } else {
        html += '<span class="tok-pre">' + esc(line) + "</span>";
      }
      i = j;
    } else {
      html += esc(ch);
      i++;
    }
  }
  return html;
}

export function cLineCount(code) {
  const lines = String(code == null ? "" : code).split("\n");
  const out = [];
  for (let i = 0; i < lines.length; i++) out.push(String(i + 1));
  return out.join("\n");
}

export function codeZoomClamp(pct) {
  const min = 80, max = 200; // 自包含：pct 非法/越界时收敛到 [80,200]
  if (typeof pct !== "number" || !Number.isFinite(pct)) return 100;
  return Math.min(max, Math.max(min, Math.round(pct)));
}

export function parseZoomStored(raw) {
  if (raw == null) return 100;
  const n = parseInt(String(raw), 10);
  return codeZoomClamp(Number.isNaN(n) ? 100 : n);
}

export function maincContentEmpty(value) {
  const text = value == null ? "" : String(value);
  return text.trim() === "";
}

export function maincFullscreenLabel(active) {
  return active ? "退出全屏" : "全屏";
}

export function isMainCPath(path) {
  const parts = String(path == null ? "" : path).replace(/\\/g, "/").split("/");
  return (parts[parts.length - 1] || "") === "main.c";
}

export function maincLineOffsetRange(text, line) {
  const lines = String(text == null ? "" : text).split("\n");
  const n = Number(line);
  if (!Number.isInteger(n) || n < 1 || n > lines.length) return null;
  let start = 0;
  for (let i = 0; i < n - 1; i++) start += lines[i].length + 1;  // +1 = \n
  return { start, end: start + lines[n - 1].length };
}

// ---------------------------------------------------------------------------
// main.c 错误行定位（迁自 ui/generate-fix.js，工单 compile-error-jump/01 原
// 件 + error-jump-task/02 单源化）：点 main.c 的错误行 = 滚动到预览卡并选中
// 该行文本（选区即持续高亮，点其他行切换）。
// ---------------------------------------------------------------------------
// 选区滚入 textarea 视口：浏览器 focus 的滚动窗口行为不可靠（headless 实测
// scrollTop 不动），这里在高亮层临时量测目标行视觉位置——hl-layer 与
// textarea 排版参数同源（font/line-height/padding/pre-wrap/视口宽，三明治
// 对齐设计保证换行点一致），折行场景同样精确，全程无像素行高公式。
export function maincScrollToRange(ta, range) {
  const hl = document.getElementById("main-c-hl");
  if (!hl) return;
  const _probe_style = "display:block;white-space:pre-wrap;word-break:break-all;";
  const before = document.createElement("span");
  before.style.cssText = _probe_style;
  before.textContent = ta.value.slice(0, range.start);
  const target = document.createElement("span");
  target.style.cssText = _probe_style;
  target.textContent = ta.value.slice(range.start, range.end);
  hl.appendChild(before);
  hl.appendChild(target);
  const top = target.offsetTop, h = target.offsetHeight;
  before.remove();
  target.remove();
  const viewH = ta.clientHeight - 24;   // 上下 padding 12px × 2
  ta.scrollTop = Math.max(0, top - (viewH - h) / 2);
}

/** 跳转 main.c 并选中该行（返回错误码：null 成功 / "empty" main.c 为空 /
 * "out-of-range" 行号越界 / "no-textarea" 预览未渲染；toast 由调用方做）。 */
export function maincJumpToLine(line) {
  const ta = document.getElementById("main-c");
  if (!ta) return "no-textarea";
  if (maincContentEmpty(ta.value)) return "empty";
  const range = maincLineOffsetRange(ta.value, line);
  if (!range) return "out-of-range";
  const card = ta.closest(".card");
  if (card && card.classList.contains("collapsed")) {
    card.classList.remove("collapsed");
    const btn = card.querySelector(".card-collapse");
    if (btn) syncCollapseBtn(btn, false);
  }
  ta.scrollIntoView({ block: "center", behavior: "smooth" });
  ta.focus();
  ta.setSelectionRange(range.start, range.end);
  maincScrollToRange(ta, range);   // 内部滚动到选区（折行也精确）
  return null;
}

if (typeof window !== "undefined") {
  Object.assign(window, { cHighlight, cLineCount, codeZoomClamp, parseZoomStored, maincContentEmpty, maincFullscreenLabel, isMainCPath, maincLineOffsetRange, maincScrollToRange, maincJumpToLine });
}
