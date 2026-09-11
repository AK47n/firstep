# 01 — 引脚容量诊断与门禁数字段

**要做什么：** 用户在生成页选出一组模块、默认脚互相撞上、`/api/generate` 被
`syscfg_pin_conflicts` 门禁拦下时，那条 400 中文里除逐脚清单之外，还要能看到可操作数字：
选中集规模与落点数、板上可用 IO 与占用/空闲、门禁发现几组冲突、一键配置解开几组还剩几组、
以及（无解时）至少要去掉几个模块。三种降级形态（板数据缺失 / 产物复核 / 非 mspm0）文案与
现状逐字一致。**只加文案，不加拦截，不动前端。**

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

- [x] 新增域模块 `pin_capacity.py`（命名严守「引脚容量」，**不得**出现裸「预算」二字）：
      `PinCapacityReport`（冻结）+ `diagnose_pin_capacity(manifests, platform, board,
      bindings)` + `render_pin_capacity_diagnosis(report)`；判定量**只**复用
      `pin_bindings._role_entries`（落点与占用脚）与
      `auto_assign_bindings(..., resolve_default_conflicts=True)` 的 `shared` 中
      `kind == "conflict"` 剩余组（可解性），板上可用 IO = `board.pins` 里
      `capabilities` 非空的脚数——不新造判据、不复制判定代码。
- [x] 报告「至少要去掉 N 个模块」的 N = **剩余无解冲突组的组数**（每个无解组至少去掉一方
      = 下界），冲突模块清单 = 这些组涉及模块的并集（保序去重）；文案须显式标注这是**下界**
      （不声称精确最小值，不用任何推算冒充）。
- [x] 三条口径落地（用户拍板）：① 可用 IO = 整板可用脚，另报占用 / 剩余空闲；② 以 solver
      剩余组为准，落点数只作**上界**背景并注明「合法共享会省脚」；③ 落点 ≤ 可用脚却仍无解
      → 另起一句「与引脚数量无关，卡在能力/实例分配，须去掉或替换冲突模块」。
- [x] `_check_syscfg_pin_conflicts` 只在 `raise` 前调用诊断器：把渲染段插在逐脚清单与
      「出路：」之间。触发条件、`by_pin`/`conflicts` 判定、逐脚清单排序**一行不改**；
      新段**不得**使用 `"<PIN>："` 形态（否则污染既有用例
      `message.count(f"{pin}：") == 7` 的逐脚计数）。
- [x] 新用例 1（回归守卫，钉死真机口径）：`2026H` 13 模块集（12 选中 + 依赖展开，即
      `k230, coord_detect, uart, key, huidu, pid, motor, l298n, oled, ntb_time, servo,
      imu_uart`）→ 报告字段 `modules == 13`、`slots == 42`、`occupied == 27`、
      `board_io == 31`、`conflict_groups == 7`、`unresolved == 3`；文案含「42」「31」「27」
      与三个无解角色对 `oled.OLED_SPI_SDA` / `motor.BIN2` / `motor.BIN1`。
      （落实形态：断言全部落在门禁 400 文案上——数字先由探针独立现算，再在门禁缝上逐条
      命中；钉死的是**角色对与剩余组数**，模块清单只断言确在剩余组里出现过的模块。）
- [x] 新用例 2（反向守卫，防到处加数字）：只选 `motor` + `servo` → 报告 `board_io == 31`
      且 `unresolved == 0`；文案说「可用自动配置解开」，**不得**出现「至少要去掉」。
- [x] 新用例 3（降级逐字不变）：`GateContext()`（无板无绑定）与 `manifests == []`（产物复核
      形态）两种输入 → 400 文案与改动前逐字一致、不含容量段；`PLATFORM_STM32` 直过照旧
      （既有用例已钉，不动）。
- [x] **既有用例零修改**（`tests/test_generator.py` 的 `test_syscfg_pin_conflicts_*` 系列、
      `tests/test_errors.py`）全绿；`python -m pytest -q` 与 `node --test tests/js/*.test.mjs`
      相对本单基线只增不减；`mypy` 改动文件零问题。
- [x] 改动面写死：`webapp.py` / `static/` / `/api/bindings/auto` 契约 / `docs/adr/0010` /
      门禁表 `GENERATION_GATES` 顺序 **零改动**。
- [x] 实测并记录一次门禁耗时（真机 13 模块集，诊断前后对照），确认增量可接受（诊断只在
      即将抛错的路径上跑）。

## 落地记录（2026-09-18）

**改动落点**：新增 `src/contest_generator/pin_capacity.py`（域模块）、`tests/test_pin_capacity.py`
（域模块缝 2 条用例）；`pin_bindings.py` 新增 `_group_modules`（组 → 涉及模块，保序去重）；
`generator.py` 门禁在 `raise` 前调诊断器 + 插入渲染段；`tests/test_generator.py` 新增 4 条用例；
`CONTEXT.md` 领域词表补「引脚容量」行。`webapp.py` / `static/` / ADR 0010 / 门禁表顺序 /
`/api/bindings/auto` 契约零改动。

**门禁新文案原文**（三种形态逐字落盘：`msg-2026h.txt` / `msg-motor_servo.txt` /
`msg-motor_servo_noboard.txt`，逐脚清单部分此处省略）：

```
【引脚容量】13 个模块 / 42 个引脚落点（上界：合法共享会少占脚）；地猛星 MSPM0G3507 板载可用 IO 31 脚，本次已占 27 脚、剩余 4 脚。
实测到的 7 组同脚冲突「自动配置」可解开 4 组，剩余 3 组无法靠改绑解开（任一方模块让位即可）：
    · oled.OLED_SPI_SDA × imu_uart.IMU601_RX
    · motor.BIN2 × servo.SERVO_PWM_C0
    · motor.BIN1 × oled.OLED_SPI_CS
解冲突后板上的可用 IO 脚已全被占用（31 脚，一个空闲脚都不剩），而剩余冲突组无法靠改绑解开——该选中集在地猛星 MSPM0G3507上物理不可实现：至少要去掉 3 个模块（冲突模块：oled、imu_uart、motor、servo）。（佐证：引脚落点 42 个 > 板上可用 IO 31 脚；落点含合法共享与没有可落脚默认脚的角色，只是上界。）
```

可解形态（`motor` + `servo`）：

```
【引脚容量】2 个模块 / 11 个引脚落点（上界：合法共享会少占脚）；地猛星 MSPM0G3507 板载可用 IO 31 脚，本次已占 10 脚、剩余 21 脚。
实测到的 1 组同脚冲突「自动配置」都可以解开（会解开 1 组），改绑后剩余空闲 20 脚——不必去掉模块。
```

缺板定义形态与产物复核形态：**逐字等于改动前**（无容量段）。

**实测（`probe-04-gate-timing.py`，只读）**：门禁最快 9.40 ms（未接诊断）→ 11.35 ms
（已接诊断），诊断本身 1.39 ms —— 增量约 2 ms，且只在**即将抛错**的路径上发生。
生成链路可达性：真母版 + 真库 13 模块集调 `generate_project` → `SyscfgPinConflictError`、
**文案带容量段 = True**、**输出目录是否产生 = False**（门禁仍在 `mkdir` 之前拦下）。

**回归（本轮实测）**：`python -m pytest -q` → **4000 passed, 1 warning**（基线 3994 → 净增 6
= 本单新用例 6 条）；`node --test tests/js/*.test.mjs` → **1444 pass / 0 fail**（无 JS 改动）；
`mypy src/contest_generator/{pin_capacity,generator,pin_bindings}.py` → 零问题。

**code-review 双轴发现与处置**（Standards + Spec 各跑一个子代理，固定点 `3ee271a0`）：

| 发现 | 处置 |
|---|---|
| Spec：实施初稿把「冲突模块」照探针写成含 `l298n` 的并集，与门禁让位顺序不符 | 改用例为门禁现算的并集，并把两处差异写进 `probe-03` 的对照说明 |
| Spec：`free_after_moves` 按**角色数**算、`occupied` 按**脚**算，同字段两口径混用 | 统一走 `_occupied_pins`（脚集合），三个字段一致 |
| Spec：`moved` 字段名与渲染「会改动 N 处绑定」把**组**数说成角色数 | 改名 `moved_groups`，文案改「会解开 N 组」 |
| Spec：我把降级断言**追加进既有用例**，违反本单「既有用例零修改」硬约束 | 撤回该行，另立新用例 `test_syscfg_pin_conflicts_no_capacity_numbers_on_output_tree_corpus` |
| Spec：spec 要求的「`pin_capacity` 纯函数直测」未做 | 新增 `tests/test_pin_capacity.py`（假板造出真机样本没有的「脚够却仍无解」形态） |
| Spec：门禁文案把 `report.occupied`（27）说成「已全被占用」——解后占用是 31 | 改为按板上可用 IO 报数，并把硬事实（解后 0 空闲脚）排在落点上界之前 |
| Standards：`CONTEXT.md` 未登记新领域概念 | 词表补「引脚容量」行（含命名纪律：不得用裸「预算」） |
| Standards：`board_io_count` 公开但仅本模块消费 | 收为私有 `_io_pin_count` |
| Standards：两处 else 分支重复整句、`_role_entries` 占用脚集合连写两遍 | 抽 `_headline`/`_occupied_pins`，尾句按「与引脚数量无关 / 无法落地」两种语义各留一处 |
| Standards：`_group_modules` 的 docstring 自述「唯一生产者与消费者」不实 | 重写为「角色键解析归本模块，消费方只拿模块名」 |

**如实记账 1（与探针的一处差异）**：`probe-03-2026h-baseline.py` 让 `l298n.L298N_EN` 挪到
PB8（该脚随后被 `oled.OLED_SPI_SDA` 合法共享），门禁沿用同一求解器则让 `motor.BIN2` 让位
——**剩余 3 组的角色对两处逐条相同**，只有「涉及哪些模块」的并集不同（探针含 `l298n`，门禁
为 `oled、imu_uart、motor、servo`）。两处共用同一求解器，差异只在让位顺序；用例钉死的是
角色对与剩余组数，模块清单只断言「确在剩余组里出现过的模块」。实施初稿照探针写死了
`l298n`，跑门禁当场变红并修正——留档以免下次再照抄探针的并集。

**如实记账 2（口径边界）**：落点数按 `_role_entries` 统计（含没有可落脚的板外默认脚的
角色），而求解器只能重分配「已占用那些脚上的角色」——“落点 ≤ 可用脚”只在两侧都按
`_role_entries` 口径时才被断言成硬界，故文案把它降为**佐证**、把硬事实（改绑后仍有剩余
组 + 一行空脚都不剩）放在前（模块 docstring 与渲染注释都写明了这条纪律）。

**如实记账 3（假板用例的边界）**：`tests/test_pin_capacity.py` 用假板读出「落点 ≤ 可用脚却
仍无解」那一支——真机 14 样本里没有这种形态，属防御支；假板形态**必须显式绑满**才有落点
可言（motor/servo 的声明默认脚不在假板上），且因显式绑定 = 用户明确选择、求解器不搬，
假板用例天然落在 `unresolved` 一侧。
