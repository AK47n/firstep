# 应用内一键更新（小发版更新包 + 检查更新 + 一键更新）

## 问题陈述

普通用户（完整包 / 安装包渠道，没有 git）的更新路径现状：等新完整包（6.2 GB、4 个 7z 分卷）全部重新下载 → 重新解压 → 再过一遍 install.bat。而真正高频变动的其实是**代码与四个库**（模块库 / 母版库 / 赛题库 / 参考文件库，共 5290 个 tracked 文件、约 0.4 GB，全部在 git 仓库内），它们却因为「发版 = 发布完整包」的约定被绑在 6.2 GB 后面。用户希望像装应用一样直接更新：在工具里检查更新、一键下载更新包、自动完成替换并重启，不动配置、不动资料库、不需要卸载重装。

## 方案

把发布拆成两级：

- **小发版（代码 / 库 / 文档变更）**：发布一个轻量更新包（单 zip，几百 MB 以内，不限 2 GB 附件上限问题），工具内置「检查更新」（比对 GitHub Release 与本地工具版本）与「一键更新」（下载 → 校验 → 停服 → 覆盖 → 按清单删除 → 按需装依赖 → 重启）。
- **大发版（`sources/materials` 资料库增删改）**：维持现状，发 6.2 GB 完整包，低频。

用户更新体验：设置页看到当前版本 → 点「检查更新」→ 有新版则显示版本号 / 大小 / 更新说明 → 点「一键更新」→ 进度与结果提示 → 自动重启并回到更新后的工具。配置（DeepSeek key、任务状态、对话记录等全部在 `%USERPROFILE%\.contest_generator\`，工具目录之外）在更新后原样保留。

## 用户故事

1. 作为用完整包的用户，我想要在设置页看到当前工具版本号与最新版本号，以便知道工具是否陈旧。
2. 作为用户，我想要点「检查更新」就知道有没有新版，以便不依赖 GitHub Release 页面。
3. 作为用户，我想要一键更新，以便更新完不丢 DeepSeek key、任务状态与配置。
4. 作为用户，我想要更新不碰 6.2 GB 电赛资料库，以便更新下载快、不占额外下载时间。
5. 作为用户，我想要更新完成后自动重启继续用，以便不用手动"停服 / 解压 / 重装"。
6. 作为用户，我想要网络不可达 / 下载失败 / 校验失败时有中文提示，以便知道怎么处理。
7. 作为用户，我想要更新失败时旧版本仍可用，以便一次失败的更新不至于毁掉工具。
8. 作为发布者，我想要一条命令打出更新包（含文件清单、删除清单、校验和），以便发版流程自动、可复现。
9. 作为发布者，我想要更新包不含 `.scratch`（本地跟踪器）、`.venv`、`sources/materials`、`.git`，以便包小且不外泄内部工作目录。
10. 作为开发者，我想要工具版本号与 Release tag 一致，以便比对逻辑可靠（现状 `__version__` 与 README 声明不一致，属已知债务）。
11. 作为用 git 克隆的用户，我想要原有 `git pull` 更新路径继续可用，以便不受影响。

## 实现决策

- **工具版本唯一出处**：`src/contest_generator/__init__.py` 的 `__version__`；`pyproject.toml` 的 `project.version` 为打包元数据副本，发版时两处同步（现状两处均为 `1.0.0`，已对齐 v1.0.0 Release）。发版流程（releasing.md）新增步骤「打 tag 前同步 `__version__` / `pyproject.toml` version / README『当前版本』」。
- **更新包契约（发布侧产物，4 个文件，ASCII 文件名）**：
  - `firstep-update-<tag>.zip`：仓库 tracked 快照（`git archive` 生成），zip 内顶层 = 仓库根；内容 = 顶层白名单（src / library / sources / tests / docs / assets / tools / .githooks / 根级配置与脚本，含 `VERSIONS.md`），**不含** `.scratch`、`.venv`、`sources/materials`、`.git`、日志。
  - `firstep-update-<tag>.files.txt`：zip 内文件清单（相对路径，每行一个）。
  - `firstep-update-<tag>.removed.txt`：自上版基线（上次发布的 files.txt）起被删除的文件（每行一个）；首次发布无基线 = 空清单，更新器跳过删除。
  - `firstep-update-<tag>.sha256.txt`：zip 的 SHA256。
- **检查更新**：新增后端端点 `GET /api/update/check` → 请求 GitHub Releases API（repo `AK47n/firstep`，latest release + assets 列表）→ 与本地 `__version__` 比对 → 返回 `{current_version, latest_version, update_available, zip_url, size_bytes, sha256, release_notes, published_at}`；`sha256` 由服务端读取配套 `.sha256.txt` 资产内容得到（apply 时前端回传，运行时只下 zip、不下校验文件，避免用户漏下配套文件）；GitHub 不可达 / 无网 → 中文提示「检查更新失败（网络原因）」，不 500。版本比对纯函数化，容忍 `v` 前缀；任一侧非合法 semver 时降级为字符串比较 + 中文提示，不 500。
- **一键更新编排（关键决策：替换动作绝不在运行中的 webapp 进程内执行）**：
  1. 前端点「一键更新」→ `POST /api/update/apply` → 服务端把 zip 下载到用户数据目录的 `updates\` 子目录（与 config.json 同级），校验 sha256；
  2. 写「待更新标记」（pending-update.json：zip 路径、版本、removed 路径、状态）；
  3. 以**独立进程**调起更新器（不通过 webapp 进程做替换）；
  4. 更新器：停服务（8000 端口 LISTENING → 先 `/api/health` 确认 `app == "contest-generator"` 再 kill，避免误杀他人）→ **zip 条目安全校验**（解压前逐个校验条目路径解析后必须在工具根内，`../` / 绝对路径 / 盘符前缀一律整体拒绝）→ 解压 zip 覆盖工具根（`.venv` / `.contest_generator` / `sources/materials` 不在包内 = 天然保留；zip 内条目直接覆盖；**覆盖前将本次将被覆盖的条目备份到 `updates\backup\<时间戳>\`**，失败提示保留备份位置，不做自动回滚）→ 按 removed.txt 删除（删除前同样校验路径落在工具根内）→ 依赖变更检测（**对比覆盖前旧 `pyproject.toml` 与覆盖后新 `pyproject.toml` 的 SHA256，变了才 `pip install -e .`**——自包含、无隐式「上次安装记录」状态；解释器 `.venv\Scripts\python.exe` 优先、系统 Python 兜底）→ 全流程日志写 `updates\updater.log`（失败摘要含备份位置与该日志路径）→ 清标记 → `start-app.vbs` 重启。
  - 更新期间保护：写「更新中」标记（`updates\updating.lock`），start-app.bat 检测到则弹窗提示「更新进行中，请稍候」；更新器异常退出留下 `pending-update.json` 时，启动器弹窗提示手动处理方式（归入前端/启动器工单）。启动器检查顺序：先 `updating.lock` → 再 `pending-update.json` → 最后走既有端口探测逻辑。
- **更新器形态**：Python 脚本（标准库 + zipfile 即可，不依赖第三方包；放 `tools\` 下独立入口 `tools/update-app.py`，由 `.venv\Scripts\python.exe` 运行），日志写 `%USERPROFILE%\.contest_generator\updates\updater.log`。
- **前端**：设置页「软件更新」区域 = 当前版本行 + 「检查更新」按钮 + 结果卡（最新版本 / 大小 / 说明 + 「一键更新」按钮）+ 进度（第一版用状态轮询端点，不做 SSE）+ 成功 / 失败中文提示。
- **API 契约新增**：`GET /api/update/check`、`POST /api/update/apply`（下载 + 校验 + 标记 + 拉起更新器）、`GET /api/update/status`（下载 / 应用进度轮询）。
- **发版流程（releasing.md）重写**：小发版 = 跑打包脚本 → 传更新包 4 件套 → 更新 `__version__` / README；大发版 = 完整包流程保留，可附带更新包。

## 测试决策

- `check` 端点：mock GitHub API 响应 → 断言比对逻辑、无可更新、不可达降级、`sha256` 随响应返回（既有先例：tests/ 下 webapp 端点测试）。
- 更新器：临时目录集成测试——构造迷你更新包（files / removed / sha256 三件套齐全）→ 目标目录放旧文件 + 用户数据 → 断言：zip 条目落位、removed 文件被删、包外文件（模拟 .venv / 资料库 / 用户数据）原样、备份生成；另测 zip slip（`../evil` 条目）整体拒绝、pyproject 变更触发依赖安装判定。
- 打包脚本：契约测试/验证——files.txt 与 zip 内容一一对应、removed 相对基线 diff 正确、sha256 可复算、zip 不含 `.scratch` / `sources/materials`、含 `VERSIONS.md`。
- 更新器只依赖标准库，spec 层面保证其可在无第三方包环境运行。

## 范围外

- `sources/materials` 资料库的增量 / 分块更新（仍走完整包大发版）。
- 自动下载 / 静默安装 Python（属于安装器规划，另议）。
- 断点续传、后台静默自动更新（更新必须经用户显式点击）。
- macOS / Linux。
- 安装器 / 自解压（SFX / Inno）本身——更新机制与安装器正交，将来安装器落地后复用本更新器。
- 自动回滚 UI（失败仅保留备份 + 提示备份位置）。

## 补充说明

- 更新包不含任何用户数据（配置全部在工具目录外的 `%USERPROFILE%\.contest_generator\`）。
- `VERSIONS.md`（面向用户的版本记录）是 tracked 根文件，必须纳入更新包白名单——否则小发版后工具内版本卡片丢失。
- 依赖变更检测不引入「上次安装记录」状态文件：以覆盖前后 pyproject.toml 哈希差异为准，更新器自包含、可重复执行。
- 本 spec 与「安装器 / 自解压窗口」（另议方案，上一轮讨论）的关系：更新功能先行落地；安装器做不做、何时做，由用户另行拍板，不影响本 spec 的独立性。
- 更新包与 git clone 的关系：`git pull` 路线保留，二者平级。
