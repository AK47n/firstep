# 调研笔记 — 工单 02 打开路径改动面（textarea 视口化）

（工单 editor-textarea-viewport/02 实施前参考；基于 2026-… 源码实读）

## 现状链路（打开 6000 行 .c）

1. `openEditorFile(path)`（ui/codeeditor.js）→ `loadFileState` fetch
   `/api/code/file`（~58ms，后端含 clex outline 扫描）→ 建 tab → `activateTab`
   → `renderPane()`。
2. `renderPane()`：
   - `box.innerHTML = gutter 空壳 + codeEditorHTML(src, lang, {marks: [], windowed: true}) + 探针 span`；
   - `codeEditorHTML`（fx/codeeditor.js）≈ `div.code-edit > pre.code-hl + pre.code-marks + textarea.code-ta`，
     windowed 时 hl/marks 留空壳，**textarea 内嵌全文**（`esc(src)`，108KB）；
   - `winBuild(src, lang)`：split 全文 → gutter 全量（轻）→ **hl 惰性占位**
     （工单 06 已改）→ lineStarts/行数组/探针；
   - `winApplySize()`：`.code-edit` 显式 height = 全量行数×行高（12.6 万 px）、
     宽度 = 最长行实测（工单 06 已改脱离文档流探针）；
   - `winRender()`：窗口 hl/gutter/marks 三层（~56 行 + spacer）；
   - `if (!viewModel) folds = codeFoldRanges(...)`（全量扫描，少量）；
   - `refreshMarkSetters()`（词/括号状态 + 首渲染）。
3. 打开渲染大头 = **textarea 全量 108KB + .code-edit 12.6 万 px 巨盒布局**
   （~195ms 拆解值）。

## 02 改动面（初拟）

| 位置 | 现状 | 视口化后 |
|---|---|---|
| `.code-ta` CSS（index.html） | `absolute; inset:0; height:100%`（铺满巨盒） | 视口高 + **贴视口**（sticky 或移出滚动层）——实现时选型并 CDP 验证 |
| `codeEditorHTML`（fx） | textarea 内容 = 全文 | 内容 = 窗口文本（01 纯件构建）；textarea 高 = 视口 |
| `renderPane` | innerHTML 后 winBuild/ApplySize/Render | 同上 + 首窗口文本装载 + 光标窗口内定位 |
| `winBuild/winCache` | lines/lineStarts/hl/lang 已有 | 增存「当前窗口文本窗口 [start,end) + winStartAbs」，供输入回写与一致性校验 |
| `syncEditorAfterInput` | ta.value = 全文 → editChangeSpan → 模型 | ta.value = 窗口文本 → 01 映射 → 视图/模型绝对段 → 模型更新；结构编辑/跨窗口先切窗口 |
| `applyEdit` | 写 ta.value 全文（execCommand/直赋值） | 03 工单改模型级（本切片先保持现状？——**不行**：02 打开后 Tab/Enter 等程序化路径会破；02 与 03 需同一批次切换或 02 先禁用程序化入口——实现时决策） |
| 光标/行列/跳转 | caretLineFast + editorCaretModelPos（模型层，已与 ta.value 解耦） | 基本不动（模型层读 tab.content）——主要检查「选区设置」入口统一走窗口偏移 |
| 滚动 | scroll → winReadView + winRender（无 textarea 同步） | 04 工单：窗口切换 + textarea 重装 + 光标定位（02 先不接滚动重装，仅锁定打开窗口——**注意**：02 期间滚动会导致 textarea 窗口文本与视图错位 → 02 必须先接「滚动即切换窗口」或保守禁用滚动重装（用一致性校验兜底）——实现时决策，倾向 02 就接最简切换（rAF 节流可在 04 加） |

## 风险点（02 验收必须覆盖）

- 打开后**立即滚动**（不输入）：窗口文本是否跟随（不跟随则 textarea 内容与
  高亮错位 → 光标/选区漂移）。
- 打开后**立即输入**：手打字符回写模型正确、光标不跳。
- **结构编辑**（Enter 新增行/删换行）：行数变化 → 窗口重算 + textarea 重装 +
  光标落位；光标贴着窗口边界。
- **跳转**（大纲/查找）：光标目标在窗口外 → 先切窗口再定位。
- **一致性校验**：任何失配（粘贴/跨窗口）→ 以模型重建窗口文本。
- 折叠态：02 保持「折叠时 textarea 全量视图文本」现状（不与窗口组合），
  04 打通三层；02 需确保折叠开合时窗口文本路径不乱。
