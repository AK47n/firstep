// ui/params.js — 生成页 · 参数速调卡（工单 param-tune/02）DOM 胶水。
//
// 参数速调 = 任务推进区内的独立卡：AI 扫描 main.c 可调数值（阈值 / 速度 /
// PID 系数 / 延时 / 占空比…）→ 参数表（改值输入框）→「改这个并验证」=
// 确定性替换声明处那一个常量（零 LLM 改值）→ 备份 + 编译验证 → diff /
// 回滚 / 烧录。参数表落盘 .contest_params.json（与任务清单独立）；改值不
// 造任务轮次、不动任务状态（spec param-tune 故事 3——改值不是重做任务）。
//
// 事件词表镜像 events.py：param_scanning / param_result / param_applying /
// compile_start / fix_start / verify_result / llm_telemetry / done / error。
// 纯件在 fx/params.js（paramListHTML / paramResultHTML）。
// 依赖：app.js（$ / apiPost / toast）+ fx/llm.js（parseSSE /
// formatLLMTelemetry）+ ui/usage.js（recordLLMUsage）+ ui/confirm.js
//（confirmModal）+ generate-revise.js（reviseGetDir）+ generate-tasks.js
//（tasksIsBusy / tasksSetBusy——与任务执行/回滚/烧录共用全局忙碌闸，
//  防两个流程同时写 main.c）。
import { $, apiPost, toast } from "/js/app.js";
import { confirmModal } from "/js/ui/confirm.js";
import { parseSSE, formatLLMTelemetry } from "/js/fx/llm.js";
import { paramListHTML, paramResultHTML } from "/js/fx/params.js";
import { recordLLMUsage } from "/js/ui/usage.js";
import { reviseGetDir } from "./generate-revise.js";
import { tasksIsBusy, tasksSetBusy } from "./generate-tasks.js";

// 本簇状态（会话级；落盘真相 = .contest_params.json）：plan = 最近一次
// read/scan 的参数数组（含 valid），scanned = 是否识别过（无表 = 未识别，
// 空表不落盘——/read 后端给 scanned 标志，前端两态区分），busy = 一轮
// 识别/应用进行中。
let paramsState = {
  plan: null,
  scanned: false,
  busy: false,
};

function paramsDir() {
  return reviseGetDir();
}

function paramsStatus(text) {
  const el = $("params-status");
  if (el) el.textContent = text || "";
}

function paramsSetBusy(busy) {
  paramsState.busy = busy;
  tasksSetBusy(busy);
  const scanBtn = $("btn-params-scan");
  if (scanBtn) scanBtn.disabled = busy;
  paramsRender();
}

/** 参数速调徽章快照（工单 step11-tabs-ui/02）：已识别参数条数（未识别 = 0）。 */
export function paramsSummary() {
  return { count: (paramsState.plan || []).length };
}

/** 面板空态引导（step11-tabs-ui/02 评审整改）：未加载输出目录时显示「先去
 * 修订页签加载目录」提示（与 delivery/tasks 同判据 dir——目录就绪后隐藏；
 * 未识别场景由网格空态文案承接，不混用）。 */
function updateParamsEmptyHint() {
  const hint = $("params-empty-hint");
  if (hint) hint.classList.toggle("hidden", !!paramsDir());
}

/** 参数表渲染：plan 空（未识别）→ 引导文案（hidden 表格）；有表 → 表格。
 * 应用后重读磁盘（old_value 已变 + valid 重验）也走这里。emptyScan =
 * 已识别但无参数（scanned 两态分支，评审整改——空表不落盘靠 /read 标志）。 */
function paramsRender() {
  const grid = $("params-grid");
  if (!grid) return;
  grid.innerHTML = paramListHTML(paramsState.plan, {
    running: paramsState.busy,
    emptyScan: paramsState.scanned,
  });
  grid.classList.toggle("hidden", !paramsState.plan);
  updateParamsEmptyHint();
  // 状态徽章（step11-tabs-ui/02）：参数表任何变化（识别/应用/重读）后广播快照
  window.dispatchEvent(new CustomEvent("step11-state-changed"));
}

/** 恢复旧值（工单 step11-tabs-ui/03）：纯前端把输入框复位为识别时的原值，
 * 不触发 API / 不写盘——点「应用」才真正写入并验证。 */
function paramsResetInput(name) {
  const item = (paramsState.plan || []).find((p) => String(p.name) === name);
  const input = item ? $("params-input-" + name) : null;
  if (!input || item.old_value === undefined || item.old_value === null) return;
  input.value = String(item.old_value);
  input.focus();
  toast("info", "输入框已恢复为原值（未保存——点「应用」才会写入并编译验证）");
}

/** 结果面板渲染（应用成功后插入；失败清空）。 */
function paramsRenderResult(data) {
  const box = $("params-result");
  if (!box) return;
  box.innerHTML = data ? paramResultHTML(data, paramsDir()) : "";
}

/** 跨簇重置（目录切换 / 清单作废）：参数表随目录生命周期走。 */
function paramsReset() {
  paramsState.plan = null;
  paramsState.scanned = false;
  paramsState.busy = false;
  const grid = $("params-grid");
  if (grid) { grid.innerHTML = ""; grid.classList.add("hidden"); }
  const box = $("params-result");
  if (box) box.innerHTML = "";
  const msg = $("params-msg");
  if (msg) msg.textContent = "";
  paramsStatus("");
  updateParamsEmptyHint();
  // 状态徽章（step11-tabs-ui/02）：重置路径未走 paramsRender，也要广播快照
  window.dispatchEvent(new CustomEvent("step11-state-changed"));
}

/** 重读磁盘参数表（目录加载 / 应用成功后回填）：/read 带 valid 重验——
 * 旧锚失效的行被禁用 + 标记（main.c 被任务执行/手工编辑改过）；scanned
 * 标志区分「未识别」与「已识别无参数」（空表不落盘）。*/
async function paramsReload() {
  const dir = paramsDir();
  if (!dir) return;
  try {
    const data = await apiPost("/api/tasks/params/read", { output_dir: dir });
    paramsState.plan = data.params || [];
    paramsState.scanned = !!data.scanned;
    paramsRender();
  } catch (e) {
    // 读取失败（表损坏 / 目录没了）：不清空旧展示，错误留给操作提示
  }
}

/** 识别 main.c 参数（SSE：param_scanning → param_result → done{params}）。 */
async function paramsScan() {
  if (paramsState.busy || tasksIsBusy()) {
    toast("info", "有流程正在进行，请等当前操作完成后再试");
    return;
  }
  const dir = paramsDir();
  if (!dir) { $("params-msg").textContent = "请先在上方「上下文入口」加载当前会话或历史目录"; return; }
  paramsSetBusy(true);
  $("params-msg").textContent = "";
  paramsRenderResult(null);
  try {
    const data = await tasksRunSSE("/api/tasks/params/scan", { output_dir: dir }, {
      param_scanning: () => { paramsStatus("AI 扫描 main.c 可调参数中…（分钟级调用，请等待）"); },
      llm_telemetry: (d) => {
        const tel = $("tasks-llm-telemetry");
        if (tel) {
          tel.textContent = formatLLMTelemetry(d);
          tel.classList.remove("hidden");
        }
        recordLLMUsage(d);
      },
    });
    paramsState.plan = data.params || [];
    paramsState.scanned = true; // 识别过（空表也算——scan 无参数不落盘）
    paramsRender();
    paramsStatus("识别完成——改值 = 只替换那一个常量，点「改这个并验证」");
    toast("ok", "参数识别完成");
  } catch (e) {
    $("params-msg").textContent = e.message;
    paramsStatus("");
  } finally {
    paramsSetBusy(false);
  }
}

/** 应用参数（SSE：param_applying → compile_start → fix_start →
 * verify_result → done{status,backup_id,compile,main_diff,message}）：
 * 改值零 LLM（确定性替换）；done 后重读参数表刷新 old_value/valid。 */
async function paramsApply(name) {
  if (paramsState.busy || tasksIsBusy()) {
    toast("info", "有流程正在进行，请等当前操作完成后再试");
    return;
  }
  const dir = paramsDir();
  if (!dir) { $("params-msg").textContent = "请先在上方「上下文入口」加载当前会话或历史目录"; return; }
  const input = $("params-input-" + name);
  const value = input && input.value || "";
  if (!value.trim()) { $("params-msg").textContent = "新值不能为空（请输入数值后再应用）"; return; }
  paramsSetBusy(true);
  $("params-msg").textContent = "";
  try {
    const data = await tasksRunSSE("/api/tasks/params/apply", {
      output_dir: dir, name: name, value: value,
    }, {
      param_applying: () => { paramsStatus("正在应用参数：备份 + 写盘 + 编译验证…"); },
      compile_start: () => { paramsStatus("编译中…"); },
      fix_start: () => { paramsStatus("首轮编译未过，自动修复轮中…"); },
      verify_result: () => { paramsStatus("验证结果收集中…"); },
      llm_telemetry: (d) => {
        const tel = $("tasks-llm-telemetry");
        if (tel) {
          tel.textContent = formatLLMTelemetry(d);
          tel.classList.remove("hidden");
        }
        recordLLMUsage(d);
      },
    });
    paramsRenderResult(data);
    await paramsReload();   // 刷 new old_value + valid 重验（其余参数可能受影响）
    if (data.status === "failed") {
      paramsStatus("参数修改失败（编译仍红）——结果已写入 main.c，可回滚或重试");
      toast("error", "编译未通过——已备份，可回滚或重试");
    } else if (data.status === "unverified") {
      paramsStatus("参数已写入（无工具链降级：未经编译验证）——请配置工具链或上板确认");
      toast("info", "参数已写入——未经编译验证");
    } else {
      paramsStatus("参数修改完成——可回滚 / 烧录上板验证");
      toast("ok", "参数已修改并通过编译验证");
    }
  } catch (e) {
    $("params-msg").textContent = e.message;
    paramsStatus("");
  } finally {
    paramsSetBusy(false);
  }
}

/** 回滚本次参数修改：复用 /api/revise/rollback（同备份族）→ 重读参数表。 */
async function paramsRollback(backupId) {
  if (paramsState.busy || tasksIsBusy()) return;
  if (!await confirmModal({
    title: "确认回滚？",
    message: "将把输出目录整体恢复到本次参数修改前的状态（含 main.c），本次参数改动全部撤销；其他已完成任务的改动不受影响。",
    danger: true,
    confirmText: "确认回滚",
  })) return;
  const dir = paramsDir();
  if (!dir) { $("params-msg").textContent = "请先在上方「上下文入口」加载当前会话或历史目录"; return; }
  paramsSetBusy(true);
  paramsStatus("回滚中…");
  try {
    await apiPost("/api/revise/rollback", { output_dir: dir, backup_id: backupId });
    paramsRenderResult(null);
    await paramsReload();
    toast("ok", "已回滚本次参数修改");
  } catch (e) {
    paramsStatus("");
    $("params-msg").textContent = "回滚失败：" + e.message;
  } finally {
    paramsSetBusy(false);
  }
}

// SSE 流（tasksRunSSE 同款语义：done 载荷返回；error 终态 / 断线 throw）——
// 不 import generate-tasks 的私有运行器（SSE 运行器保持簇私有；本簇只 import
// 其导出的 tasksIsBusy/tasksSetBusy 共享闸，两侧无运行器耦合），本簇自持一份。
async function tasksRunSSE(url, body, handlers) {
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

// 监听器（import 时绑定：module 脚本延迟执行，DOM 已就绪）
$("btn-params-scan").addEventListener("click", () => paramsScan());
$("params-grid").addEventListener("click", (event) => {
  const btn = event.target.closest(".btn-params-apply");
  if (btn && btn.dataset.paramName) paramsApply(btn.dataset.paramName);
  else {
    const reset = event.target.closest(".btn-params-reset");
    if (reset && reset.dataset.paramName) paramsResetInput(reset.dataset.paramName);
  }
});
// 输入框内 Enter 直接应用（工单 step11-tabs-ui/03）：values 输入完回车即走
// paramsApply——与点「应用」同一条路径（busy 守卫 / 空值校验在 apply 内）。
$("params-grid").addEventListener("keydown", (event) => {
  if (event.key !== "Enter") return;
  const input = event.target.closest(".param-input");
  if (!input) return;
  event.preventDefault();
  const card = input.closest(".param-card");
  const name = card && card.dataset.paramName;
  if (name) paramsApply(name);
});
$("params-result").addEventListener("click", (event) => {
  const btn = event.target.closest(".btn-params-rollback");
  if (btn && btn.dataset.backup) paramsRollback(btn.dataset.backup);
});

// 跨簇重置：目录切换清空 + 静默重读（已有参数表则回填）；
// 清单作废（修订重生成）只清空（新工程无参数表）
window.addEventListener("revise-context-loaded", () => { paramsReset(); paramsReload(); });
window.addEventListener("tasks-invalidated", () => { paramsReset(); });

export { paramsScan, paramsApply, paramsReload };
