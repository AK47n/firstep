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
import { parseError, parseHttpError, isLongError } from "/js/fx/errors.js";

// copyText(text)：剪贴板复制单源（工单 code-editor-refine/06 评审整改——
// 全仓库第 7 份同型实现收敛；app.js 规则 4「新共享件优先落本文件」+ 规则 1
// 「不 import ui/*」故不入 ui 模块）。navigator.clipboard 优先（localhost 安全
// 上下文；writeText 拒绝 = 授权拒绝/非安全上下文），失败/不可用 → 隐藏
// textarea + execCommand 保底；返回是否成功（成功与否的提示文案由调用方定
// ——各处消息不同，不强行统一）。
export async function copyText(text) {
  const value = String(text == null ? "" : text);
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(value);
      return true;
    }
  } catch (e) { /* 授权拒绝 / 非安全上下文 → 回退 execCommand */ }
  try {
    const ta = document.createElement("textarea");
    ta.value = value;
    ta.setAttribute("readonly", "");
    ta.style.position = "fixed";
    ta.style.left = "-9999px";
    ta.style.top = "0";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    const ok = !!document.execCommand && document.execCommand("copy");
    ta.remove();
    return ok;
  } catch (e) {
    return false;
  }
}

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
    // 统一错误解析（工单 ux-walkthrough-02/11）：与 SSE 终态同一路径
    const err = new Error(parseHttpError(resp.status, data).text);
    err.status = resp.status; // 调用方按状态码区分错误面（如页数端点 400 = 文件损坏）
    throw err;
  }
  return data;
}
export async function apiGet(url, opts) { return handle(await fetch(url, { signal: opts && opts.signal })); }
export async function apiPost(url, body, opts) {
  return handle(await fetch(url, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    signal: opts && opts.signal,
  }));
}
export async function apiPut(url, body, opts) {
  return handle(await fetch(url, {
    method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    signal: opts && opts.signal,
  }));
}
export async function apiDelete(url, body, opts) {
  return handle(await fetch(url, {
    method: "DELETE", headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal: opts && opts.signal,
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
/** toast 轻通知：opts = {copy: bool, ms: number, action: {label, onClick}}——
 * 长错误（500/超阈值）场景由 toastError 传 copy + 常驻；删除类操作的
 * 「撤销」用 action（工单 ux-walkthrough-02/15），点击执行后 toast 关闭。 */
export function toast(kind, text, opts = {}) {
  const root = $("toast-root");
  if (!root) return;
  while (root.children.length >= 3) root.removeChild(root.firstChild);
  const el = document.createElement("div");
  el.className = "toast " + kind;
  const copyBtn = opts.copy
    ? '<button type="button" class="toast-copy" aria-label="复制错误内容">复制</button>'
    : "";
  const actionBtn = opts.action && opts.action.onClick
    ? '<button type="button" class="toast-action" aria-label="' + (opts.action.label || "撤销") + '">'
      + (opts.action.label || "撤销").replace(/&/g, "&amp;").replace(/</g, "&lt;") + "</button>"
    : "";
  el.innerHTML = '<span class="toast-ico">' + TOAST_ICON[kind] + '</span><span class="toast-text">'
    + String(text).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/"/g, "&quot;")
    + '</span>' + actionBtn + copyBtn + '<button type="button" class="toast-close" aria-label="关闭">×</button>';
  el.querySelector(".toast-close").addEventListener("click", () => {
    // 点击关闭走离场动画（工单 ui-polish-8/03）：重触发 toast-out 后移除
    el.style.animation = "none";
    void el.offsetWidth;
    el.style.animation = "toast-out .3s ease forwards";
    setTimeout(() => el.remove(), 300);
  });
  if (actionBtn) {
    el.querySelector(".toast-action").addEventListener("click", async () => {
      try {
        await opts.action.onClick();
        if (el.isConnected) el.remove();
      } catch (e) {
        toastError(e, "撤销失败");   // 撤销动作自身失败：另报错误（评审整改：不静默吞）
        if (el.isConnected) el.remove();
      }
    });
  }
  if (copyBtn) {
    el.querySelector(".toast-copy").addEventListener("click", async () => {
      // 剪贴板守卫 + execCommand 回退——机制 = copyText 单源（工单 06 评审
      // 整改：原内联实现与 recent/main.c/核对表/母版等 7 处同型，已收敛）；
      // 按钮文案反馈保持本处特有（「已复制」1.2s 还原 / 「复制失败」）。
      const copyBtnEl = el.querySelector(".toast-copy");
      const ok = await copyText(text);
      copyBtnEl.textContent = ok ? "已复制" : "复制失败";
      if (ok) setTimeout(() => { if (el.isConnected) copyBtnEl.textContent = "复制"; }, 1200);
    });
  }
  root.appendChild(el);
  const ms = opts.ms !== undefined ? opts.ms : (opts.copy ? 6000 : 2500);
  if ((opts.copy || ms > 2500)
      && !(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches)) {
    // 长停留 / 常驻 toast：关掉 .toast 的 2.2s 自动淡出动画（否则视觉仍 2.2s 消失）；
    // reduced-motion 用户保留 CSS 的 animation:none（无障碍不回归）
    el.style.animation = "toast-in var(--dur-slow) var(--ease-ui)";
  }
  if (ms > 0) setTimeout(() => { if (el.isConnected) el.remove(); }, ms);
}

/** 错误统一出口（工单 ux-walkthrough-02/11）：parseError 归一后按长度/状态
 * 分派——长错误 / 5xx → 可复制 toast（≥6s）；短错误 → 常规 toast。
 * prefix 可选：调用方上下文前缀（如「删除失败：」）——不改变功能语义。 */
export function toastError(err, prefix) {
  const parsed = parseError(err);
  if (prefix && String(prefix).trim() && !parsed.text.startsWith(String(prefix).trim())) {
    parsed.text = String(prefix).trim() + "：" + parsed.text;
  }
  if (isLongError(parsed)) {
    // 长错误 / 5xx：常驻可复制（ms=0 不自动消失，点 ✕ 关闭）——满足「长错误
    // 常驻内联可复制」验收（工单 ux-walkthrough-02/11）
    toast("error", parsed.text, { copy: true, ms: 0 });
  } else {
    toast("error", parsed.text);
  }
  return parsed;
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
