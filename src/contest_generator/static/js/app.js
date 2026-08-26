// app.js — 前端共享壳（阶段 2 工单 02，迁自 index.html 主体共享区）：
// 跨 tab 共享件（$ / API 辅助 / 主题 / KIND_TEXT / toast / initBtnIcons / tabId
// 会话）与全局状态所有权（state + setState）。约束（禁环）：
// 1. 本文件不得 import 任何 static/js/ui/*.js（各 ui 模块 import 本文件）；
//    只允许 import 纯件 fx/*.js（btnIcon）。
// 2. state 所有权：本文件声明与 setState；其余模块 import { state } 后
//    「属性写」合法（ESM 绑定），整对象替换必须走 setState。
// 3. 不挂 window 桥（探针按需 import 或 DOM 实况；fx 纯件桥不受影响）。
// 4. 新共享件（多个 ui 模块共用、无 DOM 域归属的）优先落本文件。
import { btnIcon } from "/js/fx/btn-icon.js";

export const $ = (id) => document.getElementById(id);

// ---------------------------------------------------------------------------
// 主题切换（工单 ui-polish-5/01）：亮/暗两套变量；偏好存 localStorage；
// head 内联脚本已防闪烁，这里负责按钮图标 / 监听 / 持久化
// ---------------------------------------------------------------------------
export function currentTheme() {
  return document.documentElement.getAttribute("data-theme") === "light" ? "light" : "dark";
}
export function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  try { localStorage.setItem("firstep.theme", theme); } catch (e) { /* 忽略 */ }
  const btn = $("btn-theme");
  if (btn) {
    btn.textContent = theme === "light" ? "☀️" : "🌙";
    btn.title = theme === "light" ? "切换到深色主题" : "切换到亮色主题";
  }
}
export function initTheme() {
  let t = "dark";
  try {
    const saved = localStorage.getItem("firstep.theme");
    if (saved === "light" || saved === "dark") t = saved;
  } catch (e) { /* 忽略 */ }
  applyTheme(t);
  const btn = $("btn-theme");
  if (btn) btn.addEventListener("click", () => applyTheme(currentTheme() === "light" ? "dark" : "light"));
}
initTheme();

// ---------------------------------------------------------------------------
// API 辅助：统一错误提取（detail 是后端的中文 message）
// ---------------------------------------------------------------------------
export async function handle(resp) {
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    const err = new Error(data.detail || ("请求失败（HTTP " + resp.status + "）"));
    err.status = resp.status; // 调用方按状态码区分错误面（如页数端点 400 = 文件损坏）
    throw err;
  }
  return data;
}
export async function apiGet(url) { return handle(await fetch(url)); }
export async function apiPost(url, body) {
  return handle(await fetch(url, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  }));
}
export async function apiPut(url, body) {
  return handle(await fetch(url, {
    method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  }));
}
export async function apiDelete(url, body) {
  return handle(await fetch(url, {
    method: "DELETE", headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  }));
}

export const KIND_TEXT = { missing: "缺平台版本（生成将失败）", unverified: "未验证", hardware_bound: "硬件绑定" };

// ---------------------------------------------------------------------------
// 标签会话（启动器模式）：打开登记、关闭注销——最后一个标签关掉 = 停服务
// ---------------------------------------------------------------------------
const TAB_ID_KEY = "firstep_tab_id";
let tabId = sessionStorage.getItem(TAB_ID_KEY);
if (!tabId) { tabId = crypto.randomUUID(); sessionStorage.setItem(TAB_ID_KEY, tabId); }
fetch("/api/tabs/register", { method: "POST", headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ tab_id: tabId }) }).catch(() => {});
window.addEventListener("pagehide", () => {
  navigator.sendBeacon("/api/tabs/bye", new Blob([JSON.stringify({ tab_id: tabId })],
    { type: "application/json" }));
});

// ---------------------------------------------------------------------------
// 全局状态：GET /api/state 单源；refreshState（host 内，需渲染三个簇函数）
// 与启动 init 均经 setState 整换；ui 模块属性写（state.modules = ...）合法
// ---------------------------------------------------------------------------
export let state = null;
export function setState(v) { state = v; }

// ---------------------------------------------------------------------------
// Toast 轻通知（工单 ui-polish-3/03）：右上角堆叠，ok 青 / error 红 / info 灰，
// 2.5s 自动消失，最多同屏 3 条；行内提示保留（toast 只做显眼补充）
// ---------------------------------------------------------------------------
const TOAST_ICON = { ok: "✓", error: "✕", info: "ℹ" };
export function toast(kind, text) {
  const root = $("toast-root");
  if (!root) return;
  while (root.children.length >= 3) root.removeChild(root.firstChild);
  const el = document.createElement("div");
  el.className = "toast " + kind;
  el.innerHTML = '<span class="toast-ico">' + TOAST_ICON[kind] + '</span><span class="toast-text">'
    + String(text).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/"/g, "&quot;")
    + '</span><button type="button" class="toast-close" aria-label="关闭">×</button>';
  el.querySelector(".toast-close").addEventListener("click", () => {
    // 点击关闭走离场动画（工单 ui-polish-8/03）：重触发 toast-out 后移除
    el.style.animation = "none";
    void el.offsetWidth;
    el.style.animation = "toast-out .3s ease forwards";
    setTimeout(() => el.remove(), 300);
  });
  root.appendChild(el);
  setTimeout(() => { if (el.isConnected) el.remove(); }, 2500);
}

// ---------------------------------------------------------------------------
// 按钮图标（工单 ui-polish-9/04）：data-ico 注入内联 SVG（16px stroke 风格）。
// btnIcon 纯件在 fx/btn-icon.js（本文件顶部 import）
// ---------------------------------------------------------------------------
(function initBtnIcons() {
  document.querySelectorAll("[data-ico]").forEach((b) => {
    b.insertAdjacentHTML("afterbegin", btnIcon(b.dataset.ico));
  });
})();
