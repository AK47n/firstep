// ui/generate-mainc-sync.js — 生成页 · main.c 磁盘同步（工单 mainc-codeview-bridge/01）
//
// 职责：记录「生成上下文目录」，渲染步骤 8 状态行，提供「从磁盘重新加载」。
// 差异检测事件驱动不轮询——生成成功 / 任务执行成功 / 深化完成 / 修订应用后
// 调 refreshMainCDiskState()（工单 02 消费这些钩子）；加载 = 覆盖编辑框 +
// dispatch input 事件（编程赋值不触发 input，一次性触发既有监听：高亮同步
// generate-mainc.js + 草稿保存 generate-steps.js），避免 ui 模块间循环 import。
// 只读端点复用 /api/code/file（dir=输出目录、path=main.c，安全口径见 codeview.py）。
// 状态：模块唯一 mutable 状态 = diskDir / diskState（会话级；磁盘文本不缓存——
// 差异判定与加载都直读 API 结果，避免只写不读的缓存态）。
// 纯件在 fx/mainc-sync.js。
import { $, apiGet, toastError } from "/js/app.js";
import { maincDiskStateHTML, maincDiffers } from "/js/fx/mainc-sync.js";

const MAIN_C_PATH = "main.c";

let diskDir = "";
let diskState = "none";  // none | written | changed | synced

function stateBox() { return $("mainc-disk-state"); }

function renderDiskState() {
  const box = stateBox();
  if (!box) return;
  if (!diskDir || diskState === "none") {
    box.classList.add("hidden");
    box.innerHTML = "";
    return;
  }
  box.innerHTML = maincDiskStateHTML(diskState, diskDir);
  box.classList.remove("hidden");
}

// getMainCDiskDir()：当前生成上下文目录（草稿持久化 / 双向跳转消费）。
export function getMainCDiskDir() { return diskDir; }

// setMainCDiskContext(dir)：生成成功 / 草稿恢复后记录上下文。
// 生成成功时编辑框 = 写盘快照（同内容），状态 = written；
// 草稿恢复调用方应再 refreshMainCDiskState() 校验磁盘现状。
export function setMainCDiskContext(dir) {
  diskDir = String(dir || "");
  diskState = diskDir ? "written" : "none";
  renderDiskState();
}

// loadDiskMainC()：读磁盘 main.c → 覆盖编辑框 → 触发高亮/草稿保存；
// 失败 toastError 且编辑框不动（异步安全：读成功前不写）。
export async function loadDiskMainC() {
  if (!diskDir) return;
  try {
    const data = await apiGet(codeFileURL(diskDir, MAIN_C_PATH));
    const content = (data && data.content) != null ? String(data.content) : "";
    const ta = $("main-c");
    if (!ta) return;
    ta.value = content;
    diskState = "synced";
    renderDiskState();
    ta.dispatchEvent(new Event("input", { bubbles: true }));
  } catch (e) {
    toastError(e, "从磁盘读取 main.c 失败");  // 编辑框不动
  }
}

// refreshMainCDiskState()：差异检测——磁盘 ≠ 编辑框 → changed（等待用户加载），
// 相同 → synced。读取失败静默保留现状态（不打扰，不覆盖用户未保存编辑）。
export async function refreshMainCDiskState() {
  if (!diskDir) return;
  try {
    const data = await apiGet(codeFileURL(diskDir, MAIN_C_PATH));
    const content = (data && data.content) != null ? String(data.content) : "";
    const ta = $("main-c");
    const same = !maincDiffers(content, ta ? ta.value : "");
    diskState = same ? "synced" : "changed";
    renderDiskState();
  } catch (e) {
    /* 静默：读取失败不打扰 */
  }
}

function codeFileURL(dir, path) {
  return "/api/code/file?dir=" + encodeURIComponent(dir)
    + "&path=" + encodeURIComponent(path);
}

// initMainCDiskSync()：状态行点击委托（[data-mainc-reload] → 加载）。
export function initMainCDiskSync() {
  const box = stateBox();
  if (!box) return;
  box.addEventListener("click", (e) => {
    if (e.target.closest("[data-mainc-reload]")) loadDiskMainC();
  });
}
