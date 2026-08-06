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

**Status:** open

## Answer

（实现后填写）
