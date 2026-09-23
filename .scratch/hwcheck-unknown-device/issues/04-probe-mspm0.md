# 04 — mspm0 探测分支 + 两平台编译矩阵

**要做什么：** 同一件自建件在**地猛星**上也能生成探测程序（走 `I2C_0` / PA0(SDA)、PA1(SCL)），并把这一对脚的平台代价如实标注到页面与产物。

**被谁阻塞：** 03（探测小节渲染与注入）

**状态：** resolved

- [x] mspm0 生成的探测程序真编译 **0 error / 0 warning**（gmake 口径），本趟 `I2C_0_INST` 在实例里活着
- [x] 探测代码的 `DL_*` 调用**全在模块 `.c` 里**，`main.c` 一个字都不直接调 SDK（mspm0 母版无 `.h`，写进 main.c 实测被门禁判未定义）
- [x] 页面这一次的接线说明写的是 **PA0 / PA1**，并注明：与**板载 LED 共用**（通信期间 LED 微闪）、PA0 的板载上拉位未焊
- [x] 产物注释写同样这两条，**与页面同一句措辞**（前端不另写一份）
- [x] 非 I2C 自建件在 mspm0 上同样不生成探测程序（与 stm32 口径一致）
- [x] 两平台编译矩阵一起复跑（照既有编译矩阵口径，含"一件都不选 / 只有自建件 / 自建件 + 库内器件 / 全选"几类形态）：0 error / 0 warning；读数记进本工单

> 勾选口径（评审整改后重述）：第 6 条里的"全选"在检测页上的真实规模 = **库内有本平台配方的全部器件**（mspm0 9 件 / stm32 7 件），矩阵用 `all-recipes` 那一格如实量了；地猛星上它**物理装不下**（产品在生成前 400 点名要撤哪几件——那是正确行为，不是这一单的失败），所以验收线落在 `all-library`（能让位装下的最大子集）。
> 第 3、4 条的"页面面"与"产物面"都补了判据（真浏览器用例 + 产物注释对账），不再靠"数据在载荷里"推。

---

## 结论（2026-09-23，工单 04 已 resolved）

### 一句话

**mspm0 这一支本来就是通的**——渲染产物平台无关（03 已定），平台差异原本只有头文件名。这一单真正做出来的东西是三件：**两平台真编译矩阵**（11 格 × 2 平台）、它抓出来的**两条真缺陷**（都在"两批小节同趟"时才现形）、以及**三条验收项的真判据**（页面面真浏览器用例、产物面注释对账、mspm0 端点面）。另发现一条既有母版缺陷，已单开 11。

### 交付物

| 落点 | 是什么 |
|---|---|
| `.scratch/hwcheck-unknown-device/probe-03-compile-matrix.py` | 真编译矩阵探针（**11 格 × 2 平台**；原 `probe-03-compile-stm32.py` 并进来、改名）。两轴：平台（mspm0 gmake / stm32 UV4）× 形态（票面四类 + 全选边界格 + 03 留下的三档定义 + 两格反向形态） |
| `src/contest_generator/hwcheck.py` | 缺陷 ①② 的修：`needs_hex` 收成**唯一产地**（两个消费者合判）、`needs_int` 判据改成"真有小节才渲"、两个出口**互相独立**；`scan_rendered` 由三处各算一遍收成一算 |
| `src/contest_generator/hwcheck_generic.py` | 通用降级批次**不再自己印** `hwcheck_report_hex`（那一份是缺陷 ① 的复制品） |
| `src/contest_generator/hwcheck_custom.py` | **平台代价那句进产物注释**（`PLATFORM_PIN_COST`，验收项 4）：与页面接线行读同一份板定义的人读复述 |
| `tests/test_hwcheck_custom.py` | 用例 **41 → 47**（33 → 38 条 `def test_`，参数化后）：两平台覆盖形状 + 全选边界格 / 助手不重定义 / 没人调的助手不渲 / mspm0 载荷里的 PA0·PA1 与板载注记 / **平台代价与板定义逐条对账** |
| `tests/test_my_devices_endpoint.py` | +1 条：**mspm0 生成端点端到端**（落盘 syscfg 里 `I2C_0` 两条 `$assign` 还在、`main.c` 无 `DL_*`、`Debug/makefile` 摆好） |
| `tests/browser/hwcheck.spec.mjs` | +1 条**真浏览器**用例：地猛星上自建件的接线表**画出了** PA0/PA1 与那两句代价（验收项 3 的页面面） |
| `.scratch/hwcheck-unknown-device/probe-04-guard-strength.py` | 反证探针（**三条**注入各自变红 + 逐字节复原 + sha256 复核） |
| `.scratch/hwcheck-unknown-device/issues/11-mspm0-pin-name-collision.md` | **发现即开单**的既有缺陷（母版引脚符号重名，17 件 I2C 器件任选两件就编不过） |

### 验收读数

**两平台真编译矩阵**（`python .scratch/hwcheck-unknown-device/probe-03-compile-matrix.py`，
读数 `probe-04-compile-matrix.txt`，逐格原始日志 `matrix-logs/custom-<格>-<平台>.log`）：

```
[custom/mspm0/empty]                    exit=0 passed=True warnings=0 devices=4
[custom/stm32/empty]                    exit=0 passed=True warnings=0 devices=4
[custom/mspm0/custom-only]              exit=0 passed=True warnings=0 devices=5
[custom/stm32/custom-only]              exit=0 passed=True warnings=0 devices=5
[custom/mspm0/custom+library]           exit=0 passed=True warnings=0 devices=8（另有已知工具链 1 条）
[custom/stm32/custom+library]           exit=0 passed=True warnings=0 devices=8
[custom/mspm0/all-library]              exit=0 passed=True warnings=0 devices=9（另有已知工具链 1 条）
[custom/stm32/all-library]              exit=0 passed=True warnings=0 devices=8
[custom/mspm0/all-recipes]              产品按预期在生成前拦下（边界读数，不计入验收线）：装不下
[custom/stm32/all-recipes]              exit=0 passed=True warnings=0 devices=8（全选规模 7 件）
[custom/{mspm0,stm32}/shape1-ping-only] exit=0 passed=True warnings=0 devices=5
[custom/{mspm0,stm32}/shape2-echo]      exit=0 passed=True warnings=0 devices=5
[custom/{mspm0,stm32}/shape3-judge]     exit=0 passed=True warnings=0 devices=5
[custom/{mspm0,stm32}/no-channel]       exit=0 passed=True warnings=0 devices=2
[custom/{mspm0,stm32}/probe-already-selected] exit=0 passed=True warnings=0 devices=5
[custom/{mspm0,stm32}/custom-not-i2c]   exit=0 passed=True warnings=0 devices=4
=== 结果：全部 PASS（0 error / 0 warning） ===（11 格 × 2 平台）
```

**`all-recipes` 那一格**（票面"全选"的真实规模）刻意**不设让位**：地猛星 9 件全上，
产品在生成前 400——`装不下：5 个引脚被两只实例同时占用…至少要去掉 5 个模块`
+ 检测页三条出路。**这是正确行为**（物理装不下就该拦），也是这一格要量的东西：
在真实规模上，产品答的是"点名哪几件、撤掉谁"而不是"生成一个编不过的工程"。
stm32 侧 7 件全上直接过（`.syscfg` 是 mspm0 的事，stm32 没有这条约束）。

**`I2C_0` 活着（验收项 1 后半）**：探针在**编译之后**读 `Debug/ti_msp_dl_config.h`
（SysConfig 的真产物）判 `I2C_0_INST`，判据是**消费者 ∩ 选中集**（`INSTANCE_CONSUMERS`），
两侧都判——选了消费者却不在 = 支点被裁掉；没选却还在 = 裁剪没随选中集走
（`ml_mpu6050` 也是 `I2C_0` 的消费者，所以判据不能写成"选了 `i2c_probe` 吗"）。

**`DL_*` 全在模块 `.c` 里（验收项 2）**：`check_mspm0` 剥注释后扫
`DL_I2C` / `DL_GPIO` / `DL_Timer` / `SYSCFG_DL_init`，22 格全无命中；行为面另有
端点用例 `test_generate_on_mspm0_keeps_the_i2c_instance_alive` 钉同一件事。

**验收项 3（页面面）**：`tests/browser/hwcheck.spec.mjs` 新增的真浏览器用例
「自建件在地猛星上的接线」——选平台 mspm0、建一件 I2C 自建件、加选、等接线表，
断言表里**真有 PA0 / PA1**、真有「板载 LED 共用（通信期间微闪）」与
「上拉位未焊」，且板上共享单独成条。自建件不是模块、没有 `pins` 声明，
这一对脚全部来自支点 `i2c_probe`（视图自动补进模块集）——所以这条必须端到端验：
**载荷里有不等于画出来了**。

**验收项 4（产物面）**：`hwcheck_custom.PLATFORM_PIN_COST` 把这两句平台代价印进
产物注释（`/* 这一对脚的平台代价（与检测页同一句）：… */`），只印 mspm0、stm32 一
个字不许有（`PLATFORM_PIN_COST[stm32] == ""`）。判据三条腿在
`test_the_platform_cost_sentence_matches_the_board_definition`：
① 板定义 `BoardPin.notes` 里那两条事实都在；② 产物那句的关键词与它逐条对得上
（板定义改了这里就红——它是复述，不许自说自话）；③ 产物里真印了。

> ⚠ **为什么产物里能写这两句、而引脚字面量不行**（本单第一版把这两件事混成一件，
> 评审纠正）：生成门禁 `_check_no_pin_literals_in_main` 是 **`clex.strip_comments`
> 之后**判的——注释与字符串里的脚名无害；它挡的是**代码内联引脚**（那样换板要重写
> 骨架，也绕开 ADR 0010 的改绑机制）。而这两句里一个引脚名都没有。

**反证读数**（`python .scratch/hwcheck-unknown-device/probe-04-guard-strength.py`，
读数 `probe-04-guard-strength.txt`）——三条注入，各自让对应的守卫变红，逐字节复原：

```
[2] 注入前（守卫在）：        PASS（三条全绿）
[3] 注入 A（通用批次又印一份十六进制助手）  → RED ｜ [4] 复原 sha256 相等 ✓
[3] 注入 B（十进制出口退回"选了器件就渲"）  → RED ｜ [4] 复原 sha256 相等 ✓
[3] 注入 C（产物不再印平台代价那句）        → RED ｜ [4] 复原 sha256 相等 ✓
[5] 复原后复跑：三条都 PASS（回绿）
[6] 收尾指纹：三个文件逐字节未变 ✓
结论：反证成立
```

**测试面**：`tests/test_hwcheck_custom.py` **47 passed**（41 → 47）、
`tests/test_my_devices_endpoint.py` **31 passed**（30 → 31，本单 +1）；
全量 `python -m pytest -n auto -q` **5234 passed + 1 skipped / 153.3s**；
前端门禁 **1739 passed / 0 fail**；浏览器门禁 **35 passed / 0 fail / 123.3s**
（34 ＋ 本单新增那条真浏览器用例）。

### 矩阵抓到的三条

**① `hwcheck_report_hex` 被定义两次（编译期 error `#247`）**——自建件（有寄存器 →
要回显）与"未专精的 I2C 件同趟"（通用降级要总线扫描）时，两批渲染器各印一份同名
助手。**只在两批同趟时现形**，单跑任一批都绿：这正是"两个渲染器各管一段、谁也不知道
对方印了什么"的形态。修法 = 那个助手**唯一产地归 `_report_function`**，判据
= 这台程序里有没有人要它（自建件读寄存器 **或** 真有扫描件）。

**② `hwcheck_report_int` 声明了没人调（`#177-D`，0 warning 线当场破）**——判据原先
是"选了器件就渲"，于是"选了件但一件小节都没出"的形态（非 I2C 自建件、本平台没有
配方的件）留下死代码。修法 = 判据改成 `any_section`——注意**不能只看配方的 `read`
段**：结尾汇总那三行（通过 / 失败 / 未判定）也走这个出口（本单第一版就栽在这一步，
4 条既有用例当场红）。

**③ 母版引脚符号重名（既有缺陷，独立于本单）**→ 另开
`issues/11-mspm0-pin-name-collision.md`：`SCL`/`SDA` 一组 17 件，
**一个自建件都不选、只勾 OLED + JY61P 就 4 个 error**。矩阵的 `all-library` 格
如实记下"为它让位了谁"，但不为它变红（那是 11 的活）；`all-recipes` 格把
"全选在真实规模上会怎样"如实记下来。

### 探针自己踩的三个坑（写下来，下一个人少走）

1. **探针必须走产品那条路**。第一版自己 `resolve_dependencies()` 展开再调
   `generate()`，漏掉 `view.pin_bindings`（检测页生成前自动移开的那几根线）——
   产物带着母版原脚去撞 PA22，10 格 mspm0 全 400。产品端点在 webapp 里调的是
   `generate_project(slugs=…, bindings=…)`，探针照抄它即可，**手推一遍就是第二个
   真相源**（与 03 评审抓到的"探针手推 slugs"同一类，第二次踩）。
2. **`Debug/ti_msp_dl_config.h` 是编译期产物**，不是生成期产物（`Debug/makefile`
   的第一条规则才跑 SysConfig CLI）。判据放在编译前 = 永远读到"文件不在"。
3. **量具不许比产品严**：引脚字面量判据要按生成门禁同款口径**先剥注释**
   （`clex.strip_comments`）——裸文本扫会把 `I2C_PROBE_SCL PA6` 这种"宏名 + 人读
   标签"误报成字面量；同理"告警计数"要排掉工具汇总行 `0 Warning(s).` 与已知
   工具链提示（`.sysmem`，选了用堆的 `ml_mpu6050` 就有、与本仓库代码无关）。

### 两条与本机/工具链有关的事实

* **`.sysmem` 提示（`#10210-D`）**：TI 链接器在"选了用堆的模块"时开一个默认 0x800
  的段并提示。实测同一份配置**去掉 `ml_mpu6050` 就一条都没有**——它既不是这一单
  的代码问题，也不该混进"我们代码的告警数"（探针分两栏记）。
* **mspm0 母版 `.syscfg` 里有 14 组重名引脚符号**（`SCL`/`SDA` 17 件、
  `CS` 5 件、`OUT` 6 件……），明细与最小复现在工单 11。

### code-review 两轴结论与整改

**Standards 轴**（3 硬违规 / 7 判断项）——**3 条硬违规全部整改**：

1. **`_report_function` 的两处 docstring 与实现相反**（评审点名）：`needs_hex` 那段
   还是 03 的单消费者口径，`needs_int` 那段写"一件读数都没有时不渲染"而代码是
   `any_section`。→ 两段都按**消费者**重写（十六进制两个消费者 / 十进制两个消费者），
   并点明"两个出口互相独立"这条实测踩出来的约束；文件头那条按需渲染清单同步更正。
2. **新守卫读一个 untracked 文件**（`.gitignore` 的标准是「测试读它 → 就要入库」）：
   `tests/test_hwcheck_custom.py` 用 importlib 读探针脚本。→ 探针**随本单入库**
   （它本来就是这一单的编译证据来源；不入库的话新 clone / CI 直接红）。
3. **同一条判据写三遍**（`scan is not None` 在 `hwcheck.py` 两处 + `hwcheck_generic.py`
   一处）：标志与渲染器会静默漂移。→ 收成 `render_main_c` 里算一次的 `scan_rendered`。

判断项当场收掉 4 条：单元素 `for helper in (...)` 循环、`_real_module` 与
`test_hwcheck_generic._real` 的重复实现、探针里算出来没用的中间量（`blocked`）、
`INSTANCE_CONSUMERS` 映射的重复推导（收进 `_pin_symbol_collisions` 一处）；
**留 2 条不改**：`test_preview_and_generate_share_the_same_render_source` 那条源码
子串断言（既有先例，挡"谁又自己拼了一份"，行为面判据另有端点用例兜）；
`check_mspm0` 自带一份引脚字面量清单（探针是量具，产品门禁那份在 `generator.py`，
两处口径不同不是漂移——量具要能独立复算）。

**Spec 轴**（缺失 3 / 蔓延 0 / 实现不对 0）——**3 条缺失全部补上**：

1. **🔴 验收项 4 没实现**（最重的一条）：产物注释里根本没有那两句平台代价，而我还
   写了一条**反向**守卫（渲染链出现那两句就红）把路堵死。评审指出两件事被我混成
   一件：门禁剥注释后判引脚字面量，而这两句里一个脚名都没有——**注释里写代价完全
   合法**。→ `PLATFORM_PIN_COST` 进产物注释（照板定义复述），反向守卫删掉、换成
   与板定义逐条对账的正面判据。
2. **🔴 验收项 3 只有载荷级断言**（"数据在载荷里"≠"页面画出来了"）：→ 补真浏览器
   用例（自建件在地猛星上的接线表里真有 PA0/PA1 与那两句）。
3. **🔴 验收项 6 的"全选"被换成手挑的十件**：票面要的是检测页的全量规模。
   → 新增 `all-recipes` 边界格（库内有本平台配方的全部，不设让位），把真实规模与
   产品的答复如实记下来；验收线仍落在能让位装下的 `all-library`，勾选口径在票头
   重述（不再让"名字对上即过"）。

评审同时纠正了我在结论里写错的两处**读数**：浏览器门禁那 34 passed 是并发跑出来
的（实际 31✔/7✖，`launcher-reload` 那三条因页面重载超时连坐），且那次整轮**没有**
覆盖页面显示；以及"03 收尾 5222"实为 **5227**（`+12` 的算法基准错了）。两条都已在
上文按复跑读数更正：浏览器门禁本单复跑 **35 passed / 0 fail**。

### 范围外 / 留给后面的工单

* **检测页把自建件那几档文案与清单画得更全**（上板清单 / 顺序 / 标注）= 工单 05；
  接线表那半本单已验（页面已显示 PA0/PA1 与代价）。
* **母版引脚符号重名** = 工单 11（本单发现并开单，不在本单修——它是母版级共享面，
  最小复现里连自建件都不需要）。
* **`.sysmem` 提示**：要消掉得动 mspm0 母版的链接选项（跨平台共享面），本单只如实
  记账，不夹带。
* **未上板**：本单证的是"两平台都能生成、能编译、0 warning"；器件真能应答要等真机
  （spec 的真机口径：没跑过就写未上板）。
