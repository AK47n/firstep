// fx/btn-icon.js — 按钮图标纯函数（工单 frontend-es-modules/01，迁自 index.html 8467-8485）
// data-ico 注入内联 SVG（16px stroke 风格）；自包含：name → SVG 字符串，未知返 ""。
export function btnIcon(name) {
  const S = ' fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"';
  const I = {
    rocket: '<path d="M8 1.5 L10 5.5 L13.5 11.5 L8 14 L2.5 11.5 L6 5.5 Z"/><circle cx="8" cy="7.6" r="1.6"/>',
    code: '<path d="M5 4 L2 8 L5 12 M11 4 L14 8 L11 12"/>',
    sparkles: '<path d="M8 1.8 L9.6 6.4 L14.2 8 L9.6 9.6 L8 14.2 L6.4 9.6 L1.8 8 L6.4 6.4 Z"/>',
    doc: '<path d="M4.5 1.5 H10 L12.5 4 V14.5 H4.5 Z"/><path d="M10 1.5 V4 H12.5"/>',
    clipboard: '<path d="M5.5 3 H10.5 V5 H5.5 Z"/><path d="M4.5 5 H11.5 V14 H4.5 Z"/>',
    wrench: '<path d="M10.2 2.2 A3.6 3.6 0 0 1 12 8.8 L5.8 15 L3.8 13 L10 7.2 A3.6 3.6 0 0 1 10.2 2.2 Z"/>',
    save: '<path d="M3 1.5 H13 V14.5 H3 Z"/><path d="M5 1.5 V6 H11 V1.5 M5 8 H11 V14.5"/>',
    copy: '<rect x="2.5" y="6" width="9" height="8.5" rx="1"/><rect x="5.5" y="2.5" width="9" height="8.5" rx="1"/>',
    check: '<path d="M2.5 8.5 L6 12 L13.5 4"/>',
    upload: '<path d="M8 3 V10.5 M4.5 6.5 L8 3 L11.5 6.5 M3 13.5 H13"/>',
    download: '<path d="M8 3 V10.5 M4.5 7 L8 10.5 L11.5 7 M3 13.5 H13"/>',
    wand: '<path d="M4.5 11.5 L11.5 4.5"/><path d="M6.5 2.5 V4.5 M5.5 3.5 H7.5 M12.5 7 V9 M11.5 8 H13.5"/>',
    trash: '<path d="M3 4.5 H13 M5.5 4.5 V2.5 H10.5 V4.5 M4.5 4.5 L5 13.5 H11 L11.5 4.5"/>',
  };
  return I[name]
    ? '<svg class="btn-ico" viewBox="0 0 16 16" width="15" height="15"' + S + '>' + I[name] + '</svg>'
    : "";
}

if (typeof window !== "undefined") {
  Object.assign(window, { btnIcon });
}
