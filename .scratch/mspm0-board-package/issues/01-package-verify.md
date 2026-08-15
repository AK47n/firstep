# 01 — 地猛星板载芯片封装核实（LQFP-48(PT) vs LQFP-64(PM)）+ HUIDU R3/R4 处理

**What to build:** 工单 mspm0-master-dimx/01 发现：原理图芯片 48 脚清单与 TI LQFP-48(PT) 封装逐脚吻合（PA0=1 脚、VDD=6、VCORE=25…），而母版 syscfg 声明 LQFP-64(PM)（LaunchPad 遗留）——PB4/PB5 仅 PM 模型存在，地猛星 2×20 排针未引出它们。HUIDU R3/R4=PB4/PB5 因此"默认板外"（pin-board-config 板外默认规则已兜底）。本工单核实包型号并定 HUIDU R3/R4 处理方案。

**Blocked by:** 无（不阻塞 pin-board-config——板外默认规则已兜底）

**Status:** claimed（等用户丝印/引脚数反馈）

## 需求

1. **核实包型号**：看板载芯片丝印（用户物理操作，记录丝印文字/照片）+ 对照原理图 PDF（`sources/materials/2026_04_地猛星电赛控制题配套资料/`）与 TI 数据手册封装章（`sources/materials/2026_08_MSPM0G3507与常用芯片手册/MSPM0G3507数据手册.pdf`）。
2. 若确认 LQFP-48(PT)：评估 syscfg 的 device/package 声明是否需改（SysConfig 里 package 选择影响可用引脚集与引脚复用表）——评估改动影响（生成宏 / 编译），改动方案与风险记 Comments（改动可另开实施工单）。
3. **HUIDU R3/R4 处理裁决**（与用户定，三选）：(a) 维持板外默认（8 路灰度只用 6 路排针，另 2 路焊线引出）；(b) 重分配（需腾 2 脚——排针 32 脚已全满，只能挤占 STEP_MOTOR/I2C_0/IMU601 等新增实例，按实际用模块取舍）；(c) 其他。裁决记 Comments。

## 文件边界

- 核实阶段零代码改动；方案 (b) 若定才动 `library/masters/mspm0/mspm0.syscfg` + 相关模块注释 + pin-board-config/01 的默认值清单

## 验收

- [ ] 包型号核实结论进 Comments（丝印记录或照片）
- [ ] HUIDU R3/R4 处理裁决记录 + 相应改动（若需）

## Comments

- 2026-08-14 立项（mspm0-master-dimx/01 Comments"建议另立工单核实包型号并处理 HUIDU R3/R4"）。
