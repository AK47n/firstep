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

**状态：** resolved

- [x] mspm0 + **默认双通道**（调试串口 + OLED）+ 任意器件（含"一件都不选"）能生成检测工程，
      或页面在该形态下**给出一个学生做得到的出口**（不是"去引脚配置改绑"这句指向赛题页的话）
- [x] `POST /api/hwcheck/preview` 与 `POST /api/hwcheck/generate` 在这些形态上**判据一致**
      （现在预览 200、生成 400——页面上"预览通过 → 生成失败"）
- [x] `ADC12_0.adcPin7`（PA22）不再以"角色未登记"的身份挡住选 `adc` / `us016` / `mq2` /
      `photoresistance` / `ir_distance` / `flame` 的生成（哪怕只开一路输出通道）
- [x] 回归 `.scratch/module-hwcheck/probe-09-compile-matrix.py`：`mspm0 adc` 与 `mspm0 xunji`
      两格从「生成前拦下」变成「能生成 → 真编译 0 error / 0 warning」，且"生成前拦下"一节清空
      （`mspm0 全选 9 件`那格若仍拦，要在检测页明说为什么、怎么说都行，别静默）
- [x] 检测页引导/文案如实：改绑过引脚时，接线表与工程 README 里那条线要跟着变（学生照表接线）

## 结论（2026-09-20，工单 hwcheck-pin-conflict-exit/01）

**怎么修的**（spec 与拍板理由在 `.scratch/hwcheck-pin-conflict-exit/spec.md`）：

1. **检测页自动解冲突**（缺陷 A）：预览与生成前跑**与赛题页「自动配置」同一个**求解器
   （`auto_assign_bindings(resolve_default_conflicts=True)`，仅 mspm0），动过的线如实进载荷
   `wiring.pin_fixes`（接线表按**消解后**的脚渲染 → 与工程 README / 接线快照同源）。
   装不下时抛 `HwCheckError`，出路换成检测页做得到的三种（少选一件 / 只勾一个通道 /
   去赛题页改绑——第三条不是唯一一条），带哨兵 `HWCHECK_PIN_EXIT_MARKER` 供探针分流。
2. **孤儿 ADC 槽位让位**（缺陷 B）：母版 ADC12_0 一实例服务 20 件，实例粒度裁剪会把
   **没选中**那几件的 MEM 脚也落盘（`adcPin7` = flame 的 PA22），冲突求解器看不见它们
   （角色「未登记」）。新增槽位级裁剪判据 `AdcSlotPlan`（claims = 本趟声明的 MEM 槽位，
   occupied = 本趟已声明角色的生效脚，单源 `pin_bindings._role_entries`）：**撞上就让位**
   （改成与已声明槽位共读同一通道 + 撤掉落点行），没撞上一根不动（`adc` 配方第二路仍真读
   PA26）。门禁与写侧吃同一份判据。
   ⚠ **只删 `adcPinN.$assign` 行不够**——真机 SysConfig CLI 实证：它会按 `adcMem<N>chansel`
   把脚认回来、照样 Resource conflict（`.scratch/hwcheck-pin-conflict-exit/recon-syscfg-lab.txt`）。
3. **判据单源**：落盘 syscfg 的同脚冲突报告从生成门禁抽成 `syscfg_prune.syscfg_pin_conflict_report`，
   门禁（赛题页出路）与检测页（检测页出路）共用；「共读同槽」补进 `_role_resource_keys`
   （不再被自动配置当成冲突搬走——实测不补就会 `us016 → PB24`，等于悄悄换掉模拟输入脚）。

**读数**（本机实测，命令见下）：

| 面 | 读数 |
|---|---|
| 真编译矩阵 | **18 种形态 0 error / 0 warning**；「生成前拦下」**（无）**；「如实拦下」1 格 = `mspm0 全选 9 件`（物理装不下，页面点名冲突件与出路）；预览 / 生成**逐格同码** |
| mspm0 默认双通道 | 11 格里 10 格能生成；剩 1 格就是上面的全选 9 件 |
| 检测页验收 | `.scratch/hwcheck-pin-conflict-exit/verify-01-page-exit.txt`（10 条判据全 PASS） |
| 判据强度反向验证 | `.scratch/hwcheck-pin-conflict-exit/probe-guard-strength.txt`（3 处判据停掉即坏现象重现） |
| 测试 | `python -m pytest -n auto`：**4987 passed + 1 skipped**；前端门禁 `node --test "tests/js/*.test.mjs"`：**1683 passed** |

**顺手修掉的一处既有隐患**（本单把那条路打通后才暴露）：mspm0 选 `oled` 当**器件**、只勾串口时，
`oled.h` 没人 include → tiarmclang 4 条 `call to undeclared function`（旧矩阵该格靠"只勾 OLED"
蒙混过关）。已给 oled 配方补 `include` 段（mspm0 `oled.h` / stm32 `ml_oled.h`），并加结构守卫
`test_real_library_channel_module_recipes_declare_their_headers`。

**有意保留的一处差异**（评审提出、已写进 spec 范围外）：器件在**本平台没有条目**时预览 200
（`wiring.missing` 点名，工单 03 的契约）而生成 400——两边判的是同一件事，判据一致性由
`test_missing_platform_device_is_judged_by_both_endpoints` 钉住。

**复跑命令**：
`python .scratch\module-hwcheck\probe-09-compile-matrix.py`（约 4 分钟，真 Keil / gmake）、
`python .scratch\hwcheck-pin-conflict-exit\verify-01-page-exit.py`、
`python .scratch\hwcheck-pin-conflict-exit\probe-guard-strength.py`、
`python -m pytest -n auto`、`node --test "tests/js/*.test.mjs"`。

## 证据

- 矩阵与结论：`.scratch/module-hwcheck/probe-09-compile-matrix.txt`
  （本轮：18 形态真编译 0 error / 0 warning；生成前拦下 0；如实拦下 1）
- 检测页验收读数：`.scratch/hwcheck-pin-conflict-exit/verify-01-page-exit.txt`
- 判据强度反向验证：`.scratch/hwcheck-pin-conflict-exit/probe-guard-strength.txt`
- SysConfig CLI 实验（"只删落点行不够"的决定性证据）：
  `.scratch/hwcheck-pin-conflict-exit/recon-syscfg-lab.txt`
  （脚本 `syscfg-lab.py`；实验目录跑完即删，脚本可复跑）
- 赛题侧出口对照：`.scratch/module-hwcheck/probe-09-contest-parity.py`
- 发现它的那张单：`.scratch/module-hwcheck/issues/09-pilot-recipes-and-closeout.md`
  （该单明确"库内缺陷另开单、不在本单修"）
