// ui/generate-fix.js — 生成页 · 编译修复中心（工单 autocompile-loop/01 等
// 全家桶：单次编译 / 修复循环 ≤3 轮 / 批继续 / 横幅四态 / 结果表 / telemetry /
// 就绪度）DOM 胶水（阶段 2 工单 16，源自 index.html 生成页：10. 修复中心节）。
//
// 簇体全量迁入：FIX_MAX_ROUNDS / toolchains（主写簇：export let + setToolchains
// setter——host init 与设置页重算经 setter 写，其余读方 import）/ fixLoop /
// lastFix* / fixSourceCache + compileBanner / renderCompileBanner / fmtSeconds
//（纯函数→已迁 fx/generate.js，本模块 import）/ fixKeyOf / fixKeyBasename /
// fixToggleSource / fixRenderResults /
// fixSetBusy / fixCenterBusy / renderToolchainStatus / renderFixLLMTelemetry /
// clearFixLLMTelemetry / updateFixCenterAvailability / fixHandleEvent /
// runCompileOnce / runFixOnce / fixRounds / startFixCenter / continueFixCenter +
// 顶层监听器（btn-fix-center / btn-fix-continue / btn-fix-errors /
// btn-fix-rollback + continue 文案——import 时绑定：module 脚本延迟执行，DOM 已就绪）。
// 纯件在 fx/*.js（generate / llm / code）；状态读 A 簇（generate-recommend）
// chosenPlatform / selectedSlugs（活绑定只读——本簇是 toolchains 主写簇）。
// 跨簇：recordLLMUsage（usage）/ reportRecentStatus（recent）/ markStepDone
//（step-state）。A 簇对本簇的服务调用（updateFixCenterAvailability）仍经
// host 启动区注册的 setClusterDeps 闭包（与工单 13 pins 同构——A 不 import
// 本簇，避免 ui→ui 环；本簇单向 import A）。
import { $, apiPost, toast } from "/js/app.js";
import { confirmModal } from "/js/ui/confirm.js";
import { fmtSeconds } from "/js/fx/generate.js";
import { parseSSE, formatLLMTelemetry } from "/js/fx/llm.js";
import { isMainCPath, maincJumpToLine } from "/js/fx/code.js";
import { chosenPlatform, selectedSlugs } from "/js/ui/generate-recommend.js";
import { reportRecentStatus } from "/js/ui/recent.js";
import { recordLLMUsage } from "/js/ui/usage.js";
import { markStepDone } from "/js/ui/step-state.js";
import { aiActionStart, aiActionStop } from "/js/ui/ai-banner.js";  // 全局「AI 行动中」横幅（工单 ai-action-banner/02）

// ---------------------------------------------------------------------------
// 生成页：10. 修复中心（工单 autocompile-loop/01）——生成 → 自动编译 →
// 自动采集报错 → 喂 fix-errors 管线修复 → 重编译验证，循环 ≤3 轮；无工具链
// 回退贴文本模式（工单 compile-error-fix/01 既有路径保留）。事件词表镜像
// events.py：compile_start / parse_done / fix_start / apply_result / done /
// error（retry 是蒸馏层事件，修复流不发；实现发事件时再加回）。循环状态机
// 在前端（服务端只做单次编译），轮次可见"第 N/3 轮"。
// ---------------------------------------------------------------------------
const FIX_MAX_ROUNDS = 3;
let lastFix = null;          // {output_dir, backup_id}：回滚按钮的入口（done 终态后置位）
let lastFixDone = null;      // 最近一次 fix-errors 的 done 载荷（循环判"有无应用"）
let toolchains = { stm32: false, mspm0: false };  // /api/state 装载：平台 → 工具链可用
function setToolchains(v) { toolchains = v; }  // 写入经 setter（host init / 设置页工具链重算）
let fixLoop = { running: false, round: 0, batch: 1, resume: null };
// 循环状态机：单实例（防双击并发）；batch = 批次号（「继续修复」+1，轮次条标
// 注「继续批次」）；resume = 轮上限终态保存的续跑态快照 {errorText, lastSummary,
// lastFixDone}（工单 fix-loop-continue/01：「继续修复」消费它，不重跑编译、回喂不丢）
let fixSourceCache = {};                          // 源码行缓存（key = 归一化 path:line；列表重建时清空）

/** 编译结果横幅四态（工单 compile-experience-ui/01）：running/success/fail/notool。 */
function compileBanner(kind, text) {
  const b = $("compile-banner");
  b.className = kind;   // 重置状态类（同时移除初始 hidden）
  b.textContent = text;
  if (kind === "success") { markStepDone(10); toast("ok", "编译通过"); }  // 修复中心闭环
}

function renderCompileBanner(done) {   // compile done 载荷 → 横幅终态文案
  const dur = fmtSeconds(done.duration);
  const sum = done.summary || { errors: 0, warnings: 0 };
  if (done.timed_out) {
    compileBanner("fail", "编译超时（工具链 180s 未返回）");
  } else if (done.passed) {
    compileBanner("success", "编译成功 · " + (sum.errors || 0) + " Error "
      + (sum.warnings || 0) + " Warning · 耗时 " + dur + "s");
  } else {
    compileBanner("fail", "编译失败 · " + (sum.errors || 0) + " 个错误 · 耗时 " + dur + "s");
  }
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
 * 无法匹配 parsed 的 fixes 单独列出。列表重建时清空源码行缓存（新一轮取修复后内容）。 */
function fixRenderResults(parsed, fixes, round) {
  parsed = parsed || [];
  fixes = fixes || [];
  fixSourceCache = {};
  const list = $("fix-results");
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
    row.addEventListener("click", () => fixToggleSource(row));
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

// 已迁至 static/js/fx/llm.js（工单 09）：formatLLMTelemetry。

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
  $("btn-fix-center").disabled = !ok || fixLoop.running;
  $("btn-fix-center").title = !chosenPlatform ? "请先选择目标平台"
    : ok ? "" : "未检测到该平台工具链（可在设置页配置路径），请用贴文本模式";
}

function fixHandleEvent(type, raw, outputDir) {
  let data = {};
  try { data = JSON.parse(raw || "null") || {}; } catch { data = {}; }
  if (type === "parse_done") {
    const degraded = !data.file_count;
    $("fix-status").textContent = "已解析 " + (data.error_count || 0) + " 条报错"
      + (degraded ? "，未定位到可读取的源码文件（降级模式，只按报错全文修复）"
          : "，定位 " + data.file_count + " 个文件") + "，AI 修复中…";
  } else if (type === "fix_start") {
    $("fix-status").textContent = "AI 正在逐条修复（分钟级调用，请等待）…";
  } else if (type === "apply_result") {
    $("fix-status").textContent = "";
    const applied = data.status === "applied";
    const row = document.createElement("div");
    row.className = "fix-row";
    const tag = document.createElement("span");
    tag.className = "fix-tag " + (applied ? "fixed" : "skipped");
    tag.textContent = applied ? "已修复" : "跳过";
    const file = document.createElement("span");
    file.className = "fix-file";
    file.textContent = (data.file || "?") + (data.line ? ":" + data.line : "");
    const msg = document.createElement("span");
    msg.className = "fix-msg";
    msg.textContent = data.reason || "";
    row.appendChild(tag); row.appendChild(file); row.appendChild(msg);
    row._source = { path: data.file, line: data.line };
    row.addEventListener("click", () => fixToggleSource(row));
    $("fix-results").appendChild(row);
  } else if (type === "llm_telemetry") {
    renderFixLLMTelemetry(data);
    recordLLMUsage(data);
  } else if (type === "done") {
    lastFixDone = data;
    const fixes = data.fixes || [];
    const applied = fixes.filter((f) => f.status === "applied").length;
    const skipped = fixes.length - applied;
    lastFix = data.backup_id ? { output_dir: outputDir, backup_id: data.backup_id } : null;
    $("fix-status").textContent = "修复完成：应用 " + applied + " 处"
      + (skipped ? "，跳过 " + skipped + " 处" : "")
      + (lastFix ? "；已自动备份，可点「回滚本次修复」" : "");
    $("btn-fix-rollback").classList.toggle("hidden", !lastFix);
    // 展示层（工单 compile-experience-ui/01）：按 parsed + fixes 重建可点击列表
    // （streaming 期间逐条追加的行在此合并为最终状态）
    fixRenderResults(data.parsed || [], fixes, fixLoop.round);
  } else if (type === "error") {
    lastFixDone = null;
    $("fix-status").textContent = "";
    $("fix-errors-msg").textContent = data.message || "修复失败";
  }
}

/** 单次编译（SSE /api/compile）→ done 载荷；error 终态 / 断线 → throw（中文文案）。
 * 展示层（工单 compile-experience-ui/01）：起流前横幅「编译中（第 N/3 轮）」，
 * done / error 后横幅终态（成功 / 失败 / 超时）——只更新展示，不改循环控制流。 */
async function runCompileOnce(outputDir) {
  let finished = false;
  let done = null;
  let errorMsg = null;
  let resp;
  compileBanner("running", "编译中…"
    + (fixLoop.round > 0 ? "（第 " + fixLoop.round + "/" + FIX_MAX_ROUNDS + " 轮）" : ""));
  try {
    resp = await fetch("/api/compile", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ platform: chosenPlatform, output_dir: outputDir }),
    });
  } catch (e) { compileBanner("fail", "编译未能启动：" + e.message); throw new Error(e.message); }
  if (!resp.body) { compileBanner("fail", "服务响应无流"); throw new Error("服务响应无流"); }
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    const msg = err.detail || ("请求失败（HTTP " + resp.status + "）");
    compileBanner("fail", "编译失败：" + msg);
    throw new Error(msg);
  }
  await parseSSE(resp, (type, raw) => {
    let data = {};
    try { data = JSON.parse(raw || "null") || {}; } catch { data = {}; }
    if (type === "compile_start") {   // 事件有人消费（词表真实化）：文案与 fetch 前写死的一致
      compileBanner("running", "编译中…"
        + (fixLoop.round > 0 ? "（第 " + fixLoop.round + "/" + FIX_MAX_ROUNDS + " 轮）" : ""));
    } else if (type === "done") { done = data; finished = true; }
    else if (type === "error") { errorMsg = data.message || "编译失败"; finished = true; }
  });
  if (errorMsg) { compileBanner("fail", "编译失败：" + errorMsg); throw new Error(errorMsg); }
  if (!done) throw new Error(finished ? "编译未返回结果" : "连接中断：本次编译未完成，可安全重试");
  renderCompileBanner(done);
  reportRecentStatus(outputDir, done);  // 编译结果上报最近生成列表（工单 recent-jobs/01）
  return done;
}

/** 单次修复（SSE /api/fix-errors，复用既有管线）→ done 载荷；error / 断线 → throw。
 * previousDone = 上一轮 done 载荷：其 fixes 数组作为 previous_fixes 回喂下一轮
 * （工单 fix-loop-progress/01）；贴文本模式不传（undefined → 请求体不带该字段）。 */
async function runFixOnce(errorText, outputDir, previousDone) {
  let finished = false;
  let resp;
  try {
    resp = await fetch("/api/fix-errors", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        output_dir: outputDir,
        error_text: errorText,
        previous_fixes: previousDone && previousDone.fixes ? previousDone.fixes : undefined,
        problem_text: $("problem").value.trim(),
        platform: chosenPlatform || undefined,
        slugs: selectedSlugs,
        main_c: $("main-c").value.trim(),
      }),
    });
  } catch (e) { throw new Error(e.message); }
  if (!resp.body) throw new Error("服务响应无流");
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.detail || ("请求失败（HTTP " + resp.status + "）"));
  }
  await parseSSE(resp, (type, raw) => {
    if (type === "done" || type === "error") finished = true;
    fixHandleEvent(type, raw, outputDir);
  });
  if (!finished) throw new Error("连接中断：本次修复未完成，可安全重试");
  if (!lastFixDone) throw new Error("修复失败（见上方提示）");
  return lastFixDone;
}

/** 修复轮批（工单 fix-loop-continue/01 拆分复用）：报错 / 告警 → 修复 →
 * 重编译验证 ≤FIX_MAX_ROUNDS 轮。previousDone = 批首轮回喂的上一批 done
 * 载荷——「一键编译修复」= null（新生命周期）；「继续修复」= 上一批末轮载荷
 * （回喂上下文不丢）。批内后续轮由 fixHandleEvent 更新模块级 lastFixDone 回喂。
 * 轮上限终态保存续跑态快照并亮「继续修复」按钮。 */
async function fixRounds(errorText, lastSummary, previousDone) {
  const outputDir = $("res-dir").textContent.trim() || $("output-dir").value.trim();
  if (!outputDir) throw new Error("请先生成工程（或填写输出目录）");
  lastFixDone = previousDone;
  const batchPrefix = fixLoop.batch > 1 ? "继续批次 " : "";
  // 报错 / 告警 → 修复 → 重编译验证，≤3 轮（错误+告警共池，停条件 = 0 错
  // 0 警，工单 fix-loop-warnings/01）；本轮 0 applied 即停（停滞检测，工单
  // fix-loop-progress/01 决策 1——文件没变，重编译输出必与上轮相同，不再白跑）；
  // 第 3 轮后如实报告剩余错误/警告（不无限循环）
  // 轮次文案错误/警告数：判读单源 summary（工单 compile-verdict-align/01，
  // 删 fixErrorCount 正则——fix_errors.py 明令禁止调用方另写正则）；lastSummary
  // 与 errorText 同步更新，批首即上一批末轮的 summary
  for (fixLoop.round = 1; fixLoop.round <= FIX_MAX_ROUNDS; fixLoop.round++) {
    const n = (lastSummary && Number.isFinite(lastSummary.errors)) ? lastSummary.errors : null;
    const w = (lastSummary && Number.isFinite(lastSummary.warnings)) ? lastSummary.warnings : null;
    const headLabel = (n === null || n > 0) ? "编译有错" : "编译有警";
    const headDetail = (n !== null && n > 0)
      ? (n + " 条 Error" + (w !== null && w > 0 ? " / " + w + " 条 Warning" : ""))
      : (w !== null && w > 0 ? w + " 条 Warning" : (headLabel === "编译有错" ? "多条报错" : "多条警告"));
    $("fix-center-round").textContent = batchPrefix + "第 " + fixLoop.round + "/" + FIX_MAX_ROUNDS
      + " 轮：" + headLabel + "（" + headDetail + "）→ AI 修复…";
    const done = await runFixOnce(errorText, outputDir, lastFixDone);   // 上轮载荷回喂（决策 2）
    const applied = (done.fixes || []).filter((f) => f.status === "applied").length;
    if (applied === 0) {   // 空修复 / 全 skipped / 降级无上下文：立即停，文案写具体
      $("fix-center-round").textContent = batchPrefix + "第 " + fixLoop.round + "/" + FIX_MAX_ROUNDS
        + " 轮：未应用任何修复，停止循环";
      // 告警轮无建议：文案带剩余警数（工单 fix-loop-warnings/01，0-applied
      // 即停对告警轮同样生效——不再空转 3 轮）
      const rest = (lastSummary && lastSummary.errors === 0 && lastSummary.warnings > 0)
        ? "（剩余 " + lastSummary.warnings + " 条 Warning 见上方编译输出）" : "";
      $("fix-status").textContent = "本轮未应用任何修复（全部 skipped / 无修复建议），停止循环"
        + rest + "——可贴文本手动修复或改工程后重试";
      return;
    }
    $("fix-center-round").textContent = batchPrefix + "第 " + fixLoop.round + "/" + FIX_MAX_ROUNDS
      + " 轮：重编译验证中…";
    const compile = await runCompileOnce(outputDir);
    $("fix-center-log").value = compile.error_text || "";
    lastSummary = compile.summary || null;
    // 轮次条追加耗时（展示层工单 compile-experience-ui/01；compile 必有 duration）
    $("fix-center-round").textContent = batchPrefix + "第 " + fixLoop.round + "/" + FIX_MAX_ROUNDS
      + " 轮 · 耗时 " + fmtSeconds(compile.duration) + "s";
    if (compile.timed_out) {
      $("fix-status").textContent = "第 " + fixLoop.round + " 轮重编译超时，已停止循环——"
        + "可修改工程后点「一键编译修复」重新来过";
      return;
    }
    if (compile.passed) {
      if (((compile.summary || {}).warnings || 0) === 0) {
        $("fix-status").textContent = "第 " + fixLoop.round + " 轮重编译通过 ✅ 0 错 0 警";
        return;
      }
      // 仍有警 → 下一轮继续告警轮（工单 fix-loop-warnings/01：停条件 =
      // 0 错 0 警，仅 passed 即停的旧形态已废）
    }
    errorText = compile.error_text;   // 仍错或有警 → 下一轮喂最新编译输出
  }
  // 第 3 轮后仍错 / 仍有警：如实报告剩余清单（决策记录 2 + 工单
  // fix-loop-warnings/01）；轮上限终态保存续跑态并亮「继续修复」（工单
  // fix-loop-continue/01——按钮消费快照，不重跑初始编译、回喂不丢）
  const n = (lastSummary && Number.isFinite(lastSummary.errors)) ? lastSummary.errors : null;
  const w = (lastSummary && Number.isFinite(lastSummary.warnings)) ? lastSummary.warnings : null;
  const restParts = [];
  if (n === null || n > 0) restParts.push(n !== null ? n + " 条 Error" : "多条报错");
  if (w !== null && w > 0) restParts.push(w + " 条 Warning");
  fixLoop.resume = { errorText, lastSummary, lastFixDone };
  $("btn-fix-continue").classList.remove("hidden");
  $("fix-status").textContent = "已达 " + FIX_MAX_ROUNDS + " 轮上限，剩余 "
    + (restParts.join(" / ") || "问题") + " 见上方编译输出——可点「继续修复」再来 "
    + FIX_MAX_ROUNDS + " 轮（保留回喂上下文），或贴文本修复，或改工程后重试";
}

/** 修复中心主循环（决策记录 2/3）：编译 → 报错自动喂修复 → 重编译验证 ≤3 轮。 */
async function startFixCenter() {
  if (fixLoop.running) return;   // 单实例：循环中忽略重复触发
  const outputDir = $("res-dir").textContent.trim() || $("output-dir").value.trim();
  if (!outputDir) { $("fix-errors-msg").textContent = "请先生成工程（或填写输出目录）"; return; }
  if (!chosenPlatform) { $("fix-errors-msg").textContent = "请先选择目标平台"; return; }
  if (!(toolchains || {})[chosenPlatform]) {
    $("fix-errors-msg").textContent = "未检测到该平台工具链，已回退贴文本模式（见下方手动模式）";
    compileBanner("notool", "未检测到工具链，跳过自动编译（可在设置页填 uv4_path / gmake_path）");
    return;
  }
  fixLoop.running = true;
  fixLoop.round = 0;
  fixLoop.batch = 1;                 // 新生命周期：轮次条不带「继续批次」前缀
  fixLoop.resume = null;
  lastFix = null; lastFixDone = null;
  $("fix-errors-msg").textContent = "";
  $("fix-status").textContent = "";
  $("fix-results").innerHTML = "";
  $("fix-center-round").textContent = "";
  $("fix-center-log").value = "";
  clearFixLLMTelemetry();
  $("btn-fix-rollback").classList.add("hidden");
  $("btn-fix-continue").classList.add("hidden");   // 新循环开始即隐藏（工单 fix-loop-continue/01）
  fixCenterBusy(true);
  aiActionStart("编译修复");   // 全局「AI 行动中」横幅（工单 ai-action-banner/02）
  $("fix-status").textContent = "自动编译中…";
  try {
    // 第 0 步：首次全量编译（生成后自动触发 / 手动"一键编译修复"同一入口）
    const initial = await runCompileOnce(outputDir);
    $("fix-center-log").value = initial.error_text || "";
    if (initial.timed_out) {
      $("fix-status").textContent = "编译超时（工具链 180s 未返回），已停止循环——"
        + "可在设置页检查工具链路径后重试";
      return;
    }
    if (initial.passed) {
      const iw = (initial.summary && initial.summary.warnings) || 0;
      if (iw === 0) {
        $("fix-status").textContent = "编译通过 ✅ 0 错 0 警";
        return;
      }
      // 0 错 N 警 → 进告警轮（工单 fix-loop-warnings/01：不满足「0 错 0 警」
      // 验收标准，warning 行随完整编译输出回喂修复）
    }
    // 首编有错 / 有警 → 立即渲染结构化错误列表（全部「待修复」），修复轮
    // 结束后按 fixes 重渲染最终状态（展示层工单 compile-experience-ui/01）
    fixRenderResults(initial.parsed_errors || [], [], 0);
    // 一键编译修复 = 初始编译 + 一轮批（工单 fix-loop-continue/01：轮批拆出
    // 复用，「继续修复」直进 fixRounds 不重跑编译）
    await fixRounds(initial.error_text, initial.summary || null, null);
  } catch (e) {
    $("fix-status").textContent = "";
    $("fix-errors-msg").textContent = e.message;
  } finally {
    aiActionStop();
    fixLoop.running = false;
    fixLoop.round = 0;
    fixCenterBusy(false);
  }
}

/** 「继续修复」（工单 fix-loop-continue/01）：从轮上限终态保存的续跑态再来
 * 一批 ≤3 轮——不重跑初始编译，previous_fixes 回喂上下文不丢。 */
async function continueFixCenter() {
  if (fixLoop.running) return;   // 批内防重复触发
  const resume = fixLoop.resume;
  if (!resume) return;           // 无续跑态（非轮上限终态）不动作
  fixLoop.resume = null;
  fixLoop.batch += 1;            // 批次号 +1：轮次条标注「继续批次 第 N/3 轮」
  $("btn-fix-continue").classList.add("hidden");   // 进入新批即隐藏（终态时按结果重判）
  fixLoop.running = true;
  fixCenterBusy(true);
  aiActionStart("编译修复");   // 全局「AI 行动中」横幅（工单 ai-action-banner/02）
  $("fix-status").textContent = "";
  try {
    await fixRounds(resume.errorText, resume.lastSummary, resume.lastFixDone);
  } catch (e) {
    $("fix-status").textContent = "";
    $("fix-errors-msg").textContent = e.message;
  } finally {
    aiActionStop();
    fixLoop.running = false;
    fixLoop.round = 0;
    fixCenterBusy(false);
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
  lastFixDone = null;
  fixLoop.resume = null;             // 续跑态随之失效（工单 fix-loop-continue/01）
  fixLoop.batch = 1;
  $("btn-fix-rollback").classList.add("hidden");
  $("btn-fix-continue").classList.add("hidden");
  fixSetBusy(true);
  aiActionStart("AI 修复");   // 全局「AI 行动中」横幅（工单 ai-action-banner/02）
  $("fix-status").textContent = "解析报错中…";
  try {
    await runFixOnce(errorText, outputDir);
  } catch (e) {
    $("fix-errors-msg-manual").textContent = e.message;
  } finally {
    aiActionStop();
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
//（fixLoop.resume 结构钉在 tests/test_generate_check_contract.py）。
export { startFixCenter, continueFixCenter, runCompileOnce, runFixOnce, fixRounds,
  renderToolchainStatus, updateFixCenterAvailability, FIX_MAX_ROUNDS, fixLoop,
  toolchains, setToolchains, compileBanner };
