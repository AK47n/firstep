// ui/confirm.js — 共享确认弹窗工厂（工单 master-library-ui-2/04 创建、
// 05 全仓库迁移 8 处原生 confirm() 统一复用）。
//
// confirmModal(opts) -> Promise<boolean | string>：遮罩语言与既有
// .ref-files-overlay 一致（Esc / × / 点遮罩取消）；取消 → false；确认 →
// true，但若 extra 内含 [data-confirm-value] 元素（如平台下拉），确认后
// 解析为其 .value（调用方据此拿选择值，空值 = 取消语义）。纯件
// overlayConfirmHTML 在 fx/overlay.js，本模块只做 DOM 接线与事件解绑。
import { overlayConfirmHTML } from "/js/fx/overlay.js";

export function confirmModal({
  title,
  message,
  danger = true,
  confirmText = "确认",
  cancelText = "取消",
  extra = "",
} = {}) {
  return new Promise((resolve) => {
    document.querySelectorAll(".ref-files-overlay").forEach((o) => o.remove());
    const overlay = document.createElement("div");
    overlay.className = "ref-files-overlay";
    overlay.innerHTML = overlayConfirmHTML({
      title, message, danger, confirmText, cancelText, extra,
    });
    const onKey = (e) => { if (e.key === "Escape") finish(false); };
    let settled = false;
    const finish = (value) => {
      if (settled) return;
      settled = true;
      document.removeEventListener("keydown", onKey);
      overlay.remove();
      resolve(value);
    };
    overlay.querySelector(".ref-files-close").addEventListener("click", () => finish(false));
    overlay.addEventListener("click", (e) => { if (e.target === overlay) finish(false); });
    overlay.querySelector("[data-confirm-cancel]").addEventListener("click", () => finish(false));
    overlay.querySelector("[data-confirm-ok]").addEventListener("click", () => {
      const valued = overlay.querySelector("[data-confirm-value]");
      finish(valued ? valued.value : true);
    });
    document.addEventListener("keydown", onKey);
    document.body.appendChild(overlay);
  });
}
