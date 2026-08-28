// ui/flash.js — 烧录胶水共享（工单 flash-deploy/02 评审整改：两簇 flashRun
// 高度同构，抽共享执行体）——生成结果面板（generate-core）与任务结果面板
// （generate-tasks）共用：busy 置位（调用方守卫）→ 「烧录中…（探针，请确认
// 连接）」→ POST /api/flash → 成功/失败 flashResultHTML；400（产物缺失 /
// 工具缺失）→ flashGuideHTML 指引卡（中文，不甩裸报错）。差异（busy 守卫
// 方式、状态/结果元素、平台名）由调用方以参数注入——本模块只做「执行 +
// 渲染」共享段。
import { $, apiPost, toast } from "/js/app.js";
import { flashBusyText, flashResultHTML, flashGuideHTML } from "/js/fx/flash.js";

/** 共享烧录执行体。opts：{dir, platform, statusEl, resultEl, setBusy,
 * busyText?}——setBusy(true/false) 由调用方传入（生成 = 按钮 disabled /
 * 任务 = tasks.busy 全局闸）；statusEl / resultEl 为渲染目标；platform 仅
 * 用于 busy 文案的探针名（mspm0=XDS110 / stm32=ST-Link / 未知=通用）。
 * 返回 data（成功或失败载荷）或 null（前置 400，已渲染指引卡）。 */
export async function flashRunShared(opts) {
  const dir = opts && opts.dir;
  const statusEl = opts && opts.statusEl;
  const resultEl = opts && opts.resultEl;
  const setBusy = opts && opts.setBusy;
  if (!dir) { if (statusEl) statusEl.textContent = "请先加载输出目录"; return null; }
  if (setBusy) setBusy(true);
  if (statusEl) statusEl.textContent = flashBusyText((opts && opts.platform) || "");
  if (resultEl) resultEl.innerHTML = "";
  try {
    const data = await apiPost("/api/flash", { output_dir: dir });
    if (statusEl) statusEl.textContent = "";
    if (resultEl) resultEl.innerHTML = flashResultHTML(data);
    toast(data.ok ? "ok" : "error", data.ok ? "烧录成功" : "烧录未成功，请查看输出");
    return data;
  } catch (e) {
    if (statusEl) statusEl.textContent = "";
    if (resultEl) resultEl.innerHTML = flashGuideHTML(e.message);
    return null;
  } finally {
    if (setBusy) setBusy(false);
  }
}
