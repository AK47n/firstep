# 06 — 修：推荐 chip 的选择态与实际不一致（点掉后仍显示已选、且加不回来）

**要做什么：** 推荐区每个模块 chip 变成**双向选择开关**，且界面与工程严格一致：
点 ✕ → 从工程移除 **且 chip 立刻变未选态**（灰显虚线 + ＋）；点未选 chip → 加回工程
**且 chip 回已选态**。用户不会再看到「chip 绿着说在、工程里其实没有」。

**被谁阻塞：** 03（chip 上加了说明按钮，本次动的是同一个 chip 的交互）。

**状态：** resolved

- [x] `recommendChipHTML(slug, reason, selected)`：按选择态渲染（已选 = 绿底 ✕ /
      未选 = 虚线灰显 ＋），缺省 `selected` = true（旧调用点零变化）。
- [x] 渲染点按 `selectedSlugs` 判态（原来一律按 done 载荷的 `modules` 渲染 = 点掉后
      仍显示已选）。
- [x] 点击双向：已选 → 移除（连带清功能组记账）；未选 → 加回（`addModule(slug, false)`
      + `reRenderAfterSelectionChange()`，同一次重绘里刷新 chip 态）。
- [x] 样式：`.chip.rec.unsel`（虚线灰显 + ＋ 用 ok 色，与绿底已选态形成可读对比）。
- [x] JS 单测（渲染两态 / 双向接线）+ 真机验收（点掉 → 未选态 + 选择集去掉；点回 →
      已选态 + 选择集回填）。
- [x] 修完 `pytest` 全量绿、`node --test tests/js/*.test.mjs` 绿、真机 6/6 绿。

**修的过程里查清的两件事（都靠真机 + 探针，不靠猜）：**

1. **加回后 chip 不回已选态**，根因是 `addModule` 只重绘「已选清单 / 警告 / 模块池」，
   **从不重绘推荐区**——于是 chip 停在上一次的类名上。修法 = 加回时 `expand=false`
   不重复触发展开，改由开关统一走 `reRenderAfterSelectionChange()`（chip 与已选清单
   在同一次重绘里一致）。
2. **顺带消掉一处竞态**：原 `addModule` 会 `runExpand()`，而「点掉」路径不展开——
   于是加回时后台那次 `/api/selection/expand` 落地会把已选清单刷成**中间态**
   （探针实测：点回后 120ms 已选清单变成只剩 `motor`，`ir_beam`/`pid` 消失）。
   现在两侧都不自动展开，行为一致，该中间态不再出现；用户点「展开检查」照常生效。

**范围外（如实记录）**：`/api/selection/expand` 与前端选择集之间的一般性竞态
（连点期间后台响应落地覆盖视图）未在本单展开调查——本单只保证 chip 开关自身的
两态正确，并顺带让两条路径的展开行为一致。
