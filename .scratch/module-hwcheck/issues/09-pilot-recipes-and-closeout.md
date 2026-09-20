# 09 — 扩齐 pilot 配方 + 收尾留档

**要做什么：** 把 v1 专精清单补齐（led / oled / debug_uart / key / beep / sr04 / jy61p / xunji / adc / ml_mpu6050，按「模块 × 平台」格算），并给这件事留下不会烂掉的收尾：覆盖清单**地板守卫**、架构决策记录、领域词条、新手引导一段、真机证据落档。

**被谁阻塞：** 05（MPU6050 与探头）、06（控制台）、07（通用降级）、08（回填与排障）。

**状态：** resolved

- [x] pilot 清单内每一格（模块 × 平台）都有配方，且引用的函数名全部通过一致性守卫
- [x] **覆盖率地板守卫**：专精清单少于约定条数即红（照既有来源覆盖面地板先例），并配反证（故意删一条 → 红）
- [x] 单平台件（只有 mspm0 或只有 stm32 条目）在检测页选择时不产生"另一平台也能测"的误导
- [x] 架构决策记录落档：检测程序 = 确定性渲染 + 库内配方数据；并写清与「模块 = 纯驱动切片」的关系
- [x] 领域词表新增「硬件检测」词条（含判据单源指向：配方文件、顺序判据、冲突判据）
- [x] 新手引导（指南栏）增补一段：第一次拿到模块该去哪儿、按什么顺序验
- [x] 真机证据：两平台编译矩阵（stm32 UV4 / mspm0 gmake）+ 用户上板结果（跑过的写现象，没跑的写"未上板"，不假装）
- [x] 版本更新记录（定稿区）条目按既有格式补一段"新增：硬件检测"——**按用户裁决只留定稿草稿**（见下「VERSIONS.md 定稿草稿」：`VERSIONS.md` 只在真发版时写，首块必须等于 `__version__`，本轮不动版本号）

## 配方清单（17 格，全部通过引用校验）

| 格 | 命令 | 探头（板上判定） | 读数 | 备注 |
|---|---|---|---|---|
| led × stm32 / mspm0 | l | 无（纯输出） | 1 | 工单 04 既有 |
| oled × stm32 / mspm0 | d | 有（现象式：屏上出字） | 0 | 工单 04 既有；mspm0 这轮补了 `(unsigned char *)` 强转（见下） |
| debug_uart × stm32 / mspm0 | u | 有（现象式：发一行自报） | 1 / 0 | 本节复测 TX；RX 靠敲字符看回显 |
| key × stm32 / mspm0 | k | 无（输入件，要人按） | 2 | 只读首通道（多通道默认是别名） |
| beep × stm32 / mspm0 | p | 有（现象式：响两声） | 1 / 0 | `b` 是库内既有命令，故用 `p` |
| sr04 × mspm0（单平台） | s | 无（无身份寄存器；读数不做阈值判决） | 1 | note 讲清"读到 0 = 没等到回波" |
| jy61p × mspm0（单平台） | j | 有（整条读事务返回码 `0`） | 6 | 浮点角度拆整数 / 小数第一位两次回显 |
| xunji × mspm0（单平台） | x | 无（灰度位图没有恒等值） | 4 | **一个输出动作都不放**：`xunji_set_speed` 连命令台都不进（会动车）；⚠ **这一格当前到不了板**（生成前被默认脚冲突拦下，见下） |
| adc × stm32 / mspm0 | a | 无（读数取决于外部电压） | 2 | 直接写枚举常量（见下"判据面修的一处缺口"）；⚠ **mspm0 这一格当前到不了板**（同） |
| ml_mpu6050 × stm32 / mspm0 | m | 有（WHO_AM_I / DMP） | 6 | 工单 05 既有 |

**17 格里 2 格到不了板**（`adc × mspm0` / `xunji × mspm0`）：配方本身通过校验、也
写得对，但**生成前**就被母版默认脚冲突拦下——如实标在这里，不按"有配方 = 能测"宣传；
根因、候选修法与证据见另开单 `.scratch/hwcheck-pin-conflict-exit/`。

命令字符空间（10 件同选）：`u l a p k m d`（+ sr04 `s` / jy61p `j` / xunji `x`，
三者只有 mspm0 条目）——与库内既有 `r/y/g/o/b` 和帮助 `?` 都不撞（构建期判据）。

## 真机证据（2026-09-20，本机）

| 项 | 读数 |
|---|---|
| 编译矩阵（`.scratch/module-hwcheck/probe-09-compile-matrix.py`） | pilot 17 格 + 2 格全选（清单**单源**取自地板断言的 `PILOT`）：**16 种形态真编译，判红 0**，全部 0 error / 0 warning（stm32 走 UV4 `C:\Keil5\Core\UV4\UV4.exe`；mspm0 走 gmake `C:\ti\ccs2050\…\gmake.exe`）。逐格用的通道形态是「只串口 → 只 OLED → 都不开」里第一个能生成的那个，**每行末尾都记着**——它和检测页默认的"两个都开"不同（那个形态在 mspm0 上必 400，正是另开单那条） |
| 生成前拦下（3 格，不混进"编译通过"） | `mspm0 adc` / `mspm0 xunji`（只有"都不开"能生成，而那一形态按设计不渲染逐件小节 → 到不了板）、`mspm0 全选 9 件`（三种通道形态都 400） |
| 上板 | **未上板**：本单没有真板子跑过，按 spec「没跑过就写未上板，不假装」——已编译的那 16 格可烧可跑（0 error / 0 warning），但"板上现象"这一轮留给用户实机（步骤见指南栏「第一次拿到一件新模块」一节） |
| 判据强度探针（`.scratch/module-hwcheck/probe-09-guard-strength.py`） | **4/4 PASS**：配方少一格 / 地板清单被改小 / 枚举名不进白名单（停用的是母版头与模块头**共用的那个提取器入口**）/ 给单平台件补别的平台——四处停用都让点名用例变红，且源码逐字节复原 |
| 配方 ↔ 真库校验器（`.scratch/module-hwcheck/validate-recipes.py`） | **17 格全过**（随时可复跑；单平台件只校验有条目那一格） |
| 测试读数 | 相关面 pytest **1241 passed**（`test_hwcheck*` / `test_llm` / `test_webapp` / `test_library*` / `test_context_manifest` / `test_preflight` / `test_changelog` / `test_repo_language` / `test_errors`）；前端门禁 **1682 passed** |
| 本机端口 | 跑完实测 8000/8020/8021/8791 都没在听、无残留 python（全走进程内 TestClient + 子进程编译器） |

## 这一单修掉的两处真缺陷（都是矩阵逼出来的）

1. **判据面缺口：枚举常量与 typedef 名不在配方接口清单里**（`hwcheck_recipe.interface_names`）。
   后果不是"少个名字"而是**配方被逼绕道**：stm32 的 adc 读数只能写"整型变量 + 强转"，
   编译出 4 个 `#188-D: enumerated type mixed with another type`（验收线是 0 warning），
   而直接写 `adc_get(ADC_1, ADC_Channel_0)` 反而过不了校验。修法：白名单并入
   **enum 常量名 + typedef 类型名**（枚举体先剥注释再取名字），方向与既有的
   `_define_names` / `_extern_names` 一致（宁可多认，不可冤枉头文件里真写过的名字）；
   adc 两格随之改成自然写法，警告消失。守卫：
   `test_enum_constants_and_typedefs_are_real_interface_names`。
2. **既有配方的一处真 warning：mspm0 的 oled 探头没有强转**。
   `OLED_ShowString(u8 x, u8 y, u8 *chr, u8 size1)` 第三参是 `u8 *`，直接传
   `"OLED OK"` 被 tiarmclang 判 `passing 'char[8]' to parameter of type 'u8 *'`
   （2 条）——配方里改成 `(unsigned char *)"OLED OK"` 并在 note 里写明为什么。

## 另开的两张单（本单不修，按票面边界"库内缺陷另开单"）

`.scratch/hwcheck-pin-conflict-exit/issues/01-default-pin-conflict-no-exit.md`（ready-for-agent）：

* **检测页遇到默认脚冲突没有出口**：mspm0 上「调试串口 + OLED」是检测页默认形态，
  而母版里 `OLED_SPI_RES = PA22 = DEBUG_UART RX` —— mspm0 任何器件（含基线）在默认
  双通道下生成必 400，检测页却没有引脚配置入口。赛题链路同一条冲突有出口
  （`/api/bindings/auto` 会把它移到 PA24，实测）。
* **`ADC12_0.adcPin7` 角色未登记**：选 adc（及共读 MEM 的 us016/mq2 等）时只要开任一
  输出通道就 400；两个通道都关则能生成但逐件小节按设计不渲染——**adc:mspm0 这一格
  目前到不了板**（配方本身没问题，矩阵里如实记作"生成前拦下"）。同一张单还记着
  **xunji:mspm0**（HUIDU 的 P2/P3 与 DEBUG_UART / OLED 撞脚，也只有"都不开"能生成）。

## VERSIONS.md 定稿草稿（用户裁决：不动版本号，发版时照抄这一节）

```markdown
## v1.3.0 (YYYY-MM-DD)
- 主题：手上新到的器件，先验通路再写题——新增「硬件检测」栏目
- 新增：**「硬件检测」栏目**（顶部导航，完全独立于做题流程）：选平台 → 选器件 →
  看见接线表与「哪两件不能同时用默认脚」→ 一键生成检测工程 → 编译烧录 →
  照着「应看到什么 / 不对先查哪里」清单上板确认。**不需要赛题、不用先选模块**，
  一件器件都不选也能生成（那是先确认板子和烧录链路是活的）
- 新增：检测程序**不靠 AI 生成**——框架（LED 心跳、串口 / 屏分节、结尾汇总）由
  确定性渲染，每一件怎么测来自库内配方（led / oled / 调试串口 / 按键 / 蜂鸣器 /
  超声波 / 六轴姿态 / 灰度循迹 / ADC / MPU6050，双平台共 17 格，全部过真机编译
  矩阵 0 error / 0 warning）；没有配方的器件走通用降级（初始化 + 总线扫描）并如实标
  「未专精：只验总线和初始化」，不假装测过。⚠ **mspm0 上「ADC」「灰度循迹」两格
  暂时生成不出来**（母版默认引脚冲突，正在修；检测页会如实报错，不是你的接线问题）- 新增：上板跑完把**实际现象填回来，AI 给排查方向**（先说更像接线 / 器件 / 程序的问题，
  再给下一步查什么）；模型不可用也不阻断——仍给一份自查清单，现象与勾选照常存进
  检测工程目录，刷新还能看到
- 新增：板子上的**串口命令台**——敲一个字符就复测那一件，不用重烧（既有 r/y/g/o/b
  四条命令语义一字未变）
- 改进：检测工程与赛题工程**互不干扰**（不进「最近生成」记录、不会被修订 / 深化误抓）
```

## 落地文件

* 数据：`library/hwcheck_recipes.json`（10 件 / 17 格）
* 判据面：`src/contest_generator/hwcheck_recipe.py`（枚举常量 + typedef 名进白名单）
* 守卫：`tests/test_hwcheck_recipe.py`（地板 17 格 + 条数 + 单平台件 + 白名单扩展）、
  `tests/test_hwcheck.py`（三件单平台件在 stm32 上逐条点名）、`tests/js/hwcheck.test.mjs`
  （挑选面必须带当前平台）
* 文档：`docs/adr/0016-hwcheck-render-plus-recipes.md`、`CONTEXT.md`「硬件检测」词条、
  `fx/guide.js`「第一次拿到一件新模块：先去「硬件检测」验通路」
* 证据：`probe-09-compile-matrix.txt`（+ `probe-09-buildlogs/`）、
  `probe-09-guard-strength.txt`、`probe-09-contest-parity.py`、
  `validate-recipes.py`（配方 ↔ 真库校验器，随时可复跑）
