# spec — launcher 可机读失败原因（start-app.bat 分支留痕）

**状态：** 已拍板（2026-09-12 会话：用户选「立单 + 实现 + 顺带把 E2 超时态真机复现收口」；
写日志方式选「powershell 内联 + 静态守卫」）。

## 问题陈述

用户在 Windows 上双击 `start-app.vbs`（内部跑 `start-app.bat`）启动本工具。启动失败时脚本会弹一个
中文弹窗说明原因，但**进程侧读不到弹窗正文**，只看得到一个统一的 `exit /b 1`：

- 做真机验收的 agent 无法判定「这次失败到底是哪一条分支」（第十六轮实测只能靠**退出码 + 计时**
  侧面猜：`:port_busy` ≈7s、`:timeout` ≈25s）；
- 结果是挂账单 E2 的第三态（`:timeout` 启动超时弹窗）自第十六轮起一直「留人工 / 需劣化环境」，
  每轮盘点都要重新判一次「无法判定」；
- 用户自己在另一台机器上遇到失败时，也只能看到弹窗，事后想复盘没有可读的证据（`webapp.log`
  只在「服务起来了之后」才有内容，`no_python` / `no_deps` / `port_busy` 这类根本不会产生它）。

## 方案

启动器每次跑完都往一个固定文件追加**一行机器可读的启动记录**：

`%USERPROFILE%\.contest_generator\launcher.log`

- 行形态 = `[ISO8601 带时区] reason=<分支码> ...`，**纯 ASCII key=value**（中文只留在弹窗里）；
- 覆盖**每一条**退出路径（成功也算一条），reason 码表固定、给后续脚本与人工共用；
- 失败弹窗正文里补一句「详情见 …launcher.log」，用户能自己找到证据；
- `:port_busy` 与「本应用已在跑」两种「8000 端口有东西在听」的形态**分开记**（前者 = 身份判定
  不是本应用，后者 = 就是本应用，属正常路径），否则这一族的读法永远是错的；
- 附带把各分支的退出码**钉成固定值**（原先是一条 `%errorlevel%` 链上的偶然值，不可依赖）。

## 用户故事

1. 作为**做真机验收的 agent**，我想要启动失败时能从 `launcher.log` 读到确切分支码，以便不再靠
   计时猜是哪一态、不再把「无法判定」挂成年复一年的尾巴。
2. 作为**用户**，我想要弹窗里直接告诉我日志在哪，以便把失败现场发给别人看，而不是只截一张弹窗图。
3. 作为**维护者**，我想要「每一个退出分支都必须留痕」这件事被测试钉住，以便以后加分支时不会
   悄悄漏掉一条（漏了就是又一条无法判读的失败）。
4. 作为**同一台机器上重复双击的用户**，我想要「本应用已经在跑」不被记成「启动失败」，以便读日志
   时不会把自己正常的第二次双击误判成故障。
5. 作为**排查端口问题的用户**，我想要日志里带上 8000 端口的实际身份判定结果，以便区分「别的程序
   占了端口」与「本应用已经在跑」。
6. 作为**以后要做超时第三态验收的人**，我想要 `:timeout` 这一态能在本机被稳定造出来，以便这一态
   从此可机器判读，而不是永远「留人工」。

## 实现决策

- **日志写入单源**：新增 `tools/launcher-log.ps1`（UTF-8 with BOM，仓库硬性约定），负责「取时间 +
  拼行 + 追加（UTF-8 无 BOM）+ 必要时建目录」，参数 = `-Reason` 与可选 `-Key=Value` 若干。
  `start-app.bat` 只能通过**调用这一支脚本**写日志（cmd 没有函数，同一行 powershell 会在各分支重复
  出现——重复的是「一次调用」，格式与落盘逻辑仍是单源）。
- **为什么不用 `python tools/launcher_log.py`**（备选被否）：`no_python` / `old_python` 两条分支
  本身就是因为 Python 不可用才走到，用 Python 记日志等于这两态永远没有留痕。powershell 是弹窗已经在
  用的依赖（`start-app.bat` 注释里写明「任何 Win10/11 自带」），一致且无新依赖。
- **日志文件路径**：与 `webapp.log` / `config.json` 同目录（`%USERPROFILE%\.contest_generator\`），
  不引入新的约定目录。
- **行格式（固定字段顺序，可扩展 key=value）**：

  ```
  [2026-09-12T01:30:00+08:00] reason=port_busy pid=12345 http_status=404 message=8000 not firstep
  ```

  - 时间戳 = `yyyy-MM-ddTHH:mm:sszzz`（带时区偏移，`datetime.fromisoformat` 可直接解析）；
  - `reason` 取自固定码表（见下）；其余 `key=value` 为可选细节；
  - 值里不得出现空格（用 `-` 连接），保证「按空白切词」的读法稳定；
  - 文件按**追加**语义（保留每次启动的历史），不是覆盖。
- **reason 码表**（cmake 风格小写下划线；一次写清，避免以后被当成新分支）：

  | reason | 含义 | 旧口径 |
  |---|---|---|
  | `updating` | 更新中锁在（`updates\updating.lock`） | `:updating` |
  | `update_left` | 上次更新未完成（`pending-update.json`） | `:update_left` |
  | `no_python` | 找不到 Python / 解释器跑不起来 | `:no_python` |
  | `old_python` | Python 版本低于 3.13 | `:old_python` |
  | `no_deps` | 依赖缺失（fastapi/uvicorn/pypdf/PIL/fitz） | `:no_deps` |
  | `port_busy` | 8000 有监听，但身份判定**不是**本应用 | `:port_busy` |
  | `timeout` | 服务 20 秒内未就绪 | `:timeout` |
  | `already_running` | 8000 上的就是本应用，只开一个浏览器标签 | 原走 `:open`（无痕） |
  | `started` | 本次真的把服务拉起来了并打开浏览器 | 原走 `:open`（无痕） |

- **端口身份三态（本次顺手把第三种读法补上）**：`/api/health` 返回 JSON 里 `app == "contest-generator"`
  且 `ok` 为真 → `already_running`（正常，exit 0）；返回了但身份不符（其他程序恰好也有 `/api/health`）
  → `port_busy`（exit 1）；请求失败 / 不是 JSON → **不是**「端口被占」，而是「8000 上没有本应用」，
  继续走 `:start_service`（保留今天的行为）。改动的只有「判读与留痕」，控制流本身不动。
- **端口可覆盖（本次为验收/测试新增的唯一「旋钮」）**：`FIRSTEP_LAUNCHER_PORT`（缺省 8000）。
  理由：`port_busy` / `timeout` / `started` 三态的造法都要占住 8000，而那正是用户正在用的会话；
  有了这个覆盖，验收与测试可以整体搬到一个空闲端口（本仓库取 8899），**不打断用户**。
  正常双击 `start-app.vbs` 不设这个变量 ⇒ 行为与改动前逐字一致。
  **取值校验两侧必须同口径**（`start-app.bat` 的 `findstr` 数字形态 + `gtr 65535` 回落；
  `webapp.resolve_port()` 的 `isdigit()` + 1..65535）：只盖一半会出现「launcher 轮询坏端口、
  服务绑 8000」的假超时（探针实测误判过 `started`），故两侧都由测试钉住。
- **端口身份判据（澄清 spec 初稿的一处自相矛盾）**：`/api/health` 能解析成 JSON **且**
  `app == "contest-generator"` → `already_running`；其余一切（请求失败 / 不是 JSON / JSON 但身份不符）
  → `port_busy`。**这是既有行为**（改动前 `start-app.bat` 就是 `if errorlevel 1 goto :port_busy`），
  本单只把它记进日志、没有改它的走向——初稿写成「请求失败/非 JSON → 继续起服务」与实现相反，
  以本节为准。（`ok` 字段只作旁证：真正区分身份的是 `app`，两个键都在同一份固定契约里。）
- **轮询的「睡一秒」改 `ping`（有意偏离「不改控制流」）**：原实现用 `timeout /t 1 /nobreak`，
  而 `timeout.exe` 在 stdin 被重定向（验收/测试环境无控制台输入）时会**立刻**报错退出
  （实测「不支持输入重新定向，立即退出此进程」）⇒ 20 次轮询预算瞬间烧光、把「服务没起来」
  误判成「启动超时」。改成 `ping -n 2` 后轮询节奏与真实机器一致（每次 ≈1s，总预算仍是 20 次），
  这也让 spec 原先记录的「`:timeout` ≈25s 计时判据」重新成立（实测 21s 轮询 + 收尾）。
- **退出码固定为 0/1 语义**：成功分支（`already_running` / `started`）= `exit /b 0`；所有失败分支
  = `exit /b 1`（**保持今天对外可见的语义不变**：第十六轮验收记录就是「失败 exit 1」，不引入 2/3/4，
  否则既有验收记录与文档会被追溯性地作废）。区分靠 reason，不靠码。
- **弹窗是验收纪律问题，必须在方案里说清**：失败分支的 `WScript.Shell.Popup` 是**模态**框，
  没人点确定就不返回。第一版实现把「真跑各分支」直接放进 pytest，结果两次在用户桌面上弹出一排框
  （用户两次截图报障）并让测试挂死 9 分钟。最终口径：
  1. 测试套里**只**跑不弹框的路径（成功分支 + static/helper 层），并且把 `SystemRoot` 指向一个
     **没有 powershell 的假 Windows**——弹窗宿主物理上不可能存在；
  2. 会弹框的四态（`updating` / `no_python` / `port_busy` / `timeout`）由**真机探针**跑，探针自带
     「标题含 firstep 的窗口一出现就按 pid 杀掉」的清扫线程 + 到点 `taskkill /T`，**框不留在桌面上**；
  3. 判读口径 = `launcher.log` 的 reason 行（launcher 在弹框**之前**就写好了），不是退出码；
     被强杀的进程退不出码，这一点在落盘里如实记账。
  三条拦框的替代方案已被实测证伪（PATH/PATHEXT 垫片对绝对路径无效；假 SystemRoot 放批处理桩报
  「不是有效的 Win32 应用程序」；放 `powershell.cmd` 不被查询，因为命令行带 `.exe`）——写进工单，
  免得后来者重走。
- **弹窗文案**：`no_deps` / `port_busy` / `timeout` 三条失败正文补「详情见 …launcher.log」
  （`no_python` / `old_python` 的正文保持指向 python.org / install.bat，不动）。
- **`.bat` 编码纪律**：`start-app.bat` 现为 GBK（无 BOM）、行尾 CRLF，`.gitattributes` 钉 `eol=crlf`。
  本次改动**必须保持 GBK 无 BOM**（cmd 按 ANSI 解析）；新增内容里的 `rem` 注释一律 ASCII，
  避免给自己造第二处编码坑。
- **测试缝（本仓库既有先例）**：`tests/test_onboarding_docs.py` 已经用「读 `.bat` 文本做结构断言」
  的门禁方式（`start-app.bat` 必须含 `/api/health` / `Popup` / `.venv\Scripts\python.exe`）。
  本次沿用同一层缝：**静态结构守卫**（每个退出分支必须留痕、码表必须被穷举引用、码表与 spec 表格对齐）
  + **守卫自身的回归**（拿合成 `.bat` 文本正反各跑一遍：漏留痕 / 表外新码 / 重复用码都必须红）
  + **helper 的行为测试**（真跑 powershell 写一行、解析它）
  + **端口覆盖同口径**（Python 侧函数 + `.bat` 侧校验）
  + **验收件的在位性**（真机探针与落盘必须在位、7 态判读、全 PASS、证据新鲜）。
  失败分支的真机断言只在探针里做（原因见下「弹窗是验收纪律问题」）。不再新增更低的缝。

## 测试决策

- 好测试的形态 = **只断言外部可观察事实**：日志里那一行的形状与 reason 值、`start-app.bat` 的
  退出码、以及「每个退出分支都被留痕」这一结构不变量。不断言 powershell 内部实现、不断言弹窗文本。
- 测试面（`tests/test_launcher_log.py`）：
  1. helper 形态：真跑 `tools/launcher-log.ps1` → 文件存在、UTF-8 无 BOM、行数按追加增长、
     时间戳能被 `datetime.fromisoformat` 解析、`reason=` 命中、key=value 可切词、值内无空格；
  2. helper 自建目录（日志目录不存在时不报错、自动建）；
  3. 静态守卫：`start-app.bat` 的**每一条 `exit /b`** 之前必须有一次 `launcher-log.ps1` 调用；
     各分支的 reason 码必须取自码表且**码表被穷举引用**（新增分支忘写 reason 即红）；
  4. 真机分支矩阵（劣化环境真跑，`USERPROFILE` 重定向到 tmp，零污染用户目录）：
     `no_python`（PATH 无 python）/ `port_busy`（8000 上放一个身份不符的健康端点）/
     `already_running`（真 webapp 在跑）/ `timeout`（服务启动被 PATH 垫片延迟到轮询窗口之外）。
- 既有先例：`tests/test_onboarding_docs.py`（`.bat` 文本门禁）、`tests/test_ps1_encoding.py`
  （ps1 必须 UTF-8 BOM）、`tests/test_repo_language.py`（中文/语言兜底）。

## 范围外

- **不**把 `start-app.bat` 的分支逻辑搬到 Python/服务里（启动器必须能在「Python 不可用」时工作）。
- **不**引入 2/3/4… 的差异化退出码（会作废既有验收记录；区分靠 reason）。
- **不**改端口号（默认为 8000；新增的 `FIRSTEP_LAUNCHER_PORT` 只是一个**缺省即等于现状**的验收旋钮，
  正常双击不设），不改「关掉最后一个标签页 = 停服务」的会话机制、不改更新的下载/应用链路。
- **不**给 `install.bat` 加同类日志（本次只治启动器；install 的失败面另说）。
- **不**做日志轮转/大小上限（每次启动一行，量级可忽略；真要做另立单）。
- **不**承诺 `:timeout` 在「真·慢机器」上的表现——本次只把**劣化环境下的可复现性**打通
  （这是 E2 第三态从「留人工」转「机器可判读」的前置，不是它的替代）。

## 补充说明

- 本单是 2026-09-18「待拍板六项」里第 ⑤ 条的落地（放行、另立单，不塞进验收挂账单）；素材是
  `.scratch/newcomer-onboarding/verify-16-E2-timeout-state.txt` 里六版尝试留下的三个可复用件
  （`fakebin/python.cmd` 门控垫片、`diag-trace-start-app.bat`、`e2-launch-job.ps1`）。
- 判据来源：第十六轮把两分支计时判据钉死（`:port_busy` ≈7s、`:timeout` ≈25s）是因为**当时没有
  可机读留痕**；本单落地后，判读不再依赖计时——计时只作为「脚本没跑起来」的兜底信号。
