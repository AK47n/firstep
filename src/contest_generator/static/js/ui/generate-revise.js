// ui/generate-revise.js — 生成页 · 修订与深化阶段卡（工单 revise-deepen/05：
// 加载上下文 / 影响分析 / 确认修订 / 深化 + 编译验证 / 回滚，两段式 API）
// DOM 胶水（阶段 2 工单 17，源自 index.html 修订与深化节）。
//
// 簇体全量迁入：revise 状态对象 + 21 函数（reviseCurrentDir / reviseCountQa /
// renderReviseTelemetry / clearReviseTelemetry / reviseSetBusy / reviseResetAll /
// reviseLoad / reviseRenderContext / reviseRunSSE（独立 SSE 运行器——不共用
// progress.js 面板）/ reviseRenderDiff / reviseRenderAnalysis / reviseDiscard /
// reviseAnalyze / reviseApply / reviseRenderApplyDone / reviseDeepen /
// reviseRunDeepen / reviseRenderVerify / reviseRenderDeepenDiff /
// reviseDiffLineHtml / reviseRollback）+ 7 监听器（btn-revise-session /
// btn-revise-load-dir / revise-dir-input Enter / btn-revise-analyze /
// btn-revise-discard / btn-revise-apply / btn-revise-deepen /
// btn-revise-rollback / revise-problem-text input——import 时绑定：module 脚本
// 延迟执行，DOM 已就绪）。
// 纯件：reviseDiffLineHtml / reviseCountQa / reviseRenderDiff 均为纯计算，
// tests/js 无直测（工单 17 裁定：保持胶水随簇迁，如需直测后续单补——
// 到时按「纯函数迁 fx + fx-guard 登记」先例处理）。
// 依赖：app.js（$ / apiPost / toast）+ fx/core.js（esc）+ fx/llm.js（parseSSE /
// formatLLMTelemetry）+ ui/usage.js（recordLLMUsage）+ ui/step-state.js
//（markStepDone）。无跨簇状态读（本簇状态 = revise 对象私有）；host 对本簇
// 零调用点（监听器全部随簇迁入，无 init 可调）。
import { $, apiPost, toast } from "/js/app.js";
import { confirmModal } from "/js/ui/confirm.js";
import { esc } from "/js/fx/core.js";
import { parseSSE, formatLLMTelemetry } from "/js/fx/llm.js";
import { recordLLMUsage } from "/js/ui/usage.js";
import { markStepDone } from "/js/ui/step-state.js";

// ---------------------------------------------------------------------------
// 修订与深化阶段卡（工单 revise-deepen/05）：两条入口（当前会话 / 历史目录）
// → 影响分析（SSE）→ 确认修订（SSE）→ 可选深化（SSE）+ 编译验证 → 回滚。
// 事件词表镜像 events.py：impact_analyzing / diff_ready / revision_backup /
// revision_generating / deepening_start / compile_start / fix_start /
// verify_result / llm_telemetry / done / error。
// ---------------------------------------------------------------------------
let revise = {
  outputDir: "",      // 已加载上下文对应的输出目录
  source: "",         // "manifest" | "inferred"
  context: null,      // /api/revise/context 的 context 字段
  missing: [],        // missing 字段名列表（problem_text / requirements / main_c / slugs）
  analysis: null,     // /api/revise/analyze 的 done 载荷（可放弃）
  applyDone: null,    // /api/revise/apply 的 done 载荷
  deepenDone: null,   // /api/revise/deepen 的 done 载荷
  backupId: null,     // 最近一次备份（修订 / 深化 done 回传），回滚入口
  busy: false,        // 任一流程运行中（按钮置灰，防双击并发）
};

function reviseCurrentDir() {
  return $("res-dir").textContent.trim() || $("output-dir").value.trim();
}

/** 新 Q&A 条数：按连续空行分段计数（拆分规则 = 连续空行分段）。 */
function reviseCountQa(text) {
  const segs = text.split(/\n[ \t]*\n+/).map((s) => s.trim()).filter(Boolean);
  return segs.length || 1;
}

function renderReviseTelemetry(slot, data) {
  const el = $(slot === "analyze" ? "revise-llm-telemetry" : "revise-deepen-telemetry");
  el.textContent = formatLLMTelemetry(data);
  el.classList.remove("hidden");
}
function clearReviseTelemetry(slot) {
  const el = $(slot === "analyze" ? "revise-llm-telemetry" : "revise-deepen-telemetry");
  el.classList.add("hidden");
  el.textContent = "";
}

function reviseSetBusy(busy) {
  revise.busy = busy;
  // 禁用集合含回滚按钮：深化 SSE / 写盘 / 编译进行中不允许并发回滚；
  // 回滚按钮默认 hidden 由 class 控制，disabled 不影响其 hidden 状态。
  ["btn-revise-analyze", "btn-revise-apply", "btn-revise-deepen",
   "btn-revise-session", "btn-revise-load-dir", "btn-revise-rollback"].forEach((id) => { $(id).disabled = busy; });
}

function reviseResetAll() {
  revise.source = "";
  revise.context = null;
  revise.missing = [];
  revise.analysis = null;
  revise.applyDone = null;
  revise.deepenDone = null;
  revise.backupId = null;
  ["revise-context", "revise-analyze-box", "revise-exec-box",
   "revise-analysis", "revise-result"].forEach((id) => $(id).classList.add("hidden"));
  $("revise-analysis").innerHTML = "";
  $("revise-result").innerHTML = "";
  $("btn-revise-discard").classList.add("hidden");
  $("btn-revise-rollback").classList.add("hidden");
  $("revise-load-msg").textContent = "";
  $("revise-load-status").textContent = "";
  $("revise-analyze-msg").textContent = "";
  $("revise-analyze-status").textContent = "";
  $("revise-exec-msg").textContent = "";
  $("revise-exec-status").textContent = "";
  $("revise-rollback-status").textContent = "";
  clearReviseTelemetry("analyze");
  clearReviseTelemetry("exec");
}

/** 加载生成上下文（同步端点）：有清单直读 / 无清单反推；missing 字段前端提示补。 */
async function reviseLoad(outputDir) {
  const switched = revise.outputDir && revise.outputDir !== outputDir;
  if (switched) $("revise-qa-new").value = "";   // 换目录 = 新生命周期，旧 Q&A 清掉
  reviseResetAll();
  revise.outputDir = outputDir;
  $("revise-dir-input").value = outputDir;
  $("revise-load-status").textContent = "加载中…";
  try {
    const data = await apiPost("/api/revise/context", { output_dir: outputDir });
    revise.source = data.source || "";
    revise.context = data.context || {};
    revise.missing = data.missing || [];
    reviseRenderContext();
    $("revise-load-status").textContent = "加载完成";
  } catch (e) {
    revise.outputDir = "";
    $("revise-load-status").textContent = "";
    $("revise-load-msg").textContent = "加载失败：" + e.message;
  }
}

function reviseRenderContext() {
  const c = revise.context || {};
  $("revise-platform").textContent = c.platform || "—";
  $("revise-slugs").innerHTML = (c.slugs || []).length
    ? (c.slugs || []).map((s) => '<span class="chip out">' + esc(s) + "</span>").join(" ")
    : '<span class="muted">（空）</span>';
  $("revise-context-source").textContent = "（来源："
    + (revise.source === "manifest" ? "上下文清单直读" : "历史目录反推") + "）";
  // 题面展示优先用补题面输入框的值（非空时）：补题面后上下文区即时反映，无需重新加载
  const problemFill = $("revise-problem-text").value.trim();
  $("revise-problem").textContent = problemFill || c.problem_text || "（缺失）";
  $("revise-qa").textContent = c.qa_text || "（无）";
  const m = revise.missing || [];
  const warns = [];
  if (m.includes("problem_text")) warns.push("题面缺失：历史工程无法反推题面，修订分析需要题面证据——请在下方粘贴题面后重试。");
  if (m.includes("requirements")) warns.push("功能需求清单缺失：深化时 AI 缺少逐条需求依据，深化质量可能下降。");
  if (m.includes("main_c")) warns.push("main.c 缺失：深化需要现有 main.c 中的 TODO 预留区。");
  if (m.includes("slugs")) warns.push("模块集缺失：产物树无 modules/ 目录，将按空集分析（建议集从零推荐）。");
  const warnEl = $("revise-missing-warn");
  warnEl.innerHTML = warns.map((w) => "<div>⚠ " + esc(w) + "</div>").join("");
  warnEl.classList.toggle("hidden", !warns.length);
  $("revise-problem-fill").classList.toggle("hidden", !m.includes("problem_text"));
  $("revise-context").classList.remove("hidden");
  $("revise-analyze-box").classList.remove("hidden");
  $("revise-exec-box").classList.remove("hidden");
}

/** 修订 / 深化 SSE 流（runCompileOnce 先例）：done 载荷返回；error 终态 /
 * 断线 / HTTP 非 200 → throw（中文文案）。handlers = 进度事件词表分发。 */
async function reviseRunSSE(url, body, handlers) {
  let finished = false;
  let done = null;
  let errorMsg = null;
  let resp;
  try {
    resp = await fetch(url, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
  } catch (e) { throw new Error(e.message); }
  if (!resp.body) throw new Error("服务响应无流");
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.detail || ("请求失败（HTTP " + resp.status + "）"));
  }
  await parseSSE(resp, (type, raw) => {
    let data = {};
    try { data = JSON.parse(raw || "null") || {}; } catch { data = {}; }
    if (type === "done") { done = data; finished = true; }
    else if (type === "error") { errorMsg = data.message || "请求失败"; finished = true; }
    else if (handlers[type]) handlers[type](data);
  });
  if (errorMsg) throw new Error(errorMsg);
  if (!done) throw new Error(finished ? "服务未返回结果" : "连接中断：本次操作未完成，可安全重试");
  return done;
}

/** diff 卡渲染（确定性集合差，分析 / 执行共用）：added 绿 / removed 红 /
 * unchanged 灰；opts.summary = 修订记录形态（执行 done 的 diff 只带增删）。 */
function reviseRenderDiff(diff, opts) {
  const d = diff || {};
  const chips = (arr, cls, sign) => (arr || []).length
    ? (arr || []).map((s) => '<span class="chip ' + cls + '">' + sign + esc(s) + "</span>").join(" ")
    : '<span class="muted">无</span>';
  const rows = '<div class="head"><span class="slug">新增</span></div><div class="row" style="margin-top:4px">'
    + chips(d.added, "add", "+ ") + "</div>"
    + '<div class="head" style="margin-top:8px"><span class="slug">移除</span></div><div class="row" style="margin-top:4px">'
    + chips(d.removed, "del", "− ") + "</div>";
  return opts && opts.summary ? rows
    : rows + '<div class="head" style="margin-top:8px"><span class="slug">不变</span></div><div class="row" style="margin-top:4px">'
      + chips(d.unchanged, "same", "") + "</div>";
}

/** 分析 → 影响结论 + diff 卡 + 平台警告 + 建议模块集（可放弃）。 */
function reviseRenderAnalysis(data) {
  const box = $("revise-analysis");
  const parts = [];
  const impacts = data.impacts || [];
  if (impacts.length) {
    parts.push('<h4 style="margin-bottom:8px">逐条影响结论</h4>');
    parts.push(impacts.map((im) => {
      const add = (im.add || []).map((s) => '<span class="chip add">+ ' + esc(s) + "</span>").join("");
      const remove = (im.remove || []).map((s) => '<span class="chip del">− ' + esc(s) + "</span>").join("");
      const refs = (im.requirement_refs || []).map((r) => '<span class="chip out">' + esc(r) + "</span>").join("");
      return '<div class="item" style="margin-bottom:8px">'
        + '<div class="head"><span class="slug">Q&A #' + esc(im.qa_index) + "</span>"
        + (refs ? '<span class="muted">影响需求：' + refs + "</span>" : "")
        + "</div>"
        + '<div class="reason">' + esc(im.reason || "（无理由）") + "</div>"
        + (add || remove ? '<div class="row" style="margin-top:6px">' + add + remove + "</div>" : "")
        + "</div>";
    }).join(""));
  }
  parts.push('<h4 style="margin-bottom:8px">模块集 diff（确定性集合差）</h4>');
  parts.push('<div class="item">' + reviseRenderDiff(data.diff) + "</div>");
  const warns = data.warnings || [];
  parts.push('<h4 style="margin-top:12px;margin-bottom:8px">平台警告（按建议模块集重算）</h4>');
  parts.push(warns.length
    ? warns.map((w) => '<div class="warn-box unverified" style="margin-bottom:6px"><span class="slug">'
        + esc(w.slug) + "</span>：" + esc(w.message) + "</div>").join("")
    : '<div class="muted">无平台警告（建议模块集在该平台全部可用）。</div>');
  const suggested = data.suggested_slugs || [];
  parts.push('<h4 style="margin-top:12px;margin-bottom:8px">建议模块集</h4>');
  parts.push('<div class="row">' + (suggested.length
    ? suggested.map((s) => '<span class="chip out">' + esc(s) + "</span>").join(" ")
    : '<span class="muted">（空）</span>') + "</div>");
  box.innerHTML = parts.join("");
  box.classList.remove("hidden");
  $("btn-revise-discard").classList.remove("hidden");
  $("revise-confirmed-slugs").value = suggested.join(", ");   // 预填建议集（用户可编辑）
  box.scrollIntoView({ block: "nearest" });
}

/** 放弃分析结果：清空影响结论 / diff / 预填建议集，回到可重新分析的干净态。 */
function reviseDiscard() {
  // busy 守卫：分析 / 修订 / 深化进行中放弃无效（SSE 无法取消，完成后仍会渲染），直接忽略
  if (revise.busy) { $("revise-analyze-msg").textContent = "流程进行中，请等待完成后再放弃"; return; }
  revise.analysis = null;
  $("revise-analysis").classList.add("hidden");
  $("revise-analysis").innerHTML = "";
  $("btn-revise-discard").classList.add("hidden");
  $("revise-analyze-status").textContent = "";
  $("revise-analyze-msg").textContent = "";
  $("revise-confirmed-slugs").value = "";
  $("revise-result").classList.add("hidden");
  $("revise-result").innerHTML = "";
  $("btn-revise-rollback").classList.add("hidden");
  $("revise-exec-status").textContent = "";
  $("revise-exec-msg").textContent = "";
  revise.applyDone = null;
  revise.deepenDone = null;
  revise.backupId = null;
}

async function reviseAnalyze() {
  if (revise.busy) return;
  const qa = $("revise-qa-new").value.trim();
  if (!revise.outputDir) { $("revise-analyze-msg").textContent = "请先加载上下文（当前会话或历史目录）"; return; }
  if (!qa) { $("revise-analyze-msg").textContent = "请先粘贴新 Q&A 文本"; return; }
  const body = {
    output_dir: revise.outputDir,
    new_qa_text: qa,
    qa_count: reviseCountQa(qa),
  };
  const fill = $("revise-problem-text").value.trim();
  if (fill) body.problem_text = fill;   // 补题面覆盖回传（后端缺题面 400 中文提示；字段保留前向兼容）
  reviseSetBusy(true);
  $("revise-analyze-msg").textContent = "";
  $("revise-analyze-status").textContent = "请求中…";
  clearReviseTelemetry("analyze");
  try {
    const data = await reviseRunSSE("/api/revise/analyze", body, {
      impact_analyzing: () => { $("revise-analyze-status").textContent = "AI 影响分析中…（分钟级调用，请等待）"; },
      diff_ready: () => { $("revise-analyze-status").textContent = "diff 就绪，汇总中…"; },
      llm_telemetry: (d) => { renderReviseTelemetry("analyze", d); recordLLMUsage(d); },
    });
    revise.analysis = data;
    reviseRenderAnalysis(data);
    $("revise-analyze-status").textContent = "分析完成——请核对影响结论与 diff，确认后执行修订";
  } catch (e) {
    $("revise-analyze-status").textContent = "";
    $("revise-analyze-msg").textContent = e.message;   // 后端中文（含缺题面提示）
  } finally {
    reviseSetBusy(false);
  }
}

async function reviseApply() {
  if (revise.busy) return;
  const slugs = $("revise-confirmed-slugs").value.split(",").map((s) => s.trim()).filter(Boolean);
  const qa = $("revise-qa-new").value.trim();
  if (!revise.outputDir) { $("revise-exec-msg").textContent = "请先加载上下文（当前会话或历史目录）"; return; }
  if (!slugs.length) { $("revise-exec-msg").textContent = "请填写确认模块集（逗号分隔，可编辑）"; return; }
  if (!qa) { $("revise-exec-msg").textContent = "请先粘贴新 Q&A 文本（修订的 diff 记录需要 Q&A 原文）"; return; }
  const body = { output_dir: revise.outputDir, confirmed_slugs: slugs, new_qa_text: qa };
  // 补题面覆盖回传：与分析入口一致，输入框有值即带（后端 apply 端点支持 payload.problem_text）
  const fill = $("revise-problem-text").value.trim();
  if (fill) body.problem_text = fill;
  if (revise.analysis && (revise.analysis.impacts || []).length) body.impacts = revise.analysis.impacts;
  reviseSetBusy(true);
  $("revise-exec-msg").textContent = "";
  $("revise-exec-status").textContent = "请求中…";
  clearReviseTelemetry("exec");
  try {
    const data = await reviseRunSSE("/api/revise/apply", body, {
      revision_backup: () => { $("revise-exec-status").textContent = "备份中…（整树备份到输出目录外）"; },
      revision_generating: () => { $("revise-exec-status").textContent = "重生成中…（覆盖式重建输出目录）"; },
      llm_telemetry: (d) => { renderReviseTelemetry("exec", d); recordLLMUsage(d); },
    });
    revise.applyDone = data;
    markStepDone(11);
    toast("ok", "修订完成");
    reviseRenderApplyDone(data);
    if ($("revise-deepen-check").checked) {
      $("revise-exec-status").textContent = "修订完成，开始深化…";
      await reviseRunDeepen();   // 模块集无变化时同样自动进入深化
    } else {
      $("revise-exec-status").textContent = "修订完成——可继续「直接深化」或回滚";
    }
  } catch (e) {
    $("revise-exec-status").textContent = "";
    $("revise-exec-msg").textContent = e.message;
  } finally {
    reviseSetBusy(false);
  }
}

/** 修订执行结果：diff 记录（新增 / 移除 + 备份 + 时间）；模块集无变化 →
 * 「无需重生成」提示（main.c 手工编辑保留，深化可直接进行）。 */
function reviseRenderApplyDone(data) {
  if (data.backup_id) revise.backupId = data.backup_id;
  const box = $("revise-result");
  const parts = ['<h4 style="margin-bottom:8px">修订 diff 记录</h4>', '<div class="item">'];
  if (data.regenerated === false) {
    parts.push('<div class="ok" style="font-weight:600">无需重生成：模块集无变化，main.c 手工编辑保留；新 Q&A 已并入上下文清单。</div>');
  } else {
    parts.push(reviseRenderDiff(data.diff, { summary: true }));
  }
  parts.push('<div class="reason" style="margin-top:8px">备份：<span class="slug">' + esc(data.backup_id || "—")
    + "</span> · 修订时间：" + esc(data.generated_at || "—") + "</div>");
  // 用户故事 10：diff 记录含 Q&A 原文——展示本次并入的 Q&A 全文（esc 转义 + pre-wrap 保留换行）
  if (data.qa_text) {
    parts.push('<div class="reason" style="margin-top:8px;white-space:pre-wrap"><strong>本次并入 Q&A：</strong>'
      + esc(data.qa_text) + "</div>");
  }
  parts.push("</div>");
  box.innerHTML = parts.join("");
  box.classList.remove("hidden");
  $("btn-revise-rollback").classList.toggle("hidden", !revise.backupId);
}

/** 深化（直接入口）：按钮触发路径（busy 守卫）；勾选「执行后深化」走
 * reviseRunDeepen（busy 由修订流程持有）。 */
async function reviseDeepen() {
  if (revise.busy) return;
  await reviseRunDeepen();
}

/** 深化流核心：AI 填 TODO → 备份写盘 → 编译验证闭环（绿 = 已验证 /
 * 无工具链降级 = 未验证 / 修一轮仍红 = 失败）。 */
async function reviseRunDeepen() {
  if (!revise.outputDir) { $("revise-exec-msg").textContent = "请先加载上下文（当前会话或历史目录）"; return; }
  reviseSetBusy(true);
  $("revise-exec-msg").textContent = "";
  $("revise-exec-status").textContent = "请求中…";
  clearReviseTelemetry("exec");
  try {
    const body = { output_dir: revise.outputDir };
    // 补题面覆盖回传：深化同样需要题面证据（与 analyze / apply 入口一致）
    const fill = $("revise-problem-text").value.trim();
    if (fill) body.problem_text = fill;
    const data = await reviseRunSSE("/api/revise/deepen", body, {
      deepening_start: () => { $("revise-exec-status").textContent = "AI 填 TODO 中…（分钟级调用，请等待）"; },
      compile_start: () => { $("revise-exec-status").textContent = "编译中…"; },
      fix_start: () => { $("revise-exec-status").textContent = "AI 修复中…（首轮编译未过，自动修复一轮）"; },
      verify_result: () => { $("revise-exec-status").textContent = "验证结果收集中…"; },
      llm_telemetry: (d) => { renderReviseTelemetry("exec", d); recordLLMUsage(d); },
    });
    reviseRenderVerify(data);
    if (data.status !== "failed") { markStepDone(11); toast("ok", "深化完成"); }  // 验证通过 / 降级未验证都算闭环
    $("revise-exec-status").textContent = "深化完成";
  } catch (e) {
    $("revise-exec-status").textContent = "";
    $("revise-exec-msg").textContent = e.message;
  } finally {
    reviseSetBusy(false);
  }
}

/** 深化验证结果：verified = 绿 ✓；unverified = 黄降级提示（结果保留，未验证）；
 * failed = 红（已备份可回滚）。backup_id 进回滚入口。 */
function reviseRenderVerify(data) {
  revise.deepenDone = data;
  if (data.backup_id) revise.backupId = data.backup_id;
  const compile = data.compile || {};
  let badgeHtml, detailHtml;
  if (data.status === "verified") {
    badgeHtml = '<span class="ok" style="font-weight:600">✓ 已验证（编译通过）</span>';
    detailHtml = esc("编译通过 · exit "
      + (compile.exit_code === null || compile.exit_code === undefined ? "—" : compile.exit_code)
      + (compile.summary ? " · " + compile.summary : ""));
  } else if (data.status === "unverified") {
    badgeHtml = '<span style="color:var(--warn);font-weight:600">⚠ 未验证（无工具链降级）</span>';
    detailHtml = esc(data.message || "未检测到编译工具链：深化结果已写入 main.c，但未经编译验证——请在设置页配置工具链后重新编译，或手动编译确认。");
  } else {
    badgeHtml = '<span style="color:var(--danger);font-weight:600">✗ 未通过（编译验证失败）</span>';
    detailHtml = esc(data.message || "编译验证未通过，深化结果已写入 main.c（已备份，可回滚）。");
  }
  const box = $("revise-result");
  box.innerHTML = box.innerHTML
    + '<div class="item" style="margin-top:10px"><div class="head"><span class="slug">深化验证</span> ' + badgeHtml + "</div>"
    + '<div class="reason">' + detailHtml + "</div>"
    + '<div class="reason">备份：<span class="slug">' + esc(data.backup_id || "—") + "</span></div>"
    + reviseRenderDeepenDiff(data.main_diff)
    + "</div>";
  box.classList.remove("hidden");
  $("btn-revise-rollback").classList.toggle("hidden", !revise.backupId);
}

/** 深化效果（工单 deepen-report/01）：main.c 前后确定性 diff 介绍卡——
 * 统计行（新增 / 删除 / 处数）+ 每个 hunk 一个可折叠改动点（标题优先取被
 * 替换的 TODO 注释，展开 = 逐行着色 diff：新增绿 / 删除红 / 上下文灰）。
 * 事实源 = 后端真实 diff（不依赖 LLM 自述）；main_diff = null → 占位提示；
 * 字段缺失（旧后端）→ 不渲染。 */
function reviseRenderDeepenDiff(diff) {
  if (diff === undefined) return "";
  if (diff === null) return '<div class="muted" style="margin-top:8px">深化未改动 main.c（无差异）。</div>';
  const hunks = diff.hunks || [];
  if (!hunks.length) return '<div class="muted" style="margin-top:8px">深化未改动 main.c（无差异）。</div>';
  const s = diff.stats || {};
  const parts = ['<div class="reason" style="margin-top:8px"><strong>深化效果：</strong>'
    + '新增 <span class="ok">+' + (s.additions || 0) + "</span> 行 · 删除 <span style=\"color:var(--danger)\">−"
    + (s.deletions || 0) + "</span> 行 · " + (s.hunks || 0) + " 处改动</div>"];
  hunks.forEach((h) => {
    const title = h.title || "第 " + (h.line || "?") + " 行附近";
    parts.push('<details style="margin-top:6px"><summary class="slug" style="cursor:pointer">'
      + esc(title) + '</summary><pre style="margin:6px 0 0;padding:8px;background:#f7f7f7;border-radius:4px;font-size:12px;line-height:1.5;overflow:auto;white-space:pre">'
      + (h.lines || []).map(reviseDiffLineHtml).join("") + "</pre></details>");
  });
  return parts.join("");
}

/** diff 行着色渲染（内容已由后端剥离 +/- 前缀，此处只补前缀与颜色）。 */
function reviseDiffLineHtml(entry) {
  const text = esc(entry.text);
  if (entry.kind === "add") return '<span style="color:#2e7d32;background:#e8f5e9">+' + text + "</span>\n";
  if (entry.kind === "del") return '<span style="color:#c62828;background:#fdecea">-' + text + "</span>\n";
  return '<span style="color:#777">' + text + "</span>\n";
}

/** 回滚：恢复备份整树 → 清结果 → 重新加载上下文刷新状态。 */
async function reviseRollback() {
  if (!revise.backupId) return;
  if (!await confirmModal({
    title: "确认回滚？",
    message: "回滚本次修订/深化？将把输出目录整体恢复到备份时的状态（含手工编辑），修订/深化的改动全部撤销。",
    danger: true,
    confirmText: "确认回滚",
  })) return;
  const btn = $("btn-revise-rollback");
  btn.disabled = true;
  $("revise-rollback-status").textContent = "";
  try {
    const data = await apiPost("/api/revise/rollback", {
      output_dir: revise.outputDir, backup_id: revise.backupId,
    });
    revise.backupId = null;
    revise.applyDone = null;
    revise.deepenDone = null;
    btn.classList.add("hidden");
    $("revise-result").classList.add("hidden");
    $("revise-result").innerHTML = "";
    await reviseLoad(revise.outputDir);   // 回滚后刷新上下文展示（题面 / 模块 / Q&A）
    $("revise-exec-status").textContent = "已回滚到备份状态";
    $("revise-rollback-status").textContent = "已回滚 " + data.restored.length + " 项："
      + data.restored.join("、") + "——目录已恢复，状态已刷新";
  } catch (e) {
    $("revise-rollback-status").textContent = "回滚失败：" + e.message;
  } finally {
    btn.disabled = false;
  }
}

$("btn-revise-session").addEventListener("click", () => {
  const dir = reviseCurrentDir();
  if (!dir) { $("revise-load-msg").textContent = "请先生成工程（或填写输出目录）"; return; }
  reviseLoad(dir);
});
$("btn-revise-load-dir").addEventListener("click", () => {
  const dir = $("revise-dir-input").value.trim();
  if (!dir) { $("revise-load-msg").textContent = "请填写输出目录路径"; return; }
  reviseLoad(dir);
});
$("revise-dir-input").addEventListener("keydown", (e) => {
  if (e.key === "Enter") $("btn-revise-load-dir").click();
});
$("btn-revise-analyze").addEventListener("click", reviseAnalyze);
$("btn-revise-discard").addEventListener("click", reviseDiscard);
$("btn-revise-apply").addEventListener("click", reviseApply);
$("btn-revise-deepen").addEventListener("click", reviseDeepen);
$("btn-revise-rollback").addEventListener("click", reviseRollback);
// 补题面输入即时更新上下文区题面展示（无需重新加载；无输入时回落到上下文清单值）
$("revise-problem-text").addEventListener("input", () => {
  const fill = $("revise-problem-text").value.trim();
  $("revise-problem").textContent = fill
    || (revise.context && revise.context.problem_text) || "（缺失）";
});


// ---- 本簇导出面（host 零调用点——按工单 17 检查表导出为模块 API） ----
export { reviseLoad, reviseAnalyze, reviseApply, reviseRollback, reviseRunDeepen,
  reviseResetAll, reviseRenderContext };
