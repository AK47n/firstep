// fx/code-compile.js — 代码栏编译纯函数（工单 code-tab-compile/03）
//
// 状态行 / 错误行 HTML 的纯件：胶水（ui/code-compile.js）只做 SSE 消费 /
// 自动保存 / 跳转 / DOM 事件绑定，本模块输出可单测的字符串。状态行文案 =
// fx/generate.js compileSummaryText 单源（生成页修复中心横幅与代码栏面板
// 共用，评审整改后不再各写一份）；本模块只做面板配色类与错误行 HTML。
// 模块约定见 fx/core.js 头部。
import { esc } from "./core.js";
import { compileSummaryText } from "./generate.js";

// AUTO_COMPILE_KEY：保存自动编译开关的 localStorage 键（工单
// code-editor-refine/10）——单源常量：状态栏 toggle 与读取判断共用（默认关
// = 无键/非 "1"）；键名沿既有 firstep.* 命名域（评审整改）。
export const AUTO_COMPILE_KEY = "firstep.autoCompileOnSave";

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

// SYSCFG_CONFLICT_KIND：配置级冲突条目的 kind 值（工单 02，与后端
// fix_errors.SYSCFG_CONFLICT_KIND 逐字一致）——SysConfig 的工程外设配置冲突
// （引脚被两个模块同时占用）没有文件行号、也**不是 LLM 能修的**（没有源码可
// 改）：前端据此把这类条目渲染成不可跳转的说明行，而不是「点开看源码」的错误行。
// 旧载荷 / 源码级条目不带 kind（缺省语义 = 源码级，向后兼容）。
export const SYSCFG_CONFLICT_KIND = "syscfg_conflict";

// isSyscfgConflict(entry)：条目是否配置级冲突（parsed_errors / parsed 同型
// [{path, line, message, kind?}]）。非对象 / 无 kind → false（源码级缺省）。
export function isSyscfgConflict(entry) {
  return !!entry && entry.kind === SYSCFG_CONFLICT_KIND;
}

// compileErrorRowsHTML(errors)：结构化错误列表（parsed_errors 同型
// [{path, line, message, kind?}]）→ 可点击行；data-compile-path / data-compile-line
// 交给胶水层委托跳转。配置级冲突（kind="syscfg_conflict"）例外：无源码可跳，
// 渲染成带「配置冲突」标签的不可点击行（工单 02——真机 2026H 的 7 条 Resource
// conflict 此前整段不可见，用户拿不到任何可读原因）。空数组 → 空提示
// （无结构化错误信息——降级/解析失败）。
export function compileErrorRowsHTML(errors) {
  const list = errors || [];
  if (!list.length) {
    return '<span class="muted">（无结构化错误信息——可去生成页看编译输出原文）</span>';
  }
  return list.map((er) => {
    const path = String(er.path == null ? "" : er.path);
    const line = Number(er.line) || 0;
    const loc = path ? path + ":" + line : String(line || "");
    const msg = esc(er.message || "");
    if (isSyscfgConflict(er)) {
      return '<div class="code-compile-error code-compile-error-conflict">'
        + '<span class="code-compile-path">配置冲突'
        + (path ? "（来自 " + esc(path) + "）" : "") + "</span>"
        + '<span class="code-compile-msg">' + msg + "</span>"
        + "</div>";
    }
    return '<button type="button" class="code-compile-error"'
      + ' data-compile-path="' + esc(path) + '" data-compile-line="' + line + '"'
      + ' title="在代码栏打开并定位 ' + esc(loc) + '">'
      + '<span class="code-compile-path">' + esc(loc) + "</span>"
      + '<span class="code-compile-msg">' + msg + "</span>"
      + "</button>";
  }).join("");
}

// compileErrorPathNorm(path)：编译错误 path 归一（POSIX 分隔、去 . 段、保留 ..
// 段）——编辑器错误行映射与生成页修复中心 fixKeyOf/fixKeyBasename 共用
// （工单 05 评审整改单源化：原 generate-fix 私有归一收敛到本模块；跨簇同域
// 逻辑不各写一份）。空/undefined → ""。
export function compileErrorPathNorm(path) {
  return String(path == null ? "" : path).replace(/\\/g, "/")
    .split("/").filter((s) => s && s !== ".").join("/");
}

// compileErrorPathBase(path)：归一路径的 basename（末段；空路径 → ""）——
// compileErrorLinesForFile 文件名兜底与修复中心 fixKeyBasename 共用。
export function compileErrorPathBase(path) {
  return compileErrorPathNorm(path).split("/").pop() || "";
}

// compileErrorLinesForFile(errors, filePath)：parsed_errors 同型列表 → 当前文件
// （tab.path，如 "Core/Src/main.c"）应标记的错误行 [{line,message}] 按 line 升序
// ——错误行标记（行号色点 + 全行下划线/底色 + title 悬停）的数据源（工单
// code-editor-refine/05）。path 用 compileErrorPathNorm/Base 归一；匹配顺序 =
// 归一全等 → 前缀 ../ 后缀 → 文件名兜底（basename 相同即算——跨目录同名罕见，
// 胜过漏标）；line 0 / 非法跳过（无行号信息不可定位）；同行多条 message 以
// 换行合并（title 多行悬停）。
export function compileErrorLinesForFile(errors, filePath) {
  const list = Array.isArray(errors) ? errors : [];
  const target = compileErrorPathNorm(filePath);
  const targetBase = compileErrorPathBase(filePath);
  const byLine = new Map();
  for (const er of list) {
    const p = compileErrorPathNorm(er && er.path);
    if (!p) continue;
    const base = compileErrorPathBase(p);
    if (p !== target && !p.endsWith("/" + target) && base !== targetBase) continue;
    const line = Number(er.line);
    if (!Number.isFinite(line) || line <= 0) continue;
    const msg = String(er.message == null ? "" : er.message);
    if (byLine.has(line)) byLine.set(line, byLine.get(line) + "\n" + msg);
    else byLine.set(line, msg);
  }
  return [...byLine.entries()].map(([line, message]) => ({ line, message }))
    .sort((a, b) => a.line - b.line);
}

if (typeof window !== "undefined") {
  Object.assign(window, {
    compileStatusText,
    compileStatusClass,
    compileErrorRowsHTML,
    compileErrorLinesForFile,
    compileErrorPathNorm,
    compileErrorPathBase,
    isSyscfgConflict,
    SYSCFG_CONFLICT_KIND,
    AUTO_COMPILE_KEY,
  });
}
