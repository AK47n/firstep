# 03 — 沙箱「模拟用户机」真机验收 + 当场回写第 1 节

**要做什么：** 从**要发的那棵树**重造一份干净沙箱，按 `docs/agents/local-environment.md` 第 1 节的四个落点
（工具根 / 数据目录 / 端口 / 入口）真进程 ＋ 真 Chromium 走一遍：看的是"用户打开工具会看到什么"，
并核对本轮那两条可见变化真的出现在页面上。结论**当场回写**第 1 节与第 2 节。

**被谁阻塞：** 01（沙箱要从要发的那棵树造出来）。

**状态：** resolved（2026-10-01）

- [ ] **先收 8020**（重建会整树删工具根，带进程删会 `WinError 32`）
- [ ] `python .scratch\full-download\make_sim_sandbox.py`（工具根 `Desktop\firstep-sim`、
      数据目录 `~\.contest_generator_sim` 一起重造）
- [ ] 补回 `sim-run.py`（构建脚本不带它；恢复副本 `.scratch/update-restart-stale-service/sandbox-entry-sim-run.py`）
- [ ] `FIRSTEP_LAUNCHER_PORT=8020` 起沙箱 → `GET /api/health` 版本 = **1.4.3**
- [ ] 真浏览器验收（探针从 `.scratch/release-v1.4.0/probe-sandbox-accept.mjs` 复制一支到本目录并**加本轮检查**）：
      ① 十二页签「有文字的元素」字号 ⊆ 六档角色、正文基准 14px（老口径照旧）；
      ② **三条文字**（`.res-soft` / `.sugg-count` / `.chip.rec.unsel .reason`）的计算色 = 实色 `--muted`、
      **不再有 `opacity`**，且对比度 ≥ 4.5；
      ③ **浅色主题**板图「固定/电源」焊盘取值 = `rgb(175,184,193)`（与「空闲 IO」同一支）；
      ④ 设置页版本 = v1.4.3、版本更新记录页首块 = v1.4.3
- [ ] 真身数据目录**零触碰**：`~\.contest_generator\config.json` mtime 仍是 **2026-09-10 23:28:07**
- [ ] 收尾：收 8020、查无残留 `contest_generator.webapp` / `sim-run` 进程
- [ ] **当场回写** `local-environment.md` 第 1 节（沙箱当前状态 = v1.4.3）与第 2 节（端口实况：
      8000 真身没在跑、8020 已释放）
- [ ] 提交信息中文

## Comments

### 落地事实（2026-10-01）

| 项 | 值 |
|---|---|
| 沙箱（重造后） | `C:\Users\luoji\Desktop\firstep-sim`：构建脚本自报 **2606 个文件 / 289.4 MB**；跑完验收盘上 **2703 个文件 / 292.4 MB**（差额 = 运行时 `__pycache__` ＋补回的 `sim-run.py`） |
| 数据目录 | `C:\Users\luoji\.contest_generator_sim`（构建脚本重造：`updates/` + `config.json` + `recent.json` + `tasks-simulated.json`；**资料库基线没有**——构建脚本故意不真实） |
| 版本读数 | `/api/health` → `{"app":"contest-generator","version":"1.4.3","ok":true}`（起沙箱时与收尾前各读一次，同值） |
| 真机验收 | **50 / 50 全过**（`sandbox-accept.txt` / `.json`）——十二页签正文基准 14px、有文字元素字号 ⊆ 六档；设置页 v1.4.3 ＋ 体积文案是实测口径；版本记录页首块 = v1.4.3 且主题句逐字一致；**⑤ 本轮两条可见变化**：三条文字计算色 = `--muted` 且 `opacity = 1`（两主题）、三条规则在真样式表里**都不再有 `opacity` 声明**、焊盘令牌 亮 `{--pin-pad #d0d7de / --pin-fixed-pad #afb8c1}`、暗 `{#21262d / #171b21}` |
| 收尾 | 8020 已释放（`Stop-Process` 掉 PID 7488；端口只剩 `TIME_WAIT`、无监听）；无残留 `sim-run` 进程；**真身 `~\.contest_generator\config.json` mtime = 2026-09-10 23:28:07（零触碰）** |

### 起沙箱要带 `PYTHONPATH=src`（本轮踩到的第一条）

第一次起沙箱用了 `python sim-run.py`，**40 次 × 2 s 都没起来**，`sandbox-server.log.err` 原文是
`ModuleNotFoundError: No module named 'contest_generator'`。原因：沙箱**没有 `.venv`**（包内故意不建），
走系统 python；而系统 python **没有**装 `contest_generator`（实测 `python -c "import contest_generator"` 直接 ModuleNotFoundError），
包代码在 `firstep-sim\src\` 下、脚本目录又不在 `sys.path` 里。

**正解 = 照用户机口径来**：包内 `start-app.bat` 自己就是 `set PYTHONPATH=src` ＋ `cd /d "%~dp0"`，
所以起沙箱用 `cd firstep-sim; $env:PYTHONPATH="src"; python sim-run.py`（`FIRSTEP_LAUNCHER_PORT=8020`）。
**这条已写进 `local-environment.md` 第 1 节**。

### ⚠ 量具口径那条坑：主题切换撞上 `color` 过渡（第一版白红 1 条，**不是产品的问题**）

第一版探针在 `[light] .sugg-count` 上报红：计算色读成 **暗色**的 `--muted`（`rgb(145,154,164)`，
亮色应为 `rgb(85,94,104)`）。**先自证量具**（照本仓纪律，红了先查量具）——另起一支不作判据的诊断
`probe-diag-sugg-count.mjs`（读数 `probe-diag-sugg-count.txt`）：

- 切到亮色后 `.sugg-count` 的计算色：**+0 ms = `rgb(145,154,164)`（暗色值）→ +50 ms `rgb(132,141,151)`
  → +200 ms `rgb(95,104,114)` → +600 ms `rgb(85,94,104)`（亮色 `--muted`）**——一条干净的过渡曲线；
- 祖先链显示 `.chip` 一族带 `transition: … color 0.15s …`；真样式表里给 `.chip.out` 上色的规则
  **只有一条** `color: var(--muted)`（没有任何"钉在暗色值"的规则）。

⇒ 根因是**量具读得太早**：`.sugg-count` 自己没有 `color` 声明（继承 `.chip.out`），所以比同批另外两条
（各有自己的 `color` 规则、瞬时切换）更容易落进那个 0.15 s 的窗口。**处置**：探针改成"切主题后等 500 ms
再读"（用户看到的就是落定后的样子），产品面**一个字没动**；复跑 **50/50**。
这条与 `ui-density-sitewide` 轮"量具的口径要先自证"是同一类教训，已写进探针注释。

