# 09 — uvprojx 确定性现写：工程配置文件移出 AI 判定（判例 09 治本）

**What to build:** 把工程配置文件移出 AI 手写 XML 的判定范围，走确定性车道。判例 09 的根因：AI 把两工程各自的 .uvprojx 判 merge、手写整合 XML——结构残缺（组清空、Cads/IncludePath 丢失）照样入库，结构校验（ticket 08）只是安全网不治本。本工单：Keil 的 .uvprojx 由确定性渲染器现写（渲染器从保留清单直接生成，结构一致性由构造保证）；启动文件按器件密度去重；报告语义与确认环节同步收紧（配置文件条目规则化、不可改动作）；报告新增 .uvprojx 全文预览（与 main_c_preview 同款）。

工单由 grilling 会话产出（2026-08-06），决策树每项均经用户确认，落点如下。

## 决策（已确认）

1. **.uvprojx 现写渲染**（keil.py 新增 `render_master_uvprojx`）：确定性生成完整 .uvprojx——设备块硬编码 C8T6（参考真实母版已知良好格式：`Device STM32F103C8`、`IRAM(0-0x4FFF) IROM(0-0x7FFF) CLOCK(72000000)`、ARMCC 0x4、SchemaVersion 2.1）；文件树按顶层目录分组（sys/ml_libs/user 风格），引用**全部保留 .c/.s**；`StartupFile` 指向启动文件；`.uvoptx` 相关无需处理（剔除）。现写后 `rewrite_project_references` 在母版路径退役（渲染产物无悬空引用、main.c 条目直接指向模板落位）。
2. **启动文件去重**：文件名匹配 `startup_stm32f10x_*.s` 模式的 .s 为"启动文件候选"，至多保留一份——优先 `startup_stm32f10x_md.s`（与目标板 C8T6 中密度匹配），没有则按路径排序取第一份；落选候选规则剔除，进报告 exclude 带原因"启动文件替代：同一器件只需一份启动文件"；非 startup 命名的 .s（自定义汇编）不受影响。真实案例：2026C+21F 各带一份 md 启动（key/ 与 sys/），旧母版两份都保留（Reset_Handler 重复定义风险）。
3. **IncludePath**：= 所有保留 .h 文件所在目录，去重、排序、相对 .uvprojx 所在目录（真实保留集 ≈ `sys;ml_libs`）。模块 include path 由生成时 KeilPatcher `_append_include_dirs` 追加，母版不预埋。节点必须存在（结构校验强制）。
4. **设备配置 + 密度守卫**：模板硬编码 C8T6 配置（平台线即 STM32F103C8T6/Keil5，UI 亦然）；入库前检查保留启动文件必须为 `_md`（与目标板密度一致），否则大声失败"导入工程与目标板 STM32F103C8T6 不符（启动文件为 X）"。
5. **.uvoptx 规则剔除**：IDE 用户选项（窗口布局/断点），非编译关键；Keil **编译时自动重建**（用户确认的行为，不是打开时）。报告 exclude 带原因"IDE 用户选项：编译时自动重建"。
6. **mspm0 同移出 AI 判定，但保留首份**（.cproject/.project，确定性保留首份原样，不现写不重写）：CCS 按目录编译、无文件引用问题，无已知良好格式种子（母版库尚无 mspm0）。重点在 stm32，mspm0 是顺手统一。
7. **报告语义**：.uvprojx 进 keep 桶，规则原因"工程配置文件：由确定性模板现写，保留文件全量入树"；落选启动文件与 .uvoptx 进 exclude 桶带规则原因；配置文件条目**不可改动作**（与基础设施 `_validate_infrastructure_disposition` 同款强制）；报告新增 **uvprojx 全文预览**（与 main_c_preview 同款：确定性产物、确认回传时按平台重推导、客户端回传值不可信）。
8. **模板 main.c 修正**：`templates/main_stm32.c` 的 include 一行 `"stm32f10x_conf.h"` → `"stm32f10x.h"`。已验证：SystemInit 声明在 system_stm32f10x.h:79，stm32f10x.h:479 已 include 它。源工程为寄存器操作风格（ml_gpio.c 用 RCC->APB2ENR/GPIOx->CRL，只依赖 stm32f10x.h 无条件部分），USE_STDPERIPH_DRIVER/conf.h 机制整个不需要——之前"母版提供 conf.h 模板 + Define USE_STDPERIPH_DRIVER"的方案已否决。
9. **验收**：用真实工程 `~/Desktop/2026C` + `~/Desktop/2021F/21F`（判例 09 原案，元数据 sources 同名）重新提炼：入库通过 + 结构校验 + 渲染产物人工检查，替换 `~/.contest_generator/masters/stm32` 的坏母版（组空、0 IncludePath）；用户 Keil 实际编译一次为最终证明。

## 实现落点

- **keil.py**：`render_master_uvprojx(project_dir, kept_paths, startup_path, include_dirs)` 渲染器（复用 FileType 码 / `_keil_rel_path_from` 路径惯例 / XML 序列化底座）；启动文件密度辅助（`_md` 判定）。
- **master.py**：
  - `scan_project`：新增分类——`.uvprojx` → 工程配置文件（确定性现写，不进扫描清单/判定素材，但进报告 keep 带规则原因）；`.uvoptx` → IDE 用户选项（规则剔除）；启动文件候选去重逻辑（.s 中匹配 startup 模式的）。
  - `assemble_report` / `_validate_*_disposition`：配置文件强制 keep、.uvoptx/落选启动强制 exclude（用户确认也不可改）；uvprojx_preview 由渲染器推导。
  - `apply_distillation`：.uvprojx 由渲染器写入（固定落位 `user/Project.uvprojx`，正点原子风格，与现母版一致），不再从源工程复制；密度守卫落在此处或渲染器。
  - mspm0：`.cproject`/`.project` 按"确定性保留首份"分类，不进判定素材。
- **llm.py**：`JUDGMENT_SCOPE` 声明"工程配置文件（.uvprojx/.uvoptx/.cproject/.project）由确定性规则处理，不参与判定"（单源常量，双端契约测试同前）；AI 给配置文件路径的判定 = 越界拒绝。
- **report.py**：`DistillationReport` 加 `uvprojx_preview` 字段（必填，与 main_c_preview 同款——确认回传时按平台重推导）。
- **webapp.py**：报告往返带 uvprojx_preview（回传重推导）。
- **templates/main_stm32.c**：include 一行。
- **测试**：渲染器单测（树覆盖全部保留 .c/.s、分组、IncludePath、main.c 条目指向根）；启动文件去重（md 优先/无 md 取首份/落选剔除）；密度守卫（hd 启动拒绝）；报告语义（配置文件强制 keep、不可改）；真实工程验收（2026C+21F 提炼 → 入库 → 结构校验通过）。
- **ADR**：实现时写 ADR（0003 或修订 0001：工程配置文件移出 AI 判定、确定性现写）。

**Blocked by:** 无（ticket 08 的结构校验保留，作为安全网）

**Status:** resolved

## Answer

- [x] **keil.py 渲染器**：`build_master_uvprojx`（纯字符串确定性拼接）+ `render_master_uvprojx`（固定落位 `user/Project.uvprojx`）。设备块从真实母版 2026C/21F 原样提取（已验证与源文件逐字节一致）：C8T6 硬编码（Device STM32F103C8 / IRAM(0x20000000,0x5000) IROM(0x08000000,0x10000) / ARM-ADS 0x4 / SchemaVersion 2.1）；文件树按顶层目录分组（code/ml_libs/sys/user 风格）、引用全部保留 .c/.s + 模板 main.c 条目（`..\main.c`）；IncludePath = 保留 .h 目录（去重排序、相对 user/）；启动文件密度辅助（`is_startup_candidate` / `is_md_startup`）与密度守卫（非 _md 大声失败"导入工程与目标板 STM32F103C8T6 不符"）在渲染器。`rewrite_project_references` 在母版路径退役（删除函数与测试）。
- [x] **master.py 扫描分类**：`.uvprojx` → 工程配置文件（不进扫描清单/判定素材，报告 keep 带规则原因"工程配置文件：由确定性模板现写，保留文件全量入树"）；`.uvoptx`/`.uvguix` → IDE 用户选项规则剔除（`.uvguix` 文件名带用户名后缀，按包含匹配——真实工程 2026C/21F 成对出现，决策 5 补全）；`startup_stm32f10x_*.s` → 启动文件候选单独记录。
- [x] **启动文件跨工程去重**（assemble_report，scan 只分类）：优先 `_md`、无则路径排序取第一份；落选候选 exclude 带原因"启动文件替代：同一器件只需一份启动文件"；保留份/落选份均不可改动作（`_validate_startup_disposition`）。真实案例验证：2026C key/ + 21F sys/ 两份 md 只保留 key/ 一份。
- [x] **报告语义**：配置文件强制 keep 不可改（`_validate_config_disposition`，与基础设施同款）；`DistillationReport` 加 `uvprojx_preview` 必填字段（stm32 渲染全文 / mspm0 空串），确认回传时按最终决策集重推导（客户端值不可信，tamper 测试覆盖）；`JUDGMENT_SCOPE` 声明"工程配置文件由确定性规则处理，不参与判定"（AI 给配置路径判定 = 越界拒绝）；webapp 往返经 to_dict/from_dict 自动带上（webapp.py 无需改动）。
- [x] **落盘**：apply_distillation 跳过配置文件复制、stm32 渲染现写（密度守卫落盘前大声失败——蒸馏预览推导时即触发）；mspm0 .cproject/.project 保留首份原样复制；KeilPatcher 生成时模块条目与 include path 改按 .uvprojx 所在目录相对（user/ 落位下 `.\..\modules\...` 回算——根级相对会解析到 user/modules/ 编译缺文件）；结构与校验均对齐真实格式（IncludePath 在 `Cads/VariousControls` 下，2026C/21F 同款；FAKE_UVPROJX/FAKE_DISTILL_UVPROJX 同步更新）。
- [x] **模板 main.c**：include `"stm32f10x_conf.h"` → `"stm32f10x.h"`（已对照真实头文件验证：stm32f10x.h:479 include system_stm32f10x.h、SystemInit 声明在 :79）。
- [x] **测试**：渲染器单测 9 个（树覆盖/分组/IncludePath/设备块/确定性/密度守卫/落位/结构校验/候选辅助）+ 生成打补丁相对路径锁定 + 报告语义（强制 keep、不可改、预览往返重推导）+ 启动去重 3 场景 + 真实工程验收 `test_real_projects_2026c_21f_distill_and_import`（2026C+21F 全流程跑通：去重/剔除/渲染/入库结构校验，机器上 PASS 非 skip）。全套 418 绿 + mypy 干净。
- [x] **ADR 0003**（工程配置文件移出 AI 判定、确定性现写），CONTEXT.md 词表补充。
- [x] **验收剩余步骤（真实环境，2026-08-06 执行）**：`~/.contest_generator/masters/stm32` 坏母版已替换——新提炼母版（2026C+21F 重提炼）入库成功，结构校验 PASS（12 个 .c/.s 全入树、IncludePath=`..\ml_libs;..\sys`、启动文件去重唯一 md）；剩余：用户 Keil 实际编译一次为最终证明（含生成流程：新母版 + 选模块生成 → 编译）。
- [x] 8000 端口服务已重启加载新代码（工单 09 合入 main 后重启，418 测试绿）。

## 真实验收记录（2026-08-06）

- 工单 09 分支（b59cf75）fast-forward 合入 main（main 无独有提交，零冲突）
- 重启 8000 服务加载新代码，全套 418 测试绿
- 真实提炼（2026C + 2021F/21F，DeepSeek，约 17 分钟）：uvprojx 已移出 AI 判定——
  报告 keep 带规则原因"工程配置文件：由确定性模板现写，保留文件全量入树"、
  uvprojx_preview 16419 字符（含 Cads/IncludePath + 启动文件）；.uvoptx/.uvguix
  规则剔除；启动文件去重（key/ md 保留，sys/ hd+md 落选）
- 确认入库 200：`~/.contest_generator/masters/stm32` 坏母版（组空、0 IncludePath）
  被新母版整体替换；结构校验 PASS
- 遗留（人工）：用户 Keil 实际编译一次为最终证明

## 复验记录（2026-08-07）

- 发现 `~/.contest_generator/masters/stm32` 源文件（12 个 .c/.s）全部丢失、
  仅剩 user/ 下 3 个 XML（uvprojx 引用不存在的文件）——入库后丢失，成因
  未明（日志被重启覆盖）。**母版目录不是生成流程的写入目标**（generate 只
  读），排除代码侧写入；疑为人工清理或未知外部操作。
- 用户浏览器重新跑提炼 + 入库：母版 33 文件全量恢复（12 个 .c/.s + 头文件
  + user/Project.uvprojx），结构校验 PASS，sources=[2026C, 21F]，无残留。
- 遗留不变：用户 Keil 实际编译一次为最终证明。

## 真机编译复验（2026-08-08）

- 用户 Keil（ARMCC V5.06 build 960）首次真机编译生成工程（`~/.contest_generator/masters/stm32` 母版
  生成的 out_2026C/out_2021F），报 2 错：`ml_uart.c(21/30): #20: identifier "FILE" is undefined`
  （`FILE __stdout;` 与 `int fputc(int ch, FILE *f)`）。其余 10 个 .c/.s 全过、0 警告。
- 根因：ml_uart.c 的 ARMCC 重定向块（`struct __FILE` + `FILE __stdout;` + `__use_no_semihosting`
  + `_sys_exit`，与 `useUlib=0` 标准库模式匹配）依赖 stdio.h 的 `FILE` typedef，但全工程
  （ml_uart.c + headfile.h）从未 include `<stdio.h>`。补一行即愈，与重定向模式无冲突：
  stdio.h 只给 typedef，`struct __FILE` 由重定向块自供（ARM 官方 retarget 同款）。
- 修复：母版 `masters/stm32/ml_libs/ml_uart.c` 第 2 行补 `#include <stdio.h>`（二进制插入，
  GBK 注释字节未动）；同步补进 real-run 两个生成产物 out_2021F/out_2026C，用户可即刻复编。
- 遗留：用户重新编译一次确认 0 错 0 警为最终证明。
