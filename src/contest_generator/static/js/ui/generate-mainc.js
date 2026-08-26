// ui/generate-mainc.js — 生成页 · main.c 预览工具（阶段 2 工单 14，源自
// index.html 2325-2440 三节：main.c 行号 + 语法着色 / 代码字号缩放 / main.c 工具栏）
//
// DOM 胶水全量迁入：高亮同步（syncMainCHighlight + initMainCHighlight IIFE）/
// 字号缩放（currentCodeZoomPct / applyCodeZoom / initCodeZoom IIFE + 常量
// CODE_ZOOM_STEP / CODE_ZOOM_BASE / CODE_ZOOM_KEY）/ 工具栏（initMainCTools：
// 复制 / 下载 / 全屏）。纯件在 fx/code.js（cHighlight / cLineCount /
// codeZoomClamp / parseZoomStored / maincContentEmpty / maincFullscreenLabel——
// 本模块 import 调用；maincLineOffsetRange / isMainCPath 属行跳转簇，host 侧使用）。
// 状态所有权：本模块无跨簇 mutable 状态（CODE_ZOOM_KEY 的 localStorage 键名与
// .code-wrap font-size 为模块内私有；host 经顶部 import 活绑定调用
// syncMainCHighlight（generateMain / restoreDraft 写入后重同步）与
// initMainCTools（启动区初始化））。
// IIFE（initMainCHighlight / initCodeZoom）在 import 时自执行（module 脚本延迟
// 执行，DOM 已就绪）；顶层 addEventListener 随 IIFE 绑定。
import { $, toast } from "/js/app.js";
import { cHighlight, cLineCount, codeZoomClamp, parseZoomStored, maincContentEmpty, maincFullscreenLabel } from "/js/fx/code.js";

// ---------------------------------------------------------------------------
// main.c 行号 + 语法着色（工单 ui-polish-8/01）：textarea 透明文字 + 行号列 +
// 高亮层三明治；滚动三同步。cHighlight / cLineCount 已迁至 static/js/fx/code.js
// （本模块顶部 import，DOM 胶水直接引用）
// ---------------------------------------------------------------------------
// 滚动三同步（textarea → 行号列 / 高亮层）：syncMainCHighlight 与 scroll
// 监听器共用（评审工单 25 抽取，消除两处内联重复）。
function syncPanels(ta) {
  const nums = $("main-c-nums"); const hl = $("main-c-hl");
  hl.scrollTop = ta.scrollTop; hl.scrollLeft = ta.scrollLeft;
  nums.scrollTop = ta.scrollTop;
}
function syncMainCHighlight() {
  const ta = $("main-c"); const nums = $("main-c-nums"); const hl = $("main-c-hl");
  if (!ta || !nums || !hl) return;
  nums.textContent = cLineCount(ta.value);
  hl.innerHTML = cHighlight(ta.value);
  syncPanels(ta);
}
(function initMainCHighlight() {
  const ta = $("main-c"); const nums = $("main-c-nums"); const hl = $("main-c-hl");
  if (!ta || !nums || !hl) return;
  ta.addEventListener("input", syncMainCHighlight);
  ta.addEventListener("scroll", () => { syncPanels(ta); });
  syncMainCHighlight();
})();
// main.c 代码字号缩放（工单 code-zoom/01）：三明治以 .code-wrap 为字号基准，
// 改一层 font-size 三层同缩（行号列宽/缩进已是 em 联动）。codeZoomClamp /
// parseZoomStored 已迁至 static/js/fx/code.js（本模块顶部 import）
// ---------------------------------------------------------------------------
const CODE_ZOOM_STEP = 10;
const CODE_ZOOM_BASE = 13, CODE_ZOOM_KEY = "firstep.mainc.zoom";
function currentCodeZoomPct() {
  const wrap = $("main-c").closest(".code-wrap");
  const px = parseFloat(wrap ? wrap.style.fontSize : "");
  return px > 0 ? Math.round((px / CODE_ZOOM_BASE) * 100) : 100;
}
function applyCodeZoom(pct) {
  const wrap = $("main-c").closest(".code-wrap");
  if (!wrap) return;
  pct = codeZoomClamp(pct);
  wrap.style.fontSize = (CODE_ZOOM_BASE * pct / 100) + "px";
  $("code-zoom-label").textContent = pct + "%";
  try { localStorage.setItem(CODE_ZOOM_KEY, String(pct)); } catch (e) {}
  syncMainCHighlight(); // 行距变了，滚动位置/行号列重新对齐
}
(function initCodeZoom() {
  const btnIn = $("btn-code-zoom-in"), btnOut = $("btn-code-zoom-out");
  if (!btnIn || !btnOut) return;
  let pct = 100;
  try { pct = parseZoomStored(localStorage.getItem(CODE_ZOOM_KEY)); } catch (e) {}
  applyCodeZoom(pct);
  btnIn.addEventListener("click", () => applyCodeZoom(currentCodeZoomPct() + CODE_ZOOM_STEP));
  btnOut.addEventListener("click", () => applyCodeZoom(currentCodeZoomPct() - CODE_ZOOM_STEP));
})();

// ---------------------------------------------------------------------------
// main.c 工具栏（工单 mainc-tools/01）：复制 / 下载 / 全屏。
// 悬浮在 .code-wrap 右上角（与字号缩放同一工具条）；全屏 = 同一 DOM 原地
// fixed（三明治机制零改动）；maincContentEmpty / maincFullscreenLabel 已迁至
// static/js/fx/code.js（本模块顶部 import）
// ---------------------------------------------------------------------------
function initMainCTools() {
  const ta = $("main-c");
  const wrap = ta ? ta.closest(".code-wrap") : null;
  const btnCopy = $("btn-main-c-copy");
  const btnDownload = $("btn-main-c-download");
  const btnFull = $("btn-main-c-fullscreen");
  if (!ta || !wrap || !btnCopy || !btnDownload || !btnFull) return;
  // 空内容守卫 + 统一错误文案（复制/下载共用，防三处重复）
  const guardEmpty = () => {
    if (maincContentEmpty(ta.value)) {
      toast("info", "main.c 还没有内容，先生成骨架");
      return true;
    }
    return false;
  };
  const errText = (what, e) => what + "失败：" + (e && e.message || "未知错误");
  function copyValue() {
    if (guardEmpty()) return;
    const done = () => toast("ok", "main.c 已复制");
    const fallback = () => {
      try {
        ta.select();
        if (document.execCommand && document.execCommand("copy")) { toast("ok", "main.c 已复制"); return; }
        toast("error", "复制失败：请手动全选复制");
      } catch (e) { toast("error", errText("复制", e)); }
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(ta.value).then(done).catch(fallback);
    } else fallback();
  }
  function downloadValue() {
    if (guardEmpty()) return;
    try {
      const blob = new Blob([ta.value], { type: "text/plain;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "main.c";
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      toast("ok", "main.c 已下载");
    } catch (e) { toast("error", errText("下载", e)); }
  }
  function setFullscreen(active) {
    wrap.classList.toggle("fullscreen", active);
    document.body.classList.toggle("code-full-body-lock", active);
    btnFull.textContent = maincFullscreenLabel(active);
  }
  btnCopy.addEventListener("click", copyValue);
  btnDownload.addEventListener("click", downloadValue);
  btnFull.addEventListener("click", () => setFullscreen(!wrap.classList.contains("fullscreen")));
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && wrap.classList.contains("fullscreen")) setFullscreen(false);
  });
}


// ---- 本簇导出面（host 顶部 import 活绑定调用点） ----
export { initMainCTools, syncMainCHighlight, currentCodeZoomPct, applyCodeZoom };
