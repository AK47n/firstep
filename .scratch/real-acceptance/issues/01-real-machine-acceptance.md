# 01 — 真机验收挂账：工具链 / 浏览器 / 真实额度 / 人工取源（集中一张，不再散着重判）

**要做什么：** 把 2026-09-09 在途盘点（`.scratch/tracker-audit/2026-09-09-在途盘点.md`）判定为
**非代码可证**的验收项集中到这一张单里——它们散在约 60 张已完成工单的验收清单里，每轮盘点都要
重新判一次「无法判定」，成本高且噪音大。本单是这些项的唯一收口：**验完一项勾一项**，勾完把对应
来源工单的该项一并收尾即可。

**被谁阻塞：** 无——可立即开始。前置条件（代码侧）已逐项给出证据；缺的是真机硬件 / 工具链 /
浏览器 / 真实 LLM 额度 / 人工取源。

**状态：** ready-for-human

## 怎么用这张单

1. 每项标了 **来源**（原工单）与 **怎么验**（命令或操作步骤）；验完勾选，并在来源工单对应项上补勾。
2. 分六组：A 真机工具链 / B 浏览器与 CDP / C 真实 LLM 与视觉额度 / D 人工取源 / E 干净机器 / F 历史流程项。
3. F 组不是「待办」——是**不可回溯复核**的历史流程项，仅登记以免每轮重判（已给出替代判据）。
4. 本单**不写代码**；若验出真 bug，另开修复工单，本单该项留空并注明。

## A. 真机工具链编译矩阵（11 项）

工具在盘：UV4 `C:\Keil5\Core\UV4\UV4.exe`、gmake `C:\ti\ccs2050\ccs\utils\bin\gmake.exe`、
SysConfig `C:\ti\sysconfig_1.20.0`（探测表 `src/contest_generator/compile_runner.py:56`）。

- [x] **A1 来源 `b1-adc-servo/03`**：adc / servo 绑定场景编译矩阵 0 error 0 warning。
  怎么验：`python .scratch/b1-adc-servo/compile_matrix.py`（四例：default/bound × stm32/mspm0）。
  已就位：`.scratch/b1-adc-servo/compile_matrix.py:78-87` 与生产同闸（`build_output_tree_corpus` + `run_generation_gates`）；
  `tests/test_module_adc.py:138-154`、`tests/test_module_servo.py:125-133`（渲染侧已验）。
  **2026-09-10 第十六轮完成**：4 例全绿（default/bound × stm32/mspm0，exit=0、0 错 0 警、
  门禁同闸全过，3.6~10.1s/例）→ `.scratch/b1-adc-servo/verify-16-compile-matrix.txt`。
  **口径修订（原口径 → 现状 + 理由）**：脚本内 main.c 样例是工单期形态，`servo_init` 在
  b1-adc-servo/02 落地时已定为**双参** `servo_init(servo_id, channel)`
  （`library/modules/servo/code/servo.h:37`，tests/test_module_servo.py:71-73 守卫）——
  首跑真机报 `main.c(7): error: #165: too few arguments`，属**脚本过期**而非产品缺陷；
  已把样例改成与模块头一致并记入脚本 docstring。
- [x] **A2 来源 `compile-experience-ui/01`**：真实工程 + 工具链跑完整编译修复闭环，横幅四态与错误列表实况。
  已就位：`ui/generate-fix.js:65 compileBanner`、`index.html:469-477`、`webapp.py:3944`。
  **2026-09-10 第十六轮完成**：浏览器真机两段——
  ① `.scratch/fix-loop-warnings/verify-16-browser-fix-center.mjs`（场景②，真实工程 + 真实 UV4）：
  横幅 class=`success`、文案「编译成功 · 0 Error 0 Warning · 耗时 5.7s」、状态行「编译通过 ✅ 0 错 0 警」、
  编译日志 926 字符；② `.scratch/compile-experience-ui/verify-16-banner-shot.mjs`（完整「生成 → 自动编译」）：
  横幅渲染几何 1418 宽 ×43 高、底色 `rgba(63,185,80,.15)`、描边 `rgb(63,185,80)`、字重 600
  → `verify-16-banner-geometry.json` + `shot-16-compile-banner-success.png`；
  视觉通道目视原话「横贯的绿色状态条，带绿色边框、圆角，里面一行加粗文字…没有明显重叠、错位」
  （`shot-16-compile-banner-success.vision.txt`）。**fail 态**由 A11 前端场景的 mock 超时横幅证到
  （class=fail + 文案含「超时」）；notool 态为纯分支（`generate-fix.js:315-318`）未单独截图。
  **挂载点事实（记下来免得下轮再踩）**：`#compile-banner` 挂在 `#generate-result` 内，
  该容器只有「走过一次生成」的会话才 remove hidden——直接开页面点修复中心看不到横幅，
  必须在同会话里生成一次（或看修复中心的 `#fix-status`/轮次条）。
- [x] **A3 来源 `compile-verdict-align/01`**：修复中心横幅四态浏览器验收（数据面已验：
  `ui/fix-center-core.js:109/207/220/248`，`fixErrorCount` grep 零命中）。
  **2026-09-10 第十六轮完成**：与 A2 同批（`verify-16-browser-fix-center.mjs` 场景①/③）——
  横幅四态里的 running/success/fail 三态实况取到（running 经 `onBanner("running")` 与
  mock 首编超时路径；success 见 A2；fail 见 A11 场景），**判读单源**（`compileSummaryText`）
  与状态行文案「0 错 0 警」逐条对齐；`fixErrorCount` 仍在库中零命中。
- [ ] **A4 来源 `contest-project-generator/02`**：生成的 stm32 工程在 Keil5 里编译一次（`RUNBOOK.md:38`）。
  → **需用户点一次**（第十六轮清单：打开 `C:\Users\luoji\Desktop\firstep\.scratch\real-run\out_2026C_stm32\user\Project.uvprojx`
  → F7 Build；期望 `0 Error(s), 0 Warning(s)`）。CLI 侧同一工程已由 A9 真机 UV4 全量重建证过。
- [ ] **A5 来源 `contest-project-generator/03`**：生成的 mspm0 工程在 CCS 里编译一次（`RUNBOOK.md:39`）。
  → **需用户点一次**（第十六轮清单：CCS 导入 `.scratch/real-run/out_2026H_mspm0` → Build）。
  **2026-09-18 口径更新**：该工程（7 条 SysConfig 引脚冲突）现在**根本生成不出来**——生成期
  门禁按「写侧将要落盘的 syscfg」拦下并逐脚列出双方（`pin-conflict-gate/01`，HTTP 路径 400 见
  `verify-01-real-machine-generate-check.txt`）。所以 CCS 复验改用**可解形态**：
  生成时带 `--bindings {"servo.SERVO_PWM_C0":"PA0"}`（= 网页「一键配置」同一动作），
  命令行已验 gmake exit=0；期望 CCS 里也编过，作为跨工具链交叉印证。
- [x] **A6 来源 `ascii-project-name/01` #03**：真实生成 2024H → 桌面目录名 `2024H_Auto_Car` + gmake exit=0 + `.out` 产出。
  已就位：`generation_output.py:38-96`、`tests/test_generation_output.py` 断言 `2024H_Auto_Car`。
  **2026-09-10 第十六轮完成**：真机走 `/api/generate`（`create_desktop_topic_dir=true`）生成到
  `C:\Users\luoji\Desktop\2024H_Auto_Car_MSPM0`，`gmake -C Debug -f makefile -B all` → **exit=0、
  0 错 0 警、4.7s**，产出 `Debug\mspm0_project.out`（11936 字节），makefile 集 0 处非 ASCII 行 →
  `.scratch/ascii-project-name/verify-16-A6-desktop-gmake.txt`。
  **口径修订（原口径 → 现状 + 理由）**：验收写「桌面目录名 `2024H_Auto_Car`」，但
  `desktop-platform-suffix/01`（后于本单）已给桌面目录名加平台后缀 → 现状是
  `2024H_Auto_Car_MSPM0`（同题双平台可并存）。ascii 判据（全 ASCII、无中文路径残留）
  与「gmake exit=0 + .out 产出」两条口径不变，仍逐条验过。
- [ ] **A7 来源 `mspm0-syscfg-default/01`**：用户用 CCS Theia 打开生成工程，GUI 编译复验。
  已就位：`library/masters/mspm0/mspm0.syscfg` 默认外设实例齐全（`:93-129`、`:1053-1186`）。
  → **需用户点一次**（第十六轮清单：CCS Theia 打开 `.scratch/real-run/out_16_mspm0_min`
  ——最小工程（只选 servo）命令行已 0 错 0 警，适合做「GUI 编过」的干净样本；
  再开 `out_2026H_mspm0` 复验新单 02 的冲突形态）。
- [x] **A8 来源 `pin-board-config/01`**：真机 UV4（2021F / 2026C 0 Error）+ gmake（2026H mspm0 0 错）。
  **2026-09-10 第十六轮：stm32 线完成 / mspm0 线验出真缺陷（另开单 02）**——
  stm32：2026C 真机 UV4 `exit=0 Build Time 2s（0 错误 0 警）`（`.scratch/real-run/verify-16-A9-stm32-2026C-reuse.txt`，
  同一产物 A8 首次真机跑含一次真实修复轮：1 错 → AI 修 1 处 → 复编 0 错 0 警）；
  mspm0：**最小工程（只选 servo）真机 gmake exit=0 / 0 错 0 警**（`verify-16-A8-mspm0-min-servo.txt`）= 工具链本身健康；
  但 2026H 12 模块组合真机 **exit=2**，SysConfig 报 7 条 Resource conflict（PA7/PA27/PA13/PA31/PA28/PB18 抢脚），
  而产品的报错解析把「7 error(s)」读成 **0 错 0 警**、修复链当「未定位到可修复文件」——见
  `.scratch/real-acceptance/issues/02-mspm0-compile-verdict-parse-gap.md`。
  **本项（0 错）暂判不满足**，待新单 02 修好后复跑再勾。
  **2026-09-17 第十七轮：判读缺口已修（单 02 resolved），0 错前提不成立 → 保持未勾**——
  真机复跑 `--platform mspm0 --reuse-recommend 2026H`：轮次文案与冲突清单都说真话
  （「第 1/3 轮：7 条 Error 0 条 Warning」；7 条冲突逐条「谁抢谁 + 引脚 + 指路」）、
  配置级冲突不再喂 `/api/fix-errors`（0 次 LLM 调用即停）；
  但**编译仍 exit=2**——7 条冲突是工程真实的 SysConfig 引脚互斥（生成门禁现有检查面覆盖不到，
  附在单 02 的「另立缺口」），本项「gmake 0 错」的验收前提在 2026H 模块组合下仍不满足。
  证据 `.scratch/real-run/verify-17-A8-mspm0-2026H-verdict.txt`。
  **2026-09-18 闭环**：撞脚本体由 `pin-conflict-gate/01-02` 修掉（生成期门禁拦下 + 一键配置真能
  解默认撞脚）——真机 `generate_check.py --platform mspm0 --reuse-recommend --drop … --bindings
  {"servo.SERVO_PWM_C0":"PA0"} 2026H` 生成通过、产物门禁全过、**gmake exit=0（0 错 0 警，9.1s）**，
  证据 `.scratch/pin-conflict-gate/verify-03-auto-config-closes-the-loop.txt`；
  「全模块同选」形态仍物理不可解（落点 42 > 板上可用 IO 31），那是引脚容量问题不是判读问题，
  已记 `backlog.md` 第 7 节等拍板——**本项（stm32 + mspm0 两线 0 错）至此勾满**。
- [x] **A9 来源 `gate-corpus-closure/01`**：真机回归 `generate_check` 2026C `--reuse-recommend`，门禁全过。
  怎么验：`python .scratch/real-run/generate_check.py --topic 2026C --reuse-recommend`。
  **2026-09-10 第十六轮完成**：真机全绿（`2026C: ✓ 通过`）——
  推荐缓存复用 → 骨架 → 生成 66 文件 → **门禁全过**（产物树语料重建跑生产 `run_generation_gates`）
  → UV4 exit=0（0 错 0 警）；证据 `.scratch/real-run/verify-16-A9-stm32-2026C-reuse.txt`。
  **工具口径修订（3 处，均为 `.scratch/` 脚本过期，产品零改动）**：
  ① `generate_check.py` 题库根默认写 `~/.contest_generator/topics`，而库已随包改建到
  `<仓库>/library/topics`（ADR 0008）→ 新增 `--topics-dir` 覆盖；
  ② 同因，`--modules-dir` 覆盖「未知模块 slug」自检落点（不覆盖会把 9 个真 slug 全报成未知 = 9 条假红）；
  ③ 输出目录非空会被 `/api/generate` 正常业务拒绝（400）导致第二次回归卡死 → 脚本改为**先清自己的
  `out_<topic>_<platform>`**（只清自家目录，docstring 已声明归属）。
  另：A9 首次真机的推荐结果让 `zigbee_uart` + `zigbee_link` 同选，生成门禁 400（互斥组正常拦截）——
  按既有先例 `--drop zigbee_link` 收口（见下方「观察项 O-1」）。
- [x] **A10 来源 `cli-fix-loop-parity/01`**：真机 CLI 全链回归（含第 2 轮 `previous_fixes` 回喂）。
  已就位：`.scratch/real-run/generate_check.py:464-485`、`tests/test_generate_check_contract.py:160/179/209`。
  **2026-09-10 第十六轮完成（两段证据，口径如实写明）**：
  ① **真机修复轮闭环**：2026C/stm32 首次真机跑编译报 1 错 → `/api/fix-errors` 真调用 →
  `应用 1 处 / 跳过 0 处`（main.c:328 applied）→ 复编 `exit=0（0 错误 0 警）`，
  备份 id 落盘可回滚（`verify-16-A8-stm32-2026C.txt`）；B26 场景同样一轮清零
  （`verify-16-browser-b26-warning.json`）；
  ② **第 2 轮 `previous_fixes` 回喂**：本机未构造出「一轮修不干净」的真机形态（两处现场都是
  一轮即 0 错 0 警，硬造需人为让 AI 少修一处 = 不可复现），故该项**只有契约/结构测试与代码事实**
  支撑（`build_fix_payload` 的 `previous_fixes` 非空才发 + `run_fix_loop` 逐轮回喂上一轮 `fixes`
  + 前端 `previousDone.fixes` 同语义，`tests/test_generate_check_contract.py:160/179/209` 钉住），
  **真机第 2 轮未复现**——如实记，不拔高。CLI 判定链（含超时即停）另由 A11 真机证。
- [x] **A11 来源 `cli-init-compile-timeout/01`**：真机 probe——临时调小 `compile_runner.COMPILE_TIMEOUT_SECONDS`
  验证「首编超时即停」（`src/contest_generator/compile_runner.py:51`；行为钉 `tests/test_generate_check_contract.py:296-346`）。
  **2026-09-10 第十六轮完成（CLI + 前端两段）**：
  ① CLI：`.scratch/cli-init-compile-timeout/probe-16-first-build-timeout.py`——先 dry-run 量到
  该工程全量重建 **4.75s > 1.0s 阈值**（超时必然发生），再注入 `timeout=1.0` 跑真链路：
  `timed_out=True` / `passed` 非 True / **真实修复调用 0 次** / 墙钟 1.05s（没等到 LLM）
  → `verify-16-first-build-timeout.txt`（生产常量 180s 未改，仓库文件零改动）；
  ② 前端：`verify-16-browser-fix-center.mjs` 场景①（mock `/api/compile` 返回 `timed_out:true`）——
  横幅 `fail` + 文案「编译超时（工具链 180s 未返回）」+ 状态行「已停止循环」+ **`/api/fix-errors` 零调用**
  + 回滚按钮保持隐藏 + 按钮恢复可用。


## B. 浏览器 / CDP 目检与截图（27 项）

统一前置：起 `webapp`（默认 8000）+ Chrome 远程调试（脚本内 CDP 端口各异，见各脚本头部），
零写库或按脚本说明。仓库前端单测（`node --test tests/js/*.test.mjs`）本轮实测 1385 pass / 0 fail，
**下列项是它覆盖不到的真机面**。

**第七轮补充约定（CDP 挂死缓解 + 复跑姿势）**：
- 偶发「`Page.reload` 后渲染进程无响应」已开诊断单 `.scratch/code-editor-cdp-hang/issues/01-reload-renderer-hang.md`；
  在此之前，**每支脚本前重建标签页**（`json/close/<id>` + `PUT json/new?<url>`）是复跑约定；
  `overhaul/*.smoke*.mjs` 的 `cdp()` 已加 20s 超时守卫（挂死会显式报错而非静默卡住）。
- `overhaul/smoke-01/04/08/09` 已按「派发按键前重设选区 + 等渲染落定」修过姿势与过期断言，
  实跑全绿（09 唯一 FAIL 为回车性能项，另见 `.scratch/code-editor-perf-structural/issues/01`）。

**第八轮更新（2026-09-09 · 根因已查清，约定升级为强制）**：
- **根因**：上一支脚本留下**未保存修改**且页面拿过**用户手势**时，`Page.reload` 会弹
  **原生 beforeunload 对话框**（CDP `Page.javascriptDialogOpening`，`type=beforeunload`）；
  无人应答 → 渲染进程停住 → `Runtime.evaluate` 等命令永不返回（`Input.*` 仍应答）。
  **不是产品缺陷**（应答后页面完全恢复，`verify-recovery-clean.mjs` 9/9）。
- **强制前置**：**每支脚本启动前重建标签页**（`json/close/<id>` + **PUT** `json/new?<url>`）。
  推荐直接用批跑器（默认即按此约定）：`node .scratch/cdp-smoke-run.mjs --batch=<名> --port=<CDP 端口>`；
  脚本内自建连接用 `.scratch/cdp-harness.mjs` 的 `rebuildTab()` / `connect()`（后者**自动应答对话框**）。
- 复现与取证脚本、完整证据矩阵见 `.scratch/code-editor-cdp-hang/README.md`。

**姿势清单（第十六轮 B24 浏览器段四坑 → 工单 `real-acceptance/07` 固化；新写真机脚本前先读这一段）**：
助手已入库 `.scratch/browser-harness.mjs`（`expandCard(page, cardId, tabSelector)` /
`pollUntil(page, fn, {timeoutMs, every, label})`——零依赖、**不 import playwright**，page 由调用方
传进来，故纯件可测：`tests/js/browser-harness.test.mjs`；回归样本 =
`.scratch/revise-deepen/verify-16-revise-render.mjs`）。四个坑**都表现为「脚本红/挂住，产品其实
没问题」**，每次重踩平均烧 20~40 分钟，逐条一句 + 正确姿势：

1. **折叠 + 页签 = 元素 `display:none`**：卡默认折叠（`.card.collapsed > *:not(h2) { display:none }`）
   且卡内可能是页签式时，不展开 + 不切页签，内部元素全不可见，`fill/click` 一路等到 30s 超时，
   报错只说 `element is not visible`（看不出是页签没切）。
   **姿势**：`waitForSelector(sel,{state:"attached"})` → `classList.remove("collapsed")` + 点
   `.revise-tab[data-tab=…]` → 再 `waitForSelector(sel,{state:"visible"})`；直接用
   `expandCard(page, cardId, tabSelector)`（见证 = 页签条可见，折叠态整块 display:none）。
   顺带记下 id 事实：修复中心卡 = `#card-fix-center`；`#compile-banner` 挂在 `#generate-result`
   内，**只有走过一次生成的会话**里结果区才可见。
2. **`waitForFunction(fn, arg, options)` 的超时位置**：超时必须放**第三个参数**，写第二个会被当
   `arg` → 拿到默认 30s（现场表现「我明明写了 15 分钟，却 30 秒就红」，本轮因此误判两次「页面挂死」）。
   **姿势**：`waitForFunction(fn, null, {timeout})`；或干脆用 `pollUntil`（它没有这一格）。
3. **`page.evaluate` 里 await 长流程 = 单次 CDP 调用挂几十秒**（分析实测 28s，视觉/深化分钟级），
   期间 node 侧任何 `page.evaluate` 都可能拿不到响应，看起来像「渲染进程无响应」。
   **姿势**：kick off 不 await（`page.evaluate(() => { import(…).then(m => m.analyze()); })`）+
   `pollUntil(page, fn, {timeoutMs, every})` 在 node 侧轮询 DOM（诊断实测：这么写页面一切正常、
   t+28s 分析完成、无 pageerror）。
4. **模态确认不点 = 请求根本不发**：`reviseApply` / `reviseRollback` 各有一层 `confirmModal`
   （覆盖式重生成明示 / 回滚危险确认），不点确认 `POST /api/revise/apply` 不会发出——现场表现
   「执行阶段状态行一直空、服务端日志里只有 analyze」。
   **姿势**：等模态出现后**按按钮文字**点最稳：
   `page.locator(".confirm-modal button, .modal button").filter({ hasText: /执行修订|确认回滚/ }).first().click()`。

- [x] **B1 来源 `code-page-vscode-overhaul/01`**：补折叠与保存的 CDP 断言（现 `smoke-01.mjs` 8 项只覆盖行操作/只读/帮助；
  `grep "折叠|Ctrl+S|保存" .scratch/code-page-vscode-overhaul/*.mjs` 仅命中「截图已保存」）。
  **2026-09-09 第六轮完成**：`smoke-01.mjs` 补折叠 5 项（未折叠基线 / Ctrl+Shift+[ 折叠 + 占位行 + gutter 箭头 + 视图文本 /
  点箭头展开 / 点占位行展开 / Ctrl+Shift+] 展开）+ 保存 3 项（脏点 → Ctrl+S → 脏点清 + toast「已保存」+ 磁盘内容 = 模型），
  并修正脚本注入姿势（派发按键前重设选区）→ 实跑 **19/19 PASS**。顺带修出两处产品缺陷：块选区坍缩（applyEdit 补 taSetRange）、
  幽灵占位行（增量 patch 加 `!winCache.foldedView` 前提）。截图 `shot-01-lineops-dark.png` 已入库。
- [x] **B2 来源 `code-page-vscode-overhaul/07`**：深/浅双主题各一张截图——缩进引导线可见对齐、括号配对描边框、Ctrl+滚轮缩放后仍对齐。
  已就位：`fx/code-marks.js:103 codeIndentGuideMarks`、`index.html:1890 .code-mark-bracket`。
  **2026-09-09 第七轮完成**：`smoke-07.mjs` 实跑 **7/7 PASS**，产物 `shot-07-visual-dark.png` / `shot-07-visual-light.png` 已入库；
  来源工单 `07` 验收四项据此全勾、`Status: resolved`。
- [x] **B3 来源 `code-page-vscode-overhaul/09`**：5000 行 .c 连续**回车 / Tab** 输入路径实测（现 `smoke-09.mjs:87-96` 只 dispatch 字符 `'x'`）。
  **2026-09-09 第六轮完成**：回车 12 次（模型行数 +12 / 长度 +12，均值 13.2ms）、Tab 12 次（模型长度 +48 = 12×4 空格、行数不变，均值 12.6ms），
  输入后仍真彩色 + DOM 行数有界 → 实跑 **14/14 PASS**；截图 `shot-09-input-window-dark.png` 已入库。
- [x] **B4 来源 `code-editor-vscode-polish/02`**：深浅主题截图（`smoke-02.mjs:154/158` 会写 `shot-editor-light/dark.png`，产物不在库）。
  注：当前行左侧 accent 竖线已被后续提交有意移除（`index.html:1829-1833`）。
  **2026-09-09 第七轮完成**：`smoke-02.mjs` 实跑 **8/8 PASS**，产物 `shot-editor-light.png` / `shot-editor-dark.png` 已入库。
- [x] **B5 来源 `code-editor-vscode-polish/08`**：全页验收图 `shot-ide-dark/light.png`（`smoke-08.mjs:133/136`）。
  **2026-09-09 第七轮完成**：`smoke-08.mjs` 实跑 **4/4 PASS**，产物 `shot-ide-dark.png` / `shot-ide-light.png` 已入库。
- [x] **B6 来源 `code-editor-refine/04`**：括号彩虹双主题截图（现以 computed 色值断言代替，无截图产物）。
  **2026-09-10 第十五轮完成**：新写 `.scratch/code-editor-refine/shot-rainbow.mjs`——打开
  `sample-proj-04/nest.c`，断言「深度标记 ≥3 个、逐层颜色互不相同（≥3 色）、深浅两套色不同」，
  产物 `shot-04-rainbow-dark.png` / `shot-04-rainbow-light.png` 入库（视觉通道目视：深色看到 3 种颜色，
  浅色 3 种且「清晰可辨」；注释/字符串里的假括号不被标记）。
- [x] **B7 来源 `module-library-ui/01`**：模块库表格目视截图 `01-table-shot.png`（从未提交；`git log --all --` 无该路径）。
  注（2026-09-09 第七轮实测）：`.scratch/module-library-ui/smoke.mjs` 在本机复跑**未就绪退出**（`页面未就绪`）——
  脚本就绪判据要求全局 `state.modules` 为数组，与当前页面形态不符（同批其它脚本用 DOM 判据）；截图仍未生成，留待脚本判据更新后重跑。
  **2026-09-09 第九轮完成**：脚本按 `master-library-ui-2/smoke.mjs` 模板重写后实跑 **71/71（后 75/75）PASS**，
  截图 `01-table-shot.png` + 收尾截图 `01-table-shot-final.png` 均已入库（每轮冒烟复跑都会重截）。
  **2026-09-10 第十四轮完成目视**：执行 agent 的模型不声明图像输入，经用户拍板改用**仓库自带视觉通道**
  （`contest_generator.vision.describe_image`）看图 + **像素级定量核对**：标题未被吸顶栏遮挡、5 列、无斑马纹、
  徽章与按钮配色统一（仅删除为红字）、slug 等宽、简介列省略号截断、无渲染异常，总评「正常渲染、样式统一」。
  证据：`.scratch/module-library-ui/vision-eyeball.py`、`01-table-shot{,-final}.vision.txt`、`probe-shot-pixels.py`；
  来源工单 `module-library-ui/01` 该项已勾（口径变更留痕见该单「第十四轮」段）。
- [x] **B8 来源 `master-library-ui-2/02`**：母版树冒烟补「目录数 / 文件数」数值断言 + 二进制 / 缺失路径 400 中文断言。
  **2026-09-10 第十五轮完成**：`master-library-ui-2/smoke.mjs` 断言「DOM 树文件条目 = `/tree` 端点条数且逐条同名」
  「DOM `details` 数 = 清单推导的目录数」「缺失路径 400 中文」「`../` 穿越 400 中文」；二进制 400 用
  **同约束的代码端点 + 临时目录**验证（母版树里实测 0 个含 NUL 文件，无真样本——口径写在收口记录里）。
- [x] **B9 来源 `master-library-ui-2/03`**：冒烟补 `pin_config.h` / `mspm0.syscfg` 高亮 span 断言 + 剪贴板内容子串断言。
  **2026-09-10 第十五轮完成**：`pin_config.h`（C 高亮）与 `.cproject`（真 XML）断言 `tok-*` span > 0；
  剪贴板经 `Browser.grantPermissions` 授权后读回内容含 `#define`（复制钮 → 剪贴板闭环）。
  **口径修订**：`.syscfg` 的内容实为 **SysConfig JavaScript**，而 `languageOf` 把 `.syscfg` 归到 XML 分词器
  （`tests/js/highlight.test.mjs` 有守卫）⇒ 该文件 0 个 tok-*、预览为纯文本。冒烟里以 `NOTE` 记录该
  **已知缺口**（要真高亮需加 JS 词法或改映射，属新特性），并把「高亮 span」判据落到真 XML 的工程配置上。
- [x] **B10 来源 `master-library-ui-2/04`**：冒烟补「开导入弹窗 + 平台下拉选项数 + 空 project_dir / 非法平台 400」。
  **2026-09-10 第十五轮完成**：入口接线（`#btn-direct-import` → 隐藏目录输入，spy 计数）、
  平台下拉 = `state.platforms`、空 `project_dir` / 非法平台各 400 中文、导入同形确认弹窗（下拉选项数 + 双钮）。
  **口径修订**：真实「选文件夹 → 暂存 → 弹窗」链路走**原生目录选择器**，CDP `DOM.setFileInputFiles`
  不产生 `webkitRelativePath` 而产品按 `parts.length > 1` 过滤 ⇒ 无法用它跑通，故拆成上述四段机器判据。
- [x] **B11 来源 `master-library-ui-2/05`**：冒烟补「点遮罩取消 + 确认闭合」。
  **2026-09-10 第十五轮完成**：在导入同形弹窗上实测三条闭合路径——**确认**（OK → 返回所选平台值 + 关闭，
  只调组件不调后端、零写库）/ **点遮罩** / **Esc**；取消路径返回值按实现断言「falsy」（带
  `[data-confirm-value]` 时返回 `false`，非 `null`）。
- [x] **B12 来源 `master-library-ui-2/06`**：母版 tab 五项冒烟清单全绿 + 截图 `shot-06-detail-tree.png`。
  **2026-09-10 第十五轮完成**：`smoke.mjs` 扩到 **35 项全绿**（原 17），截图每轮重存档；
  视觉通道目视确认弹窗内是**可展开文件树**（截图看到的是折叠态顶层 6 条，43 个文件条目在 DOM 里，
  机器判据已逐条对齐）。
- [x] **B13 来源 `gen-result-panel/01`**：宽 / 窄屏截图目检生成结果两列布局。
  **2026-09-10 第十五轮完成**：新写 `.scratch/gen-result-panel/verify-01-layout.mjs`——宽屏（1418）
  `.res-grid` 两列且 `.res-side` 在右列（宽 ≈380px、top 齐），窄屏（900）单列且 `.res-side` 落到下方；
  9 个既有 id 全在、`.res-label` ≥5、结构树在右列。产物 `shot-01-wide.png` / `shot-01-narrow.png`；
  视觉通道目视：宽屏「上半部分左右两列」、窄屏「从上到下单列、无横向溢出」。
- [x] **B14 来源 `ui-detail/01`、`/02`、`/03`**：headless 截图目检（步进导航 warn 态 / 动效令牌 / 卡分组）。
  **2026-09-10 第十五轮完成**：新写 `.scratch/ui-detail/verify-01-03.mjs`——① `.step-dot.warn`/`.done`
  规则存在且**挂类后计算样式确实变成 warn-dim / ok-dim**（注意：`transition` 150ms，读数必须等落定，
  否则读到动画起始值）；② 四个动效令牌存在且 40 个采样元素的计算 transition 全部取自它们；
  ③ `.card-group` 规则 + 生成页 12 个分组（卡 10 `#card-fix-center` 两段、卡 11 四段）。
  产物 3 张截图 + 视觉通道目视。
- [x] **B15 来源 `ux-polish-02/09`**：CDP 跑 `.scratch/ux-polish-02/probe-t09.mjs`（八项行为 + 四页零 JS 异常 + 无横向溢出 + 未触发真实 LLM 请求）。
  **2026-09-10 第十五轮完成**：探针修掉两处过期前提后实跑 **13 项全绿**（含 9 个页签零横向溢出、
  零未捕获 JS 异常、零真实 LLM 请求）；证据 `.scratch/ux-polish-02/verify-09-t09.txt`。
  **口径修订**：① 检查项 04 的假工程需补最小 `.uvprojx`（`/api/revise/context` 现在要求工程配置文件）；
  ② 检查项 03 改为点击后轮询（首跑三条子断言全 false、随后单跑/人工复现均通过）；
  ③ 任务卡缺失时按 FAIL 报告而不是抛异常中断整支脚本。
- [x] **B16 来源 `frontend-es-modules/11`**：8 个 tab 浏览器冒烟（`.scratch/frontend-es-modules/smoke.mjs`）。
  **2026-09-10 第十五轮完成**：实跑 **11 passed / 0 failed**（含「每个 tab 的 aria-controls 指向存在的
  section」结构不变量，导航现为 11 个 tab——第九轮口径修订），证据 `verify-11-smoke.txt`。
- [x] **B17 来源 `frontend-es-modules-stage2/23`**：新增平台下拉 options 实况（`ui/master.js:655 renderNewPlatformOptions` 已导出）。
  **2026-09-10 第十五轮完成**：`master-library-ui-2/smoke.mjs` 断言下拉选项值集合 = `state.platforms`
  （`["stm32","mspm0"]`，逐项对齐）；`tests/js/master-render.test.mjs` 静态守卫在位。
- [x] **B18 来源 `frontend-es-modules-stage2/24`**：草稿清除按钮实况点按（共享 handler `generate-steps.js:77 bindClearDraftButton`）。
  **2026-09-10 第十五轮完成**：新写 `.scratch/frontend-es-modules-stage2/verify-24-25.mjs`——点 `#btn-clear-draft`
  → 草稿键确实被清 + 文案「已清除」→ 1.5s 回「清除草稿」；第二入口 `#btn-draft-clear` 同 handler 同样生效。
- [x] **B19 来源 `frontend-es-modules-stage2/25`**：main.c 滚动三同步实况（`generate-mainc.js:26-30 syncPanels`）。
  **2026-09-10 第十五轮完成**：同上脚本——200 行内容后行号列行数跟新、高亮层有 tok-* span；
  滚到 300px 与 80% 处时 `#main-c-nums` / `#main-c-hl` 的 `scrollTop` 与 textarea 相等（三方同步）。
- [x] **B20 来源 `frontend-es-modules-stage2/21`**：diag 零 EXC + `smoke.mjs` 11/11。
  **2026-09-10 第十五轮完成**：`frontend-es-modules/diag.mjs` 实跑 **事件区零 EXC**（另有 1 条
  `/api/generate/preview-dir` 400 与 1 条 favicon 404，均为预期/无关，非异常）；`smoke.mjs` 11/11。
  证据 `verify-21-diag.txt` / `verify-11-smoke.txt`。
- [x] **B21 来源 `newcomer-onboarding/03`**：欢迎卡「不再显示」跨刷新持久 + 配 key 后转 compact（localStorage 跨刷新）。
  **2026-09-10 第十五轮完成**：新写 `.scratch/newcomer-onboarding/verify-03-welcome.mjs`——**12 项全绿**：
  纯件真值表（full/compact/hidden×2）/ 未配 key 首访完整卡 + 三步 + 四按钮 / 「去配置 API key」切页并聚焦
  （AI API 卡自动展开）/ 「检查环境」切页且体检结果区非空 / 「不再显示」写键并清空卡片 + **跨刷新持久** /
  已配 key → compact 卡（含「开始做题」）/ 已配 key + 有草稿 → 不显示 / gen-banner「去设置」跳转。
  口径澄清：草稿优先于 compact，但**未配 key 时仍走 full**（`welcomeMode` 的判定顺序）。
- [x] **B22 来源 `wiki-materials/02`**：Markdown 资料库人工验收（批次可见 / 70+2 篇 / 过滤 mpu6050 / 预览渲染 / 刷新清空）。
  **2026-09-10 第十五轮完成**：新写 `.scratch/wiki-materials/verify-md-library.mjs`——列表行数 = 端点全量
  （**156 篇**，库已扩容）、批次 chips 含 `lckfb-地猛星移植手册`（该批 **72 篇**）、两篇索引在列、
  过滤「mpu6050」命中数与端点同源（**2 篇**，地阔星 + 地猛星各一）、预览渲染正文（6 个标题 / 5 个代码块 /
  169 个 tok-* 高亮 span）、刷新与清空正常、点「打开」经**可信点击**开新标签且列表不受影响。
  口径修订：篇数按库现状（156 / 该批 72 / mpu6050 两篇）而非旧记录的 70+2 / 1 篇。
- [x] **B23 来源 `wiki-md-repair/04`、`/06`**：彩屏篇预览显示 gif；列表首列显示中文标题 + 文件名小字。
  **2026-09-10 第十五轮完成**：同脚本——图片端点直取 gif 200 + `image/gif`；彩屏篇预览 `img`
  src 指素材端点且 `naturalWidth=1634`（真解码）；无图手册（sht30）预览有正文、无图、无错误态；
  首列中文标题 + 文件名小字（13px vs 11px）。产物 `shot-md-list.png` / `shot-md-color-preview.png`；
  视觉通道目视：列表确为「中文标题 + 小字文件名」两行结构、预览弹窗确有图片。
- [x] **B24 来源 `revise-deepen/05`**：修订/深化阶段卡视觉与交互（含历史目录补题面全流程、三态、回滚、SSE 断线提示）。
  **2026-09-10 第十五轮：可确定性验证的一半已做**（`.scratch/revise-deepen/verify-05-stage-card.mjs`，7 项全绿）：
  两条入口齐备 / 初始态三槽位与回滚按钮隐藏 / 历史目录加载成功（来源=反推、平台 stm32、模块 led、
  题面缺失提示）/ 错误路径①目录不存在 400 中文 / 错误路径②无工程配置文件 400 中文。
  **2026-09-10 第十六轮完成剩余三处（真 LLM + 真工具链，两段证据）**：
  ① **服务端真链段** `.scratch/revise-deepen/probe-16-revise-analyze.py`：真 `/api/revise/analyze`
  SSE 事件流 `impact_analyzing → llm_telemetry → diff_ready → done`（7.5s）、
  `impacts=2`（两段 Q&A 逐条不漏）、`diff={added:0, removed:['relay'], unchanged:11}`、
  `suggested_slugs=11`、`warnings=0` → `verify-16-revise-analyze.{txt,json}`（7 项全绿）。
  ② **浏览器渲染段** `.scratch/revise-deepen/verify-16-revise-render.mjs`（19 项全绿）：
  历史目录加载 → 补题面框（该目录 `.contest_context.json` 的 `problem_text` 为空，走原验收项的
  「历史目录补题面全流程」）→ 分析区渲染（逐条影响结论 + 模块集 diff 三栏 + 平台警告 + 建议模块集，
  3 个条目块 / 27 个 chip、「放弃」按钮亮、建议集预填确认框）→ 确认执行（真「确认执行修订？」模态
  → SSE 进度 `备份 → 重生成 → 编译验证` 三态可见）→ 结果区（`修订完成——可继续「直接深化」或回滚`
  + diff 记录 + 回滚按钮亮）→ **回滚真撒**（确认模态 → `已回滚到备份状态` + `已回滚 149 项`
  + main.c sha 逐字节复原）→ 截图 `shot-16-revise-{analysis,result}.png`。
  证据 `.scratch/revise-deepen/verify-16-revise-render.{txt,json}` + `verify-16-revise-progress.txt`。
  **本轮踩到并记下的浏览器验收坑（写在这里省下次时间）**：① 第 11 步卡是**页签式**且默认折叠，
  不切 `.revise-tab[data-tab="revise"]` 内部元素全 `display:none`；② playwright
  `waitForFunction(fn, arg, options)` 的**超时必须放第三个参数**（放第二个会被当 arg → 默认 30s，
  表现为「15 分钟超时其实 30 秒」）；③ `page.evaluate` 里 await 长流程 = 单次 CDP 调用挂几十秒
  （分析实测 28s），要改成「kick off 不 await + node 侧轮询 DOM」；④ 执行/回滚各有一层
  `confirmModal`，不点确认根本不会发 POST（服务端日志里只看到 analyze 就是这个原因）。
- [x] **B25 来源 `k230-multi-template/04`**：浏览器手测模板切换 → 生成的 `main.py` 随选择变化。
  **2026-09-10 第十五轮完成（两段证据）**：
  ① **UI 段** `.scratch/k230-multi-template/verify-04-frontend.mjs`（7 项全绿）：走确定性端点
  `/api/selection/expand` + 导出的 `renderSelected()` → k230 卡出现「副产物模板」下拉（3 选项 = manifest
  templates、默认 = `default`(blob)、title 带 description）；选 `rect` 记进 `pythonTemplates`、
  改回默认则删除（默认不发字段）；选 `digit` → 展开结果含模板级依赖 `digit_uart`。
  ② **渲染段** `.scratch/k230-multi-template/verify-04-templates.py`（14 项全绿）：三份模板文件在盘，
  经产品渲染器 `k230_render.render_python_artifact` 渲染后**两两不同**且各含特征调用
  （find_blobs / find_rects / AnchorBaseDet），digit 的随工程分发资产在盘。
  仍未覆盖：整条生成链（推荐 → 骨架 → 落盘 main.py）需真实额度，属 C 组。
- [x] **B26 来源 `fix-loop-warnings/01`**：浏览器注入未用变量 → 自动清零到「0 错 0 警」。
  **第十五轮结论：留在 A/C 组**——本机 UV4/gmake 虽在盘（环境体检已勾 ✓），但要跑「注入告警 → 自动
  续跑修复轮 → 复编到 0 错 0 警」需要在 IDE/真编译链路里跑完整修复循环并消耗真实额度；
  与 A 组编译矩阵、C 组额度项同源，不重复挂账。
  **2026-09-10 第十六轮完成（浏览器真机）**：`.scratch/fix-loop-warnings/verify-16-browser-fix-center.mjs`
  场景③——向 `main.c` 的 `main()` 内注入 `int unused_probe_16 = 1;` → 页面点「一键编译修复」→
  真 UV4 首编 1 警 → 真 `/api/fix-errors` 修复轮（第 1/3 轮）→ 注入行被 AI 删除 → 复编
  「第 1 轮重编译通过 ✅ 0 错 0 警」+ 回滚按钮可见 → `verify-16-browser-b26-warning.json` +
  `shot-16-fix-warning-cleared.png`（视觉通道目视原话：「第 1/3 轮 · 耗时 5.2s」「第 1 轮重编译通过 ✅ 0 错 0 警」
  「已修复 ../main.c:71 … unused_probe_16」）。
- [x] **B27 来源 `recommend-progress-ui/01`**：真实 API 跑 2021F（第 2 轮收敛跳满 / 死寂期计时器跳动 / 补问 / 中途杀服务断线 / 未配 key 400）。
  **第十五轮结论：留在 C 组**——五条子项里「未配 key 400」可离线验，其余四条都要真实推荐额度；
  已由 C 组的真实额度项统一承接（`recommend-vision-qa/03` 的 2021F 真机验收同批一起跑最省额度）。
  **2026-09-10 第十六轮完成（逐条给判据）**：
  ① 第 2 轮收敛跳满 / 死寂期计时器跳动：真机 2021F 推荐实测**收敛轮次 [1,2,3,4]**、2026C `[1,2]`、
  2026F `[1,2]`（`.scratch/recommend-domain-reject/verify-16-recommend-*.txt`）——
  `converged` 事件提前收敛与「条跳满」是同一 `.prog-bar` 宽度的两个分支（`ui/generate-recommend.js`
  `converged → 100%`），死寂期计时器 = `setInterval(tickRec,1000)` 独立于事件；
  机器判据落在 B27 原工单的 jsdom 39 断言（可选自查，未入库）+ 本轮的真机事件序列（round 计数）。
  ② 补问路径：真机多次命中并留档（2026H 1 条 / 2026C 3 条 / 2026F 1→2 条，问题原文见各 `verify-16-recommend-*.txt`）。
  ③ 中途杀服务断线：**未做**——本轮 webapp 被正式重启过两次（配置热更 + E2 端口被占态），但没有在推荐流
  中途 kill；判据可由前端 `if (!recProg.finished) showRecommendError("连接中断…")` 分支 + 提炼侧同款
  代码事实支撑（`index.html:1531-1534` 先例），**如实记为未实测**。
  ④ 未配 key 400：`tests/test_webapp.py:1742-1754` `test_ai_endpoints_reject_with_hint_when_unconfigured`
  对 `/api/recommend` 断言 400 + 「未配置 AI API」——已由测试守门（离线判据）。


## C. 真实 LLM / 视觉额度（5 项）

- [ ] **C1 来源 `recommend-vision-qa/03`（ready-for-human）**：2021F 真视觉主链路（图内尺寸类澄清被自动消化，不再问用户）+ 三条降级路径。
  已就位：`webapp.py:1752-1769` 注入链、`tests/test_vision_qa.py` 9 例；本机 `vision_api_key` 为空（按仓库口径复用主 key，会消耗主 key 额度）。
- [ ] **C2 来源 `clarify-no-restriction/02`**：重启服务后 2024H 不再问「起始方向 / 声光形式 / 几路」。
  已就位：提示词条款 `llm.py:153/182`、契约测试 `tests/test_llm.py:5743`。
- [ ] **C3 来源 `fix-request-budget/01`**：真实超大中文上下文打 `/api/fix-errors`，不再「请求体过大」。
  已就位：`fix_errors.py:359`、`tests/test_llm.py:1117`（最坏总量 < 128KB 已钉死）。
- [ ] **C4 来源 `fix-session-homing/01`**：真机贴文本修复一次真实调用，事件流与回滚一致。
  已就位：`fix_errors.py:726 run_fix_round`、`tests/test_fix_errors.py:932/998/1013/1177/1200`。
- [ ] **C5 来源 `key-multi-instance/07`**：AI 推荐抽验 2026F / 2022C / 2026C（多实例猜测是否合理）。

## D. 人工取源 / 外部账号（2 项）

- [ ] **D1 来源 `identity-fields/06`（ready-for-human）**：6 个器件补 `kit` + `source_url`（beep / ir_beam / key / led / led_beep / step_motor）——
  或明确判「永久不补」并改 `library.MODULE_KIND`（内部件 / 协议切片）。**机器不许编链接**，必须人工核实。
- [ ] **D2 来源 `wiki-md-repair/02`**：跨分类抽查 ≥5 篇（现记 4 篇：sensor / rf / screen / control 各一）。

## E. 干净机器 / 启动脚本三态（2 项）

- [ ] **E1 来源 `newcomer-onboarding/01`**：全新机器 `install.bat` → `.venv` → 双击 `start-app.vbs` 起服务走通
  （含「无 python」「有旧版 python」两态中文提示；`tests/test_onboarding_docs.py:27` 已守门文案）。
- [ ] **E2 来源 `newcomer-onboarding/02`**：`start-app.bat` 双态实测——正常态无黑窗 + 端口被占中文弹窗 + 超时弹窗带日志路径。

## F. 历史流程项（不可回溯复核，仅登记）

- [ ] **F1 `arch-model-cycle/01`、`arch-source-read-seam/01`、`arch-stage-domain/01`、`arch-store-skeleton/01`**：
  验收含「独立 worktree + 独立 commit」——**历史流程项，无法回溯复核**；替代判据 = 代码事实（`report.py:358/379`、
  `skeleton.py:126`、`entry_store.py:125` 单源 + 结构测试）与全量回归（2026-09-09 实测 pytest 3928 passed）。
- [ ] **F2 `local-llm-safety/02`**：验收含「跑全量 pytest、mypy 和 Node 测试」——全量 pytest 3928 / node 1385 已实测，
  mypy 见 `pyproject.toml` 配置；**无需逐项重判**，回归基线以 `2026-09-09-在途盘点.md` 为准。
- [ ] **F3 `pin-verdict-seam/02`（deferred）**：已裁决不做（前端镜像与后端 `resolve_bindings` 当前同口径），
  仅在未来真有矩阵改动时作 prefactoring 前置——**非待办**。

## 收尾约定

- 本单每验完一项：勾选 + 在来源工单对应验收项补勾（来源工单不删本单指针）。
- 验出真 bug：另开修复工单，本单该项留空并注明修复单号。
- 全部 A~E 勾完 = 本单 resolved；F 组随本单一起收尾（它只是登记）。
- 下一轮盘点**不再逐张重判**这些项——只看本单进度。
