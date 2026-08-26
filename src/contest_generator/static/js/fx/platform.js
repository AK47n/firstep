// fx/platform.js — 平台卡点击决策纯函数（工单 frontend-es-modules/01，迁自 index.html 2347-2355）
// 三态：same = 重复点击已选平台（无操作）；first = 首次选择（保留下游选择）；
// switch = 真实切换平台（下游全部重来）。
export function platformClickAction(current, clicked) {
  if (current === clicked) return "same";
  if (current === null) return "first";
  return "switch";
}

if (typeof window !== "undefined") {
  Object.assign(window, { platformClickAction });
}
