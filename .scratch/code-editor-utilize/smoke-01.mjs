// 冒烟（code-editor-utilize/01）：打开桥指定文件——openCodeViewer(dir, filePath)
// → tab-code 激活 + 该文件标签打开且为活动标签（等价覆盖结果区 chips 点击
// 链路；chips 事件绑定 = 同一 openCodeViewer 调用，见 generate-core.js）。
import { connect, SAMPLE } from "./cdp.mjs";

const { Eval, waitFor, check, summary } = await connect();

await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}, '设计报告草稿.md'))`);
check("桥打开：目录加载（树出现）", await waitFor(`document.querySelectorAll('#code-tree [data-code-file]').length === 5`));
check("桥打开：tab-code 激活", await Eval(`document.getElementById('tab-code').classList.contains('active')`));
check("桥打开：产物标签打开且活动", await waitFor(`(() => {
  const t = document.querySelector('.code-tab[data-tab-path="设计报告草稿.md"]');
  return !!t && t.classList.contains('on');
})()`));
check("桥打开：中栏渲染该文件（md 默认预览态）", await waitFor(`document.querySelector('.code-md-preview') && document.querySelector('.code-md-preview').textContent.includes('系统方案')`));

// 变量目录切换 + 指定 src/imu.c（子目录路径）
await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}, 'src/imu.c'))`);
check("桥打开：子目录文件标签", await waitFor(`!!document.querySelector('.code-tab[data-tab-path="src/imu.c"].on')`));

summary();
