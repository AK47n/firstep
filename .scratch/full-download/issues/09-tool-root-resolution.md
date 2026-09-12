# 09 — 沙箱真机演练抓到的三处路径缺陷（工具根判定）

**要做什么：** 把「源码直跑」（`start-app.bat` 起服务的方式）下的工具根判定统一，
让更新器路径、资料库基线路径、版本记录路径三处都指向真正的工具根，而不是 `<根>/src`。

**背景（真机演练实测）**：本机建了一个「模拟用户机」沙箱（`Desktop\firstep-sim`
+ 独立数据目录 + 端口 8020），用**线上真实的 v1.1.0 完整包**走了完整链路。
三处缺陷全部现形，其中前两处是**用户必踩**的：

| # | 现象 | 根因 | 影响 |
|---|---|---|---|
| 1 | 更新器秒退：`can't open file '<根>\src\tools\update-app.py'`，而编排报成功 | `webapp.tool_root()` = `parent.parent` → `<根>/src` | **用户点「一键全量」＝下载 783 MB 后什么都没发生，还显示成功** |
| 2 | 全量落位后资料库检查仍报 `baseline-missing` | `materials_update.materials_library_dir()` 同款推导 → `<根>/src/sources/materials` | **「全量一次之后转增量」的核心收益失效**（每次都被要求下完整包） |
| 3 | 版本更新记录读不到（前台空态） | `webapp` 里 `parents[2]/VERSIONS.md`、`changelog.__main__` 同款推导 | 用户看不到版本要点；CHANGELOG 补录写错位置 |

诱发条件：`start-app.bat` 里 `set PYTHONPATH=src` —— 这正是**用户机的标准启动方式**，
不是边缘场景。

**被谁阻塞：** 无——已修复。

**状态：** resolved

- [x] 新增工具根判定单源 `tool_root.find_tool_root`：候选 `包的上级 / 上级的上级 / 再上一级`，取**像工具根**的那层（有 `tools`/`library`/`sources`/`assets` 目录或根级启动脚本）；都不像则回退第一候选（站点包安装的既有行为不变）
- [x] 四处改为引用同一单源：`webapp.tool_root()`、`webapp` 的 VERSIONS.md 路径、`materials_update.materials_library_dir()`、`wordlist` 的源码模块库锚点、`changelog.__main__` 的根
- [x] 更新器**拉起前预检** `tools/update-app.py` 是否存在：不存在 → 拒绝并给中文原因，不再「起得来就算成功」
- [x] 单测 `tests/test_tool_root.py`（8 例）：仓库根判定、源码直跑布局、站点包回退、四个引用口径一致、词表锚点真存在
- [x] 单测 `tests/test_full_apply_paths.py`（6 例）：真工具根下命令路径正确、缺更新器脚本时拒绝且不起进程、URL 不被改坏、停服端口取环境变量
- [x] 沙箱真机复验：全量落位 8774 文件 → 基线写回 12 批次 / 5087 文件 → 重启后 `/api/health` 报 1.1.0 → 资料库检查读到本地版本 `v1.1.0`（不再是 baseline-missing）

## 附：同一轮演练抓到的另一个真缺陷（已修，工单 08 相关）

`load_full_manifest` 收 URL 时按 `str(路径)` 判前缀，而 **Windows 上 `Path("https://a/b")`
会把 `//` 折叠成 `\`**（实测 Python 3.14）→ `https://` 变成 `https:\` → 判成"本地路径"
→ `[Errno 22] Invalid argument`。修法：该参数**全程保持 str**，绝不过 `Path`；
`UpdateOptions.full_manifest_location: str` 与 `build_updater_command` 同步改；
新增三条回归（URL 原样送达 / 走网络分支 / 反斜杠形态大声报错）。

## 附：停服端口必须显式传（已修）

更新器默认端口 8000，**同机上可能有另一个实例**：沙箱的更新器把用户在 8000 上
正在用的实例停掉了（本次演练真实发生，随后已恢复）。修法：
`full_apply.resolve_launcher_port()` 读 `FIRSTEP_LAUNCHER_PORT`（与启动器/服务端同源），
非法值回落 8000；命令行显式 `--port`。

## Comments

- 相关工单：`08`（跨包换行符一致性 + 空删除清单注释行）——发布侧遗留，与本单无关。
- 沙箱构建脚本：`.scratch/full-download/make_sim_sandbox.py`；演练与验证脚本同目录
  （`trigger_and_watch.py` / `verify_sim_after_update.py` / `repro_url_arg.py` / `dump_resolution.py`）。
