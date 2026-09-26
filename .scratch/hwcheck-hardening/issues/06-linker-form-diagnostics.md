# 06 — 链接器形态的诊断要看得见（"0 warning" 不再漏）

**要做什么：** 工程带链接器告警时，**编译面板如实显示它**，不再报"0 warning"——
学生与维护者看到的读数与真日志一致。

**被谁阻塞：** 无——可立即开始。

**状态：** ready-for-agent

- [ ] 解析器新增一类「**没有文件引用的工具链诊断**」：`#NNNN-D:` 形态，warning 与 error 都收
      （真例：`warning #10210-D: creating ".sysmem" section with default size of 0x800; …`）。
- [ ] 归类与落点照既有先例：归到**伪路径**（同 SysConfig 冲突那条路），行号 0 = **不可跳转**
      （复用既有"不可跳转行"的渲染，不新造一种）。
- [ ] 汇总如实：`errors / warnings` 计数含它（面板与修复中心读到的是同一份）。
- [ ] 用例（真日志原文进 / 结构化出）：喂那条 `.sysmem` 原文 → 出 1 条 warning；汇总 → `warnings = 1`；
      **既有 UV4 / CCS / gmake / SysConfig 四类形态的用例全绿**（不许为了收新形态把旧的判松）。
- [ ] 反证：把新形态的识别停用 → 新用例必须红（读数落 `.scratch/hwcheck-hardening/probe-06-red.txt`）。
- [ ] 账本如实记账：`ml_mpu6050 × mspm0` 那格的 `.sysmem` 告警**属工具链行为**，
      **不修驱动**（`inv_mpu.c` 的 `log_i/log_e` 不动）——本单只保证它被看见。
- [ ] 相关面全绿：`tests/test_fix_errors.py` + 编译判决相关用例。
