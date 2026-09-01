// ui/code-fix-panel.js — IDE 修复面板（工单 code-ide-ai/06，B 全配双出口）
//
// 底部面板 #code-fix-panel 与编译/变更/AI 对话面板同型并列；绑定工单 05
// 共享状态机的长驻回调（subscribeFixCenter——单实例循环无论从生成页还是
// IDE 触发，本面板与生成页修复中心同步广播）。入口：编译失败面板「在此修复」
// 按钮（在 IDE 内跑修复循环；「去生成页一键编译修复」B 低配按钮保留——
// 双出口并存）。写盘守卫与生成页入口同口径（guardCodeTabWrite(WG.fix)，
// 取消 → 中止；IDE 无输出目录/循环进行中 → 按钮态或提示）。
// 感知闭环：onCompiled（修复与重编译之间 fix-errors 已落盘）→
// checkCodeDiskChanges()——变更面板自动出现（干净标签自动重载磁盘版）。
import { $, apiPost, toast } from "/js/app.js";
import { confirmModal } from "/js/ui/confirm.js";  // 回滚确认（与生成页同文案）
import { fixRowHTML } from "/js/fx/fix-rows.js";
import { guardCodeTabWrite } from "/js/ui/code-write-guard.js";
import { WRITE_GUARD_ACTIONS as WG } from "/js/fx/write-guard.js";
import { aiActionStart, aiActionStop } from "/js/ui/ai-banner.js";
import { checkCodeDiskChanges } from "/js/ui/codeview.js";  // 感知联动（checkCodeDiskChanges 导出自 code-ide-flow/02）
import { fixRenderResults } from "/js/ui/generate-fix.js";  // 最终列表重建共享（工单 06——行点击跳 IDE 编辑器）
import { getCodeDir, openEditorFile, editJumpToLine } from "/js/ui/codeeditor.js";
import { chosenPlatform } from "/js/ui/generate-recommend.js";  // 修复循环平台上下文（生成页所选项；null → 核心降级不传）
import {
  startFixCenterCore,
  continueFixCenterCore,
  subscribeFixCenter,
  isFixRunning,
  FIX_MAX_ROUNDS,
} from "/js/ui/fix-center-core.js";  // 共享状态机（工单 05）

// ---- 面板 inner 元素（index.html 常驻） ----
function statusEl() { return $("code-fix-status"); }
function roundEl() { return $("code-fix-round"); }
function errorsEl() { return $("code-fix-errors-msg"); }
function resultsEl() { return $("code-fix-results"); }
function rollbackBtn() { return $("btn-code-fix-rollback"); }
function continueBtn() { return $("btn-code-fix-continue"); }

// ---- 取消“修复中”的待写状态（本面板回滚态；生成页的 lastFix 在另一壳层） ----
let lastFix = null;

/** 展开面板（收起态展开）。 */
function openPanel() {
  const panel = $("code-fix-panel");
  if (!panel) return;
  if (panel.classList.contains("collapsed")) {
    panel.classList.remove("collapsed");
    const btn = $("btn-code-fix-collapse");
    if (btn) { btn.textContent = "收起"; btn.title = "收起修复状态"; }
  }
  panel.classList.remove("hidden");
  panel.scrollIntoView({ block: "nearest" });
}

// ---- 长驻回调（工单 05 事件广播 → 本面板 DOM；index.html 全 DOM 常驻） ----
const fixCb = {
  onState: (t) => { const el = statusEl(); if (el) el.textContent = t; },
  onError: (t) => { const el = errorsEl(); if (el) el.textContent = t; },
  onRound: (t) => { const el = roundEl(); if (el) el.textContent = t; },
  onApply: (item) => {
    const el = statusEl(); if (el) el.textContent = "";
    const list = resultsEl();
    if (!list) return;
    list.insertAdjacentHTML("beforeend", fixRowHTML(item));
    const row = list.lastElementChild;
    if (row) row.addEventListener("click", () => ideRowClick(row));
  },
  onList: (parsed, fixes, round) => {
    // 最终列表重建（与生成页同渲染逻辑；行点击 = IDE 跳转编辑器而非源码行展开）
    fixRenderResults(parsed, fixes, round, resultsEl(), ideRowClick);
  },
  // （onLog/onBanner/onTelemetry 不订阅——编译输出日志、横幅与 LLM 用量展示
  // 属生成页上下文；emitAll 对缺失键安全跳过。）
  onDone: (data, outputDir) => {
    lastFix = data && data.backup_id
      ? { output_dir: outputDir, backup_id: data.backup_id } : null;
    const rb = rollbackBtn();
    if (rb) rb.classList.toggle("hidden", !lastFix);
  },
  onReset: () => {
    const el = statusEl(); if (el) el.textContent = "";
    const re = errorsEl(); if (re) re.textContent = "";
    const rr = roundEl(); if (rr) rr.textContent = "";
    const list = resultsEl(); if (list) list.innerHTML = "";
    lastFix = null;
    const rb = rollbackBtn(); if (rb) rb.classList.add("hidden");
    const cb = continueBtn(); if (cb) cb.classList.add("hidden");
  },
  onBusy: (b) => {
    const rb = rollbackBtn(); if (rb) rb.disabled = b;
    const cb = continueBtn(); if (cb) cb.disabled = b;
    const here = $("btn-code-compile-fix-here");
    if (here) here.disabled = b;
  },
  onResume: (resume) => {
    const cb = continueBtn();
    if (cb) cb.classList.toggle("hidden", !resume);
  },
  onCompiled: () => {
    // 感知闭环（验收 4）：修复/重编译期间 fix-errors 已写盘 → 立即检查磁盘
    // 基线——变更面板自动出现、干净标签自动重载磁盘版。
    checkCodeDiskChanges();
  },
};
subscribeFixCenter(fixCb);

// ---- 入口：编译失败 → 「在此修复」 ----
function fixInput() {
  return {
    outputDir: getCodeDir() || "",
    platform: chosenPlatform || undefined,
    problemText: "",   // IDE 无赛题原文输入（生成页上下文才有——循环仍可跑，降级）
    mainC: "",
    slugs: [],
    callbacks: fixCb,
  };
}

/** 「在此修复」（IDE 内跑修复循环）：校验目录 + 写盘守卫（与生成页同口径）
 * → startFixCenterCore（单实例 running 防重入；生成页入口同时可用）。 */
async function startFixHere() {
  if (isFixRunning()) { toast("info", "修复循环进行中（生成页或本面板已启动），请等待完成"); return; }
  const dir = getCodeDir();
  if (!dir) { toast("error", "请先打开工程目录（选择文件夹或最近记录「查看代码」）"); return; }
  openPanel();
  // anyDir（与工单 04 AI apply 同语义）：IDE 内发起的修复动作在任意目录都该
  // 防未保存编辑覆盖（生成页入口保持上下文目录限定语义不变）。
  if (!await guardCodeTabWrite(WG.fix, { anyDir: true })) return;   // 脏标签确认/取消（取消 → 中止）
  aiActionStart("编译修复");   // 全局「AI 行动中」横幅（与生成页入口同）
  try {
    await startFixCenterCore(fixInput());
  } finally {
    aiActionStop();
  }
}

/** 「继续修复」（IDE 面板）：轮上限终态续跑（与生成页同消费核心 resume）。 */
async function continueFixHere() {
  if (isFixRunning()) return;
  if (!await guardCodeTabWrite(WG.continueFix, { anyDir: true })) return;
  const cb = continueBtn();
  if (cb) cb.classList.add("hidden");
  aiActionStart("编译修复");
  try {
    await continueFixCenterCore(fixInput());
  } finally {
    aiActionStop();
  }
}

/** 行点击（IDE 版）：打开编辑器 + 跳该行（生成页版为 fixToggleSource——
 * 展开源码行/main.c 预览；IDE 语义不同，仿 code-compile 行跳转）。 */
function ideRowClick(row) {
  const src = row && row._source;
  if (!src || !src.path) return;
  openEditorFile(src.path)
    .then(() => editJumpToLine(src.line))
    .catch(() => { /* 文件打开失败（如只读/不存在）：保持现状 */ });
}

/** 回滚本次修复（与生成页同确认文案、同端点）。 */
async function rollbackFix() {
  if (!lastFix) return;
  if (!await confirmModal({
    title: "确认回滚？",
    message: "回滚本次修复？将把备份的文件内容恢复到写回前状态。",
    danger: true,
    confirmText: "确认回滚",
  })) return;
  const rb = rollbackBtn();
  if (rb) rb.disabled = true;
  const el = errorsEl(); if (el) el.textContent = "";
  try {
    const data = await apiPost("/api/fix-errors/rollback", lastFix);
    const st = statusEl(); if (st) st.textContent = "已回滚（文件内容已恢复，可重新编译验证）";
    lastFix = null;
    if (rb) rb.classList.add("hidden");
    toast("ok", "已回滚 " + data.restored.length + " 个文件：" + data.restored.join("、"));
    checkCodeDiskChanges();   // 回滚也写盘 → 感知
  } catch (e) {
    if (el) el.textContent = e.message;
  } finally {
    if (rb) rb.disabled = false;
  }
}

// ===== 接线 =====
export function initCodeFixPanel() {
  const here = $("btn-code-compile-fix-here");
  if (here) here.addEventListener("click", startFixHere);

  const cb = continueBtn();
  if (cb) {
    cb.addEventListener("click", continueFixHere);
    cb.textContent = "继续修复（再来 " + FIX_MAX_ROUNDS + " 轮）";
  }
  const rb = rollbackBtn();
  if (rb) rb.addEventListener("click", rollbackFix);

  const collapse = $("btn-code-fix-collapse");
  if (collapse) collapse.addEventListener("click", () => {
    const panel = $("code-fix-panel");
    if (!panel) return;
    const collapsed = panel.classList.toggle("collapsed");
    collapse.textContent = collapsed ? "展开" : "收起";
    collapse.title = collapsed ? "展开修复状态" : "收起修复状态";
  });
}
