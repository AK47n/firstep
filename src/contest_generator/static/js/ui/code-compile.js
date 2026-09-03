// ui/code-compile.js — 代码栏编译胶水（工单 code-tab-compile/03）
//
// 状态栏「编译」按钮 + 底部可折叠错误面板 + 错误行跳转：点击编译 →
// 自动保存全部脏标签（saveAllDirtyTabs，取消则中止）→ POST /api/compile
// （只带 output_dir，平台后端自动推断）→ SSE done → 面板状态行 + 结构化
// 错误列表（点击 = source-line 归一路径 → editJumpToFile 打开定位）。
// 纯件在 fx/code-compile.js；SSE 解析走 fx/llm.js parseSSE 单源；失败时
// 「去生成页一键编译修复」判据与「去生成页编辑 main.c」同源（目录 = 生成
// 上下文）。编译不调 LLM（无 aiAction 横幅）；AI 修复仍归生成页修复中心。
import { $, apiGet, apiPost, toast, toastError } from "/js/app.js";
import { parseHttpError } from "/js/fx/errors.js";
import { parseSSE } from "/js/fx/llm.js";
import {
  compileStatusText,
  compileStatusClass,
  compileErrorRowsHTML,
  AUTO_COMPILE_KEY,
} from "/js/fx/code-compile.js";
import {
  getCodeDir,
  getActiveTab,
  saveAllDirtyTabs,
  editJumpToFile,
  setCompileErrors,   // 编辑器侧错误显示态（工单 code-editor-refine/05：状态归 codeeditor——UI 单向依赖约定，见其模块态注释）
  onFileSaved,        // 保存成功监听（工单 10：自动编译只认手工保存）
} from "/js/ui/codeeditor.js";
import { getMainCDiskDir } from "/js/ui/generate-mainc-sync.js";
import { isMainCDiskDir } from "/js/ui/codeview.js";  // 单源谓词（评审整改：本模块不再重复实现）
import { scrollToStep } from "/js/ui/step-state.js";
import { startFixCenter } from "/js/ui/generate-fix.js";  // 一键编译修复入口（工单 code-ide-flow/04：跳转后自动开始）
import { showPanel, hidePanel } from "/js/ui/code-bottom-panels.js";  // 底部面板 tab 化（工单 06）

let compileBusy = false;

function panel() { return $("code-compile-panel"); }
function statusEl() { return $("code-compile-status"); }
function errorsEl() { return $("code-compile-errors"); }

// setStatus(text, cls)：状态行（cls = ok / err / ""）。
function setStatus(text, cls) {
  const el = statusEl();
  if (!el) return;
  el.textContent = text || "";
  el.className = "code-compile-status" + (cls ? " " + cls : "");
}

function setErrors(html) {
  const el = errorsEl();
  if (el) el.innerHTML = html || "";
}

// setGotoVisible(failVisible)：「在此修复」（工单 code-ide-ai/06：IDE 内跑
// 修复循环——与生成页同 /api/compile + /api/fix-errors 端口，任意打开目录
// 可跑，问题文本为空时降级）仅当编译失败且非超时可见；「去生成页一键编译
// 修复」多一个生成上下文限制（去生成页修复中心才有赛题/AI 修复上下文）。
function setGotoVisible(failVisible) {
  const here = $("btn-code-compile-fix-here");
  if (here) here.classList.toggle("hidden", !failVisible);
  const btn = $("btn-code-compile-goto");
  if (btn) btn.classList.toggle("hidden", !(failVisible && isMainCDiskDir()));
}

function openPanel() {
  showPanel("compile");
}

// renderDone(done)：done 载荷 → 状态行 + 错误列表 + 失败自动展开列表。
// 编译通过 → toast 提示可烧录（工单 code-editor-utilize/04：「改-编译-烧录」
// 闭环衔接——不自动烧录，用户手动确认）。
function renderDone(done) {
  openPanel();
  setStatus(compileStatusText(done), compileStatusClass(done));
  const errs = done.parsed_errors || [];
  setCompileErrors(errs);
  setErrors(compileErrorRowsHTML(errs));
  setGotoVisible(!done.passed && !done.timed_out);   // 「在此修复」任意目录；「去生成页」内部再叠加 isMainCDiskDir
  if (errs.length) {
    const p = panel();
    if (p) p.classList.remove("collapsed");   // 失败自动展开（用户可再收起）
  }
  if (done.passed) toast("ok", "编译通过——可点状态栏「烧录到板子」写入板子");
}

// runCompileOnceForCode(dir)：SSE 单次编译（/api/compile 只带 output_dir，
// 平台自动推断=工单 01）→ done；HTTP 非 2xx / SSE error / 断线 → throw 中文。
async function runCompileOnceForCode(dir) {
  let done = null;
  let errMsg = null;
  let finished = false;
  let resp;
  try {
    resp = await fetch("/api/compile", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ output_dir: dir }),
    });
  } catch (e) {
    throw new Error("编译未能启动：" + e.message);
  }
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(parseHttpError(resp.status, err).text);
  }
  await parseSSE(resp, (type, raw) => {
    let data = {};
    try { data = JSON.parse(raw || "null") || {}; } catch { data = {}; }
    if (type === "done") { done = data; finished = true; }
    else if (type === "error") { errMsg = data.message || "编译失败"; finished = true; }
  });
  if (errMsg) throw new Error(errMsg);
  if (!done) throw new Error(finished ? "编译未返回结果" : "连接中断：本次编译未完成，可安全重试");
  return done;
}

// runCodeCompile()：编译入口——自动保存全部（取消 → 中止）→ SSE 编译 → 面板。
// 重入保护从点击起生效（含自动保存阶段——保存期间再点不会并发两套保存）。
export async function runCodeCompile() {
  const dir = getCodeDir();
  if (!dir) { toast("info", "请先打开工程目录（选择文件夹或最近生成记录「查看代码」）"); return; }
  if (compileBusy) return;
  compileBusy = true;
  const btn = $("btn-code-compile");
  if (btn) {
    btn.disabled = true;
    btn.textContent = "编译中…";
  }
  openPanel();
  setStatus("编译中…", "");
  setErrors("");
  setCompileErrors([]);        // 重编开始即清旧错误（工单 05：成功清除/重试无线索残留）
  setGotoVisible(false);
  try {
    const saved = await saveAllDirtyTabs();
    if (!saved.ok) {
      toast("info", "有未保存修改未落盘，已中止编译（可先保存或处理冲突后再试）");
      return;
    }
    renderDone(await runCompileOnceForCode(dir));
  } catch (e) {
    openPanel();
    setStatus(e.message, "err");
    setErrors("");
    setCompileErrors([]);
    setGotoVisible(false);
    toastError(e, "编译失败");
  } finally {
    compileBusy = false;
    if (btn) {
      btn.disabled = false;
      btn.textContent = "编译";
    }
  }
}

// jumpToCompileError(path, line)：错误行点击 → 兜底链（spec 决策）：
// ①先试原始 path 打开（GET /api/code/file 预检——memo/直读语义，失败 =
// 400 非法路径，如 UV4 `..\` 形态 / 工程文件基准目录路径）；
// ②失败 → POST /api/compile/source-line 取 path_resolved 归一；
// ③打开文件并定位（editJumpToFile 复用：未开 tab 打开 + 选区跳行 +
// 行高亮 + flash）。有效路径只花一次文件预检，不为每条错误多发 source-line。
async function jumpToCompileError(path, line) {
  const dir = getCodeDir();
  if (!dir || !path) return;
  const lineNo = Number(line) || 1;
  let resolved = path;
  try {
    await apiGet("/api/code/file?dir=" + encodeURIComponent(dir)
      + "&path=" + encodeURIComponent(path));
  } catch (e) {
    try {
      const data = await apiPost("/api/compile/source-line", {
        output_dir: dir,
        path,
        line: lineNo,
      });
      resolved = data.path_resolved;
    } catch (e2) {
      toastError(e2, "跳转到错误行失败");
      return;
    }
  }
  await editJumpToFile(resolved, lineNo);
}

// ===== 保存自动编译开关（工单 code-editor-refine/10）=====
// 状态栏 toggle（默认关）：localStorage（AUTO_COMPILE_KEY 单源）；开启后
// 手工保存成功（onFileSaved manual=true——程序化保存如编译前自动落盘不触发）
// → runCodeCompile（内部已含自动保存全部 + 防重入 compileBusy）。手动点
// 「编译」不受开关影响；编译失败只进错误面板（不弹额外提示，既有行为）。
function autoCompileEnabled() {
  try { return localStorage.getItem(AUTO_COMPILE_KEY) === "1"; } catch { return false; }
}

function setAutoCompileBtn(btn) {
  if (!btn) return;
  const on = autoCompileEnabled();
  btn.classList.toggle("on", on);
  btn.textContent = on ? "自动编译：开" : "自动编译：关";
  btn.title = on
    ? "已开启：保存成功自动触发编译（点此关闭）"
    : "保存成功后自动触发编译（默认关，点此开启）";
}

function initAutoCompileToggle() {
  const btn = $("btn-code-auto-compile");
  if (btn) btn.addEventListener("click", () => {
    const on = !autoCompileEnabled();
    try {
      localStorage.setItem(AUTO_COMPILE_KEY, on ? "1" : "0");
    } catch {
      // 隐私模式/禁用存储：写不进去——提示未生效，按钮回读真实态（评审整改）
      setAutoCompileBtn(btn);
      toast("info", "无法写入设置（浏览器存储不可用），本次操作未生效");
      return;
    }
    setAutoCompileBtn(btn);
    toast("info", on ? "已开启保存自动编译（保存成功即触发）" : "已关闭保存自动编译");
  });
  setAutoCompileBtn(btn);
  // 手工保存成功钩子：开关开 + 非编译中 → runCodeCompile（自身含防重入与
  // 自动保存全部）。编译失败沿用 runCodeCompile 既有 catch（toastError + 面板
  // err 态——与手动编译同路径，工单「不弹额外提示」= 无新增提示，按此理解）。
  // manual = 用户显式保存（Ctrl+S/保存按钮/保存全部/冲突覆盖确认）+ 程序化
  // 自动落盘（编译前 saveAllDirtyTabs/守卫/磁盘重载）不触发。
  onFileSaved((tab, resp, manual) => {
    if (!manual || !autoCompileEnabled()) return;
    if (compileBusy) return;   // 编译中连续保存不重复触发（工单 10 验收；runCodeCompile 内另有防重入）
    runCodeCompile();
  });
}

// initCodeCompile()：入口绑定（host 启动区调用；DOM 已就绪）。
export function initCodeCompile() {
  const btn = $("btn-code-compile");
  if (btn) btn.addEventListener("click", () => runCodeCompile());
  initAutoCompileToggle();

  const errors = errorsEl();
  if (errors) errors.addEventListener("click", (e) => {
    const row = e.target.closest("[data-compile-path]");
    if (!row) return;
    jumpToCompileError(row.dataset.compilePath, row.dataset.compileLine);
  });

  // 行号色点点击（工单 code-editor-refine/05）：错误行 gutter 点 → 复用兜底链
  // 跳转（jumpToCompileError 已有原始 path 预检 + source-line 归一）。折叠箭头
  // 不拦截（展开/折叠优先）；占位行无色点类。
  const viewer = $("code-viewer");
  if (viewer) viewer.addEventListener("click", (e) => {
    if (e.target.closest(".code-fold-arrow")) return;
    const gn = e.target.closest(".code-gutter-line.code-err-line");
    if (!gn) return;
    const tab = getActiveTab();
    if (!tab) return;
    jumpToCompileError(tab.path, Number(gn.dataset.codeLine) || 1);
  });

  const clear = $("btn-code-compile-clear");
  if (clear) clear.addEventListener("click", () => {
    hidePanel("compile");
    setStatus("", "");
    setErrors("");
    setCompileErrors([]);
    setGotoVisible(false);
  });

  const collapse = $("btn-code-compile-collapse");
  if (collapse) collapse.addEventListener("click", () => {
    const p = panel();
    if (!p) return;
    const collapsed = p.classList.toggle("collapsed");
    collapse.textContent = collapsed ? "展开" : "收起";
    collapse.title = collapsed ? "展开错误列表" : "收起错误列表";
  });

  // 「去生成页一键编译修复」→ 跳转并自动开始修复循环（工单 code-ide-flow/04）：
  // startFixCenter 自带全部前置校验（输出目录/平台/工具链）与写盘守卫
  // （未保存编辑 → 保存全部或取消中止），无需本侧重复；循环运行中防重入。
  const goto = $("btn-code-compile-goto");
  if (goto) goto.addEventListener("click", () => {
    const tab = document.querySelector('nav button[data-tab="generate"]');
    if (tab) tab.click();
    scrollToStep(10);   // 修复中心（生成页步骤 10）
    startFixCenter();
  });
}
