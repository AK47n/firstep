// synthetic-cases.mjs — 「零未使用具名 import」判据的**合成红证用例表**（单源）。
//
// 工单 module-import-usage/01。为什么要合成片段：真源码上判据只会给一个**绿**（0 处），
// 而"绿"本身证明不了判据有牙齿。这里每一条都是**判据的假绿反例**（或防假红的反向对照）：
// 喂一段**手写**的模块源码，断言判据报出 / 不报**指定的那个名字**。
//
// 单源：`probe-01-synthetic-red-proof.mjs`（CLI）与 `probe-02-base-red-proof.mjs`（真红证的第 ④ 段）
// **共用本表**——同一件事不抄两份（抄两份必然分叉）。
//
// 每条用例带三类字段：
//   · `expect`        —— 判据**应当报出**的名字（空数组 = 必须不报）；
//   · `bodyIncludes`  —— 语料里 import 语句**之外**必须真的出现这些名字（**注入自检**：
//                        没有它，用例可能因为"名字压根没写进去"而两边都空、假过）；
//   · 差分校准（可选）—— 同一条语料在**别的口径**下的预期结果，用来证明"是本轮的口径修正抓到了它"：
//       `oldCaliber`     工单 02 那个旧口径（`hostBody` 正文 ＋ 按**源名**判）；
//       `naiveMask`      只用 `maskCommentsAndStrings`（模板表达式一并掩掉）；
//       `naiveSubstring` 丢掉标识符边界的朴素子串口径。
import {
  unusedImports, hostBody, parseImports, identRe,
} from "../../tests/js/import-usage.mjs";
import { maskCommentsAndStrings } from "../../tests/js/boot-contract.mjs";

/** 造一段带单条 import 的模块源码。 */
const mk = (body, { names = "esc", spec = "./core.js" } = {}) =>
  `import { ${names} } from "${spec}";\n${body}\n`;

/** 判据报出的名字（判据本体）。 */
const reported = (src) => unusedImports(src).flatMap((p) => p.unused);

/** 按区间把 import 语句切片从 `text` 里抹成空格（保长度、保换行）。 */
function stripImports(src, text, imports) {
  let out = text;
  let cursor = 0;
  for (const imp of imports) {
    const at = src.indexOf(imp.raw, cursor);
    if (at < 0) throw new Error(`合成语料与解析器不一致：找不到 ${imp.spec} 的切片`);
    cursor = at + imp.raw.length;
    out = out.slice(0, at) + out.slice(at, cursor).replace(/[^\n]/g, " ") + out.slice(cursor);
  }
  return out;
}

/** 语料里 import 语句**之外**的正文。 */
const bodyRegion = (src) => stripImports(src, src, parseImports(src));

/** 旧口径（工单 02）报出的名字：正文 = 原文 − import − 整行 `//`，按**源名**判。 */
function oldCaliberReported(src) {
  const imports = parseImports(src);
  const body = hostBody(src, imports);
  const out = [];
  for (const { names } of imports) for (const n of names) if (!identRe(n).test(body)) out.push(n);
  return out;
}

/** naive 掩码口径（`maskCommentsAndStrings`）报出的名字：按**本地名**判。 */
function naiveMaskReported(src) {
  const imports = parseImports(src);
  const masked = stripImports(src, maskCommentsAndStrings(src), imports);
  const out = [];
  for (const { names, locals } of imports) {
    names.forEach((n, i) => { if (!identRe(locals[i] || n).test(masked)) out.push(n); });
  }
  return out;
}

/** 朴素子串口径（**丢掉标识符边界**）报出的名字：给边界用例提供差分牙齿。 */
function naiveSubstringReported(src) {
  const body = bodyRegion(src);
  const out = [];
  for (const { names } of parseImports(src)) for (const n of names) if (!body.includes(n)) out.push(n);
  return out;
}

const CALIBERS = {
  oldCaliber: { label: "旧口径", run: oldCaliberReported },
  naiveMask: { label: "naive 掩码", run: naiveMaskReported },
  naiveSubstring: { label: "朴素子串", run: naiveSubstringReported },
};

/**
 * 用例表。`expect` = 判据应当报出的名字（空数组 = 必须不报）。
 * `bodyIncludes` = import 语句之外必须出现过的名字（注入自检）。
 */
export const CASES = [
  // ── 假绿反例：名字**不在代码里**，判据必须报出 ──────────────────────────────
  {
    id: "comment-line",
    why: "名字只在行注释里（旧口径正是被它喂绿的）",
    src: mk("const a = 1; // esc 在这里出现，但这不是使用"),
    expect: ["esc"], bodyIncludes: ["esc"], oldCaliber: [],
  },
  {
    id: "comment-block",
    why: "名字只在块注释里",
    src: mk("/* esc 单源取自 core.js */\nconst a = 1;"),
    expect: ["esc"], bodyIncludes: ["esc"], oldCaliber: [],
  },
  {
    id: "comment-trailing-block",
    why: "名字只在**行尾**块注释里（旧口径只剥整行 `//`，这行剥不掉）",
    src: mk("const a = 1; /* esc */"),
    expect: ["esc"], bodyIncludes: ["esc"], oldCaliber: [],
  },
  {
    id: "string-double",
    why: "名字只在双引号字符串里",
    src: mk('const s = "esc";'),
    expect: ["esc"], bodyIncludes: ["esc"], oldCaliber: [],
  },
  {
    id: "string-single",
    why: "名字只在单引号字符串里",
    src: mk("const s = 'esc';"),
    expect: ["esc"], bodyIncludes: ["esc"], oldCaliber: [],
  },
  {
    id: "regex-literal",
    why: "名字只在正则字面量里（正则要被识别成正则，不能当除号——否则引号会开启字符串状态）",
    src: mk("const re = /esc/;\nconst a = re.test(x);"),
    expect: ["esc"], bodyIncludes: ["esc"], oldCaliber: [],
  },
  {
    id: "template-text-segment",
    why: "名字只在模板串的**文本段**里",
    src: mk("const s = `esc 是文本段`;"),
    expect: ["esc"], bodyIncludes: ["esc"], oldCaliber: [],
  },
  {
    id: "template-text-then-expr",
    why: "模板串里既有文本段的 `esc` 又有别的表达式 —— 文本段那个不算使用",
    // 文本段的 `esc` 后面要留空格：写成 `` `esc${y}` `` 时 `esc$` 会被**标识符边界**看成一个整体
    //（`$` 是合法的标识符字符），旧口径于是"碰巧"也对，那条就失去差分校准的意义了。
    src: mk("const s = `esc ${y}`;"),
    expect: ["esc"], bodyIncludes: ["esc"], oldCaliber: [],
  },
  {
    id: "comment-inside-template-expr",
    why: "名字在模板**表达式**里的注释中（表达式是代码区，但注释里的同名不算使用）",
    src: mk("const s = `${ /* esc */ 1 }`;"),
    expect: ["esc"], bodyIncludes: ["esc"],
  },
  {
    id: "longer-identifier",
    why: "名字只是更长标识符的前缀/子串（标识符边界）—— 朴素子串口径在这里假绿",
    src: mk("const escFoo = 1; escFoo();"),
    expect: ["esc"], bodyIncludes: ["escFoo"], naiveSubstring: [],
  },
  {
    id: "dollar-suffix",
    why: "`$` 只出现在更长标识符里（用 \\b 会恒假，用 lookaround 才对）—— 朴素子串口径在这里假绿",
    src: mk("const $x = 1; const y$ = 2; use($x, y$);", { names: "$", spec: "/js/app.js" }),
    expect: ["$"], bodyIncludes: ["$x", "y$"], naiveSubstring: [],
  },
  {
    id: "dollar-template-substitution",
    why: "`$` 只作为**模板替换语法**出现（`${` 是语法不是标识符）—— 既不能喂绿、也不能算用",
    src: mk("const s = `a${x}b`;", { names: "$", spec: "/js/app.js" }),
    expect: ["$"], bodyIncludes: ["a${x}b"],
  },
  {
    id: "never-mentioned",
    why: "名字在正文里一次都没出现（最朴素的那条；旧口径在这个形态上也是对的）",
    src: mk("const a = 1;"),
    expect: ["esc"], bodyIncludes: [], oldCaliber: ["esc"],
  },

  // ── 反向对照：名字**真在代码里**，判据必须不报（防假红） ────────────────────
  {
    id: "code-call",
    why: "代码里的直接调用",
    src: mk("const h = esc(x);"),
    expect: [], bodyIncludes: ["esc"],
  },
  {
    id: "template-expression",
    why: "**模板表达式**里的使用 —— naive 掩码口径会把整串掩掉、判成死的（假红）；`maskNonCode` 必须判活",
    src: mk("const h = `<b>${esc(x)}</b>`;"),
    expect: [], bodyIncludes: ["esc"], naiveMask: ["esc"],
  },
  {
    id: "template-expression-nested",
    why: "嵌套模板表达式（`${` 里再开一个模板串）里的使用",
    // 这条**不带** naive 校准：naive 掩码件按"遇到下一个反引号就收尾"扫模板串，嵌套形态下它只掩掉
    // 一小截、剩下的当代码，反倒"碰巧"判活 —— 差异不成立，如实不写。
    src: mk("const h = `${ `a${esc(x)}b` }`;"),
    expect: [], bodyIncludes: ["esc"],
  },
  {
    id: "template-expression-braces",
    why: "表达式里有对象字面量（花括号深度必须数对，否则 `}` 提前收尾、后面的代码被当文本段掩掉）",
    src: mk("const h = `${foo({ a: esc(x) })}`;"),
    expect: [], bodyIncludes: ["esc"], naiveMask: ["esc"],
  },
  {
    id: "reexport-clause",
    why: "经**再导出清单**被消费（`export { esc };` 本身就是一条消费边）",
    src: mk("export { esc };"),
    expect: [], bodyIncludes: ["esc"], oldCaliber: [],
  },
  {
    id: "import-then-reexport",
    why: "工单点名的连写形态：`import { x } from \"M\"; export { x };` —— 导入的 x 由再导出消费，不许报",
    src: 'import { esc } from "./core.js";\nexport { esc };\n',
    expect: [], bodyIncludes: ["esc"], oldCaliber: [],
  },
  {
    id: "alias-local-used",
    why: "`import { A as B }` 里**本地名 B** 被用（按源名判会假红——工单 02 的 5 处误报都是这种）",
    src: mk("if (!guard(WG.fix)) return;", { names: "WRITE_GUARD_ACTIONS as WG", spec: "/js/fx/write-guard.js" }),
    expect: [], bodyIncludes: ["WG"], oldCaliber: ["WRITE_GUARD_ACTIONS"],
  },
  {
    id: "bare-load",
    why: "裸装载零具名 —— 判据不碰它（永远合法）",
    src: 'import "./core.js";\nconst a = 1;\n',
    expect: [], bodyIncludes: [],
  },
  {
    id: "dollar-real-use",
    why: "`$` 被当真（`$(\"id\")`）",
    src: mk('const el = $("id");', { names: "$", spec: "/js/app.js" }),
    expect: [], bodyIncludes: ["$"],
  },
  {
    id: "quote-inside-regex",
    why: "正则里的引号不能开启字符串状态（否则后面几十行被掩成空白 → 假红）",
    src: mk('const re = /["\'`]/;\nconst h = esc(x);'),
    expect: [], bodyIncludes: ["esc"],
  },
  {
    id: "comment-before-code",
    why: "注释里出现名字、代码里也出现 —— 必须判活（不能因为注释就报）",
    src: mk("// esc 来自 core.js\nconst h = esc(x);"),
    expect: [], bodyIncludes: ["esc"],
  },

  // ── 多名字同一条语句：只报没用的那个 ────────────────────────────────────────
  {
    id: "multi-name-partial",
    why: "同一条语句里一个真用一个没用 —— 只报没用的那个",
    src: mk("const h = esc(x);", { names: "esc, formatSize" }),
    expect: ["formatSize"], bodyIncludes: ["esc"],
  },
];

/** 跑全部用例 → [{ id, ok, why, detail }]（`ok=false` 时 detail 写清实得与应得）。 */
export function syntheticChecks() {
  const results = [];
  for (const c of CASES) {
    const lines = [];
    const got = reported(c.src);
    if (JSON.stringify(got.slice().sort()) !== JSON.stringify(c.expect.slice().sort())) {
      lines.push(`判据实得 ${JSON.stringify(got)}，应得 ${JSON.stringify(c.expect)}`);
    }
    // **注入自检**：语料里 import 之外真的写过这些名字（否则这条用例可能在空转）
    const body = bodyRegion(c.src);
    for (const n of c.bodyIncludes || []) {
      if (!body.includes(n)) lines.push(`注入自检：正文里找不到 \`${n}\` —— 这条用例在空转`);
    }
    // 差分校准
    for (const [key, caliber] of Object.entries(CALIBERS)) {
      if (c[key] === undefined) continue;
      const actual = caliber.run(c.src);
      if (JSON.stringify(actual.slice().sort()) !== JSON.stringify(c[key].slice().sort())) {
        lines.push(`差分校准（${caliber.label}）实得 ${JSON.stringify(actual)}，应得 ${JSON.stringify(c[key])}`);
      }
    }
    results.push({ id: c.id, why: c.why, ok: lines.length === 0, detail: lines.join("；") });
  }
  return results;
}
