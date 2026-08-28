# 01 — 后端：烧录模块（flash.py）+ /api/flash + 配置键

**要做什么：** 新的确定性烧录后端——工具探测（config 覆盖 > 自动）、固件/ccxml 定位、命令构建（openocd / st-flash / dslite 三条 builder）、执行（180s 超时、输出尾截断）、中文结果；webapp `POST /api/flash`；config.json 三个烧录路径键；tests/test_flash.py + webapp 集成测试。

**被谁阻塞：** 无（spec flash-deploy 已定）。

**状态：** resolved

- [x] flash.py：`FlashTool` dataclass（kind/exe/display）；`resolve_flash_tool(platform, config)`（openocd_path/stflash_path/dslite_path 覆盖 > which(openocd/st-flash) > C:/ti/ccs* 扫 DSLite）；`find_firmware(output_dir, platform)`（hex/out rglob 最新，跳过 .backup/revise-backups 类目录）；`find_ccxml`；`build_flash_command`（三 builder 精确参数：openocd `-f interface/stlink.cfg -f target/stm32f1x.cfg -c "program <hex> verify reset exit"`；stflash `write <hex> 0x08000000`；dslite `flash --config=<ccxml> <out> -u`）；`run_flash`（subprocess timeout=180 capture，exit 0=ok，输出尾 40 行，中文 message）。
- [x] config.py / settings：注册 `openocd_path` / `stflash_path` / `dslite_path` 三键（读取 + 写回，沿用 uv4/make 模式）。
- [x] webapp.py：`POST /api/flash` `{output_dir}` → 平台推断（context_manifest._infer_platform 复用）→ 产物/工具缺失抛 400 中文 → run_flash → `{ok, tool, command, firmware, output, message}`；docstring + errors.py 登记 FlashError。
- [x] tests/test_flash.py：artifact 定位（hex/out 最新、备份目录跳过）、探测（覆盖优先/自动/缺失 None）、三 builder 精确参数、run 成功失败超时（patch subprocess）、webapp /api/flash（fake 工具经 config 覆盖注入；产物缺失 400）。
- [x] 全量 pytest 绿（2643 passed）+ standards/spec 双轴 review（均通过；standards 判断项 2/4 已整改：`_iter_candidates` 补 `-> Iterator[Path]`、build_flash_command docstring 注明 output_dir 仅 dslite 用）。

**答复：** 已实现并合入（提交见 git log flash-deploy/01）。实现说明：①resolve_flash_tool 按 spec 语义实现但签名用三键路径参数而非整个 config（解耦，webapp 转调时取 config 字段）；②FlashTool 无 args/command 字段，命令组装在 build_flash_command（构建参数是工具能力不是工具属性）；③run_flash 返回 FlashRun dataclass，尾截断与中文 message 上移 flash_project；④测试用真实 subprocess（假 .bat 工具）而非 mock.patch——与 test_compile_runner 同型。评审观察整改：command_text 用 _join_command 对含空白参数加双引号（复制到 shell 可执行，工单 02 一并合入）。
