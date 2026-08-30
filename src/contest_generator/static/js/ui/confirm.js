// ui/confirm.js — 共享确认弹窗工厂（工单 master-library-ui-2/04 创建、
// 05 全仓库迁移 8 处原生 confirm() 统一复用）。
//
// confirmModal(opts) -> Promise<boolean | string>：遮罩语言与既有
// .ref-files-overlay 一致（Esc / × / 点遮罩取消）；取消 → false；确认 →
// true，但若 extra 内含 [data-confirm-value] 元素（如平台下拉），确认后
// 解析为其 .value（调用方据此拿选择值，空值 = 取消语义）。纯件
// overlayConfirmHTML 在 fx/overlay.js，本模块只做 DOM 接线与事件解绑。
import { overlayConfirmHTML } from "/js/fx/overlay.js";

// 级联清理（评审 05 修正）：并发/重入时旧弹窗被直接 remove 会残留 keydown
// 监听且 Promise 永不 settle——新工厂创建时先关旧弹窗（cleanup 解绑 +
// resolve(false)），无并发场景零影响。
let activeCleanup = null;

export function confirmModal({
  title,
  message,
  danger = true,
  confirmText,
  cancelText = "取消",
  extra = "",
} = {}) {
  // 开发告警（工单 ux-walkthrough-02/15）：防漏传光秃秃的「确认」——动作
  // 语义（确认删除 / 执行修订…）应由调用点给出；默认值仅兜底不静默
  if (!confirmText) {
    console.warn("confirmModal 未传 confirmText（默认「确认」）：请在调用点给足动作语义，如「确认删除」");
    confirmText = "确认";
  }
  return new Promise((resolve) => {
    // 焦点管理（工单 ux-walkthrough-02/19）：在旧弹窗级联清理**前**记录
    // 触发元素——旧 finish 会把焦点还给旧触发钮，后读会错记为旧钮（评审整改）
    const opener = typeof document !== "undefined" && document.activeElement
      ? document.activeElement : null;
    if (activeCleanup) {
      const old = activeCleanup;
      activeCleanup = null;
      old();
    }
    document.querySelectorAll(".ref-files-overlay").forEach((o) => o.remove());
    const overlay = document.createElement("div");
    overlay.className = "ref-files-overlay";
    overlay.innerHTML = overlayConfirmHTML({
      title, message, danger, confirmText, cancelText, extra,
    });
    const onKey = (e) => {
      if (e.key === "Escape") { finish(false); return; }
      // Tab 焦点陷阱：限制在弹窗内（首尾循环）
      if (e.key === "Tab") {
        const focusables = Array.from(
          overlay.querySelectorAll("button, input, select, textarea, [href], [tabindex]:not([tabindex='-1'])")
        ).filter((el) => !el.disabled && el.offsetParent !== null);
        if (!focusables.length) return;
        const first = focusables[0];
        const last = focusables[focusables.length - 1];
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
      }
    };
    let settled = false;
    const finish = (value) => {
      if (settled) return;
      settled = true;
      document.removeEventListener("keydown", onKey);
      overlay.remove();
      activeCleanup = null;
      // 关闭后把焦点还给触发元素（评审 19：Esc / 取消 / 确认 / 遮罩点击一致；
      // disabled 触发钮 focus 为 no-op，跳过）
      if (opener && !opener.disabled && typeof opener.focus === "function"
          && opener.isConnected) opener.focus();
      resolve(value);
    };
    activeCleanup = () => finish(false);
    overlay.querySelector(".ref-files-close").addEventListener("click", () => finish(false));
    overlay.addEventListener("click", (e) => { if (e.target === overlay) finish(false); });
    overlay.querySelector("[data-confirm-cancel]").addEventListener("click", () => finish(false));
    overlay.querySelector("[data-confirm-ok]").addEventListener("click", () => {
      const valued = overlay.querySelector("[data-confirm-value]");
      finish(valued ? valued.value : true);
    });
    document.addEventListener("keydown", onKey);
    document.body.appendChild(overlay);
    // 打开即聚焦：危险确认默认给「取消」防误触 Enter；普通确认给「确认」
    const focusTarget = overlay.querySelector(
      danger ? "[data-confirm-cancel]" : "[data-confirm-ok]");
    if (focusTarget) focusTarget.focus();
  });
}
