// boot-contract.mjs — 装载根契约的**判据单源**（工单 frontend-boot-module/01）。
//
// 为什么单独一个文件（照 import-usage.mjs / ui-dom-contract.mjs 先例）：判据要被三处用——
//   1. 守卫本体（fx-guard / static-import-guard / import-usage-guard / ui-dom-contract）
//   2. 红证脚本 `.scratch/frontend-boot-module/probe-01-red-proof.mjs`
//      （同一套判据作用在**收走前那个提交**的源码上）
//   3. 探针的判据强度自检（内存注入）
// 放在 `.test.mjs` 里会让 import 方顺带注册并运行那批用例。
//
// ## 五类不变量（判据全部是纯函数：源码文本 / 模块表进，违规清单出）
//
//   ① `indexHtmlImports(html)` = 0    —— 装载根不在 HTML 里（判据 ①）
//   ② `inlineDefinitions(html)` = 0   —— HTML 里零顶层 JS 定义（判据 ②）
//   ③ `bareLoads(root)` = 0 且 `wiringViolations(root, modules)` = 0
//                                      —— 零裸装载 ＋ 求值期零接线（判据 ③）
//   ④ `graphBreaks(...)` / `reachable(...)` —— 全图 import↔export 对账 + 从装载根可达（判据 ④）
//   ⑤ `unconsumedExports(...)` / `nonFunctionCallees(...)` —— **导出面**对账（工单
//      export-surface-guard/01，判据 D/T）：导出必须真有消费者（import 边）＋ 被调用的导出必须是
//      函数形态。④ 管"被 import 的名字有没有出处"，⑤ 管反向与形态——三条合起来把导出面夹住。
//
// ## 三个必须踩住的坑（都写进实现里了）
//
//   · **掩码必须按 UTF-16 码元切**（`split("")`，不是 `Array.from`）：源码里满是中文与
//     emoji（`✎/🗑`），码点数组与 `text[i]` 的下标在第一个星平面字符之后错位一格，
//     掩码范围整体偏移（实测：注释行的首个 `/` 掩不掉，冒出 30+ 条假副作用）。
//   · **正则字面量要单独识别**：本仓库是代码编辑器前端，`/["'`]/`、/```/g` 这类正则遍地；
//     把 `/` 一律当除号，正则里的引号/反引号会开启"字符串状态"，一路把几十行代码掩成空白
//     （实测：`fx/markdown.js` 的 `export function parseMarkdownBlocks` 被掩掉 →
//     全图对账误报 3 处"未导出"）。
//   · **注释与字符串**：`import {\n  // 注释\n  onFileSaved,\n} from …` 在现状里真实存在。
//     不做注释剥离的解析器会把注释文字当成导入名（第一版探针就在这里误报 2 处）。
//
// 判据**不绑写法**：判的是事实（HTML 里有没有 import / 模块求值期有没有副作用语句 /
// 每条具名 import 的目标模块是否真导出那个名字），不是源码形状。改名变量、拆行、
// `import { a as b }` 都算通过。

import { readFileSync, readdirSync, existsSync } from "node:fs";

/** 装载根在模块表里的键（图里的"根节点"，不属于图内节点）。本文件内部用。 */
const LOAD_ROOT_KEY = "boot.js";

// ---------------------------------------------------------------------------
// 掩码：把注释、字符串字面量与正则字面量的内容换成空格（保留换行与行结构）
//
// **两种口径、一份实现**（工单 module-import-usage/01）：
//   · `maskCommentsAndStrings`（`templateExpressions = false`）：模板串**整串**掩掉，含 `${…}`。
//     判据 D / T、图对账、接线全依赖它——语义与行为**一字不变**。
//   · `maskNonCode`（`templateExpressions = true`）：模板串按「**文本段**掩掉、`${…}` 表达式内部
//     **当代码**（内部照旧掩注释 / 字符串 / 正则 / 嵌套模板的文本段）」处理。
//
// 为什么必须有第二种口径：掩掉模板表达式对**判据 T**（"调用位 ⇒ 函数形态"）是**保守**的
// （漏报，不假红）；但对**「零未使用具名 import」**方向**相反**——`${esc(x)}` 里的 `esc` 会被
// 判成死的（**假红**），照它删就是运行时 `ReferenceError`。实测：naive 口径报 45 处，
// 其中 **33 处**是这种假红（工单 module-import-usage/01 的读数）。
// ---------------------------------------------------------------------------

const REGEX_ALLOWED_BEFORE = "(,=:[!&|?{};+-*%~^<>";
const KEYWORDS_BEFORE_REGEX = new Set([
  "return", "typeof", "case", "in", "of", "new", "delete", "void",
  "instanceof", "do", "else", "yield", "await",
]);

/**
 * 掩码**核心**（全仓唯一一份分词）→ 同长度文本：注释、字符串与正则字面量的**内容**变空格；
 * 引号/斜杠定界符与换行保留（列 0 判定与行号不受影响）。
 *
 * `templateExpressions = true` 时额外维护"模板状态"：模板字面量的**文本段**整段掩掉，
 * `${` 之后切回代码模式，用**花括号深度栈**找它自己的收尾 `}`（嵌套模板 / 表达式里的对象字面量
 * 都靠这个栈）。`false` 时模板串与普通字符串同款处理（整串掩掉），与本次改动前逐字符相同。
 */
function mask(text, templateExpressions) {
  const out = text.split("");                 // UTF-16 码元切（见文件头第 1 个坑）
  const blank = (from, to) => {
    for (let k = from; k < to && k < out.length; k++) if (out[k] !== "\n") out[k] = " ";
  };
  const tplStack = [];                        // 每个 `${` 一层：{ depth } = 表达式内的花括号深度
  let inTplText = false;                      // 当前在模板字面量的**文本段**（只掩、不算代码）
  let i = 0;
  let lastSig = "";                           // 上一个有意义的字符（判 `/` 是不是除号）
  let lastIdent = "";                         // 紧邻的上一个标识符（判 `return /re/` 这类）
  while (i < text.length) {
    const c = text[i];
    const next = text[i + 1];
    if (inTplText) {                          // 模板文本段：整段掩掉（只有 templateExpressions 口径会进来）
      if (c === "\\") { blank(i, i + 2); i += 2; continue; }
      if (c === "`") { inTplText = false; lastSig = "`"; lastIdent = ""; i++; continue; }
      if (c === "$" && next === "{") {
        // `$` 是**模板替换的语法**、不是标识符 —— 掩掉它（`{` 留着无所谓）。
        // 不掩的话，任何含模板串的模块里那个名为 `$` 的 import 都会被喂绿
        //（`(?<![\w$])\$(?![\w$])` 会匹配到 `${` 的 `$`），判据当场漏一处死 import。
        blank(i, i + 1);
        tplStack.push({ depth: 0 }); inTplText = false; i += 2; continue;
      }
      blank(i, i + 1); i++; continue;
    }
    if (/\s/.test(c)) { i++; continue; }
    if (c === "/" && next === "/") {                       // 行注释
      let j = i;
      while (j < text.length && text[j] !== "\n") j++;
      blank(i, j); i = j; continue;
    }
    if (c === "/" && next === "*") {                       // 块注释
      const end = text.indexOf("*/", i + 2);
      const j = end < 0 ? text.length : end + 2;
      blank(i, j); i = j; continue;
    }
    if (c === '"' || c === "'" || (c === "`" && !templateExpressions)) {   // 字符串 /（旧口径的）模板串
      let j = i + 1;
      while (j < text.length) {
        if (text[j] === "\\") { j += 2; continue; }
        if (text[j] === c) { j++; break; }
        if (c !== "`" && text[j] === "\n") break;          // 未闭合的单/双引号：行内止损
        j++;
      }
      blank(i + 1, j - 1);
      lastSig = c; lastIdent = ""; i = j; continue;
    }
    if (c === "`") {                                       // 模板串开头（表达式感知口径）
      inTplText = true; lastSig = c; lastIdent = ""; i++; continue;
    }
    if (c === "/" && (lastSig === "" || REGEX_ALLOWED_BEFORE.includes(lastSig)
        || KEYWORDS_BEFORE_REGEX.has(lastIdent))) {        // 正则字面量
      let j = i + 1;
      let inClass = false;
      while (j < text.length) {
        const d = text[j];
        if (d === "\\") { j += 2; continue; }
        if (d === "\n") break;                             // 未闭合：行内止损
        if (d === "[") inClass = true;
        else if (d === "]") inClass = false;
        else if (d === "/" && !inClass) { j++; break; }
        j++;
      }
      blank(i + 1, j - 1);                                 // 正则内容掩掉（里面的引号不算字符串）
      lastSig = "/"; lastIdent = ""; i = j; continue;
    }
    if ((c === "{" || c === "}") && tplStack.length) {     // `\${…}` 表达式内的花括号：只数深度
      const top = tplStack[tplStack.length - 1];
      if (c === "{") top.depth++;
      else if (top.depth === 0) { tplStack.pop(); inTplText = true; }   // `}` 收尾 → 回到文本段
      else top.depth--;
      lastSig = c; lastIdent = ""; i++; continue;
    }
    if (/[A-Za-z_$]/.test(c)) {                            // 标识符：记下来给正则判定用
      let j = i;
      while (j < text.length && /[\w$]/.test(text[j])) j++;
      lastIdent = text.slice(i, j);
      lastSig = text[j - 1];
      i = j; continue;
    }
    lastSig = c; lastIdent = ""; i++;
  }
  return out.join("");
}

/**
 * 注释 / 字符串 / 正则字面量 / 模板串**整串**（含 `${…}`）的内容变空格。
 * 判据 D / T、图对账、接线与通用掩码都走这个口径——**语义与行为不得改动**。
 */
export function maskCommentsAndStrings(text) {
  return mask(text, false);
}

/**
 * 注释 / 字符串 / 正则字面量 / 模板串**文本段**的内容变空格，`${…}` **表达式内部保留为代码**
 * （内部照旧掩注释 / 字符串 / 正则 / 嵌套模板的文本段）；`${` 那两个字符本身也掩掉
 * （它们是替换语法、不是标识符——留着会把名为 `$` 的 import 喂绿）。
 *
 * 「零未使用具名 import」判据的正文口径（工单 module-import-usage/01）：用 `maskCommentsAndStrings`
 * 会把 `${esc(x)}` 这种**真使用**判成死的。
 */
export function maskNonCode(text) {
  return mask(text, true);
}

// ---------------------------------------------------------------------------
// ① / ② index.html：零 import、零顶层 JS 定义
// ---------------------------------------------------------------------------

/** 抽 HTML 里全部 `<script …>…</script>` 块 → [{ attrs, src, text, line }]。
 *  fx-guard 的"index.html 脚本块恰好两处"判据用它（内联 JS 的表达式形态只有它能看见）。 */
export function scriptBlocks(html) {
  const out = [];
  const re = /<script\b([^>]*)>([\s\S]*?)<\/script\s*>/gi;
  let m;
  while ((m = re.exec(html)) !== null) {
    const attrs = m[1];
    const srcMatch = /\bsrc\s*=\s*["']([^"']+)["']/i.exec(attrs);
    out.push({
      attrs,
      src: srcMatch ? srcMatch[1] : null,
      text: m[2],
      line: html.slice(0, m.index).split("\n").length,
    });
  }
  return out;
}

/** HTML 里**内联**脚本（无 src）的块清单。（内部件：判据 ①② 用） */
function inlineScripts(html) {
  return scriptBlocks(html).filter((b) => b.src === null);
}

/** 装载标签：`<script type="module" src="…">` → { count, tag, src }（没有时 src = null）。 */
export function loadRootTag(html) {
  const mods = scriptBlocks(html).filter((b) => /type\s*=\s*["']module["']/i.test(b.attrs));
  if (mods.length !== 1) return { count: mods.length, tag: null, src: null };
  return { count: 1, tag: mods[0], src: mods[0].src };
}

/**
 * 判据 ①：HTML 内联脚本里的 **import / 动态 import 语句**清单 → [{ line, text }]。
 * 空数组 = 装载根不在 HTML 里。（`text` 取**原始行**，便于人读与红证打印。）
 */
export function indexHtmlImports(html) {
  const out = [];
  for (const block of inlineScripts(html)) {
    const masked = maskCommentsAndStrings(block.text);
    const raw = block.text.split("\n");
    masked.split("\n").forEach((line, n) => {
      if (/^[ \t]*(import\b|export\s+[^;]*\bfrom\b)/.test(line) ||
          /\bimport\s*\(/.test(line)) {
        out.push({ line: block.line + n, text: (raw[n] || "").trim() });
      }
    });
  }
  return out;
}

/**
 * 判据 ②：**任意源码文本**里的顶层定义行（列 0 的 `function` / `class` / `const` /
 * `let` / `var`，含 `export` / `async` 前缀）→ [{ line, text }]。
 *
 * 只认**列 0**（顶层）——缩进在函数/回调体内的 `const` 不是"这个文件里定义了一个东西"
 * （与判据 ③ 同一套"列 0 = 顶层"口径）。
 */
export function topLevelDefinitions(text) {
  const masked = maskCommentsAndStrings(text);
  const raw = text.split("\n");
  const out = [];
  masked.split("\n").forEach((line, n) => {
    if (DECLARATION_RE.test(line)) {
      out.push({ line: n + 1, text: (raw[n] || "").trim() });
    }
  });
  return out;
}

/**
 * **任意缩进**的定义行（`function` / `class` / `const` / `let` / `var`，含 `export` / `async`
 * 前缀）→ [{ line, text }]。
 *
 * 只用在 **HTML 内联脚本**这一侧（`inlineDefinitions`）：HTML 里就不该有 JS，缩进四格的
 * `const` 同样是"HTML 重新变成模块图的一部分"（工单 05 评审实测：只认列 0 会让缩进形态溜过去）。
 * **不要**拿它判装载根：boot.js 的回调体里满是缩进的 `const`（页签分发器先例），会全假红。
 */
export function anyDepthDefinitions(text) {
  const masked = maskCommentsAndStrings(text);
  const raw = text.split("\n");
  const out = [];
  masked.split("\n").forEach((line, n) => {
    if (DECLARATION_RE.test(line.trimStart())) {
      out.push({ line: n + 1, text: (raw[n] || "").trim() });
    }
  });
  return out;
}

/**
 * 判据 ②（HTML 侧）：`index.html` 内联脚本里的 **JS 定义行**（任意缩进）。
 * 空数组 = HTML 里零 JS 定义。
 */
export function inlineDefinitions(html) {
  const out = [];
  for (const block of inlineScripts(html)) {
    for (const def of anyDepthDefinitions(block.text)) {
      out.push({ line: block.line + def.line - 1, text: def.text });
    }
  }
  return out;
}

// ---------------------------------------------------------------------------
// ③ 求值期零接线：列 0 的非声明语句
// ---------------------------------------------------------------------------

const DECLARATION_RE = /^(export\s+)?(async\s+)?(function|class|const|let|var)\b/;
// 探针桥（fx 模块底部给 CDP/devtools 用的那段）：**不算**页面接线
//（先例：frontend-import-fossils 的"要不要保留装载"判据）。
const PROBE_BRIDGE_RE = /^if\s*\(\s*typeof\s+window\b/;
// 续行形态（`\n  .then(…)` 写成列 0 时不该被当成独立语句；首字符类已含 `.`）
const CONTINUATION_RE = /^[.)\]},?:]|^[+-]\s|^=>|^&&|^\|\|/;

/**
 * 模块的求值期副作用语句（列 0 的非声明语句）→ [{ line, text, bridge }]。
 * **内部件**：对外只有 `wiringEffects`（"真接线"，排除探针桥）——没有任何消费方需要
 * 单独看带 bridge 标记的全集，就不导出（工单 01 评审要求"仍无消费方的导出删掉"）。
 */
function topLevelEffects(text) {
  const masked = maskCommentsAndStrings(text);
  const raw = text.split("\n");
  const out = [];
  masked.split("\n").forEach((line, n) => {
    if (!line.trim()) return;
    if (!/^[^\s]/.test(line)) return;              // 有缩进 → 函数/对象体内
    const t = line.trim();
    if (DECLARATION_RE.test(t)) return;            // 声明不是接线
    if (CONTINUATION_RE.test(t)) return;           // 续行
    if (/^(import|export)\b/.test(t)) return;      // import / re-export 是边，不是接线
    out.push({ line: n + 1, text: (raw[n] || "").trim(), bridge: PROBE_BRIDGE_RE.test(t) });
  });
  return out;
}

/** 判据 ③ 的"真接线"那一半：副作用语句，排除探针桥。 */
export function wiringEffects(text) {
  return topLevelEffects(text).filter((e) => !e.bridge);
}

// ---------------------------------------------------------------------------
// ④ 全图 import↔export 对账 + 从装载根可达
// ---------------------------------------------------------------------------

/** 跳过空白与注释（import 语句内部要能穿过注释）。 */
function skipWsComments(text, i) {
  while (i < text.length) {
    if (/\s/.test(text[i])) { i++; continue; }
    if (text[i] === "/" && text[i + 1] === "/") {
      while (i < text.length && text[i] !== "\n") i++;
      continue;
    }
    if (text[i] === "/" && text[i + 1] === "*") {
      const end = text.indexOf("*/", i + 2);
      i = end < 0 ? text.length : end + 2;
      continue;
    }
    break;
  }
  return i;
}

/** 读一段 `{ a, b as c }` → { names: [a, b], locals: [a, c], end }（end 在 `}` 之后）。 */
function readBracedNames(text, i) {
  const names = [];
  const locals = [];
  const close = text.indexOf("}", i);
  if (close < 0) return { names, locals, end: text.length };
  const body = text.slice(i + 1, close);
  for (const part of body.split(",")) {
    const clean = part.replace(/\/\/[^\n]*/g, "").replace(/\/\*[\s\S]*?\*\//g, "").trim();
    if (!clean) continue;
    const alias = clean.split(/\s+as\s+/);
    names.push(alias[0].trim());                        // 目标模块要导出的名字
    locals.push((alias[1] || alias[0]).trim());         // 本文件里用的名字
  }
  return { names, locals, end: close + 1 };
}

/** 读一个引号字符串（说明符）→ { value, end }。 */
function readString(text, i) {
  const quote = text[i];
  if (quote !== '"' && quote !== "'") return { value: null, end: i };
  let j = i + 1;
  while (j < text.length && text[j] !== quote) j++;
  return { value: text.slice(i + 1, j), end: j + 1 };
}

/**
 * 模块的 import / re-export 边 → [{ spec, names, locals, raw, bare, star, line }]。
 *
 *   names  = 说明符里的**源名**（对账目标模块要导出谁）
 *   locals = **本地名**（`import { a as b }` 收 b——"谁被导入了却没被调用"按它判）
 *   raw    = 语句原文切片（剥装载清单时按它整条替换）
 *
 * 注释感知（`import {\n // 注释\n onFileSaved,\n} from …` 只收 onFileSaved）；
 * 裸装载 names = [] 且 bare = true；`import * as ns` / `export *` 记 star = true。
 */
export function parseModuleImports(text) {
  const out = [];
  const masked = maskCommentsAndStrings(text);
  const re = /(^|\n)([ \t]*)(import|export)\b/g;
  let m;
  while ((m = re.exec(masked)) !== null) {
    const origin = m.index + m[1].length + m[2].length;
    const kind = m[3];
    let i = skipWsComments(text, origin + kind.length);
    const line = text.slice(0, origin).split("\n").length;
    let names = [];
    let locals = [];
    let star = false;
    // `export` 只在 "… from" 形态下是边（`export function` 是定义）
    const afterKind = masked.slice(origin + kind.length, origin + kind.length + 40);
    if (kind === "export" && !/^\s*(\{|\*)/.test(afterKind)) continue;
    if (text[i] === "{") {
      const read = readBracedNames(text, i);
      names = read.names; locals = read.locals; i = skipWsComments(text, read.end);
    } else if (text[i] === "*") {
      star = true; i = skipWsComments(text, i + 1);
      if (/^as\b/.test(masked.slice(i, i + 3))) {
        i = skipWsComments(text, i + 2);
        // `* as ns`：别名标识符**必须吃掉**——不吃的话下面 `/^from\b/` 判在 "ns from …" 上，
        // 整条星号导入被静默丢掉（工单 export-surface-guard/01 实测：`import * as ns from "…"`
        // 与 `export * as ns from "…"` 都返回空数组，而 `export * from "…"` 正常）。
        const alias = /^[A-Za-z_$][\w$]*/.exec(masked.slice(i, i + 80));
        if (alias) i = skipWsComments(text, i + alias[0].length);   // 停在 `from` 上（不能留空格）
      }
    } else if (text[i] === '"' || text[i] === "'") {
      // `import "…"` 裸装载：说明符就在当前位置，没有 from
      const bare = readString(text, i);
      if (bare.value !== null) {
        const end = skipSemicolon(text, bare.end);
        out.push({ spec: bare.value, names: [], locals: [], raw: text.slice(origin, end), bare: true, star: false, line });
      }
      continue;
    } else {
      // 缺省导入（本项目没有，但解析器不该在这里静默跑偏）
      const id = /^[A-Za-z_$][\w$]*/.exec(masked.slice(i, i + 80));
      if (!id) continue;
      names = [id[0]]; locals = [id[0]];
      i = skipWsComments(text, i + id[0].length);
      if (text[i] === ",") {
        i = skipWsComments(text, i + 1);
        if (text[i] === "{") {
          const read = readBracedNames(text, i);
          names = names.concat(read.names); locals = locals.concat(read.locals);
          i = skipWsComments(text, read.end);
        }
      }
    }
    if (!/^from\b/.test(masked.slice(i, i + 4))) continue; // `export { a };` 不是边
    i = skipWsComments(text, i + 4);
    const spec = readString(text, i);
    if (spec.value === null) continue;
    const end = skipSemicolon(text, spec.end);
    out.push({ spec: spec.value, names, locals, raw: text.slice(origin, end), bare: false, star, line });
  }
  return out;
}

/** 说明符之后吃掉一个可选分号（`raw` 切片要连它一起，剥清单时整条替掉）。 */
function skipSemicolon(text, i) {
  let j = i;
  while (j < text.length && (text[j] === " " || text[j] === "\t")) j++;
  return text[j] === ";" ? j + 1 : i;
}

/**
 * 模块的导出名集合（含 `export { a as b }` 的导出名与 `export { x } from "…"` 的再导出）。
 * 全部扫在**掩码文本**上——注释里的 `export {` 与字符串里的同名片段都不算导出。
 */
export function parseModuleExports(text) {
  const names = new Set();
  const masked = maskCommentsAndStrings(text);
  const patterns = [
    /export\s+(?:async\s+)?function\s+([A-Za-z_$][\w$]*)/g,
    /export\s+(?:const|let|var)\s+([A-Za-z_$][\w$]*)/g,
    /export\s+class\s+([A-Za-z_$][\w$]*)/g,
    /export\s*\{([^}]*)\}/g,
  ];
  for (const re of patterns) {
    for (const m of masked.matchAll(re)) {
      if (m[1] === undefined) continue;
      for (const part of m[1].split(",")) {
        const clean = part.trim();
        if (!clean) continue;
        const alias = clean.split(/\s+as\s+/);           // `export { a as b }` → 导出名 b
        names.add((alias[1] || alias[0]).trim());
      }
    }
  }
  return names;
}

/**
 * 把说明符归一成 `/js` 根下的仓库内相对键（`ui/x.js`）；仓外说明符返回 null。
 *
 * 名字与 `ui-dom-contract.resolveSpec` **刻意不同**：那个的键空间带 `js/` 前缀
 * （`js/ui/x.js`），本文件的键空间相对 `static/js`（`ui/x.js`）——同名不同键空间
 * 是下一处解析漂移的温床，故这里的名字把差异写进名字里。
 */
export function resolveModuleKey(spec, importerKey) {
  if (spec.startsWith("/js/")) return spec.slice(4);
  if (!spec.startsWith(".")) return null;              // 裸说明符（node: / 外部包）
  const base = importerKey ? importerKey.split("/").slice(0, -1) : [];
  for (const part of spec.split("/")) {
    if (part === "." || part === "") continue;
    if (part === "..") base.pop();
    else base.push(part);
  }
  return base.join("/");
}

/**
 * 判据 ④-a：全图 import↔export 对账。
 *
 * entries = [{ key, text }]，key 形如 `boot.js` / `app.js` / `ui/x.js`。
 * 返回 → [{ from, spec, missing: [名字], why }]；空数组 = 每条具名 import 都真有出处。
 */
export function graphBreaks(entries) {
  const byKey = new Map(entries.map((e) => [e.key, e]));
  const problems = [];
  for (const entry of entries) {
    for (const edge of parseModuleImports(entry.text)) {
      const key = resolveModuleKey(edge.spec, entry.key);
      if (key === null) continue;
      const target = byKey.get(key);
      if (!target) {
        problems.push({ from: entry.key, spec: edge.spec, missing: [], why: "文件不存在" });
        continue;
      }
      if (edge.star) continue;                          // `import * as ns` 不逐个对账
      const exported = parseModuleExports(target.text);
      const missing = edge.names.filter((n) => !exported.has(n));
      if (missing.length) {
        problems.push({ from: entry.key, spec: edge.spec, missing, why: "未导出" });
      }
    }
  }
  return problems;
}

/** 递归列出目录下所有 .js（POSIX 相对路径，排序确定）。 */
export function listJs(dir) {
  const out = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const path = `${dir}/${entry.name}`;
    if (entry.isDirectory()) out.push(...listJs(path));
    else if (entry.name.endsWith(".js")) out.push(path);
  }
  return out.sort();
}

// ---------------------------------------------------------------------------
// 模块源码的通用取件：init 导出 / 调用点 / 可达正文
// （原先散在 ui-dom-contract.mjs 与 import-usage.mjs 里，三份解析器各写各的；
//   工单 02 双轴评审把"判据抄两份必然分叉"挑出来后收敛到这里——本文件是**唯一**一份
//   ESM 解析器，另两处改为薄适配器。）
// ---------------------------------------------------------------------------

const DEFINES_INIT_RE = /^[ \t]*export\s+(?:async\s+)?function\s+(init[A-Za-z0-9_]*)\s*\(/gm;
const REEXPORT_LINE_RE = /^[ \t]*export\s*\{([^}]*)\}\s*from\s*["'][^"']+["']/gm;

/** 模块自己定义并导出的 init 名（`export { x } from` 的 re-export **不算**它的）。 */
export function ownInitExports(text) {
  const reexported = new Set();
  for (const m of text.matchAll(REEXPORT_LINE_RE)) {
    for (const name of m[1].split(",")) {
      const clean = name.trim().split(/\s+as\s+/).pop().trim();
      if (clean) reexported.add(clean);
    }
  }
  const names = [];
  for (const m of text.matchAll(DEFINES_INIT_RE)) {
    if (!reexported.has(m[1])) names.push(m[1]);
  }
  return [...new Set(names)].sort();
}

const escapeRe = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

// 声明/定义行（`export function initXxx(` / `function initXxx(`）——判"有没有调用点"时
// 必须先把它们抠掉：定义本身也含 `initXxx(`，留在正文里会让"忘了调用"永远看不出来
// （ui-dom-contract-gate 红证实测踩到：删掉启动区的调用点后守卫照样绿）。
const CALL_SITE_RE = (name) => new RegExp(`(?<![\\w$.])${escapeRe(name)}\\s*\\(`);

/** 去掉每个 init 的**定义行**之后的正文（调用点判据的取数面）。**内部件**。 */
function withoutInitDefinitions(text, initNames) {
  let out = text;
  for (const name of initNames) {
    const def = new RegExp(
      `^[ \\t]*(?:export\\s+)?(?:async\\s+)?function\\s+${escapeRe(name)}\\b[^\\n]*$`,
      "gm");
    out = out.replace(def, "");
  }
  return out;
}

/** 正文里有没有该 init 的**调用点**（排除定义行）。 */
export function hasCallSite(text, name) {
  return CALL_SITE_RE(name).test(withoutInitDefinitions(text, [name]));
}

/**
 * 从装载根沿 import 边广搜 → { reachable: Set<key>, importedNames: Set<名字>, bodies: [text] }。
 *
 * hostText = 装载根原文（import 边就在这里）；modules = [{ key, text }]（key 形如 `ui/x.js`）。
 * `importedNames` 收的是**本地名**（`import { a as b }` 收 b）——"谁被导入了却没被调用"要按
 * 调用处写的那个名字判。
 *
 * **内部件**：对外只有 `reachable`（只要可达集合与掉队清单）。
 */
function reachableWithBodies(hostText, modules) {
  const byKey = new Map(modules.map((m) => [m.key, m]));
  const reachableKeys = new Set();
  const importedNames = new Set();
  const bodies = [hostText];
  const queue = [];
  for (const edge of parseModuleImports(hostText)) {
    const key = resolveModuleKey(edge.spec, "boot.js");
    if (key) queue.push(key);
    for (const name of edge.locals) importedNames.add(name);
  }
  while (queue.length) {
    const key = queue.shift();
    if (reachableKeys.has(key) || !byKey.has(key)) continue;
    reachableKeys.add(key);
    const text = byKey.get(key).text;
    bodies.push(text);
    for (const edge of parseModuleImports(text)) {
      const next = resolveModuleKey(edge.spec, key);
      if (next) queue.push(next);
      for (const name of edge.locals) importedNames.add(name);
    }
  }
  return { reachable: reachableKeys, importedNames, bodies };
}

/**
 * 判据 ④-b：从装载根（boot.js 原文）沿 import 图可达的模块键集合，以及掉队的模块。
 *
 * 返回 { reachable: Set<key>, orphans: [key] }（orphans = modules 里走不到的）。
 */
export function reachable(rootText, modules) {
  const { reachable: reachableKeys } = reachableWithBodies(rootText, modules);
  return {
    reachable: reachableKeys,
    orphans: modules.map((m) => m.key).filter((k) => !reachableKeys.has(k)).sort(),
  };
}

/** 装载根文本里具名导入的模块键（boot 直接装载的那一层）。 */
export function loadRootKeys(rootText) {
  const keys = new Set();
  for (const edge of parseModuleImports(rootText)) {
    const key = resolveModuleKey(edge.spec, "boot.js");
    if (key) keys.add(key);
  }
  return keys;
}

/**
 * 判据 ③ 的另一半：**裸装载**（`import "…"`，零具名）清单 → [{ spec, line }]。
 *
 * 裸装载 = "这个模块存在的意义就是被加载"——正是本次要退场的那条隐式边。
 * 空数组 = 装载清单里每条 import 都有明确的用处（具名 + 有人调用）。
 */
export function bareLoads(rootText) {
  return parseModuleImports(rootText)
    .filter((e) => e.bare)
    .map((e) => ({ spec: e.spec, line: e.line }));
}

/** 谁 import 了它（全图反向边，不含装载根）→ Set<key>。 */
export function importersOf(key, modules) {
  const out = new Set();
  for (const m of modules) {
    if (m.key === key) continue;
    for (const edge of parseModuleImports(m.text)) {
      if (resolveModuleKey(edge.spec, m.key) === key) out.add(m.key);
    }
  }
  return out;
}

/**
 * 禁环判据：**有没有模块 import 装载根**（boot.js）→ [{ key, line }]；空数组 = 分层成立。
 *
 * 分层规则（照 js/app.js 的禁环约定）：boot 可以 import ui/app，**任何 ui/app 都不得
 * import boot**——否则成环，且"谁先求值"会变成隐式约定。
 */
export function modulesImportingLoadRoot(modules) {
  const out = [];
  for (const m of modules) {
    for (const edge of parseModuleImports(m.text)) {
      if (resolveModuleKey(edge.spec, m.key) === LOAD_ROOT_KEY) {
        out.push({ key: m.key, line: edge.line, spec: edge.spec });
      }
    }
  }
  return out;
}

/**
 * 判据 ③ 的适用面（本次 spec 的 B 档）——**两半**：
 *
 *   ③-b-1 **结构那一半**：boot 装载的 ui 模块中，boot 是它唯一装载来源的那些
 *           （别的模块都不 import 它）——它们的接线只可能是"被 boot 装载"的结果，
 *           所以必须住在导出 init*() 里、求值期零接线。**不需要任何名单**。
 *   ③-b-2 **登记那一半**：`EXPLICIT_WIRING_MODULES` 里的模块同样必须求值期零接线。
 *           为什么要这张 11 项的小表：其中 4 个（generate-revise / generate-tasks /
 *           params / delivery）**另有别的 ui 模块 import 它们**，结构判据抓不到；
 *           而"接线住不住求值期"这条纪律对它们一样要钉死（spec 的 11 个模块 = 两半的并集）。
 *           表自带体检（`registryProblems`）：键必须存在、是 ui/、被 boot 装载、
 *           且 boot 真的调用了它导出的某个 init*——**表不会静默腐烂**。
 *
 * 返回 → [{ key, effects }]；空数组 = 不变量成立。
 */
export function wiringViolations(rootText, modules) {
  const byKey = new Map(modules.map((m) => [m.key, m]));
  const problems = [];
  const keys = new Set(EXPLICIT_WIRING_MODULES);
  for (const key of loadRootKeys(rootText)) {
    if (!key.startsWith("ui/")) continue;
    if (!byKey.has(key)) continue;
    if (importersOf(key, modules).size > 0) continue;    // 另有装载来源 → 只由登记那一半管
    keys.add(key);
  }
  for (const key of [...keys].sort()) {
    const entry = byKey.get(key);
    if (!entry) continue;
    const effects = wiringEffects(entry.text);
    if (effects.length) problems.push({ key, effects });
  }
  return problems;
}

/**
 * 「接线已显式化」登记表（工单 03/04 的交付面）：这些 ui 模块的求值期接线已搬进
 * 导出的 init*()，由 boot 显式调用，因此求值期必须零接线。
 *
 * 11 项 = spec「实现决策」B 档：裸装载 5（前四项另有 importer，故需登记）＋
 * boot 唯一装载来源 6。新增"显式化"的模块往这里加一行即可（守卫会替你体检）。
 */
export const EXPLICIT_WIRING_MODULES = [
  "ui/code-fix-panel.js",
  "ui/delivery.js",
  "ui/generate-core.js",
  "ui/generate-revise.js",
  "ui/generate-tasks.js",
  "ui/library.js",
  "ui/master.js",
  "ui/params-chat.js",
  "ui/params.js",
  "ui/reference.js",
  "ui/topic.js",
];

/**
 * 登记表体检 → [{ key, why }]；空数组 = 表本身没烂。
 *
 * 每一行必须：① 模块存在；② 是 ui/ 模块；③ 被装载根装载；④ 它导出的某个 `init*`
 * 在装载根正文里**有调用点**（"登记了却没人调"= 接线其实没搬出去，或 boot 忘了调）。
 *
 * **单向**：只查"登记了的必须成立"，不查"成立了的必须登记"——后者不可判定（没有任何结构标记
 * 能区分"接线被搬过"与"本来就没有接线"）。`ui-dom-contract.test.mjs` 的断言文案与 CONTEXT.md
 * 已按这个事实写（工单 05 评审抓出过"双向"的过度声称）。
 *
 * 调用点判在**掩码文本**上：boot.js 里满是墓碑注释（"…已迁至 …initHandoffNote()…"），
 * 未掩码正文会让"删掉真调用"照样绿（同一轮评审实测：删 `initGenerateActions();` 后体检报绿）。
 */
export function registryProblems(rootText, modules) {
  const byKey = new Map(modules.map((m) => [m.key, m]));
  const booted = loadRootKeys(rootText);
  const maskedBoot = maskCommentsAndStrings(rootText);
  const problems = [];
  for (const key of EXPLICIT_WIRING_MODULES) {
    const entry = byKey.get(key);
    if (!entry) { problems.push({ key, why: "登记了，但模块不存在" }); continue; }
    if (!key.startsWith("ui/")) { problems.push({ key, why: "不是 ui/ 模块" }); continue; }
    if (!booted.has(key)) { problems.push({ key, why: "登记了，但装载根没装载它" }); continue; }
    const inits = ownInitExports(entry.text);
    if (!inits.length) { problems.push({ key, why: "登记了，但它没有导出 init*()" }); continue; }
    if (!inits.some((name) => hasCallSite(maskedBoot, name))) {
      problems.push({ key, why: `登记了，但装载根没调用它导出的 init*（${inits.join(" / ")}）` });
    }
  }
  return problems;
}

// ---------------------------------------------------------------------------
// ⑤ 导出面对账：判据 D（零消费者导出）与判据 T（调用位 ⇒ 函数形态）
//
// 工单 export-surface-guard/01。判据 ④（`graphBreaks`）管的是"被 import 的名字**有没有出处**"，
// 本节两条管**另外两个方向**——合起来把导出面夹住：
//   · **判据 D（下限）**：每个导出必须真有消费者（一条 import 边）。旧 `DOMAINS` 名字表被删掉
//     之后，"没人用的导出"再没有任何东西看着（工单 frontend-boot-module/05 如实记的代价之一）。
//   · **判据 T（形态）**：被**调用**的导出必须是函数形态。把 `export function x` 悄悄换成同名的
//     `export const x = 数据`，④ 照样绿（名字还在），直到运行时那次调用炸成 TypeError。
//
// 两条都**零名单**：新增模块、改导出名都不需要登记——这正是 `DOMAINS` 那种表被拆掉的原因。
// ---------------------------------------------------------------------------

/**
 * 消费侧（测试）文件的说明符 → 页面模块键（`fx/x.js`）；仓外/无关说明符返回 null。
 *
 * 测试侧实测两种写法都要认：`../../src/contest_generator/static/js/fx/x.js`（`tests/js` 与
 * `tests/browser` 的通行写法）与 `/js/fx/x.js`。归一到**页面模块表那个键空间**（相对
 * `static/js`）才谈得上对账——`resolveModuleKey` 的键空间是同一个，但它按**页面模块**的相对
 * 位置解析，用在测试文件上会把 `../../` 解析到 `tests/` 外面去。
 */
export function consumerSpecToKey(spec) {
  const norm = spec.split("\\").join("/");
  const at = norm.indexOf("static/js/");
  if (at >= 0) return norm.slice(at + "static/js/".length);
  return norm.startsWith("/js/") ? norm.slice(4) : null;
}

/**
 * 全图**消费边**（页面侧 ＋ 消费侧）→ [{ kind, from, target, name, edge, entry }]。
 *   · `kind` = `"page"`（页面模块之间的 import 边）｜`"consumer"`（tests/js · tests/browser 的边）
 *   · `target` = 被 import 的模块键（页面键空间）；`edge` / `entry` 是原始切片（自检要拿它做注入）
 *
 * **判据 D 与守卫／红证的自检共用这一遍遍历**——工单 export-surface-guard/03 双轴评审指出守卫
 * 那边抄了第三份走图代码（"同一件事解析三处必然分叉"）。
 */
export function consumptionEdges(pageEntries, consumerEntries = []) {
  const pageKeys = new Set(pageEntries.map((e) => e.key));
  const out = [];
  const walk = (entries, kind, toKey) => {
    for (const entry of entries) {
      for (const edge of parseModuleImports(entry.text)) {
        const target = toKey(edge.spec, entry.key);
        if (target === null || !pageKeys.has(target)) continue;   // 仓外 / 指向不存在的模块
        for (const name of edge.names) out.push({ kind, from: entry.key, target, name, edge, entry });
      }
    }
  };
  walk(pageEntries, "page", resolveModuleKey);
  walk(consumerEntries, "consumer", consumerSpecToKey);
  return out;
}

/**
 * 判据 D：**零消费者导出** → [{ key, name }]；空数组 = 每个导出都有人 import。
 *
 * 消费者 = 一条 **import 边**：页面模块图（`pageEntries`，含装载根 `boot.js`）∪ 消费侧
 * （`consumerEntries` = `tests/js` 与 `tests/browser` 的 .mjs，说明符经 `consumerSpecToKey` 归一）。
 *
 * - **注释提及不算消费者**：工单 frontend-boot-module/05 评审实测过"墓碑注释把判据喂绿"
 *   （boot.js 里满是"已迁至 …"）。`.scratch` 一次性探针同样不算——它们是历史证据，不是闸门。
 * - **口径是"哪条导出"（`模块::名字`），不是"这个名字还有没有人用"**：改用全局名字集会放过
 *   冗余的**转手再导出** —— 实测（`probe-05-duplicate-names`）全仓 5 个名字被 ≥2 个模块导出，
 *   其中 3 处按模块算根本没人取（`ui/full-update.js::fullStateText`、
 *   `ui/generate-fix.js::{FIX_MAX_ROUNDS, fixLoop}`），名字级口径会把它们静默放过。
 * - 反过来**不会假红**：`export { x } from "M"` 本身就是一条指向 M 的 import 边，所以
 *   "M 里声明 + R 里转手再导出"这两侧都会被记上（实测 `gotoNavTab`：`ui/goto-nav.js` 声明、
 *   `ui/nav-jump.js` 转手，两侧都被正确判为有人用）。被判红的只有"没人从这儿取过"的那些。
 */
export function unconsumedExports(pageEntries, consumerEntries = []) {
  const consumed = new Set(
    consumptionEdges(pageEntries, consumerEntries).map((e) => `${e.target}::${e.name}`));
  const out = [];
  for (const entry of pageEntries) {
    for (const name of parseModuleExports(entry.text)) {
      if (!consumed.has(`${entry.key}::${name}`)) out.push({ key: entry.key, name });
    }
  }
  return out;
}

/**
 * 星号导入体检 → [{ key, spec, line }]；空数组 = 判据 D 的"逐名对账"是完整的。
 *
 * `import * as ns from "…"` 一旦出现在**触达前端**的位置，判据 D 就**判不了**：它按名字对账，
 * 而命名空间的成员是运行时属性——`ns.foo()` 这种用法在判据 D 眼里等于没人用 `foo`
 * （实测：注入 `import * as ns …` + `ns.maincScrollToRange()` 后，判据 D 仍报
 * `maincScrollToRange` 零消费者）。现状实测 0 处，所以判据不必处理它；一旦出现就报出来，
 * 逼人显式决定（要么改成具名导入，要么把判据口径想清楚），而不是让判据悄悄失真。
 */
export function starImports(pageEntries, consumerEntries = []) {
  const out = [];
  const scan = (entry, normalizer) => {
    for (const edge of parseModuleImports(entry.text)) {
      if (edge.star && normalizer(edge.spec, entry.key) !== null) {
        out.push({ key: entry.key, spec: edge.spec, line: edge.line });
      }
    }
  };
  for (const entry of pageEntries) scan(entry, resolveModuleKey);
  for (const entry of consumerEntries) scan(entry, consumerSpecToKey);
  return out;
}

// 声明形态：函数形态（`function` / `class` / 箭头 / 函数表达式）与非函数声明（值形态）。
// `export const x = 别的名字;` 单独一档——形态要跟到那个名字的出处去（见 exportFormOf）。
// 名字后面一律用 `(?![\w$])` 而不是 `\b`：`$`（本仓库真有 `export const $ = (id) => …`）
// 是非单词字符，`\b` 在 `$(` 之间**不成立** —— 用它会把 `$` 这类名字的形态判成"解不开"，
// 从而假红（工单 export-surface-guard/01 自检 7/9 实测踩到）。
const DECL_FN_RE = (name) => new RegExp(
  `(?:^|\\n)[ \\t]*(?:export\\s+)?(?:async\\s+)?function\\s+${escapeRe(name)}(?![\\w$])`
  + `|(?:^|\\n)[ \\t]*(?:export\\s+)?class\\s+${escapeRe(name)}(?![\\w$])`
  + `|(?:^|\\n)[ \\t]*(?:export\\s+)?(?:const|let|var)\\s+${escapeRe(name)}\\s*=`
  + `\\s*(?:async\\s*)?(?:\\(|function\\b|[A-Za-z_$][\\w$]*\\s*=>)`);
const DECL_ANY_RE = (name) => new RegExp(
  `(?:^|\\n)[ \\t]*(?:export\\s+)?(?:async\\s+)?(?:function|class|const|let|var)\\s+`
  + `${escapeRe(name)}(?![\\w$])`);
const DECL_ALIAS_RE = (name) => new RegExp(
  `(?:^|\\n)[ \\t]*(?:export\\s+)?(?:const|let|var)\\s+${escapeRe(name)}\\s*=\\s*([A-Za-z_$][\\w$]*)\\s*;`);

/** `edge` 是不是**再导出**（`export { … } from "…"` / `export { … };`），而不是 `import`。 */
function isReexportEdge(edge) {
  return /^export/.test(edge.raw.trimStart());
}

/** `key` 模块里的本地名 `local` 是从哪个模块 **import** 进来的 → { key, name }；不是则 null。 */
function importSourceOf(byKey, key, local) {
  for (const edge of parseModuleImports(byKey.get(key).text)) {
    if (isReexportEdge(edge)) continue;                     // 再导出不是 import
    const at = edge.locals.indexOf(local);
    if (at < 0) continue;
    const target = resolveModuleKey(edge.spec, key);
    return target === null ? null : { key: target, name: edge.names[at] };
  }
  return null;
}

/**
 * 导出名的**形态** → `"fn"` / `"value"` / `null`（解不开）。
 *
 * 跟随两条链（不跟就会假红——实测：不做这两步，1112 条调用位里冒出 44 条假红）：
 *   · **再导出链**：`export { x } from "…"` 递归进目标模块；
 *   · **函数别名链**：`export const x = 别的名字;` —— 先看同名声明在不在本文件，
 *     再看 `别的名字` import 自哪儿。
 *
 * 解不开返回 null，**由调用方当违规处理**（不许静默跳过）。已知的"解不开"来源：
 * `= 全局函数名`（如 `= parseInt`）与工厂调用 `= makeClock()`（后者按值形态算）。
 */
function exportFormOf(byKey, key, name, seen = new Set()) {
  const tag = `${key}::${name}`;
  if (seen.has(tag)) return null;                            // 环：判"解不开"
  seen.add(tag);
  const entry = byKey.get(key);
  if (!entry) return null;
  const masked = maskCommentsAndStrings(entry.text);
  if (DECL_FN_RE(name).test(masked)) return "fn";
  const alias = DECL_ALIAS_RE(name).exec(masked);
  if (alias) {
    const target = alias[1];
    if (DECL_FN_RE(target).test(masked)) return "fn";
    const src = importSourceOf(byKey, key, target);
    if (src) return exportFormOf(byKey, src.key, src.name, seen);
    return DECL_ANY_RE(target).test(masked) ? "value" : null;
  }
  if (DECL_ANY_RE(name).test(masked)) return "value";
  for (const edge of parseModuleImports(entry.text)) {        // 本文件没声明 → 只可能是再导出
    if (!isReexportEdge(edge)) continue;
    if (!edge.names.includes(name)) continue;
    const next = resolveModuleKey(edge.spec, key);
    return next === null ? null : exportFormOf(byKey, next, name, seen);
  }
  return null;
}

/**
 * 判据 T 的适用面：**调用位的导入边** → [{ entry, edge, target, name, local }]。
 * 判据 T 与取数面体检同用它（"调用位"这件事只解析一处，免得两处判定分叉）。**内部件**。
 */
function callPositionEdges(pageEntries) {
  const byKey = new Map(pageEntries.map((e) => [e.key, e]));
  const out = [];
  for (const entry of pageEntries) {
    const masked = maskCommentsAndStrings(entry.text);
    for (const edge of parseModuleImports(entry.text)) {
      const target = resolveModuleKey(edge.spec, entry.key);
      if (target === null || edge.star || !byKey.has(target)) continue;
      edge.locals.forEach((local, i) => {
        if (!new RegExp(`(?<![\\w$.])${escapeRe(local)}\\s*\\(`).test(masked)) return;
        out.push({ entry, edge, target, name: edge.names[i], local });
      });
    }
  }
  return out;
}

/**
 * 判据 T：**调用位 ⇒ 函数形态** → [{ from, to, name, form }]；空数组 = 形态面合规。
 *
 * 一条 import 边的本地名若在**被导入方**处于调用位（`name(`），它在导出侧就必须解析成函数形态。
 * 调用位判在 `maskCommentsAndStrings` 的正文上：注释里的 `x(` 不算调用位（评审先例：
 * 注释喂绿）；代价是**模板串 `${…}` 里的调用也一并被掩掉**（该掩码件的已知限制）——
 * 方向是保守的（漏报，不假红），如实记账。
 *
 * **只算页面模块图**（spec「实现决策」）：测试侧调用点实测也是 0 违规 0 解不开，但那条口径
 * 要另外纳进 spec 才作数（本轮按 spec 走，读数记在工单 Comments）。
 */
export function nonFunctionCallees(pageEntries) {
  const byKey = new Map(pageEntries.map((e) => [e.key, e]));
  const out = [];
  for (const { entry, target, name } of callPositionEdges(pageEntries)) {
    const form = exportFormOf(byKey, target, name);
    if (form !== "fn") out.push({ from: entry.key, to: target, name, form: form || "解不开" });
  }
  return out;
}

/**
 * 导出面两条判据的**取数面下限**（数字取得比实测低一截——只在"抽取器静默失效"，
 * 如目录搬了 / 说明符换了写法时才会触发，不追着现状贴脸）。
 * 实测（base `27a7b46e`）：消费侧 164 个模块 / 导出条目 **995** / 调用位 1112；
 * 清点后（工单 02）导出条目降到 **884** —— 下限必须按**清点后**那个数取，
 * 否则清理一做完体检就先自己红了（工单 01 规范轴评审实测抓到的坑）。**内部件**。
 */
const EXPORT_FACE_FLOORS = { consumers: 120, exports: 800, callSites: 800 };

/**
 * 取数面体检 → [问题…]；空数组 = 判据 D/T 的分母还在。**断言为空必须配这个**——
 * 抽取器一旦静默失效，`unconsumedExports` 会"全绿"（先例 `ui-dom-contract.test.mjs`
 * 「那种绿比红更坏」）。
 *
 * 第一条专治"**少喂了装载根**"：`readJsModules` 按其文档**不含** boot.js，调用方必须自己把它
 * 拼在最前面（`[{ key: "boot.js", text: readLoadRoot(dir) }, ...readJsModules(dir)]`）。
 * 漏拼就会丢掉装载清单那 60 多条 import 边——实测判据 D 从 111 处飙到 189 处假红，
 * 而消费侧计数照旧"正常"。这条体检让它当场现形，而不是等 ticket 03 接闸门时才发现。
 */
export function exportFaceProblems(pageEntries, consumerEntries = []) {
  const problems = [];
  const root = pageEntries.find((e) => e.key === LOAD_ROOT_KEY);
  if (!root || typeof root.text !== "string" || !root.text) {
    problems.push("页面模块表里没有装载根（boot.js）—— 装载清单的 import 边全丢，判据 D 会整片假红");
  }
  const consumers = consumerEntries.length;
  const exports = pageEntries.reduce((n, e) => n + parseModuleExports(e.text).size, 0);
  const callSites = callPositionEdges(pageEntries).length;
  if (consumers < EXPORT_FACE_FLOORS.consumers) {
    problems.push(`消费侧只抽到 ${consumers} 个模块（下限 ${EXPORT_FACE_FLOORS.consumers}）`
      + "——判据 D 会当成「没人 import」整片假红");
  }
  if (exports < EXPORT_FACE_FLOORS.exports) {
    problems.push(`页面导出名只抽到 ${exports} 个（下限 ${EXPORT_FACE_FLOORS.exports}）`);
  }
  if (callSites < EXPORT_FACE_FLOORS.callSites) {
    problems.push(`调用位只抽到 ${callSites} 条（下限 ${EXPORT_FACE_FLOORS.callSites}）`
      + "——判据 T 会真空绿");
  }
  return problems;
}

// ---------------------------------------------------------------------------
// 取数面：把 static/js 下的模块读成 [{ key, text }]
// ---------------------------------------------------------------------------

/**
 * 读 static/js/** → [{ key, text }]（key 相对 static/js，形如 `ui/x.js`）。
 *
 * **不含装载根本身**（`boot.js`）：它是图的**根**，不是图里的节点——把它混进模块表会让
 * 「谁 import 了它」把根算成 importer（判据③-b 会因此整片假绿）、让可达性把根自己报成
 * 掉队模块。根由 `readLoadRoot` 单独取。
 */
export function readJsModules(staticDir) {
  const root = `${staticDir.replace(/[\\/]+$/, "")}/js`;
  return listJs(root)
    .map((path) => ({
      key: path.slice(root.length + 1).split("\\").join("/"),
      text: readFileSync(path, "utf8"),
    }))
    .filter((m) => m.key !== LOAD_ROOT_KEY);
}

/** 读装载根（boot.js）文本；不存在返回 null（收走前那个提交就是这种状态）。 */
export function readLoadRoot(staticDir) {
  const path = `${staticDir.replace(/[\\/]+$/, "")}/js/boot.js`;
  return existsSync(path) ? readFileSync(path, "utf8") : null;
}

/**
 * 读**消费侧**（`tests/js` 与 `tests/browser` 的 .mjs，含子目录）→ [{ key, text }]。
 * key 是仓库相对路径（`tests/js/x.test.mjs`），只用于定位报错；说明符经 `consumerSpecToKey` 归一。
 *
 * 判据 D 的消费者集合有一半在这里——少了它，测试缝（`tests/js` 直接 import fx 模块的那 150+ 条边）
 * 全部不算数，实测会把 108 处错报成 262 处。
 */
export function readConsumerModules(repoRoot) {
  const out = [];
  const walk = (abs, key) => {
    if (!existsSync(abs)) return;
    for (const entry of readdirSync(abs, { withFileTypes: true }).sort((a, b) => (a.name < b.name ? -1 : 1))) {
      const childAbs = `${abs}/${entry.name}`;
      const childKey = `${key}/${entry.name}`;
      if (entry.isDirectory()) walk(childAbs, childKey);
      else if (entry.name.endsWith(".mjs")) {
        out.push({ key: childKey, text: readFileSync(childAbs, "utf8") });
      }
    }
  };
  const root = repoRoot.replace(/[\\/]+$/, "");
  for (const dir of ["tests/js", "tests/browser"]) walk(`${root}/${dir}`, dir);
  return out;
}
