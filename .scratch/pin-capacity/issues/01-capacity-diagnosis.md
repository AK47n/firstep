# 01 — 引脚容量诊断与门禁数字段

**要做什么：** 用户在生成页选出一组模块、默认脚互相撞上、`/api/generate` 被
`syscfg_pin_conflicts` 门禁拦下时，那条 400 中文里除逐脚清单之外，还要能看到可操作数字：
选中集规模与落点数、板上可用 IO 与占用/空闲、门禁发现几组冲突、一键配置解开几组还剩几组、
以及（无解时）至少要去掉几个模块。三种降级形态（板数据缺失 / 产物复核 / 非 mspm0）文案与
现状逐字一致。**只加文案，不加拦截，不动前端。**

**被谁阻塞：** 无——可立即开始。

**状态：** ready-for-agent

- [ ] 新增域模块 `pin_capacity.py`（命名严守「引脚容量」，**不得**出现裸「预算」二字）：
      `PinCapacityReport`（冻结）+ `diagnose_pin_capacity(manifests, platform, board,
      bindings)` + `render_pin_capacity_diagnosis(report)`；判定量**只**复用
      `pin_bindings._role_entries`（落点与占用脚）与
      `auto_assign_bindings(..., resolve_default_conflicts=True)` 的 `shared` 中
      `kind == "conflict"` 剩余组（可解性），板上可用 IO = `board.pins` 里
      `capabilities` 非空的脚数——不新造判据、不复制判定代码。
- [ ] 报告「至少要去掉 N 个模块」的 N = 剩余无解冲突组内**可让位模块的并集**大小（保序
      去重），文案须显式标注这是**下界**（不声称精确最小值，不用任何推算冒充）。
- [ ] 三条口径落地（用户拍板）：① 可用 IO = 整板可用脚，另报占用 / 剩余空闲；② 以 solver
      剩余组为准，落点数只作**上界**背景并注明「合法共享会省脚」；③ 落点 ≤ 可用脚却仍无解
      → 另起一句「与引脚数量无关，卡在能力/实例分配，须去掉或替换冲突模块」。
- [ ] `_check_syscfg_pin_conflicts` 只在 `raise` 前调用诊断器：把渲染段插在逐脚清单与
      「出路：」之间。触发条件、`by_pin`/`conflicts` 判定、逐脚清单排序**一行不改**；
      新段**不得**使用 `"<PIN>："` 形态（否则污染既有用例
      `message.count(f"{pin}：") == 7` 的逐脚计数）。
- [ ] 新用例 1（回归守卫，钉死真机口径）：`2026H` 13 模块集（12 选中 + 依赖展开，即
      `k230, coord_detect, uart, key, huidu, pid, motor, l298n, oled, ntb_time, servo,
      imu_uart`）→ 报告字段 `modules == 13`、`slots == 42`、`occupied == 27`、
      `board_io == 31`、`conflict_groups == 7`、`unresolved == 3`；文案含「42」「31」「27」
      与三个无解角色对 `oled.OLED_SPI_SDA` / `motor.BIN2` / `motor.BIN1`。
- [ ] 新用例 2（反向守卫，防到处加数字）：只选 `motor` + `servo` → 报告 `board_io == 31`
      且 `unresolved == 0`；文案说「可用自动配置解开」，**不得**出现「至少要去掉」。
- [ ] 新用例 3（降级逐字不变）：`GateContext()`（无板无绑定）与 `manifests == []`（产物复核
      形态）两种输入 → 400 文案与改动前逐字一致、不含容量段；`PLATFORM_STM32` 直过照旧
      （既有用例已钉，不动）。
- [ ] **既有用例零修改**（`tests/test_generator.py` 的 `test_syscfg_pin_conflicts_*` 系列、
      `tests/test_errors.py`）全绿；`python -m pytest -q` 与 `node --test tests/js/*.test.mjs`
      相对本单基线只增不减；`mypy` 改动文件零问题。
- [ ] 改动面写死：`webapp.py` / `static/` / `/api/bindings/auto` 契约 / `docs/adr/0010` /
      门禁表 `GENERATION_GATES` 顺序 **零改动**。
- [ ] 实测并记录一次门禁耗时（真机 13 模块集，诊断前后对照），确认增量可接受（诊断只在
      即将抛错的路径上跑）。
