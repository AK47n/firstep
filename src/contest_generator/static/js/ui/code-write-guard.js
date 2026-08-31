// ui/code-write-guard.js — 反向写盘守卫（工单 code-write-guard/01）
//
// 生成页写盘动作发起前调用 guardCodeTabWrite(actionLabel)：代码栏目录 =
// 生成上下文 且 有未保存文件 → 两键确认模态（「保存全部并继续」/「取消」）；
// 确认 → saveAllDirtyTabs（保存取消/失败 → false，动作中止 + toast）；
// 取消 → false（编辑保留）。无脏 / 非上下文 → true（直通零打扰）。
// 纯件在 fx/write-guard.js；接线点（5 个写盘入口）见工单 02。
import { toast } from "/js/app.js";
import { confirmModal } from "/js/ui/confirm.js";
import {
  writeGuardNeeded,
  writeGuardTitle,
  writeGuardMessage,
} from "/js/fx/write-guard.js";
import { dirtySavableTabCount, saveAllDirtyTabs } from "/js/ui/codeeditor.js";
import { isMainCDiskDir } from "/js/ui/codeview.js";

// guardCodeTabWrite(actionLabel)：返回 Promise<boolean>——true = 可以继续
// 写盘动作；false = 用户取消 / 保存未落盘，调用方应中止动作。
export async function guardCodeTabWrite(actionLabel) {
  const dirtyCount = dirtySavableTabCount();
  if (!writeGuardNeeded(isMainCDiskDir(), dirtyCount)) return true;
  const proceed = await confirmModal({
    title: writeGuardTitle(),
    message: writeGuardMessage(actionLabel, dirtyCount),
    confirmText: "保存全部并继续",
    cancelText: "取消",
  });
  if (!proceed) {
    toast("info", "已取消：代码栏未保存修改保留，动作未启动");
    return false;
  }
  const saved = await saveAllDirtyTabs();
  if (!saved.ok) {
    toast("info", "有未保存修改未落盘，动作已中止");
    return false;
  }
  return true;
}
