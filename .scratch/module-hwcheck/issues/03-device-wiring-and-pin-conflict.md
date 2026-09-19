# 03 — 器件选择 + 接线表 + 默认脚冲突预警

**要做什么：** 在检测页选上器件（例：MPU6050 + OLED + LED）后，直接看到「这几根线各接哪里」的接线行与**默认脚冲突预警**（含地猛星 MPU6050 的 I2C0 = PA0/PA1 与板载 LED 同脚这类暗雷），以及建议的检测顺序（先确认板子活着，再测器件）。

**被谁阻塞：** 01（栏目骨架）。

**状态：** resolved

- [x] 器件选择复用模块库既有载荷与卡片/chip 渲染，不另造一套模块清单协议
      （挑选面 = `GET /api/modules` 既有载荷 + `moduleGridHTML` 卡片（含搜索与「需切换平台」标记）
      + `recommendChipHTML` chip（✕ 移除 + 内嵌「说明」按钮，说明走既有 `bindModuleInfoEntry` 委托）；
      页面只发 slug，器件对象由服务端现读库——前端不把自己那份缓存当判据）
- [x] 接线行与生成工程 README 的引脚接线表**同一判据单源**（同函数、同字段；不允许两处各推一遍）
      （行本体 = `wiring.wiring_rows`（= README `_pin_row_items` 同一推导入参），只多一列 `pin_note`；
      机器判据两条：`test_rows_match_the_readme_pin_table_cell_by_cell`（与真渲染的 README 解析回来逐格相等）
      与 `test_rows_are_the_wiring_snapshot_projection_verbatim`；端到端在 `test_generate_wiring_rows_equal_the_generated_readme_pin_table`，
      真机证据 ③a「README 5 行 vs 载荷 5 行」逐格相等）
- [x] 同脚冲突 / 合法共享按既有分类规则判定（同一 I2C 总线 = 合法共享；同脚分属不同外设 = 物理冲突，标 ⚠）；
      地猛星 MPU6050 × 板载 LED 的默认脚重叠**必须被如实呈现**
      （组 = `pin_bindings._shared_groups` 原样透传，前端只上色；PA0/PA1 的板载 LED 同脚走**板上共享**一列
      （板定义 `BoardPin.notes` 归并）——`_shared_groups` 只看模块角色、看不见板子自己接好的东西，
      见 Comments「评审整改」①。真机 `verify-03-real-machine.txt` ①b/①d）
- [x] 未声明引脚角色的模块不产生接线行（与 README 行为一致）
      （`test_modules_without_declared_pins_produce_no_rows`：stm32 的 led / delay 实现内嵌母版、无 pins 声明）
- [x] 建议顺序复用既有 bring-up 顺序单源（不在此另立），并在页面显式展示"建议按这个次序测"的理由
      （排序 = `readme.sort_verification_order`，`bring_up` 标记 = `readme.BRING_UP_SLUGS`，
      引导语 = `readme.VERIFICATION_GUIDE`，尾注 = `readme.PIN_TABLE_FOOTNOTE`，
      「为什么是这个次序」= `hwcheck_board.HWCHECK_ORDER_REASON`；机器判据逐项比对排序函数输出）
- [x] 选择的器件在**本平台没有条目**时不静默省略：明确提示"该模块无本平台版本，无法检测"
      （判据 = `selection.check_platform_warnings` 的 missing 一类，文案 `hwcheck_missing_message`；
      预览 / 生成 / 回读三个端点都带 `wiring.missing`；真机 ②：stm32 上选只有 mspm0 条目的 sr04 被点名）
- [x] 前端渲染是 fx 纯函数并有单测（接线行 / 冲突标记 / 顺序文案三块）
      （`hwcheckWiringTableHTML` / `hwcheckPinGroupsHTML` + `hwcheckBoardSharesHTML` / `hwcheckOrderHTML`
      （+`hwcheckOrderDesc` 截断） / `hwcheckMissingDevicesHTML` / `hwcheckDeviceChipsHTML` / `hwcheckDevicePick`；
      `tests/js/hwcheck.test.mjs` ⑤ 段逐块覆盖，`fx-guard` 登记 14 个新导出）

## 边界与决策引用

- 冲突判定口径见领域词表「引脚绑定」「引脚容量」；本单**只做预警**，不新增拦截。
- 顺序判据复用生成 README 里已有的 bring-up 顺序（spec「板上行为与判据」）。


## Comments

### 开工前的接线判断（读完既有件之后：哪些直接用、哪些不重造）

| 既有件 | 判断 | 落点 |
|---|---|---|
| `wiring.wiring_rows`（接线快照行的结构化投影，与 README「引脚接线表」同一推导 `readme._pin_row_items`） | **直接用**：页面接线行 = 这个函数的输出（只补一列板上注记） | `hwcheck_board.py`（新建） |
| `pin_bindings._shared_groups`（同脚多角色的 share / conflict 分类，工单 pin-share-rule/01） | **直接用**：冲突 / 合法共享一行判据都不新立；它是私有名，但 `pin_capacity` 已有同样用法 | 同上 |
| `readme.sort_verification_order` / `BRING_UP_SLUGS` / `VERIFICATION_GUIDE` / `PIN_TABLE_FOOTNOTE` | **直接用**：建议顺序、引导语、尾注与工程 README 同源 | 同上 |
| `selection.check_platform_warnings`（平台警告表，missing 一类） | **直接用**：缺平台条目的判据（与生成侧同一处），文案归检测页 | 同上 |
| `library.MODULE_KIND`（`/api/modules` 投影为 `kind` / `requires_identity`） | **不用它过滤挑选面**（见「评审整改」②）：它分的是"要不要购买链接"，不是"能不能上板测" | 挑选面不过滤 |
| `moduleGridHTML` / `recommendChipHTML`（fx/module.js） | **直接用**：器件挑选的卡片与 chip 渲染（票面要求「不另造一套模块清单协议」） | `fx/hwcheck.js` + `ui/hwcheck.js` |
| `bindModuleInfoEntry`（推荐 chip 的说明按钮委托，捕获阶段拦） | **扩一个可选参数** `platformOf`：检测页有自己的平台选择（既有调用点零变化） | `ui/generate-recommend.js` |
| `hwcheck_store.read_hwcheck_project` / `context_manifest` | 加 `devices`（可选字段）与回读——器件选择**不能**从 slugs 反推 | 见下 |

### 三个设计决策（都写进了代码注释）

1. **器件进模块集**（`hwcheck_modules` = 框架 ∪ 通道 ∪ 器件）：页面接线表要与工程 README 同源，前提是两边
   的模块集是同一个。先量后写：`.scratch/module-hwcheck/probe-03-generate-with-devices.py` 先跑了四组
   （stm32/mspm0 × ml_mpu6050 / hmc5883l / sr04），确认器件会被生成门禁吃下去，再动手写 UI。
2. **上下文清单新增可选 `devices` 字段**（写侧不传 = 键不出现 → 赛题工程清单逐字节不变）：
   slugs 是依赖展开后的完整集合，分不出"用户选的器件"与"它的依赖"（如 `xunji` 与它带进来的 `motor`），
   所以器件选择必须单独记一份——否则回读后 chip 与接线表对不上。
3. **检测程序这一版还不测器件**（配方归 04、探头归 05）：器件只进工程 + 进接线表，检测页那句
   「逐件的检测小节与板上通断判定还在做」是刻意写的——不假装测过（spec 判据）。

### 测试缝（沿用票面约定的最高既有缝）

- 域层纯函数（`hwcheck_board.hwcheck_board_view`：内存直测，真库真板数据）——23 条。
- 端点：`TestClient` + 真库真母版（preview / generate / project 三个端点收发行器件与板侧视图）——9 条新增。
- 前端：`tests/js/hwcheck.test.mjs` ⑤⑥ 两段（fx 纯函数 + 接线守卫），`fx-guard` 登记新导出。
- 真机：`tests/browser/hwcheck.spec.mjs`（真浏览器 + 真后端 + 真 UV4，6/6）+ `.scratch/module-hwcheck/verify-03-real-machine.py`（走产品端点，9 条判据全 PASS）。

## 实施结果与证据（都在 `.scratch/module-hwcheck/`）

| 证据文件 | 内容 | 结论 |
|---|---|---|
| `probe-03-generate-with-devices.py` | 写代码**之前**的前置探针：器件进模块集能否过生成门禁（两平台 × 四组） | 四组全过（真库真母版真内核） |
| `verify-03-real-machine.txt` | 走产品端点：接线行 / 同脚组 / 板载共享 / 顺序 / 缺条目 / README 逐格对比 / 回读 | **9 条判据全 PASS，判红 0** |
| `verify-03-suite.txt` | 全量 `python -m pytest -n auto` | **4726 passed / 1 skipped**（101s） |
| `verify-03-js-suite.txt` | 完整前端门禁 `node --test "tests/js/*.test.mjs"` | **1628 passed / 0 failed** |
| `verify-03-browser.txt` | `node --test tests/browser/hwcheck.spec.mjs`（真 chromium + 8791 真后端 + 真 UV4） | **6/6**：选 MPU6050 → 接线表带 PA0/PA1 与板载共享 + 冲突区标 ⚠ PA22 + 板上共享单独成条 + 顺序把器件排最后 + 去掉器件页面跟着变；stm32 选 sr04 → 点名「无本平台版本」 |
| `negative-verify-03.py` / `.txt` | 判据强度探针：14 条注入（行不再照抄快照推导 / 板上注记被丢 / 冲突被抹平 / 顺序不走既有排序 / 缺条目判据被掐 / 回读不取器件 / 清单不落器件 / 器件不进模块集 / ⚠ 标记抹平 / 板载共享不渲染 / 载荷不带器件 / 板载共享不投影 / 在途触发不排队） | **14/14 注入后对应用例变红**，文件逐字节复原 |

## 双轴评审与整改（Standards + Spec，基线 `ad082c37` 未提交工作区）

两轴并行子代理评审，**结论已逐条处置**：

**Standards 轴：0 条硬违规 + 5 条判断题**
| # | 意见 | 处置 |
|---|---|---|
| S1 | Duplicated Code：「保序去重」在 `hwcheck_devices` / `_missing_devices` / 两处 fx 各写一遍 | **已修**（Python 侧）：新增 `hwcheck.dedup_slugs` 单源，`hwcheck_devices` 与 `_missing_devices` 都调它。fx 那两处是跨语言镜像（`hwcheckDevicePick` 改选中 / `hwcheckDeviceSlugs` 出载荷），语义不同、JS 也 import 不到 Python，保留 |
| S2 | Divergent Change：回读端点先 `read_hwcheck_project` 再 `read_context_fields` 读第二遍；slugs 归一在路由、devices 归一在读侧 | **已修**：板侧视图改按 `hwcheck_modules(config)` 投影（依赖展开由 `hwcheck_board` 做，结果与工程 slugs 同一集合）——第二遍读盘与路由里的项级归一一起消失，`_hwcheck_wiring` 也不再收 `slugs` |
| S3 | **过期响应**（CONTEXT.md「展开收口」先例）：`refreshHwcheckView` 无令牌无排队，而响应会回写 `devices`——连点两件器件时慢响应会把刚选的抹掉 | **已修**（本单最值得修的一条）：在途触发记 `hwcheckViewPending` 收尾重跑；落地前比请求体快照（选择集变了 = 结果属于旧选择，不写状态）；失败只清板侧视图不清 main.c。新增静态守卫用例钉住三条纪律 |
| S4 | 残留双检：`if platform not in KNOWN_PLATFORMS: require_known_platform(platform)` | **已修**：直接调 `require_known_platform`，`KNOWN_PLATFORMS` 导入随之删掉 |
| S5 | `hwcheckDevicePick` 重复选中会把该件挪到末尾 | **已修**：改成幂等（已选再点 = no-op，状态原样返回），用例同步 |

**Spec 轴：4 条缺失 / 越界 / 实现有误**
| # | 意见 | 处置 |
|---|---|---|
| a① | 工单仍 claimed、验收未勾、无 Comments（02 同款曾被评） | **已办**：验收 7 条全勾 + `Status: resolved` + 本节 |
| a② | **暗雷半做**：板载 LED 同脚只在接线行的注记里；同脚组走 `_shared_groups`（只算模块角色），只选 MPU6050 时冲突区反输出「✓ 没有共用同一个引脚」= 假安心 | **已修**：新增板侧视图 `board_shares` 一列（板定义注记归并：脚 + 注记 + 用到它的角色），冲突区单独成条「⚠ 板上共享（原厂就这么接的，不是接线错误）」；空集那句话改成「没有**两件模块**抢同一个引脚（板上自带的共享另见下一条）」；真机 ①d 与浏览器用例都钉住 |
| b③ | 器件池按 `requires_identity` 过滤是**自定口径**：spec 的 v1 专精清单里 `adc` 属 internal，被过滤后永远选不到 | **已修**：挑选面 = 模块库全量（与模块库页同一份，票面只要求"复用既有载荷与卡片"）；顺带发现 stm32 侧更值钱的事实——MPU6050 默认脚 PA11/PA12 是 **USB D+/D-**，注记现在也会被列出来 |
| c④ | `refreshHwcheckView` 失败即清 preview：库未配置时接线表 400 会连坐抹掉工单 02 已交付的预览 | **已修**：失败只清板侧视图（main.c 只依赖平台与通道，换平台 / 换通道那两处本来就会清），新增守卫用例数「清预览」的处数恰好为 2 |
| 记账 | 范围蔓延两条：`devices` 落进上下文清单（spec 只写「加一个 kind 字段」）、`bindModuleInfoEntry` 签名扩展 | **保留并说明**：前者是回读的唯一办法（决策 2）；后者是可选参数、既有调用点零变化，且避免在检测页再抄一遍"捕获阶段拦"的坑 |

**未修但记账**：检测页的引脚配置 / 自动配置（把 ⚠ 变成可改绑）、mspm0 的 SysConfig 初始化注入、
逐件检测小节与探头——都归后续工单（spec 用户故事 3 的完整解、04 / 05）。
