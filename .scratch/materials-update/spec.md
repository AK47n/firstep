# 资料库大发版：增量更新包 + 软件更新器式选择弹窗

## 问题陈述

应用内一键更新（auto-update）只覆盖小发版：代码与四个库（模块库 / 母版库 / 赛题库 / 参考文件库，约 0.4 GB，git 内）。而 `sources/materials` 电赛资料库（本地实测 5.68 GB、10 个顶级目录批次，gitignore 不入库、随完整包分发）一旦有增删改，就是「大发版」：用户必须去 GitHub Releases 手动下载 4 个 7z 分卷（`firstep-full.7z.001~004`）→ 需 7-Zip 解压 → 再跑 install.bat。网页上的「软件更新」对资料库无能为力，只提示「去 Releases 下载完整包」。（`sources/contest`、`sources/car` 是 git 跟踪内容，走小发版，不在本 spec 范围。）

用户此前设想：像软件更新器一样，**弹出选择窗口**面对这类几 GB 的大更新——先看到更新内容与总量，可以选择下载或稍后，下载时看到进度，不用手动下分卷、不用装 7-Zip、不用动 install.bat。本次把该设想落地，并让它尽量只传「真正变化的部分」。

## 方案

把资料库发布从「每次 6 GB 完整包」升级为「基线清单 + 增量分卷」，并在工具内提供软件更新器式的下载弹窗：

- **发布侧**：新增资料库打包脚本。它保存/发布一份「资料库清单」（manifest：版本 + 每批次文件集的相对路径 / 大小 / SHA256），发布新版本时与上一版清单做 diff，只把**新增 / 修改**的文件按批次打成 zip（增量包，zip 格式，单批次超 1.9 GB 自动拆多分卷，均低于 GitHub 单资产 2 GB 上限），并把**删除**列表写进清单；每版随 Release 发布新清单作为下一版的基线。zip 用标准库可解，用户不再需要 7-Zip。没有历史基线时（首次引入）支持「初始基线」模式：只生成清单不打包，或「全量」模式：把当前资料库完整打成批次分卷包。
- **用户侧（网页）**：设置页新增「资料库更新」区。检查更新时读取本地基线清单（存在 `sources/materials/.materials-manifest.json`）并与线上最新清单对比 → 发现新版 → **弹出选择窗口**：列出版本信息、每个批次（顶级目录）的名称、变更文件数（新增 / 修改 / 删除）与增量大小，提供勾选子集（默认全选）与「一键全选」，底部显示已选总大小与磁盘空间校验；确认后开始下载。
- **下载与进度**：后端后台任务逐分卷下载（webapp 进程内线程，不阻塞请求），每卷从 Content-Length 算字节进度，轮询接口显示**总进度条 / 当前卷 / 速度 / 剩余时间**；**分卷级断点续传**（已下载且 SHA256 校验通过的卷持久化标记，取消、失败、重启后重试自动跳过）；失败 / 取消后已完成的卷不重下。
- **应用**：全部所选卷下载并校验完成后，应用阶段在 webapp 进程内完成（资料库是数据不是运行代码，无需停机重启）：zip 条目逐条路径安全校验（zip slip 整体拒绝，规则同小发版更新器）→ 将被覆盖 / 被删除的旧文件备份到用户数据目录 `updates\materials-backup\<时间戳>\` → 解压覆盖 → 按删除清单删除（路径校验落在资料库根内）→ 写入新基线清单（`.materials-manifest.json`）。
- **版本与部分更新**：资料库与软件**独立版本**，Release tag 形如 `materials-v1.1.0`（与软件 tag `v1.0.0` 互不干扰）；检查走 GitHub releases 列表接口并按 `materials-` 前缀过滤，不依赖 `releases/latest`。本地基线按**批次粒度记版本**（`.materials-manifest.json` 内 `batches: {slug: version}`），勾选子集 = 只更新选中批次、其余批次基线不变，下次检查只提示未更新的批次。
- **无基线的降级**：本地 `sources/materials/.materials-manifest.json` 缺失（老完整包用户）= 无法算增量 → 前端明确提示「资料库版本未知，无法增量更新；请下载完整包，或联系发布者提供初始基线」，不猜测、不强行全量。

## 用户故事

1. 作为完整包用户，我想要资料库更新时在网页上看到「发现资料库新版本」弹窗（含版本号与总增量大小），以便不用去 GitHub Releases 手动找文件。
2. 作为用户，我想要弹窗按批次列出本次变更（名称、新增 / 修改 / 删除文件数、增量大小），并可勾选只下载需要的批次，以便 6 GB 级大盘子只取自己要的部分，也便于按批次分批下载。
3. 作为用户，我想要「一键全选」与「稍后再说」，以便与软件类更新弹窗习惯一致。
4. 作为用户，我想要下载时有总进度（已下 / 总量 / 速度 / 剩余时间）与逐卷状态，以便几 GB 下载过程心里有数，不担心页面卡住。
5. 作为用户，我想要下载失败、取消、重启后重试时已经下好并校验通过的卷不再重下，以便弱网环境不至于从头再来。
6. 作为用户，我想要下载完成自动解压落位、备份被覆盖的旧文件、按清单删除废弃文件，以便全程不用 7-Zip、不手动操作 sources\materials。
7. 作为用户，我想要资料库更新完成后本地基线随之更新、之后只收增量，以便后续更新都是「只传变化的部分」。
8. 作为用户，我想要无基线或磁盘空间不足、下载失败、校验失败时得到中文提示与可重试入口，以便知道怎么处理、页面不崩。
9. 作为发布者，我想要一条命令打出资料库增量包（按批次 zip + 分卷 + 清单 + 删除清单 + 校验和），以便发版流程自动、可复现。
10. 作为发布者，我想要首次引入时能生成初始基线清单（或选择全量打包），以便老资料库也能平滑接入增量机制。
11. 作为用户，我想要资料库更新不动软件本体、配置与四个库，以便与「小发版更新」互不干扰，随时可略过。
12. 作为用 git 克隆的用户，我想要原有 git pull 与完整包路径继续可用，以便不受影响。

## 实现决策

- **资料库版本独立**：Release tag `materials-vX.Y.Z`，与软件 tag 并列；检查端点从 GitHub `releases` 列表（per_page 上限内）过滤 `materials-` 前缀取最新，不做 `releases/latest`。资料库版本号只在资料库变更时递增。
- **清单（manifest）契约**（发布侧产物与用户侧本地基线的同一格式，JSON）：
  - 顶层：`version`、`published_at`、`batches: [{slug, name, files: [{path, size, sha256}], removed: [path], parts: [{zip_name, size, sha256}]}]`；`slug` = 顶级目录名的稳定 ASCII 化标识（同目录名，中文用固定映射；新增目录须在发布侧登记 slug），`files` 为该批次全量文件集（含未变更文件，作下一版 diff 基线），`removed` 为自上一基线起删除的文件相对路径，`parts` 为本次批次增量 zip 分卷（未变更批次 `parts` 为空）。
  - 用户侧本地文件名固定 `sources/materials/.materials-manifest.json`（发布侧扫描时排除自身）；线上资产名 `firstep-materials-<tag>.manifest.json` 与 `firstep-materials-<tag>-<slug>.zip`（分卷追加 `.part<N>`）。
- **发布侧打包逻辑**（Python 核心模块 + PowerShell 薄封装脚本，UTF-8 with BOM；工具目录 `tools\`）：
  - 三种模式：`-Diff`（给上一版清单或 GitHub 自动拉取 → diff → 批次 zip + 新版清单）、`-Init`（只生成当前快照清单，不打包）、`-Full`（无基线全量打批次分卷包）；单批次 zip 超 1.9 GB 自动拆 `part<N>`（GitHub 单资产 2 GB 上限留余量），每 part 独立 SHA256。
  - 清单 SHA256 计算与 diff 逻辑纯函数化，可单测；扫描时跳过 `.materials-manifest.json` 自身与备份/临时噪音。
- **用户侧模块**（`src/contest_generator/` 下新模块，webapp 端点薄调，可注入 fetch / download 函数便于测试不碰网络）：
  - `GET /api/update/materials/check`：读本地清单（缺失 = `baseline_missing` 降级提示）→ 拉线上最新清单 → 按批次 diff（本地批次版本 vs 线上版本）→ 200 级返回 `{current_version, latest_version, update_available, total_size_bytes, batches: [{slug, name, add_count, modify_count, del_count, size_bytes, parts: [{zip_url, size_bytes, sha256}]}], error, message}`；网络 / 解析失败一律 200 级 + 中文 message（沿 auto-update 契约风格）。
  - `POST /api/update/materials/apply`：校验所选批次 slug 集合（白名单 = check 返回的批次，防注入）→ 校验目标磁盘剩余空间 ≥ 下载总量 + 备份余量（不足 400 中文）→ 启动后台下载任务（线程）→ 返回 `started`。
  - `GET /api/update/materials/status`：后台任务内存态 + 落盘节流快照（`updates\materials-task.json`，每 ~2 s 持久化一次，重启可恢复）→ `{state: idle|downloading|applying|done|failed|partial, current_part_name, parts: [{name, downloaded_bytes, total_bytes, ok}], total_downloaded_bytes, total_bytes, speed_bps, error, message}`；`partial` = 只更新了部分批次（用户勾选子集时属正常终态）。
  - `POST /api/update/materials/cancel`：置取消标记，任务在分卷边界停止；已完成卷标记保留（断点续传）。
  - **应用器**（模块内独立函数，临时目录可集成测试）：zip 条目路径校验（`..` / 绝对路径 / 盘符前缀 / 反斜杠一律整体拒绝，规则同 `tools/update-app.py`）→ 备份将被覆盖与将被删除的旧文件到 `updates\materials-backup\<时间戳>\`（保留目录结构）→ 解压覆盖资料库根 → 按 `removed` 删除（同样路径校验）→ 写回新 `.materials-manifest.json`；应用异常保留备份并中文报错，已完成部分不重复下载（卷级校验）。
- **前端**：设置页「软件更新」卡下方新增「资料库更新」区（当前版本行 + 检查按钮 + 结果区）。发现新版本 → 弹窗（复用 `.ref-files-overlay` 模态骨架，新容器样式）：版本头 + 批次勾选列表（名称 / 变更文件数 / 增量大小 / 勾选）+ 全选 / 反选 + 底部已选大小与「开始下载 / 稍后」；下载中改弹窗为进度（总进度条 + 当前卷 + 速度 + 剩余时间 + 后台继续 / 取消）；完成 / 失败中文结果；`baseline_missing` 与空间不足显示明确指引。纯函数（勾选聚合、进度 HTML、状态文案）走 `fx/`，DOM 胶水走 `ui/`，与 auto-update 同构。
- **与现有机制的关系**：资料库更新独立于小发版更新（不碰工具本体、不重启、不动四个库）；完整包（7z 分卷）路径保留，作为无基线 / 全新安装渠道；`docs/agents/releasing.md` 更新发行步骤（tag 命名、打包命令、资产上传、清单随包发布）。
- **超大文件说明**：大于 100 MB 的第三方安装包 / 固件镜像仍按现状以原样二进制放资料库（不在 git），增量机制对它们无特殊处理（改了就进增量包，没改就不传）。

## 测试决策

- 发布侧核心（Python 纯函数）：清单生成 / diff（新增 / 修改 / 删除三态）/ 批次分组 / 1.9 GB 分卷拆分 / 扫描排除自身；对全量与增量模式各一组 fixture（临时目录造小资料库树）。
- 用户侧 check：注入假 fetch（GitHub 列表响应 + manifest 文本）→ 断言对比逻辑、`baseline_missing`、无新版、网络失败降级、批次差异计算（既有先例：`tests/test_update_check.py`）。
- 应用器：临时目录集成测试——构造迷你资料库（旧基线 + 改一个文件 / 增一个文件 / 删一个文件）→ 迷你增量 zip + 删除清单 → 断言：文件落位、备份生成、删除生效、新清单写回、包外文件原样；另测 zip slip（`../evil` 条目）整体拒绝、分卷 part 顺序应用。
- 后台任务 / 端点：monkeypatch 下载函数（仿 `tests/test_update_apply.py` 先例）→ 测卷级断点（第 1 卷成功、第 2 卷失败后重试只下第 2 卷）、取消、空间不足 400、非法批次 slug 400、status 各状态。
- 前端纯函数（`tests/js/`，node）：批次勾选聚合（全选 / 部分 / 总大小）、进度 HTML、状态文案、XSS 转义。
- 端到端冒烟：本机起临时 HTTP 服务模拟 GitHub 资产 + 迷你资料库 → webapp 完整走 check → 弹窗 → apply → 落位（参照 auto-update e2e 先例，可做脚本化或手动清单）。

## 范围外

- 单卷内部的 HTTP Range 断点续传（只做**卷级**断点；发布侧分卷 ≤ 1.9 GB 已控制单卷重下代价）。
- 资料库文件与本地磁盘的实际一致性校验（用户手动增删改资料库文件不被检测——资料库视为只读数据；增量只信清单）。
- 自动下载 / 后台静默更新（更新必须经用户显式点击，与 auto-update 一致）。
- 完整包 7z 打包流程本身的改动（其内容可能新增 `.materials-manifest.json`，属发布侧辅助动作，随 releasing.md 说明）。
- macOS / Linux。
- 多版本跳级（用户基线落后不止一版时：直接以线上最新清单为基线做 diff，中间版本不需要——清单是全量快照，天然支持跳级；无需逐版应用）。
- 资料库回滚 UI（失败仅保留备份位置提示，同 auto-update 语义）。
- 中文目录名 slug 的自动化：一次性登记映射表，新目录需人工补记（低频动作）。

## 补充说明

- zip 格式决策的理由：标准库 `zipfile` 可解压，用户侧无需安装 7-Zip（完整包路线仍用 7z，因历史与压缩率，不受影响）；资料库增量 zip 单批次 ≤ 1.9 GB 分卷控制 GitHub 单资产上限。
- 本地基线清单几 MB（全量文件集）可接受；随资料库本体存放在 `sources/materials/` 下，随完整包 / 增量更新自然延续。
- 首次引入时的存量用户：无 `.materials-manifest.json` → 提示走完整包或联系发布者获取「初始基线」；发布者可先用 `-Init` 在自己机器生成并随下一版完整包分发，存量用户下次即可增量。
- 测试接缝沿用仓库既有先例：check 用注入 fetch、端点用 monkeypatch、前端用 node 纯函数测试，全链路仅新增一个「临时 HTTP 资产服务」小工具（测试用，不发布）。
