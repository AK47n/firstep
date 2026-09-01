// ui/code-flash.js — 代码栏烧录胶水（工单 code-editor-utilize/04）
//
// 状态栏「烧录到板子」按钮 + 底部可折叠烧录面板：点击烧录 → 自动保存全部
// 脏标签（saveAllDirtyTabs，取消/冲突则中止）→ 共享执行体 ui/flash.js
// flashRunShared（POST /api/flash → flashResultHTML / 400 → flashGuideHTML）
// → 面板状态行 + 结果容器。平台参数传空（探针名仅 busy 文案展示用途，平台
// 后端从产物树反推，与生成页 chosenPlatform 前端状态解耦——代码栏不依赖
// 生成页上下文）。
import { $, toast, toastError } from "/js/app.js";
import { flashRunShared } from "/js/ui/flash.js";
import { getCodeDir, saveAllDirtyTabs } from "/js/ui/codeeditor.js";

let flashBusy = false;

function panel() { return $("code-flash-panel"); }
function statusEl() { return $("code-flash-status"); }
function resultEl() { return $("code-flash-result"); }

function openPanel() {
  const p = panel();
  if (p) p.classList.remove("hidden");
}

// runCodeFlash()：烧录入口——无目录提示；自动保存全部（取消 → 中止）→
// 共享执行体（按钮防重 + busy 文案 + 结果/指引卡渲染）。重入保护从点击起
// 生效（含自动保存阶段——保存期间再点不并发）。
export async function runCodeFlash() {
  const dir = getCodeDir();
  if (!dir) { toast("info", "请先打开工程目录（选择文件夹或最近生成记录「查看代码」）"); return; }
  if (flashBusy) return;
  flashBusy = true;
  const btn = $("btn-code-flash");
  if (btn) {
    btn.disabled = true;
    btn.textContent = "烧录中…";
  }
  openPanel();
  try {
    const saved = await saveAllDirtyTabs();
    if (!saved.ok) {
      toast("info", "有未保存修改未落盘，已中止烧录（可先保存或处理冲突后再试）");
      return;
    }
    await flashRunShared({
      dir,
      platform: "",
      statusEl: statusEl(),
      resultEl: resultEl(),
      setBusy: () => { /* 按钮防重已在本层处理（最终 finally 恢复） */ },
    });
  } catch (e) {
    // flashRunShared 内部已渲染 400 指引卡；此 catch 兜底意外异常（如保存链路
    // reject）——对齐 runCodeCompile 先例，失败有明确反馈且按钮由 finally 复位。
    toastError(e, "烧录失败");
  } finally {
    flashBusy = false;
    if (btn) {
      btn.disabled = false;
      btn.textContent = "烧录到板子";
    }
  }
}

// initCodeFlash()：入口绑定（host 启动区调用；DOM 已就绪）。
export function initCodeFlash() {
  const btn = $("btn-code-flash");
  if (btn) btn.addEventListener("click", () => runCodeFlash());

  const collapse = $("btn-code-flash-collapse");
  if (collapse) collapse.addEventListener("click", () => {
    const p = panel();
    if (!p) return;
    const collapsed = p.classList.toggle("collapsed");
    collapse.textContent = collapsed ? "展开" : "收起";
    collapse.title = collapsed ? "展开结果" : "收起结果";
  });
}
