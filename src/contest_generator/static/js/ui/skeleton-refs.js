// ui/skeleton-refs.js — 生成页 · 骨架引用模块锚定胶水（工单 mainc-codeview-bridge/04）
//
// 渲染步骤 8 编辑框下方的「骨架引用的模块」chips（fx/skeleton-refs.js 纯提取；
// 与已选模块匹配，点击开 module-info 详情弹窗——与推荐卡同款，改不了它的
// 元数据部分）。触发 = #main-c input（防抖 200ms；覆盖用户手输与
// loadDiskMainC 的 dispatch input）+ 显式调用（骨架/自检生成成功、草稿恢复
// 的编程赋值不走 input 事件）。无命中整区隐藏（宁少标不错标）。
// 状态：本模块无跨簇 mutable 状态（refTimer 模块内私有）。
import { $ } from "/js/app.js";
import { selectedSlugs, chosenPlatform, openModuleInfo } from "/js/ui/generate-recommend.js";
import { skeletonModuleRefs, skeletonRefsHTML } from "/js/fx/skeleton-refs.js";

let refTimer = 0;
const REF_DEBOUNCE_MS = 200;

// renderSkeletonRefs()：读取编辑框 + 已选模块 → 渲染 chips / 隐藏；
// 供启动、骨架生成成功、草稿恢复三处显式调用（编程赋值不走 input 事件）。
export function renderSkeletonRefs() {
  const box = $("skeleton-module-refs");
  if (!box) return;
  const ta = $("main-c");
  const refs = skeletonModuleRefs(ta ? ta.value : "", selectedSlugs);
  if (!refs.length) {
    box.classList.add("hidden");
    box.innerHTML = "";
    return;
  }
  box.innerHTML = skeletonRefsHTML(refs);
  box.classList.remove("hidden");
}

function scheduleRender() {
  clearTimeout(refTimer);
  refTimer = setTimeout(renderSkeletonRefs, REF_DEBOUNCE_MS);
}

// initSkeletonRefs()：input 防抖监听 + chips 点击委托（openModuleInfo 同条目；
// platform 显式传 chosenPlatform 避免依赖默认参数时序）+ 首帧渲染。
export function initSkeletonRefs() {
  const ta = $("main-c");
  if (!ta) return;
  ta.addEventListener("input", scheduleRender);
  const box = $("skeleton-module-refs");
  if (box) {
    box.addEventListener("click", (e) => {
      const chip = e.target.closest("[data-skeleton-ref]");
      if (chip) openModuleInfo(chip.dataset.skeletonRef, chosenPlatform);
    });
  }
  renderSkeletonRefs();
}
