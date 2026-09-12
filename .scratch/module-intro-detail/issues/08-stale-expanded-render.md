# 08 — 【作废】点掉 chip 后已选清单「渲染过期展开结果」——经复现证伪，是我方判据误报

**要做什么（原始假设）：** 用户点掉推荐 chip 之后，已选清单必须立刻只反映当前工程里的
模块，不得出现「已从工程移除的模块，仍带着引脚/文件信息挂在清单里」。

**被谁阻塞：** 06、07。

**状态：** wontfix（**结论不成立，已撤回**；保留本文件是为了让下一个人不必重走一遍）

## 为什么当初以为它是 bug

`playwright-deep-audit.mjs` 的 C2 节（单点一次 + expand 注入 700ms 延迟）打出这样一条
时间线，`FAIL` 判据当场报警「过期视图写回」：

```
t+  15ms start        chip已选[ir_beam,motor] 清单「ir_beam 说明 STM32 已验证 …」
t+ 109ms expand→req   chip已选[motor]         清单「已选（未展开依赖）：pid、motor」 body={"slugs":["pid","motor"],…}
t+ 139ms frame        chip已选[motor]         清单「已选（未展开依赖）：pid、motor」
t+ 892ms expand←resp  chip已选[motor]         清单「已选（未展开依赖）：pid、motor」   status=200
t+ 905ms frame        chip已选[motor]         清单「motor 说明 … 移除 TB6612 …」
```

当时的判据是「清单里**看不到** `ir_beam` = 过期写回」。**这条判据写错了**：
`已选（未展开依赖）：pid、motor` **正是正确的占位**——它逐字列出当前选择
（`pid` + `motor`），被点掉的 `ir_beam` **根本不在里面**。那一帧没有任何过期内容。

## 怎么证伪的（三步，缺一不可）

1. **把 `renderSelected` 临时改回原实现的两行分支形状**（`if (!expanded.length) …`
   + 占位文案）→ 真机时间线**照旧**：那一帧仍然只有
   `已选（未展开依赖）：pid、motor`，**从未渲染出 `ir_beam` 的行**。
   「旧展开结果被画出来」这个现象不存在。
2. **注入反例**（点掉后**无条件**按 `expanded` 渲染）→ 清单变成**空**，不是过期行：
   因为 `reRenderAfterSelectionChange` **已经先清了 `expanded`**，
   `renderRecommendResult` 里那次 `renderSelected()` 拿到的就是空数组。
3. **读码确认时序**：点击路径（chip 移除 / 组卡换选）一律
   `expanded = []; warnings = [];` → `renderSelected(); renderWarnings();
   renderRecommendResult(lastRecommend, false)`——**清在前、渲染在后**；
   `addModule` / 切平台同样先清再渲。`renderSelected` 能拿到的 `expanded` 只可能是
   「空」或「本次（上次）请求已落地的新结果」，**不存在「上一个选择集的产物」**。

## 处置

- [x] 撤回结论；本单作废（`wontfix`）。
- [x] 为它写的 `expandedSelectionHTML` 守卫（fx 层纯函数）与那批单测**全部回退**——
  不为假 bug 留代码（本仓口径：不为想象中的未来写代码）。
- [x] 只保留两条**描述既有行为**的判据进 `tests/js/module-intro-detail.test.mjs`：
      ① 占位文案逐字等于当前选择（且不含被点掉的模块）；
      ② 点击路径「清 `expanded` 必须**早于**渲染」——这才是「不会显示过期结果」的
         真正保障，谁把顺序调换就会红。
- [x] 审计脚本的 C / C2 判据改成第三版（**唯一**口径：被移除的模块不得出现在清单里，
      既不能有它的行、也不能被列进占位文案），前两版的误报口径写进脚本注释防重犯。

## 留给后人的一句话

真机 + 时间线 + 请求体三条线都在，**判据写错**照样能得到「铁证如山」的假结论。
同一个症状，我的判据三版分别报 3 帧 / 2 帧 / 0 帧「违规」——看的是**同一段真机输出**。
