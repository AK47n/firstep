// 确定性复现（第十轮）：把「目录加载竞态」从偶发变成必现 —— 注入 fetch 垫片，
// 让**先发起**的那次 /api/code/open 晚 800ms 返回（后发起的先回）。
//
// 为什么不用自然复现：实测偶发率约 1/10（本机 webapp 单端点 ≈500ms，
// diag-save-switch-flake.mjs 十轮 1 次），A/B 对照要几十轮才有统计意义。
// 垫片把「晚到」这一条件**固定**下来，于是单轮即可判定：
//   · 有 codeDirSeq 守卫（现行代码）→ 树 = 新目录的文件清单（late 响应被丢弃）
//   · 无守卫（stash src/ 后）        → 树 = 旧目录的文件清单（late 响应覆盖）
//
// 用法：node .scratch/code-editor-perf-structural/diag-dir-race-deterministic.mjs
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

// fetch 垫片：只对「首次」/api/code/open 加 800ms 延迟（= 先发起的那次晚到）
await Eval(`(() => {
  window.__raceLog = [];
  const orig = window.fetch;
  let seen = 0;
  window.fetch = async (input, init) => {
    const url = typeof input === 'string' ? input : (input && input.url) || '';
    const isOpen = url.includes('/api/code/open');
    if (isOpen) {
      seen += 1;
      if (seen === 1 && init && typeof init.body === 'string' && init.body.includes('sample-proj')) {
        window.__raceLog.push('delay#1 ' + JSON.parse(init.body).dir);
        await new Promise((r) => setTimeout(r, 800));
      } else {
        window.__raceLog.push('fast#' + seen + ' ' + (init && init.body ? JSON.parse(init.body).dir : ''));
      }
    }
    return orig(input, init);
  };
  return true;
})()`);

const result = await Eval(`(async () => {
  const { openCodeViewer } = await import('/js/ui/codeview.js');
  // 两次加载交叠：A 先发起（被垫片推迟 800ms），B 后发起（先返回）
  openCodeViewer(${JSON.stringify(DIR_A)});
  await new Promise((r) => setTimeout(r, 50));
  openCodeViewer(${JSON.stringify(DIR_B)});
  await new Promise((r) => setTimeout(r, 3000));
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
  ? "PASS 树 = 新目录清单（晚到的旧目录响应被丢弃 → 守卫生效）"
  : "FAIL 树 = 旧/错目录清单（晚到响应覆盖了新目录 → 无守卫）");
c.close();
process.exit(ok ? 0 : 1);
