# 烧录（flash-deploy）Spec

## 问题陈述

电赛工程生成器已实现「生成 → 编译全自动」，但**烧录仍是纯手动**：README/演示脚本只给文字步骤（Keil 按 F8 接 ST-Link、CCS 里点 Load）。逐步深化每步执行后都要「烧录上板观察」，用户必须离开工具去 Keil/CCS 手动烧——步骤多、易错（找不到产物、连错探针）。用户诉求：**在 firstep 上直接烧录**——点一个按钮，工具自动定位固件产物、调用本机烧录器 CLI、中文回报结果。

## 目标

生成结果面板与任务执行结果面板各加「烧录到板子」按钮：

1. 自动定位固件产物：STM32 → `user/Objects/*.hex`（母版已开 `<CreateHexFile>1`，取最新）；MSPM0 → `Debug/*.out`（样例 `mspm0_project.out`，rglob 取最新）。
2. 自动探测/配置烧录工具（单源 flash.py，同 find_uv4/find_ccs_tools 先例）：
   - **MSPM0 + XDS110**：CCS 自带 `C:\ti\ccs*\ccs\ccs_base\DebugServer\bin\DSLite.exe`（实测 20.5.0.4019，`FlashMSPM0.dll` 在位）——**本机零安装**；ccxml 自动定位 `targetConfigs/*.ccxml`。调用：`DSLite.exe flash --config=<ccxml> <out> -u`（-u = 烧完运行）。
   - **STM32 + ST-Link**：OpenOCD（`openocd -f interface/stlink.cfg -f target/stm32f1x.cfg -c "program <hex> verify reset exit"`）或 st-flash（`st-flash write <hex> 0x08000000`）——本机未装：探测不到 → 指引卡（安装提示 + 设置页路径配置 + 一键复制命令）。
3. 探测顺序 = config 覆盖（openocd_path / stflash_path / dslite_path）> 自动（shutil.which / C:/ti/ccs* 扫描）> 缺失（400 中文 + 指引）。
4. 执行超时 180s（同编译先例）；结果中文汇报：成功（工具 + 闪存目标 + 用时）/ 失败（输出尾 40 行截断）/ 工具缺失（指引）。

## 用户故事

1. 作为用户，生成/任务执行完成后，结果面板有「烧录到板子」按钮。
2. 点击后 ① 定位产物 ② 探测工具 ③ 调用烧录 ④ 中文结果——全程无需离开工具。
3. MSPM0 工程点烧录 → 走 XDS110/DSLite（ccxml 自动找到，无需配置）。
4. STM32 工程点烧录 → 探测 OpenOCD/st-flash；未装 → 明确指引（装 OpenOCD 放 PATH / 设置页填路径 / 复制命令），不甩裸报错。
5. 产物缺失（未先编译）→ 中文提示「请先完成编译」。
6. 烧录失败 → 展示真实输出尾 + 常见排查（探针连接 / 供电 / 板在 DFU 状态）提示。
7. 烧录中 UI 明确「烧录中…」状态与按钮防重。
8. 设置页可配置三个烧录工具路径（与 uv4/make 同款），自动探测到则显示「已自动找到」。

## 实现决策

- `flash.py`（新模块，纯确定性，不 import llm——与编译/烧录无 LLM 参与一致）：
  - `resolve_flash_tool(platform, config) -> FlashTool | None`（dataclass: kind/exe/args 模板/command/display）；DSLite 扫描 `_CCS_SCAN_ROOT` 同款 glob（`C:/ti/ccs*/ccs/ccs_base/DebugServer/bin/DSLite.exe`，复用 compile_runner._CCS_SCAN_ROOT 思路，独立常量不 import compile_runner 防环？——compile_runner 无环问题，直接 import 常量亦可，按 review 定）。
  - `find_firmware(output_dir, platform) -> Path | None`（hex：rglob `*.hex` 最新；out：rglob `*.out` 最新，跳过备份目录）。
  - `find_ccxml(output_dir) -> Path | None`（rglob `*.ccxml` 最新）。
  - `build_flash_command(tool, firmware, output_dir) -> list[str]`（三 builder 单测断言精确参数）。
  - `run_flash(...) -> dict`（subprocess.run timeout=180 capture；出口码 0 = ok；输出尾 40 行）。
  - 探测 DSLite 版本打印不解析（v1 不做版本门槛）。
- config.json 新键：`openocd_path` / `stflash_path` / `dslite_path`（空 = 自动）。
- webapp：`POST /api/flash` `{output_dir}` → 平台推断（复用 context_manifest._infer_platform）→ 定位产物/工具（缺失 400 中文）→ run_flash → `{ok, tool, command, firmware, output, message}`；SSE 不需要（秒级~分钟级，前端 busy 文案足够，观察后按需升级）。
- 前端：
  - 按钮位置：`tasksRenderResult`（任务结果面板，烧录按钮放备份行内）+ 生成结果面板（generate-core 结果区，同位置）。
  - 点击：busy 防重 + 「烧录中…（XDS110/ST-Link，请确认连接）」→ 结果行（✓ 已烧录/✗ 失败/指引卡）+ 输出明细（可折叠）。
  - 工具缺失指引卡：平台对应安装说明 + 设置页跳转 + 「复制烧录命令」。
- 测试决策：`tests/test_flash.py` 单测（定位/三 builder/探测覆盖优先/缺失/run 成功失败超时——patch subprocess）+ webapp 集成（fake tool 注入 config 覆盖）；纯确定性、无 LLM seam；前端 JS 测试补 fx 纯函数（命令/指引文案）。
- 范围外：编译后自动烧录；串口 ISP / UART BSL 路线（ST 蓝药丸 BOOT0、MSPM0 BSL 排针——DP v1 不做，留指引文案提及）；Keil/CCS GUI 内嵌下载；DSLite identifyProbe 硬件探测（v2 候选）。

## 10 条用户故事清单（上文 8 条）
（见上文，规格层面即这些）
