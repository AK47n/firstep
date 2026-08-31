// fx/mainc-sync.js — main.c 磁盘同步状态行的纯函数（工单 mainc-codeview-bridge/01）
//
// 生成页步骤 8（main.c 编辑框）与「代码」tab（代码查看器）的事实同步：
// 生成成功后显示「已写入磁盘」，任务/深化/修订改过磁盘后差异检测提示
// 「磁盘 main.c 已更新 → 加载」（工单 02 消费同一判定）。模块约定见
// fx/core.js 头部；esc 单源取 fx/core.js。
import { esc } from "./core.js";

// maincDiskState(state)：状态行语义——label 文案 + kind 样式类（ok/warn/''）。
// state 取值：written（生成写入后默认态）/ changed（磁盘 ≠ 编辑框，等待加载）/
// synced（编辑框 = 磁盘，显式核对后）；unknown → 空（不渲染）。
// dir 参数供 HTML 渲染使用（state 本身不持目录）。
export function maincDiskState(state) {
  switch (state) {
    case "written": return { kind: "ok", label: "main.c 已写入磁盘" };
    case "changed": return { kind: "warn", label: "磁盘 main.c 已更新" };
    case "synced": return { kind: "ok", label: "已同步磁盘版本" };
    default: return { kind: "", label: "" };
  }
}

// maincDiskStateHTML(state, dir)：状态行完整标记——标签 + 目录（esc 转义）+
// 「从磁盘重新加载 / 加载为编辑内容」按钮（changed 态文案提示覆盖语义）。
// 未知态返回空串（调用方隐藏容器）。
export function maincDiskStateHTML(state, dir) {
  const meta = maincDiskState(state);
  if (!meta.label) return "";
  const dirText = dir
    ? '<span class="mainc-disk-dir"> ' + esc(dir) + "</span>"
    : "";
  const btnText = state === "changed" ? "加载为编辑内容" : "从磁盘重新加载";
  return '<span class="mainc-disk-label ' + meta.kind + '">' + meta.label + dirText
    + "</span><button type=\"button\" class=\"act mainc-disk-reload\" data-mainc-reload>"
    + btnText + "</button>";
}

// maincDiffers(a, b)：磁盘文本 vs 编辑框文本的逐字节差异判定；
// null/undefined 防御为空串（读失败 / 空内容场景不误判差异）。
export function maincDiffers(a, b) {
  return String(a == null ? "" : a) !== String(b == null ? "" : b);
}

if (typeof window !== "undefined") {
  Object.assign(window, { maincDiskState, maincDiskStateHTML, maincDiffers });
}
