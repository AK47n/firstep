# 04 — 配方机制 + led / oled 两件专精

**要做什么：** 立起"每一件怎么测"的数据机制：库内配方文件（形状见 spec：前置 / 初始化 / 探头 / 读数展示 / 控制台命令 / 平台说明），加载时校验，**配方里引用的函数名必须能在该模块接口清单里找到，否则当场大声失败**；先让 led 与 oled 两件在生成的检测程序里有专精小节（led 心跳与通道控制、oled 分节显示）。

**被谁阻塞：** 02（要能出工程）、03（要能选器件）。

**状态：** resolved

- [x] 配方文件落库根中央文件（跟随模块库根、不新增配置键），键 = `slug → platform → 配方`
      （`library/hwcheck_recipes.json`；落点 = 模块库根的**平级兄弟**
      `<库根>/hwcheck_recipes.json`，`hwcheck_recipe.recipe_library_path` 单源推导，
      与 topics / references 同款布局；**没加任何配置键**）
- [x] 配方字段按 spec 六段：`prereq` / `init`（+期望）/ `probe`（+期望）/ `read`（+单位）/ `console` / `note`；缺段表示该件不支持该项
      （六段全在 `_SEGMENTS`，段形状统一是对象：`{calls}` / `{expressions|items}` /
      `{lines}` / `{command, description}`；`console` 本单只解析 + 校验 + 进载荷，
      **C 侧分派归工单 06**——文件头也不再提前印"控制台命令"，等命令表真落地再印）
- [x] 加载校验（纯函数，可内存直测）：键必须是库内真实 slug、必须存在该平台条目、引用的函数名必须在接口清单内；任一不满足 = 构建期失败 + 中文理由（**不学骨架兜底改成注释**）
      （`parse_recipes` 判形状 / `validate_recipes` 判引用，两者都是纯函数；
      形状的 20 条 + 引用的 10 条都在 `tests/test_hwcheck_recipe.py`。
      **read 段的裸常量也查**——见「评审整改」②）
- [x] **红证**：故意把某条配方的函数名写错 → 守卫用例变红并点名；恢复即绿（证据落 Comments）
      （`negative-verify-04.py` 有 16 条注入，其中 A/B/P 三条就是"引用判据被掐"；
      真机红证在 `verify-04-real-machine.txt` ⑥：改坏 `led_init` → 产品端点 400 点名
      `led_initX`，配方文件逐字节复原）
- [x] led 专精：stm32 走板载三色通道宏、mspm0 只走通道 0（该平台驱动会把越界通道静默钳回 0，配方不得照搬红黄绿宏）
      （真库配方：两平台都只 `led_init(LED_RED)`；mspm0 的 note 写明"越界通道被钳回 0，
      所以只测通道 0"，**调用面**不出现 LED_YELLOW / LED_GREEN——note 里提到它们
      是**说明的一部分**，判据只查调用面，见「评审整改」⑥）
- [x] oled 专精：两平台分节显示可用；地猛星无浮点显示接口这一事实在配方层处理（不在地猛星侧写浮点显示调用）
      （两平台都 `OLED_Init()` + 探头动作"让屏上出现一行 OLED OK"；两侧 note 都写明
      "无浮点显示接口 / 只回显整数 / 小数由工单 05 的配方自己拆"）
- [x] 生成的检测程序里，专精件与未专精件的段落**外观可区分**（用户能一眼看出哪件是"真测了"）
      （专精小节带 `[专精]` 标题尾标 + 页面徽章；未专精件走 `unspecialized` **逐条点名**
      "不会给它出检测小节"——程序里不生成通用小节是 07 的边界，所以"段落外观"这条
      在**页面**上成立、在程序里是"有 / 无"，如实记账见「评审整改」⑦）
- [x] 渲染仍为零 LLM：整套渲染路径不产生任何模型调用（结构断言）
      （`test_recipe_rendering_never_calls_a_model`：两个域模块都不 import LLM 层、
      `render_main_c` / `load_recipes` 签名里也没有 llm 参数）

## 边界与决策引用

- 配方是"怎么用这个模块"的元数据，**不是模块逻辑**：不写进模块源码、不改变"模块 = 纯驱动切片"的既有边界（ADR 0009 关系记在新 ADR 里）。
- 通用降级（未专精件）归 07，本单不做。

## Comments

### 开工前的判断（读完既有件之后：哪些直接用、哪些不重造）

| 既有件 | 判断 | 落点 |
|---|---|---|
| `skeleton.extract_header_functions` / `format_interface_blocks`（骨架自检与生成门禁共用的接口块提取） | **直接用**：配方引用的函数名判据与生成门禁同源，避免"配方过了校验、门禁说未定义" | `hwcheck_recipe.interface_names` |
| `ModuleCorpus.master_headers`（生成语料的母版头） | **直接用**：`files: []` 的平台条目（stm32 的 led / oled / delay）实现在母版里，能调的函数全在母版头 | 同上（webapp 装配点喂进去） |
| `readme.sort_verification_order`（bring-up 稳定分区） | **直接用**：小节顺序与工程 README「验证顺序清单」同一函数 | `hwcheck_recipe.resolve_sections` |
| `entry_store` / `HwCheckError` | 异常类**拆成叶子模块** `hwcheck_errors.py`（工单 04 起 `hwcheck` 要反向 import 配方渲染件，异常留在 `hwcheck` 里就成环） | `hwcheck_errors.py`（原位置继续可 import） |
| `hwcheck.HwCheckConfig` / `render_main_c` | **扩参**：`render_main_c(config, sections=())`——缺省空 = 工单 02 的框架形态逐字节不变 | `hwcheck.py` |

### 三个设计决策

1. **接口清单 = 模块头 ∪ 母版头**（`interface_names`）：只看模块自己的头会冤枉 stm32 的
   led / oled（它们 `files: []`，一个模块头都没有）；只看母版头会放过模块自带的
   `OLED_RES_128X64` 之类。两份并集 + **对象宏名**（`#define LED_CHANNEL_COUNT 3`——
   门禁的提取只收类函数宏与带类型的声明，配方读数最自然的写法恰恰是对象宏）。
2. **判定全部在板上算**（渲染期只生成比较式）：`init_expect` / `probe.expect` 有值就
   落比较式、探不到打 FAIL 并直接 return；判不了的（void 初始化 / 纯输出件）如实打
   `hwcheck_verdict_probe_none` + "只看现象"，**不算通过**。渲染期**不写判定结果**
   （写了只会是恒定值，汇总侧照它分支就是一条永不触发的死路）。
3. **中文字面量一律转义成 `\xNN`**（`hwcheck_recipe.c_string`）：见「真机判例」——
   ARMCC 5.06 按本地代码页解析源文件，原样中文串会让整份 main.c 编不过。注释保留
   中文（给人读，不影响解析）。

### 真机判例：中文字面量让 ARMCC 报 22 个 error（本单最值得记的一条）

`.scratch/module-hwcheck/probe-04-compile-matrix.py`（UV4 真编译四种形态）第一次跑出来：

| 形态 | 结果 |
|---|---|
| 框架（不选器件） | 0 error |
| led / oled / led+oled 专精 | **22 / 22 / 22 error** |

三类错（原始 buildlog 留在 `probe-04-buildlogs/`）：

1. `#8: missing closing quote` × 20 —— **中文字符串字面量**：ARMCC 默认按本地多字节
   代码页（本机 GBK）解析源文件，「通过：」的 `EF BC 9A` 里最后那个 `0x9A` 被当成
   GBK 前导字节，把收尾引号 `0x22` 当尾字节一起吞掉 → 该行字符串没有收尾引号。
2. `#513: a value of type "void" cannot be assigned to an entity of type "int"` ——
   `r = led_init(LED_RED)`：`void led_init(uint8_t)` 没有返回值，配方给的
   `init_expect: "0"` 是**编出来的**期望。
3. `#20: identifier "OLED_RES_128X64" is undefined` —— stm32 的 oled **模块条目里
   没有这个宏**（它在 mspm0 的 oled.h 里），而配方 read 段引用了它。

三条都治了根，代价是三条**测量**（都在同目录，可复跑）：

| 量具 | 量什么 | 结论 |
|---|---|---|
| `probe-04-armcc-utf8.py` | 哪些收尾字符会让 ARMCC 炸 | 12 个候选 6 个炸：全角冒号 / 全角括号 / 句号 / 汉字 / 等号结尾 + 全角括号后接汉字——**跟字符无关，跟"字节对 + 引号"有关** |
| `probe-04-armcc-flags.py` | 加什么编译开关能治 | `--locale=english` → 0 error；`--multibyte_chars=utf8` → ARMCC 5.06 不认这个选项 |
| `probe-04-escaped-literals.py` | 不靠开关行不行 | **把非 ASCII 转义成 UTF-8 字节 → 0 error，且产出的字节与原文逐字节相等** |

取第三条（转义）：不动母版工程的编译开关（那是跨平台共享面），也不依赖任何编译器
的本地化设置；上网后学生看到的还是同一个字。转义单源 = `hwcheck_recipe.c_string`。

编译矩阵最终（`probe-04-compile-matrix.txt`）：**四种形态 0 error / 0 warning**。
顺带治掉两条 `#177-D: declared but never referenced`（`hwcheck_verdict` /
`hwcheck_report_int` 在"没有可判项"的形态里是死代码）——按需渲染，见「评审整改」④。

### 测试缝

- 域层纯函数（`parse_recipes` / `validate_recipes` / `resolve_sections` /
  `render_recipe_section` / `render_recipe_summary`：内存直测）——`tests/test_hwcheck_recipe.py` 43 条。
- 渲染结构（专精 / 未专精可区分、三档分账、纯 ASCII 回归守卫、死代码守卫）——
  `tests/test_hwcheck.py` 新增 12 条。
- 端点：`TestClient` + 真库真母版（preview / generate / project 三个端点都带
  `sections` 与 `unspecialized`）。
- 前端：`tests/js/hwcheck.test.mjs` ⑦ 段 8 条 + `fx-guard` 登记 6 个新导出。
- 浏览器：`tests/browser/hwcheck.spec.mjs` 新增「专精小节」用例（7/7）。
- 真机：`probe-04-compile-matrix.py`（UV4 四形态）+ `verify-04-real-machine.py`（20 条判据）。

## 实施结果与证据（都在 `.scratch/module-hwcheck/`）

| 证据文件 | 内容 | 结论 |
|---|---|---|
| `probe-04-armcc-utf8.py` / `.txt` | 量具：ARMCC 对中文字面量的容忍边界（12 候选逐个真编译） | 6 个炸（全角冒号 / 括号 / 句号 / 汉字 / 等号结尾…） |
| `probe-04-armcc-flags.py` / `.txt` | 量具：三组编译开关 | `--locale=english` 0 error；`--multibyte_chars=utf8` 不被支持 |
| `probe-04-escaped-literals.py` / `.txt` | 量具：`\xNN` 转义 | 转义版 0 error，**字节与原文逐字节相等** |
| `probe-04-compile-matrix.py` / `.txt` + `probe-04-buildlogs/`（含 `-broken/` 整改前那一跑） | UV4 真编译四种形态 | **4/4 全绿（0 error / 0 warning）**；整改前的 22 error 原始日志留在 `-broken/` |
| `verify-04-real-machine.py` / `.txt` | 走产品端点：配方校验 / 专精小节 / 未专精点名 / 顺序 / 回读 / 母版缺失降级 / **UV4 真编译三形态** / 配方写错的红证 | **20 条判据全 PASS，判红 0** |
| `verify-04-suite.txt` | 全量 `python -m pytest -n auto` | **4783 passed / 1 skipped**（137s） |
| `verify-04-js-suite.txt` | 完整前端门禁 `node --test "tests/js/*.test.mjs"` | **1638 passed / 0 failed** |
| `verify-04-browser.txt` | `node --test tests/browser/hwcheck.spec.mjs`（真 chromium + 8791 真后端 + 真 UV4） | **7/7** |
| `negative-verify-04.py` / `.txt` | 判据强度探针：**16 条注入** | **16/16 注入后对应用例变红**，文件逐字节复原 |

## 双轴评审与整改（Standards + Spec，基线 `52e2fbd2` 未提交工作区）

两轴并行子代理评审，**结论已逐条处置**：

**Standards 轴：1 条硬违规 + 6 条判断题**

| # | 意见 | 处置 |
|---|---|---|
| S1 | **硬违规**：`hwcheckSectionsEmptyHTML` 已导出却没登记 `fx-guard.test.mjs` 的 `DOMAINS` 表（正向白名单 → 漏登记静默不漏红） | **已修**：补登记（该表的约定就是"新 fx 导出必须登记"） |
| S2 | Duplicated Code：`_section_reports` 定义了两遍（前一份被遮蔽 = 死代码） | **已修**：删掉重复定义 |
| S3 | 死分支：`render_recipe_section` 从不产生 `verdict == "fail"`，而汇总按它过滤 → 「失败件的排查指引」永不触发（用例手工塞数据掩盖了它） | **已修**：渲染期**删掉结果字段**（判定只有板上才产生），汇总改按"有没有带判定的件"决定印不印排查行；用例同步改成"不按结果过滤" |
| S4 | Speculative Generality：`specialized` / `platform` / `prereq` 前端不消费；`_report_dispatch` 的 `line_var` 没人传 | **部分已修**：删 `specialized`（假字段）与 `line_var`（死参数）；`platform` / `prereq` **保留并说明**——那是配方契约的可见面，06 的命令表要读同一份载荷（缺了下一个工单就得改端点） |
| S5 | Data Clumps：三个端点各自拼 `view.to_dict()` / `_hwcheck_sections_payload` / `unspecialized` | **已修**：`_hwcheck_view` 直接回板块载荷字典，三处 `**board["board"]` 展开 |
| S6 | Divergent Change：`hwcheck_recipe.py` 既管纯解析又读盘 | **保留并说明**：`load_recipes` 是"数据 + 其磁盘形态"的所有者，与 `hwcheck_store`（检测工程的落点 / 回读）不是一回事；拆开会让"配方从哪来"有两处。已在模块头写明边界 |
| S7 | 小项：`errors.py` 从 `.hwcheck_recipe` 而不是叶子取异常；`_hwcheck_view` 里逐件重算 missing 集合 | **已修**：errors.py 改指 `hwcheck_errors`；missing 集合提到循环外 |

**Spec 轴：7 条（其中 5 条是本单最值钱的发现）**

| # | 意见 | 处置 |
|---|---|---|
| ① | **专精产物编译不过**（UV4 实测 22 error：中文字面量吞引号 / void 赋值给 int / 跨平台常量未定义） | **已修**（本单最大的整改）：中文字面量全部经 `c_string` 转义、`init_expect` 可缺省（void 初始化如实"不判返回值"）、read 裸常量纳入判据、oled 的 read 换成两平台都有的常量。**新增编译矩阵探针**把"spec 要求的 stm32 编译绿"这条判据真正覆盖到本单产物（4/4 全绿） |
| ② | 函数名判据在最关键处失效：`_calls_in` 只认"标识符紧跟 `(`"，**裸常量一律放行**，而 pilot 的 read 恰好全是裸宏 | **已修**：read 段整条表达式过判据（含裸常量），并补了「裸常量不在清单 → 红」的用例与注入（探针 P） |
| ③ | 空清单宽免 `if not known: continue` 让守卫在"母版库未配"时静默失效 | **已修一半、如实记账**：宽免保留（判不了就不判，页面照常可用，否则没导入母版的机器上检测页直接 400），但**真实库的地位断言**（`test_real_library_recipes_reference_only_real_interfaces`）在真库 + 真母版头上把每条配方都过一遍——那条路判据是完整的；母版缺失时的降级有专门用例与真机证据 ⑦ |
| ④ | `prereq` 段的说明指向不存在的文档（悬空引用） | **已修**：说明写进 `RecipeSection.prereq` 与 `validate_recipes` 的 docstring（跨模块前置调用归工单 05，本单没有跨模块 prereq） |
| ⑤ | 汇总无条件印 trouble（探头判过的件也先喊一句"通信失败…"；led 的"只看现象"印两遍） | **已修**：只在"有带判定的件"时印，且只印带判定件的排查行 |
| ⑥ | 「led 专精：stm32 走板载三色通道宏」只有散文（只调 `LED_RED`，三色宏仅在 note） | **如实记账**：三色宏在 stm32 侧由 `led_instances.h` 提供、note 里逐条讲清；**调用面只调 LED_RED 是刻意的**——检测程序的目的是"确认灯会亮"，逐个通道点灯是赛题逻辑不是 bring-up。真库用例同时钉住 mspm0 不得出现 YELLOW / GREEN（钳回 0 的平台事实） |
| ⑦ | 「专精件与未专精件的**段落**外观可区分」在程序里只表现为"有 / 无" | **如实记账**：通用小节归工单 07，本单的"可区分"落在**页面**（`[专精]` 徽章 + 未专精逐条点名）与文件头；`SECTION_TAG` 常量已备好，07 的通用小节不带它 |
| ⑧ | 串口行尾 `\r\n`→`\n`；`console` 无 C 分派却在文件头印"控制台命令"；零 LLM 断言偏弱 | **已修后两条**：文件头不再提前印命令（等 06 落地）；零 LLM 断言改成结构化的（两个模块都不 import LLM 层 + 签名里没有 llm 参数）。行尾：新出口统一按 `\n` 攒行，**串口端行尾归工单 06 的命令循环一起定**（本单没有 `\r\n` 的消费方证据，不擅自加） |

**未修但记账**：mspm0 侧的真机编译矩阵（本机没有 gmake/CCS 那一路的判据留到 05，
`verify-04-real-machine.py` 的编译段只覆盖 stm32 UV4）；跨器件命令字符冲突归 06。

## 给后续工单的接口备忘

- **05（MPU6050 探头）**：`init_expect` / `probe.expect` 就是"板上判定"的两个入口；
  `prereq` 段已在配方里预留（stm32 侧软 I2C 初始化这类跨模块前置调用，本单没有
  实例，校验暂不覆盖 prereq）；read 表达式必须是整数（渲染走 `hwcheck_report_int`），
  小数按 note 里写的"拆整数 / 小数两次显示"。
- **06（串口命令台）**：`console` 段已解析 / 校验（单字符硬要求）并进载荷
  （`sections[].console`），命令表与字符冲突判定在那一单做；产物里的行尾策略也在
  那一单定。
- **07（通用降级）**：`SECTION_TAG` 是"专精"的可见标记，通用小节**不带**它；
  `unspecialized` 载荷（本单的"点名"）是那一单要接着长成"通用小节"的入口。
