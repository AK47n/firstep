# 01 — mspm0 生成链注入 SysConfig 初始化：生成的工程烧进去，外设真的初始化

**要做什么：** 学生在地猛星上生成任何一个工程（骨架 / 赛题 / 检测），烧进板子后外设**真的被初始化**——
串口能出字、灯能闪、屏幕能亮。今天不是这样：渲染出的 `main.c` 里 SysConfig 初始化那一行是**注释占位**，
必须手动取消注释再编译才生效；不取消就是"灯不闪、串口一个字没有"，**这是最像板子坏掉的失败形态**。
根因不在硬件检测页：生成门禁按"这个名字在头文件里存不存在"判接口，而 `SYSCFG_DL_init` 由 SysConfig
**构建期**生成，于是被判成未定义调用、sanitize 顺手注释掉。骨架与赛题工程同样中招，
硬件检测只是第一个把它摆到台面上的功能——所以修在生成链，不是修某个页面。

**被谁阻塞：** 无——可立即开始

**状态：** resolved

- [x] **先量后定**：把门禁判 `SYSCFG_DL_init` 为未定义、以及 sanitize 注释掉它的那一段路径写清（进 Comments），
      再在两条候选修法里择一并写理由：① 把该符号纳入 mspm0 的**已知接口面**；② 把它作为**母版 main.c 模板的一部分**进产物，
      而不是"main.c 里的一个调用"。不许不量就选
- [x] 三条路都成立：骨架 / 赛题 / 检测生成的 mspm0 工程，那一行都是**活代码**（文本断言，不是注释）。
      反例现场：`.scratch/hwcheck-acceptance/main-mspm0.c`（当前 HEAD 实测渲染结果）
- [x] **门禁不许被削弱**：放行必须有判据，不是开白名单后门——新增/修改的门禁用例在"故意写一个真不存在的调用"时
      仍然必须红（反证读数记进本工单）
- [x] 真编译矩阵：stm32 UV4 **不回归**；mspm0 gmake **0 error / 0 warning**；检测工程两平台各至少一格
      （mspm0 三条路各一格在 `probe-01-compile-matrix.txt`；**检测工程 stm32 那格由既有 hwcheck 矩阵
      复跑补**——`[stm32] adc` / `ml_mpu6050` / `全选` 三格 UV4 0 error / 0 warning，
      读数 `.scratch/module-hwcheck/probe-09-compile-matrix.txt`）
- [x] 检测页那条「mspm0 专属：确认 `SYSCFG_DL_init();` 已取消注释」的清单项随之移除或改写——
      两个平台都不再需要学生手改一行代码
- [x] 同批更正描述该限制的既有文字：检测页渲染器的模块头注释（现在写着"这是既有生成链的已知限制，本单如实输出注释占位"）、
      `CONTEXT.md`「硬件检测」词条里对应的措辞（**实测该文件里没有这句**，见下面「没做/不该做的」）
- [x] 不碰已 resolved 的 `module-hwcheck` / `hwcheck-unknown-device` 机制（只允许"那一行从注释变活"这类被动适配）

---

## Comments

### 2026-09-24 立项依据

- 这条限制的出处：`.scratch/module-hwcheck/issues/02-minimal-selftest-to-board.md` 第 67–74 行
  （明文写着"留给后续工单（mspm0 生成链注入 SysConfig 初始化）"），以及
  `.scratch/architecture-deepening-v5/issues/08-mspm0-theia-master.md` 两处"init 注入留后续工单"。
  **至今没有这张单**——本工单就是补它。
- 现状现场（本仓 HEAD 实测，非转述）：`.scratch/hwcheck-acceptance/main-mspm0.c` 第 321 行
  `/* SYSCFG_DL_init(); */`；同文件头注释与检测页清单第 6 条都写着"上板前先取消注释"。
- 影响面判定：这是**生成链**的问题。只改检测页渲染 = 把同一个坑留给骨架与赛题工程。

### 2026-09-24 先量后定（票面第一条：不许不量就选）

**这一行是怎么被注释掉的**（读代码定位，不是转述）：

| 环节 | 落点 | 行为 |
|---|---|---|
| 接口面（喂 LLM + 判据共用） | `skeleton.build_skeleton_interfaces` | 只收**模块头 + 母版 `ml_libs/*.h`** 的文本——`ti_msp_dl_config.h` **不在母版里**（SysConfig 构建期生成），于是 `SYSCFG_DL_init` 不在已知函数集里 |
| 骨架 sanitize | `skeleton.sanitize_skeleton` / `find_undefined_calls` | 判它"不存在" → 语句位置整段替换成 `/* SYSCFG_DL_init(); */` + TODO |
| 生成门禁 | `generator._check_main_calls`（`UndefinedCallsError`） | 同一份接口面（模块头 + `corpus.master_headers`）——所以哪怕手写回去，门禁照样 400 |
| 检测页渲染器 | `hwcheck.render_main_c` | **主动**输出注释占位（模块 docstring 写明"不输出一个过不了自己门禁的活调用"）+ 清单第一条"上板前取消注释" |
| 母版模板 | `templates/main_mspm0.c` + `master.main_c_template` | 这一份**是活的**（`SYSCFG_DL_init();`）——但生成时被按赛题的骨架 main.c 覆盖 |

**量到的函数面**（`probe-01-symbol-surface.py`，扫本机 **109 份**真产物 `Debug/ti_msp_dl_config.h`，读数 `probe-01-symbol-surface.txt`）：

```
恒有（109/109，与选中集无关）：SYSCFG_DL_init / SYSCFG_DL_initPower /
                              SYSCFG_DL_SYSCTL_init / SYSCFG_DL_GPIO_init
按实例生成（名字随选中集变）：SYSCFG_DL_<实例>_init（SYSCFG_DL_OLED_init 这种）
条件生成（65/109，**不敢放行**）：SYSCFG_DL_saveConfiguration / restoreConfiguration
```

**裁决：取候选①，但要做成"精确判据"而不是前缀白名单**——

1. 放行的名字 = **恒有 4 个 ∪ 裁剪后仍然活着的实例各一条 `SYSCFG_DL_<实例>_init`**。
   判据由母版 + 选中集**现算**（`parse_syscfg(...).prune(slugs)` 的既有 pipeline），
   所以"调一个**没选中**实例的 init"（`SYSCFG_DL_LCD_init()` 而 lcd 没选）**照样红**，
   "拼错名"（`SYSCFG_DL_TYPO_init`）**照样红**——门禁没被削弱（反证项见验收）。
   不含 `save/restoreConfiguration`：它们**不是恒有**（109 份里只有 65 份有），
   放行等于让一条真会编不过的调用过关。
2. 只把"名字"放进接口面**不够**：门禁只解决"别删"，**LLM 压根没写**同样等于没初始化。
   所以另加一条**确定性**保证：mspm0 的 main.c 在 sanitize 之后，若 `main()` 体里
   没有活的 `SYSCFG_DL_init();`，就由渲染器补在函数体首（判据是词法级"活代码调用"，
   注释里的旧占位不算）。
3. 候选②（"把调用作为模板的一部分进产物"）不取：生成链的 main.c 是"LLM 出稿 →
   sanitize → 落盘"，模板那一份（`templates/main_mspm0.c`）在生成时本就被覆盖；
   要在 LLM 产物上做结构注入（切 main 体、插语句）与"LLM 自己写了怎么办"重复判定，
   而候选① + 确定性补行已经覆盖同一判据，改动面小得多。

**三条路的落点**（验收要逐条有文本断言 + 真编译）：

* 骨架 / 赛题：`build_skeleton_interfaces` 增一块"平台外部接口（构建期生成）"——
  块文本与判据**同一份**（喂 LLM 的就是 sanitize / 门禁认的那份，沿用既有单源），
  `_check_main_calls` 并入同一块；
* 检测页：`render_main_c` 直接输出**活调用**，并删掉"上板前取消注释"那条清单项与
  文件头说明；
* 母版模板：本来已经是活的，不动（作为对照腿钉住）。

### 2026-09-24 结论（本单已落地）

**一句话：** mspm0 生成链现在把 SysConfig 的 `SYSCFG_DL_*` 当作**平台外部接口
（构建期生成）**认下来——喂 LLM 的接口块、骨架 sanitize、生成门禁、检测页渲染器
认的是同一份判据；那一行活代码在三条路上都真的在了，真机编译 0 error / 0 warning。

**改法**（按上面「先量后定」的裁决，未另立修法）：

| 落点 | 改动 |
|---|---|
| `syscfg_model.py` | 新增 `MSPM0_SYSCFG_ALWAYS_INIT_FUNCTIONS`（恒有四个）+ `MSPM0_SYSCFG_INIT_NAME`（显式字面量，不再取下标）+ `MSPM0_GPIO_MODULE` + `syscfg_init_functions(model)`＝四个 ∪ 裁剪后**外设**实例各一条（**GPIO 实例不算**——实测 0/109，GPIO 引脚初始化走模块级 `SYSCFG_DL_GPIO_init`）；`save/restoreConfiguration` **刻意不含**（109 份里只有 65 份有，放行 = 让真会编不过的调用过关） |
| `skeleton.py` | `syscfg_interface_block`（读盘入口）/ `syscfg_interface_block_from_text`（**纯文本入口**，门禁走这条）+ 单源的 `_syscfg_block_lines`；`build_skeleton_interfaces` 在 mspm0 且拿得到母版时并入；判据单源 `syscfg_init_functions_for`（每调用读一次盘，骨架一路两次——docstring 如实写明）；`ensure_sysconfig_init`（纯函数，clex 词法判据）在 sanitize 后按现算结果补行，**出稿里已有整行注释形态的旧占位时就地复活那一行**；`_generate_main_c`（骨架 / 冒烟共用）接线 |
| `generator.py` | `_check_main_calls` 并入同一块（`_corpus_syscfg_interface_blocks` 走**语料文本**的纯函数入口，不读盘）；语料里没有 syscfg 文本 = 不并入（退回现状，不静默放行） |
| `hwcheck.py` | 启动行改成活调用（名字取 `MSPM0_SYSCFG_INIT_NAME` 单源）；删掉 `syscfg-init` 清单项与文件头"已知限制"段；模块 docstring 按事实改写 |
| `library/hwcheck_recipes.json` | xunji / adc 两条配方 note 里"上板前把 `SYSCFG_DL_init()` 取消注释""那一行是注释占位"改写成事实（**超出票面点名范围，但同一条限制的第三处文案**） |

**读数**：

* 真编译矩阵 `.scratch/hwcheck-acceptance/probe-01-compile-matrix.txt` —— **全绿**：
  A 骨架式 mspm0、B 赛题式 mspm0、C 检测程序 mspm0（默认双通道）三格各
  `exit=0 / error 0 / warning 0 / 产物 main.c 活调用 1 处`；D stm32（aht10+delay）
  UV4 `exit=0 / error 0 / warning 0`。产物落系统临时目录（可重建）；
  **检测工程 stm32 那一格**由既有 hwcheck 矩阵复跑补上（见下面评审整改 Sp2）。
* 反证 `.scratch/hwcheck-acceptance/probe-01-reverse.txt` —— **成立**（三份被注入文件
  逐字节复原 + sha256 复核，见读数文件抬头；sha256 随整改重跑更新，以**读数文件为准**）：
  * **针 A**（判据单源 `syscfg_model.syscfg_init_functions` 恒空 = 关掉放行面）：赛题这一路
    `UndefinedCallsError` 红；"出稿写了 init"的骨架这一路被打回 **TODO 注释占位**
    （`blocked=('SYSCFG_DL_init',)`，正是票面点名的原始失败形态）；检测页那条读成
    "该名字在构建期接口面里=**False**（对不上）"；"出稿没写 init"的骨架这一路**仍绿**
    ——补行那一道兜住了（两道保险互相独立，这说明它们不是同一个东西写两遍）。
  * **针 B**（再关掉 `ensure_sysconfig_init`，叠在 A 上）：骨架这一路才红。
  * **针 C**（把渲染器启动行换成 `SYSCFG_DL_TYPO_init();`）：门禁**仍红**
    ——`UndefinedCallsError: …不存在的函数：SYSCFG_DL_TYPO_init…`。放行面是精确
    判据，不是前缀白名单。
* `python -m pytest -n auto -q` —— **5370 passed, 1 skipped**（154s；skip 与
  本单无关，是既有的）。新增 / 改写的用例：`test_hwcheck.py` 6 条（三条路文本断言、
  精确判据、清单项删除、白名单出处重核）、`test_skeleton.py` 7 条（接口块内容、
  活调用不被占位、没写就补行且只一次、不重复插、旧占位不算、词法边界、冒烟同效）。
  **口径备忘**（不是本单引入的，但会让人误读读数）：
  `tests/test_js_gate.py::test_full_mode_runs_js_gate_and_pytest` 会真的调
  `prepush.main(["--full"])`，而 `run_pytest(full=True)` 里写死 `-n auto`——于是
  `-n auto` 跑整套时它是**嵌套的 `-n auto`**，机器一忙就输（复跑读数：`-n auto`
  下 1 failed；`-n 4` 下 `5370 passed, 1 skipped`；单跑该文件两条口径都过）。
  本单没碰 prepush / JS 门禁，判为环境性的既有抖动。

**没做 / 不该做的**（逐条一句理由）：

* **`CONTEXT.md` 一个字没改**：`grep SYSCFG_DL` / `取消注释` / `注释占位` 实测命中的三处
  都不是这条限制——「母版」行里的 `SYSCFG_DL_init() + while(1)` 是模板事实（模板本来就
  是活的、本单没改它）、「骨架」行里的"幻觉调用改注释占位"是 sanitize 机制（照旧为真）、
  「硬件检测」行里那处是"配方文件不许静默改注释占位"（配方校验，照旧为真）。
  **没有该改而没改的措辞**，故不动（票面那一条的前提在这份文件里不成立）——
  这一条是整改时逐处核过的（评审指出原稿"两处是骨架"的数法不准）。
* **约 60 个 `tests/test_module_*.py` 的 `"    /* SYSCFG_DL_init(); */\n"` 夹具没改**：
  它们是"某份 main.c"的**测试夹具**（直接喂 `generate()` 的 `main_c_content`，绕过
  骨架阶段与补行），代表的是**本单之前**的产物形态；留着正好当"旧形态工程仍能生成"
  的对照，改成活调用不会多验到任何本单判据（三条路的活调用由上面的新用例逐条钉住）。
* **多实例新实例的 init 不在放行面里**：`syscfg_init_functions` 的输入是
  `parse_syscfg(母版).prune(选中集)` 的裁剪模型，而 `render_instances` 追加的
  `LED_<N>` / `KEY_<N>` 实例发生在写侧之后（不在母版里）——所以
  `SYSCFG_DL_LED_1_init()` 仍会被判未定义。这是**既有行为、不是本单引入的回归**
  （修之前连 `SYSCFG_DL_init` 都不放行），且票面明确要求"按裁剪后模型的实例名逐条"，
  故不扩权；若要覆盖多实例，得让实例计划参与判据（另开单）。
* **另三处重写 main.c 的路径没有接确定性补行**（评审指出，本单不扩）：`deepen.py`、
  `task_progress.py`、`params.py` 也会覆写 main.c，它们走的是各自的内核、不经
  `skeleton._generate_main_c`，所以"生成链保证那一行活着"这条在**这三条路径上不成立**
  （放行面放宽之后，它们若丢掉那一行也不会报——与修之前的 hole 相同，不是本单引入）。
  补是一条小事（调用点各接一次 `ensure_sysconfig_init`），但要先确认那三条路径的
  mspm0 形态与"用户手改过的 main.c 要不要被工具补一行"这条产品判断——另开单。

### 2026-09-24 双轴评审与整改（领单 agent 复核）

**评审结论**：Standards 轴 0 条语言/格式硬违规，但**报出 2 条"文档与行为不符"+
1 条"门禁读盘"**；Spec 轴报出 **1 条真缺陷（门禁被削弱）+ 1 条缺格 + 若干自述与读数不符**。
逐条整改：

| # | 评审意见 | 处置 |
|---|---|---|
| S1 | `_corpus_syscfg_interface_blocks` 自述"吃语料不读盘"，实际转调读盘入口——违反门禁契约；实测"把语料 syscfg 换成没有实例的文本，门禁仍按盘上母版放行" | **已修**：新增纯函数 `skeleton.syscfg_interface_block_from_text`（字符串进），门禁改走它；读盘入口只是它的包装。新增用例 `test_mspm0_syscfg_surface_comes_from_the_corpus_not_the_disk`（语料空 → 连 `SYSCFG_DL_OLED_init` 也红；真母版文本 → 放行） |
| S2 | 自述"一次生成只读一次母版"，骨架实际读两次 | **已改口径**：docstring 如实写"每调用一次读一次盘，骨架这一路两次；两次输入相同、结果必然相同；不引缓存是因为失效判据比读盘贵" |
| Sp1 | **门禁被削弱（最重）**：`syscfg_init_functions` 给**每个**存活实例无条件拼 `SYSCFG_DL_<实例>_init`，于是 `SYSCFG_DL_OLED_SPI_init()` / `SYSCFG_DL_LED_BEEP_init()`（GPIO 实例）被放行，而它们在 109 份真产物头里出现 **0 次** | **已修**：按实例的 **syscfg 模块**把 GPIO 实例排除（`MSPM0_GPIO_MODULE`）——GPIO 实例的引脚初始化走模块级 `SYSCFG_DL_GPIO_init`（109/109），SysConfig **不生成**实例级 init。测得的外设实例（I2C/UART/ADC12/PWM/TIMER）保留。用例改写成四条腿（没选中的红 / **GPIO 实例即使选中也红** / 外设实例选中则放行 / 拼错名与 save·restore 红），并加母版数据守卫 `test_master_keeps_a_gpio_module_for_the_init_surface_rule`（母版把 GPIO 模块改名 → 当场红，防这条排除判据静默失效） |
| Sp2 | 缺"检测工程 **stm32** 一格"（D 格是赛题式） | **已补读数**：复跑既有 hwcheck 矩阵 `probe-09-compile-matrix.py`——`[stm32] adc` / `[stm32] ml_mpu6050` / `[stm32] 全选` 三格 UV4 真编译 **0 error / 0 warning**（读数 `.scratch/module-hwcheck/probe-09-compile-matrix.txt`），另 mspm0 各格同样全绿；判红 0 / 如实拦下 1（9 件全选装不下） |
| Sp3 | 结论里的 sha256 与读数文件不符（探针重跑后换了） | **已修**：本节读数按**最后一次**重跑填写；反证探针的注入点也搬到判据单源上（见下） |
| Sp4 | "能编译"被写成"能上板" | **已修**：`hwcheck.py` 两处措辞改成"那一行在产物里是活代码 + 工程真编译 0 error / 0 warning；板上真的动起来见工单 05（**未上板**）" |
| Sp5 | scope creep：配方 note 改写、就地复活旧占位注释 | **保留并在此记账**：配方 note 是**用户可见文案**，不改就是留一句"上板前取消注释"的假指示；就地复活是"补行"的同一判据（那一行必须是活的），只是避免"活调用 + 旧注释"并排读成"还得再取消注释一次"（新增断言：旧占位必须消失且活调用恰好一处） |
| S3 | 判断项：`MSPM0_SYSCFG_INIT_NAME = ALWAYS[0]` 位置耦合 | **已修**：改成显式字面量 + 守卫用例断言它仍在恒有那四个里 |

**整改后复跑读数**（全部在整改后的工作树上重跑）：

* 真编译矩阵 `probe-01-compile-matrix.txt`：**全绿**（A 骨架式 / B 赛题式 / C 检测程序
  mspm0 各 `exit=0、error 0、warning 0、产物 main.c 活调用 1 处`；D stm32 `exit=0、
  error 0、warning 0、活调用 0 处`）。
* 反证 `probe-01-reverse.txt`：**成立**——针 A 注在**判据单源**
  `syscfg_model.syscfg_init_functions` 上（关掉放行面）→ 赛题路 `UndefinedCallsError` 红、
  骨架（写了 init）被打回 TODO 注释占位、检测页那条"这个名字在构建期接口面里"读成
  **False（对不上）**；针 B 叠上"关掉补行"→ 骨架（没写 init）也红；针 C 证明拼错名
  **门禁仍红**。三份文件逐字节复原、sha256 相符（见读数文件）。
  > 探针本轮自己也修了两处**假绿**：① 注入点原在转调层（`syscfg_init_functions_for`），
  > 门禁走语料文本入口、扎不中——"针 A 没能让赛题变红"当场报出来；② 清缓存只清了
  > `skeleton/generator/hwcheck`，而针 A 注在 `syscfg_model`（其余模块 `from ... import`
  > 已握住旧函数对象）→ 改成**整包清**。两处都是"探针自己没换代码"，不是判据没生效。
* 领单复核 `verify-01-lead.py`（**另一条路线**：域层门禁直调，不编译、不走端点）：
  14 条全过——含"没选中的实例红 / **GPIO 实例即使选中也红** / 外设实例放行 /
  拼错名红 / save·restore 红 / 语料空文本不静默放行 / 骨架三种出稿形态各恰好一行活调用 /
  stm32 不插 / 检测页渲染活调用且不再出现"取消注释" / 检测页 stm32 不出现该名字"。
* `python -m pytest -n auto -q`：**5372 passed + 1 skipped**（整改后最终复跑，154s）。
  前一版复跑（5369 + 1 failed）撞的是 `test_js_gate.py::test_full_mode_runs_js_gate_and_pytest`
  的嵌套 `-n auto` 抖动——单跑该文件过、`-n 4` 过，见上一节的口径备忘。

