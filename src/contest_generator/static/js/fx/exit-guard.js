// fx/exit-guard.js — 未保存退出保护纯件（工单 code-editor-refine/01）
//
// 目录切换前「保存全部并切换 / 放弃修改并切换 / 取消」三选模态的消息与
// overlay HTML。判据（哪些标签算脏）由调用方用 fx/codeeditor.js
// dirtySavableTabs 单源给出——本模块只做展示层纯函数：计数、清单截断、
// HTML 转义（esc 单源取自 fx/core.js），事件接线在 ui/codeeditor.js。
import { esc } from "./core.js";

// 清单最多显示条数（超出以「等 N 个」省略——弹窗只提示用户有谁，不刷屏）
export const UNSAVED_SWITCH_LIST_MAX = 8;

// unsavedSwitchMessage(dir, dirtyTabs)：目录切换确认消息（HTML 片段，全部
// 转义）——dirtyTabs 为已按未保存判据过滤的标签数组（只需 .path）。
export function unsavedSwitchMessage(dir, dirtyTabs) {
  const list0 = dirtyTabs || [];
  const paths = list0.map((t) => t.path);
  const shown = paths.slice(0, UNSAVED_SWITCH_LIST_MAX);
  const more = paths.length - shown.length;
  const list = shown.map((p) => "「" + esc(p) + "」").join("、")
    + (more > 0 ? " 等 " + more + " 个" : "");
  return "切换到「" + esc(dir) + "」前，有 " + paths.length
    + " 个文件未保存" + (list ? "：" + list : "") + "。"
    + "选择「保存全部并切换」将先保存文件；"
    + "「放弃修改并切换」将丢弃这些修改；"
    + "「取消」保留当前编辑不动。";
}

// unsavedSwitchModalHTML(opts)：三选模态内容纯函数——opts = {dir,
// dirtyTabs}；按钮 data-unsaved-action="save|discard|cancel" 交事件层。
// 样式复用 confirm-modal / pdf-detail-actions 既有 token（深浅主题随动）。
export function unsavedSwitchModalHTML({ dir, dirtyTabs }) {
  return `<div class="ref-files-modal confirm-modal code-unsaved-modal">
    <div class="ref-files-head"><strong>${esc("有未保存的修改")}</strong>
      <button class="ref-files-close" title="关闭">×</button></div>
    <div class="ref-detail-scroll"><div class="confirm-message">${unsavedSwitchMessage(dir, dirtyTabs)}</div></div>
    <div class="pdf-detail-actions">
      <button type="button" class="primary" data-unsaved-action="save">${esc("保存全部并切换")}</button>
      <button type="button" data-unsaved-action="discard">${esc("放弃修改并切换")}</button>
      <button type="button" data-confirm-cancel data-unsaved-action="cancel">${esc("取消")}</button>
    </div>
  </div>`;
}
