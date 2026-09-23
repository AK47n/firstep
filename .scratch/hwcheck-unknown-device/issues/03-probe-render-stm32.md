# 03 — 探测小节渲染 + 注入 + stm32 真编译

**要做什么：** 选了自建件、平台是 stm32 时，生成的检测工程 `main.c` 里多出这一件的探测小节：**ping 地址**（板上判应答）+（可选）**读一个身份寄存器**——有期望值就判 OK/FAIL，没有就**只回显读到的字节**。全程确定性渲染、过既有生成门禁、真编译通过。

**被谁阻塞：** 01（`i2c_probe` 模块）、02（定义与表单）

**状态：** resolved

- [x] 新域模块 `hwcheck_custom.py` 拥有「定义 → 探测小节 C 语句 + 页面文案」这一半（纯函数、字符串进字符串出、零 LLM），可在内存里直测
- [x] 三种形态按定义分档，且**页面上说的与板上做的一致**：① 只有地址 → 只 ping + 明说"这一趟只验了应答"；② 有寄存器无期望值 → 读回显（十六进制）+ 明说"没有期望值可比，只回显"；③ 有寄存器 + 期望值 → 板上比较并判 OK/FAIL，失败给排查话术（供电 / 上拉 / 线序 / 地址写法）
- [x] 无输出通道时不渲染小节（照既有"不假装测过"口径：渲染了也没人看得见）
- [x] 有自建件时主程序的模块集**自动带上 `i2c_probe`**；自建件本身**不进 slugs**（它不是模块，库外 slug 会在生成链上游被拒）
- [x] 构建期守卫：渲染出的调用集 ⊆ `i2c_probe` 头里的接口（找不到即红）；产物里**没有任何写寄存器调用**、**没有任何引脚字面量**（脚一律走宏名 / 模块参数）
- [x] 注入点在 main.c 的**唯一产地**（预览与生成共用同一份渲染，两处产物逐字节一致）
- [x] stm32 真编译 **0 error / 0 warning**；既有按需渲染口径不破（该留的函数在、该死的一个不留）
- [x] 反证：让渲染器多调一个不存在的函数，守卫用例必须变红（读数记进本工单）

---

## 结论（2026-09-23，工单 03 已 resolved）

### 交付物

| 落点 | 是什么 |
|---|---|
| `src/contest_generator/hwcheck_custom.py` | 新域模块：自建件定义 → **探测小节 C 语句 + 页面文案**（纯函数、零 LLM）。`CustomSection` / `render_custom_section` / `resolve_custom_sections` / `sections_payload` / `custom_headers`；三档文案（`PLAN_PING_ONLY` / `PLAN_ECHO_ONLY` / `PLAN_JUDGE`）与 `RUNTIME_CALLS` 白名单都住在这里 |
| `src/contest_generator/hwcheck.py` | `render_main_c` 新增第 4 个参数 `custom`（**唯一产地**照旧：预览与生成都调它）；`_report_function` 新增按需渲染的 `hwcheck_report_hex`（`needs_hex`）；include 段按 `custom_headers(platform)` 印支点头；上电调用段排在库内两批之后 |
| `src/contest_generator/hwcheck_board.py` | `hwcheck_view` 的接口从 `custom_device_ids` 换成 **`data_dir`**（一个参数就是一个真相源）：读「我的器件」→ 解析小节 → 从模块集里摘掉自建件 → 真有小节时自动带上 `i2c_probe`；`HwCheckView` 新增 `custom` 字段；载荷新增 `custom` 键 |
| `src/contest_generator/webapp.py` | 四个检测端点改传 `data_dir=context.config_path.parent`；预览与生成把 `view.custom` 一起喂 `render_main_c`（删掉了 02 留下的 `_my_device_ids()` 中转件） |
| `tests/test_hwcheck_custom.py` | 41 条判据（三形态 / 只读 / 无引脚字面量 / 小节形状 / 载荷 / 用户文本消毒 / 接进 main.c 的按需渲染与顺序 / generation_slugs） |
| `.scratch/hwcheck-unknown-device/probe-03-compile-stm32.py` | 真编译探针（四种形态走产品真路径生成 + UV4 编译） |
| `.scratch/hwcheck-unknown-device/probe-03-guard-strength.py` | 判据强度探针（反证项 8 的量具，逐字节复原 + sha256 复核） |

### 验收读数

**真编译**（`python .scratch/hwcheck-unknown-device/probe-03-compile-stm32.py`，原始日志
`matrix-logs/custom-*.log`；**不手写 main.c**——手写就绕过了要验的东西，这五格都是
`hwcheck_view` + `render_main_c` 真路径渲染出来的产物，模块集吃 `view.generation_slugs`）：

```
[custom/shape1-ping-only] exit=0 passed=True warnings=0     ← 形态① 只有地址
[custom/shape2-echo]      exit=0 passed=True warnings=0     ← 形态② 有寄存器无期望值
[custom/shape3-judge]     exit=0 passed=True warnings=0     ← 形态③ 有寄存器 + 期望值
[custom/mixed-library]    exit=0 passed=True warnings=0     ← 库内专精件（ml_mpu6050）+ 自建件同趟
[custom/no-channel]       exit=0 passed=True warnings=0     ← 无输出通道（产物里零自建件字样）
=== 结果：全部 PASS（0 error / 0 warning） ===
```

> `mixed-library` 那格是评审补的：三个"按需渲染"开关（`needs_hex` /
> `needs_verdict` / `needs_probe_none`）的交点正在"库内件 + 自建件同趟"这个形态上
> ——只跑"自建件单独"证不到它。

**反证读数**（`python .scratch/hwcheck-unknown-device/probe-03-guard-strength.py`，
读数 `probe-03-guard-strength.txt`）——往渲染产物里多插一句头里不存在的
`i2c_probe_write_reg(...)`（同时是写侧调用）、逐字节复原后复核 sha256 相等：

```
[1] 前置检查：源文件 sha256=3007befc3f5c9659…，注入目标唯一 ✓
[2] 注入前（守卫在）：        PASS（全绿）  ｜ 4 passed
[3] 注入后（多调不存在的函数）：RED（守卫用例变红）｜ 4 failed
[4] 复原复核：sha256 相等 ✓（3007befc3f5c9659…）
[5] 复原后复跑：              PASS（回绿）  ｜ 4 passed
结论：反证成立（多调一个不存在的函数 = 守卫当场变红）
```

→ **验收项 8 成立**：那 4 条 = 参数化的头接口对账（2 平台）+ 读侧白名单 + 写调用
禁令；注入后全红（`i2c_probe_write_reg` 既不在头里、又是写侧调用，两条判据各挡一半）。

**附：用户文本消毒那条守卫的反证**（评审抓到"用户文本原样进 C 注释"这个缺陷后补的）；
读数 `probe-03b-sanitize-strength.txt`——把 `_comment_text` 改成恒等（= 回到修复前）
→ 用例变红 → 逐字节复原 → sha256 相等 → 复跑回绿。

**测试面**：`tests/test_hwcheck_custom.py` **41 passed**；全量
`python -m pytest -n auto -q` **5227 passed + 1 skipped**（那 1 条 failed 是仓库
既有的并行争用偶发 `tests/test_js_gate.py::test_full_mode_runs_js_gate_and_pytest`
——**单跑该文件 29 passed / 111s**，与本单无关，环境事实已记进 local-environment）；
前端门禁 **1739 passed / 0 fail**；浏览器门禁 **34 passed / 0 fail**
（连跑时 `launcher-reload.spec.mjs` 偶发红，**单跑 3/3 绿**——同一类争用偶发，
那支 spec 不碰检测页）。

### 验收第 6 条（注入点唯一产地）的两条腿

除了源码文本判据（`test_preview_and_generate_share_the_same_render_source`：两个
端点都调 `render_main_c(…, view.sections, view.generic, view.custom)`，路由层不许
自己拼小节名），**行为面**是 `tests/test_my_devices_endpoint.py` 的
`test_preview_and_generate_render_byte_identical_main_c`：预览出的 `main_c`、
生成出的 `main_c`、落盘的 `main.c` **三份逐字节相等**（评审指出"只有源码正则、
证不了两次渲染真的同字节"，已补）。另有 `test_generate_with_a_custom_device_is_not_a_400`
盯生成端点本身（见下面评审整改第 1 条）。

### code-review 两轴结论与整改

**Standards 轴**（5 硬违规 / 4 判断项）——**5 条硬违规全部整改**：

1. **`_custom_devices_for` 自述与实现不符**：自述"只读选中的那几件、不扫整个数据
   目录"，实现却全目录 `list_devices()`（无关的坏条目会让整页 400），而后面的
   `if slug in known` 又静默丢弃已删 / 读不出的选中件。→ 改成**逐件读选中那几件**
   （坏 / 缺都点名报错），自述与实现对齐，"静默丢弃"也一并消失。
2. **自建件 include 漏了通用批**（评审实测复现）：用户自己把 `i2c_probe` 选上时，
   产物印**两行** `#include "i2c_probe_stm32.h"`——违反本文件明文那条"撞名时不再印
   第二遍"。→ `skip` 补上通用批（`generic_headers` 提成变量）。
3. **"三档文案单源"的声明不成立**：`_plan_for` 的 `PLAN_*` 与产物渲染里那几句是两份
   字面量。→ 把两者的关系写清（页面读 `plan`；产物里那几句由 `_TROUBLE_*` 与
   `ping_trouble` 常量承担），并**把复制的那句判定收成一个常量**（见判断项）。
4. **用例抄了一份接口名单 + 恒真断言**：用例顶部的 `READ_SIDE` 与它自己"不在这里抄
   一份名单"的自述相反；`... or True` / `is not None` 是摆设。→ 用例改成**从真头文件
   现解析**接口名再比调用集；两处恒真断言换成真判据（形态① vs 形态③ 的按需渲染对照）。
5. **新域词没进 `CONTEXT.md`**（workflow 明文要求"术语定下就更新"）。→ 新增
   「我的器件（自建件 / 库外件）」词条，并在「硬件检测」词条节点名 `hwcheck_custom.py`
   与 `generation_slugs` 那条判据。

判断项里**当场收掉 4 条**：`HwcheckProbeSlug` / `custom_section_ids`（重构后零引用的
死件）、`_recipe_runtime(needs_hex=…)` 那个从不读的参数、判定句复制粘贴（失败支与
通过支各写一份同一句话 → 收成 `ping_trouble` 常量）、`needs_hex` 隔层读
`section.device.register` 的 Feature Envy（→ `CustomSection.reads_register`）。
**留 1 条不改**：三档分档在 `my_devices.echo_only` / `_plan_for` / 渲染分支 / `needs_hex`
四处各写一遍——收成 `CustomDevice.shape` 要动工单 02 已 resolved 的域模型，而 04
（mspm0 分支）落地时这几处会自然收口，留到那时一起做。

**Spec 轴**（缺失 3 / 蔓延 1 / 实现不对 5）——**真缺陷 2 条已修**：

1. **🔴 `generate` 端点选了自建件会 400（最重的一条）**：`webapp.py` 仍传
   `slugs=hwcheck_modules(config)`——那个集合含 `mine_*`，于是自建件被当成模块送进
   生成链、在 `resolve_dependencies` 抛「库中不存在模块」；而**预览走视图的局部
   manifests 所以照样 200**。这正是 `tests/test_hwcheck.py` 那条"预览 200 / 生成 400
   不许分家"要灭的事，本单第一版又踩了一次。→ `HwCheckView` 新增
   **`generation_slugs`**（生成端点吃它：自建件已摘、`i2c_probe` 已补），并补两条
   **行为**判据（见上「验收第 6 条」那节）。
2. **🔴 用户自由文本原样进 C 注释**：备注里一个 `*/` 就把注释提前闭合、整份产物变成
   语法错误（`手册写的 0x68 */` 是很自然的输入）；换行会让注释行错位。→ 新增
   `_comment_text` 消毒（终结序列 / 换行 / 控制字符 → 空白 + 收白 + 截断），补用例 +
   反证探针（`probe-03b-sanitize-strength.txt`）。
3. **编译探针手推 slugs**（= 第二个真相源，与它"走真路径"的自述矛盾）：→ 改成吃
   `view.generation_slugs`；并补 `mixed-library` 那格（库内件 + 自建件同趟——三个按需
   渲染开关的交点）。
4. **验收第 6 条只有源码正则判据**：→ 补行为判据（三份 `main_c` 逐字节相等）。
5. **`board["custom"]` 载荷与 `plan` 前端零消费** → **判定为"05 的活，本单不删"**：
   spec 把"检测页的接线说明 / 清单 / 顺序 / 标注"整块派给 05；本单把文案单源
   （`plan` / `tag_text` / 三档说明）先算好下发，05 直接渲染即可——删了它 05 还要再
   算一遍，那正是 spec 反对的"两个判据来源"。工单第 2 条那条勾**按实情重述**：
   本单交付的是"**文案单源 + 产物注释与三档语义一致**"，把这三档在页面上**显示出来**
   是 05 的事（`board["custom"]` 就是它的输入契约）。范围蔓延那条同此判定。

### 两处实施时定的口径

1. **`hwcheck_view` 的接口从"id 集"换成"数据目录"**（02 的 `custom_device_ids`
   是过渡形态）：`data_dir` 是一个参数、一个真相源，`hwcheck_custom` 只管"定义 →
   C 语句"、`my_devices` 只管"盘上有什么"，两边都不必知道对方的存在。顺带把
   02 留下的 `webapp._my_device_ids()` 中转件删了（那是"取 id 只为传下去"的中间人）。
2. **`i2c_probe` 由 `hwcheck_view` 自动加进模块集**（只在真有自建件小节时，且只加
   一次）：探测代码调它的接口，而生成门禁要求"调的函数在被选模块头里真实存在"，
   mspm0 上更是硬要求。页面上不显示"你选了 i2c_probe"——它不是用户选的器件，
   是这一趟的支点。
   ⚠ **同时摘掉的是"选中的自建件全体"**，不只是"出了小节"的那几件：非 I2C 件与
   "没勾输出通道"的形态不出小节，但它们**仍然不是模块**，漏摘一件就会在
   `resolve_dependencies` 那里报「库中没有这个模块」（本单实测踩到，已补用例）。

### 范围外 / 留给后面的工单

- **mspm0 那一支**与两平台编译矩阵 = 工单 04（本单的渲染产物**平台无关**：两平台
  `i2c_probe` 接口同名同语义，差异只有头文件名，已由 `custom_headers` 一处收口）。
- **检测页的接线说明 / 上板清单 / 顺序 / 标注** = 工单 05。载荷里的 `custom` 键
  （含 `tag_text` / `plan` / `address_text` 与三种形态文案）本单已经下发，但
  **页面还没渲染它**——那是 05 的活（本单只管"页面上说的与板上做的一致"这条
  文案单源：`plan` 由本模块产出，页面照抄即可，不必再写一份）。
- **串口复测命令** = 06；**资料上传与草稿** = 07；**工程内快照与回读** = 08；
  **AI 排障带自建件事实** = 09。
- **未上板**：本单只证"能编译、0 warning"与"产物形态对"；器件真能应答要等真机
  （spec 的真机口径：没跑过就写未上板）。
