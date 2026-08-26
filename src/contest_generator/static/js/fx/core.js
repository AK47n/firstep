// fx/core.js — 前端纯函数模块（工单 frontend-es-modules/01：共享件单源化）
//
// 模块约定（全部 fx/*.js 同守）：
// 1. 只含纯函数：收数据返数据，不碰 DOM / fetch / 定时器；
// 2. 浏览器端启用方式 = 主体脚本 module 化顶部静态 import（index.html 的
//    <script type="module"> 首部 import '/js/fx/...'，module 语义保证本模块
//    先求值）；window 同名桥（本文件尾部）为兼容层，供探针脚本 / devtools
//    按全局名取用；
// 3. node 端（tests/js）直接 import 本模块做单测，不再字符串提取；
// 4. 同域常量随函数入驻；新纯函数一律写进 fx 模块（勿回 index.html 内联）。
export function esc(text) {
  return String(text).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[c]);
}

export function formatSize(bytes) {
  if (!Number.isFinite(bytes)) return "";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let v = bytes, i = 0;
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i++; }
  return (i === 0 ? String(Math.round(v)) : v.toFixed(1)) + " " + units[i];
}

export function fmtClock(sec) {   // 计时器显示：mm:ss（分可超 59）
  const m = Math.floor(sec / 60), s = Math.floor(sec % 60);
  return String(m).padStart(2, "0") + ":" + String(s).padStart(2, "0");
}
export function fmtDuration(sec) {   // 完成行："12 分 34 秒" / "45 秒" / "1 小时 2 分 3 秒"
  sec = Math.round(sec);
  const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60;
  const parts = [];
  if (h) parts.push(h + " 小时");
  if (m || h) parts.push(m + " 分");
  parts.push(s + " 秒");
  return parts.join(" ");
}

export function truncate(text, n) {
  text = String(text);
  return text.length <= n ? text : text.slice(0, n) + "…";
}

if (typeof window !== "undefined") {
  Object.assign(window, { esc, formatSize, fmtClock, fmtDuration, truncate });
}
