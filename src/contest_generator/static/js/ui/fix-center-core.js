// ui/fix-center-core.js — 修复循环核心状态机（工单 code-ide-ai/05）
//
// 生成页第 10 步修复中心（原 generate-fix.js）的流程状态机抽共享：**无 DOM**——
// 持有流程状态（running/round/batch/resume/lastFixDone）+ SSE/端点调用 + 轮次
// 逻辑（≤FIX_MAX_ROUNDS 轮 / 0-applied 停滞检测 / 轮上限续跑态），渲染经
// 事件回调广播；generate-fix.js（生成页壳层）绑回调保持第 10 步行为零变化，
// IDE 修复面板（工单 06）绑同回调双出口。写盘守卫 / 平台工具链校验仍在壳层
// （issue 05 决策：核心只管流程）。单实例：fixLoop.running 防重入沿用。
// 双面板同时打开 → 同回调广播各自渲染（状态天然一致）。
//
// 回调集（全部可选，缺省 noop；壳层逐项绑 DOM）：
// - onState(text)            状态行（fix-status）
// - onError(text)            错误行（fix-errors-msg；error 事件 / catch 兜底）
// - onRound(text)            轮次条（fix-center-round）
// - onApply(item)            apply_result 条目 {file,line,status,reason}
// - onLog(text)              编译输出写入（fix-center-log + 分组显隐）
// - onBanner(kind,text)      编译横幅四态（running/success/fail/notool）
// - onList(parsed,fixes,round)  最终错误列表重建（fixRenderResults）
// - onTelemetry(data)        llm_telemetry 载荷
// - onDone(done)             done 载荷（null = 新一轮清场时已由 onReset 处理）
// - onReset()                新生命周期清场（结果/日志/回滚钮/继续钮/telemetry）
// - onBusy(busy)             忙态（按钮禁用/ spinner）
// - onResume(resume|null)    轮上限续跑态（壳层按此显隐「继续修复」）
// - onCompiled(done,outputDir)  每次编译 done（跨簇副作用如 recent 上报）
// 相对路径 import（区别于 ui 簇常规 /js/ 绝对路径）：本模块为 node 可测纯
// 流程模块（tests/js/fix-center-core.test.mjs 直接 import），相对路径在浏览器
// 与 node 两种解析器下一致（/js/ui/ → ../fx/ = /js/fx/）；fx 内部同先例。
import { parseSSE } from "../fx/llm.js";
import { parseHttpError } from "../fx/errors.js";
import { compileSummaryText, fmtSeconds } from "../fx/generate.js";
import { isSyscfgConflict } from "../fx/code-compile.js";

export const FIX_MAX_ROUNDS = 3;

// 配置级冲突（工单 02，mspm0 / SysConfig 真机形态）：编译失败原因是工程外设
// 配置冲突（引脚被两个模块同时占用），没有源码可改——不进 AI 修复轮（域层
// 也短路不喂 LLM，前端这里提前收口：省一次请求 + 状态行给准话），直接列出
// 冲突清单 + 指路。条目判据单源 = fx/code-compile.js isSyscfgConflict（与后端
// fix_errors.SYSCFG_CONFLICT_KIND 逐字一致，缺省缺 kind = 源码级）。
// 文案与后端 fix_errors.SYSCFG_CONFLICT_NOTICE 刻意同文（跨语言对偶，同
// TRUNCATION_NOTICE 先例：前端不逐字 import 后端常量），尾句是本界面专属引导。
export function syscfgConflictStateText(conflicts) {
  return "SysConfig 资源冲突：本次编译的失败原因是工程外设配置冲突（引脚被两个"
    + "模块同时占用），不是源码写错——属于配置级问题，没有源码可改，因此不进行"
    + "AI 修复。请按上方冲突清单处理：改引脚绑定（模块实例卡里换脚 / 自动分配），"
    + "或去掉冲突模块中的一个，然后重新「一键编译修复」。";
}

// ---- 流程状态（live 对象——壳层 re-export / check_contract 读 .resume 结构；
// 只经本模块 mutate）----
export const fixLoop = { running: false, round: 0, batch: 1, resume: null };
let lastFixDone = null;   // 最近一次 fix-errors done 载荷（批内回喂；上一批末轮载荷由 resume 携带）

export function isFixRunning() { return fixLoop.running; }
export function fixLoopSnapshot() {
  return {
    running: fixLoop.running, round: fixLoop.round, batch: fixLoop.batch,
    resume: fixLoop.resume ? { ...fixLoop.resume } : null,
  };
}

// input 形状（壳层组装）：{outputDir, platform, problemText, mainC, slugs,
// callbacks}；callbacks 见头部注释。emitAll 对缺失键安全跳过（无 noop 填充
// ——回调组可只订阅关心的事件）。

// ---- 订阅制广播（工单 code-ide-ai/06）：事件发往全部订阅回调组（Set 去重
// 同一对象）。双面板（生成页修复中心 / IDE 修复面板）各自 subscribe 长驻组 →
// 单实例循环的状态天然广播到两处 DOM（spec 二期「双面板同时打开时状态同
// 步」）；触发方 input.callbacks 由 subscribeTrigger 临时订阅（**原始对象**
// ——若与长驻组同一对象则 Set 天然去重只收一次——Standards 评审整改 H1：
// 原 withCbs 包装新对象使「长驻 + 触发方」两个引用并存导致事件双发，
// fixRowHTML 重复追加 + LLM 用量重复计数）。单个监听器异常不阻断其他订阅。 ----
const fixSubs = new Set();
export function subscribeFixCenter(cb) {
  fixSubs.add(cb);
  return () => fixSubs.delete(cb);   // 退订（长驻面板忽略返回值；测试隔离用）
}
function emitAll(name, ...args) {
  for (const cb of fixSubs) {
    const f = cb && cb[name];
    if (typeof f === "function") {
      try { f(...args); } catch (e) { /* 监听器异常不阻断其他订阅 */ }
    }
  }
}
/** 触发方临时订阅：原始 callbacks 对象进 fixSubs（已是成员则不加——同对象
 * 去重防双发）；返回退订函数（仅本次新增时才真删——不误删长驻组）。 */
function subscribeTrigger(input) {
  const cb = input && input.callbacks;
  if (!cb || typeof cb !== "object") return () => {};
  let added = false;
  if (!fixSubs.has(cb)) { fixSubs.add(cb); added = true; }
  return () => { if (added) fixSubs.delete(cb); };
}

// ---------------------------------------------------------------------------
// 单次编译（SSE /api/compile）→ done 载荷；error 终态 / 断线 → throw（中文文案）。
// 横幅（running/终态）经 onBanner——文案与 fx/generate.compileSummaryText 单源。
// ---------------------------------------------------------------------------
async function runCompileOnce(input) {
  let finished = false;
  let done = null;
  let errorMsg = null;
  let resp;
  const runningText = () => "编译中…"
    + (fixLoop.round > 0 ? "（第 " + fixLoop.round + "/" + FIX_MAX_ROUNDS + " 轮）" : "");
  emitAll("onBanner", "running", runningText());
  try {
    resp = await fetch("/api/compile", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ platform: input.platform, output_dir: input.outputDir }),
    });
  } catch (e) { emitAll("onBanner", "fail", "编译未能启动：" + e.message); throw new Error(e.message); }
  if (!resp.body) { emitAll("onBanner", "fail", "服务响应无流"); throw new Error("服务响应无流"); }
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    const msg = parseHttpError(resp.status, err).text;
    emitAll("onBanner", "fail", "编译失败：" + msg);
    throw new Error(msg);
  }
  await parseSSE(resp, (type, raw) => {
    let data = {};
    try { data = JSON.parse(raw || "null") || {}; } catch { data = {}; }
    if (type === "compile_start") {
      emitAll("onBanner", "running", runningText());
    } else if (type === "done") { done = data; finished = true; }
    else if (type === "error") { errorMsg = data.message || "编译失败"; finished = true; }
  });
  if (errorMsg) { emitAll("onBanner", "fail", "编译失败：" + errorMsg); throw new Error(errorMsg); }
  if (!done) throw new Error(finished ? "编译未返回结果" : "连接中断：本次编译未完成，可安全重试");
  const text = compileSummaryText(done);   // 文案单源（compileSummaryText，与 IDE 编译横幅同源）
  emitAll("onBanner", done.timed_out ? "fail" : done.passed ? "success" : "fail", text);
  emitAll("onCompiled", done, input.outputDir);
  return done;
}

// ---------------------------------------------------------------------------
// SSE 事件 → 状态 + 回调（fix-errors 事件词表：parse_done/fix_start/
// apply_result/llm_telemetry/done/error）。核心只记回喂态 lastFixDone；
// done 的备份信息（backup_id）经 onDone 交壳层（回滚按钮态）。
// ---------------------------------------------------------------------------
function fixHandleEvent(type, raw, outputDir) {
  let data = {};
  try { data = JSON.parse(raw || "null") || {}; } catch { data = {}; }
  if (type === "parse_done") {
    const degraded = !data.file_count;
    // 配置级冲突（工单 02）：域层对纯冲突短路不调 LLM——本阶段就报冲突 + 指路，
    // 不显示「AI 修复中」（否则是先误导再改口）。判据单源 = parse_done.conflicts
    // 条目 kind（isSyscfgConflict）；并存源码错时既修源码错也需要用户改配置，
    // 两条信息都给。
    const conflicts = (data.conflicts || []).filter(isSyscfgConflict);
    if (conflicts.length) {
      emitAll("onState", syscfgConflictStateText(conflicts));
      return;
    }
    emitAll("onState", "已解析 " + (data.error_count || 0) + " 条报错"
      + (degraded ? "，未定位到可读取的源码文件（降级模式，只按报错全文修复）"
        : "，定位 " + data.file_count + " 个文件") + "，AI 修复中…");
  } else if (type === "fix_start") {
    emitAll("onState", "AI 正在逐条修复（分钟级调用，请等待）…");
  } else if (type === "apply_result") {
    emitAll("onState", "");
    emitAll("onApply", {
      file: data.file, line: data.line, status: data.status, reason: data.reason,
    });
  } else if (type === "llm_telemetry") {
    emitAll("onTelemetry", data);
  } else if (type === "done") {
    lastFixDone = data;
    const fixes = data.fixes || [];
    const applied = fixes.filter((f) => f.status === "applied").length;
    const skipped = fixes.length - applied;
    emitAll("onState", "修复完成：应用 " + applied + " 处"
      + (skipped ? "，跳过 " + skipped + " 处" : "")
      + (data.backup_id ? "；已自动备份，可点「回滚本次修复」" : ""));
    emitAll("onDone", data, outputDir);
    // 列表重建（streaming 期逐条追加的行合并为最终状态）
    emitAll("onList", data.parsed || [], fixes, fixLoop.round);
  } else if (type === "error") {
    lastFixDone = null;
    emitAll("onState", "");
    emitAll("onError", data.message || "修复失败");
  }
}

// ---------------------------------------------------------------------------
// 单次修复（SSE /api/fix-errors）→ done 载荷；error / 断线 → throw。
// previousDone = 上一轮 done 载荷：fixes 回喂下一轮（previous_fixes）。
// ---------------------------------------------------------------------------
async function runFixOnce(input, errorText, previousDone) {
  let finished = false;
  let resp;
  try {
    resp = await fetch("/api/fix-errors", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        output_dir: input.outputDir,
        error_text: errorText,
        previous_fixes: previousDone && previousDone.fixes ? previousDone.fixes : undefined,
        problem_text: input.problemText,
        platform: input.platform || undefined,
        slugs: input.slugs,
        main_c: input.mainC,
      }),
    });
  } catch (e) { throw new Error(e.message); }
  if (!resp.body) throw new Error("服务响应无流");
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(parseHttpError(resp.status, err).text);
  }
  await parseSSE(resp, (type, raw) => {
    if (type === "done" || type === "error") finished = true;
    fixHandleEvent(type, raw, input.outputDir);
  });
  if (!finished) throw new Error("连接中断：本次修复未完成，可安全重试");
  if (!lastFixDone) throw new Error("修复失败（见上方提示）");
  return lastFixDone;
}

// ---------------------------------------------------------------------------
// 修复轮批：报错/告警 → 修复 → 重编译验证 ≤FIX_MAX_ROUNDS 轮（错误+告警共
// 池，停条件 = 0 错 0 警）；本轮 0 applied 即停（停滞检测——文件没变重编译
// 输出必同，不再白跑）；轮上限终态保存续跑态快照 + onResume 亮「继续修复」。
// ---------------------------------------------------------------------------
async function fixRounds(input, errorText, lastSummary, previousDone) {
  if (!input.outputDir) throw new Error("请先生成工程（或填写输出目录）");
  lastFixDone = previousDone;
  const batchPrefix = fixLoop.batch > 1 ? "继续批次 " : "";
  for (fixLoop.round = 1; fixLoop.round <= FIX_MAX_ROUNDS; fixLoop.round++) {
    const n = (lastSummary && Number.isFinite(lastSummary.errors)) ? lastSummary.errors : null;
    const w = (lastSummary && Number.isFinite(lastSummary.warnings)) ? lastSummary.warnings : null;
    const headLabel = (n === null || n > 0) ? "编译有错" : "编译有警";
    const headDetail = (n !== null && n > 0)
      ? (n + " 条 Error" + (w !== null && w > 0 ? " / " + w + " 条 Warning" : ""))
      : (w !== null && w > 0 ? w + " 条 Warning" : (headLabel === "编译有错" ? "多条报错" : "多条警告"));
    emitAll("onRound", batchPrefix + "第 " + fixLoop.round + "/" + FIX_MAX_ROUNDS
      + " 轮：" + headLabel + "（" + headDetail + "）→ AI 修复…");
    const done = await runFixOnce(input, errorText, lastFixDone);
    const applied = (done.fixes || []).filter((f) => f.status === "applied").length;
    if (applied === 0) {
      emitAll("onRound", batchPrefix + "第 " + fixLoop.round + "/" + FIX_MAX_ROUNDS
        + " 轮：未应用任何修复，停止循环");
      const rest = (lastSummary && lastSummary.errors === 0 && lastSummary.warnings > 0)
        ? "（剩余 " + lastSummary.warnings + " 条 Warning 见上方编译输出）" : "";
      emitAll("onState", "本轮未应用任何修复（全部 skipped / 无修复建议），停止循环"
        + rest + "——可贴文本手动修复或改工程后重试");
      return;
    }
    emitAll("onRound", batchPrefix + "第 " + fixLoop.round + "/" + FIX_MAX_ROUNDS
      + " 轮：重编译验证中…");
    const compile = await runCompileOnce(input);
    emitAll("onLog", compile.error_text);
    lastSummary = compile.summary || null;
    emitAll("onRound", batchPrefix + "第 " + fixLoop.round + "/" + FIX_MAX_ROUNDS
      + " 轮 · 耗时 " + fmtSeconds(compile.duration) + "s");
    if (compile.timed_out) {
      emitAll("onState", "第 " + fixLoop.round + " 轮重编译超时，已停止循环——"
        + "可修改工程后点「一键编译修复」重新来过");
      return;
    }
    if (compile.passed) {
      if (((compile.summary || {}).warnings || 0) === 0) {
        emitAll("onState", "第 " + fixLoop.round + " 轮重编译通过 ✅ 0 错 0 警");
        return;
      }
      // 仍有警 → 下一轮继续告警轮（停条件 = 0 错 0 警）
    }
    errorText = compile.error_text;
  }
  // 第 3 轮后仍错 / 仍有警：如实报告剩余清单；轮上限终态保存续跑态并亮「继续修复」
  const n = (lastSummary && Number.isFinite(lastSummary.errors)) ? lastSummary.errors : null;
  const w = (lastSummary && Number.isFinite(lastSummary.warnings)) ? lastSummary.warnings : null;
  const restParts = [];
  if (n === null || n > 0) restParts.push(n !== null ? n + " 条 Error" : "多条报错");
  if (w !== null && w > 0) restParts.push(w + " 条 Warning");
  fixLoop.resume = { errorText, lastSummary, lastFixDone };
  emitAll("onResume", fixLoop.resume);
  emitAll("onState", "已达 " + FIX_MAX_ROUNDS + " 轮上限，剩余 "
    + (restParts.join(" / ") || "问题") + " 见上方编译输出——可点「继续修复」再来 "
    + FIX_MAX_ROUNDS + " 轮（保留回喂上下文），或贴文本修复，或改工程后重试");
}

// ---------------------------------------------------------------------------
// 主入口（核心部分）：初始全量编译 → 有错/有警进一轮批（≤3 轮）。
// 校验（输出目录/平台/工具链）与写盘守卫在壳层（本模块不碰）。onReset 前
// 置 running（单实例防重入——壳层二次触发直接忽略）。
// ---------------------------------------------------------------------------
export async function startFixCenterCore(input) {
  if (fixLoop.running) return;   // 单实例：循环中忽略重复触发
  const unsub = subscribeTrigger(input);   // 触发方原始对象临时订阅（与长驻同对象 → Set 去重）
  fixLoop.running = true;
  fixLoop.round = 0;
  fixLoop.batch = 1;
  fixLoop.resume = null;
  lastFixDone = null;
  emitAll("onReset");
  emitAll("onBusy", true);
  emitAll("onState", "自动编译中…");
  try {
    const initial = await runCompileOnce(input);
    emitAll("onLog", initial.error_text);
    if (initial.timed_out) {
      emitAll("onState", "编译超时（工具链 180s 未返回），已停止循环——"
        + "可在设置页检查工具链路径后重试");
      return;
    }
    if (initial.passed) {
      const iw = (initial.summary && initial.summary.warnings) || 0;
      if (iw === 0) {
        emitAll("onState", "编译通过 ✅ 0 错 0 警");
        return;
      }
      // 0 错 N 警 → 进告警轮（验收标准 = 0 错 0 警）
    }
    emitAll("onList", initial.parsed_errors || [], [], 0);
    // 配置级冲突（工单 02）：没有源码可改 → 不进修复轮（不白烧一轮 LLM），
    // 冲突行已在错误列表里，状态行给准话 + 指路即收工（判据 = 条目 kind，
    // 单源 fx/code-compile.js isSyscfgConflict）
    const conflicts = (initial.parsed_errors || []).filter(isSyscfgConflict);
    if (conflicts.length) {
      emitAll("onState", syscfgConflictStateText(conflicts));
      return;
    }
    await fixRounds(input, initial.error_text, initial.summary || null, null);
  } catch (e) {
    emitAll("onState", "");
    emitAll("onError", e.message);
  } finally {
    emitAll("onBusy", false);
    fixLoop.running = false;
    fixLoop.round = 0;
    unsub();
  }
}

// 「继续修复」：从轮上限终态保存的续跑态再来一批 ≤3 轮——不重跑初始编译，
// previous_fixes 回喂上下文不丢。守卫在壳层。
export async function continueFixCenterCore(input) {
  if (fixLoop.running) return;   // 批内防重复触发
  const resume = fixLoop.resume;
  if (!resume) return;           // 无续跑态（非轮上限终态）不动作
  const unsub = subscribeTrigger(input);
  fixLoop.resume = null;
  fixLoop.batch += 1;            // 批次号 +1：轮次条标注「继续批次 第 N/3 轮」
  fixLoop.running = true;
  emitAll("onBusy", true);
  emitAll("onState", "");
  try {
    await fixRounds(input, resume.errorText, resume.lastSummary, resume.lastFixDone);
  } catch (e) {
    emitAll("onState", "");
    emitAll("onError", e.message);
  } finally {
    emitAll("onBusy", false);
    fixLoop.running = false;
    fixLoop.round = 0;
    unsub();
  }
}

/** 单次修复（手动贴文本模式）：新生命周期一条 fix-errors 流（无回喂）。
 * 清场/按钮态由壳层处理（核心只跑流）；done 载荷经 lastFixDone 返回。
 * 手动模式是独立生命周期：清续跑态（原壳层 btn-fix-errors 语义——fixLoop.
 * resume/batch/lastFixDone 复位，继续按钮消费的快照随之失效）。
 * **单实例**（Standards 评审整改）：手动模式也置 running——手动修复与自动
 * 循环都写工程文件，并发会互相清空共享态（原 generate-fix.js 基线可并发，
 * 抽取后暴露为共享态风险）；运行中再触发 → 抛错交壳层显示。 */
export async function runFixOnceCore(input, errorText) {
  const unsub = subscribeTrigger(input);
  if (fixLoop.running) throw new Error("修复循环进行中，请等待完成后再试");
  fixLoop.resume = null;
  fixLoop.batch = 1;
  lastFixDone = null;
  fixLoop.running = true;
  try {
    return await runFixOnce(input, errorText, undefined);
  } finally {
    fixLoop.running = false;
    fixLoop.round = 0;
    unsub();
  }
}

/** 单次编译（导出面）：供壳层/外部按需跑一遍编译（输入 outputDir 由 input
 * 携带）；banner 经回调。 */
export async function runCompileOnceCore(input) {
  const unsub = subscribeTrigger(input);
  try {
    return await runCompileOnce(input);
  } finally {
    unsub();
  }
}

/** 修复轮批（导出面）：批入口（「继续修复」前批次由 continueFixCenterCore
 * 调度；本导出供壳层/外部直跑一批）。 */
export async function fixRoundsCore(input, errorText, lastSummary, previousDone) {
  const unsub = subscribeTrigger(input);
  try {
    return await fixRounds(input, errorText, lastSummary, previousDone);
  } finally {
    unsub();
  }
}
