# 01 — 5000 行文件结构性编辑（回车）仍 ~76ms：整树重排是主成本

**要做什么：** 5000 行 .c 文件下，**结构性编辑**（回车/粘贴换行等使行数变化）的输入同步耗时仍
超出 `smoke-09` 阈值（<50ms 均值）。非结构性路径（逐键字符、Tab 缩进）本轮已达标（3–10ms），
本条只针对「行数变化」这一类。

**被谁阻塞：** 无——可立即开始（诊断数据已就位，见下）。

**Type:** task
**Status:** ready-for-agent

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

- [ ] `smoke-09.mjs` 回车路径均值 < 50ms（峰值 < 150ms）——现有断言即验收标准，实跑通过。
- [ ] 逐键 / Tab 路径不回归（当前 3.4 / 10.0ms）。
- [ ] `smoke-01.mjs`（24/24，行操作 + 折叠 + 保存）、`smoke-08.mjs`（13/13，滚动窗口化）
      实跑不回归。
- [ ] `tests/js` 全量绿（当前 1393 pass）；`code-window.test.mjs` / `code-editor-window-guard.test.mjs`
      若涉及窗口几何，补对应用例。

## Comments

- 2026-09-09 第七轮：用户拍板「另开性能工单」。本条不是第七轮改动的回归——第七轮只减少强制布局
  （两处已修，见上），回车从 131.4ms 降到 76.1ms；剩余部分是窗口化渲染在**行数变化**时的固有成本。
- 相关：`code-page-vscode-overhaul/08`（滚动窗口化）、`09`（输入窗口化）、
  `editor-textarea-viewport/02`（textarea 窗口化）——本条是它们的性能收尾。
