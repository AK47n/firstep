# 04 — 账本与文档收尾（C6 的尾巴结清）

**要做什么：** 把这次换归属之后**变成假话**的旧描述改对，并把账记进该记的地方：`CONTEXT.md`
的一键全量下载词条、`full_task.py` 的两处「webapp 模块级单例」话术与 `set_full_task` 的
docstring、`backlog.md` 新增一节、`docs/agents/local-environment.md` 补本轮会话段。

**被谁阻塞：** 01、02、03

**状态：** resolved

## 验收标准

- [x] `full_task.py` 的两处「webapp 模块级单例」话术（模块级注释块、`FullDownloadTask` 类
      docstring）与 `set_full_task` 的 docstring「状态单源在本模块」（**那个函数才带这句话**，
      `set_last_check` 没有 docstring）**已随工单 01 改对**——删掉模块状态那一刻它们就成了假话，
      那时一并改的；本条**不重复做**，只核对
- [x] `CONTEXT.md` 一键全量下载词条：照 C6 给任务推进词条补
      `AppContext.running_task_execs` 的同款写法，把状态归属补明（含工单号）——写成
      `full_task.py（下载任务；**无模块级会话态**——check 结果与进行中的任务归
      `AppContext.full_last_check` / `AppContext.full_task`…工单 01；并发 apply 由
      `_full_task_lock` 收口，工单 02）`
- [x] `backlog.md` 新增 §18：做法（只换归属 + 补一把锁）/ 判据三处 / 红证与读数指针 / 剩余；
      并写明**C6 的尾巴就此结清**、架构评审候选到此全部结清（C7 只是验收尺、未立项）；同时把
      §17 末尾那条「剩余」补一句指向 §18
- [x] `docs/agents/local-environment.md` 补本轮会话段：本轮不起服务器、收尾端口实测（8000 /
      8020 / 8021 / 8791 与残留 python 进程）、读数（pytest / 前端门禁 / 结构钉单文件）、
      本轮量到的两条工具事实；**第 0 节的发布落差表不动**（本轮不进任何发布包）——与环境相同的
      框架句按同节已有先例「只记差异面」，不逐字重抄上一条
- [x] 零行为改动核对：`git diff --stat fe79f57b..HEAD -- src` **为空**（01/02 之后 src 零改动）；
      整轮 `git diff c6040566..HEAD -- src` 逐行核过 = **只有换归属 + 补锁 + 注释**，
      没有判定次序 / 文案 / 路径 / 载荷漂移；`tests` 的改动 = 换缝 + 三条行为判据 + 结构钉扩面
      （都是本计划内的真判据，不算漂移）
- [x] 双轴评审（固定点 = 01 之前那个提交 `c6040566`，两轴各一个并行子代理），结论落账；范围蔓延
      一条不留（C6 那次抓到的两条——判定次序被挪、顺手抽常量——本轮对照检查项：**都未发生**）
- [x] `python -m pytest -n auto -q` 全绿；`node --test "tests/js/*.test.mjs"` 全绿

## Comments

### 2026-09-22 21:5x 落地读数

- **三份文档**：
  - `CONTEXT.md` 一键全量下载词条：`full_task.py（下载任务）` → 补上状态归属与两条工单号
    （写法与同表「任务推进」词条里 C6 补的 `AppContext.running_task_execs` 同形）。
  - `backlog.md` §18（四段：问题 / 做法 / 判据三处 / 红证与读数 + 剩余），并在 §17 末尾补一句
    指向 §18；**剩余**一句写明架构评审候选**全部结清**、只剩 C7 这条验收尺。
  - `docs/agents/local-environment.md`：新增本轮会话段。与环境相同的框架句按同节先例
    （C6 段里已有「不重抄」的写法）**只记差异面**；本轮真正属于这台机器的新事实 = 不起服务器 /
    端口实测 / 三条读数 / 两条工具事实。**第 0 节发布落差表一字未动**。
- **零行为改动核对（读数）**：`git diff --stat fe79f57b..HEAD -- src` **为空**（03/04 没碰 src）；
  整轮 `git diff c6040566..HEAD -- src` 是 2 个文件 120 行，逐行核过 = 删掉模块级状态与四个
  accessor、端点改经 `context.*`、两段进锁、其余全是注释/docstring；前端
  `git diff c6040566..HEAD -- src/contest_generator/static src/contest_generator/static/index.html`
  为空（**前端零字节**）。
- **双轴评审**（固定点 `c6040566`，整轮）：
  - **Standards 轴**：硬违规 0（本轮在评的那条「工单状态未收口」随本条 resolve 闭合）；判断题
    处置一条：`local-environment` 新段落与相邻 C6 段的框架句逐字重复 → **按建议收成「只记差异面」**
    （事实本身无误：起服务器 = 否、四端口无监听、前端零字节）。另确认：`CONTEXT.md` 词条写法同形、
    `backlog §18` 四段 ≡ §17 格式、**全仓零旧话术残留**（`last_check(` / `get_full_task` 在 src /
    tests / docs / CONTEXT / CLAUDE 全零命中——只剩结构钉名单与历史说明里的**故意保留**）。
  - **Spec 轴**：无缺失、**范围蔓延无**（三处进程级缓存未动、`clear()+update()` 没被统一、
    `create_app()` 与模块级 `app` 照旧、没抽常量也没合夹具、前端零字节）；抓到的都是**记账**
    层面的错，逐条已修：
    ① **`backlog §18` 把强度探针的路径挂错**（写成 full-update 目录）→ 改指
    `.scratch/webapp-state-into-ctx/probe-02-guard-strength.py`，并把「归属错位」一并写明；
    ② 本工单验收第三条「`git diff -U0 -- src tests` 只应有 docstring / 注释级改动」**自相矛盾**
    （03 在 `tests` 里实加了 523 行真判据）→ 改写成「`src` 仅注释/换归属级改动；`tests` 的改动
    = 换缝 + 新判据」；
    ③ 本工单验收第一条把「状态单源在本模块」挂在 `set_last_check` 上（**那个函数没有 docstring**）
    → 改回 `set_full_task`（正文本来就是对的）；
    ④ 本条自身这轮的评审结论与「零行为核对」读数**此前没落账** → 即本 Comments。
- **全量**：`python -m pytest -n auto -q` → **5081 passed + 1 skipped / 106.2s**；前端门禁
  `node --test "tests/js/*.test.mjs"` → **1702 passed / 0 fail**（本轮前端零字节，属回归确认）。
- **四张工单收口**：01→`83ef851d`、02→`78d69b80`、03→`884894cb`、04→本条（各带一次
  `chore: 自动更新 CHANGELOG`）。**C6 的尾巴到此结清**：架构评审候选（C2 / C5a / C5 剩余 / C4 /
  C6＋本条）全部落地，只剩 C7 这条不立项的验收尺。
