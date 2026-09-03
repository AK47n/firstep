// fx/line-diff.js — 文件行级确定性 diff 计算纯函数（工单 code-ide-flow/03
// 自 main.c 起步；code-ide-ai/08 泛化——任意打开过的文件，模块/函数命名随
// 语义去 main.c 特化）
//
// 供「磁盘变更」面板行级展示：基线内容快照 vs 当前磁盘文件内容，输出与
// 后端 deepen.py main_diff 同语义的结构（stats + hunks[{line, title,
// lines[{kind: add|del|ctx, text}]}]）——渲染层直接复用 fx/diff.js
// mainDiffHTML 单源（同一主题化行级展示）。算法 = 行级 LCS（DP 回溯）+
// hunk 分组（difflib.unified_diff n=2 语义：变更块两侧各 2 行上下文，
// 块间距 ≤ 2n 行合并）＋标题规则（删除行 TODO 注释 →「填充 TODO「…」」，
// 退化注释行，再退化空串——与 deepen.py _hunk_title / _comment_text /
// _strip_todo_prefix 逐条对齐，防两套标题观感漂移）。
// 纯函数：无 DOM / 网络 / localStorage（模块约定见 fx/core.js 头部）。
// 超限（行数积 > LINE_DIFF_MAX_CELLS）返回 null——面板显示占位文案。

// 行级 DP 单元格上限（约 2000×2000 行：实际文件远小于此；超限不做——
// O(n·m) 内存与循环在超大输入下不可控，退化占位并保提示可查可改）。
export const LINE_DIFF_MAX_CELLS = 4_000_000;

const TODO_RE = /TODO|FIXME|XXX/i;
const TODO_PREFIX_RE = /^(TODO|FIXME|XXX)\s*([:：-]|$)/i;

// splitlines（对齐 Python str.splitlines 的 \n / \r\n / \r；尾随单个行终止符
// 不产生空行——JS split 会多留一个尾部 ""，pop 掉还原 Python 行数语义）。
function splitlines(s) {
  const t = String(s == null ? "" : s);
  if (t === "") return [];
  const lines = t.split(/\r\n|\r|\n/);
  if (lines[lines.length - 1] === "" && /[\r\n]$/.test(t)) lines.pop();
  return lines;
}

// commentText(line)：行内注释文本（/* … */ 同行 / // 或 /* 起始行），
// 剥前导 * 与空白，无注释 → ""（对齐 deepen.py _comment_text）。
function commentText(line) {
  const m = /\/\*([\s\S]*?)\*\//.exec(line);
  let text;
  if (m) {
    text = m[1];
  } else {
    const i1 = line.indexOf("//");
    let idx;
    if (i1 < 0) {
      idx = line.indexOf("/*");
      if (idx < 0) return "";
      text = line.slice(idx + 2);
    } else {
      text = line.slice(i1 + 2);
    }
  }
  return text.trim().replace(/^\*+/, "").trim();
}

// stripTodoPrefix(text)：「TODO: 循迹」→「循迹」（只剥标记 + 分隔符）
function stripTodoPrefix(text) {
  const m = TODO_PREFIX_RE.exec(text);
  return m ? text.slice(m[0].length).trim() : text;
}

// hunkTitle(lines)：删除行 TODO 注释 → 「填充 TODO「…」」；删除行注释行 →
// 注释文本；上下文注释行 → 注释文本；空串（对齐 deepen.py _hunk_title）。
function hunkTitle(lines) {
  for (const e of lines) {
    if (e.kind !== "del") continue;
    const t = commentText(e.text);
    if (t && TODO_RE.test(t)) {
      const inner = stripTodoPrefix(t);
      return "填充 TODO「" + (inner || t) + "」";
    }
  }
  for (const e of lines) {
    if (e.kind === "del") {
      const t = commentText(e.text);
      if (t) return t;
    }
  }
  for (const e of lines) {
    if (e.kind === "ctx") {
      const t = commentText(e.text);
      if (t) return t;
    }
  }
  return "";
}

// lineDiffCompute(before, after)：旧内容 vs 新内容 → {stats, hunks}
// （无差异 / 超限 → null）。hunks[].line = 新文件起始行号（diff 段内第一个
// 非删除行的 b 侧行号；全删除段取删除位置——对齐 _hunk_new_start 语义）。
// 任意文本文件通用（行级 LCS 与语言无关；code-ide-ai/08 起跨 main.c 泛化）。
export function lineDiffCompute(before, after) {
  const a = splitlines(before);
  const b = splitlines(after);
  if (a.length === b.length && a.every((x, i) => x === b[i])) return null;
  const n = a.length;
  const m = b.length;
  if (n * m > LINE_DIFF_MAX_CELLS) return null;

  // LCS 长度矩阵（行级；n.m 有限——上限已 guard）
  const W = m + 1;
  const d = new Int32Array((n + 1) * W);
  for (let i = n - 1; i >= 0; i--) {
    const base = i * W;
    const next = (i + 1) * W;
    for (let j = m - 1; j >= 0; j--) {
      d[base + j] = a[i] === b[j]
        ? d[next + j + 1] + 1
        : Math.max(d[next + j], d[base + j + 1]);
    }
  }

  // 回溯 ops（equal 优先——保持 ctx 稳定性；del 先于 add 反映删除优先序）
  const ops = [];
  let i = 0;
  let j = 0;
  while (i < n && j < m) {
    if (a[i] === b[j]) { ops.push({ kind: "equal", text: a[i], bIdx: j }); i++; j++; }
    else if (d[(i + 1) * W + j] >= d[i * W + j + 1]) {
      ops.push({ kind: "del", text: a[i] }); i++;
    } else {
      ops.push({ kind: "add", text: b[j], bIdx: j }); j++;
    }
  }
  while (i < n) { ops.push({ kind: "del", text: a[i++] }); }
  while (j < m) { ops.push({ kind: "add", text: b[j], bIdx: j++ }); }

  // hunk 分组：变更连续段 → 间距 ≤ 2n(4) 行 ctx 合并 → 两侧各 2 行 ctx 扩展
  const ranges = [];
  let k = 0;
  while (k < ops.length) {
    if (ops[k].kind === "equal") { k++; continue; }
    const s = k;
    while (k < ops.length && ops[k].kind !== "equal") k++;
    ranges.push([s, k]);
  }
  if (!ranges.length) return null;
  const merged = [];
  for (const [s, e] of ranges) {
    const last = merged[merged.length - 1];
    if (last && s - last[1] <= 4) { last[1] = e; continue; }
    merged.push([s, e]);
  }

  const hunks = merged.map(([s0, e0]) => {
    const s = Math.max(0, s0 - 2);
    const e = Math.min(ops.length, e0 + 2);
    const lines = [];
    for (let x = s; x < e; x++) {
      const op = ops[x];
      lines.push(op.kind === "equal"
        ? { kind: "ctx", text: op.text }
        : { kind: op.kind, text: op.text });
    }
    // 新文件起始行号：第一个非删除行的 bIdx + 1；全删除段 → 删除点（段前
    // 最近 equal 的 bIdx + 1；无 → 1）
    const anchor = ops.slice(s, e).find((o) => o.kind !== "del");
    let line = 1;
    if (anchor && typeof anchor.bIdx === "number") {
      line = anchor.bIdx + 1;
    } else {
      for (let x = s - 1; x >= 0; x--) {
        if (ops[x].kind === "equal") { line = ops[x].bIdx + 1; break; }
      }
    }
    return { line, title: hunkTitle(lines), lines };
  });

  return {
    stats: {
      additions: hunks.reduce((acc, h) =>
        acc + h.lines.filter((l) => l.kind === "add").length, 0),
      deletions: hunks.reduce((acc, h) =>
        acc + h.lines.filter((l) => l.kind === "del").length, 0),
      hunks: hunks.length,
    },
    hunks,
  };
}

// lineDiffFirstChangedLine(diffObj)：lineDiffCompute 结果 → 首个改动行号
//（首个 del/add 所在的行，按 hunk 顺序 + ctx 步进；锚点行 = hunk 起始）——
// 工单 code-editor-refine/08「应用后跳转首处改动行」用（hunk.line 是锚点
// 可含 ctx，非精确首改行）；无改动/空结果 → null。
export function lineDiffFirstChangedLine(diffObj) {
  if (!diffObj || !Array.isArray(diffObj.hunks)) return null;
  for (const h of diffObj.hunks) {
    let line = h.line;
    for (const ln of h.lines || []) {
      if (ln.kind === "ctx") { line += 1; continue; }
      return line;
    }
  }
  return null;
}

if (typeof window !== "undefined") {
  Object.assign(window, { lineDiffCompute, lineDiffFirstChangedLine, LINE_DIFF_MAX_CELLS });
}
