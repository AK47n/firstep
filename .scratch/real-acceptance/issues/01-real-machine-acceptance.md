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

- [ ] **A1 来源 `b1-adc-servo/03`**：adc / servo 绑定场景编译矩阵 0 error 0 warning。
  怎么验：`python .scratch/b1-adc-servo/compile_matrix.py`（四例：default/bound × stm32/mspm0）。
  已就位：`.scratch/b1-adc-servo/compile_matrix.py:78-87` 与生产同闸（`build_output_tree_corpus` + `run_generation_gates`）；
  `tests/test_module_adc.py:138-154`、`tests/test_module_servo.py:125-133`（渲染侧已验）。
- [ ] **A2 来源 `compile-experience-ui/01`**：真实工程 + 工具链跑完整编译修复闭环，横幅四态与错误列表实况。
  已就位：`ui/generate-fix.js:65 compileBanner`、`index.html:469-477`、`webapp.py:3944`。
- [ ] **A3 来源 `compile-verdict-align/01`**：修复中心横幅四态浏览器验收（数据面已验：
  `ui/fix-center-core.js:109/207/220/248`，`fixErrorCount` grep 零命中）。
- [ ] **A4 来源 `contest-project-generator/02`**：生成的 stm32 工程在 Keil5 里编译一次（`RUNBOOK.md:38`）。
- [ ] **A5 来源 `contest-project-generator/03`**：生成的 mspm0 工程在 CCS 里编译一次（`RUNBOOK.md:39`）。
- [ ] **A6 来源 `ascii-project-name/01` #03**：真实生成 2024H → 桌面目录名 `2024H_Auto_Car` + gmake exit=0 + `.out` 产出。
  已就位：`generation_output.py:38-96`、`tests/test_generation_output.py` 断言 `2024H_Auto_Car`。
- [ ] **A7 来源 `mspm0-syscfg-default/01`**：用户用 CCS Theia 打开生成工程，GUI 编译复验。
  已就位：`library/masters/mspm0/mspm0.syscfg` 默认外设实例齐全（`:93-129`、`:1053-1186`）。
- [ ] **A8 来源 `pin-board-config/01`**：真机 UV4（2021F / 2026C 0 Error）+ gmake（2026H mspm0 0 错）。
- [ ] **A9 来源 `gate-corpus-closure/01`**：真机回归 `generate_check` 2026C `--reuse-recommend`，门禁全过。
  怎么验：`python .scratch/real-run/generate_check.py --topic 2026C --reuse-recommend`。
- [ ] **A10 来源 `cli-fix-loop-parity/01`**：真机 CLI 全链回归（含第 2 轮 `previous_fixes` 回喂）。
  已就位：`.scratch/real-run/generate_check.py:464-485`、`tests/test_generate_check_contract.py:160/179/209`。
- [ ] **A11 来源 `cli-init-compile-timeout/01`**：真机 probe——临时调小 `compile_runner.COMPILE_TIMEOUT_SECONDS`
  验证「首编超时即停」（`src/contest_generator/compile_runner.py:51`；行为钉 `tests/test_generate_check_contract.py:296-346`）。

## B. 浏览器 / CDP 目检与截图（27 项）

统一前置：起 `webapp`（默认 8000）+ Chrome 远程调试（脚本内 CDP 端口各异，见各脚本头部），
零写库或按脚本说明。仓库前端单测（`node --test tests/js/*.test.mjs`）本轮实测 1385 pass / 0 fail，
**下列项是它覆盖不到的真机面**。

- [x] **B1 来源 `code-page-vscode-overhaul/01`**：补折叠与保存的 CDP 断言（现 `smoke-01.mjs` 8 项只覆盖行操作/只读/帮助；
  `grep "折叠|Ctrl+S|保存" .scratch/code-page-vscode-overhaul/*.mjs` 仅命中「截图已保存」）。
  **2026-09-09 第六轮完成**：`smoke-01.mjs` 补折叠 5 项（未折叠基线 / Ctrl+Shift+[ 折叠 + 占位行 + gutter 箭头 + 视图文本 /
  点箭头展开 / 点占位行展开 / Ctrl+Shift+] 展开）+ 保存 3 项（脏点 → Ctrl+S → 脏点清 + toast「已保存」+ 磁盘内容 = 模型），
  并修正脚本注入姿势（派发按键前重设选区）→ 实跑 **19/19 PASS**。顺带修出两处产品缺陷：块选区坍缩（applyEdit 补 taSetRange）、
  幽灵占位行（增量 patch 加 `!winCache.foldedView` 前提）。截图 `shot-01-lineops-dark.png` 已入库。
- [ ] **B2 来源 `code-page-vscode-overhaul/07`**：深/浅双主题各一张截图——缩进引导线可见对齐、括号配对描边框、Ctrl+滚轮缩放后仍对齐。
  已就位：`fx/code-marks.js:103 codeIndentGuideMarks`、`index.html:1890 .code-mark-bracket`。
- [x] **B3 来源 `code-page-vscode-overhaul/09`**：5000 行 .c 连续**回车 / Tab** 输入路径实测（现 `smoke-09.mjs:87-96` 只 dispatch 字符 `'x'`）。
  **2026-09-09 第六轮完成**：回车 12 次（模型行数 +12 / 长度 +12，均值 13.2ms）、Tab 12 次（模型长度 +48 = 12×4 空格、行数不变，均值 12.6ms），
  输入后仍真彩色 + DOM 行数有界 → 实跑 **14/14 PASS**；截图 `shot-09-input-window-dark.png` 已入库。
- [x] **B4 来源 `code-editor-vscode-polish/02`**：深浅主题截图（`smoke-02.mjs:154/158` 会写 `shot-editor-light/dark.png`，产物不在库）。
  注：当前行左侧 accent 竖线已被后续提交有意移除（`index.html:1829-1833`）。
  **2026-09-09 第七轮完成**：`smoke-02.mjs` 实跑 **8/8 PASS**，产物 `shot-editor-light.png` / `shot-editor-dark.png` 已入库。
- [x] **B5 来源 `code-editor-vscode-polish/08`**：全页验收图 `shot-ide-dark/light.png`（`smoke-08.mjs:133/136`）。
  **2026-09-09 第七轮完成**：`smoke-08.mjs` 实跑 **4/4 PASS**，产物 `shot-ide-dark.png` / `shot-ide-light.png` 已入库。
- [ ] **B6 来源 `code-editor-refine/04`**：括号彩虹双主题截图（现以 computed 色值断言代替，无截图产物）。
- [ ] **B7 来源 `module-library-ui/01`**：模块库表格目视截图 `01-table-shot.png`（从未提交；`git log --all --` 无该路径）。
  注（2026-09-09 第七轮实测）：`.scratch/module-library-ui/smoke.mjs` 在本机复跑**未就绪退出**（`页面未就绪`）——
  脚本就绪判据要求全局 `state.modules` 为数组，与当前页面形态不符（同批其它脚本用 DOM 判据）；截图仍未生成，留待脚本判据更新后重跑。
- [ ] **B8 来源 `master-library-ui-2/02`**：母版树冒烟补「目录数 / 文件数」数值断言 + 二进制 / 缺失路径 400 中文断言。
- [ ] **B9 来源 `master-library-ui-2/03`**：冒烟补 `pin_config.h` / `mspm0.syscfg` 高亮 span 断言 + 剪贴板内容子串断言。
- [ ] **B10 来源 `master-library-ui-2/04`**：冒烟补「开导入弹窗 + 平台下拉选项数 + 空 project_dir / 非法平台 400」。
- [ ] **B11 来源 `master-library-ui-2/05`**：冒烟补「点遮罩取消 + 确认闭合」。
- [ ] **B12 来源 `master-library-ui-2/06`**：母版 tab 五项冒烟清单全绿 + 截图 `shot-06-detail-tree.png`。
- [ ] **B13 来源 `gen-result-panel/01`**：宽 / 窄屏截图目检生成结果两列布局。
- [ ] **B14 来源 `ui-detail/01`、`/02`、`/03`**：headless 截图目检（步进导航 warn 态 / 动效令牌 / 卡分组）。
- [ ] **B15 来源 `ux-polish-02/09`**：CDP 跑 `.scratch/ux-polish-02/probe-t09.mjs`（八项行为 + 四页零 JS 异常 + 无横向溢出 + 未触发真实 LLM 请求）。
- [ ] **B16 来源 `frontend-es-modules/11`**：8 个 tab 浏览器冒烟（`.scratch/frontend-es-modules/smoke.mjs`）。
- [ ] **B17 来源 `frontend-es-modules-stage2/23`**：新增平台下拉 options 实况（`ui/master.js:655 renderNewPlatformOptions` 已导出）。
- [ ] **B18 来源 `frontend-es-modules-stage2/24`**：草稿清除按钮实况点按（共享 handler `generate-steps.js:77 bindClearDraftButton`）。
- [ ] **B19 来源 `frontend-es-modules-stage2/25`**：main.c 滚动三同步实况（`generate-mainc.js:26-30 syncPanels`）。
- [ ] **B20 来源 `frontend-es-modules-stage2/21`**：diag 零 EXC + `smoke.mjs` 11/11。
- [ ] **B21 来源 `newcomer-onboarding/03`**：欢迎卡「不再显示」跨刷新持久 + 配 key 后转 compact（localStorage 跨刷新）。
- [ ] **B22 来源 `wiki-materials/02`**：Markdown 资料库人工验收（批次可见 / 70+2 篇 / 过滤 mpu6050 / 预览渲染 / 刷新清空）。
- [ ] **B23 来源 `wiki-md-repair/04`、`/06`**：彩屏篇预览显示 gif；列表首列显示中文标题 + 文件名小字。
- [ ] **B24 来源 `revise-deepen/05`**：修订/深化阶段卡视觉与交互（含历史目录补题面全流程、三态、回滚、SSE 断线提示）。
- [ ] **B25 来源 `k230-multi-template/04`**：浏览器手测模板切换 → 生成的 `main.py` 随选择变化。
- [ ] **B26 来源 `fix-loop-warnings/01`**：浏览器注入未用变量 → 自动清零到「0 错 0 警」。
- [ ] **B27 来源 `recommend-progress-ui/01`**：真实 API 跑 2021F（第 2 轮收敛跳满 / 死寂期计时器跳动 / 补问 / 中途杀服务断线 / 未配 key 400）。

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
