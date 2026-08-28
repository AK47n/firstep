// ui/delivery.js — 生成页 · 交付卡胶水（工单 delivery-suite/02）：打开工程 /
// 交付检查 / 一键打包三个动作。执行体 = /api/delivery/open-ide|check|package
// 同步端点（flash 端点同构）；busy 闸共享 tasks.busy（tasksSetBusy 全局闸——
// 与任务执行 / 参数流程互斥，防弹窗与写盘竞争）；目录取 reviseGetDir
//（「修订与深化」卡已加载上下文，主写簇归 generate-revise.js）。
import { $, apiPost, toast } from "/js/app.js";
import { deliveryCheckHTML, deliveryPackageHTML } from "/js/fx/delivery.js";
import { reviseGetDir } from "./generate-revise.js";
import { tasksSetBusy, tasksIsBusy } from "./generate-tasks.js";

const state = { busy: false };

function dir() {
  return reviseGetDir();
}

function deliverySetBusy(busy) {
  state.busy = busy;
  tasksSetBusy(busy);
  for (const id of ["btn-delivery-open", "btn-delivery-check", "btn-delivery-package"]) {
    const btn = $(id);
    if (btn) btn.disabled = busy;
  }
}

async function deliveryRun(action, render, okText) {
  const outputDir = dir();
  if (!outputDir) {
    toast("info", "请先加载输出目录（「修订与深化」卡）再操作");
    return;
  }
  if (tasksIsBusy() || state.busy) {
    toast("info", "有任务正在执行中，请等当前任务完成后再操作");
    return;
  }
  deliverySetBusy(true);
  try {
    const data = await apiPost("/api/delivery/" + action, { output_dir: outputDir });
    render(data);
    toast("ok", okText(data));
  } catch (e) {
    toast("error", e.message);
  } finally {
    deliverySetBusy(false);
  }
}

export async function deliveryOpen() {
  await deliveryRun(
    "open-ide", () => {}, (data) => data.message || "已打开工程。"
  );
}

export async function deliveryCheck() {
  await deliveryRun(
    "check",
    (data) => { $("delivery-result").innerHTML = deliveryCheckHTML(data); },
    (data) => data.ok ? "全部步骤完成，可以打包交付。" : "还有步骤未完成，详见下方清单。"
  );
}

export async function deliveryPackage() {
  await deliveryRun(
    "package",
    (data) => { $("delivery-result").innerHTML = deliveryPackageHTML(data); },
    (data) => "已打包：" + data.zip_path
  );
}

export function deliveryReset() {
  state.busy = false;
  const result = $("delivery-result");
  if (result) result.innerHTML = "";
}

$("btn-delivery-open").addEventListener("click", () => deliveryOpen());
$("btn-delivery-check").addEventListener("click", () => deliveryCheck());
$("btn-delivery-package").addEventListener("click", () => deliveryPackage());
// 输出目录切换（加载其他工程 / 修订重生成清清单）→ 清结果，防跨工程误读
window.addEventListener("revise-context-loaded", () => deliveryReset());
window.addEventListener("tasks-invalidated", () => deliveryReset());

Object.assign(window, { deliveryOpen, deliveryCheck, deliveryPackage, deliveryReset });
