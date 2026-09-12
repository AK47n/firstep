# 04 — 编译矩阵：四组 0 error / 0 warning + verified 回写

**要做什么：** 用真工具链证明两件生成的工程**真能编译**（不是「看着像能编」）：两件 × 两平台 = 四组，每组「单选生成 → SysConfig CLI（mspm0）/ 静态门禁（stm32）→ gmake / UV4」，**0 error、0 module warning** 为硬门槛；通过后把 manifest 的 `verified` 由 false 回写 true。不过就不翻牌，如实留 false。

**被谁阻塞：** 01、02、03（03 会先跑全量 pytest 抓出遗漏，避免带着红测试去跑编译）。

**状态：** resolved

- [x] 编译矩阵脚本（照 `.scratch/wiki-modules-batch1/run_joystick_matrix.py` 改 slug）落在本 slug 目录下
- [x] `hmc5883l` × mspm0：SysConfig CLI 通过（新实例合法、引脚不冲突）→ gmake 0 error / 0 module warning
- [x] `hmc5883l` × stm32：UV4（`C:\Keil5\Core\UV4\UV4.exe`）0 error / 0 module warning
- [x] `qmc5883l` × mspm0：同上
- [x] `qmc5883l` × stm32：同上
- [x] 四组结果原始输出留档（本 slug 目录），`verified` 回写 true；任一失败则如实记录失败输出并保持 false
- [x] 全量 pytest 跑一遍（编译矩阵改了 manifest，确认无回归）

**结论（工单 04 已 resolved，2026-09-12）**：四组真编译全 PASS——hmc5883l × {mspm0, stm32}、qmc5883l × {mspm0, stm32}，均 0 error / 0 module warning；原始输出留档 `.scratch/magnetometer-modules/matrix/*.log`。**首轮 qmc5883l/mspm0 红** = 母版 `mspm0.syscfg` 里 QMC5883L 实例被重复声明（`SyntaxError: Identifier 'QMC5883L' has already been declared`，声明区与实例块各一行），去重后通过——已记入 manifest notes。verified 四条目全部回写 true，模块测试断言同步改口径。
