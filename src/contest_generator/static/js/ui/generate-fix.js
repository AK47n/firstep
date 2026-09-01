// ui/generate-fix.js — 生成页 · 编译修复中心（工单 autocompile-loop/01 等
// 全家桶：单次编译 / 修复循环 ≤3 轮 / 批继续 / 横幅四态 / 结果表 / telemetry /
// 就绪度）DOM 胶水（阶段 2 工单 16，源自 index.html 生成页：10. 修复中心节）。
//
// 工单 code-ide-ai/05（二期 B 全配第一步）：流程状态机已抽 ui/fix-center-core.js
//（无 DOM 纯流程 + 事件回调广播）；本模块 = 生成页**壳层**——校验/守卫 +
// 回调绑定现有 DOM 渲染（第 10 步修复中心行为零变化）；IDE 修复面板（工单
// 06）绑同回调双出口（单实例 fixLoop.running 跨出口天然共享）。
//
// 簇体保留：compileBanner / setFixCenterLog / fixKeyOf / fixKeyBasename /
// fixToggleSource / fixRenderResults / fixSetBusy / fixCenterBusy /
// renderToolchainStatus / renderFixLLMTelemetry / clearFixLLMTelemetry /
// updateFixCenterAvailability + 顶层监听器（btn-fix-center /
// btn-fix-continue / btn-fix-errors / btn-fix-rollback + continue 文案——
// import 时绑定：module 脚本延迟执行，DOM 已就绪）。
// 纯件在 fx/*.js（generate / llm / code）；状态读 A 簇（generate-recommend）
// chosenPlatform / selectedSlugs（活绑定只读——本簇是 toolchains 主写簇）。
// 跨簇：recordLLMUsage（usage）/ reportRecentStatus（recent）/ markStepDone
//（step-state）。A 簇对本簇的服务调用（updateFixCenterAvailability）仍经
// host 启动区注册的 setClusterDeps 闭包（与工单 13 pins 同构——A 不 import
// 本簇，避免 ui→ui 环；本簇单向 import A）。
import { $, apiPost, toast } from "/js/app.js";
import { confirmModal } from "/js/ui/confirm.js";
import { fixLogGroupHidden } from "/js/fx/generate.js";
import { formatLLMTelemetry } from "/js/fx/llm.js";
import { fixRowHTML } from "/js/fx/fix-rows.js";  // 修复结果行共享（工单 code-ide-ai/06）
import { isMainCPath, maincJumpToLine } from "/js/fx/code.js";
import { makeWaitClock } from "/js/ui/progress.js";  // 长任务秒表（工单 ux-walkthrough-02/12）
import { chosenPlatform, selectedSlugs } from "/js/ui/generate-recommend.js";
import { reportRecentStatus } from "/js/ui/recent.js";
import { recordLLMUsage } from "/js/ui/usage.js";
import { markStepDone } from "/js/ui/step-state.js";
import { aiActionStart, aiActionStop } from "/js/ui/ai-banner.js";  // 全局「AI 行动中」横幅（工单 ai-action-banner/02）
import { guardCodeTabWrite } from "/js/ui/code-write-guard.js";  // 生成侧覆盖保护（工单 code-write-guard/02）：写盘前保存代码栏未保存编辑
import { WRITE_GUARD_ACTIONS as WG } from "/js/fx/write-guard.js";  // 动作名单源（评审整改）
import {
  startFixCenterCore,
  continueFixCenterCore,
  runFixOnceCore,
  runCompileOnceCore,
  fixRoundsCore,
  subscribeFixCenter,
  isFixRunning,
  FIX_MAX_ROUNDS,
} from "/js/ui/fix-center-core.js";  // 流程核心（工单 code-ide-ai/05——无 DOM 状态机）
export { FIX_MAX_ROUNDS, fixLoop } from "/js/ui/fix-center-core.js";  // 导出面保持（check_contract / generate-core 活引用）

// ---------------------------------------------------------------------------
// 生成页：10. 修复中心（工单 autocompile-loop/01）——生成 → 自动编译 →
// 自动采集报错 → 喂 fix-errors 管线修复 → 重编译验证，循环 ≤3 轮；无工具链
// 回退贴文本模式（工单 compile-error-fix/01 既有路径保留）。事件词表镜像
// events.py：compile_start / parse_done / fix_start / apply_result / done /
// error（retry 是蒸馏层事件，修复流不发；实现发事件时再加回）。循环状态机
// 在前端（服务端只做单次编译），轮次可见"第 N/3 轮"。
// ---------------------------------------------------------------------------
let lastFix = null;          // {output_dir, backup_id}：回滚按钮的入口（done 终态后置位）
let toolchains = { stm32: false, mspm0: false };  // /api/state 装载：平台 → 工具链可用
function setToolchains(v) { toolchains = v; }  // 写入经 setter（host init / 设置页工具链重算）
let fixSourceCache = {};                          // 源码行缓存（key = 归一化 path:line；列表重建时清空）

const fixWait = makeWaitClock("fix-status");      // 长任务秒表（工单 ux-walkthrough-02/12）

/** 编译结果横幅四态（工单 compile-experience-ui/01）：running/success/fail/notool。 */
function compileBanner(kind, text) {
  const b = $("compile-banner");
  b.className = kind;   // 重置状态类（同时移除初始 hidden）
  b.textContent = text;
  if (kind === "success") { markStepDone(10); toast("ok", "编译通过"); }  // 修复中心闭环
}

/** 编译输出（自动采集）写入 + 分组显隐（工单 ux-polish/01）：无输出时整组隐藏，
 * 避免 rows=10 的空 readonly 文本框常驻占位；有输出（含 warnings）即露出。 */
function setFixCenterLog(text) {
  $("fix-center-log").value = text || "";
  $("fix-log-group").classList.toggle("hidden", fixLogGroupHidden(text));
}

// 错误条目 key（工单 compile-experience-ui/01）：path 归一 POSIX；精确匹配
// 未命中时 basename 兜底（fix-errors 的 file 可能是短名形态）
function fixKeyOf(path, line) {
  return ((path || "").replace(/\\/g, "/").replace(/^\.\/+/, "")) + ":" + (line || 0);
}
function fixKeyBasename(path, line) {
  const parts = ((path || "").replace(/\\/g, "/")).split("/");
  return "~" + (parts[parts.length - 1] || "") + ":" + (line || 0);
}

// ---------------------------------------------------------------------------
// main.c 错误行定位（工单 compile-error-jump/01 + error-jump-task/02 单源化）：
// 实现已迁至 static/js/fx/code.js（maincJumpToLine / maincScrollToRange——
// 修复中心与任务结果面板共用同一份；迁出后本模块只保留调用 + 错误码 toast，
// 三条消息语义逐字保留）。非 main.c 的行维持 fixToggleSource 展开源码行。
// ---------------------------------------------------------------------------

/** 点击条目 → 展开/收起对应源码行（薄接口 /api/compile/source-line，缓存防重复请求）。
 * main.c 错误行例外（工单 compile-error-jump/01）：整行点击 = 跳转 main.c
 * 预览定位（选中该行文本高亮），不再展开源码行。 */
async function fixToggleSource(row) {
  const src = row._source;
  if (!src || !src.path) return;
  if (isMainCPath(src.path)) {
    const reason = maincJumpToLine(src.line);
    if (reason === "empty") toast("info", "main.c 还没有内容，先「生成骨架」再跳转");
    else if (reason === "out-of-range") toast("info", "行号超出 main.c 范围：" + src.line);
    return;
  }
  const existing = row.querySelector(".fix-source");
  if (existing) { existing.remove(); return; }   // 再点收起
  const outputDir = $("res-dir").textContent.trim() || $("output-dir").value.trim();
  if (!outputDir) return;
  const key = fixKeyOf(src.path, src.line);
  try {
    let text = fixSourceCache[key];
    if (text === undefined) {   // 未命中缓存才发请求
      const data = await apiPost("/api/compile/source-line",
        { output_dir: outputDir, path: src.path, line: src.line });
      text = data.line_text;
      fixSourceCache[key] = text;
    }
    const line = document.createElement("div");
    line.className = "fix-source";
    line.textContent = (src.line || "?") + ": " + text;
    row.appendChild(line);
  } catch (e) {
    const err = document.createElement("div");
    err.className = "fix-source fix-source-err";
    err.textContent = "源码行加载失败：" + e.message;
    row.appendChild(err);
  }
}

/** 结构化错误列表渲染（工单 compile-experience-ui/01）：[状态标签] path:line 消息。
 * parsed = 解析出的错误（[{path,line,message}]）；fixes = 修复结果
 * （[{file,line,status,reason}]）；round ≤ 1 无对应 fix 标「待修复」、后续轮「新增」；
 * 无法匹配 parsed 的 fixes 单独列出。列表重建时清空源码行缓存（新一轮取修复后内容）。
 * listEl / onRowClick 可选（工单 code-ide-ai/06：IDE 修复面板复用——listEl=
 * 面板结果容器，onRowClick=IDE 行点击跳转编辑器；缺省 = 生成页容器 +
 * fixToggleSource）。 */
function fixRenderResults(parsed, fixes, round, listEl, onRowClick) {
  parsed = parsed || [];
  fixes = fixes || [];
  fixSourceCache = {};
  const list = listEl || $("fix-results");
  list.innerHTML = "";
  const exact = new Map(), fuzzy = new Map();
  for (const f of fixes) {
    exact.set(fixKeyOf(f.file, f.line), f);
    fuzzy.set(fixKeyBasename(f.file, f.line), f);
  }
  const appendRow = (entry, label, cls, extra) => {
    const row = document.createElement("div");
    row.className = "fix-row";
    const tag = document.createElement("span");
    tag.className = "fix-tag " + cls;
    tag.textContent = label;
    row.appendChild(tag);
    const file = document.createElement("span");
    file.className = "fix-file";
    file.textContent = (entry.path || entry.file || "?")
      + (entry.line ? ":" + entry.line : "");
    row.appendChild(file);
    const msg = document.createElement("span");
    msg.className = "fix-msg";
    msg.textContent = extra || entry.message || "";
    row.appendChild(msg);
    row._source = { path: entry.path || entry.file, line: entry.line };
    row.addEventListener("click", () => (onRowClick || fixToggleSource)(row));
    list.appendChild(row);
  };
  for (const p of parsed) {
    const f = exact.get(fixKeyOf(p.path, p.line)) || fuzzy.get(fixKeyBasename(p.path, p.line));
    if (f) {
      appendRow(p, f.status === "applied" ? "已修复" : "跳过",
        f.status === "applied" ? "fixed" : "skipped", f.reason);
    } else {
      appendRow(p, round <= 1 ? "待修复" : "新增", round <= 1 ? "pending" : "new", "");
    }
  }
  const unmatched = fixes.filter((f) => !parsed.some((p) =>
    fixKeyOf(p.path, p.line) === fixKeyOf(f.file, f.line)
    || fixKeyBasename(p.path, p.line) === fixKeyBasename(f.file, f.line)));
  for (const f of unmatched) {
    appendRow(f, f.status === "applied" ? "已修复" : "跳过",
      f.status === "applied" ? "fixed" : "skipped", f.reason);
  }
}

function fixSetBusy(busy) {   // 手动贴文本按钮
  $("btn-fix-errors").disabled = busy;
  $("btn-fix-errors").innerHTML = busy
    ? '<span class="spinner"></span>AI 修复中…' : "开始修复（贴文本）";
}

function fixCenterBusy(busy) {   // 一键编译修复 + 继续修复按钮
  $("btn-fix-center").disabled = busy || !toolchains[chosenPlatform] || !chosenPlatform;
  $("btn-fix-center").innerHTML = busy
    ? '<span class="spinner"></span>编译修复中…' : "一键编译修复";
  $("btn-fix-continue").disabled = busy;
}

function renderToolchainStatus() {
  const t = toolchains || {};
  $("fix-center-toolchain").textContent =
    "工具链：Keil UV4 " + (t.stm32 ? "✅" : "❌") + " / gmake " + (t.mspm0 ? "✅" : "❌")
    + "（缺失时一键按钮置灰，用下方贴文本模式；可在设置页配置路径）";
}

function renderFixLLMTelemetry(data) {
  const el = $("fix-llm-telemetry");
  el.textContent = formatLLMTelemetry(data);
  el.classList.remove("hidden");
}

function clearFixLLMTelemetry() {
  const el = $("fix-llm-telemetry");
  el.classList.add("hidden");
  el.textContent = "";
}

function updateFixCenterAvailability() {
  const ok = !!chosenPlatform && !!(toolchains || {})[chosenPlatform];
  $("btn-fix-center").disabled = !ok || isFixRunning();
  $("btn-fix-center").title = !chosenPlatform ? "请先选择目标平台"
    : ok ? "" : "未检测到该平台工具链（可在设置页配置路径），请用贴文本模式";
}

// ---------------------------------------------------------------------------
// 壳层输入 + 长驻回调（工单 code-ide-ai/05-06）：core 事件广播 → 本模块 DOM
// 渲染。fixCb 为模块级长驻订阅组（subscribeFixCenter 注册——单实例循环无论
// 从生成页还是 IDE 面板触发，本页 DOM 都能同步；index.html 全 DOM 常驻，
// 回调元素恒在，无需按面板显隐守卫）。fixInput() 每次流程启动时取
// （problem/main-c/平台可能已被用户改过——outputDir 同理取当下值）。
// ---------------------------------------------------------------------------
const fixCb = {
  onState: (t) => { $("fix-status").textContent = t; },
  onError: (t) => { $("fix-errors-msg").textContent = t; },
  onRound: (t) => { $("fix-center-round").textContent = t; },
  onApply: (item) => {
    $("fix-status").textContent = "";
    const list = $("fix-results");
    list.insertAdjacentHTML("beforeend", fixRowHTML(item));
    const row = list.lastElementChild;
    if (row) {
      row._source = { path: item.file, line: item.line };
      row.addEventListener("click", () => fixToggleSource(row));
    }
  },
  onLog: (t) => setFixCenterLog(t),
  onBanner: (kind, text) => compileBanner(kind, text),
  onList: (parsed, fixes, round) => fixRenderResults(parsed, fixes, round),
  onTelemetry: (data) => { renderFixLLMTelemetry(data); recordLLMUsage(data); },
  onDone: (data, outputDir) => {
    lastFix = data && data.backup_id
      ? { output_dir: outputDir, backup_id: data.backup_id } : null;
    $("btn-fix-rollback").classList.toggle("hidden", !lastFix);
  },
  onReset: () => {
    $("fix-errors-msg").textContent = "";
    $("fix-status").textContent = "";
    $("fix-results").innerHTML = "";
    $("fix-center-round").textContent = "";
    setFixCenterLog("");
    clearFixLLMTelemetry();
    lastFix = null;
    $("btn-fix-rollback").classList.add("hidden");
    $("btn-fix-continue").classList.add("hidden");   // 新循环开始即隐藏（工单 fix-loop-continue/01）
  },
  onBusy: (b) => fixCenterBusy(b),
  onResume: (resume) => {
    $("btn-fix-continue").classList.toggle("hidden", !resume);
  },
  onCompiled: (done, outputDir) => reportRecentStatus(outputDir, done),
};
subscribeFixCenter(fixCb);   // 长驻订阅（工单 06：IDE 面板触发的循环本页同步）

function fixInput() {
  return {
    outputDir: $("res-dir").textContent.trim() || $("output-dir").value.trim(),
    platform: chosenPlatform,
    problemText: $("problem").value.trim(),
    mainC: $("main-c").value.trim(),
    slugs: selectedSlugs,
    callbacks: fixCb,   // 触发方临时订阅（与长驻为同一组——无重复分发）
  };
}

/** 单次编译（导出面保持——检查表 import 用）：fixInput 组好调核心。 */
async function runCompileOnce(outputDir) {
  const input = fixInput();
  if (outputDir) input.outputDir = outputDir;
  return runCompileOnceCore(input);
}

/** 单次修复（导出面保持）：手动贴文本模式经 runFixOnceCore（新生命周期）。 */
async function runFixOnce(errorText, outputDir) {
  const input = fixInput();
  if (outputDir) input.outputDir = outputDir;
  return runFixOnceCore(input, errorText);
}

/** 修复轮批（导出面保持）。 */
async function fixRounds(errorText, lastSummary, previousDone) {
  const input = fixInput();
  return fixRoundsCore(input, errorText, lastSummary, previousDone);
}

/** 修复中心主入口（薄壳）：校验 + 写盘守卫在壳层（工单 code-ide-ai/05 决策），
 * 流程在核心（startFixCenterCore——内部 onReset/onBusy/onState 已清场）。 */
async function startFixCenter() {
  if (isFixRunning()) return;   // 单实例：循环中忽略重复触发
  const outputDir = $("res-dir").textContent.trim() || $("output-dir").value.trim();
  if (!outputDir) { $("fix-errors-msg").textContent = "请先生成工程（或填写输出目录）"; return; }
  if (!chosenPlatform) { $("fix-errors-msg").textContent = "请先选择目标平台"; return; }
  if (!(toolchains || {})[chosenPlatform]) {
    $("fix-errors-msg").textContent = "未检测到该平台工具链，已回退贴文本模式（见下方手动模式）";
    compileBanner("notool", "未检测到工具链，跳过自动编译（可在设置页填 uv4_path / gmake_path）");
    return;
  }
  // 生成侧覆盖保护（工单 code-write-guard/02）：代码栏同目录有未保存编辑 →
  // 先保存全部再编译修复（取消 → 中止，编辑保留）。放校验之后——无输出目录/
  // 无工具链时不打扰。
  if (!await guardCodeTabWrite(WG.fix)) return;
  aiActionStart("编译修复");   // 全局「AI 行动中」横幅（工单 ai-action-banner/02）
  fixWait.start();
  try {
    await startFixCenterCore(fixInput());
  } finally {
    aiActionStop();
    fixWait.stop();
  }
}

/** 「继续修复」（工单 fix-loop-continue/01）：从轮上限终态保存的续跑态再来
 * 一批 ≤3 轮——不重跑初始编译，previous_fixes 回喂上下文不丢。 */
async function continueFixCenter() {
  if (isFixRunning()) return;   // 批内防重复触发
  // 生成侧覆盖保护（工单 code-write-guard/02）：继续修复同样写盘（fix-errors
  // 回喂轮），复用路径与主入口一致拦截（评审整改补齐）。
  if (!await guardCodeTabWrite(WG.continueFix)) return;
  if (!$("btn-fix-continue").classList.contains("hidden")) {
    $("btn-fix-continue").classList.add("hidden");   // 进入新批即隐藏（终态时按结果重判）
  }
  aiActionStart("编译修复");   // 全局「AI 行动中」横幅（工单 ai-action-banner/02）
  fixWait.start();
  try {
    await continueFixCenterCore(fixInput());
  } finally {
    aiActionStop();
    fixWait.stop();
  }
}

$("btn-fix-center").addEventListener("click", startFixCenter);
$("btn-fix-continue").addEventListener("click", continueFixCenter);
$("btn-fix-continue").textContent = "继续修复（再来 " + FIX_MAX_ROUNDS + " 轮）";

$("btn-fix-errors").addEventListener("click", async () => {
  $("fix-errors-msg-manual").textContent = "";
  $("fix-status").textContent = "";
  const errorText = $("fix-errors-text").value.trim();
  if (!errorText) { $("fix-errors-msg-manual").textContent = "请先粘贴编译报错全文"; return; }
  const outputDir = $("res-dir").textContent.trim() || $("output-dir").value.trim();
  if (!outputDir) { $("fix-errors-msg-manual").textContent = "请先生成工程（或填写输出目录）"; return; }
  $("fix-results").innerHTML = "";   // 新生命周期：旧结果清空
  clearFixLLMTelemetry();
  lastFix = null;
  $("btn-fix-rollback").classList.add("hidden");
  $("btn-fix-continue").classList.add("hidden");
  fixSetBusy(true);
  aiActionStart("AI 修复");   // 全局「AI 行动中」横幅（工单 ai-action-banner/02）
  $("fix-status").textContent = "解析报错中…";
  fixWait.start();
  try {
    await runFixOnce(errorText, outputDir);
  } catch (e) {
    $("fix-errors-msg-manual").textContent = e.message;
  } finally {
    aiActionStop();
    fixWait.stop();
    fixSetBusy(false);
  }
});

$("btn-fix-rollback").addEventListener("click", async () => {
  if (!lastFix) return;
  if (!await confirmModal({
    title: "确认回滚？",
    message: "回滚本次修复？将把备份的文件内容恢复到写回前状态。",
    danger: true,
    confirmText: "确认回滚",
  })) return;
  $("btn-fix-rollback").disabled = true;
  $("fix-errors-msg").textContent = "";
  try {
    const data = await apiPost("/api/fix-errors/rollback", lastFix);
    $("fix-errors-msg").classList.add("ok");
    $("fix-errors-msg").textContent = "已回滚 " + data.restored.length + " 个文件："
      + data.restored.join("、");
    $("btn-fix-rollback").classList.add("hidden");
    $("fix-status").textContent = "已回滚（文件内容已恢复，可重新编译验证）";
    lastFix = null;
  } catch (e) {
    $("fix-errors-msg").classList.remove("ok");
    $("fix-errors-msg").textContent = e.message;
  } finally { $("btn-fix-rollback").disabled = false; }
});


// ---- 本簇导出面（host / generate-core 顶部 import 活绑定调用点） ----
// 说明（工单 16 记录）：host 实际使用 renderToolchainStatus / setToolchains /
// updateFixCenterAvailability（启动区与 setSettingsDeps 回调用）；generate-core
// 导入 startFixCenter / compileBanner / toolchains（工单 15 的 setGenerateCoreDeps
// 接缝已由静态 import 取代）。runCompileOnce / runFixOnce / fixRounds /
// continueFixCenter / FIX_MAX_ROUNDS / fixLoop 经检查表导出为模块 API
//（fixLoop.resume 结构钉在 tests/test_generate_check_contract.py；FIX_MAX_ROUNDS
// 与 fixLoop 自工单 code-ide-ai/05 起 re-export 自 fix-center-core.js）。
export { startFixCenter, continueFixCenter, runCompileOnce, runFixOnce, fixRounds,
  renderToolchainStatus, updateFixCenterAvailability, fixRenderResults,
  toolchains, setToolchains, compileBanner };
