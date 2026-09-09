// fx/overlay.js — 确认弹窗纯件（工单 master-library-ui-2/04：共享 confirm
// 工厂的 HTML 纯件；05 全仓库迁移复用——遮罩 / 双钮 / 危险色 / extra 内容）。
// esc 单源取自 fx/core.js；extra 为调用方已控制的内容（如平台下拉）原样
// 透传，本纯件不对其转义（调用方保证——与 ref 轮弹窗 extra 同理）。
import { esc } from "./core.js";

// overlayConfirmHTML(opts)：确认弹窗内容纯函数——opts = {title, message,
// danger（默认 true = 主钮危险红）/ confirmText / cancelText / extra（可选
// HTML 片段，追加在消息后，如平台选择下拉）}。data-confirm-ok /
// data-confirm-cancel 交事件层（ui/confirm.js 工厂）。
// data-confirm-error = 就地校验错误槽（默认隐藏，工单 code-tree-ops/02
// 在途盘点补口）：确认前校验失败时弹窗**不关闭**，错误显示在这里。
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
    <div class="ref-detail-scroll"><div class="confirm-message">${esc(message)}</div>${extra}
      <div class="confirm-error error hidden" data-confirm-error role="alert"></div></div>
    <div class="pdf-detail-actions">
      <button type="button" class="${danger ? "danger" : "primary"}" data-confirm-ok>${esc(confirmText)}</button>
      <button type="button" data-confirm-cancel>${esc(cancelText)}</button>
    </div>
  </div>`;
}

// menuClamp(x, y, w, h, vw, vh)：浮层菜单定位防视口溢出（共享组件
// ui/context-menu.js 与文件树菜单共用；原随 06 树菜单落位 code-tree-ops，
// 07 泛化后归浮层纯件族本模块）——fixed 坐标 {left, top} 钳到 [8px 边距,
// 视口尺寸 - 菜单尺寸 - 8px]；菜单比视口大时贴 8px 边（配合 CSS
// max-height + overflow-y 兜底，见 index.html）。返回纯坐标，无副作用。
export function menuClamp(x, y, w, h, vw, vh) {
  const pad = 8;
  return {
    left: Math.max(pad, Math.min(x, vw - w - pad)),
    top: Math.max(pad, Math.min(y, vh - h - pad)),
  };
}

if (typeof window !== "undefined") {
  Object.assign(window, { overlayConfirmHTML, menuClamp });
}
