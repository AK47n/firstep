// fx/guide.js — 「新手指引」教程页纯函数（工单 beginner-guide/01：
// 子页签定义 / 面板 id 映射 / 方向键循环；工单 02 起在此扩展教程正文数据与
// HTML 渲染单源）。无 DOM / fetch——node:test 直测。模块约定见 fx/core.js 头部。

// 子页签定义（key = data-guide-tab / 面板 id 后缀；label = 子页签文案）。
// index.html #guide-tabs 静态按钮标记与 GUIDE_TABS 的契约由 tests/js/guide.test.mjs
// 守卫钉住（键 / 顺序 / 面板 id 一一对应，防四处漂移）。
export const GUIDE_TABS = [
  { key: "prepare", label: "准备" },
  { key: "build", label: "做题主线" },
  { key: "compile", label: "编译与上板" },
  { key: "deliver", label: "交付与收尾" },
];

/** tab key → 面板 id（index.html #guide-panel-<key> 面板容器契约）。 */
export function guidePanelFor(tab) {
  return "guide-panel-" + tab;
}

/** 方向键循环：index 移动 dir 步（±1，Home/End 由 ui 层直给 0/count-1），
 * 在 [0, count) 内回绕；count=0 返回 -1。 */
export function guideTabNext(index, dir, count) {
  const n = Math.max(0, Math.floor(Number(count) || 0));
  if (n === 0) return -1;
  const i = Number.isFinite(Number(index)) ? Math.floor(Number(index)) : 0;
  return ((i + dir) % n + n) % n;
}

// window 桥（fx 模块通用兼容层，见 fx/core.js：44）：供 index.html 直调 /
// 旧脚本内联引用的同名全局；node 测试环境无 window。
if (typeof window !== "undefined") {
  Object.assign(window, { GUIDE_TABS, guidePanelFor, guideTabNext });
}
