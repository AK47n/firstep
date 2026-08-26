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

if (typeof window !== "undefined") {
  Object.assign(window, { esc, formatSize });
}
