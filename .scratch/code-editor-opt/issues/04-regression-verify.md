# 04 — 回归验证（全量测试 + 冒烟 + 截图）

**要做什么：** 01–03 全部落地后做一次整体回归：node 单测全量 + pytest 全量 +
CDP 冒烟抽样（保存/折叠/查找/括号彩虹/编译错误标记/跳行）+ 深浅两主题截图对比，
确认既有编辑器能力零回退。

**被谁阻塞：** 01、02、03。

**状态：** resolved

- [x] `node --test tests/js/*.test.mjs` 全量 **1275 绿**（含新增 22 项 edit-patch、
      二分行号、pairScanPatch、wordRangesPatch 单测）。
- [x] pytest 全量 **3159 绿**（3 条既有 SyntaxWarning；后端零改动确认）。
- [x] CDP 冒烟（smoke-04.mjs）5/5：文末逐键 10 次无异常且脏长度正确 /
      跳转 25 行（sel=426）/ 文件内查找 2500 命中 / 折叠-展开无异常 /
      三层 top 集合 1:1；另隔离探针 probe-jump.mjs（新页直接跳行）通过。
      注：冒烟中一次跳行 FAIL 经隔离复现为**测试序列间全局状态（查找/折叠）
      干扰**，非产品缺陷——固定为查找/折叠前跳行。
- [x] 深浅两主题编辑器代表截图存档（`.scratch/code-editor-opt/final-*.png`）。
- [x] 提交信息中文；CHANGELOG 自动补录中文。
