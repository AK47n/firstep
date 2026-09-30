// ===========================================================================
// 腿⑨：渲染方内联取色登记簿（工单 light-contrast/04）
//
// **为什么要这条腿**（描边那轮的先例）：样式块面干净**不等于**渲染方干净。
// `static/js/**` 里用模板串拼出来的 `style="color:var(--x)"` 有 19 处——
// 门禁此前只 `readFileSync(index.html)`，**看不见它们**：把某处换成不过线的令牌、
// 或者新拼一处内联色，样式块那三面都不会红。
//
// **形状**：`[文件, 锚点, 前景令牌, 假定底, 类别]`
//   · **锚点 = 该行的一段可认片段**，**不取行号**（行号会随插行漂；本机
//     `Get-Content` 不带 `-Encoding UTF8` 还会把行数读错——描边那轮踩过）；
//   · **假定底 = 这块钱被插进哪层底**（多为 `--panel`）——假定是**登记内容的一部分**，
//     静态判不了真实层叠（`<span>` 进哪张卡由调用方决定）；
//   · **类别**：`text`（文字，4.5）/ `nontext`（色点这类图形，3.0）。
//
// **三面之外还有两处明文不判**（边界写清，免得当地毯）：① 值不是纯令牌的
// 5 处（`#111`/`#eee` 那对高对比浮标、三处 `transparent`）——不构成缺陷，探针每轮盯着；
// ② **跨行拼出来的**取色声明（本仓 0 处，与描边第五条腿的已知留白同类）
// ===========================================================================

const JS_CONTRAST_REGISTER = [
  ["fx/flash.js", 'color:var(--danger-text);font-weight:600">✗ 烧录未成功', "--danger-text", "--panel", "text"],
  ["fx/flash.js", 'color:var(--warn-text);font-weight:600">烧录未就绪', "--warn-text", "--panel", "text"],
  ["fx/task.js", 'const summary = "已完成 <b style=\\"color:var(--ok-text)\\"', "--ok-text", "--panel", "text"],
  ["fx/task.js", 'class="tasks-done-line"', "--ok-text", "--panel", "text"],
  ["fx/task.js", 'border-radius:var(--radius-md);background:var(--panel-2)', "--panel-2", "--panel", "nontext"],
  ["fx/task.js", 'color:var(--warn-text);font-weight:600">⚠ 未验证（上板确认）', "--warn-text", "--panel", "text"],
  ["fx/task.js", 'color:var(--warn-text);font-weight:600">⚠ 未验证（无工具链降级）', "--warn-text", "--panel", "text"],
  ["fx/task.js", 'color:var(--danger-text);font-weight:600">✗ 未通过', "--danger-text", "--panel", "text"],
  ["ui/generate-pins.js", 'class="muted" style="color:var(--warn-text)">已达上限', "--warn-text", "--panel", "text"],
  ["ui/generate-pins.js", 'font-family:var(--mono);color:var(--accent-text)', "--accent-text", "--panel", "text"],
  ["ui/generate-pins.js", 'class="dot" style="background:var(--pin-pad)', "--pin-pad", "--panel", "nontext"],
  ["ui/generate-pins.js", 'class="dot" style="background:var(--pin-fixed-pad)', "--pin-fixed-pad", "--panel", "nontext"],
  ["ui/generate-pins.js", 'style="color:var(--danger-text)">未绑定', "--danger-text", "--panel", "text"],
  ["ui/generate-pins.js", 'style="color:var(--warn-text)">默认板外', "--warn-text", "--panel", "text"],
  ["ui/generate-pins.js", 'style="color:var(--warn-text)">默认 ${esc(r.decl.default)} 与', "--warn-text", "--panel", "text"],
  ["ui/generate-pins.js", 'style="color:var(--warn-text)">默认 ${esc(r.decl.default)} 已被', "--warn-text", "--panel", "text"],
  ["ui/generate-pins.js", 'class="role-status" style="color:var(--warn-text)">共享宏族', "--warn-text", "--panel", "text"],
  ["ui/generate-recommend.js", 'color:var(--muted)">副产物模板', "--muted", "--panel", "text"],
  ["ui/step-state.js", 'toggleBtn.style.cssText = "margin-top: var(--space-2)', "--muted", "--panel", "text"],
];

/** 渲染方内联令牌取色：`[{ file, line, prop, token, text }]`（按文件、行序）。 */
function jsInlineColorEntries(files = jsFiles()) {
  const re = /(?<![\w-])(color|background|background-color)\s*:\s*var\((--[a-z0-9-]+)\)/;
  const out = [];
  for (const [rel, text] of files) {
    text.split("\n").forEach((line, i) => {
      const m = re.exec(line);
      if (m) out.push({ file: rel, line: i + 1, prop: m[1], token: m[2], text: line });
    });
  }
  return out;
}

/** 腿⑨ 的三条判据（纯函数，吃 `files` 与 `register`，红证要喂坏的）。 */
function jsContrastRegisterProblems(files = jsFiles(), register = JS_CONTRAST_REGISTER) {
  const out = [];
  const entries = jsInlineColorEntries(files);
  // ① 盘上每一处都要被登记项认领（同一文件 + 锚点出现在该行 + 令牌一致）
  const claimed = new Set();
  for (const row of register) {
    if (!Array.isArray(row) || row.length !== 5) {
      out.push(`渲染方登记项形状不对（应为 [文件, 锚点, 前景令牌, 假定底, 类别]）：${JSON.stringify(row)}`);
      continue;
    }
    const [file, anchor, token, base, kind] = row;
    if (!["text", "nontext"].includes(kind)) out.push(`渲染方登记项类别只能是 text / nontext：${file} ${anchor}`);
    const hits = entries.filter((e) => e.file === file && e.text.includes(anchor));
    if (hits.length === 0) {
      out.push(`渲染方登记项在盘上一条都找不到（锚点过期 / 文件改名）：${file} —— ${anchor}`);
      continue;
    }
    if (hits.length > 1) {
      out.push(`渲染方登记项锚点不够独特（命中 ${hits.length} 行）：${file} —— ${anchor}`);
      continue;
    }
    const hit = hits[0];
    if (hit.token !== token) {
      out.push(`渲染方登记项的令牌与盘上不一致：${file}:${hit.line} 盘上 ${hit.token} / 登记 ${token}`);
      continue;
    }
    claimed.add(`${file}|${hit.line}`);
    // ③ 比值判据（假定底 + 该令牌）
    const themes = ["dark", "light"];
    for (const theme of themes) {
      const tables = contrastTokenTables(contrastCss(html));
      const fg = tokenValue(token, theme, tables);
      const bg = tokenValue(base, theme, tables);
      if (!fg || !bg) {
        out.push(`渲染方登记项解不出颜色（令牌改名了？）：${file} ${token} on ${base}（${theme}）`);
        continue;
      }
      const ratio = contrastRatio(compositeOver(fg, bg), bg);
      const need = kind === "nontext" ? CONTRAST_THRESHOLDS.large : CONTRAST_THRESHOLDS.small;
      if (ratio < need) {
        out.push(`渲染方 ${file} 的 ${token} 压在 ${base} 上只有 ${ratio.toFixed(2)}:1（要 ≥${need}）`
          + `——改令牌或改它的底（这一面静态判不了真实层叠，假定底写在这条登记里）`);
      }
    }
  }
  // ② 盘上每一处都要被登记（反向）
  for (const e of entries) {
    if (!claimed.has(`${e.file}|${e.line}`)) {
      out.push(`渲染方新出现一处没登记的内联取色：${e.file}:${e.line} —— ${e.text.trim().slice(0, 80)}`
        + "（把它加进 JS_CONTRAST_REGISTER：锚点取该行一段可认片段 + 假定底 + 类别）");
    }
  }
  return out;
}

