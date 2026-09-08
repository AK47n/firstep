// 冒烟（code-editor-utilize/02）：步骤 8「编辑 main.c」——建立生成上下文
// （setMainCDiskContext，同 generate-mainc-sync 服务端落盘真相的页面态）→
// 点 btn-edit-mainc → tab-code 激活 + main.c 标签打开且为活动标签；
// 「查看工程」仍只开目录（无指定文件）。
import { connect, SAMPLE } from "./cdp.mjs";

const { Eval, waitFor, check, summary } = await connect();

// 建立生成上下文并回生成页（步骤 8 按钮在生成页）
await Eval(`import('/js/ui/generate-mainc-sync.js').then((m) => m.setMainCDiskContext(${JSON.stringify(SAMPLE)}))`);
await Eval(`document.querySelector('nav button[data-tab="generate"]').click()`);
await waitFor(`document.getElementById('tab-generate').classList.contains('active')`);
check("步骤8「编辑 main.c」按钮存在", await Eval(`!!document.getElementById('btn-edit-mainc')`));
await Eval(`document.getElementById('btn-edit-mainc').click()`);
check("编辑 main.c：tab-code 激活", await waitFor(`document.getElementById('tab-code').classList.contains('active')`));
check("编辑 main.c：main.c 标签打开且活动", await waitFor(`(() => {
  const t = document.querySelector('.code-tab[data-tab-path="main.c"]');
  return !!t && t.classList.contains('on');
})()`));
check("编辑 main.c：中栏渲染 main.c", await waitFor(`document.querySelector('.code-ta') && document.querySelector('.code-ta').value.includes('main(void)')`));

// 「查看工程」= 只开目录（清标签后验证不自动开会话文件）
await Eval(`document.querySelector('nav button[data-tab="generate"]').click()`);
await Eval(`document.getElementById('btn-goto-code-mainc').click()`);
await waitFor(`document.getElementById('tab-code').classList.contains('active')`);
await waitFor(`document.querySelectorAll('#code-tree [data-code-file]').length === 5`);
check("查看工程：仅目录（无自动打开的标签）", await Eval(`document.querySelectorAll('.code-tab').length === 0`));

summary();
