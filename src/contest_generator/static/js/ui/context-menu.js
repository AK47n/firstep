// ui/context-menu.js — 共享浮层菜单（工单 code-editor-refine/06 创建、07 复用）
//
// 文件树右键菜单与选中代码动作菜单共用同一浮层与关闭通道；样式 = index.html
// .code-ctx-menu / .code-ctx-item（token 与 confirmModal 浮层同族，深浅主题
// 自适应）。项契约：items = [{label, danger?, run?}]（label 一律 esc 防注入；
// danger → code-ctx-item-danger 类；run = 点击回调，先关菜单再执行——动作
// 内部可能开模态/刷新树）。定位坐标由调用方给（右键 clientX/Y 或按钮 rect），
// 溢出钳制 = fx ctxMenuClamp（8px 边距；菜单超屏时 CSS max-height 兜底）。
// 关闭三通道：外部 mousedown（含右键——下一次 contextmenu 自然重开并跟随新
// 目标）/ 任意滚动（capture——树内滚动也关）/ Esc；菜单上右键 preventDefault
// 不叠浏览器原生菜单。
import { menuClamp } from "/js/fx/overlay.js";
import { esc } from "/js/fx/core.js";

let menuEl = null;

export function closeContextMenu() {
  if (menuEl) {
    menuEl.remove();
    menuEl = null;
  }
}

export function openContextMenu(items, x, y) {
  closeContextMenu();
  const el = document.createElement("div");
  el.className = "code-ctx-menu";
  el.innerHTML = (items || []).map((it, i) => '<button type="button" class="code-ctx-item'
    + (it.danger ? " code-ctx-item-danger" : "")
    + '" data-ctx-index="' + i + '">' + esc(it.label) + "</button>").join("");
  document.body.appendChild(el);
  const r = el.getBoundingClientRect();
  const pos = menuClamp(x, y, r.width, r.height, window.innerWidth, window.innerHeight);
  el.style.left = pos.left + "px";
  el.style.top = pos.top + "px";
  menuEl = el;
  el.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-ctx-index]");
    if (!btn) return;
    const item = items[Number(btn.dataset.ctxIndex)];
    closeContextMenu();
    if (item && item.run) Promise.resolve(item.run()).catch(() => { /* 被调方已自吞中文 toast；防未处理拒绝 */ });
  });
  el.addEventListener("contextmenu", (e) => e.preventDefault());
}

// 全局关闭通道：模块加载即绑一次（document 常驻；菜单单例，最近开的为准）。
document.addEventListener("mousedown", (e) => {
  if (menuEl && !menuEl.contains(e.target)) closeContextMenu();
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && menuEl) { e.preventDefault(); closeContextMenu(); }
});
document.addEventListener("scroll", () => { if (menuEl) closeContextMenu(); }, true);
