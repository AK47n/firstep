# 04 — 前端接入：模块配置 + `.py` 交付

**What to build:** 用户在前端能勾选 K230 模块、给它的串口配主控引脚，生成的 `.py` 随下载产物一起拿到——一条从「勾选」到「拿到可烧录 .py」的完整闭环。

**Blocked by:** 03 — k230 模块落地 + 真实视觉模板

**Status:** resolved

- [x] K230 模块出现在前端模块选择里，串口引脚可在配置菜单里配（验证现有通用 pins 机制是否已自动覆盖；若已覆盖，本项仅需端到端验证，不新写 UI）
- [x] `.py` 产物随下载链路交付（确认打包/下载逻辑包含新写的 `.py` 文件，不改动现有 C 工程产物）
- [x] 端到端验收：推荐链路识别到视觉需求 → 勾选 K230 → 生成产物同时含主控工程（ball_detect 解析）+ K230 `main.py`，协议对齐
- [x] 前端相关测试绿（node:test / webapp 测试），全量 Python 测试绿

完成（分支 k230-vision-copilot/04）：探查先行——模块池 / 推荐 chips / 引脚配置对 k230（pins 空 + files 空）已全通用覆盖，零新 UI（renderModulePool / renderModuleSearch / renderSelected / renderWarnings / renderPinCard 全吃 manifest 数据；k230 依赖 ball_detect 自动挂上，其 uart_tx/uart_rx 角色就是引脚卡配置项）；推荐链路 selection.py 零改动（实测真 LLM：找球小车题面 → 顶层 modules `['k230', 'ball_detect', 'motor', 'led']`，k230 第一命中、视觉需求无库外建议；识别数字题面 → digit_uart 库内命中 + K230 库外建议——k230 首批能力只做色块/球检测，数字识别 .py 属 Out of Scope，行为正确）；产物交付 = output_dir 本地目录（无 zip 链路），`.py` 已写工程根——唯一缺口是前端产物摘要不体现副产物，补上：GenerationSummary 增 `python_artifacts`（slug → 输出文件名，模块级声明与平台无关；未选带声明模块 = 空元组旧行为）+ `_generation_result` 带 `python_artifacts` 数组 + index.html 抽纯函数 `formatResModules`（files 空模块显示「副产物 main.py」）。

测试：tests/js/format-res-modules.test.mjs 4 用例（node:test 17 绿 = 13 基线 + 4）；test_webapp.py 新增 `_add_fake_k230_modules` 假模块对 + 两条 e2e（expand：依赖序 [ball_detect, k230]、k230 pins 空、ball_detect uart_tx/rx 角色在、unverified+hardware_bound 警告；generate：ball_detect.c 落盘 + k230 无 C 子树 + main.py 工程根 + python_artifacts 载荷）+ 旧 generate 测试补 `python_artifacts == []` 向后兼容断言；test_k230_artifact.py 三条摘要断言（probe 模块 + 真实 k230 双平台 generate_project）。全量 1776 绿（1765 基线 + 11）+ mypy 46 文件干净 + node:test 17 绿。

留痕：真 LLM 推荐探针脚本在 `.scratch/k230-vision-copilot/probe-recommend-vision.py`（复用成本低，两个视觉题面对照）；k230 前端徽标 = 硬件绑定（未上板真机，人工验收）；数字识别对端 .py 能力留后续工单。
