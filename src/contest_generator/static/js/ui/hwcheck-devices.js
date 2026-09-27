// ui/hwcheck-devices.js — 「我的器件」（库外件）的增删改查与草稿（工单 hwcheck-hygiene/11）。
//
// 正文由 `ui/hwcheck.js` 整段搬来（函数体与注释逐字保留），另加四个委托处理分支
// （原 initHwcheck 里那几个匿名回调整段搬来，正文一个字没改）。
//
// 分工：**渲染在核心件**（renderMyDevices / renderHwcheckDevices），本件管"点了之后
// 做什么"——表单状态机、请求、校验理由。件与平台无关（切平台不清这些键）。
//
// 依赖方向（单源 = ui/hwcheck-core.js 头部）：本件 → 动作件（删一件后要重取板侧视图）、
// 核心件。**不 import 入口**——那会成环。

import {
  $,
  apiDelete,
  apiGet,
  apiPost,
  handle,
  toast,
  toastError,
} from "/js/app.js";
import {
  myDeviceAddressPreviewHTML,
  myDeviceDraftToForm,
  myDeviceEditTarget,
  myDeviceFormBlank,
  myDeviceFormCheck,
  myDeviceFormFromPayload,
  myDeviceKnownSlugs,
  myDeviceList,
  myDevicePayload,
  myDeviceSavedDevice,
  myDeviceSlugFromName,
} from "/js/fx/my-devices.js";
import { addHwcheckDevice, refreshHwcheckView } from "/js/ui/hwcheck-actions.js";
import {
  hwcheckUI,
  renderHwcheckDevices,
  renderHwcheckHandoff,
  renderMyDevices,
  selectorValue,
  setPendingFocus,
} from "/js/ui/hwcheck-core.js";
// myDeviceFormError(form)：按当前表单算一次校验理由（保存按钮与提示共用同一句）。
// `myEditId` = 正在编辑的那一件的 id（新建时空串）——**必须传**：不传的话编辑
// 自己那件会被判成"撞已有件"，保存按钮永远灰着（编辑功能整个用不了）。
function myDeviceFormError(form) {
  return myDeviceFormCheck(
    form,
    hwcheckUI.knownSlugs,
    hwcheckUI.myDevices.map((d) => (d && d.id) || "").filter(Boolean),
    hwcheckUI.myEditId,
  );
}

// syncMyDeviceForm()：**就地把输入框里的字交给 state**，并只更新那两个小节点
// （地址预览 + 校验理由/保存按钮）。
//
// ⚠ 这里**绝不能整块重绘表单**（本单浏览器验收当场抓到的 bug）：整块重绘 =
// 用户正在打字的那个 `<input>` 被换掉——浏览器里看着就是"打一个字表单就清空、
// 后面的字全丢"，而按钮与预览还像是正常的。所以本函数一个 `innerHTML =` 都不做
// （整块重绘只发生在"打开 / 编辑 / 保存 / 取消"这类显式动作上）。
function syncMyDeviceForm() {
  const box = $("my-devices-form");
  if (!box || !hwcheckUI.myForm) return;
  const form = { ...hwcheckUI.myForm };
  box.querySelectorAll("[data-my-device-field]").forEach((el) => {
    form[el.dataset.myDeviceField] = el.value;
  });
  hwcheckUI.myForm = form;
  hwcheckUI.myFormError = myDeviceFormError(form);
  const preview = box.querySelector("[data-my-device-address-preview-slot]");
  if (preview) {
    preview.innerHTML = myDeviceAddressPreviewHTML(form.address, form.bus);
  }
  const save = box.querySelector("[data-my-device-save]");
  if (save) save.disabled = !!hwcheckUI.myFormError;
  const errorBox = box.querySelector("[data-my-device-form-error]");
  if (errorBox) errorBox.textContent = hwcheckUI.myFormError;
}

// closeMyDeviceForm()：收起表单——**唯一出口**（新建 / 编辑共用一份表单状态，
// 三处（保存成功 / 取消 / 删掉的正是编辑对象）都必须连 `myEditId` 一起清掉：
// 漏清一处，下次"新建"就会被上一条的 id 顶掉"撞已有件"判据）。
// 资料原文与草稿**一起清**（工单 08）：它们是"这一件"的来源记录——留着的话，
// 下一件（尤其是编辑另一件）保存时会把上一件的资料 / 草稿悄悄写进它的条目。
function closeMyDeviceForm() {
  hwcheckUI.myForm = null;
  hwcheckUI.myEditId = "";
  hwcheckUI.myFormError = "";
  hwcheckUI.myMaterial = "";
  hwcheckUI.myMaterialMessage = "";
  hwcheckUI.myDraft = null;
  hwcheckUI.myDraftApplied = false;
}

export function openMyDeviceForm(device) {
  hwcheckUI.myForm = device
    ? myDeviceFormFromPayload(device) : myDeviceFormBlank();
  // 正在编辑的那一件（新建 = 空串）：校验"撞已有件"时要把自己排除在外
  hwcheckUI.myEditId = device ? String(device.id || "") : "";
  hwcheckUI.myFormError = myDeviceFormError(hwcheckUI.myForm);
  if (device) hwcheckUI.myDraftApplied = false;  // 表单换成编辑态了，"已填进表单"那句不再成立
  if (device) {
    // 编辑已有器件时不带任何残留的资料 / 草稿（跨件来源污染的另一半：
    // 表单侧 applyMyDraft 挡了"填"，保存侧这里挡"发"）
    hwcheckUI.myMaterial = "";
    hwcheckUI.myDraft = null;
  }
  renderMyDevices();
}

// —— 资料 → 事实草稿（工单 hwcheck-unknown-device/07）——
// 抽取 / 填表都在服务端判过形状了；这里只管发请求、把载荷交给 fx、把降级原因
// 说成人话。**草稿永远不会自己保存**：它只变成表单预填，保存走既有的
// saveMyDevice（服务端照旧全量校验）。

// applyDraftResponse(payload)：抽取响应 → 状态（成功 = 草稿 + 填进表单；
// 降级 = 不报错，说清"直接手填"——票面硬要求：AI 不可用流程不阻断）。
function applyDraftResponse(payload) {
  if (payload && payload.degraded) {
    hwcheckUI.myDraft = null;
    hwcheckUI.myDraftApplied = false;
    hwcheckUI.myMaterialMessage =
      "AI 没接上（" + String(payload.message || "原因不明") + "）——直接手填，一样能测";
    return;
  }
  hwcheckUI.myDraft = payload ? payload.draft : null;
  hwcheckUI.myDraftApplied = false;
  if (hwcheckUI.myDraft) applyMyDraft();
}

// applyMyDraft()：把草稿填进表单（可再改）。**只用于新建**：正在编辑已有器件时
// 草稿不许覆盖（编辑态保存按 id 幂等覆盖，填错一件会冲掉那件的原事实）。
function applyMyDraft() {
  if (!hwcheckUI.myDraft) return;
  if (hwcheckUI.myEditId) {
    hwcheckUI.myMaterialMessage =
      "正在编辑已有的器件——草稿只用于新建；先「取消」再抽一次";
    return;
  }
  hwcheckUI.myForm = myDeviceDraftToForm(hwcheckUI.myDraft, hwcheckUI.myForm);
  hwcheckUI.myFormError = myDeviceFormError(hwcheckUI.myForm);
  hwcheckUI.myDraftApplied = true;
}

async function draftMyDevice() {
  if (hwcheckUI.myMaterialBusy) return;
  const text = String(hwcheckUI.myMaterial || "").trim();
  if (!text) {
    hwcheckUI.myMaterialMessage = "先贴一段资料文字（或选一个文件）——没有资料就直接手填";
    renderMyDevices();
    return;
  }
  hwcheckUI.myMaterialBusy = true;
  hwcheckUI.myMaterialMessage = "";
  renderMyDevices();
  try {
    applyDraftResponse(await apiPost("/api/my-devices/draft", { text }));
  } catch (e) {
    hwcheckUI.myMaterialMessage = e && e.message ? e.message : String(e);
  } finally {
    hwcheckUI.myMaterialBusy = false;
  }
  renderMyDevices();
}

// draftFromMyDeviceFile(file)：文件先走**既有抽取通道**（/api/extract，赛题页
// 同一条路——不新开第二条抽取路），拿回文本再进草稿端点。抽出的文字回填到
// 文本框：用户看得到送出去的是什么（知情权）。
async function draftFromMyDeviceFile(file) {
  if (!file || hwcheckUI.myMaterialBusy) return;
  hwcheckUI.myMaterialBusy = true;
  hwcheckUI.myMaterialMessage = "";
  renderMyDevices();
  try {
    const form = new FormData();
    form.append("upload", file);
    const data = await handle(await fetch("/api/extract", { method: "POST", body: form }));
    const text = String((data && data.text) || "");
    if (!text.trim()) {
      hwcheckUI.myMaterialMessage = "这份文件抽不出文字——换个文件，或直接手填";
      return;
    }
    hwcheckUI.myMaterial = text;
    applyDraftResponse(await apiPost("/api/my-devices/draft", { text }));
  } catch (e) {
    hwcheckUI.myMaterialMessage = e && e.message ? e.message : String(e);
  } finally {
    hwcheckUI.myMaterialBusy = false;
  }
  renderMyDevices();
}

export async function loadMyDevices() {
  try {
    const payload = await apiGet("/api/my-devices");
    hwcheckUI.myDevices = myDeviceList(payload);
    hwcheckUI.knownSlugs = myDeviceKnownSlugs(payload);
    hwcheckUI.myError = "";
  } catch (e) {
    hwcheckUI.myDevices = [];
    hwcheckUI.myError = e && e.message ? e.message : String(e);
  }
  renderMyDevices();
  renderHwcheckHandoff();   // 带入块的分类要这份清单（哪几件是库外自建件）
}

// saveMyDevice()：提交这一件（按 id 幂等）。失败 = 服务端 400 的中文原样带出
// （表单不关、用户填的东西一个字不丢——这正是"当场点名要求改名"那条判据的用法）。
async function saveMyDevice() {
  if (!hwcheckUI.myForm || hwcheckUI.myBusy) return;
  hwcheckUI.myFormError = myDeviceFormError(hwcheckUI.myForm);
  if (hwcheckUI.myFormError) {
    renderMyDevices();
    return;
  }
  hwcheckUI.myBusy = true;
  try {
    const payload = myDevicePayload(hwcheckUI.myForm);
    // 资料原文与抽取草稿随保存落进条目（工单 08：归档的源头）。没给 = 服务端
    // 保留旧的那份——改个名字不该抹掉"当时凭什么填了那个地址"。
    if (String(hwcheckUI.myMaterial || "").trim()) {
      payload.material_text = hwcheckUI.myMaterial;
    }
    if (hwcheckUI.myDraft) payload.draft = hwcheckUI.myDraft;
    const saved = await apiPost("/api/my-devices", payload);
    const savedDevice = myDeviceSavedDevice(saved);
    closeMyDeviceForm();
    await loadMyDevices();
    toast("ok", "已存进「我的器件」：" + ((savedDevice && savedDevice.name) || ""));
  } catch (e) {
    hwcheckUI.myFormError = e && e.message ? e.message : String(e);
  } finally {
    hwcheckUI.myBusy = false;
  }
  renderMyDevices();
}

// deleteMyDevice(id)：删掉一件；同时把它从**这次检测的选择**里去掉。
// 为什么不"直接不管"：删掉之后那个 id 既不在库里、也不再是自建件，下次预览就是
// 400「未知模块」——而页面上那个 chip 还挂着，学生根本不知道是自己刚删的那件。
async function deleteMyDevice(id) {
  if (!id || hwcheckUI.myBusy) return;
  hwcheckUI.myBusy = true;
  try {
    await apiDelete("/api/my-devices/" + encodeURIComponent(id));
    if (hwcheckUI.myForm && hwcheckUI.myForm.id === id) closeMyDeviceForm();
    if ((hwcheckUI.devices || []).includes(id)) {
      hwcheckUI.devices = hwcheckUI.devices.filter((slug) => slug !== id);
      renderHwcheckDevices();
      refreshHwcheckView();
    }
    await loadMyDevices();
    toast("ok", "已删掉这件：" + id);
  } catch (e) {
    toastError(e, "删不掉这件器件");
  } finally {
    hwcheckUI.myBusy = false;
  }
  renderMyDevices();
}

// —— 事件委托的处理分支（工单 hwcheck-hygiene/11）——
// 由入口 `ui/hwcheck.js` 的接线调用：这里只放「点了之后做什么」，选择器的归属
// 仍在入口的接线行上（一处只写一遍）。

// handleMyDeviceClick(e)：「我的器件」那一块的全部点击分支（加选 / 改 / 删 / 保存 
// /抽草稿 / 填草稿 / 弃草稿 / 取消），全部走容器级委托（innerHTML 全量重绘后仍有效）
// 。
export function handleMyDeviceClick(e) {
  // 加选 / 取消（工单验收第 6 条「能选」）：走**库内器件同一条路**
  // （addHwcheckDevice → hwcheckUI.devices → 既有 chip / 检测计划 / 生成都认它），
  // 不另造一套"自建件的选择"。
  const pick = e.target.closest("[data-my-device-pick]");
  if (pick) {
    const id = pick.dataset.myDevicePick;
    // 重绘后焦点回这一行（工单 hwcheck-hygiene/06）：`renderMyDevices()` 换掉整块
    // innerHTML，不回焦点的话键盘 / 连续点选都会掉回 body。
    setPendingFocus(`[data-my-device-pick="${selectorValue(id)}"]`);
    addHwcheckDevice(id, !(hwcheckUI.devices || []).includes(id));
    renderMyDevices();   // 按钮两态跟着选择变（chip 那边由 addHwcheckDevice 重绘）
    return;
  }
  const edit = e.target.closest("[data-my-device-edit]");
  if (edit) {
    openMyDeviceForm(myDeviceEditTarget(hwcheckUI.myDevices, edit.dataset.myDeviceEdit));
    return;
  }
  const del = e.target.closest("[data-my-device-del]");
  if (del) {
    // 删掉之后那一行**不在了**：焦点落到"新建"按钮上（不回 body，键盘还能继续走）
    setPendingFocus("#btn-my-device-new");
    deleteMyDevice(del.dataset.myDeviceDel);
    return;
  }
  if (e.target.closest("[data-my-device-save]")) {
    saveMyDevice();
    return;
  }
  if (e.target.closest("[data-my-device-draft]")) {
    draftMyDevice();
    return;
  }
  if (e.target.closest("[data-my-device-draft-apply]")) {
    applyMyDraft();
    renderMyDevices();
    return;
  }
  if (e.target.closest("[data-my-device-draft-dismiss]")) {
    hwcheckUI.myDraft = null;
    hwcheckUI.myDraftApplied = false;
    renderMyDevices();
    return;
  }
  if (e.target.closest("[data-my-device-cancel]")) {
    closeMyDeviceForm();
    renderMyDevices();
  }
}

// handleMyDeviceInput(e)：表单输入——`input` 覆盖打字（地址预览与校验理由实时跟上）
// ；资料文本框只同步 state，**不许重绘**（正在打字，同表单纪律）。
export function handleMyDeviceInput(e) {
  if (e.target.matches("[data-my-device-material]")) {
    hwcheckUI.myMaterial = e.target.value;
    return;
  }
  if (e.target.closest("[data-my-device-field]")) syncMyDeviceForm();
}

// handleMyDeviceChange(e)：`change` 单独接一次是为了 `<select>`（总线下拉在部分浏览器上不触发 
// input）；资料文件选择走既有抽取通道。
export function handleMyDeviceChange(e) {
  const fileInput = e.target.closest("[data-my-device-file]");
  if (fileInput) {
    const file = fileInput.files && fileInput.files[0];
    if (file) draftFromMyDeviceFile(file);
    fileInput.value = "";   // 清掉选择：允许重复选同一个文件再抽一次
    return;
  }
  if (e.target.closest("[data-my-device-field]")) syncMyDeviceForm();
}

// suggestMyDeviceId(myBox, e)：名称 → id 建议（**捕获阶段**，照原样）。只在 id 
// 还是空 /还是上一次自动填的那值时补一下，用户手填过 id 就不动它。
export function suggestMyDeviceId(myBox, e) {
  const el = e.target.closest('[data-my-device-field="name"]');
  if (!el || !hwcheckUI.myForm) return;
  const current = String(hwcheckUI.myForm.id || "");
  if (current && !/^mine_(device)?$/.test(current)) return;
  const idBox = myBox.querySelector('[data-my-device-field="id"]');
  if (!idBox) return;
  idBox.value = myDeviceSlugFromName(el.value);
  syncMyDeviceForm();
}
