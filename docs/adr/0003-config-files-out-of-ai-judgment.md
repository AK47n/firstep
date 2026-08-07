# 工程配置文件移出 AI 判定：确定性现写（判例 09 治本）

Status: accepted

工程配置文件（Keil 的 .uvprojx / .uvoptx / .uvguix、CCS 的 .cproject / .project）**移出 AI 判定范围**，走确定性规则车道——AI 给出这些路径的判定是越界，系统拒绝。判例 09 的根因是 AI 把两工程各自的 .uvprojx 判了 merge、手写整合 XML：结构残缺（组清空、Cads/IncludePath 丢失）照样入库，ticket 08 的结构校验只是安全网、不治本（AI 手写 XML 配置仍有失败率）。

## 决策

- **stm32 的 .uvprojx 由确定性渲染器现写**（keil.render_master_uvprojx，固定落位 `user/Project.uvprojx`，正点原子风格）：设备块硬编码 C8T6（平台线即 STM32F103C8T6/Keil5）——`Device STM32F103C8`、`IRAM(0x20000000,0x5000) IROM(0x08000000,0x10000)`（C8T6 20KB RAM / 64KB Flash）、ARM-ADS 0x4、SchemaVersion 2.1；文件树按顶层目录分组（sys/ml_libs/user 风格）、引用**全部保留 .c/.s** + 模板 main.c 条目（指向工程根落位）；IncludePath = 所有保留 .h 所在目录（去重、排序、相对 .uvprojx 所在目录）；.uvoptx 相关无需处理（规则剔除）。渲染产物无悬空引用、无缺失节点，结构一致性由构造保证——旧的"落盘后引用重写"（rewrite_project_references）在母版路径退役。ticket 08 的结构校验保留为手工导入母版的安全网。
- **启动文件跨工程去重**：文件名匹配 `startup_stm32f10x_*.s` 的 .s 是"启动文件候选"，至多保留一份——优先 `_md`（与目标板 C8T6 中密度匹配），没有则按路径排序取第一份；落选候选规则剔除（原因"启动文件替代：同一器件只需一份启动文件"），不可改动作。真实案例：2026C+21F 各带一份 md 启动（key/ 与 sys/），旧母版两份都保留（Reset_Handler 重复定义风险）。非 startup 命名的 .s（自定义汇编）不受影响。
- **密度守卫**：保留启动文件必须为 `_md`，否则大声失败"导入工程与目标板 STM32F103C8T6 不符（启动文件为 X）"——非中密度器件的工程不能静默产出无法编译的母版。
- **.uvoptx / .uvguix 规则剔除**：IDE 用户选项（断点 / 调试配置 / 窗口布局），非编译关键，Keil 编译时自动重建；原因"IDE 用户选项：编译时自动重建"。.uvguix 文件名带用户名后缀（Project.uvguix.luoji，2026C/21F 成对出现），按包含匹配。
- **mspm0 同移出 AI 判定，但保留首份**（.cproject/.project 确定性保留首份原样，不现写不重写）：CCS 按目录编译、无文件引用问题，且母版库尚无 mspm0 已知良好格式种子。重点在 stm32，mspm0 是顺手统一。
- **报告语义**：.uvprojx 进 keep 桶带规则原因"工程配置文件：由确定性模板现写，保留文件全量入树"；配置文件条目**不可改动作**（与基础设施同款强制）；报告新增 .uvprojx 全文预览（uvprojx_preview，与 main_c_preview 同款：确定性产物、确认回传时按最终决策集重推导、客户端回传值不可信；mspm0 无现写为空串）。
- **模板 main.c 修正**：`templates/main_stm32.c` 的 include 一行 `"stm32f10x_conf.h"` → `"stm32f10x.h"`。已验证：SystemInit 声明在 system_stm32f10x.h:79，stm32f10x.h:479 已 include 它；源工程为寄存器操作风格（ml_gpio.c 用 RCC->APB2ENR/GPIOx->CRL，只依赖 stm32f10x.h 无条件部分），USE_STDPERIPH_DRIVER/conf.h 机制整个不需要——之前"母版提供 conf.h 模板 + Define USE_STDPERIPH_DRIVER"的方案已否决。

## 格式来源与对 grilling 决策的修正

渲染器的静态设备块从真实工程（2026C / 21F，判例 09 原案，用户机器上可编译）原样提取，保证"打开就能编译"直接成立。对照工单 09 的 grilling 决策，以下两点以真实格式为准修正（其余决策原样落地）：

- **StartupFile 留空**（决策 1 的"StartupFile 指向启动文件"修正）：两份真实母版的 `<StartupFile>` 均为空，启动文件经工程树注册（FileType 2）即可编译——按已知良好格式实现，不设置该元素。
- **CLOCK(12000000)**（决策 1 摘要写 72000000）：真实母版的 `Cpu` 行为准。

其余补充：.uvguix 与 .uvoptx 同族纳入规则剔除（决策 5 只列 .uvoptx，真实工程暴露）；密度守卫落在渲染器（build_master_uvprojx），蒸馏报告预览推导时即触发（入库前大声失败）；启动去重放在跨工程报告组装层（assemble_report），scan 只做候选分类。

## 被否掉的候选

- 保留 AI 判定 + 结构校验兜底（ticket 08 现状）：安全网不治本，AI 手写 XML 每次提炼都有失败率，失败点落在入库前也浪费一轮提炼。
- 让 AI "选一份"替代 merge（ticket 08 待定项）：仍是 AI 判定，且选中的源工程 .uvprojx 可能带悬空引用 / 陈旧 include path，仍需重写补救；确定性渲染一步到位。

## 已知风险

- 渲染产物是"最小可信设备块"的完整拷贝（~380 行静态 XML），后续换器件 / 换 IDE 版本需要更新模板常量；工具平台线即 C8T6/Keil5，短期无此需求。
- 密度守卫只认 `_md` 后缀命名；若用户工程用非官方命名（如 `startup.s` 不带密度），按"非启动候选"落入基础设施保留、绕过守卫——但 .s 不进 AI 判定，仍由规则保留，编译链不断。
