# 01 — 启动器版本一致性判据：端口上那个服务是旧进程就踢掉重起

**要做什么：** 让「更新换完文件后重新打开工具」这一步拿到**新版本**：启动器在确认端口上确实是自己
的应用之后，再比一次版本——服务版本**小于**盘上版本 → 判旧进程 → 按既有停服纪律踢掉 → 走原本的
起服务路径。用户可观察结果：更新完成后打开的就是新版，不必自己关掉再重开。

**被谁阻塞：** 无——spec 已拍板（`.scratch/update-restart-stale-service/spec.md`）。

**状态：** resolved（2026-09-19）

**完成记录。** 修法按 `spec.md` 拍板落地（②：启动器版本一致性判据），并随 **v1.2.1 资产重发** 出去
（同 tag 换资产，见工单 02）。修的过程里又抓出**两处只有真跑才看得见的问题**，都属于本单：

1. **判据静默不执行**：`for /f` 少了 `usebackq`，反引号被 cmd 当成**文件名**，循环一次都不跑 →
   启动器照旧走 `already_running`（第一次重发后真机演练就是这么红的）。修 + 加静态/行为/判据强度三层守卫。
2. **起服务前数据目录不存在**：`:start_service` 把日志重定向进 `%USERPROFILE%\.contest_generator\`，
   目录不在时 cmd 报「系统找不到指定的路径」、整行不执行 → 服务根本起不来（`launcher.log` 记
   `timeout`、`webapp.log` 压根没有）。真机上这个目录由 `install.bat` 的 bootstrap 配置保证存在，
   但启动器不该依赖别处先建好 → 加一行条件 mkdir。

真机验收（脚本零改动）：`served = 1.2.1`、`restarted_by_updater = true`，
`launcher.log` = `reason=started tries=1 port=8020 stale=1 served=1.1.1 disk=1.2.1`。
判据强度探针 **9/9 注入全部转红**；全仓测试 4556 passed / 1 skipped。

## 背景（本单就是这么发现的，别丢）

沙箱真机演练 B1（`sandbox-drill/01`，2026-09-18 22:40，脚本 `.scratch/verify-gate-drills/drill-01-upgrade.py`）
把这条链真跑了一遍：

| 环节 | 实测 | 判据 |
|---|---|---|
| 检查更新 | `latest=1.2.1 size=304729724 sha256=ec9921fc…` | ✅ |
| 真下载 + 校验 | 304,729,724 B，14.65 MB/s，sha256 与线上清单一致 | ✅ |
| 替换 | 落位 4329 文件、删 727、备份 4312、盘上 `__init__.py` = **1.2.1** | ✅ |
| **跑起来的服务** | `GET /api/health` → `version = 1.1.1` | ❌ |
| 重启 | `launcher.log` 只有 `reason=already_running port=8020`（认为「已在运行」，只开了浏览器） | ❌ |

根因链：发起更新的那一代（v1.1.1）拉起更新器时**没传 `--port`** → 更新器按默认 8000 停服
（`updater.log`：「端口 8000 无监听进程，跳过停服」）→ 旧进程还占着端口 → 更新器换完文件调启动器 →
启动器看到 `/api/health` 应答且 `app == contest-generator` → 判「已在运行」→ 只开浏览器。

**射程更正**（详见 spec「补充说明」）：更新器默认端口与普通用户的端口都是 8000，**两边默认值相同
→ 停服停对了**；本缺陷只在端口 ≠ 8000 时咬人（沙箱 8020；同机双实例更糟：会把 8000 上用户正在用的
那个停掉）。且只有小发版这条路缺 `--port`（v1.1.1 的完整包路径是传的）。

## 验收标准

- [x] `src/contest_generator/update.py` 有纯谓词 `is_stale_service(served, on_disk)`：语义比较、
      复用 `compare_versions`、非合法 semver 一律**不下判断**（False）；单测覆盖
      真旧 / 相等 / 服务更新 / 空串 / 非 semver / `v` 前缀 / `1.10.0` vs `1.9.0` 七类，
      且反向注入（改成 `<=`、改成字符串比较）必须转红
- [x] `tools/launcher-stale.py`：`--port P` → stdout **恰好一行**，三选一
      `stale stale=1 served=<旧> disk=<盘上>` / `fresh served=… disk=…` / `unknown`；
      任何异常、身份不符、health 缺 version、非法 semver 都是 `unknown` 且退出码 0；
      契约测试用**进程内 HTTP 桩 + 真子进程**覆盖四种 unknown 路径与两种正常路径
- [x] `start-app.bat` 在「身份是本应用」分支后调用该 CLI，**只在 token 为 `stale` 时**走踢进程路径；
      判据不在批处理里手写（不得出现版本字符串比较）
- [x] 踢进程：作用域 = `%FIRSTEP_LAUNCHER_PORT%`，只在身份已确认的分支里发生，踢完等一拍
      （`ping -n 2`，不得用 `timeout /t`）再走**原本的** `:start_service`
- [x] **留痕不新增 reason 码**：旧进程被踢记在 `started` 行的附加字段（`stale=1 served=… disk=…`），
      `already_running` 行同样带字段；`tools/launcher-log.ps1` 空值会让整行静默丢失，故取值前给初值
- [x] `tests/test_launcher_log.py` 全部既有判据**不动且全绿**（退出分支数仍 9、留痕调用数一一对应、
      码集合 == 码表、`.bat` 仍 GBK + CRLF 无 BOM）；`.scratch/launcher-failure-reason/` 的 spec 与探针**零改动**
- [x] `.bat` 新增静态守卫（新测试文件）：断言它调用了 CLI、只在 `stale` 时踢、作用域是端口变量、
      踢完回原起服务路径；并断言启动器里**没有**手写的版本比较
- [x] 既有内容断言全绿：`tests/test_onboarding_docs.py`（`/api/health` / `Popup` / `启动失败` / `.venv` 优先）
- [x] 全仓测试跑一次绿（`python -m pytest -n auto -q`）
- [x] 提交（中文提交信息；`.bat` 的 GBK 编码不得被编辑器改坏）
