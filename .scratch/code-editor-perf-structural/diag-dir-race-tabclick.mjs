// 确定性复现（第十一轮）：第二个目录竞态 —— 「切 tab 的 checkCodeDiskChanges 探测旧目录」。
//
// 为什么必须确定性：自然复现率 ≈1/4（`diag-batch-loop.mjs` 8 轮 2 次、10 轮 2 次），
// 单轮判定不了守卫有没有用。这里用 fetch 垫片把**触发条件**固定下来：
//
//   失败序列（CDP 观测器实测，第十一轮取证）：
//     ① openCodeViewer(B) 先 `btn.click()` 切「代码」tab → nav 处理器**同步**调
//        checkCodeDiskChanges()，此刻 codeDir 还是 A → 对 **A** 发起 /api/code/open；
//     ② 随后 setCodeDir(B) 才把 codeDir 改成 B，并对 **B** 发起探测；
//     ③ B 先返回（本机 7ms）、A 后返回（10ms）→ 若 probeDiskBaseline 无条件写
//        `codeFiles`，A 的清单就覆盖 B 的 → 树渲染 main.c 而标签显示 b →
//        用户点 other.c 点不到（「没有活动标签 / 编辑器空白」）。
//
// 垫片把第 ③ 步固定成「第一次 /api/code/open（= A 那次）晚 800ms 返回」，
// 于是条件必现、单轮即可判定：
//   · 有守卫（现行代码）→ 树 = B 的清单（other.c），A 的晚到响应被丢弃
//   · 无守卫（stash src/ 后）→ 树 = A 的清单（main.c）而标签 = b
//
// 用法：node .scratch/code-editor-perf-structural/diag-dir-race-tabclick.mjs
import { mkdirSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { rebuildTab, connect } from "../cdp-harness.mjs";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const OUT = join(ROOT, ".scratch", "code-editor-refine");
const DIR_A = join(OUT, "sample-proj", "a");
const DIR_B = join(OUT, "sample-proj", "b");
mkdirSync(DIR_A, { recursive: true });
mkdirSync(DIR_B, { recursive: true });
writeFileSync(join(DIR_A, "main.c"), "int a = 1;\n");
writeFileSync(join(DIR_B, "other.c"), "int b = 2;\n");

await rebuildTab({ port: 9251, pageUrl: "http://127.0.0.1:8000/", settleMs: 2000 });
const c = await connect({ port: 9251, pageUrl: "http://127.0.0.1:8000/" });
await c.cdp("Page.enable");
const Eval = (e) => c.Eval(e);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// 垫片：把**第一次** /api/code/open（= 切 tab 时对旧目录 A 的那次）推迟 800ms
await Eval(`(() => {
  window.__raceLog = [];
  const orig = window.fetch;
  let seen = 0;
  window.fetch = async (input, init) => {
    const url = typeof input === 'string' ? input : (input && input.url) || '';
    if (url.includes('/api/code/open')) {
      seen += 1;
      let dir = '';
      try { dir = JSON.parse(init.body).dir; } catch {}
      const tag = dir.split(/[\\\\/]/).pop();
      if (seen === 1) {
        window.__raceLog.push('delay#1 ' + tag + ' (切 tab 的 checkCodeDiskChanges)');
        await new Promise((r) => setTimeout(r, 800));
      } else {
        window.__raceLog.push('fast#' + seen + ' ' + tag + ' (loadCodeDir)');
      }
    }
    return orig(input, init);
  };
  return true;
})()`);

// 先正常打开 A 并等树就位（此后 codeDir = A，基线已建立）
await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(DIR_A)}))`);
await c.waitFor(`!!document.querySelector('#code-tree [data-code-file="main.c"]')`, 15000);
// 复现本竞态：**不**等任何东西，立刻切到 B（openCodeViewer 会先点 nav tab）
const result = await Eval(`(async () => {
  const { openCodeViewer } = await import('/js/ui/codeview.js');
  openCodeViewer(${JSON.stringify(DIR_B)});
  await new Promise((r) => setTimeout(r, 3000));   // 等晚到的 A 响应落地
  const box = document.getElementById('code-tree');
  return {
    label: document.getElementById('code-dir-label').textContent.split(/[\\\\/]/).pop(),
    treeFiles: [...box.querySelectorAll('[data-code-file]')].map((b) => b.dataset.codeFile),
    treeText: box.textContent.trim().slice(0, 40),
    raceLog: window.__raceLog,
  };
})()`);

console.log("请求序：" + JSON.stringify(result.raceLog, null, 1));
console.log(`标签目录 = ${result.label}`);
console.log(`树内文件 = ${JSON.stringify(result.treeFiles)}`);
const ok = result.label === "b" && result.treeFiles.length === 1 && result.treeFiles[0] === "other.c";
console.log(ok
  ? "PASS 树 = 新目录清单（切 tab 那次对旧目录的晚到响应被丢弃 → 守卫生效）"
  : "FAIL 树 = 旧目录清单（旧目录的晚到响应覆盖了新目录 → 无守卫）");
c.close();
process.exit(ok ? 0 : 1);
