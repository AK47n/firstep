// fx/my-devices.js — 「我的器件」（库外件）的表单纯函数（工单 hwcheck-unknown-device/02）。
//
// 学生手上新到一件不在模块库里的器件：名称 / 总线 / **7 位地址** / 身份寄存器 /
// 期望值 / 备注。本文件只出字符串与状态对象，**不碰 DOM、不发请求**（DOM 胶水在
// ui/hwcheck.js）。件**与平台无关**——同一件在两个平台上都能测，所以这里没有
// 任何平台字段。
//
// 三条纪律（与仓库既有分工一致）：
//
// 1. **地址双向显示**（`myDeviceAddressForms`）：手册里 7 位（0x68）与 8 位
//    （0xD0 / 0xD1）两种写法都常见，页面必须两种都给出来——这是填错地址最常见
//    的一处坑。真相只有一个（存下来的 7 位值），8 位形式永远是派生的。
// 2. **表单校验不是判据本体**：判据在服务端（`my_devices.CustomDevice.validated`），
//    这里的 `myDeviceFormCheck` 只是"别让用户白跑一趟"。两边规则由
//    `tests/js/my-devices.test.mjs` 读真源码逐字对账（词表 / 前缀 / 地址区间）。
// 3. **用户填的一切都走 esc**：名称与备注会进 innerHTML，转义单源取自 fx/core.js。
import { esc } from "./core.js";

// id 前缀：与服务端 `my_devices.DEVICE_ID_PREFIX` 同源（跨语言守卫对账）
export const MY_DEVICE_ID_PREFIX = "mine_";

// 7 位地址的合法区间（I2C 规范保留段之外）：与服务端 ADDRESS7_MIN/MAX 同源
export const MY_DEVICE_ADDRESS_MIN = 0x08;
export const MY_DEVICE_ADDRESS_MAX = 0x77;

// id 文法 = 前缀 + slug 形（与服务端 `entry_store.SLUG_PATTERN` 同一文法）
const MY_DEVICE_ID_RE = /^[A-Za-z0-9_][A-Za-z0-9_-]*$/;

// 总线词表 + 中文展示名（与服务端 `BUS_VOCABULARY` / `BUS_LABELS` 同源。
// 只有 i2c 这一版会生成探测程序，其余如实说"不生成"——见 myDeviceRowHTML）
export const MY_DEVICE_BUS_OPTIONS = [
  { value: "i2c", label: "I2C" },
  { value: "spi", label: "SPI" },
  { value: "uart", label: "UART" },
  { value: "onewire", label: "单总线" },
  { value: "analog", label: "模拟量" },
  { value: "gpio", label: "普通 IO（电平）" },
  { value: "other", label: "其它 / 不确定" },
];

const BUS_LABELS = MY_DEVICE_BUS_OPTIONS.reduce((acc, o) => {
  acc[o.value] = o.label;
  return acc;
}, {});

// 「这一版不生成探测程序」那句话的**判据**是总线（只有 i2c 走 i2c_probe 支点）。
// 文案单源在这里，行渲染与页面都读它，不各写一句（**不导出**：文案不该被别处
// 另接一份，要改只改这一处）。
const MY_DEVICE_NON_I2C_NOTE =
  "这一版只对 I2C 器件生成探测程序（其它总线暂时给清单与排障，不假装测过）";

// 名称很长时它是"必填"的第一落点：与后端 NAME_MAX_CHARS 同量级
const NAME_MAX_CHARS = 60;

// 名字 → id 候选（只作"填个建议"用，用户可以改；合法性由 myDeviceFormCheck 判）。
// 中文名派生不出 ASCII slug 时给 `mine_device` 兜底——空 id 提交必被后端拒，
// 有一个能改的默认值比让用户对着空框想"该填什么"好。
export function myDeviceSlugFromName(name) {
  const raw = String(name == null ? "" : name).toLowerCase();
  const body = raw
    .replace(/[^a-z0-9_-]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 32);
  return MY_DEVICE_ID_PREFIX + (body || "device");
}

// 空白表单（点「+ 我的器件」时的初值）。id 留空：由用户填或按名称派生。
export function myDeviceFormBlank() {
  return {
    id: "", name: "", bus: "i2c",
    address: "", register: "", expect: "", notes: "",
  };
}

// 服务端载荷 → 表单值。整数回填成 `0xNN` 十六进制：手册上就是这个写法，
// 用户改起来不用先做一次进制换算（空 = 空串，不写 "0x00" 那种假值）。
export function myDeviceFormFromPayload(device) {
  const d = device || {};
  return {
    id: String(d.id || ""),
    name: String(d.name || ""),
    bus: String(d.bus || "i2c"),
    address: hexField(d.address),
    register: hexField(d.register),
    expect: hexField(d.expect),
    notes: String(d.notes || ""),
  };
}

function hexField(value) {
  if (value === null || value === undefined || value === "") return "";
  const n = Number(value);
  if (!Number.isInteger(n)) return "";
  return "0x" + n.toString(16).toUpperCase().padStart(2, "0");
}

// parseByte(text)：表单里的一个字节字段（"0x68" / "104" / ""）→ 整数或 null。
// 认不出 / 越界一律 null（由 myDeviceFormCheck 说清楚为什么，不在解析层静默取 0）。
// **不导出**：它是本模块的内部解析件（跨模块消费者会绕过表单校验直接用，
// 那正是"两个判据来源"的开端）。
function myDeviceParseByte(text) {
  const raw = String(text == null ? "" : text).trim();
  if (!raw) return null;
  const value = /^0x[0-9a-f]+$/i.test(raw) ? parseInt(raw.slice(2), 16) : Number(raw);
  if (!Number.isInteger(value) || value < 0 || value > 0xFF) return null;
  return value;
}

// myDeviceAddressForms(address)：7 位地址 → {7 位, 8 位读, 8 位写} 三种写法。
// 8 位形式 = 7 位左移一位 + 读写位（读 1 / 写 0）。解析不出 / 越界 = 三个空串——
// **不编一个 0x00 出来**（"没填"与"地址是 0"是两件事）。
export function myDeviceAddressForms(address) {
  const empty = { address7: "", read8: "", write8: "" };
  const raw = String(address == null ? "" : address).trim();
  if (!raw) return empty;
  const value = myDeviceParseByte(raw);
  if (value === null || value < MY_DEVICE_ADDRESS_MIN || value > MY_DEVICE_ADDRESS_MAX) {
    return empty;
  }
  const hex = (n) => "0x" + n.toString(16).toUpperCase().padStart(2, "0");
  return {
    address7: hex(value),
    read8: hex((value << 1) | 0x01),
    write8: hex(value << 1),
  };
}

// myDeviceAddressPreviewHTML(address, bus, forms)：地址那一行的实时预览。
// 非 I2C 不出这一段（那一类压根没有地址，摆出来等于教用户填一个用不上的字段）；
// 地址为空 = 只说"填 7 位地址"，不显示三种写法（还没得可显示）。
export function myDeviceAddressPreviewHTML(address, bus = "i2c", forms = null) {
  if (bus !== "i2c") return "";
  const derived = forms || myDeviceAddressForms(address);
  if (!derived.address7) {
    return '<div class="hwcheck-hint" data-my-device-address-preview>'
      + "填手册里的 <strong>7 位地址</strong>（如 0x68）——下面会自动给出它对应的"
      + " 8 位读 / 写写法。</div>";
  }
  return '<div class="hwcheck-hint" data-my-device-address-preview>'
    + `地址（7 位）：<span class="hwcheck-pin">${esc(derived.address7)}</span>`
    + ` ｜ 手册里的 8 位写法：读 <span class="hwcheck-pin">${esc(derived.read8)}</span>`
    + ` / 写 <span class="hwcheck-pin">${esc(derived.write8)}</span>`
    + "（7 位与 8 位是同一个地址的两种写法，照着手册对一下就不会填错）</div>";
}

// myDeviceFormCheck(form, knownSlugs, existingIds, editingId)：提交前的自查 →
// 中文理由或空串。
//
// `knownSlugs` = 库内 slug 全量（载荷 `known_slugs`）；`existingIds` = 现有自建件
// id；`editingId` = **正在编辑的那一件**（新建时空串）。
//
// ⚠ `editingId` 不是可有可无的：改一件已有器件时，它的 id 必然出现在
// `existingIds` 里——不带这个参数，"保存这件"永远被判成"撞已有件"而置灰，
// 于是**编辑功能整个用不了**（本单浏览器验收当场抓到的 bug：改名字改成一半
// 按钮就灰了）。规则与服务端 `validated()` 同一套：服务端才是判据本体，
// 这里只是"别让用户白跑一趟"。
export function myDeviceFormCheck(form, knownSlugs = [], existingIds = [], editingId = "") {
  const f = form || {};
  const id = String(f.id || "").trim();
  const name = String(f.name || "").trim();
  const bus = String(f.bus || "");
  if (!id) return "请填 id（这件东西在你工具里的唯一名字，如 mine_gyro）";
  if (!id.startsWith(MY_DEVICE_ID_PREFIX) || !MY_DEVICE_ID_RE.test(id)
      || id.length <= MY_DEVICE_ID_PREFIX.length) {
    return `id 必须是 ${MY_DEVICE_ID_PREFIX} 开头、后面只跟字母数字下划线连字符`
      + "（例：mine_gyro）";
  }
  if (!name) return "请填名称（写你认得出来的那个名字）";
  if (name.length > NAME_MAX_CHARS) return `名称太长了（上限 ${NAME_MAX_CHARS} 字）`;
  if (!BUS_LABELS[bus]) return "请选一个总线类型";
  if ((knownSlugs || []).includes(id)) {
    return `器件 id ${id} 与库内模块同名（库内 slug 也叫这个）——请改名：`
      + "换成你自己的名字（如 " + id + "_v2）再存";
  }
  // 「已经有一件叫这个」只对**新建**成立；编辑自己那件时它就是同一件（同名 =
  // 覆盖它，这正是编辑想要的语义）
  if (id !== String(editingId || "") && (existingIds || []).includes(id)) {
    return `已经有一件叫 ${id} 了——再存就是覆盖它（改个 id 可以并存）`;
  }
  const address = myDeviceParseByte(f.address);
  const register = myDeviceParseByte(f.register);
  const expect = myDeviceParseByte(f.expect);
  if (Boolean(String(f.address || "").trim()) && address === null) {
    return "地址读不出来：填 7 位地址（0x08–0x77，十六进制或十进制都行）";
  }
  if (Boolean(String(f.register || "").trim()) && register === null) {
    return "身份寄存器读不出来：填 8 位值（0x00–0xFF）";
  }
  if (Boolean(String(f.expect || "").trim()) && expect === null) {
    return "期望值读不出来：填 8 位值（0x00–0xFF）";
  }
  if (bus === "i2c") {
    if (address === null) return "I2C 器件必须填地址（手册里的 7 位地址，如 0x68）";
    if (address < MY_DEVICE_ADDRESS_MIN || address > MY_DEVICE_ADDRESS_MAX) {
      return "地址不是 7 位地址（合法区间 0x08–0x77）——手册里常见的是 8 位写法"
        + "（0xD0 这种），请填它的 7 位形式（0x68）";
    }
  } else if (address !== null) {
    return "只有 i2c 才填地址——地址是 I2C 总线的事实，别的总线请留空";
  }
  if (expect !== null && register === null) {
    return "填了期望值就必须填身份寄存器——「期望值」说的是「读哪个寄存器该读回什么」";
  }
  return "";
}

// myDevicePayload(form)：提交体（服务端契约 `{device: {...}}`）。
// 空的可选字段发 **null**（不是空串）：服务端把 null 读成"没填"，空串只是被
// `_optional_byte` 顺带容忍——发 null 语义准。
export function myDevicePayload(form) {
  const f = form || {};
  const notes = String(f.notes || "").trim();
  return {
    device: {
      id: String(f.id || "").trim(),
      name: String(f.name || "").trim(),
      bus: String(f.bus || ""),
      address: myDeviceParseByte(f.address),
      register: myDeviceParseByte(f.register),
      expect: myDeviceParseByte(f.expect),
      notes,
    },
  };
}

// myDeviceRowHTML(device, selected)：列表里的一行。
//
// 「选中」= 这件进这一趟检测（工单验收第 6 条「能选」）：按钮文案按 `selected` 两态，
// 与库内器件的 chip 是**同一条路**（点这里 → 加进 hwcheckUI.devices → 既有的 chip /
// 检测计划 / 生成都认它）。非 I2C 的行如实标一句"这一版不生成探测程序"——不让用户
// 期待一个不存在的能力。
export function myDeviceRowHTML(device, selected = false) {
  const d = device || {};
  const forms = d.address_forms || {};
  const busLabel = d.bus_label || BUS_LABELS[d.bus] || String(d.bus || "");
  const addressLine = forms.address7
    ? `地址 <span class="hwcheck-pin">${esc(forms.address7)}</span>`
      + `（8 位：读 ${esc(forms.read8)} / 写 ${esc(forms.write8)}）`
    : "";
  const registerLine = (d.register === null || d.register === undefined)
    ? ""
    : `身份寄存器 <span class="hwcheck-pin">${esc(hexField(d.register))}</span>`
      + (d.expect === null || d.expect === undefined
        ? "（没填期望值：板上只回显读到的字节）"
        : ` 期望 <span class="hwcheck-pin">${esc(hexField(d.expect))}</span>`);
  const noteLine = d.bus === "i2c" ? "" : `<span class="hwcheck-share">${esc(MY_DEVICE_NON_I2C_NOTE)}</span>`;
  const pick = selected
    ? `<button type="button" class="primary" data-my-device-pick="${esc(d.id)}"`
      + ' title="从这一趟检测里去掉（它的定义还留着）">✓ 已在这次检测里</button>'
    : `<button type="button" data-my-device-pick="${esc(d.id)}"`
      + ' title="把这件加进这一趟检测（与库内器件一起测）">加进这次检测</button>';
  return `<div class="hwcheck-my-device${selected ? " picked" : ""}"`
    + ` data-my-device-row="${esc(d.id)}">`
    + '<div class="hwcheck-my-device-head">'
    + `<span class="slug">${esc(d.id)}</span>`
    + `<span class="hwcheck-my-device-name">${esc(d.name)}</span>`
    + `<span class="badge">${esc(busLabel)}</span></div>`
    + `<div class="hwcheck-hint">${addressLine}`
    + (addressLine && registerLine ? " ｜ " : "") + registerLine + "</div>"
    + (d.notes ? `<div class="hwcheck-hint">备注：${esc(d.notes)}</div>` : "")
    + noteLine
    + '<div class="row">' + pick
    + `<button type="button" data-my-device-edit="${esc(d.id)}">编辑</button>`
    + `<button type="button" class="danger" data-my-device-del="${esc(d.id)}"`
    + ' title="删掉这件（连同你传的资料副本）">删除</button>'
    + "</div></div>";
}

// myDeviceEmptyHTML()：一件都还没建时的说明。「手上这件不在库里」不是错误状态
// ——它是这个栏目存在的理由，所以这句话要把入口说清楚。
export function myDeviceEmptyHTML() {
  return '<div class="muted">还没有「我的器件」。手上那件不在模块库里？'
    + "点上面的「+ 我的器件」把它的名称与地址填进来——保存后点它那行的"
    + "「加进这次检测」，它就会跟库内器件一起出现在检测计划里，下次不用重填。</div>";
}

// myDeviceListHTML(devices)：整块列表（空 = 空态那一句）。
export function myDeviceListHTML(devices, selectedIds = []) {
  const list = Array.isArray(devices) ? devices : [];
  if (!list.length) return myDeviceEmptyHTML();
  const selected = new Set(
    (Array.isArray(selectedIds) ? selectedIds : []).map((s) => String(s)));
  return list.map((d) => myDeviceRowHTML(d, selected.has(String((d && d.id) || "")))).join("");
}

// myDeviceFormHTML(form, error)：表单（+ 保存 / 取消 + 一句校验理由）。
// `error` 非空时**明说为什么**并把保存按钮置灰——"点了没反应"是最难查的一类界面。
export function myDeviceFormHTML(form, error = "") {
  const f = form || myDeviceFormBlank();
  const bus = String(f.bus || "i2c");
  const options = MY_DEVICE_BUS_OPTIONS.map((o) =>
    `<option value="${esc(o.value)}"${o.value === bus ? " selected" : ""}>${esc(o.label)}</option>`
  ).join("");
  return `<div class="hwcheck-my-device-form" data-my-device-form>
    <div class="row">
      <label class="hwcheck-my-device-field">id
        <input type="text" data-my-device-field="id" value="${esc(f.id)}"
               placeholder="mine_gyro（必须 mine_ 开头）"></label>
      <label class="hwcheck-my-device-field">名称
        <input type="text" data-my-device-field="name" value="${esc(f.name)}"
               placeholder="例：卖家给的六轴模块"></label>
      <label class="hwcheck-my-device-field">总线
        <select data-my-device-field="bus">${options}</select></label>
    </div>
    <div class="row">
      <label class="hwcheck-my-device-field">7 位地址
        <input type="text" data-my-device-field="address" value="${esc(f.address)}"
               placeholder="0x68（I2C 必填）"></label>
      <label class="hwcheck-my-device-field">身份寄存器
        <input type="text" data-my-device-field="register" value="${esc(f.register)}"
               placeholder="0x75（可选）"></label>
      <label class="hwcheck-my-device-field">期望值
        <input type="text" data-my-device-field="expect" value="${esc(f.expect)}"
               placeholder="0x68（可选；填了才判 OK/FAIL）"></label>
    </div>
    <label class="hwcheck-my-device-field wide">备注
      <input type="text" data-my-device-field="notes" value="${esc(f.notes)}"
             placeholder="可选：卖家页怎么说的、你从哪儿抄来的（会进清单与 AI 排障）"></label>
    <div data-my-device-address-preview-slot>${myDeviceAddressPreviewHTML(f.address, bus)}</div>
    <div class="row" style="margin-top: var(--space-2)">
      <button type="button" class="primary"${error ? " disabled" : ""} data-my-device-save>保存这件</button>
      <button type="button" data-my-device-cancel>取消</button>
      <span class="hwcheck-hint" data-my-device-form-error>${esc(error)}</span>
    </div>
    <div class="hwcheck-hint">件与平台无关：同一件在两个平台上都能测（地址与寄存器
      是器件的事实，总线脚由平台决定）。备注里那句「卖家页写的 WHO_AM_I」将来会
      进 AI 排障的上下文——写你手上有的关键事实就够。</div>
  </div>`;
}

// myDeviceEditTarget(devices, id)：要编辑的那件（找不到 = null）。
export function myDeviceEditTarget(devices, id) {
  const key = String(id == null ? "" : id);
  if (!key) return null;
  return (Array.isArray(devices) ? devices : []).find((d) => d && d.id === key) || null;
}

// myDeviceKnownSlugs(payload)：载荷里的库内 slug 集（缺键 = 空数组）。
export function myDeviceKnownSlugs(payload) {
  const data = payload || {};
  return Array.isArray(data.known_slugs) ? data.known_slugs.map((s) => String(s)) : [];
}

// myDeviceList(payload)：载荷里的自建件列表（缺键 = 空数组）。
export function myDeviceList(payload) {
  const data = payload || {};
  return Array.isArray(data.devices) ? data.devices : [];
}

// myDeviceSavedDevice(payload)：保存响应里的那件（缺 = null）。
export function myDeviceSavedDevice(payload) {
  const data = payload || {};
  return (data.device && typeof data.device === "object") ? data.device : null;
}
