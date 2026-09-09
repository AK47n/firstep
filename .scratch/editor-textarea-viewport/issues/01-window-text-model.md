# 01 — 纯件：窗口文本模型（构建 / 编辑映射 / 一致性校验）

**要做什么：** 把「textarea 窗口文本 ↔ 模型全文」的映射做成可单测的 fx 纯件：
①窗口文本构建（模型/视图文本 + 窗口行区间 → 窗口文本 + 偏移表：窗口起点绝对
偏移、行映射）；②窗口编辑映射（窗口文本变更段 → 模型绝对变更段，含折叠态
视图→模型一环）；③一致性校验（由模型推导的预期窗口文本 ≠ 实际 → 可检出）。
三者构成视口化的脑子，ui 只做搬运。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

**交付（双轴 code-review 整改后）：**
- fx/window-text.js：windowTextBuild（{start,end,text,winLineStarts,absStart}
  窗口对象；start 钳制 ≤ len）、windowEditToView（越界/不同步 → **null**
  不静默归零；空窗口插入映射到窗口起点）、windowEditToModel（非折叠绝对段
  直替换；折叠态经 codeFoldMapEdit 承接「触碰占位 → 展开/整块覆盖」语义）、
  windowTextMatches / windowTextMatchesModel（视图层 / 模型推导层校验）。
- 单源整改（Standards 轴）：buildLineStarts/caretLineFromStarts 直接 import
  fx/codeeditor.js（删除局部复制），测试同样 import 生产函数（删除第三份
  拷贝）；winInfo/winLineStarts 命名与窗口对象聚合消除 Data Clumps 与
  同名异义。
- Spec 轴整改：折叠映射（原声称拥有而未实现）已兑现（windowEditToModel +
  占位触碰测试）；空窗口插入恒 p=0 → 修复并补测；越界 `||0` 静默归零 →
  null 失配；窗口起点绝对偏移（absStart）输出；「往返一致/折叠+占位/跨窗口
  边界/模型推导校验」测试补齐（11 用例全绿）。
- 全量 node 1286 绿；window-text 导入链无环（window-text → codeeditor/
  code-fold/edit-patch，下游无反向依赖）。

- [x] 窗口文本构建：非折叠（模型即视图）与折叠（视图文本 + 占位行）两形态；
      窗口 [start,end) + overscan；输出窗口文本与逐行绝对偏移表。
- [x] 窗口编辑映射：输入窗口文本变更（editChangeSpan 口径）→ 变更段绝对偏移
      （窗口起点 + 段内偏移）→ 折叠映射（存在折叠时）→ 模型段；与「模型直接
      编辑」逐字节一致。
- [x] 一致性校验：窗口文本重建函数可对拍（幂等 + 随机编辑后仍一致）；
      模型推导窗口文本 ≠ textarea 实际 → 返回失配标志。
- [x] node 单测：往返一致（模型→窗口→回写→模型）、插入/删除/跨窗口边界、
      折叠 + 占位行组合、错位可检出、空文/单行窗口。


## Comments

- 2026-09-09 在途盘点（第二轮）：本单未勾项经代码事实逐条核对，判定全部为「已实现（勾选没跟）」——证据见 `.scratch/tracker-audit/2026-09-09-在途盘点.md`（判定总表按批次给出 `文件:行号` / 测试文件名 / grep 否证）。本次只勾选 + 状态归一 resolved，未改任何验收项文字。
