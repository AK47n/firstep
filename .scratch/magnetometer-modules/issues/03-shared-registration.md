# 03 — 共有件注册：INSTANCE_CONSUMERS + wordlist + 引脚表/白名单同步

**要做什么：** 让两件新模块**真正接入生成器与选型链路**：syscfg 裁剪认识新实例（否则 mspm0 工程里实例被当噪音删掉/保留错）、选型词表能搜到「电子罗盘/磁力计」、默认脚重叠被引脚表与白名单如实登记（否则 `test_pins`/`test_default_layout`/`test_pin_bindings` 红）。做完这单，全量 pytest 绿。

**被谁阻塞：** 01、02（两件的实例名与默认脚定稿后才好登记）。

**状态：** resolved

- [x] `src/contest_generator/syscfg_instances.py` 的 `INSTANCE_CONSUMERS` 新增 `"HMC5883L": ("hmc5883l",)` 与 `"QMC5883L": ("qmc5883l",)`
- [x] `wordlist.json` 就近分类补录两件（电子罗盘/磁力计需求词；两件互写互替说明；不新增重复方案）
- [x] `tests/test_pins.py::MSPM0_DEFAULT_MAP` 登记两件默认脚
- [x] `tests/test_pin_bindings.py` 刻意重叠表登记：`hmc5883l`×(aht10,pca9685) 于 PB6/PB7、`qmc5883l`×bmp180 于 PA23/PA24
- [x] `tests/test_default_layout.py` 软 I2C 总线共享组登记（stm32 PA6/PA7 白名单新增两件）+ mspm0 侧重叠断言按新事实更新
- [x] `tests/test_syscfg_prune.py` 覆盖新实例的裁剪行为
- [x] **全量 pytest 绿**（`python -m pytest -q`，无失败无新增 skip）

**结论（工单 03 已 resolved，2026-09-12）**：`syscfg_instances.py` 登记 HMC5883L/QMC5883L 两实例；`wordlist.json` 给既有「磁力计指南针（HMC/QMC）」两条方案挂 lib_modules 并改写 note；`reference_library.MODULE_PERIPHERAL_TERMS` 两件映射到既有「姿态」词项（参考库无磁力计条目，改用最近类别）；`tests/test_pins.py`、`test_pin_bindings.py`（两处计数表）、`test_default_layout.py`、`test_mspm0_default_layout.py` 白名单同步。**另修一处守卫误判**：`test_lckfb_attribution.py` 新增非 wiki 来源豁免登记（数据手册派生代码不受「来源块 = wiki 页」约束）+ 反向自守用例。全量 pytest 4226 passed。
