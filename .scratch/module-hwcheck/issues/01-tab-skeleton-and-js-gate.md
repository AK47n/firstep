# 01 — 栏目贯通骨架 + 前端测试门禁接通

**要做什么：** 导航里出现新栏目「硬件检测」（放在「做题」组第 2 位，紧跟「生成」），点开能选平台、点「预览检测程序」拿到**零器件最小自检**的 main.c 文本（LED 心跳 + 输出通道自报 + 结尾汇总），全程零 LLM、零配方。同时把前端测试接进闸门：推之前的本地闸门在改动命中前端文件时真的会跑前端用例（`node --test "tests/js/*.test.mjs"`——见下方 Comments 的口径说明），CI 同样加一步——本单先接通，后面每一单都受益。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

- [x] 导航按钮、面板、三处注册（静态 import / 启动调用 / 切换时懒加载）齐备，ARIA 与 title 满足既有 parity 守卫；两处守卫文件（键表 + 分组表）已同步
- [x] 栏目内可选平台（stm32 / mspm0），默认继承全局当前平台，但**不依赖**生成流程任何状态（不要求题面、不要求已选模块）
- [x] 「预览检测程序」调新端点 → 文本区显示最小自检 main.c；心跳段与输出通道自报段存在且可断言
- [x] 域层渲染是纯函数（字符串进 / 字符串出），单测覆盖三种通道形态：只有 debug_uart / 只有 oled / 两者都没有（此时只闪灯 + 页面明示"没有输出通道，只能看灯闪"，**不报错阻断**）
- [x] 两个通道都没有时不产生任何打印调用（结构断言，防"假装测过"）
- [x] 本地闸门：改动命中前端文件时会跑前端用例；**红证** = 故意删一个导航键 → 推送被拦并点名失败用例
- [x] CI 增加前端测试步骤，且不联网、不吃 secret
- [x] 反向验证证据：停用任一新增守卫 → 对应用例变红（记录在 Comments）

## 边界与决策引用

- 检测程序**渲染零 LLM**（spec「检测程序怎么来」）；本单只做框架，不碰配方。
- 顺序判据复用既有 bring-up 顺序单源（本单用不到，05 之后才会体现，但不要在此自造一套）。
- 命名：栏目名「硬件检测」、tab key `hwcheck`、域模块 `hwcheck.py`、异常 `HwCheckError`（→400）。
- spec 里「CONTEXT 词条」与「新写一条 ADR」属**工单 09 的收尾项**（09 验收栏明列这两条），
  本单只在 `hwcheck.py` 头注释里注明"ADR 待写"——不留指向不存在文档的悬空编号。

## Comments

**测试口径的一处偏离（有意，已落文档）**：票面写的是 `node --test tests/js`。本机
Node v24.15.0 实测**目录形式根本跑不起来**（node 把目录当模块解析：
`Error: Cannot find module '...\tests\js'`），`node --test tests/js/` 同样失败。故
实际命令 = `node --test "tests/js/*.test.mjs"`（glob 位置参数需 Node ≥21；CI 用
`setup-node` 钉 22）。本地闸门为兼容 Node 20（不认 glob 位置参数）改为**在
Python 侧展开文件清单**后传给 node（`tools/prepush.py: js_test_files`）。
口径已写进 `docs/agents/workflow.md`「闸门」一节与
`docs/agents/local-environment.md` §2.5d。

**红证（故意删一个导航键 → 推送被拦并点名失败用例）**：
1. 删掉 `index.html` 里 `data-tab="hwcheck"` 那颗按钮；
2. `python tools/prepush.py --changed src/contest_generator/static/index.html` →
   `[prepush] 改动 1 个文件 → 整套 pytest + 前端门禁（tests/js/*.test.mjs）`，
   前端门禁退出非 0，**prepush 退出码 = 1（推送会被拒）**，并点名 4 条失败用例：
   - `✖ tab 按钮 ARIA：role=tab + aria-selected + aria-controls + roving tabindex`
   - `✖ 12 个 tab 键在顶部导航内各恰好一次，无多余/缺失`
   - `✖ 组归属与组内顺序：做题 5 个、资料管理 5 个、指南 2 个，无串组`
   - `✖ tab 按钮 title 覆盖：12 个均有非空中文 title（长度 ≥8）`
   同一次运行的 pytest 面**全绿**（4620 passed）——正是"pytest 看不见前端"的实证：
   没有这道门禁，这次破坏会一路推到用户机上。
3. 恢复按钮 → 前端用例 `1588 passed / 0 failed`（全量 pytest 亦全绿）。

**反向验证（停用新增守卫 → 变红）**：
- 停用「两通道都没有 → 不产生打印调用」的结构断言（把 `render_main_c` 改成无条件
  渲染打印）：`tests/test_hwcheck.py` 的 `test_no_channel_renders_no_print_call_at_all`
  与 `test_header_comment_matches_the_form_it_renders` 当场红。
- 停用导航守卫的组首白名单（把白名单加长成含组内第二颗，或把某组首 `tabindex` 改回
  `-1`）：`nav-tabs-guard.test.mjs` 的「组首白名单…」与「tab 按钮 ARIA…」两条红。
- 停用前端门禁的 js 标志（把 `select_tests` 里 `js` 判断改回"循环内累加"）：
  `tests/test_js_gate.py::test_frontend_gate_survives_a_full_fallback_in_the_same_change`
  的 4 个参数化用例全红——这条正是评审抓出来的真缺陷（改动顺序里先公共面/后前端文件
  时，提前 return 把前端门禁整个吞掉）。

**双轴评审整改**（Standards + Spec 两轴，见提交信息）：
① `select_tests` 的顺序相关静默跳过（真缺陷，已修 + 回归用例）；
② `ui/hwcheck.js` 手拼 fx 已提供的产物区壳（双源 + 丢 esc）→ 改走
`hwcheckPanelHTML`/`hwcheckCodeTarget` 单源，并加"ui 不得手拼该壳"的守卫；
③ 悬空 ADR 引用 → 改为"ADR 待写，见工单 09"；
④ `node --test` 目录形式的口径矛盾 → 统一为 glob / 展开清单，文档同步；
⑤ CI 未钉 node 版本 → `setup-node@22` + 守卫用例；
⑥ 零通道形态的文件头自述与产物矛盾（自称"结果写到输出通道"却一个打印都没有）
→ 文件头按形态生成 + 守卫用例；
⑦ 测试自称"不手写函数名清单"却手写白名单 → 改为读**真实库内头文件**判据
（`library/modules/{delay,debug_uart,oled,led}` + stm32 母版 `ml_libs/`），
母版外部事实白名单逐条给出处并用例核对；
⑧ 「组首白名单」用例自比自 → 改为对**标记**判定（导航里 `tabindex=0` 的按钮数
必须恰好等于组数）。
