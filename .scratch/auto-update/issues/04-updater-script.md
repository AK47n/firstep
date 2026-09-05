# 04 — 更新器脚本（停服→备份→覆盖→删除→依赖→重启）

**要做什么：** 一个独立进程命令行工具，能把工具目录安全替换到指定新版本：停掉 8000 上的本应用服务、备份将被覆盖的文件、解压更新包覆盖、按删除清单清理、按需重装依赖、重启应用——全程不依赖运行中的 webapp。

**被谁阻塞：** 无——可立即开始（新增独立脚本文件，仅标准库 + zipfile，与代码查看器优化零文件交集）。

**状态：** resolved

- [x] 脚本可独立运行：入参 = 更新包 zip 路径（+可选 removed 清单、解压目标目录）；解释器 = `.venv\Scripts\python.exe` 优先、系统 Python 兜底（`pick_python`）
- [x] 停服：8000 端口 LISTENING 进程先经 `/api/health` 确认是 `contest-generator` 再结束（netstat -ano 解析 PID）；无从确认则拒绝并中文提示，不误杀
- [x] 覆盖前把本次**将被覆盖**的条目备份到 `updates\backup\<时间戳>\`（相对路径镜像），任何一步失败保留备份并在日志/提示中给出备份位置（不做自动回滚）
- [x] 覆盖 = 解压 zip 到工具根（zip 内条目逐个覆盖，先写 .update-tmp 再 os.replace 防半写）；`.venv`、`.contest_generator`、`sources/materials` 不在包内 = 天然保留
- [x] 按 removed.txt 删除已废弃文件（无清单=跳过）；删除前确认路径落在工具根内（safe_join）；**zip 条目解压前全量预检 zip slip（../、绝对路径、盘符、逃逸解析一律整体拒绝）**
- [x] 依赖变更检测：**对比覆盖前后 pyproject.toml 的 SHA256**（自包含，无「上次安装记录」隐式状态），变了才 `pip install -e .`（失败 = 中文提示 + 退出码，不静默）；解释器 .venv 优先
- [x] 结束：写结果记录 `last-update.json`（ok/failed + 版本 + 备份位置）→ 清「待更新标记」→ 调用 start-app.vbs 重启 → 打印结果摘要；全流程日志写 `updates\updater.log`
- [x] 集成测试（临时目录）：构造迷你更新包（zip/removed）→ 模拟旧树 + 用户数据 → 断言落位/删除/包外保留/备份四件事 + zip slip 拒绝 + pyproject 变更触发依赖安装判定（tests/test_update_app.py，7 项全绿）

## Answer

新增 `tools/update-app.py`（仅标准库：zipfile / urllib / subprocess / optparse；核心逻辑在 `run_update(UpdateOptions)`，`main()` 只做参数解析）。安全关键点：`safe_join` 拒绝 `..` / 绝对路径 / 盘符 / 解析逃逸，`validate_zip_members` 在写盘前全量预检；依赖检测用覆盖前后 pyproject.toml 哈希对比（比 spec 原来的「上次安装记录」更自包含）；`--no-stop / --no-restart / --skip-pip` 供集成测试。测试经 importlib 加载（须注册 sys.modules，否则 UpdateOptions dataclass 注解解析崩溃）。7 项全绿。
