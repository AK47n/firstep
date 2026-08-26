// fx/code.js — main.c 工具纯函数（工单 frontend-es-modules/01，迁自 index.html 4315-4369 /
// 4394-4403 / 4434-4440 / 5222-5233）。原实现刻意自包含（不引用模块级常量、不调用
// 其它抽取函数）；模块化后 esc 单源化自 fx/core.js（cHighlight 原局部 esc 已移除，
// 行为零变化），其余函数保持逐字原样。
import { esc } from "./core.js";

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
      html += kw[word] ? '<span class="tok-kw">' + word + "</span>" : esc(word);
      i = j;
    } else if (ch === "#" && (i === 0 || src[i - 1] === "\n")) {  // 预处理行
      let j = src.indexOf("\n", i); if (j < 0) j = n;
      html += '<span class="tok-pre">' + esc(src.slice(i, j)) + "</span>";
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

if (typeof window !== "undefined") {
  Object.assign(window, { cHighlight, cLineCount, codeZoomClamp, parseZoomStored, maincContentEmpty, maincFullscreenLabel, isMainCPath, maincLineOffsetRange });
}
