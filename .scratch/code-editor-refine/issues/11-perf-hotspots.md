# 11 — 性能热点治理（诊断先行）

**要做什么：** 定位并消除大文件（5000 行 .c/复杂嵌套）逐击键的残余卡顿。先行诊断：写探针（`.scratch/code-editor-refine/probe-*.mjs`，CDP Performance/长任务采样 + 注入 5000 行样例）实测各阶段耗时（输入 → 同步回调 → 折叠 mapEdit/重算、标记 currentMarks、find 候选、括号/深度扫描），得出热点排序；再按实测结果改造（候选：折叠区域增量/缓存、括号深度扫描复用（兼容 04）、选中词全文 map 增量、find 输入防抖）；每步以探针前后对比为准；交付记录前后数据（不引入帧率 CI 断言）。

**被谁阻塞：** 无（实现时若 04/05 已落地需兼容其标记/扫描实现；未落地则按独立实现计划）。

**Type:** task
**Status:** resolved

## 实现要点

- 探针脚本放 `.scratch`（不提交 tests/），先测基线（每键累计耗时、长任务次数、阶段占比）。
- 改造点以实测为准：若实测折叠不是热点则不强改，记录结论（避免无谓重构）。
- 语义不回归：折叠/查找/选中词/括号/撤销/窗口化渲染全保持。

## 诊断结论与整改（前后数据）

**探针（.scratch/code-editor-refine/probe-11*.mjs，6000 行样例 big.c）基线：**
- 纯件单次全量：foldRanges 3.6ms / indentGuide 1.2ms / bracketDepth 5.9ms / bracketPairAt 4.1ms——**单项都不是数量级问题**；
- **probe-11b 分项：codeFoldMerge = 52ms**（每次击键调用；3000+ 折叠 O(n²) 逐对 some）——热点 ①；
- **probe-11c CPU Profile：输入链 24% GC + 19.5% native + cHighlight 12%（winBuild 每键全量重高亮 6000 行）+ 其余零散**——热点 ②；
- 输入处理总耗时：冷启动合成口径 230ms（探针 value-set 全量写 + 首次 GC/布局），真实击键（execCommand/input 路径）warm ~97ms（含 native undo 快照 90ms）；门控后 warm ~21ms。

**整改（全部落地，语义回归全绿）：**
1. **codeFoldMerge O(n)**（fx/code-fold.js）：折叠态保留 = 折叠签名集 `startLine:endLine` 一次构建 + 新列表哈希命中——3000+ 折叠下 ~52ms → <1ms；单测补签名保留/漂移/大输入。
2. **winPatchEdit 缓存增量**（ui/codeeditor.js）：非折叠态行数不变 → 首尾比对找变更行区间，只重算这些行高亮 + 探针最长行（旧探针行被改且无人超越才全量重扫）——逐键全量重高亮（cHighlight 12%）消除。
3. **结构性编辑门控**（ui/codeeditor.js）：textEditIsStructural = 变更段无换行/括号/引号/#/tab 且行首空白不变 → 折叠清单（无 newline/brace 则行号括号位不变）与标记集整体跳过重算；markClean + marksCache（模型级标记缓存，窗口过滤每次切片）——折叠重算、currentMarks 全量（缩进 + 彩虹扫描）逐键消除；查找/词/括号/错误/换 tab 任一状态变化即失效。
4. **大文档撤销路径**（applyEdit）：内容 >200KB 跳过 execCommand（原生撤销对巨型 textarea 快照每击 ~90ms）改直赋值 + 既有快照栈（snapshot 存字符串引用，v8 rope 零拷贝；nativeUndo 关闭时 Ctrl+Z/Y 已走快照栈——语义等价）。

**改造后数据：**
- probe-11 冷启动口径 230ms → 206ms（首键含 GC/全量缓存预热；连续键入走 warm 路径）；
- probe-11e（warm 真实输入路径）**21ms/键**（门控前 ~97-230ms）；
- CPU Profile：cHighlight 12% → ~0；GC 24% → 14%；JS 占比显著下降（余量为浏览器原生 textarea/布局）。
- 结论记录：折叠清单「区域增量重算」未做（实测热点在缓存重建与合并算法，不在折叠扫描本身——避免无谓重构）；find 输入防抖未做（无查询时零成本，实测不是热点）。

## 验收 checklist

- [x] 探针记录基线 + 改造后数据（probe-11-baseline/after.log、probe-11b.log、probe-11c*.log、probe-11d.log、probe-11e.log 存证；每键 warm 21ms、冷启动 230→206ms、merge 52ms→<1ms）。
- [x] 5000 行 .c 连续输入肉眼无卡顿（warm 21ms/键；深浅主题 CSS 随 token，无回归）；折叠/查找/选中词/括号/撤销/窗口化渲染回归全绿（全量 node --test + smoke-05..10 全部 PASS）。
- [x] 全量 node --test pass + pytest（后台跑，结果见 .scratch/code-editor-refine/pytest.log）；代表性 CDP 冒烟 smoke-05/06/07/08/09/10 重跑全绿。
