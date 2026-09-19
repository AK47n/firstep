# 05 — MPU6050 专精 + 通信探头 + 平台差异如实呈现

**要做什么：** 让"新到一块 MPU6050，我想知道它通不通"这件事真正闭环：板上给出**通信 OK / FAIL 的自证判定**，mspm0 上直接显示 pitch / roll / yaw 三维角度，stm32 上显示原始六轴并**明写本平台没有姿态解算**（避免用户把"显示不了角度"误判成"我接错了"）。

**被谁阻塞：** 04（配方机制）。

**状态：** resolved

- [x] 通信探头**自证**，不信驱动的初始化返回值（既有 stm32 驱动不做通信校验、失败也照样往下写寄存器）：stm32 走寄存器读身份寄存器比对期望值；mspm0 用官方 DMP 初始化返回 + 探头组合
      （`library/hwcheck_recipes.json`：stm32 = `probe.calls ["MPU6050_Read(WHO_AM_I)"]` + `expect "0x68"`；
      mspm0 = `init_expect "0"`（官方 DMP 内部会读设备 ID）+ 探头 `DMP_Read_Data(&pitch,&roll,&yaw)`
      `expect "0"`（真从 FIFO 读回一帧）。**行为证据**：`probe-05-verdict-behaviour.py` 把渲染出的
      那一节用 gcc 真编真跑——探头桩返回 0x68 打 OK、返回 0x69 打 FAIL，见下）
- [x] 探头判 FAIL 时输出明确中文（"通信失败：先查供电 / 上拉 / 地址 / 线序"），不继续打一堆无意义读数
      （`render_recipe_section` 的 FAIL 分支：`hwcheck_detail(排查话术)` + `hwcheck_verdict(0,…)` + **`return;`**；
      行为证据同上：0x69 那一跑只有 FAIL 与排查行，**六轴读数一行都没有**）
- [x] 前置调用入配方：stm32 侧必须先初始化软 I2C 总线（既有驱动不初始化总线），检测程序生成时必须带上
      （`prereq.calls ["I2C_Init()"]`；工单 05 起 `prereq` **纳入引用校验**，判据面 = 该平台库内任何模块 ∪ 母版
      ——详情见「评审整改」⑥）
- [x] mspm0：`DMP_Init` + 读角度，OLED 显示**自拆整数 / 小数**（该平台无浮点显示接口）
      （新增小节级 `locals` 段声明 `float pitch/roll/yaw`，探头把角度搬进去；`read` 里每角两条整数表达式
      `(int)pitch` 与 `(int)((pitch - (int)pitch) * 10)`。行为证据：桩给 pitch=12.34/roll=-5.67/yaw=0.5
      → 真跑打印 `12` 与 `3`、`-5` 与 `-6`、`0` 与 `5`）
- [x] stm32：显示原始六轴 + 页面与产出的注释里都写明"本平台无姿态解算，要角度请用串口姿态模块或改 mspm0"；**不得假装有角度**
      （`read` = `ax/ay/az/gx/gy/gz`（驱动的 extern 全局量，工单 05 起并入接口清单），stm32 的 note 第一条就是这句话；
      note 直接印到检测页、也作为注释进产物；`test_...stm32...only` 反向钉住"不许出现角度"）
- [x] 互斥提示：姿态类件同属一个互斥组（只能选一件），检测页选择时与既有互斥规则一致
      （**用户拍板「单选交换 + 提示」**：载荷带按平台过滤的库级组（判据单源 = `collect_exclusive_groups`，
      与赛题侧同一函数），点同组第二件自动换掉旧的，并在器件区写明「这一组只能选一件 / 再点 X 会自动换掉 Y」）
- [x] 单测：双平台渲染文本各断言一次（含平台差异文案存在性）；**红证** = 把探头期望值改错 → 判定翻 FAIL
      （`test_mpu6050_stm32_renders…` / `test_mpu6050_mspm0_renders…` 各一次；
      **红证两条**：① 判据强度探针 A 条把配方里的 `expect` 改成 `0x69` → 对应用例红；
      ② `probe-05-verdict-behaviour.py` 把**探头桩的返回值**改成 0x69 → 真跑输出翻 FAIL 且不再打读数）

## 边界与决策引用

- stm32 侧 DMP 移植**不在本期**（spec 范围外）。
- 已知库内缺陷（本单不修，撞上就另开单）：该件 stm32 条目漏声明延时依赖；stm32 驱动不做身份校验。

## 实施结果

> 会话时间：2026-09-19 23:xx（本机时钟；工单 04 同日晚 21:5x）。

配方数据（`library/hwcheck_recipes.json`）+ 渲染机制（`hwcheck_recipe.py` / `hwcheck.py`）+ 载荷（`webapp.py`）
+ 前端（`fx/hwcheck.js` / `ui/hwcheck.js` / `index.html`）。本单顺带修掉**四条**上一单留下的真缺陷，见下。

### 途中发现并修掉的四个真缺陷（都不是本单"顺手重构"，是不修就交不了差）

| # | 现象（量具） | 根因 | 处置 |
|---|---|---|---|
| ① | stm32 编译 **7 error**：`#20 identifier "ax"/"WHO_AM_I" is undefined` + 一串 `#223-D function declared implicitly`（`probe-05-compile-matrix.py`） | 框架的 include 只覆盖通道与心跳，**器件模块的头没人 include**——检测程序直接调模块函数，于是全是隐式声明 | 新增配方 `include` 段（器件头 + 跨模块前置头如 `ml_i2c.h`），渲染进 main.c；头名进引用校验 |
| ② | ARMCC 报 `#27-D: character value is out of range`（同一次编译） | `\xNN` 转义**贪婪吃十六进制数字**：`"±2g"` 的字节 `C2 B1 32 67` 写成 `\xc2\xb12g` 被读成 `\xb12`（越界）——凡"非 ASCII 字节后紧跟 0-9a-f"的文案全中招 | 转义改**三位八进制**（最多三位、天然自终止，字节不变）；留逐字节还原守卫 |
| ③ | 换 mspm0 预览就 400：说 stm32 的 `ax` 找不到 | 配方全平台一份，而校验**只拿当前平台的清单**去查**所有平台**的段——平台不对称一出现就误报 | `interfaces` 改按平台分开（`{平台: {slug: 名字}}`），每段按自己的平台判；装配点两个平台都装 |
| ④ | 大写函数名拼错**不会被拦**（`DMP_Initt` 一路过校验） | `_calls_in` 只收小写/下划线开头的标识符（当年假设"全大写多半是宏"），而官方库的函数**恰恰全是大写** | 判据改成"形式"而非"大小写"：标识符紧跟 `(` 即算调用（跳过 C 关键字）；`sizeof` 之类仍是语言构造 |

### 顺带做掉的两件事（都有真机/结构性理由，不是加需求）

- **mspm0 的 SysTick 垫片**：库内 DMP 端口（`mpu_port.c` 的 `DMP_Init`）自己打开 `SysTick_CTRL_TICKINT_Msk`
  并 `__enable_irq()`，而 mspm0 母版**没有** SysTick 服务函数、TI 启动文件把 `SysTick_Handler` 弱别名到
  `Default_Handler`（`while (1) {}`，源码已读）——缺它就卡在 `DMP_Init()` 里（灯都不闪）。检测程序（它就是"应用"）
  补一个空的 `SysTick_Handler`；与 `_PLATFORM_BOOT_LINES` 同级：平台事实。
- **按需渲染补齐第 3 条**：整趟都是带判定的探头时（只选 ml_mpu6050），`hwcheck_verdict_probe_none` 与"未判定"档
  声明了没人调 → tiarmclang `-Wunused-function`（实测 1 warning）。验收线是 0 error / 0 warning，故按需渲染。

## 实施结果与证据（都在 `.scratch/module-hwcheck/`）

| 证据文件 | 内容 | 结论 |
|---|---|---|
| `probe-05-compile-matrix.py` / `.txt` + `probe-05-buildlogs/` | **两个平台各三形态真编译**（stm32 UV4 / mspm0 gmake + SysConfig CLI）：框架 → ml_mpu6050 专精 → ml_mpu6050 + 另一个输出通道 | **6/6 全绿（0 error / 0 warning）**，退出码 0；stm32 三形态 3–5 秒/次，mspm0 含 SysConfig 生成约 9 秒/次 |
| `probe-05-verdict-behaviour.py` / `.txt` | **把渲染器真产出的那一节**用 gcc（`C:/mingw64/bin/gcc.exe`）编起来跑，探头桩返回值可控 | **4/4 符合预期**：0x68 → OK + 六轴读数；**0x69 → FAIL + 中文排查行，且一行读数都没有**（`return;` 真生效）；mspm0 角度拆出 `12/3`、`-5/-6`、`0/5` |
| `negative-verify-05.py` / `.txt` | 判据强度探针：**11 条注入**（含票面点名的"改错探头期望值"）逐条停用守卫 | **11/11 注入后对应用例变红**，文件逐字节复原（前置干净性检查通过） |
| `probe-05-interfaces.py` | 量具：`ml_mpu6050` 在两个平台的接口清单（配方判据面） | stm32：`MPU6050_*` / `WHO_AM_I` / `ax…gz` / `I2C_Init`；mspm0：`DMP_Init` / `DMP_Read_Data` / `MPU_Read_Len` |
| `probe-05-coverage.py` / `-groups.py` | 量具：哪些件已专精（逐平台） / 各互斥组的平台成员 | 专精 = led / oled / ml_mpu6050 × 两平台；`attitude-hold` 在 mspm0 三件、**stm32 只剩 ml_mpu6050（单成员组不出卡）** |
| `probe-05-render.py` | 量具：真库配方 → 两个平台的渲染产物（转义还原后给人读） | 两平台小节逐行可读，平台差异一目了然 |
| `verify-05-suite.txt` | 全量 `python -m pytest -n auto` | **4815 passed / 1 skipped**（79.6s） |
| `verify-05-js-suite.txt` | 完整前端门禁 `node --test "tests/js/*.test.mjs"` | **1645 passed / 0 failed** |
| `verify-05-browser.txt` | `node --test tests/browser/hwcheck.spec.mjs`（真 chromium + 8791 真后端 + 真 UV4） | **9/9**（新增两条：MPU6050 专精小节 + 同组互斥单选交换） |

**未上板（如实记账，spec「没跑过就写未上板，不假装」）**：本机没有 MPU6050 模块与地猛星/最小系统板，
所以**上板那一步没跑**——本单的证据是"编译绿 + 产物行为在宿主机上真跑通 + 契约与守卫全覆盖"，
不含"对着真器件看过现象"。检测页的读数参考值（静止时 |a|≈1g / 角速度≈0 / 角度≈0）来自器件手册与驱动量程，
不是本机实测。**上板后若现象与清单不符，按检测页的「不对先查哪里」走；确认是库内驱动问题的另开单。**

## 双轴评审与整改（Standards + Spec，基线 `1d190a65` 未提交工作区）

两轴并行子代理评审，**结论已逐条处置**：

**Standards 轴：3 条硬违规 + 5 组判断题**

| # | 意见 | 处置 |
|---|---|---|
| S1 | **硬违规**：工单仍 `claimed`、验收框全空（workflow.md Step 4.4） | **已修**：本文件（结单时置 `resolved` + 勾选 + 证据） |
| S2 | **硬违规**：`tests/test_hwcheck.py` 里仍用被占用的「自检」二字（spec.md:124 规定本功能一律叫「硬件检测」） | **已修**（本单 touch 到的两处）；**如实记账**：`hwcheck.py` / `webapp.py` 里的「自检报告三件套」「零器件最小自检」「串口会打印每一段自检结果」等是 01/02/04 留下的**既有**用词债（含一处用户可见文案），不在本单范围内改（改用户可见文案要连带改用例），留作后续小单 |
| S3 | **硬违规**：`index.html` 写死「当前：led / oled / ml_mpu6050」，与同一 diff 里 fx 注释「服务端按库内配方给，页面不猜哪几件有」自相矛盾；同句还残留 Markdown `**…**`（HTML 里会原样显示星号） | **已修**：删掉写死清单 + 改用 `<strong>` |
| S4 | 陈旧 docstring：`hwcheck.py` / `hwcheck_recipe.py` 仍写 `\xNN`（本单已改八进制） | **已修**（两处都改；`webapp.py` 的「载荷三键」也改成四键） |
| S5 | `_section_includes` 声称"与框架那几行重名时只印一次"，实现只在 sections 内部去重 | **已修**：`render_main_c` 把框架已印的头名传进 `skip`，声明与实现一致 |
| S6 | `_LOCAL_DECL_RE` 的注释被读成"描述现状"（评审实测 `"int"` 不匹配） | **已修**：改写成反事实表述（放宽成 `\s*` 才会拆成 `i`+`nt`） |
| S7 | `RecipeSection` docstring 称 locals 是"第 7 项"、include"第 8 项"，与 `_SEGMENTS` 顺序相反 | **已修**：按字段顺序改写，不再给自相矛盾的编号 |
| S8 | 判断项：八进制解码器在两个测试文件各一份（共三份） | **已修**：单源到 `tests/_c_escape.py`，两个文件 thin 引用；判"编译器读出什么"的 C 语义量具仍单独一份（用途不同，已在模块头写明） |
| S9 | 判断项：`_extern_names` 与 `_define_names` 近乎同形，可合并 | **保留并说明**：两者正则与语义不同（对象宏 vs extern 变量），合并只会多一个"薄包装"（Middle Man）；调用点已经是一行 `|` 并集 |
| S10 | 判断项：`platform_header_names` 自称与生成门禁"同口径"，实为第三套头名实现 | **已修**：docstring 改成"方向一致、口径不同"并写清两处各自判什么（门禁判真实工程可解析性，这里判库/母版声明过） |
| S11 | 判断项：`_recipe_runtime(needs_probe_none=True)` 的默认值无人用 | **已修**：删默认，两个开关都由调用方显式算好 |
| S12 | 判断项：`_declared_names` 放宽后在理论上可被"两标识符开头的调用式"满足；另有一条恒真断言 | **已修**：删掉恒真断言；`_declared_names` 保留（放宽是为了认 `void SysTick_Handler(void)` 这种非 static 定义，实测形态不会误吞裸调用），理由写进 docstring |
| S13 | 判断项：`src/contest_generator/hwcheck.py` 的「自检」同 S2 | 见 S2 的如实记账 |

**Spec 轴：3 条缺失/偏弱 + 1 条范围蔓延 + 2 条实现问题**

| # | 意见 | 处置 |
|---|---|---|
| ① | 工单没结 + 全部证据里 grep 不到「未上板」 | **已修**：本文件 resolved + 证据表 + **「未上板」单列一段** |
| ② | **红证偏弱**：原有红证只让"断言 expect == 0x68"变红，没有证据表明"读回值不符会走 FAIL 分支" | **已修（本单最值钱的一条整改）**：新增 `probe-05-verdict-behaviour.py`——把**渲染器真产出的那一节**用 gcc 编起来真跑（探头桩可控）。0x68 → OK + 六轴读数；0x69 → FAIL + 中文排查行、**一行读数都没有**。票面那条红证现在是**行为证据**，不是文本断言 |
| ③ | spec 判据第③层「给正常范围参考」只落在 stm32 note | **已修**：mspm0 note 补「静止放平时 pitch/roll ≈ 0°；**yaw 会缓慢漂移**（这套 DMP 无磁力计，漂是物理事实不是坏了）」 |
| ④ | 范围蔓延：`index.html` 与 `hwcheckSectionsEmptyHTML` 两处未要求的文案改写 | **保留并说明**：这两处原文在本单之后**已经变成假话**（"逐件的检测小节与板上通断判定还在做" / "当前是 led / oled"）——改的正是"本单让它们过期"的那一句，符合本仓库"陈旧文案当场修"的既有标准（04 的评审同款） |
| ⑤ | **校验被整平台免除**：母版树缺失就 `continue`，那个平台的函数名/include/locals/prereq 全不判（而 mspm0 仅凭模块头就能判） | **已修一半 + 如实记账**：母版缺失时的宽免**保留**（那是 04 定下的"判不了就不判，页面照常可用"——stm32 的 `OLED_Init` 这类只住母版的名字没有母版就判不了），但**新增用例证明"母版配齐时两个平台都不免检"**：注入 stm32 的函数名错 / mspm0 的头名错，两个平台的预览都 400 并点名。也就是说**产品路径上不存在"整平台免检"**，宽免只在"用户根本没导入母版"时生效 |
| ⑥ | `prereq` 段的判据面（04 留的接口备忘） | **已定**：函数名判据面 = **该平台库内任何模块 ∪ 母版**（跨模块前置调用天生如此）；`test_validate_covers_the_prereq_segment_across_modules` + 注入探针 E 双向钉住 |

**一句话**：两轴的硬违规全部落地；判断题里 2 条"保留并说明"（S9 合并薄包装、Spec④ 文案连带修）
与 1 条"已修一半 + 记账"（Spec⑤ 母版缺失宽免）都写清了取舍——没有留下没说法的沉默。

## 给后续工单的接口备忘

- **06（串口命令台）**：`console` 段照旧（本单没给 ml_mpu6050 加命令字符——命令表与字符冲突判定都在那一单）；
  本单新增的 `include` 段若某件要 include 新头（如 `debug_uart.h` 之外的东西），照 ml_mpu6050 的写法加即可。
- **07（通用降级）**：本单的 `include` / `locals` 两段是"专精件"的机制，通用小节**不需要**它们
  （降级 = 初始化 + 总线扫描，不猜读函数）；`SECTION_TAG` 的可见标记判据不变。
- **08/09**：本单把「平台不对称」的**数据形态**立起来了（同一件两个平台可以有不同的 include / locals /
  probe / read / note），ADR 里值得记一条：**平台差异住在配方数据里，不在渲染器分支里**
  （`hwcheck.py` 的平台分支只剩文件作用域垫片与固定 include 两张表）。
- **本单立起的两条量具**（以后任何"生成 C 代码"的功能都能复用）：
  ① `probe-05-compile-matrix.py` 的双平台真编译骨架（UV4 + gmake/SysConfig）；
  ② `probe-05-verdict-behaviour.py` 的"把渲染产物编起来真跑"骨架（gcc + 桩头/桩函数 + 宏控返回值）
  ——文本断言证明不了的运行时行为（判定翻不翻、return 有没有生效），这一招能证明。
- **量退出码要小心**：`python probe.py 2>&1 | Select-Object -Last N` 会把 python 的 stderr 警告
  包装成 PowerShell 的 NativeCommandError，**退出码显示 1**（其实探针是 0）。要判退出码就
  `*> $null` 后看 `$LASTEXITCODE`（本单实测）。
