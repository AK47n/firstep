# 01 — 检测页遇到默认脚冲突没有出口（mspm0 默认双通道 = 生成必 400）

**要做什么（背景）：** 工单 `module-hwcheck/09` 把 pilot 配方补到 10 件 / 17 格、跑真编译矩阵时撞出来的两条既有缺陷。它们都不是配方的问题（配方本身 17 格全过、真编译 17 形态全 0 error / 0 warning），而是**检测页这条路走不通**：

## 缺陷 A（🔴 用户可见）：mspm0 上「默认形态」根本生成不出来

检测页打开时的通道默认是**「调试串口 + OLED」都勾上**。而 mspm0 母版里
`OLED_SPI_RES = PA22 = DEBUG_UART RX`（同一颗脚），于是：

| 形态 | 结果 |
|---|---|
| mspm0 + 默认双通道 + **任何**器件（也含"一件都不选"的基线） | **400**：`PA22：oled（OLED_SPI.associatedPins[4].pin，角色 oled.OLED_SPI_RES） × debug_uart（DEBUG_UART.peripheral.rxPin，角色 debug_uart.DEBUG_UART_RX）` |
| mspm0 + 只开串口（或都不开 / 只开 OLED）+ 多数器件 | 200，正常 |

**为什么这条特别坏**：检测页**没有引脚配置入口**，而 400 的出路文案是
"在引脚配置里改绑上述角色（或点「自动配置」一键解开）"——那是**赛题页**的东西。
学生按默认状态点「生成检测工程」，得到的是一句他没法执行的指引。

**赛题链路同一条冲突有出口**（实测）：
`POST /api/bindings/auto {platform: mspm0, slugs: [led, oled, debug_uart]}`
→ `ok:true`，`debug_uart.DEBUG_UART_RX → PA24`（原 PA22 与 `oled.OLED_SPI_RES` 冲突）。
证据：`.scratch/module-hwcheck/probe-09-contest-parity.py`。

**候选修法（按代价排序，任选其一，需拍板）**：
1. 检测页在生成前**调一次 `/api/bindings/auto`**（`resolve_default_conflicts=True`）
   把默认撞脚解开，并把"动了哪几根线"如实打在检测页/工程 README 里——
   与赛题页的「自动配置」同源判据，学生不必做任何事。
2. 检测页给一个**最小改绑入口**（只列本趟冲突角色 + 可选脚），复用
   `/api/bindings/matrix` 与 `/api/bindings/auto`。
3. 只改默认值：检测页默认**只勾串口**（OLED 由学生按需勾上）——最便宜，但
   mspm0 想用屏的人照样会撞上，且"默认只勾一个通道"与 spec 的
   "OLED 或串口把结果分段打出来"相比是产品让步。

> 相关的第二层（同源）：`POST /api/hwcheck/preview` 在这些形态上**一律 200**
> （预览不跑落盘后的 syscfg 引脚冲突门禁），所以页面上"预览通过 → 生成 400"。
> 修 A 时顺手确认预览要不要一起报（`generate-check-parity` 那条"预览/生成
> 判据同源"的既有讨论适用）。

## 缺陷 B（🟠 库内数据）：`ADC12_0.peripheral.adcPin7` 角色未登记

mspm0 选 `adc`（或 us016/mq2/photoresistance/ir_distance/flame 这些共读 MEM 的件）
时，只要开任何一个输出通道就 400：

```
· PA22：debug_uart（DEBUG_UART.peripheral.rxPin，角色 debug_uart.DEBUG_UART_RX）
      × ADC12_0.peripheral.adcPin7（角色未登记）
```

根因：母版 `mspm0.syscfg` 的 `ADC12_0` 把 8 个 MEM 脚全占了
（MEM6 = `adcPin7` = PA22 归 flame 的 `FLAME_AO_CH6`），而**该角色只有选中 flame
时才在工程里**——选 adc 而不选 flame 时，这颗脚"没有主人"，冲突求解器解不开。
两个都不开输出通道时能生成 200，但逐件小节按设计不渲染（"只验板子活着"那条路），
所以**这一格到不了板**。

**候选修法**：① 母版 syscfg 里把未用 MEM 脚的那几行**跟选中集一起裁剪**
（现在是"选中 ADC12_0 就整段保留"）；② 或给这些脚补上"通用 ADC 角色"登记，
让 `auto_assign_bindings` 有东西可移。修完回归
`.scratch/module-hwcheck/probe-09-compile-matrix.py`（那条 `adc` 格会从"生成前拦下"
变成"能生成 → 真编译"）。

**被谁阻塞：** 无——可立即开始（两条都在本仓库内可复现）。

**状态：** ready-for-agent

- [ ] mspm0 + **默认双通道**（调试串口 + OLED）+ 任意器件（含"一件都不选"）能生成检测工程，
      或页面在该形态下**给出一个学生做得到的出口**（不是"去引脚配置改绑"这句指向赛题页的话）
- [ ] `POST /api/hwcheck/preview` 与 `POST /api/hwcheck/generate` 在这些形态上**判据一致**
      （现在预览 200、生成 400——页面上"预览通过 → 生成失败"）
- [ ] `ADC12_0.adcPin7`（PA22）不再以"角色未登记"的身份挡住选 `adc` / `us016` / `mq2` /
      `photoresistance` / `ir_distance` / `flame` 的生成（哪怕只开一路输出通道）
- [ ] 回归 `.scratch/module-hwcheck/probe-09-compile-matrix.py`：`mspm0 adc` 与 `mspm0 xunji`
      两格从「生成前拦下」变成「能生成 → 真编译 0 error / 0 warning」，且"生成前拦下"一节清空
      （`mspm0 全选 9 件`那格若仍拦，要在检测页明说为什么、怎么说都行，别静默）
- [ ] 检测页引导/文案如实：改绑过引脚时，接线表与工程 README 里那条线要跟着变（学生照表接线）

## 证据

- 矩阵与结论：`.scratch/module-hwcheck/probe-09-compile-matrix.txt`
  （17 形态真编译 0 error / 0 warning；mspm0 每格都记了"默认双通道"那一列 400）
- 赛题侧出口对照：`.scratch/module-hwcheck/probe-09-contest-parity.py`
- 发现它的那张单：`.scratch/module-hwcheck/issues/09-pilot-recipes-and-closeout.md`
  （该单明确"库内缺陷另开单、不在本单修"）
