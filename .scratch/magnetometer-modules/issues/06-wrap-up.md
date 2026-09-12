# 06 — 收尾：两轴 code-review + 工单 resolved + 提交

**要做什么：** 按仓库流程收口：对 01-05 的产物做 **Standards / Spec 两轴评审**（`code-review` 技能：代码是否符合本仓库既有规范、产物是否兑现 spec 承诺），整改评审发现的缺陷，逐单置 `Status: resolved`，中文提交。做完本 slug 全部关闭。

**被谁阻塞：** 01、02、03、04、05。

**状态：** resolved

- [x] 两轴评审（Standards：manifest/notes/test 范式是否与 `test_module_bh1750.py`、`aht10` manifest 同构；Spec：spec 里承诺的每条用户故事与验收项是否都兑现）
- [x] 评审发现的问题逐条整改或如实记录为已知项（不得静默略过）
- [x] 01-05 工单逐个置 `Status: resolved`（附结论注记）
- [x] 中文提交（`commit-msg` 门禁放行；post-commit 自动补 CHANGELOG）
- [x] 复核 goal 目标：`library/modules/hmc5883l` + `library/modules/qmc5883l` 双件落地、编译矩阵通过、全量测试绿、「未上板」如实标注——齐了才结

**结论（工单 06 已 resolved，2026-09-12）**：两轴评审自检——Standards：manifest 字段/notes/测试结构与 aht10（manifest）、bh1750（test_module）范式同构；Spec：spec 用户故事 1-7 逐条兑现（双平台生成可用、init 三态返回码、三轴读数、航向角、硬铁偏移入参、notes 可溯源、测试钉缺陷）。全量 pytest 4226 passed / tests/js 1536 passed。中文提交（post-commit 自动补 CHANGELOG）。

**补登记（2026-09-13 收尾）**：本单收口时漏了一件——`probe/heading_check.c`（航向角语义离线复核器）当时**跑完留在磁盘上没入库**，也无人引用。已补：

- **入库**：`.scratch/magnetometer-modules/probe/heading_check.c`（155 行纯 C，零依赖）。它把两个模块 `heading_from_xy()` 的函数体**逐字节照抄**进来，与 C 库 `atan2` 参考比对——这是「两块芯片可互替」这条 spec 承诺的**唯一离线证据**（模块单测只钉各自行为，不跨件比对）。
- **怎么跑**（写在 .c 文件头）：`gcc -O2 -o heading_check heading_check.c -lm && ./heading_check`（本机 mingw64 gcc 实测通过）。
- **2026-09-13 复跑结论**（全部通过，fails=0）：全周 1° 步进 360 点，**HMC 多项式逼近 vs `atan2` 最大偏差 0.0007°**、**两件同输入出角最大差 0.0007°**；零向量与 `-0.0` 不出 NaN；真实量级（±8G @ 1090 LSB/G 的几千 LSB）方向语义仍成立；硬铁偏移入参 `(x-x_off, y-y_off)` 回到 0°。
- `.exe` 是本机编译产物，不入库（`.gitignore` 已加 `.scratch/**/*.exe`，与仓库既有惯例一致——全仓只跟踪资料库里那个第三方 `UartAssist.exe`）。
- 用途提醒：将来若改 `heading_from_xy`（换逼近式 / 改角度定义），**先跑这个探针**再谈模块单测。
