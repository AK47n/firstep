// ui/generate-pins.js — 生成页 · 实例配置 + 引脚板图（阶段 2 工单 13，源自
// index.html 2313-3204 两节：6.5 多实例配置 + 7 引脚配置）
//
// DOM 胶水全量迁入：实例增删 / 显示名 / 颜色 / 板图选脚（instList /
// renderInstanceConfig / instanceBlock / instanceRow / addInstance / delInstance /
// pickInstancePin / clearInstancePin / assignInstancePin）+ 引脚板图（renderPinCard /
// loadPinBoard / renderPinLegend / renderPinOverviewLegend / renderPinBoard / svgPin /
// renderPinRoles / unbindRole / bindRole / showPinMenu）+ 总览着色 / 能力判定 / 自动配置。
// 纯件在 fx/*.js（module.js：multiInstanceModules / instancePayload /
// ensureDefaultInstances；generate.js：collectBindings；core.js：esc）。
// 状态所有权（本模块 = 主写簇；host 经顶部 import 活绑定只读，写经导出函数）：
//   instances / instancePinTarget / pinBoard / pinBoardError / pinBindings /
//   pinUnbound / pinShowOptional / pinHighlight / pinRotation / pinOverview +
//   常量 LED_COLORS / PIN_TYPE_STYLE / PIN_TYPE_ZH / MODULE_COLORS。
// host → 本簇：顶部 import 代理（instances / pinBindings / pinUnbound / pinRoles /
//   renderInstanceConfig / renderPinCard / loadPinBoard——generateMain /
//   renderGenerateSuccess / btn-generate / handoffPinLines 读点与启动占位渲染）
//   与 setClusterDeps 注册改挂本簇导出（renderPinCard / renderInstanceConfig /
//   loadPinBoard / resetPinState / resetInstances / clearInstanceTarget /
//   backfillInstances——推荐簇 A 的跨簇服务入口：工单 12 的 host 薄胶水接缝 →
//   本票迁入本体，见 index.html 启动区）。
// 顶层 addEventListener（Esc 取消选脚 / btn-pin-reset / btn-pin-rotate /
// btn-pin-overview / btn-pin-auto）在 import 时绑定（module 脚本延迟执行，DOM 已就绪）。
import { $, apiGet, apiPost, toast, state } from "/js/app.js";
import { esc } from "/js/fx/core.js";
import { confirmModal } from "/js/ui/confirm.js";
import { pinResetConfirmMessage } from "/js/fx/danger.js";  // 还原默认确认文案（工单 ux-walkthrough-02/01）
import { multiInstanceModules, ensureDefaultInstances, instanceGapCount } from "/js/fx/module.js";
import { collectBindings, pinShareClass } from "/js/fx/generate.js";  // pinShareClass = 同脚多角色 共享/冲突 判据（工单 pin-share-rule/01，与后端 _shared_groups 同口径）
import { syncStep7, markSubStep, refreshStepNav } from "/js/ui/step-state.js";
import { chosenPlatform, expanded, selectedSlugs } from "/js/ui/generate-recommend.js";

// ---- 全局状态：多实例 + 引脚板图（随簇；host 经 import 活绑定读） ----
export let instances = {};               // 多实例配置（工单 04）：{ slug: [{name, variant, pin}] }
export let instancePinTarget = null;     // 正在从板图选引脚的实例 { slug, index }（null = 非选脚模式）

// ---------------------------------------------------------------------------
// 生成页：6.5 多实例配置（工单 module-multi-instance/04）
// manifest.multi_instance 非空的模块（当前只有 led）显示实例列表：每实例可改
// 显示名 / 选颜色（red/yellow/green，可重复）/ 绑引脚（复用板图，空 = 自动
// 分配）；添加 / 删除实例，上限 = multi_instance.max，超限禁用并提示。
// instances 装配进 /api/skeleton 与 /api/generate 的 instances 字段（缺省 =
// 不发 = 旧行为单默认实例）。
// ---------------------------------------------------------------------------

export const LED_COLORS = [["red", "红"], ["yellow", "黄"], ["green", "绿"], ["", "无颜色（通用编号）"]];

// 多实例变体下拉选项（工单 key-multi-instance/06）：后端 expand 端点按策略表
// 投影带 variants（[{value, label}]，token 序单源）——led = 红/黄/绿、
// key = 启动/停止/模式/设置；旧数据（无 variants 字段）回退 LED_COLORS。
function variantOptionsOf(slug) {
  const m = expanded.find((x) => x.slug === slug);
  const variants = m && m.multi_instance && m.multi_instance.variants;
  if (variants && variants.length) return variants;
  return LED_COLORS.map(([value, label]) => ({ value, label }));
}

// 多实例选脚的可用能力（工单 key-multi-instance/06）：优先消费后端 expand 端点
// 透传的 multi_instance.pin_capability（展开策略表权威投影）；旧数据回退按模块
// 首 pin 角色类型推导（led = gpio_out、key = gpio_in），再缺省 gpio_out 兜底。
function instancePinCapability(slug) {
  const m = expanded.find((x) => x.slug === slug);
  const cap = m && m.multi_instance && m.multi_instance.pin_capability;
  if (cap) return cap;
  const pins = m && m.platforms && m.platforms[chosenPlatform] && m.platforms[chosenPlatform].pins;
  const type = pins && pins[0] && pins[0].type;
  return type === "gpio_in" ? "gpio_in" : "gpio_out";
}

// 已迁至 static/js/fx/module.js（工单 06）：multiInstanceModules（迁入后参数化 = expanded）。

function instList(slug) {
  return instances[slug] || (instances[slug] = []);
}

// 已迁至 static/js/fx/module.js（工单 06）：instancePayload（迁入后参数化 = expanded, instances）。

// 已迁至 static/js/fx/module.js（工单 06）：ensureDefaultInstances（迁入后参数化 = expanded, instances）。

// 6.5 多实例卡与步骤系统联动（工单 ux-walkthrough-02/02）：步骤 6 卡顶部
// 「还差 N 个实例」徽章 + 导航 6.5 点完成态；导航按卡片可见性重建。
function syncInstanceGap() {
  const mods = multiInstanceModules(expanded);
  const gap = instanceGapCount(expanded, instances);
  const badge = $("instance-gap-badge");
  if (badge) {
    if (mods.length && gap > 0) {
      badge.textContent = "还差 " + gap + " 个实例";
      badge.classList.remove("hidden");
    } else {
      badge.classList.add("hidden");
    }
  }
  refreshStepNav();
  markSubStep("6.5", mods.length > 0 && gap === 0);
  // 总览 6.5 chip 随卡片显隐（无多实例模块时不出现在总览条）
  const chip = document.querySelector('.ov-chip[data-step="6.5"]');
  if (chip) chip.classList.toggle("hidden", !mods.length);
}

function renderInstanceConfig() {
  const card = $("card-instance-config");
  // 清掉已不在最终工程集内模块的实例清单（模块被移除后不残留；expanded
  // 未展开时按 selectedSlugs 兜底 = 旧行为——推荐回填的实例清单不被误删）
  const keep = new Set(expanded.length ? expanded.map((m) => m.slug) : selectedSlugs);
  for (const slug of Object.keys(instances)) {
    if (!keep.has(slug)) delete instances[slug];
  }
  ensureDefaultInstances(expanded, instances);  // 首次呈现预填平台默认（键不存在才填）
  // 选脚目标失效守卫：slug 已不在选择集 / 实例号越界 → 清掉（防陈旧高亮）
  if (instancePinTarget) {
    const targetList = instances[instancePinTarget.slug] || [];
    if (!keep.has(instancePinTarget.slug) || instancePinTarget.index >= targetList.length) {
      instancePinTarget = null;
    }
  }
  const mods = multiInstanceModules(expanded);
  if (!mods.length) { card.classList.add("hidden"); syncInstanceGap(); return; }
  card.classList.remove("hidden");

  const hint = $("instance-pin-hint");
  if (instancePinTarget) {
    const targetInst = instances[instancePinTarget.slug][instancePinTarget.index];
    const cap = instancePinCapability(instancePinTarget.slug);
    hint.textContent = "正在为「" + (targetInst && targetInst.name ? targetInst.name : "未命名实例") + "」选引脚：点击板图上的 IO 引脚绑定（" + (cap === "gpio_in" ? "gpio_in 输入" : "gpio_out 输出") + " 能力）；再次点「选引脚」或按 Esc 取消。";
    hint.classList.remove("hidden");
  } else {
    hint.classList.add("hidden");
  }

  const box = $("instance-config");
  box.innerHTML = mods.map((m) => instanceBlock(m)).join("");
  box.querySelectorAll("[data-field]").forEach((el) => {
    el.addEventListener("input", () => {
      const list = instList(el.dataset.slug);
      list[+el.dataset.index][el.dataset.field] = el.value;
    });
  });
  box.querySelectorAll("[data-pick]").forEach((b) =>
    b.addEventListener("click", () => pickInstancePin(b.dataset.slug, +b.dataset.index)));
  box.querySelectorAll("[data-clear-pin]").forEach((b) =>
    b.addEventListener("click", () => clearInstancePin(b.dataset.slug, +b.dataset.index)));
  box.querySelectorAll("[data-del]").forEach((b) =>
    b.addEventListener("click", () => delInstance(b.dataset.slug, +b.dataset.index)));
  box.querySelectorAll("[data-add]").forEach((b) =>
    b.addEventListener("click", () => addInstance(b.dataset.add)));
  syncInstanceGap();
}

function instanceBlock(m) {
  const slug = m.slug;
  const max = m.multi_instance.max;
  const list = instList(slug);
  const atMax = list.length >= max;
  const rows = list.map((inst, i) => instanceRow(slug, i, inst)).join("");
  return `
    <div class="instance-mod">
      <div class="instance-head">
        <strong style="font-family:var(--mono)">${esc(slug)}</strong>
        <span class="muted">已配 ${list.length} / ${max} 个实例 · 变体 = ${esc(m.multi_instance.variant)}</span>
      </div>
      ${rows}
      <div class="instance-actions">
        <button data-add="${esc(slug)}" ${atMax ? "disabled" : ""}>添加实例</button>
        ${atMax ? `<span class="muted" style="color:var(--warn)">已达上限 ${max}</span>` : ""}
        ${list.length ? "" : `<span class="muted">（未配置实例 = 默认单实例）</span>`}
      </div>
    </div>`;
}

function instanceRow(slug, i, inst) {
  const picking = instancePinTarget && instancePinTarget.slug === slug && instancePinTarget.index === i;
  const m = expanded.find((x) => x.slug === slug);
  const variants = m && m.multi_instance && m.multi_instance.variants;
  // 变体 = 自由文本 + 建议（工单 06 验收「自由文本」）：<input list> 组合框；
  // 建议 = 后端策略表投影（led = 红/黄/绿、key = 启动/停止/模式/设置）；
  // 旧数据（无 variants）回退 LED_COLORS（已含空选项，不再追加）
  const opts = variants && variants.length
    ? variants
    : LED_COLORS.map(([value, label]) => ({ value, label }));
  const listId = "variant-opts-" + esc(slug);
  const datalistItems = opts.map((v) =>
    `<option value="${esc(v.value)}">${esc(v.label)}</option>`).join("")
    + (opts.some((v) => v.value === "") ? "" : '<option value="">通用编号</option>');
  const colors = `<input list="${listId}" data-field="variant" data-slug="${esc(slug)}" data-index="${i}" value="${esc(inst.variant)}" placeholder="内置变体或留空">`
    + `<datalist id="${listId}">${datalistItems}</datalist>`;
  const pinShow = inst.pin
    ? `<span style="font-family:var(--mono);color:var(--accent)">${esc(inst.pin)}</span>`
    : '<span class="muted">自动分配</span>';
  return `
    <div class="instance-row${picking ? " instance-picking" : ""}">
      <span class="muted" style="font-family:var(--mono)">#${i + 1}</span>
      <input type="text" data-field="name" data-slug="${esc(slug)}" data-index="${i}" value="${esc(inst.name)}" placeholder="显示名（自由中文）">
      ${colors}
      <span class="instance-pin">
        ${pinShow}
        <button data-pick="1" data-slug="${esc(slug)}" data-index="${i}">${picking ? "取消" : "选引脚"}</button>
        ${inst.pin ? `<button data-clear-pin="1" data-slug="${esc(slug)}" data-index="${i}">改回自动</button>` : ""}
      </span>
      <button class="danger" data-del="1" data-slug="${esc(slug)}" data-index="${i}">删除</button>
    </div>`;
}

function addInstance(slug) {
  const m = expanded.find((x) => x.slug === slug);
  if (!m || !m.multi_instance) return;
  const list = instList(slug);
  if (list.length >= m.multi_instance.max) return;  // 按钮已禁用，双保险
  // 默认名与变体按模块（工单 key-multi-instance/06）：led = 灯 N / 内置色，
  // key = 键 N / 首个内置变体（start）；无 variants 时回退空变体 + LED_COLORS 旧行为
  const defaultName = slug === "key" ? "键 " + (list.length + 1) : "灯 " + (list.length + 1);
  const opts = variantOptionsOf(slug);
  const firstVariant = (opts[0] && opts[0].value) || "red";
  list.push({ name: defaultName, variant: firstVariant, pin: "" });
  renderInstanceConfig();
}

function delInstance(slug, index) {
  const list = instList(slug);
  list.splice(index, 1);
  if (instancePinTarget && instancePinTarget.slug === slug) instancePinTarget = null;
  renderInstanceConfig();
  renderPinCard();  // 实例清单变化 → 步骤 7 就绪判定重算（工单 ux-walkthrough-02/02）
}

function pickInstancePin(slug, index) {
  const same = instancePinTarget && instancePinTarget.slug === slug && instancePinTarget.index === index;
  instancePinTarget = same ? null : { slug, index };
  renderInstanceConfig();
  renderPinCard();
}

function clearInstancePin(slug, index) {
  instList(slug)[index].pin = "";
  if (instancePinTarget && instancePinTarget.slug === slug && instancePinTarget.index === index) {
    instancePinTarget = null;
  }
  renderInstanceConfig();
  renderPinCard();
}

function assignInstancePin(pinName) {
  if (!instancePinTarget) return;
  const t = instances[instancePinTarget.slug][instancePinTarget.index];
  t.pin = pinName;
  instancePinTarget = null;
  renderInstanceConfig();
  renderPinCard();
}

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && instancePinTarget) {
    instancePinTarget = null;
    renderInstanceConfig();
    renderPinCard();
  }
});

// ---------------------------------------------------------------------------
// 生成页：7. 引脚配置（板图点选，板级引脚配置工单 03）
// 板定义 = GET /api/boards（板图坐标/能力集单源，无静态路由——SVG 由 JSON
// 坐标内联渲染）；角色声明 = 展开结果 expanded[].platforms[platform].pins。
// 绑定只含用户动过的角色（缺省 = 默认），未配任何引脚不发 bindings 字段。
// 能力过滤与后端门禁同语义（ADR 0011 平台×类型分级）：stm32 pwm = 类型级
// （任意 pwm:* 脚可绑，实例随绑定引脚）；其余 strict-all（工单 02 口径）——
// 角色默认引脚能力 token 的**全部实例**都必须命中——motor.PWMAB_C0 默认
// PA12 有 pwm:TIMG0_C0 + pwm:TIMA0_C3 双实例，any-of 会放行仅 TIMA0_C3 的
// PA28（界面兼容但 SysConfig 路由必炸）；UI 过滤不兼容角色灰显 + 原因，
// 双实例俱有的 PA23 可绑。
// mspm0 排针满员 → v1 交互 = 替换两步换位（点已占用引脚 → 原角色红显未绑 →
// 再绑目标脚）；stm32 LED_PORT / DIP_GPIO 共享宏族绑定给提示（不拦截）。
// ---------------------------------------------------------------------------
export let pinBoard = null;             // 当前平台板定义（GET /api/boards，切平台重取）
export let pinBoardError = "";          // 板定义加载失败信息（占位文案用）
export let pinBindings = {};            // {"<slug>.<role_id>": "<PIN>"}（只含用户动过的角色）
export let pinUnbound = new Set();      // 被替换/显式解除的角色 key（红显未绑，不发字段）
export let pinShowOptional = false;     // 是否显示可选接线角色（默认只列必接）
export let pinHighlight = null;         // 清单条目高亮中的角色 key（板图候选脚）
export let pinRotation = 0;             // 板图视角旋转（每次 +90°，纯视图不影响数据）
export let pinOverview = false;         // 总览模式：按模块着色已配置引脚（必接角色 + 可选已显式绑定）

// 角色类型配色（与 CSS :root 引脚令牌一一对应：全色 / 淡化色）
export const PIN_TYPE_STYLE = {
  gpio_out: ["var(--pin-gpio)", "var(--pin-gpio-dim)"],
  gpio_in: ["var(--pin-gpio)", "var(--pin-gpio-dim)"],
  pwm: ["var(--pin-pwm)", "var(--pin-pwm-dim)"],
  enc: ["var(--pin-enc)", "var(--pin-enc-dim)"],
  uart_tx: ["var(--pin-uart)", "var(--pin-uart-dim)"],
  uart_rx: ["var(--pin-uart)", "var(--pin-uart-dim)"],
  i2c_scl: ["var(--pin-i2c)", "var(--pin-i2c-dim)"],
  i2c_sda: ["var(--pin-i2c)", "var(--pin-i2c-dim)"],
  spi_mosi: ["var(--pin-spi)", "var(--pin-spi-dim)"],
  spi_miso: ["var(--pin-spi)", "var(--pin-spi-dim)"],
  spi_sck: ["var(--pin-spi)", "var(--pin-spi-dim)"],
  spi_cs: ["var(--pin-spi)", "var(--pin-spi-dim)"],
  adc: ["var(--pin-adc)", "var(--pin-adc-dim)"],
  exti: ["var(--pin-exti)", "var(--pin-exti-dim)"],
};
export const PIN_TYPE_ZH = {
  gpio_out: "GPIO输出", gpio_in: "GPIO输入", pwm: "PWM", enc: "编码器",
  uart_tx: "UART发", uart_rx: "UART收", i2c_scl: "I2C时钟", i2c_sda: "I2C数据",
  spi_mosi: "SPI主出", spi_miso: "SPI主入", spi_sck: "SPI时钟", spi_cs: "SPI片选",
  adc: "ADC", exti: "EXTI中断",
};

// 总览模式模块配色（按角色出现顺序分配，超出循环复用）
export const MODULE_COLORS = [
  "#60a5fa", "#f87171", "#34d399", "#fbbf24", "#a78bfa", "#f472b6",
  "#22d3ee", "#a3e635", "#fb923c", "#e879f9", "#38bdf8", "#facc15",
];

function pinIndex() {
  const idx = {};
  for (const p of (pinBoard && pinBoard.pins) || []) idx[p.name] = p;
  return idx;
}

function pinRoles() {
  const roles = [];
  for (const m of expanded) {
    const entry = (m.platforms || {})[chosenPlatform];
    for (const decl of (entry && entry.pins) || []) {
      roles.push({ key: m.slug + "." + decl.id, slug: m.slug, decl });
    }
  }
  return roles;
}

// ---- 总览模式：按模块着色"已配置"引脚 ----
function moduleColorMap(roles) {
  const map = new Map();
  let i = 0;
  for (const r of roles) if (!map.has(r.slug)) map.set(r.slug, MODULE_COLORS[i++ % MODULE_COLORS.length]);
  return map;
}

// 某引脚上"已配置"的角色（总览口径）：显式绑定必含；未绑定时必接角色走默认也含，
// 可选角色走默认不算；显式解除（pinUnbound）不算。
function overviewRolesAt(pinName, roles) {
  const res = [];
  for (const r of roles) {
    if (pinUnbound.has(r.key)) continue;
    const b = pinBindings[r.key];
    if (b) { if (b === pinName) res.push(r); continue; }
    if (r.decl.required && r.decl.default === pinName) res.push(r);
  }
  return res;
}

// 总览高亮环：单模块整圈同色；多模块按模块数把圆周均分成各色弧段（2=半圆、3=三等分…）
function overviewRing(cx, cy, r, colors, width) {
  if (!colors.length) return "";
  if (colors.length === 1) {
    return `<circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="${colors[0]}" stroke-width="${width}"/>`;
  }
  const C = 2 * Math.PI * r;
  const seg = C / colors.length;
  return colors.map((color, i) =>
    `<circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="${color}" stroke-width="${width}" stroke-dasharray="${seg.toFixed(2)} ${(C - seg).toFixed(2)}" stroke-dashoffset="${(-i * seg).toFixed(2)}" transform="rotate(-90 ${cx} ${cy})"/>`
  ).join("");
}

// 总览焊孔分色扇形：多模块共享时把 r 半径圆填充分成 N 等份扇形（厚描边画法，
// 半径 r/2、描边宽 r 覆盖 [0,r] 整圆，dasharray 切 N 段）。
function overviewPie(cx, cy, r, colors, opacity) {
  if (colors.length <= 1) return "";
  const C = Math.PI * r;               // 半径 r/2 的圆周
  const seg = C / colors.length;
  return colors.map((color, i) =>
    `<circle cx="${cx}" cy="${cy}" r="${r / 2}" fill="none" stroke="${color}" stroke-width="${r}" stroke-opacity="${opacity}" stroke-dasharray="${seg.toFixed(2)} ${(C - seg).toFixed(2)}" stroke-dashoffset="${(-i * seg).toFixed(2)}" transform="rotate(-90 ${cx} ${cy})"/>`
  ).join("");
}

// ---- 能力判定（镜像后端 pin_bindings.resolve_bindings 口径：stm32 pwm /
// enc / uart 类型级 + mspm0 uart / i2c / pwm 类型级（pwm 另按角色通道过滤）+
// 其余 strict-all） ----
function pinSupports(pin, type, instance) {
  const token = instance ? type + ":" + instance : type;
  return (pin.capabilities || []).includes(token);
}

function roleInstances(decl) {
  // 角色实例 = 默认引脚能力 token 的实例（与门禁一致：板外默认无实例）
  const def = pinIndex()[decl.default];
  if (!def) return [];
  const prefix = decl.type + ":";
  return (def.capabilities || []).filter((t) => t.startsWith(prefix)).map((t) => t.slice(prefix.length));
}

function pinIsTypeLevel(decl) {
  if (chosenPlatform === "stm32") {
    return decl.type === "pwm" || decl.type === "enc" ||
      decl.type === "uart_tx" || decl.type === "uart_rx";
  }
  if (chosenPlatform === "mspm0") {
    return decl.type === "uart_tx" || decl.type === "uart_rx" ||
      decl.type === "i2c_scl" || decl.type === "i2c_sda";
  }
  return false;
}

function pwmRoleChannel(decl) {
  const m = decl.id.match(/_C(\d+)$/);
  return m ? "C" + m[1] : null;
}

function mspm0PwmAllowed(pin, decl) {
  // 全类型级（04）：有任意 pwm token 且通道匹配角色尾 _C0/_C1 的脚可选
  // （_C0N 等互补通道不算 _C0，后端同款 endswith 判据）
  const channel = pwmRoleChannel(decl);
  return (pin.capabilities || [])
    .filter((t) => t.startsWith("pwm:"))
    .map((t) => t.slice(4))
    .filter((i) => !channel || i.endsWith("_" + channel));
}

function pinCanHost(pin, decl) {
  if (!pin || pin.kind !== "io") return false;
  // 类型级（镜像后端）：任意对应类型 token 即 canHost，实例随绑定引脚；
  // mspm0 pwm 全类型级（跨族已放开，通道仍按角色尾过滤）
  if (pinIsTypeLevel(decl)) return pinListsType(pin, decl.type);
  if (chosenPlatform === "mspm0" && decl.type === "pwm") {
    return mspm0PwmAllowed(pin, decl).length > 0;
  }
  const insts = roleInstances(decl);
  if (insts.length) return insts.every((i) => pinSupports(pin, decl.type, i));
  return pinSupports(pin, decl.type, "");
}

function pinListsType(pin, type) {
  // 菜单第一层过滤：引脚能力集里连该类型 token 都没有的角色直接不列
  // （UART 脚不出现 PWM 角色）；类型有但实例不齐 → 列但灰显
  return (pin.capabilities || []).some((t) => t === type || t.startsWith(type + ":"));
}

function pinMissReason(pin, decl) {
  // 类型级：灰显原因 = 无对应 token（与后端类型级报错文案同语义）
  if (pinIsTypeLevel(decl)) return "该脚不支持角色类型 " + decl.type;
  if (chosenPlatform === "mspm0" && decl.type === "pwm") {
    const channel = pwmRoleChannel(decl);
    return channel
      ? "该脚没有 pwm 通道 " + channel + "（互补通道不算同通道）"
      : "该脚不支持角色类型 pwm";
  }
  const insts = roleInstances(decl);
  if (insts.length) {
    const miss = insts.filter((i) => !pinSupports(pin, decl.type, i));
    return "需要 " + decl.type + " 实例 " + insts.join("、") + "，此脚缺 " + miss.join("、");
  }
  return "该脚不支持角色类型 " + decl.type;
}

function pinMacroFamilies(roles) {
  // 共享宏族（工单 02 发现）：macros 里与其它角色共享的宏——LED_PORT 三灯
  // 共口 / DIP_GPIO 四拨码共口，绑一个角色会改到同族其它角色的共享宏。
  // v1 不拦截（接线语义用户把关），只给提示文案列出同族角色。
  const byMacro = new Map();
  for (const r of roles) {
    for (const macro of r.decl.macros || []) {
      if (!byMacro.has(macro)) byMacro.set(macro, []);
      byMacro.get(macro).push(r);
    }
  }
  const fam = new Map();
  for (const [macro, members] of byMacro) {
    if (members.length < 2) continue;
    for (const r of members) {
      fam.set(r.key, {
        macro,
        siblings: members.filter((o) => o.key !== r.key).map((o) => o.decl.label || o.decl.id),
      });
    }
  }
  return fam;
}

function pinHint(text) {
  const m = $("pin-config-msg");
  m.textContent = text;
  m.classList.toggle("hidden", !text);
}

// ---- 卡片总渲染（板图 SVG + 图例 + 角色清单 + 固定资源丝印） ----
function renderPinCard() {
  const empty = $("pin-config-empty"), body = $("pin-config-body");
  const roles = pinRoles();
  const keys = new Set(roles.map((r) => r.key));
  // 展开结果变化后清理已消失角色的绑定/红显/高亮（新角色默认值预填显示）
  if (expanded.length) {
    for (const k of Object.keys(pinBindings)) if (!keys.has(k)) delete pinBindings[k];
    for (const k of [...pinUnbound]) if (!keys.has(k)) pinUnbound.delete(k);
    if (pinHighlight && !keys.has(pinHighlight)) pinHighlight = null;
  }
  $("btn-pin-reset").style.display = (Object.keys(pinBindings).length || pinUnbound.size) ? "" : "none";
  if (!chosenPlatform) {
    body.classList.add("hidden"); empty.classList.remove("hidden");
    empty.textContent = "请先选择目标平台（步骤 3）。";
    syncStep7({ platform: chosenPlatform, expanded, roles: pinRoles(), bindings: pinBindings, instances })
    return;
  }
  if (!pinBoard) {
    body.classList.add("hidden"); empty.classList.remove("hidden");
    empty.textContent = pinBoardError ? "板定义加载失败：" + pinBoardError : "板定义加载中…";
    syncStep7({ platform: chosenPlatform, expanded, roles: pinRoles(), bindings: pinBindings, instances })
    return;
  }
  // 选了平台就能看板图（不必等推荐/展开）：未展开模块清单时角色区显示占位文案
  empty.classList.add("hidden"); body.classList.remove("hidden");
  $("pin-highlight-msg").textContent = pinHighlight
    ? "已选中角色：板图高亮可接引脚（灰 = 不兼容），点引脚弹菜单绑定。"
    : "";
  $("btn-pin-overview").classList.toggle("pin-overview-on", pinOverview);
  renderPinLegend(roles);
  renderPinOverviewLegend(roles);
  renderPinBoard();
  renderPinRoles(roles, pinMacroFamilies(roles));
  const fixedHtml = (pinBoard.fixed || []).map((f) =>
    `<span class="fx" title="${esc(f.note)}">${esc(f.name)}：${esc(f.occupies.join("、"))}</span>`).join("");
  $("pin-fixed-list").innerHTML = fixedHtml;
  $("pin-fixed-sub").classList.toggle("hidden", !fixedHtml);
  // 板载共用警示（可见警告，不只悬停）：io 引脚带 notes = 与板载资源共用（BSL/LED/ROSC 等）
  const warnHtml = (pinBoard.pins || [])
    .filter((p) => p.kind === "io" && p.notes)
    .map((p) => `<span class="wx" title="${esc(p.notes)}">⚠ ${esc(p.name)} · ${esc(p.notes)}</span>`)
    .join("");
  $("pin-warn-list").innerHTML = warnHtml;
  $("pin-warn-sub").classList.toggle("hidden", !warnHtml);
  // 步骤 7 完成判定随角色/绑定/展开变化重算（工单 step7-done/01）
  syncStep7({ platform: chosenPlatform, expanded, roles: pinRoles(), bindings: pinBindings, instances })
}

async function loadPinBoard() {
  pinBoard = null; pinBoardError = "";
  renderPinCard();
  if (!chosenPlatform) return;
  try {
    const data = await apiGet("/api/boards?platform=" + encodeURIComponent(chosenPlatform));
    pinBoard = (data.boards || [])[0] || null;
    if (!pinBoard) pinBoardError = "该平台没有板定义数据。";
  } catch (e) {
    pinBoard = null;
    pinBoardError = e.message;
  }
  renderPinCard();
}

function renderPinLegend(roles) {
  const seen = [];
  for (const r of roles) if (!seen.includes(r.decl.type)) seen.push(r.decl.type);
  let html = seen.map((t) => {
    const st = PIN_TYPE_STYLE[t] || ["var(--accent)", "var(--accent-dim)"];
    return `<span class="lg"><span class="dot" style="background:${st[0]}"></span>${esc(PIN_TYPE_ZH[t] || t)}</span>`;
  }).join("");
  html += `<span class="lg"><span class="dot" style="background:var(--pin-pad);border:1px solid var(--border-strong)"></span>空闲 IO</span>`;
  html += `<span class="lg"><span class="dot" style="background:transparent;border:1px dashed var(--warn)"></span>板载共用（见板图下方警示）</span>`;
  html += `<span class="lg"><span class="dot" style="background:var(--pin-fixed-pad);border:1px solid var(--border)"></span>固定/电源（不可点）</span>`;
  $("pin-legend").innerHTML = html;
}

function renderPinOverviewLegend(roles) {
  const box = $("pin-overview-legend");
  if (!pinOverview) { box.classList.add("hidden"); box.innerHTML = ""; return; }
  const cmap = moduleColorMap(roles);
  const items = [...cmap.entries()].map(([slug, color]) =>
    `<span class="lg"><span class="dot" style="background:${color}"></span>${esc(slug)}</span>`).join("");
  box.innerHTML = `<span class="muted" style="font-weight:600">总览（按模块着色，仅标已配置引脚）：</span> ${items}`;
  box.classList.remove("hidden");
}

// ---- 板图 SVG（boards JSON 坐标内联渲染：双排焊盘 + 丝印 + 功能区） ----
// 旋转 180° = 坐标对换重渲染（丝印天然正对、位置随板走、标签仍在焊孔两侧）；
// 90°/270° = CSS 旋转缩放（丝印侧置，用户不要求）。板名标题在 SVG 外永远正对。
// ⚠ 几何常量（rowH/topPad/W/焊盘 r=7/标签 font-size=11）与 fx/resource-board.js
// 资源板图（resource-overview-polish/02）交叉同步——两处改动必须一致。
function renderPinBoard() {
  const box = $("pin-board-svg");
  const roles = pinRoles();
  if (!pinBoard) { box.innerHTML = ""; $("pin-board-caption").textContent = ""; return; }
  const idx = pinIndex();
  const rowH = 22, topPad = 46;
  const rows = Math.max(...pinBoard.pins.map((p) => p.y)) + 1;
  const rot = ((pinRotation % 360) + 360) % 360;
  const rotated180 = rot === 180;
  const hasTop = (pinBoard.landmarks || []).some((l) => l.edge === "top");
  const hasBottom = (pinBoard.landmarks || []).some((l) => l.edge === "bottom");
  // 底部额外空间：0° 时下缘地标（Type-C 标签）；180° 时上缘地标转下来（4P 排针伸出板外 34px）
  const extraBottom = rotated180 ? (hasTop ? 48 : 14) : (hasBottom ? 40 : 14);
  const W = 460, H = topPad + rows * rowH + extraBottom;
  const pcbBottom = topPad - 10 + rows * rowH + 18;
  const parts = [];
  // 90/270 走 CSS 旋转缩放塞进 440 宽栏（transform 不动布局盒，盒子高度按缩放后算）；
  // 0/180 无 transform（180 由坐标对换承担）
  const cssRotate = rot === 90 || rot === 270;
  const scale = cssRotate ? W / H : 1;
  box.style.height = Math.round(cssRotate ? 440 * (W / H) : (440 * H) / W) + "px";
  parts.push(`<svg viewBox="0 0 ${W} ${H}" style="width:100%;max-width:440px;${cssRotate ? `transform:rotate(${rot}deg) scale(${scale});transform-origin:center` : ""}" role="img" aria-label="${esc(pinBoard.name)}板图">`);
  // PCB 本体 + 芯片丝印（pcb_color = 板 JSON 底色，俯视观感；缺省用默认令牌）
  // 顶部留 30px 给向上伸出的排针、底部额外 +18：最下排焊孔与板缘留出间距
  parts.push(`<rect x="100" y="${topPad - 10}" width="260" height="${rows * rowH + 18}" rx="8" fill="${esc(pinBoard.pcb_color || "var(--pin-pcb)")}" stroke="var(--border)" stroke-width="1.5"/>`);
  const chip = chosenPlatform === "stm32" ? "STM32F103C8T6" : "MSPM0G3507";
  parts.push(`<rect x="186" y="${H / 2 - 34}" width="88" height="68" rx="4" fill="var(--panel-2)" stroke="var(--border-strong)" stroke-width="1"/>`);
  parts.push(`<text x="230" y="${H / 2 - 10}" text-anchor="middle" font-family="var(--mono)" font-size="8.5" fill="var(--muted)">${esc(chip)}</text>`);
  parts.push(`<text x="230" y="${H / 2 + 14}" text-anchor="middle" font-size="9" fill="var(--muted)">2×20 排针</text>`);
  // 板缘地标（俯视画法，渲染器只认认识的 kind，未知静默跳过）：
  // header_4p = 黑色胶壳贴板缘 + 4 根金色长排针（30px）向板外伸出；
  // usb_typec = 银白宽扁壳面贴板面向板内延伸，开口朝屏幕外
  for (const lm of pinBoard.landmarks || []) {
    // 180° 坐标对换后：上缘地标画到下缘、下缘地标画到上缘（镜像几何）
    const edge = rotated180
      ? (lm.edge === "top" ? "bottom" : lm.edge === "bottom" ? "top" : lm.edge)
      : lm.edge;
    if (lm.kind === "header_4p" && edge === "top") {
      parts.push(`<rect x="192" y="${topPad - 14}" width="76" height="6" rx="1" fill="#14161a" stroke="var(--border)" stroke-width="0.8"><title>${esc(lm.note || "")}</title></rect>`);
      for (let i = 0; i < 4; i++) {
        parts.push(`<rect x="${198 + i * 16}" y="2" width="4" height="30" fill="#c9a227" stroke="#8a6d1d" stroke-width="0.5"/>`);
      }
      parts.push(`<text x="230" y="${topPad - 1}" text-anchor="middle" font-size="7.5" fill="var(--muted)">${esc(lm.label || "4P 弯针")}</text>`);
    } else if (lm.kind === "header_4p" && edge === "bottom") {
      parts.push(`<rect x="192" y="${pcbBottom - 4}" width="76" height="6" rx="1" fill="#14161a" stroke="var(--border)" stroke-width="0.8"><title>${esc(lm.note || "")}</title></rect>`);
      for (let i = 0; i < 4; i++) {
        parts.push(`<rect x="${198 + i * 16}" y="${pcbBottom - 2}" width="4" height="30" fill="#c9a227" stroke="#8a6d1d" stroke-width="0.5"/>`);
      }
      parts.push(`<text x="230" y="${pcbBottom - 12}" text-anchor="middle" font-size="7.5" fill="var(--muted)">${esc(lm.label || "4P 弯针")}</text>`);
    } else if (lm.kind === "usb_typec" && edge === "bottom") {
      parts.push(`<rect x="205" y="${pcbBottom - 30}" width="50" height="26" rx="3" fill="#c9ced6" stroke="#7d848e" stroke-width="1"><title>${esc(lm.note || "USB Type-C 插口")}</title></rect>`);
      parts.push(`<rect x="213" y="${pcbBottom - 7}" width="34" height="3" rx="1" fill="var(--bg)"/>`);
      parts.push(`<text x="230" y="${pcbBottom + 8}" text-anchor="middle" font-size="8" fill="var(--muted)">${esc(lm.label || "Type-C")}</text>`);
    } else if (lm.kind === "usb_typec" && edge === "top") {
      parts.push(`<rect x="205" y="${topPad - 6}" width="50" height="26" rx="3" fill="#c9ced6" stroke="#7d848e" stroke-width="1"><title>${esc(lm.note || "USB Type-C 插口")}</title></rect>`);
      parts.push(`<rect x="213" y="${topPad - 6}" width="34" height="3" rx="1" fill="var(--bg)"/>`);
      parts.push(`<text x="230" y="${topPad - 18}" text-anchor="middle" font-size="8" fill="var(--muted)">${esc(lm.label || "Type-C")}</text>`);
    }
  }
  // 板名标题在 SVG 之外（HTML div）：旋转视角时永远正对用户、永远在最下面
  $("pin-board-caption").textContent = pinBoard.name;
  for (const pin of pinBoard.pins) parts.push(svgPin(pin, roles, idx, rotated180));
  parts.push(`</svg>`);
  box.innerHTML = parts.join("");
  box.querySelectorAll("circle[data-pin]").forEach((c) => {
    c.addEventListener("click", () => {
      // 多实例选脚模式（工单 04 + key-multi-instance/06）：按模块首 pin 能力
      // 过滤候选（led = gpio_out、key = gpio_in），点即绑
      if (instancePinTarget) {
        const p = pinIndex()[c.dataset.pin];
        if (p && p.kind === "io" && (p.capabilities || []).includes(instancePinCapability(instancePinTarget.slug))) {
          assignInstancePin(c.dataset.pin);
        }
      } else {
        showPinMenu(c, c.dataset.pin);
      }
    });
  });
}

function svgPin(pin, roles, idx, rotated180) {
  const rowH = 22, topPad = 46;
  // 180° 坐标对换：列互换、行倒序（两板均 20 行，y 0..19）——丝印位置随板走、
  // 标签仍在焊孔外侧（左列→右侧样式、右列→左侧样式），文字天然正对无需补偿
  const gx = rotated180 ? 1 - pin.x : pin.x;
  const gy = rotated180 ? 19 - pin.y : pin.y;
  const cx = gx === 0 ? 150 : 310;
  const cy = topPad + gy * rowH + rowH / 2;
  const bound = roles.filter((r) => pinBindings[r.key] === pin.name);
  const overview = pinOverview ? overviewRolesAt(pin.name, roles) : [];
  const overviewMods = pinOverview && overview.length ? [...new Set(overview.map((r) => r.slug))] : [];
  const io = pin.kind === "io";
  let fill = "var(--pin-pad)", stroke = "var(--border-strong)", labelFill = "var(--muted)";
  let fillOpacity = "1", strokeWidth = "1.5", overviewColor = null, pieSvg = "";
  const overviewColors = overviewMods.map((s) => moduleColorMap(roles).get(s));
  if (!io) { fill = "var(--pin-fixed-pad)"; stroke = "var(--border)"; }
  else if (pinOverview && overview.length) {
    overviewColor = overviewColors[0] || "var(--accent)";
    labelFill = overviewColor;
    if (overviewMods.length > 1) {
      // 多模块：焊孔填充（pieSvg 扇形）+ 焊孔描边（r=7 弧段）都按模块数分色
      fill = "transparent"; stroke = "none";
      pieSvg = overviewPie(cx, cy, 7, overviewColors, "0.75");
    } else {
      fill = overviewColor; stroke = overviewColor; fillOpacity = "0.75"; strokeWidth = "2.5";
    }
  }
  else if (bound.length) {
    const st = PIN_TYPE_STYLE[bound[0].decl.type] || ["var(--accent)", "var(--accent-dim)"];
    fill = st[1]; stroke = st[0]; labelFill = st[0];
  }
  let cls = "", extra = "";
  // 总览模式：单模块整圈同色；多模块焊孔描边（r=7）+ 高亮环（r=10.5）都按模块数均分着色
  if (overviewColor) {
    if (overviewMods.length > 1) extra += overviewRing(cx, cy, 7, overviewColors, 2.5);
    extra += overviewRing(cx, cy, 10.5, overviewColors, 2);
  }
  if (pinHighlight) {
    const hl = roles.find((r) => r.key === pinHighlight);
    if (hl) {
      if (idx[hl.decl.default] === pin) {
        extra += `<circle cx="${cx}" cy="${cy}" r="13" fill="none" class="pin-default-cand"/>`;
        extra += `<circle cx="${cx}" cy="${cy}" r="4" class="pin-default-dot"/>`;
      }
      if (pinCanHost(pin, hl.decl)) cls = ' class="pin-cand"';
      else if (io) cls = ' class="pin-dim"';
    }
  }
  // 多实例选脚模式（工单 04 + key-multi-instance/06）：按模块首 pin 能力候选
  if (instancePinTarget && io) {
    const assigned = (instances[instancePinTarget.slug] || [])[instancePinTarget.index]
      && instances[instancePinTarget.slug][instancePinTarget.index].pin === pin.name;
    if ((pin.capabilities || []).includes(instancePinCapability(instancePinTarget.slug))) {
      cls = ' class="pin-cand"';
      if (assigned) extra += `<circle cx="${cx}" cy="${cy}" r="13" fill="none" class="pin-default-cand"/>`;
    } else {
      cls = ' class="pin-dim"';
    }
  }
  // 同引脚多角色共享（非总览）→ 焊盘上方叠小色点（按类型色；xunji/huidu 先例）。
  // 总览的多模块共存由上方 overviewRing 圆周均分弧段表达，不再画小点。
  if (!pinOverview && bound.length > 1) {
    for (let i = 0; i < Math.min(bound.length, 3); i++) {
      const st = PIN_TYPE_STYLE[bound[i].decl.type] || ["var(--accent)", "var(--accent-dim)"];
      extra += `<circle cx="${cx - 6 + i * 6}" cy="${cy - 13}" r="3" fill="${st[0]}"/>`;
    }
    if (bound.length > 3) extra += `<text x="${cx + 8}" y="${cy - 9}" font-size="9" fill="var(--muted)">+${bound.length - 3}</text>`;
  }
  // 板载共用警告环（io 且带 notes = 与板载资源共用，如 BSL/LED/ROSC——
  // 可见警示不靠悬停，下方 pin-warn-list 有完整清单）
  if (io && pin.notes) {
    extra += `<circle cx="${cx}" cy="${cy}" r="9.5" fill="none" stroke="var(--warn)" stroke-width="1" stroke-dasharray="2.5 2"/>`;
  }
  const ttl = [pin.name, io ? "IO 引脚" : "固定/电源"];
  if (bound.length) ttl.push("已绑：" + bound.map((r) => r.decl.label || r.decl.id).join("、"));
  if (pinOverview && overview.length) ttl.push("总览已配置：" + overview.map((r) => r.slug + "." + (r.decl.label || r.decl.id)).join("、"));
  if (pin.notes) ttl.push(pin.notes);
  if (io) ttl.push("能力：" + (pin.capabilities || []).join("、"));
  const labelX = gx === 0 ? cx - 14 : cx + 14;
  const anchor = gx === 0 ? "end" : "start";
  const clickable = io ? ` data-pin="${esc(pin.name)}" style="cursor:pointer"` : ' style="pointer-events:none"';
  return pieSvg +
    `<circle cx="${cx}" cy="${cy}" r="7" fill="${fill}" fill-opacity="${fillOpacity}" stroke="${stroke}" stroke-width="${strokeWidth}"${cls}${clickable}>` +
    `<title>${esc(ttl.join(" · "))}</title></circle>${extra}` +
    `<text x="${labelX}" y="${cy + 4}" text-anchor="${anchor}" font-family="var(--mono)" font-size="11" fill="${labelFill}"${overviewColor ? ' font-weight="700"' : ""}>${esc(pin.name)}</text>`;
}

// ---- 角色清单（标签 / 默认值 / 三态绑定；点条目 → 板图高亮可接引脚） ----
function renderPinRoles(roles, fam) {
  const box = $("pin-role-items");
  if (!roles.length) {
    box.innerHTML = expanded.length
      ? '<div class="muted">所选模块在此平台没有可配置的引脚角色——按默认布线生成，无需配置。</div>'
      : '<div class="muted">尚未展开模块清单（步骤 6）——板图先行，展开后这里列出接线角色。</div>';
    return;
  }
  const idx = pinIndex();
  // 同脚多角色 共享/冲突 判据（工单 pin-share-rule/01）：默认脚重叠的角色对按
  // 物理资源键分类——同一 I2C 总线 / UART 实例 / syscfg 器件实例 = 合法共享
  // （灰度 8 路 / zigbee 家族 / UART1 三件套）；其余同脚 = 冲突（DIP×灰度、
  // 电机×按键、灰度×UART 等默认布局残留——旧行为同型同脚静默通过）。
  const instanceMap = (state && state.module_instances) || {};
  const defaultOverlap = new Map();
  for (const r of roles) {
    if (!idx[r.decl.default]) continue;
    const others = roles.filter((o) => o.key !== r.key && o.decl.default === r.decl.default);
    if (!others.length) continue;
    const cls = pinShareClass([r, ...others], r.decl.default, pinBoard, instanceMap);
    defaultOverlap.set(r.key, {
      kind: cls.kind,
      reason: cls.reason,
      others: others.map((o) => o.decl.label || o.decl.id).join("、"),
    });
  }
  const roleHtml = (r) => {
    const st = PIN_TYPE_STYLE[r.decl.type] || ["var(--accent)", "var(--accent-dim)"];
    const bound = pinBindings[r.key];
    const unbound = pinUnbound.has(r.key);
    const defOnBoard = !!idx[r.decl.default];
    const famInfo = fam.get(r.key);
    const overlap = defaultOverlap.get(r.key);
    let status;
    if (bound) {
      status = `<span style="color:${st[0]}">已绑 ${esc(bound)}</span>` +
        (bound !== r.decl.default ? ` <span class="muted">（默认 ${esc(r.decl.default)}）</span>` : "") +
        ' <button class="pin-role-unbind">还原默认</button>';
    } else if (unbound) {
      status = `<span style="color:var(--danger)">未绑定</span>` +
        `<span class="muted">（生成仍按默认 ${esc(r.decl.default)} 走）</span>` +
        ' <button class="pin-role-restore">清除红显</button>';
    } else if (!defOnBoard) {
      status = `<span style="color:var(--warn)">默认板外（排针未引出）——仍可绑到板内空闲脚</span>`;
    } else if (overlap && overlap.kind === "conflict") {
      status = `<span style="color:var(--warn)">默认 ${esc(r.decl.default)} 与 ${esc(overlap.others)} 冲突（同脚分属不同外设）——未绑定时生成会资源冲突，建议改线</span>`;
    } else if (Object.values(pinBindings).includes(r.decl.default)) {
      const by = Object.entries(pinBindings).find(([k, v]) => v === r.decl.default && k !== r.key);
      const byName = esc((by && by[0]) || "其它角色");
      status = overlap && overlap.kind === "share"
        ? `<span class="muted">默认 ${esc(r.decl.default)} 已被 ${byName} 占用（同一外设/总线，合法共享）</span>`
        : `<span style="color:var(--warn)">默认 ${esc(r.decl.default)} 已被 ${byName} 占用——未绑定时生成可能资源冲突，建议改线</span>`;
    } else if (overlap && overlap.kind === "share") {
      status = `<span class="muted">默认 ${esc(r.decl.default)}（与 ${esc(overlap.others)} 共用同一外设/总线，合法共享）</span>`;
    } else {
      status = `<span class="muted">默认 ${esc(r.decl.default)}</span>`;
    }
    return `<div class="pin-role ${bound ? "bound" : ""} ${unbound ? "unbound" : ""}" data-role="${esc(r.key)}">
      <div class="role-head">
        <span class="role-type" style="color:${st[0]};background:${st[1]};border:1px solid ${st[0]}">${esc(r.decl.type)}</span>
        <strong>${esc(r.decl.label || r.decl.id)}</strong>
        <span class="muted">${esc(r.slug)}</span>
        ${r.decl.required ? '<span class="badge hw">必接</span>' : '<span class="badge dep">可选</span>'}
      </div>
      <div class="role-status">${status}</div>
      ${famInfo ? `<div class="role-status" style="color:var(--warn)">共享宏族 ${esc(famInfo.macro)}：同族 ${esc(famInfo.siblings.join("、"))}</div>` : ""}
    </div>`;
  };
  const requiredRoles = roles.filter((r) => r.decl.required);
  const optionalRoles = roles.filter((r) => !r.decl.required);
  // 已动过的可选角色不能被折叠藏起来（用户绑了线/红显解除后要可见）
  const hasTouchedOptional = optionalRoles.some(
    (r) => pinBindings[r.key] || pinUnbound.has(r.key)
  );
  const showOptional = pinShowOptional || hasTouchedOptional;
  let html = requiredRoles.map(roleHtml).join("");
  if (optionalRoles.length) {
    if (showOptional) {
      html += optionalRoles.map(roleHtml).join("");
      html += '<button class="pin-toggle-optional" id="btn-pin-hide-optional">收起可选角色</button>';
    } else {
      html += `<button class="pin-toggle-optional" id="btn-pin-show-optional">显示 ${optionalRoles.length} 个可选角色（不接 = 按默认生成）</button>`;
    }
  }
  box.innerHTML = html;
  box.querySelectorAll(".pin-role").forEach((el) => {
    el.addEventListener("click", (e) => {
      if (e.target.closest("button")) return;
      const key = el.dataset.role;
      pinHighlight = pinHighlight === key ? null : key;
      renderPinCard();
    });
  });
  box.querySelectorAll(".pin-role-unbind").forEach((b) => {
    b.addEventListener("click", () => unbindRole(b.closest(".pin-role").dataset.role));
  });
  box.querySelectorAll(".pin-role-restore").forEach((b) => {
    b.addEventListener("click", () => {
      pinUnbound.delete(b.closest(".pin-role").dataset.role);
      renderPinCard();
    });
  });
  const showOptBtn = $("btn-pin-show-optional");
  if (showOptBtn) showOptBtn.addEventListener("click", () => { pinShowOptional = true; renderPinCard(); });
  const hideOptBtn = $("btn-pin-hide-optional");
  if (hideOptBtn) hideOptBtn.addEventListener("click", () => { pinShowOptional = false; renderPinCard(); });
}

$("btn-pin-reset").addEventListener("click", async () => {
  // 清空全部绑定前确认（工单 ux-walkthrough-02/01）：误点清零是第三处数据丢失风险
  const count = Object.keys(pinBindings).length + pinUnbound.size;
  const ok = await confirmModal({
    title: "还原默认？",
    message: pinResetConfirmMessage(count),
    confirmText: "还原",
  });
  if (!ok) return;
  pinBindings = {}; pinUnbound = new Set(); pinHighlight = null; pinHint("");
  renderPinCard();
  if (count) toast("ok", `已将 ${count} 处引脚改动还原为默认`);
});

$("btn-pin-rotate").addEventListener("click", () => {
  pinRotation += 90;  // 每次 +90°（0→90→180→270→0），纯视图不影响绑定数据
  renderPinBoard();
});

$("btn-pin-overview").addEventListener("click", () => {
  pinOverview = !pinOverview;
  renderPinCard();  // 总览着色 + 模块图例切换
});

// 自动配置（工单 pin-auto-assign/01）：一键解冲突——确定性算法把真冲突角色
// 重分到不冲突引脚，合法共享保留并标注；只动冲突角色，用户合法绑定不动。
$("btn-pin-auto").addEventListener("click", async () => {
  const msg = $("pin-config-msg");
  msg.classList.add("hidden");
  if (!chosenPlatform) { msg.textContent = "请先选择目标平台"; msg.classList.remove("hidden"); return; }
  const slugs = expanded.map((m) => m.slug);
  const bindings = collectBindings(slugs, pinBindings, instances);
  const btn = $("btn-pin-auto");
  btn.disabled = true;
  try {
    const res = await apiPost("/api/bindings/auto", {
      platform: chosenPlatform, slugs, bindings: Object.keys(bindings).length ? bindings : null,
    });
    if (!res.ok) { msg.textContent = res.error || "自动配置失败"; msg.classList.remove("hidden"); return; }
    // 应用增量：只覆盖冲突角色（其余绑定不动）
    for (const [key, pin] of Object.entries(res.bindings || {})) {
      pinBindings[key] = pin;
    }
    renderPinCard();
    // 结果说明条：已调整 + 同脚标注（工单 pin-share-rule/01：kind 区分
    // 合法共享 🔗 与物理冲突 ⚠——旧行为统一「合法共享，不拆」误导接线）
    const lines = [];
    for (const line of res.fixed || []) lines.push("✓ " + line);
    for (const s of res.shared || []) {
      lines.push((s.kind === "conflict" ? "⚠ " : "🔗 ") + s.pin + "：" + s.roles.join(" / ") + " —— " + s.reason);
    }
    if (!lines.length) lines.push("当前绑定无冲突，无需调整。");
    msg.textContent = lines.join("\n");
    msg.classList.remove("hidden");
  } catch (e) {
    msg.textContent = e.message || String(e);
    msg.classList.remove("hidden");
  } finally {
    btn.disabled = false;
  }
});

function unbindRole(key) {
  delete pinBindings[key];
  pinUnbound.add(key);  // 显式解除 = 红显未绑（生成仍按默认走）
  renderPinCard();
  syncStep7({ platform: chosenPlatform, expanded, roles: pinRoles(), bindings: pinBindings, instances })
}

function bindRole(key, pinName) {
  const roles = pinRoles();
  const r = roles.find((x) => x.key === key);
  if (!r || pinBindings[key] === pinName) return;
  // 替换本脚占用者：被替换角色回"未绑定"红显（排针满员两步换位交互）
  for (const [k, v] of Object.entries(pinBindings)) {
    if (v === pinName && k !== key) {
      delete pinBindings[k];
      pinUnbound.add(k);
    }
  }
  pinBindings[key] = pinName;
  pinUnbound.delete(key);
  pinHighlight = null;
  renderPinCard();
  syncStep7({ platform: chosenPlatform, expanded, roles: pinRoles(), bindings: pinBindings, instances })
  // 共享宏族提示（v1 不拦截，接线语义用户把关）
  const famInfo = pinMacroFamilies(roles).get(key);
  pinHint(famInfo
    ? `已绑 ${r.decl.label || r.decl.id} → ${pinName}：与同族角色 ${famInfo.siblings.join("、")} 共享宏 ${famInfo.macro}——改线会同步影响同族其它角色的共享宏，请确认接线。`
    : "");
}

// ---- 引脚锚定浮层菜单（复用 .ref-files-overlay 模式） ----
function showPinMenu(pinEl, pinName) {
  const roles = pinRoles();
  const pin = pinIndex()[pinName];
  if (!pin) return;
  const fam = pinMacroFamilies(roles);
  const occupants = roles.filter((r) => pinBindings[r.key] === pinName);
  const defaulters = roles.filter((r) => !pinBindings[r.key] && r.decl.default === pinName);
  document.querySelectorAll(".pin-menu-overlay").forEach((o) => o.remove());
  const overlay = document.createElement("div");
  overlay.className = "pin-menu-overlay";
  const menu = document.createElement("div");
  menu.className = "pin-menu";
  let rows = "";
  if (occupants.length) {
    rows += `<li class="muted" style="font-weight:600">已占用（可直接替换：点下方角色即换绑，原占用角色红显未绑）</li>` +
      occupants.map((r) => {
        const st = PIN_TYPE_STYLE[r.decl.type] || ["var(--accent)", "var(--accent-dim)"];
        return `<li><span class="dot" style="background:${st[0]}"></span>` +
          `<strong>${esc(r.decl.label || r.decl.id)}</strong> <span class="muted">${esc(r.slug)}</span>` +
          `<button class="pin-menu-unbind" data-key="${esc(r.key)}">解除</button></li>`;
      }).join("");
  }
  if (defaulters.length) {
    // 同脚分类（工单 pin-share-rule/01）：默认重叠的角色与已占用角色一起判定——
    // 同一外设/总线 = 合法共享；分属不同外设 = 物理冲突，提示改线。
    const cls = pinShareClass(
      [...occupants, ...defaulters], pinName, pinBoard, (state && state.module_instances) || {}
    );
    const suffix = cls.kind === "conflict"
      ? "——同脚分属不同外设（物理冲突），请改线"
      : "——同用一外设/总线（合法共享）";
    rows += `<li class="muted">另有 ${defaulters.length} 个角色默认使用此脚（未绑定，按默认生成）：${defaulters.map((r) => esc(r.decl.label || r.decl.id)).join("、")}${suffix}。</li>`;
  }
  rows += `<li class="muted" style="font-weight:600;border-top:1px dashed var(--border);margin-top: var(--space-1);padding-top:8px">绑定角色到此脚（点条目即绑定）：</li>`;
  rows += roles.filter((r) => pinListsType(pin, r.decl.type)).map((r) => {
    const can = pinCanHost(pin, r.decl);
    const st = PIN_TYPE_STYLE[r.decl.type] || ["var(--accent)", "var(--accent-dim)"];
    const bound = pinBindings[r.key];
    const why = can ? "" : pinMissReason(pin, r.decl);
    const famInfo = fam.get(r.key);
    return `<li class="${can ? "can" : "cant"}" ${can ? `data-bind="${esc(r.key)}"` : ""} title="${esc(why)}">
      <span class="role-type" style="color:${st[0]};background:${st[1]};border:1px solid ${st[0]}">${esc(r.decl.type)}</span>
      <strong>${esc(r.decl.label || r.decl.id)}</strong>
      <span class="muted">${esc(r.slug)} · 默认 ${esc(r.decl.default)}</span>
      ${r.decl.required ? '<span class="badge hw">必接</span>' : ""}
      ${bound ? ` <span style="color:${st[0]}">现绑 ${esc(bound)}</span>` : ""}
      ${famInfo ? `<span class="fam">共享宏族 ${esc(famInfo.macro)}：绑它会改到同族 ${esc(famInfo.siblings.join("、"))} 的共享宏</span>` : ""}
      ${why ? `<span class="why">不兼容：${esc(why)}</span>` : ""}
    </li>`;
  }).join("");
  menu.innerHTML = `
    <div class="pin-menu-head">
      <strong style="font-family:var(--mono)">${esc(pinName)}</strong>
      <span class="muted">${esc(pin.notes || "IO 引脚")}</span>
      <button class="ref-files-close" title="关闭">×</button>
    </div>
    <div class="muted" style="padding:6px 14px;font-size:12px;font-family:var(--mono);word-break:break-all">能力：${esc((pin.capabilities || []).join("、") || "无")}</div>
    <ul class="pin-menu-list">${rows}</ul>`;
  overlay.appendChild(menu);
  document.body.appendChild(overlay);
  const close = () => overlay.remove();
  overlay.querySelector(".ref-files-close").addEventListener("click", close);
  overlay.addEventListener("click", (e) => { if (e.target === overlay) close(); });
  const onKey = (e) => { if (e.key === "Escape") close(); };
  document.addEventListener("keydown", onKey);
  overlay.addEventListener("remove", () => document.removeEventListener("keydown", onKey));
  // 锚定弹层：贴引脚右侧/左侧（越界翻面），纵向夹在视口内
  const rect = pinEl.getBoundingClientRect();
  let left = rect.right + 10;
  if (left + 436 > window.innerWidth) left = rect.left - 446;
  left = Math.max(8, Math.min(left, window.innerWidth - 444));
  const top = Math.max(8, Math.min(rect.top, window.innerHeight - menu.offsetHeight - 8));
  menu.style.left = left + "px";
  menu.style.top = top + "px";
  menu.querySelectorAll("li[data-bind]").forEach((li) =>
    li.addEventListener("click", () => { bindRole(li.dataset.bind, pinName); close(); }));
  menu.querySelectorAll(".pin-menu-unbind").forEach((b) =>
    b.addEventListener("click", (e) => { e.stopPropagation(); unbindRole(b.dataset.key); close(); }));
}


// ---- 跨簇接缝函数（原 index.html 启动区 setClusterDeps 薄胶水迁入本体；工单 12
// 接缝 → 13 静态化；推荐簇 A 经 setClusterDeps 注册调用） ----
export function pinChangeCount() {
  // 用户改过的引脚处数（绑定 + 显式解除）——平台切换确认 / 还原默认确认的计数口径
  return Object.keys(pinBindings).length + pinUnbound.size;
}
export function configuredInstanceCount() {
  // 已配置实例总数（跨模块求和）——平台切换确认的计数口径
  return Object.values(instances).reduce((s, a) => s + ((a && a.length) || 0), 0);
}
export function resetPinState() {
  pinBindings = {}; pinUnbound = new Set(); pinHighlight = null; pinHint("");
}
export function resetInstances() {
  instances = {}; instancePinTarget = null; renderInstanceConfig();
}
export function clearInstanceTarget() {
  instancePinTarget = null;
}
export function backfillInstances(dataInstances) {
  for (const slug of Object.keys(dataInstances)) {
    instances[slug] = (dataInstances[slug] || []).map((i) => ({
      name: String(i.name || ""), variant: i.variant || "", pin: i.pin || "",
    }));
  }
  instancePinTarget = null;  // 旧选脚目标可能越界，清掉防陈旧高亮
}

// ---- 本簇导出面（host 顶部 import 代理 + 推荐簇 A 接缝导点名） ----
export { renderInstanceConfig, renderPinCard, loadPinBoard, bindRole, unbindRole, assignInstancePin, addInstance, delInstance, pinRoles };
