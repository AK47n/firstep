// fx/overlay.js — 确认弹窗纯件（工单 master-library-ui-2/04：共享 confirm
// 工厂的 HTML 纯件；05 全仓库迁移复用——遮罩 / 双钮 / 危险色 / extra 内容）。
// esc 单源取自 fx/core.js；extra 为调用方已控制的内容（如平台下拉）原样
// 透传，本纯件不对其转义（调用方保证——与 ref 轮弹窗 extra 同理）。
import { esc } from "./core.js";

// overlayConfirmHTML(opts)：确认弹窗内容纯函数——opts = {title, message,
// danger（默认 true = 主钮危险红）/ confirmText / cancelText / extra（可选
// HTML 片段，追加在消息后，如平台选择下拉）}。data-confirm-ok /
// data-confirm-cancel 交事件层（ui/confirm.js 工厂）。
export function overlayConfirmHTML({
  title,
  message,
  danger = true,
  confirmText = "确认",
  cancelText = "取消",
  extra = "",
} = {}) {
  return `<div class="ref-files-modal confirm-modal">
    <div class="ref-files-head"><strong>${esc(title)}</strong>
      <button class="ref-files-close" title="关闭">×</button></div>
    <div class="ref-detail-scroll"><div class="confirm-message">${esc(message)}</div>${extra}</div>
    <div class="pdf-detail-actions">
      <button type="button" class="${danger ? "danger" : "primary"}" data-confirm-ok>${esc(confirmText)}</button>
      <button type="button" data-confirm-cancel>${esc(cancelText)}</button>
    </div>
  </div>`;
}

if (typeof window !== "undefined") {
  Object.assign(window, { overlayConfirmHTML });
}
