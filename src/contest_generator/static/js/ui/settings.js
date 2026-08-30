// ui/settings.js — 设置 tab DOM 胶水（阶段 2 工单 10）
//
// 设置 tab 全部胶水：配置加载（loadSettings：主/视觉/工具链/LLM 单价与计费
// 时段/推荐缓存/收敛轮数）与保存（btn-save-settings → PUT /api/settings +
// refreshState 重载）、视觉服务预设切换（VISION_PRESETS / VISION_HINTS /
// syncVisionProviderFromFields / applyVisionPreset + 手改转自定义）、视觉自检、
// 环境体检（envCheckRun，渲染件在 fx/env.js）、价格参考表与周期占位
// （renderPriceReference / periodPlaceholders，数据单源 = 后端）、单价收集
// （collectLlmPrices → llmPricesDefaults，单价表属 ui/usage.js——工单 04 前置
// 拆分持有，本模块经 import 读写活绑定）、最近 LLM 工作流渲染
// （renderRecentWorkflows / loadRecentWorkflows，纯件在 fx/workflow.js——
// 工单 01 迁）、设置页折叠 glue（saveSettingsCollapse / initSettingsCollapse /
// expandSettingsCollapse，纯件在 fx/settings.js——工单 10 迁；expand 为
// flash-guide-settings/03 新增：指引「去设置页配置」展开工具链卡并落盘）。
// 状态（模块内）：visionZhipuMask / visionApplyingPreset（视觉预设联动）。
// 跨簇接缝（模块无法 import host 作用域）：refreshState（保存后重载——
// 原为 host 函数，唯一调用点随本簇迁入）写 toolchains + 调
// renderToolchainStatus（宿主 E 簇 16 迁 / 启动共用）——经 setSettingsDeps
// 注册薄胶水（16 迁出后改静态 import）；renderPlatforms / renderModulePool
// 经 ui/generate-recommend.js import（12 交付成立）。
// host 页签分发器 / 启动区经顶部 import 调 loadSettings / loadRecentWorkflows /
// initSettingsCollapse（见 import 行与启动区）。
// 顶层监听（set-vision-provider / set-vision-base-url / set-vision-model /
// btn-vision-selfcheck / btn-env-check / price-period 收音机 / set-local-llm-model /
// btn-save-settings / btn-refresh-recent-wf）在 import 时绑定。
import { $, apiGet, apiPut, apiPost, setState, state, toast } from "/js/app.js";
import { esc } from "/js/fx/core.js";
import { envCheckStatusHTML, toolchainProbeText } from "/js/fx/env.js";
import { SETTINGS_COLLAPSE_KEY, parseSettingsCollapse, effectiveCollapsed, settingsMasterLabel, settingsSectionHead, applySettingsCollapseState, secretEyeState } from "/js/fx/settings.js";
import { formatWorkflowCall, formatWorkflowSummary } from "/js/fx/workflow.js";
import { collectResettableKeys } from "/js/fx/reset.js";
import { confirmModal } from "/js/ui/confirm.js";
import { gotoNavTab } from "/js/ui/goto-nav.js";  // 跳转原语（无回边：goto-nav 不 import settings）
import { llmPricesDefaults, setLlmPricesDefaults } from "/js/ui/usage.js";
import { renderPlatforms, renderModulePool } from "/js/ui/generate-recommend.js";

// ---- 跨簇接缝（host 启动区 setSettingsDeps 注册；16 迁出后改静态 import）----
const settingsDeps = {};
export function setSettingsDeps(deps) { Object.assign(settingsDeps, deps); }

// API key / 视觉 key 显隐切换（工单 ux-polish/01）：默认密码态（掩码值与新粘贴
// 的明文 key 都不外露），点「显示」才看明文；文案与 aria-pressed 随状态走。
for (const [btnId, inputId] of [["btn-eye-api", "set-api-key"], ["btn-eye-vision", "set-vision-api-key"]]) {
  $(btnId).addEventListener("click", () => {
    const input = $(inputId);
    const next = secretEyeState(input.type);
    input.type = next.nextType;
    $(btnId).textContent = next.label;
    $(btnId).setAttribute("aria-pressed", String(next.nextType === "text"));
  });
}

/** 烧录工具的「已自动找到」状态行（工单 flash-deploy/02）：覆盖为空且自动
 * 探测命中 → muted 提示（display + exe 短路径）；否则清空。kind 限定用于
 * st-flash 字段（stm32 探测优先 OpenOCD，st-flash 只在兜底命中时提示）。 */
function flashAutoStatus(spanId, tool, override, kind) {
  const el = $(spanId);
  if (!el) return;
  const hit = tool && (!override || !String(override).trim())
    && (!kind || tool.kind === kind);
  el.textContent = hit ? "已自动找到：" + (tool.display || "") + "（" + tool.exe + "）" : "";
}

export async function loadSettings() {
  try {
    const s = await apiGet("/api/settings");
    $("set-base-url").value = s.base_url || "https://api.deepseek.com";
    $("set-model").value = s.model || "deepseek-v4-flash";
    // key 只回掩码（前 4 位 + 与真实长度一致的圆点），直接填入文本框
    $("set-api-key").value = s.api_key;
    $("set-lib-dir").value = s.module_library_dir;
    $("set-masters-dir").value = s.masters_dir;
    // 工具链可选覆盖（工单 autocompile-loop/01）：空串 = 自动探测
    $("set-uv4-path").value = s.uv4_path || "";
    $("set-gmake-path").value = s.gmake_path || "";
    // CCS 三件套可选覆盖（工单 mspm0-build-makefiles/01）：空串 = 自动探测
    $("set-ccs-sdk-dir").value = s.ccs_sdk_dir || "";
    $("set-ccs-compiler-dir").value = s.ccs_compiler_dir || "";
    $("set-ccs-sysconfig-cli").value = s.ccs_sysconfig_cli || "";
    // 烧录工具可选覆盖（工单 flash-deploy/02）：空串 = 自动探测
    $("set-openocd-path").value = s.openocd_path || "";
    $("set-stflash-path").value = s.stflash_path || "";
    $("set-dslite-path").value = s.dslite_path || "";
    // 「已自动找到」状态（spec 故事 8）：覆盖为空且自动探测命中 → 显示探测
    // 到的工具（display + exe）；覆盖非空 / 探测不到 = 空（用户手动填或留空）
    const autoTools = s.flash_auto_tools || {};
    flashAutoStatus("set-openocd-status", autoTools.stm32, s.openocd_path);
    flashAutoStatus("set-stflash-status", autoTools.stm32, s.stflash_path, "stflash");
    flashAutoStatus("set-dslite-status", autoTools.mspm0, s.dslite_path);
    // 本地 LLM 端点（工单 local-llm-routing/03）：空串 = 本地路由关闭
    $("set-local-llm-base-url").value = s.local_llm_base_url || "";
    // 本地模型下拉（速度/质量自选）：预设三档；自定义旧值保留为附加选项
    const llmSel = $("set-local-llm-model");
    if (s.local_llm_model && !Array.from(llmSel.options).some((o) => o.value === s.local_llm_model)) {
      const opt = document.createElement("option");
      opt.value = s.local_llm_model;
      opt.textContent = s.local_llm_model + "（自定义）";
      llmSel.appendChild(opt);
    }
    llmSel.value = s.local_llm_model || "";
    // 视觉通道（工单 vision-deepseek-native/01）：key 只回掩码；空 = 复用主
    // DeepSeek key（自定义视觉端点 = 关闭，见设置页说明）
    $("set-vision-base-url").value = s.vision_base_url || "";
    $("set-vision-api-key").value = s.vision_api_key || "";
    $("set-vision-model").value = s.vision_model || "";
// 问答式精注记开关（工单 vision-detail-qa/01）：缺省开——旧 state 无该字段
// 时按开处理（`!== false`），避免老用户升级后悄悄丢精注记
$("set-vision-detail-qa").checked = s.vision_detail_qa !== false;
    // 视觉服务下拉（工单 vision-provider-switch/01）：掩码 key 存档供切回智谱
    // 时回填沿用；按 base_url 推断当前模式（不覆盖用户已存字段）
    visionZhipuMask = s.vision_api_key || "";
    syncVisionProviderFromFields();
    // LLM 单价（工单 llm-cost-control/01 + 缓存拆分 + 计费时段）：输入框只显示
    // 用户显式覆盖（llm_prices_override 原文）；无覆盖 = 留空，placeholder 显示
    // 所选时段的官方价（留空 = 按时段基准价计费）
    setLlmPricesDefaults(s.llm_prices || {});
    const priceOverride = s.llm_prices_override || {};
    const dsOv = priceOverride.deepseek || {};
    $("set-ds-in-hit").value = dsOv.input_cache_hit_per_million ?? "";
    $("set-ds-in").value = dsOv.input_cache_miss_per_million ?? (dsOv.input_per_million ?? "");
    $("set-ds-out").value = dsOv.output_per_million ?? "";
    const localOv = priceOverride.local || {};
    $("set-local-in").value = localOv.input_cache_miss_per_million ?? (localOv.input_per_million ?? "");
    $("set-local-out").value = localOv.output_per_million ?? "";
    // 计费时段（工单 01 扩展）：peak 高峰 / off_peak 空闲，决定 placeholder 与基准价
    const period = s.llm_price_period === "off_peak" ? "off_peak" : "peak";
    $("period-peak").checked = period === "peak";
    $("period-off-peak").checked = period === "off_peak";
    renderPriceReference(s.price_reference);
    periodPlaceholders(period);
    // 推荐缓存开关（工单 llm-cost-control/02）：缺省开
    $("set-recommend-cache").checked = s.recommend_cache_enabled !== false;
    // 收敛轮数上限（工单 01）：缺省 4
    $("set-recommend-rounds").value = String(s.recommend_max_rounds ?? 4);
    $("set-config-path").textContent = s.config_path;
    $("settings-banner").classList.toggle("hidden", !!s.configured);
    void refreshToolchainProbes();  // 已保存配置的探测回显（工单 ux-walkthrough-02/06）
  } catch (e) { $("settings-msg").textContent = e.message; }
}

// 工具链内联探测回显（工单 ux-walkthrough-02/06）：E1 探测结果逐字段显示
// 「已配置/自动探测到/未找到」；只读探测失败静默（不打扰设置页）。
async function refreshToolchainProbes() {
  try {
    const st = await apiGet("/api/env/status");
    const map = [
      ["set-uv4-probe", (st.toolchains || {}).stm32],
      ["set-gmake-probe", (st.toolchains || {}).mspm0],
      ["set-ccs-sdk-probe", (st.ccs_tools || {}).sdk],
      ["set-ccs-compiler-probe", (st.ccs_tools || {}).compiler],
      ["set-ccs-sysconfig-probe", (st.ccs_tools || {}).sysconfig],
    ];
    for (const [spanId, entry] of map) {
      const el = $(spanId);
      if (el) el.textContent = toolchainProbeText(entry);
    }
  } catch (e) { /* 探测失败静默 */ }
}

// 体检行「去设置填」跳转（工单 ux-walkthrough-02/06）：展开对应折叠区 →
// 切设置页签 → 聚焦输入框；切页签原语经 goto-nav.js（与 nav-jump 同源，
// 无「settings 不 import 本模块」的回边问题）。
function bindEnvJumps(box) {
  box.querySelectorAll(".env-jump").forEach((b) =>
    b.addEventListener("click", () => {
      if (b.dataset.envCollapse) expandSettingsCollapse(b.dataset.envCollapse);
      gotoNavTab("settings", b.dataset.envJump);
    }));
}

// 视觉服务下拉（工单 vision-provider-switch/01）：一键切换 DeepSeek / 智谱
// 预设，自动填 base_url 与模型；切 DeepSeek 清空 key（防显式 key 优先把智谱
// key 发给 DeepSeek），切智谱回填已存掩码（PUT 掩码 → 后端沿用旧值）。
let visionZhipuMask = "";
let visionApplyingPreset = false;
const VISION_PRESETS = {
  deepseek: { base: "https://api.deepseek.com", model: "deepseek-v4-flash-vision-exp" },
  zhipu: { base: "https://open.bigmodel.cn/api/paas/v4", model: "glm-4.6v-flash" },
};
const VISION_HINTS = {
  deepseek: "DeepSeek 官方视觉模型，与主 LLM 同 key 同价；key 留空自动复用主 key，零额外配置。",
  zhipu: "智谱 GLM-4.6V-Flash 视觉通道；key 自动沿用已保存的智谱 key（掩码不变），留空则需自行填写。",
  custom: "其它 OpenAI 兼容视觉服务须自备 key；主 key 只在 DeepSeek 官方端点时复用，绝不外发其它服务商。",
};
function syncVisionProviderFromFields() {
  // 按 base_url 推断当前模式：bigmodel.cn → 智谱；api.deepseek.com 或空
  // （空 = 回落默认 DeepSeek）→ DeepSeek；其它 → 自定义。只动下拉与提示，
  // 不覆盖用户已存字段。
  const base = ($("set-vision-base-url").value || "").trim().toLowerCase();
  let mode = "custom";
  if (!base || base.includes("api.deepseek.com")) mode = "deepseek";
  else if (base.includes("bigmodel.cn")) mode = "zhipu";
  $("set-vision-provider").value = mode;
  $("vision-provider-hint").textContent = VISION_HINTS[mode];
}
function applyVisionPreset(mode) {
  visionApplyingPreset = true;
  try {
    if (mode === "deepseek") {
      $("set-vision-base-url").value = VISION_PRESETS.deepseek.base;
      $("set-vision-model").value = VISION_PRESETS.deepseek.model;
      $("set-vision-api-key").value = "";   // 安全必需：显式 key 优先，不清空会把旧智谱 key 发给 DeepSeek
      $("set-vision-api-key").placeholder = "留空 = 复用主 DeepSeek key";
    } else if (mode === "zhipu") {
      $("set-vision-base-url").value = VISION_PRESETS.zhipu.base;
      $("set-vision-model").value = VISION_PRESETS.zhipu.model;
      $("set-vision-api-key").value = visionZhipuMask || "";
      $("set-vision-api-key").placeholder = "智谱开放平台 API key";
    } else {
      $("set-vision-api-key").placeholder = "自定义服务 API key";
    }
  } finally {
    visionApplyingPreset = false;
  }
  $("vision-provider-hint").textContent = VISION_HINTS[mode];
}
$("set-vision-provider").addEventListener("change", () =>
  applyVisionPreset($("set-vision-provider").value));
// 手动改 base_url / 模型与当前预设不符 → 自动转「自定义」（key 手改不触发；
// 预设填充期间用 visionApplyingPreset 屏蔽，避免与切换互相覆盖）
["set-vision-base-url", "set-vision-model"].forEach((id) => {
  $(id).addEventListener("input", () => {
    if (visionApplyingPreset) return;
    const mode = $("set-vision-provider").value;
    const pres = VISION_PRESETS[mode];
    const key = id === "set-vision-base-url" ? "base" : "model";
    if (pres && $(id).value.trim() !== pres[key]) {
      $("set-vision-provider").value = "custom";
      $("vision-provider-hint").textContent = VISION_HINTS.custom;
    }
  });
});

// 视觉通道自检（工单 vision-selfcheck/01）：用当前填写参数（含"key 留空 =
// 复用主 key"装配逻辑，后端 _resolve_vision 同源）真实调用一次视觉模型；
// 成功绿字回显模型/耗时，失败红字显示后端中文原因（handle() 统一提取）。
$("btn-vision-selfcheck").addEventListener("click", async () => {
  const status = $("vision-selfcheck-status");
  status.className = "muted";
  status.textContent = "正在调用视觉模型…";
  try {
    const data = await apiPost("/api/vision/selfcheck");
    status.className = "ok";
    status.textContent = "✓ 视觉通道正常（模型 " + esc(data.model || "?") + "，耗时 "
      + (data.elapsed_ms ?? "?") + "ms）：" + esc(data.message || "");
  } catch (e) {
    status.className = "error";
    status.textContent = "✕ 自检失败：" + e.message;
  }
});

// 环境体检（工单 env-check-center/01）：静态探测 + 文本/视觉双通道真实自检。
// envRowHTML / envChannelHTML / envCheckStatusHTML / ENV_BADGE_GLYPH 已迁至
// static/js/fx/env.js（本模块顶部 import，含模块级常量）
async function envCheckRun() {
  const btn = $("btn-env-check");
  const box = $("env-check-results");
  if (!btn || !box || btn.disabled) return;
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>体检中…';
  let status;
  try {
    status = await apiGet("/api/env/status");
  } catch (e) {
    box.innerHTML = '<div class="error">体检失败：' + esc(e.message) + "</div>";
    btn.disabled = false;
    btn.textContent = "一键体检";
    return;
  }
  box.innerHTML = envCheckStatusHTML(status, "pending", "pending");
  bindEnvJumps(box);
  const [textRes, visionRes] = await Promise.allSettled([
    apiPost("/api/llm/selfcheck"),
    apiPost("/api/vision/selfcheck"),
  ]);
  const settleCh = (r) => r.status === "fulfilled"
    ? { ok: true, data: r.value }
    : { ok: false, msg: (r.reason && r.reason.message) || "请求失败" };
  box.innerHTML = envCheckStatusHTML(status, settleCh(textRes), settleCh(visionRes));
  bindEnvJumps(box);
  btn.disabled = false;
  btn.textContent = "一键体检";
}
$("btn-env-check").addEventListener("click", envCheckRun);

// 本地模型下拉联动：选「关闭」→ 清空 base_url（本地路由关闭）；选模型 → 补默认端点
$("set-local-llm-model").addEventListener("change", () => {
  const urlEl = $("set-local-llm-base-url");
  if ($("set-local-llm-model").value === "") {
    urlEl.value = "";
  } else if (!urlEl.value.trim()) {
    urlEl.value = "http://localhost:11434/v1";
  }
});

/** DeepSeek Flash 官方价格参考表渲染（工单 llm-cost-control 更新）：
 * 数据单源 = 后端 DEEPSEEK_FLASH_PRICE_REFERENCE（/api/settings
 * price_reference），前端只渲染不硬编码；缺数据 = 面板隐藏。
 * 同时缓存到 window.__priceRef 供 periodPlaceholders 用（placeholder =
 * 所选时段的官方价）。 */
export function renderPriceReference(ref) {
  const rows = $("price-ref-rows");
  if (!ref || !rows) return;
  rows.innerHTML = "";   // 重绘前清空：loadSettings 每次进设置页都调用，不清空会累积重复
  window.__priceRef = ref;
  const fmt = (v) => (v ?? "-") + " 元";
  const row = (label, entry) => {
    const tr = document.createElement("tr");
    tr.innerHTML = "<td style='padding:4px 8px;border-bottom:1px solid var(--border,#333)'>" + esc(label) + "</td>"
      + "<td style='padding:4px 8px;border-bottom:1px solid var(--border,#333)'>" + fmt(entry.off_peak) + "</td>"
      + "<td style='padding:4px 8px;border-bottom:1px solid var(--border,#333)'>" + fmt(entry.peak) + "</td>";
    rows.appendChild(tr);
  };
  row("输入（缓存命中）", ref.input_cache_hit || {});
  row("输入（缓存未命中）", ref.input_cache_miss || {});
  row("输出", ref.output || {});
  const foot = $("price-ref-foot");
  if (foot) {
    const concur = ref.concurrent_connections;
    const asOf = ref.as_of ? "（" + esc(ref.as_of) + " 官方定价）" : "";
    foot.textContent = concur
      ? "单服务实例最大并发连接数：" + concur + " " + asOf
      : asOf;
  }
}

/** 输入框 placeholder = 所选时段的官方价（留空 = 按此时段基准价计费）。 */
function periodPlaceholders(period) {
  const ref = window.__priceRef || {};
  const set = (id, entry) => {
    const v = (entry || {})[period];
    if (v !== undefined && $(id)) $(id).placeholder = String(v);
  };
  set("set-ds-in-hit", ref.input_cache_hit);
  set("set-ds-in", ref.input_cache_miss);
  set("set-ds-out", ref.output);
}

document.querySelectorAll('input[name="price-period"]').forEach((radio) =>
  radio.addEventListener("change", () => periodPlaceholders(radio.value)));

function collectLlmPrices() {
  // 每个 provider 的框全留空 = 不覆盖（维持当前/默认）；任一填写则按填的值
  // （未填的沿用当前生效值）→ 空对象 = 后端恢复内置默认。
  // DeepSeek 输入分缓存命中/未命中两档（官方差价 ~30 倍）；local 无缓存
  // 概念：输入框值同时写命中/未命中两档。
  const llmPrices = {};
  const ds = {};
  const curDs = llmPricesDefaults.deepseek || { input_cache_hit_per_million: 0, input_cache_miss_per_million: 0, output_per_million: 0 };
  const hit = $("set-ds-in-hit").value.trim(), miss = $("set-ds-in").value.trim(), out = $("set-ds-out").value.trim();
  if (hit || miss || out) {
    ds.input_cache_hit_per_million = hit ? parseFloat(hit) : curDs.input_cache_hit_per_million;
    ds.input_cache_miss_per_million = miss ? parseFloat(miss) : curDs.input_cache_miss_per_million;
    ds.output_per_million = out ? parseFloat(out) : curDs.output_per_million;
    llmPrices.deepseek = ds;
  }
  const i = $("set-local-in").value.trim(), o = $("set-local-out").value.trim();
  if (i || o) {
    const cur = (llmPricesDefaults.local || { input_cache_miss_per_million: 0, output_per_million: 0 });
    const localIn = i ? parseFloat(i) : cur.input_cache_miss_per_million;
    llmPrices.local = {
      input_cache_hit_per_million: localIn,
      input_cache_miss_per_million: localIn,
      output_per_million: o ? parseFloat(o) : cur.output_per_million,
    };
  }
  return llmPrices;
}

// ---------------------------------------------------------------------------
// 保存：sticky 保存条 + 底部按钮共用（工单 ux-walkthrough-02/04）——
// 成功后 toast（任意位置可见）+ 原有页内绿字保留；保存中禁用双按钮防连点；
// 任意字段改动 → 顶部「有未保存的修改」提示。
// ---------------------------------------------------------------------------
let settingsSaving = false;
let settingsDirty = false;
function updateSettingsDirtyUI() {
  const hint = $("settings-dirty-hint");
  if (hint) hint.classList.toggle("hidden", !settingsDirty);
}
async function saveSettings() {
  if (settingsSaving) return false;
  settingsSaving = true;
  const btn = $("btn-save-settings");
  const sticky = $("btn-save-settings-sticky");
  if (btn) btn.disabled = true;
  if (sticky) sticky.disabled = true;
  $("settings-msg").textContent = "";
  try {
    await apiPut("/api/settings", {
      base_url: $("set-base-url").value.trim(),
      api_key: $("set-api-key").value.trim(),
      model: $("set-model").value.trim(),
      module_library_dir: $("set-lib-dir").value.trim(),
      masters_dir: $("set-masters-dir").value.trim(),
      uv4_path: $("set-uv4-path").value.trim(),
      gmake_path: $("set-gmake-path").value.trim(),
      ccs_sdk_dir: $("set-ccs-sdk-dir").value.trim(),
      ccs_compiler_dir: $("set-ccs-compiler-dir").value.trim(),
      ccs_sysconfig_cli: $("set-ccs-sysconfig-cli").value.trim(),
      openocd_path: $("set-openocd-path").value.trim(),
      stflash_path: $("set-stflash-path").value.trim(),
      dslite_path: $("set-dslite-path").value.trim(),
      local_llm_base_url: $("set-local-llm-base-url").value.trim(),
      local_llm_model: $("set-local-llm-model").value.trim(),
      vision_base_url: $("set-vision-base-url").value.trim(),
      vision_api_key: $("set-vision-api-key").value.trim(),
      vision_model: $("set-vision-model").value.trim(),
      vision_detail_qa: $("set-vision-detail-qa").checked,
      llm_prices: collectLlmPrices(),
      llm_price_period: $("period-peak").checked ? "peak" : "off_peak",
      recommend_cache_enabled: $("set-recommend-cache").checked,
      recommend_max_rounds: parseInt($("set-recommend-rounds").value, 10) || 4,
    });
  } catch (e) {
    $("settings-msg").classList.remove("ok");
    $("settings-msg").textContent = e.message;
    toast("error", "设置保存失败：" + e.message);
    return false;
  } finally {
    settingsSaving = false;
    if (btn) btn.disabled = false;
    if (sticky) sticky.disabled = false;
  }
  // 保存已成功：刷新放在错误路径之外——刷新失败（状态可能滞后）不误报
  // 「保存失败」，保存本身已生效（工单 ux-walkthrough-02/04 评审整改）
  $("settings-msg").classList.add("ok");
  $("settings-msg").textContent = "已保存，立即生效。";
  toast("ok", "设置已保存，立即生效。");
  settingsDirty = false;
  updateSettingsDirtyUI();
  try {
    await refreshState();
    loadSettings();
  } catch (e) { /* 刷新失败静默：下轮操作会重新取状态 */ }
  return true;
}
$("btn-save-settings").addEventListener("click", () => saveSettings());
if ($("btn-save-settings-sticky")) {
  $("btn-save-settings-sticky").addEventListener("click", () => saveSettings());
}
// 设置表单任意改动 → 未保存提示（loadSettings 程序赋值不触发 input/change）
$("tab-settings").addEventListener("input", () => { settingsDirty = true; updateSettingsDirtyUI(); });
$("tab-settings").addEventListener("change", () => { settingsDirty = true; updateSettingsDirtyUI(); });

// 保存并连接（工单 ux-walkthrough-02/04）：保存当前设置 → 真实调用校验连接；
// key 未填给明确提示（不调后端保存，避免把空 key 覆盖掉已有配置）。
// 保存中禁用自身按钮防连点（工单 04 验收「保存中禁用按钮」对两处按钮一致）。
$("btn-save-connect").addEventListener("click", async () => {
  const msg = $("save-connect-msg");
  const btn = $("btn-save-connect");
  const key = $("set-api-key").value.trim();
  msg.classList.remove("ok", "error");
  if (!key) {
    msg.textContent = "请先填写 API key（留空 = 保持已保存的 key 不变，不会覆盖）";
    msg.classList.add("error");
    toast("error", "请先填写 API key");
    $("set-api-key").focus();
    return;
  }
  if (settingsSaving) return;  // 首个保存仍在途：静默忽略连点（防误导性「保存失败」）
  btn.disabled = true;
  msg.textContent = "正在保存并验证连接…";
  const saved = await saveSettings();
  if (!saved) {
    msg.textContent = "保存失败，请按上方提示修正后重试";
    msg.classList.add("error");
    btn.disabled = false;
    return;
  }
  msg.textContent = "已保存，正在验证连接…";
  try {
    const data = await apiPost("/api/llm/selfcheck");
    // 后端回 {ok, model, elapsed_ms, reply}——真实字段回显（工单 04 评审整改）
    const detail = [];
    if (data && data.model) detail.push("模型 " + data.model);
    if (data && data.elapsed_ms != null) detail.push("耗时 " + data.elapsed_ms + "ms");
    const tail = data && data.reply ? "：" + data.reply : "";
    msg.textContent = "✓ " + (detail.length ? "连接成功（" + detail.join("，") + "）" : "连接成功，AI 功能可用") + tail;
    msg.classList.add("ok");
    toast("ok", "AI API 连接成功");
  } catch (e) {
    msg.textContent = "✕ 连接失败：" + e.message;
    msg.classList.add("error");
    toast("error", "AI API 连接失败：" + e.message);
  } finally {
    btn.disabled = false;
  }
});

// 保存后重载（原 host 函数，唯一调用点 = 保存按钮，随本簇迁入）：
// state / modules 重拉 + 工具链可用性重算（经接缝写宿主 toolchains +
// renderToolchainStatus——16 迁出后改静态 import）+ 平台卡 / 模块池重渲染。
async function refreshState() {
  setState(await apiGet("/api/state"));
  $("gen-banner").classList.toggle("hidden", !!state.api_configured);
  // 未配置时模块库读不到：保留旧列表（可能为空），不能让渲染中断
  try { state.modules = await apiGet("/api/modules"); }
  catch (e) { state.modules = state.modules || []; }
  // 工具链可用性（工单 autocompile-loop/01）：一键编译修复按钮的置灰依据
  settingsDeps.applyToolchains(state.toolchains || { stm32: false, mspm0: false });
  renderPlatforms();
  renderModulePool();
}

// ---------------------------------------------------------------------------
// 最近 LLM 工作流（工单 llm-observability-dashboard/03）：只读内存仪表盘
// 纯函数已迁至 static/js/fx/workflow.js（阶段 2 工单 01）：wfNum / formatWorkflowUsage /
// formatWorkflowCost / formatWorkflowSummary / formatWorkflowCall；以下为渲染胶水。
// ---------------------------------------------------------------------------
function renderRecentWorkflows(data) {
  const el = $("recent-workflows");
  const workflows = (data && data.workflows) || [];
  if (!workflows.length) {
    el.innerHTML = '<div class="empty-state"><div class="es-icon">⚙️</div><div class="es-title">暂无已完成的工作流</div><div class="es-hint">运行一次推荐 / 骨架 / 修复 / 提炼后，这里会出现记录。</div></div>';
    return;
  }
  el.innerHTML = workflows.map((w) => {
    const calls = (w.calls || []).map((c) => {
      const line = formatWorkflowCall(c);
      return '<div class="call-row" title="' + esc(line) + '">' + esc(line) + "</div>";
    }).join("");
    const statusText = w.status === "error" ? "失败" : "成功";
    const statusCls = w.status === "error" ? "wf-status-error" : "wf-status-ok";
    return '<div class="recent-wf-summary">'
      + '<div><span class="wf-name">' + esc(w.workflow_name || "unknown") + "</span>"
      + ' <span class="' + statusCls + '">' + statusText + "</span>"
      + ' <span class="muted">' + esc(w.workflow_id) + "</span></div>"
      + '<div class="muted">' + esc(formatWorkflowSummary(w)) + "</div>"
      + (calls ? '<div class="recent-wf-calls">' + calls + "</div>" : "")
      + "</div>";
  }).join("");
}

export async function loadRecentWorkflows() {
  const el = $("recent-workflows");
  try {
    renderRecentWorkflows(await apiGet("/api/llm-workflows/recent"));
  } catch (e) {
    el.innerHTML = '<div class="muted">读取失败：' + esc(e.message || String(e)) + "</div>";
  }
}

$("btn-refresh-recent-wf").addEventListener("click", loadRecentWorkflows);

// ---------------------------------------------------------------------------
// 重置本地记录（工单 reset-local-records/02）：换题前一键恢复「第一次打开」
// 的状态。确认弹窗（confirmModal）→ 清理清单单源 fx/reset.js 判定 →
// 前端 localStorage 直清（同源页面）→ 服务端 POST /api/reset-records
// （recent 列表 + AI 推荐缓存）→ 结果汇总。
// ---------------------------------------------------------------------------
$("btn-reset-records").addEventListener("click", async () => {
  const msg = $("reset-records-msg");
  msg.className = "muted";
  msg.textContent = "";
  const ok = await confirmModal({
    title: "清空本地记录？",
    message: "将清除：任务自检勾选、题面草稿、评分核对勾选、购买决策记忆、"
      + "最近工程列表与 AI 推荐缓存。API 配置、主题与缩放等界面偏好、"
      + "磁盘上的工程文件不受影响。此操作不可撤销。",
    danger: true,
    confirmText: "清空本地记录",
    cancelText: "取消",
  });
  if (!ok) return;
  // 前端 localStorage 直清（fx/reset.js 判定单源：只清题相关记录）
  const localKeys = collectResettableKeys(Object.keys(localStorage));
  for (const k of localKeys) localStorage.removeItem(k);
  let result;
  try {
    result = await apiPost("/api/reset-records");
  } catch (e) {
    msg.className = "error";
    msg.textContent = "本地记录已清除（" + localKeys.length + " 项）；服务端记录清除失败："
      + esc(e.message || String(e));
    return;
  }
  const parts = [];
  if (localKeys.length) parts.push("本地记录 " + localKeys.length + " 项");
  if (result.recent_entries) parts.push("最近工程 " + result.recent_entries + " 条");
  if (result.cache_files) parts.push("推荐缓存 " + result.cache_files + " 个");
  msg.className = parts.length ? "ok" : "muted";
  msg.textContent = parts.length
    ? "已清除：" + parts.join("；") + "。"
    : "没有可清除的记录。";
});

// ---------------------------------------------------------------------------
// 设置页折叠（工单 settings-infoarch/01-03）：整卡折叠 + 默认收起次要项 +
// 状态记忆；与生成页折叠（CARD_COLLAPSE_SELECTOR）互不干扰。
// 存储：localStorage「firstep.settingsCollapse.v1」，JSON {id: collapsed}，
// 用户选择优先于默认集；解析失败按 {}。默认集单源 = SETTINGS_DEFAULT_COLLAPSED
// ---------------------------------------------------------------------------
// 折叠元状态（工单 flash-guide-settings/03 整改：原为 initSettingsCollapse
// 闭包局部 state 与 localStorage 双副本——expandSettingsCollapse 旁路只写盘，
// 后续 toggle 其他卡会把陈旧闭包 state 整包写回，展开被反向清除。提升为模块
// 级内存单源：init 从 storage 播种，toggle / expand / 总开关三处读写同一对象，
// 写盘 = 持久化该对象。会话内唯一真相）
const settingsCollapseState = {};

function saveSettingsCollapse(state) {
  try { localStorage.setItem(SETTINGS_COLLAPSE_KEY, JSON.stringify(state)); }
  catch (e) { /* 忽略，沿主题/用量先例 */ }
}

/** 折叠总开关标签重算（单源：initSettingsCollapse 与 expandSettingsCollapse
 * 共用——工单 flash-guide-settings/03 收敛，原为 initSettingsCollapse 私有闭包）。 */
function syncSettingsMasterLabel(items) {
  const master = $("btn-settings-collapse-all");
  if (!master) return;
  const allCollapsed = items.every((c) => c.classList.contains("collapsed"));
  master.textContent = settingsMasterLabel(allCollapsed);
}

/** 展开指定设置卡片（工单 flash-guide-settings/03 修复）：烧录工具输入框藏在
 * 默认折叠的「工具链」卡内（SETTINGS_DEFAULT_COLLAPSED 含 toolchain）——「去
 * 设置页配置」只切 tab 时用户看不到输入框，误以为没跳转。展开 + 落盘用户
 * 选择 + 刷新总开关标签；已展开 = 无操作。 */
export function expandSettingsCollapse(collapseId) {
  const card = document.querySelector('[data-collapse-id="' + collapseId + '"]');
  if (!card || !card.classList.contains("collapsed")) return;
  applySettingsCollapseState(card, false);
  // 内存单源（settingsCollapseState）：若 init 尚未播种（极端时序），先补播
  if (!Object.keys(settingsCollapseState).length) {
    Object.assign(settingsCollapseState, parseSettingsCollapse(localStorage.getItem(SETTINGS_COLLAPSE_KEY)));
  }
  settingsCollapseState[collapseId] = false;
  saveSettingsCollapse(settingsCollapseState);
  const section = $("tab-settings");
  if (section) {
    syncSettingsMasterLabel(Array.from(section.querySelectorAll("[data-collapse-id]")));
  }
}

export function initSettingsCollapse() {
  const section = $("tab-settings");
  if (!section) return;
  const items = Array.from(section.querySelectorAll("[data-collapse-id]"));
  if (!items.length) return;
  const stored = parseSettingsCollapse(localStorage.getItem(SETTINGS_COLLAPSE_KEY));
  // 内存单源播种：清空后从盘面读入（模块级 settingsCollapseState，见 :420 注释）
  for (const k of Object.keys(settingsCollapseState)) delete settingsCollapseState[k];
  Object.assign(settingsCollapseState, stored);
  // 单元素切换（计费头 / ▾ / 标题三处共用）：toggle → 落 state → 同步按钮 →
  // 写盘 → 刷新总开关标签（标签重算 = 模块级 syncSettingsMasterLabel）
  const toggleSettingsCollapse = (c) => {
    const next = c.classList.toggle("collapsed");
    settingsCollapseState[c.dataset.collapseId] = next;
    applySettingsCollapseState(c, next);
    saveSettingsCollapse(settingsCollapseState);
    syncSettingsMasterLabel(items);
  };
  for (const c of items) {
    const id = c.dataset.collapseId;
    const collapsed = effectiveCollapsed(id, stored);
    settingsCollapseState[id] = collapsed;
    const head = settingsSectionHead(c);
    if (head) {   // 计费小节：头按钮即 toggle（无 h2）
      applySettingsCollapseState(c, collapsed);
      head.addEventListener("click", () => toggleSettingsCollapse(c));
      continue;
    }
    const h2 = c.querySelector("h2");
    if (!h2) continue;   // 保存设置卡无 h2 → 不可折叠
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "card-collapse";
    btn.textContent = "▾";
    h2.appendChild(btn);   // 先挂载再应用（工单 settings-infoarch/02）：apply 经
                           // querySelector 找按钮同步初始 title/aria
    applySettingsCollapseState(c, collapsed);
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      toggleSettingsCollapse(c);
    });
    h2.addEventListener("click", (e) => {
      if (e.target.closest(".card-collapse")) return;
      toggleSettingsCollapse(c);
    });
  }
  const master = $("btn-settings-collapse-all");
  if (master) {
    master.addEventListener("click", () => {
      const target = !items.every((c) => c.classList.contains("collapsed"));
      for (const c of items) {
        const id = c.dataset.collapseId;
        settingsCollapseState[id] = target;
        applySettingsCollapseState(c, target);
      }
      saveSettingsCollapse(settingsCollapseState);
      syncSettingsMasterLabel(items);
    });
    syncSettingsMasterLabel(items);
  }
}
