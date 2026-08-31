// fx/code-compile.js — 代码栏编译纯函数（工单 code-tab-compile/03）
//
// 状态行 / 错误行 HTML 的纯件：胶水（ui/code-compile.js）只做 SSE 消费 /
// 自动保存 / 跳转 / DOM 事件绑定，本模块输出可单测的字符串。状态行文案 =
// fx/generate.js compileSummaryText 单源（生成页修复中心横幅与代码栏面板
// 共用，评审整改后不再各写一份）；本模块只做面板配色类与错误行 HTML。
// 模块约定见 fx/core.js 头部。
import { esc } from "./core.js";
import { compileSummaryText } from "./generate.js";

// compileStatusText(done)：/api/compile done 载荷 → 面板状态行（单源别名——
// 实现 = compileSummaryText，见模块头注释）；done 为空 → 空串。
export const compileStatusText = compileSummaryText;

// compileStatusClass(done)：状态行配色类（ok / err / ""——运行中与超时无着色）。
export function compileStatusClass(done) {
  if (!done) return "";
  if (done.passed && !done.timed_out) return "ok";
  if (!done.passed && !done.timed_out) return "err";
  return "";
}

// compileErrorRowsHTML(errors)：结构化错误列表（parsed_errors 同型
// [{path, line, message}]）→ 可点击行；data-compile-path / data-compile-line
// 交给胶水层委托跳转。空数组 → 空提示（无结构化错误信息——降级/解析失败）。
export function compileErrorRowsHTML(errors) {
  const list = errors || [];
  if (!list.length) {
    return '<span class="muted">（无结构化错误信息——可去生成页看编译输出原文）</span>';
  }
  return list.map((er) => {
    const path = String(er.path == null ? "" : er.path);
    const line = Number(er.line) || 0;
    const loc = path ? path + ":" + line : String(line || "");
    return '<button type="button" class="code-compile-error"'
      + ' data-compile-path="' + esc(path) + '" data-compile-line="' + line + '"'
      + ' title="在代码栏打开并定位 ' + esc(loc) + '">'
      + '<span class="code-compile-path">' + esc(loc) + "</span>"
      + '<span class="code-compile-msg">' + esc(er.message || "") + "</span>"
      + "</button>";
  }).join("");
}

if (typeof window !== "undefined") {
  Object.assign(window, {
    compileStatusText,
    compileStatusClass,
    compileErrorRowsHTML,
  });
}
