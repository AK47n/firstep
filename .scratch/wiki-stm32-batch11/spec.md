# 批次 11「stm32 线收官」— C 类核对 + st7789_para 1.14 寸（B 类待资料）

## 问题陈述

stm32 线进度：批次 1-10 全部完成（批 10 显示件组 7 件 + 批 4/05 vl53l0x 于批 10 收尾一并收官）。本批 = **stm32 线收官**：
- **C 类核对 4 件**（既有 stm32 条目与地阔星页面逐页对照——「核对不提炼」口径：servo（control--16-ch-servo-drive-module.md）/motor（control--tb6612-motor-drive-module.md，motor 源自 2021F 提取页面是对照）/ml_mpu6050（sensor--mpu6050-six-axis-sensor.md）/0-96-iic（screen--0-96-iic-single-screen.md，oled I2C 128×64 母版内嵌核对）；
- **B 类 st7789_para（1.14 寸 8 位并口 ST7789V）**：新 slug——**待用户提供 lcdwiki 同款下载链接**（参照 ili9341/ili9488 流程：页面 `screen--1-14-color-screen.md` 零驱动/零引脚表 → lcdwiki 包直提；接口 = 8 位并口（与 lcd 全系软 SPI 不同——驱动结构不同，dkx-map-summary 记录「独立：控制器 ST7789V 与 lcd 的 V2/V3 同族，但接口为 8 位并口」）；资料到位后按 B 类流程实施（与 ili 两件同构：码/manifest/引脚宏/测试/UV4 矩阵/wordlist 补录——并口 8 位数据线 + 控制线，默认脚待资料后拍板）。

## 方案

1. **C 类核对**：四件逐页对照（芯片/总线/地址/寄存器/时序/换算/默认脚/页面缺陷 vs 库内实现与 notes）——核对结论写入 `.scratch/wiki-stm32-batch11/核对报告.md`：一致即确认；**实质差异才改**（高置信 + 具体建议，改动最小化——优先 notes 补充；代码改动须重跑矩阵）。
2. **st7789_para**：用户资料到位后（lcdwiki 1.14 寸包——8 位并口版）开工——B 类新 slug 全流程（照 ili9341/ili9488 模式：序列/引脚表包内直提 + API 照 mspm0 lcd.h 风格 + 字库 lcdfont.h 同源副本 + 触摸范围外（1.14 无触摸））。**资料未到位 = 本件保持待资料，不阻塞核对结论**。

## 范围外

- st7789_para 实施（待用户 lcdwiki 链接——参照 ili9341/ili9488 同款下载）；
- 上板真机验证（核对四件 notes 口径沿用：真机验证留后续）；
- mspm0 条目改动（零改动——C 类仅核对）。

## 验收标准

- 核对报告四件齐全（结论 = 一致/差异+建议）；实质差异已按建议处置（或记录挂起原因）；
- 全量 pytest 绿；中文提交。
