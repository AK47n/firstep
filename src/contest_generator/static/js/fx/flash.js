// fx/flash.js — 烧录展示纯函数（工单 flash-deploy/02）：忙碌文案 / 结果行 /
// 指引卡 / 输出明细 / 命令复制行。数据形状 = 后端 /api/flash 载荷
// {ok, tool{kind,exe,display}, command[], command_text, firmware, output,
// message, timed_out, duration, exit_code}；400 时走 FlashError 中文 message
//（flashGuideHTML 兜底渲染）。共享件用 esc（fx/core.js）。模块约定见
// fx/core.js 头部。
import { esc } from "./core.js";

/** 烧录中状态文案（前端 busy 防重期间的提示，spec 故事 7「烧录中 UI 明确
 * 状态与按钮防重」）：指定平台时带上探针名（mspm0 = XDS110 / stm32 =
 * ST-Link），未知平台给通用文案。 */
export function flashBusyText(platform) {
  const probe = platform === "mspm0" ? "XDS110"
    : platform === "stm32" ? "ST-Link" : "烧录探针";
  return "烧录中…（" + probe + "，请确认探针连接，勿拔线）";
}

/** 烧录结果行（spec 故事 2/4/6）：ok → ✓ 已烧录 + 工具 + 耗时 + 固件路径 +
 * 输出明细 + 命令复制；失败（工具报错 / 探针未接 / 超时）→ ✗ + message +
 * 超时标注 + 输出明细 + 命令复制。空载荷 = 空串（防御）。 */
export function flashResultHTML(data) {
  if (!data) return "";
  const duration = (data.duration !== undefined && data.duration !== null)
    ? ' <span class="muted">（' + Number(data.duration).toFixed(1) + "s）</span>"
    : "";
  if (data.ok) {
    return '<div class="reason">'
      + '<span class="ok" style="font-weight:600">✓ 已烧录</span> '
      + esc(data.message || "烧录成功")
      + duration
      + ' <span class="muted">工具：' + esc((data.tool || {}).display || "") + "</span>"
      + '<div class="muted" style="margin-top:2px">固件：<span class="slug">'
      + esc(data.firmware || "") + "</span></div>"
      + flashOutputHTML(data.output)
      + flashCommandHTML(data.command_text)
      + "</div>";
  }
  return '<div class="reason">'
    + '<span style="color:var(--danger);font-weight:600">✗ 烧录未成功</span> '
    + esc(data.message || "烧录失败，请查看下方输出")
    + (data.timed_out ? ' <span class="muted">（超时）</span>' : "")
    + flashOutputHTML(data.output)
    + flashCommandHTML(data.command_text)
    + "</div>";
}

/** 指引卡（spec 故事 4/5：工具缺失 / 产物缺失不甩裸报错）：后端 FlashError
 * 的中文 message（已含安装 / 配置指引）渲染成显眼卡片——与结果行区分开，
 * 红黄边框一眼看出是「没就绪」而非「烧失败」；附「去设置页配置」按钮
 *（胶水层委托处理——切到设置 tab 填工具路径，spec 前端决策「设置页跳转」）。 */
export function flashGuideHTML(message) {
  return '<div class="reason" style="border:1px solid var(--warn, #e6a23c);'
    + 'border-radius:8px;padding:8px 10px">'
    + '<span style="color:var(--warn, #e6a23c);font-weight:600">烧录未就绪</span> '
    + esc(message || "烧录前置条件未就绪，请查看提示")
    + ' <button class="btn-flash-goto-settings">去设置页配置</button>'
    + "</div>";
}

/** 输出明细（可折叠，spec 故事 6「展示真实输出尾」）：后端已截尾 40 行；
 * 空输出 = 空串（不渲染空折叠框）。 */
export function flashOutputHTML(output) {
  if (!output) return "";
  return '<details style="margin-top:6px"><summary class="muted">'
    + "查看烧录输出（尾 40 行）</summary>"
    + '<pre class="result" style="max-height:240px;overflow:auto">'
    + esc(output) + "</pre></details>";
}

/** 命令复制行（spec 故事 4「一键复制命令」）：成功与失败都给出实际命令，
 * 复制按钮 data-cmd 携带全文（胶水层 document 级委托统一处理）。 */
export function flashCommandHTML(commandText) {
  if (!commandText) return "";
  return '<div class="muted" style="margin-top:4px">命令：<span class="slug">'
    + esc(commandText) + "</span>"
    + ' <button class="btn-flash-copy-cmd" data-cmd="' + esc(commandText)
    + '">复制</button></div>';
}

/** 任务结果面板的烧录控制行（工单 flash-deploy/02 评审整改：胶水层不拼
 * HTML——控制行结构单源在此，tasksRenderResult 只插入）：烧录按钮（data-dir
 * 由委托回读）+ 状态位 + 结果容器。dir 空 = 不渲染（无目录无烧录对象）。 */
export function flashPanelHTML(dir) {
  if (!dir) return "";
  return '<div class="row" style="margin-top:6px">'
    + '<button class="btn-task-flash" data-dir="' + esc(dir) + '">烧录到板子</button>'
    + '<span id="tasks-flash-status" class="muted" style="margin-left:8px"></span>'
    + "</div>"
    + '<div id="tasks-flash-result" style="margin-top:6px"></div>';
}

if (typeof window !== "undefined") {
  Object.assign(window, {
    flashBusyText, flashResultHTML, flashGuideHTML,
    flashOutputHTML, flashCommandHTML, flashPanelHTML,
  });
}
