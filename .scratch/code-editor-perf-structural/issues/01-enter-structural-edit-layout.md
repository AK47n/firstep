# 01 — 5000 行文件结构性编辑（回车）仍 ~76ms：整树重排是主成本

**要做什么：** 5000 行 .c 文件下，**结构性编辑**（回车/粘贴换行等使行数变化）的输入同步耗时仍
超出 `smoke-09` 阈值（<50ms 均值）。非结构性路径（逐键字符、Tab 缩进）本轮已达标（3–10ms），
本条只针对「行数变化」这一类。

**被谁阻塞：** 无——可立即开始（诊断数据已就位，见下）。

**Type:** task
**Status:** resolved

## 现状（2026-09-09 第七轮实测，webapp 8000 + Chrome headless CDP 9251）

`node .scratch/code-page-vscode-overhaul/smoke-09.mjs`（5000 行 `big.c`，12 次/路径）：

| 路径 | 第七轮修复前 | 第七轮修复后 | 阈值 |
|---|---|---|---|
| 逐键字符 | 55.8ms **FAIL** | **3.4ms PASS**（峰值 4.3） | <50 均值 / <150 峰值 |
| Tab 缩进 | 63.3ms **FAIL** | **10.0ms PASS**（峰值 13.9） | 同上 |
| **回车** | 131.4ms **FAIL** | **76.1ms 仍 FAIL**（峰值 97.2 PASS） | 同上 |

分阶段墙钟（`performance.mark` 打点，回车 4 次，修复后）：

```
sync-start 1.7 → word 1.7 → bracket 5.4 → winBuild 11.1 → winRender 结束 → winApplySize 45.8
→ taWindowApply 结束 76.0 → renderTabs/notify 77.7
```

即：**`winBuild + winRender` ≈ 9ms、`winApplySize` ≈ 35ms、`taWindowApply` ≈ 30ms**。

## 已排查/已修（不要再重复查）

- ✅ 宽度探针每次回车重跑 → 强制深布局 ≈50ms：`winApplySize` 的 `winSize.cols` 被行数变化重置，
  已改为「只有行高变化才失效重测」（第七轮修复，`ui/codeeditor.js`）。
- ✅ 输入路径读 `box.clientHeight` 触发强制布局：`taApplyWindowStyle` 已改取 `winView.viewportH`
  缓存（第七轮修复）——这条把逐键/Tab 从 55/63ms 拉到 3/10ms。
- ✅ `.code-edit` 高度写本身实测 **0.1ms**（`performance.mark` 夹逼），说明 35ms 不是 JS 耗时，
  而是**样式失效后的布局/绘制**（在下一步几何读或帧末落账，计时器会把它记在相邻阶段上）。

## 待办方向（按可行性排序）

1. **结构性编辑不整树重排**：`.code-edit` 高度 = 行数 × 行高（5000 行 ≈ 104k px）。行数 +1 时
   是否必须重写高度？可试：只在大跨步变化（如 ±32 行）时才写、或把高度写移到 rAF 之后
   （避免同帧布局失效传导到输入同步路径）。
2. **`winBuild` 降频/增量**：行数变化走全量 `winBuild`（重建 gutter 数组 + 行起点表 + 行态）。
   大文件可只重建受影响区段（行号数组尾部偏移 + gutter 片段），或 gutter 也窗口化（只建窗口行）。
3. **`taWindowApply` 的窗口重装**：回车后光标换行 → 窗口可能重算 → 重建窗口文本 + 重装。
   可试：光标仍在窗口内时不做全量重装（只更新 `absStart` 与选区）。

## 验收 checklist

- [x] `smoke-09.mjs` 回车路径均值 < 50ms（峰值 < 150ms）——现有断言即验收标准，实跑通过。
- [x] 逐键 / Tab 路径不回归（当前 3.4 / 10.0ms）。
- [x] `smoke-01.mjs`（24/24，行操作 + 折叠 + 保存）、`smoke-08.mjs`（13/13，滚动窗口化）
      实跑不回归。
- [x] `tests/js` 全量绿（当前 1393 pass）；`code-window.test.mjs` / `code-editor-window-guard.test.mjs`
      若涉及窗口几何，补对应用例。

## Comments

- 2026-09-09 第七轮：用户拍板「另开性能工单」。本条不是第七轮改动的回归——第七轮只减少强制布局
  （两处已修，见上），回车从 131.4ms 降到 76.1ms；剩余部分是窗口化渲染在**行数变化**时的固有成本。
- 相关：`code-page-vscode-overhaul/08`（滚动窗口化）、`09`（输入窗口化）、
  `editor-textarea-viewport/02`（textarea 窗口化）——本条是它们的性能收尾。
- **2026-09-09 第九轮收口（实跑，webapp 8000 + Chrome headless CDP 9251）**：
  根因不是「整树重排不可避免」，而是 `syncTail` 里一次**读→写回同值**的滚动恢复。

  **定位**（`.scratch/code-editor-perf-structural/diag-enter-path.mjs`：把
  `Element.prototype` 的 `scrollTop/scrollLeft/clientHeight/offsetHeight/offsetTop/
  offsetWidth/getBoundingClientRect` 包一层，统计同步路径里的调用点与各自耗时）：

  | 访问器 | 次数/回车 | 耗时/回车 | 调用点 |
  |---|---|---|---|
  | `box.scrollTop` 读 | 1 | **33.7ms** | `syncTail`（`ui/codeeditor.js` 旧 2432 行） |
  | `box.scrollTop` 写 | 1 | **30.6ms** | `syncTail`（旧 2439 行） |
  | `scrollLeft` 读/写 | 1+1 | ≈0 | 同上（值恒 0） |

  两处都在 `winRender`（写 innerHTML）+ `winApplySize`（写 `.code-edit` 高度）**之后**
  ——布局已失效，读 `scrollTop` 强制一次整树深布局（5000 行 ≈104k px），
  写 `scrollTop` 需要 scroll extent 再强制一次。而写回的值与刚读到的值**相同**，
  语义上是 no-op（浏览器自身保持 scrollTop，内容变矮时按需钳制；窗口切片读
  `winView.scrollTop` 缓存）——所以整段删除，一并去掉 `needScrollRestore`。

  **修复**：`ui/codeeditor.js` `syncTail` 删除 `box.scrollTop/scrollLeft` 的读与写
  （带注释说明为什么不需要人工保持 + 为什么同步路径一律不碰滚动访问器）。

  **实测**（`verify-structural-edit.mjs` 10/10、`smoke-09.mjs` 15/15、
  `diag-enter-path.mjs`）：

  | 路径 | 第七轮 | 第九轮 | 阈值 |
  |---|---|---|---|
  | 回车（结构性编辑） | 76.1ms（本条诊断时 78.9ms） | **9.8–13.6ms**（峰值 11.5） | <50 均值 |
  | 同步路径布局强制读 | 2 次（≈64ms） | **0 次** | — |
  | 逐键 / Tab | 3.4 / 10.0ms | 9.5ms（Tab，同量级） | <50 均值 |

  滚动语义未回退（新增断言）：中部滚动后回车 → `scrollTop` 不变（40000 → 40000）、
  可见窗口行号序列不变（1903 起 62 行，前后一致）、内容高度确实 +21px（1 行）。

  **顺带修出（同一轮实跑暴露，均带实跑证据）**：
  1. **标记缓存被状态段污染**（产品缺陷）：`winRenderMarks` 复用分支把
     `base.concat(extra)` 的结果写回 `marksCache.marks` → 下次复用把上一次的
     括号/词/查找段当基础段带回来（`polish/smoke-06`「光标移开 → 括号标记消失」、
     `polish/smoke-05`「光标移到 '{' → 词标记消失」两处红，基线（stash 本改动）
     同红 → 与本条改动无关的既有缺陷）。修法 = 缓存只存基础清单。
  2. **`smoke-08` 「窗口内滚动零 DOM 变更」断言写死 +5px**：窗口 `[start,end)` 由
     `codeWindowRange` 按滚动偏移精确重算，5px 可能跨过底部边界（实测
     `end 2541 → 2542`），DOM 行数变 1 是**正确行为**。修法 = 用同一纯件现算
     「不跨边界」的位移再断言零变化（该断言此前对滚动位置敏感，批次里必红）。

  **回归证据**：`overhaul` 9 支全绿（01 24/24、08 13/13、09 15/15）、
  `polish` 8 支全绿、`refine`/`viewer`/`ideai`/`treeops`/`ideflow`/`bridge` 全绿、
  库 UI 4 支全绿（master 17、reference 47、pdf 51、module 71）、
  `tests/js` **1400 pass / 0 fail**（+4 守卫用例）、`pytest` **3928 passed**
  （零回归）。守卫：`tests/js/code-editor-window-guard.test.mjs` 新增
  「`syncTail` 不读/写 `scrollTop`」「缓存只存基础清单」「smoke-08 不写死位移」
  三例（静态源断言 + 冒烟断言防放宽）。
